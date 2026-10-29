from __future__ import annotations

from app.database import dumps_json, get_connection, loads_json
from app.services.game_state import clamp
from app.services.market_service import ensure_market_state_with_connection


def apply_historical_events_for_month(year: int, month: int) -> list[str]:
    applied: list[str] = []
    with get_connection() as conn:
        events = conn.execute(
            """
            SELECT * FROM historical_events
            WHERE year = ? AND (month IS NULL OR month = ?)
              AND (type IS NULL OR type != 'foreign_market')
            ORDER BY month, id
            """,
            (year, month),
        ).fetchall()
        if not events:
            return applied
        market = ensure_market_state_with_connection(conn, year, month)
        values = dict(market)
        modifiers = loads_json(values.get("modifiers_json"), {})
        for event in events:
            effects = loads_json(event["effects_json"], {})
            _apply_domestic_event_impact(values, modifiers, effects)
            unlocks = loads_json(event["unlocks_json"], []) if "unlocks_json" in event.keys() else []
            _write_history_unlocks(conn, event["id"], unlocks, year, month)
            conn.execute(
                """
                INSERT INTO news_items (
                    year, month, title, body, source_type, target_type,
                    target_id, effects_json
                ) VALUES (?, ?, ?, ?, 'historical', 'market', ?, ?)
                """,
                (
                    year,
                    month,
                    event["title"],
                    event["description"],
                    event["id"],
                    event["effects_json"],
                ),
            )
            conn.execute(
                """
                INSERT INTO systems_press (
                    year, month, title, body, source_type, target_type,
                    target_id, effects_json
                ) VALUES (?, ?, ?, ?, 'historical', 'market', ?, ?)
                """,
                (
                    year,
                    month,
                    event["title"],
                    event["description"],
                    event["id"],
                    event["effects_json"],
                ),
            )
            applied.append(event["id"])
        conn.execute(
            """
            UPDATE market_state
            SET theater_demand = ?, ott_power = ?, foreign_competition = ?,
                korean_film_trust = ?, modifiers_json = ?
            WHERE year = ? AND month = ?
            """,
            (
                values["theater_demand"],
                values["ott_power"],
                values["foreign_competition"],
                values["korean_film_trust"],
                dumps_json(modifiers),
                year,
                month,
            ),
        )
        conn.execute(
            """
            INSERT OR REPLACE INTO save_market_state (
                year, month, theater_demand, ott_power, foreign_competition,
                korean_film_trust, genre_trends_json, modifiers_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                year,
                month,
                values["theater_demand"],
                values["ott_power"],
                values["foreign_competition"],
                values["korean_film_trust"],
                values.get("genre_trends_json") or "{}",
                dumps_json(modifiers),
            ),
        )
        conn.commit()
    return applied


def apply_protected_director_films_for_month(year: int, month: int) -> list[str]:
    applied: list[str] = []
    with get_connection() as conn:
        films = conn.execute(
            """
            SELECT f.*, p.name_ko AS director_name
            FROM history_protected_director_films f
            LEFT JOIN people p ON p.id = f.director_id
            WHERE f.release_year = ? AND f.release_month = ?
            ORDER BY f.id
            """,
            (year, month),
        ).fetchall()
        if not films:
            return applied

        market = _ensure_market_state(conn, year, month)
        values = dict(market)
        modifiers = loads_json(values.get("modifiers_json"), {})
        genre_trends = loads_json(values.get("genre_trends_json"), {})

        for film in films:
            metadata = loads_json(film["metadata_json"], {})
            inserted = conn.execute(
                """
                INSERT OR IGNORE INTO market_releases (
                    id, title, origin, release_year, release_month, genre_id,
                    scale_id, expected_audience, effects_json
                ) VALUES (?, ?, 'protected_domestic', ?, ?, ?, ?, ?, ?)
                """,
                (
                    film["id"],
                    film["title"],
                    film["release_year"],
                    film["release_month"],
                    metadata.get("genreId"),
                    metadata.get("scaleId"),
                    int(metadata.get("expectedAudience", 0)),
                    dumps_json(metadata.get("marketImpact", {})),
                ),
            ).rowcount
            conn.execute(
                """
                INSERT OR IGNORE INTO movies_historical (
                    id, title, origin, release_year, release_month, genre_id,
                    scale_id, expected_audience, effects_json
                ) VALUES (?, ?, 'domestic_protected', ?, ?, ?, ?, ?, ?)
                """,
                (
                    film["id"],
                    film["title"],
                    film["release_year"],
                    film["release_month"],
                    metadata.get("genreId"),
                    metadata.get("scaleId"),
                    int(metadata.get("expectedAudience", 0)),
                    dumps_json(metadata),
                ),
            )
            conn.execute(
                """
                INSERT OR IGNORE INTO movies (
                    id, title, movie_type, genre_id, scale_id, status,
                    metadata_json
                ) VALUES (?, ?, 'historical_protected', ?, ?, 'released', ?)
                """,
                (
                    film["id"],
                    film["title"],
                    metadata.get("genreId"),
                    metadata.get("scaleId"),
                    dumps_json(
                        {
                            "directorId": film["director_id"],
                            "directorName": film["director_name"],
                            "directorProtectionLevel": metadata.get("directorProtectionLevel"),
                            "historicalFilmographyLocked": metadata.get("historicalFilmographyLocked", False),
                            "protectionLevel": film["protection_level"],
                            "allowedPlayerResponses": metadata.get("allowedPlayerResponses", []),
                        }
                    ),
                ),
            )
            if not inserted:
                continue

            _apply_protected_release_impact(values, modifiers, genre_trends, metadata.get("marketImpact", {}))
            body = (
                f"{film['director_name'] or '감독 미상'} 감독의 주요 작품 "
                f"'{film['title']}'이 개봉했다. "
                "동시기 시장에서는 경쟁, 편승, 개봉 시기 조정이 중요해졌다."
            )
            conn.execute(
                """
                INSERT INTO news_items (
                    year, month, title, body, source_type, target_type,
                    target_id, effects_json
                ) VALUES (?, ?, ?, ?, 'protected_history', 'film', ?, ?)
                """,
                (
                    year,
                    month,
                    f"주요 한국영화 개봉: {film['title']}",
                    body,
                    film["id"],
                    dumps_json(metadata),
                ),
            )
            conn.execute(
                """
                INSERT INTO systems_press (
                    year, month, title, body, source_type, target_type,
                    target_id, effects_json
                ) VALUES (?, ?, ?, ?, 'protected_history', 'film', ?, ?)
                """,
                (
                    year,
                    month,
                    f"주요 한국영화 개봉: {film['title']}",
                    body,
                    film["id"],
                    dumps_json(metadata),
                ),
            )
            applied.append(film["id"])

        conn.execute(
            """
            UPDATE market_state
            SET theater_demand = ?, ott_power = ?, foreign_competition = ?,
                korean_film_trust = ?, genre_trends_json = ?, modifiers_json = ?
            WHERE year = ? AND month = ?
            """,
            (
                values["theater_demand"],
                values["ott_power"],
                values["foreign_competition"],
                values["korean_film_trust"],
                dumps_json(genre_trends),
                dumps_json(modifiers),
                year,
                month,
            ),
        )
        conn.execute(
            """
            INSERT OR REPLACE INTO save_market_state (
                year, month, theater_demand, ott_power, foreign_competition,
                korean_film_trust, genre_trends_json, modifiers_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                year,
                month,
                values["theater_demand"],
                values["ott_power"],
                values["foreign_competition"],
                values["korean_film_trust"],
                dumps_json(genre_trends),
                dumps_json(modifiers),
            ),
        )
        conn.commit()
    return applied


def apply_foreign_fixed_events_for_month(year: int, month: int) -> list[str]:
    applied: list[str] = []
    with get_connection() as conn:
        events = conn.execute(
            """
            SELECT * FROM history_foreign_events
            WHERE year = ? AND (month IS NULL OR month = ?)
            ORDER BY month, id
            """,
            (year, month),
        ).fetchall()
        if not events:
            return applied

        market = _ensure_market_state(conn, year, month)
        values = dict(market)
        modifiers = loads_json(values.get("modifiers_json"), {})

        for event in events:
            effects = loads_json(event["effects_json"], {})
            genre = loads_json(event["genre_json"], []) if "genre_json" in event.keys() else []
            release_id = event["id"]
            inserted = conn.execute(
                """
                INSERT OR IGNORE INTO market_releases (
                    id, title, origin, release_year, release_month,
                    expected_audience, effects_json
                ) VALUES (?, ?, 'foreign_fixed', ?, ?, ?, ?)
                """,
                (
                    release_id,
                    event["title"],
                    event["year"],
                    event["month"],
                    int(effects.get("expected_audience", 0)),
                    event["effects_json"],
                ),
            ).rowcount
            conn.execute(
                """
                INSERT OR IGNORE INTO movies_historical (
                    id, title, origin, release_year, release_month,
                    expected_audience, effects_json
                ) VALUES (?, ?, 'foreign_fixed', ?, ?, ?, ?)
                """,
                (
                    release_id,
                    event["title"],
                    event["year"],
                    event["month"],
                    int(effects.get("expected_audience", 0)),
                    event["effects_json"],
                ),
            )
            conn.execute(
                """
                INSERT OR IGNORE INTO movies (
                    id, title, movie_type, status, metadata_json
                ) VALUES (?, ?, 'historical_foreign_fixed', 'released', ?)
                """,
                (
                    release_id,
                    event["title"],
                    dumps_json(
                        {
                            "releaseYear": event["year"],
                            "releaseMonth": event["month"],
                            "fixedLevel": event["fixed_level"],
                            "titleKo": event["title_ko"] if "title_ko" in event.keys() else event["title"],
                            "titleEn": event["title_en"] if "title_en" in event.keys() else None,
                            "impactGrade": event["impact_grade"] if "impact_grade" in event.keys() else None,
                            "genre": genre,
                            "origin": "foreign_fixed",
                        }
                    ),
                ),
            )
            if inserted:
                _apply_foreign_release_impact(values, modifiers, effects)
                conn.execute(
                    """
                    INSERT INTO news_items (
                        year, month, title, body, source_type, target_type,
                        target_id, effects_json
                    ) VALUES (?, ?, ?, ?, 'foreign_fixed', 'film', ?, ?)
                    """,
                    (
                        event["year"],
                        event["month"] or month,
                        f"외화 대작 개봉: {event['title']}",
                        event["description"],
                        release_id,
                        event["effects_json"],
                    ),
                )
                conn.execute(
                    """
                    INSERT INTO systems_press (
                        year, month, title, body, source_type, target_type,
                        target_id, effects_json
                    ) VALUES (?, ?, ?, ?, 'foreign_fixed', 'film', ?, ?)
                    """,
                    (
                        event["year"],
                        event["month"] or month,
                        f"외화 대작 개봉: {event['title']}",
                        event["description"],
                        release_id,
                        event["effects_json"],
                    ),
                )
                applied.append(release_id)
        if applied:
            conn.execute(
                """
                UPDATE market_state
                SET theater_demand = ?, ott_power = ?, foreign_competition = ?,
                    korean_film_trust = ?, modifiers_json = ?
                WHERE year = ? AND month = ?
                """,
                (
                    values["theater_demand"],
                    values["ott_power"],
                    values["foreign_competition"],
                    values["korean_film_trust"],
                    dumps_json(modifiers),
                    year,
                    month,
                ),
            )
            conn.execute(
                """
                INSERT OR REPLACE INTO save_market_state (
                    year, month, theater_demand, ott_power, foreign_competition,
                    korean_film_trust, genre_trends_json, modifiers_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    year,
                    month,
                    values["theater_demand"],
                    values["ott_power"],
                    values["foreign_competition"],
                    values["korean_film_trust"],
                    values.get("genre_trends_json") or "{}",
                    dumps_json(modifiers),
                ),
            )
        conn.commit()
    return applied


def _ensure_market_state(conn, year: int, month: int):
    return ensure_market_state_with_connection(conn, year, month)


def _apply_protected_release_impact(
    values: dict,
    modifiers: dict,
    genre_trends: dict,
    impact: dict,
) -> None:
    for key, value in impact.items():
        if key in {"theater_demand", "ott_power", "foreign_competition", "korean_film_trust"}:
            values[key] = clamp(int(values.get(key, 50)) + int(value))
        elif key.endswith("_trend"):
            genre_trends[key] = int(genre_trends.get(key, 0)) + int(value)
        else:
            modifiers[key] = int(modifiers.get(key, 0)) + int(value)


DOMESTIC_EFFECT_KEY_MAP = {
    "theaterDemand": "theater_demand",
    "ottPower": "ott_power",
    "foreignCompetition": "foreign_competition",
    "koreanFilmTrust": "korean_film_trust",
    "distributionPower": "distribution_power",
    "firstWeekImportance": "first_week_importance",
    "actionInvestment": "action_investment",
    "blockbusterConfidence": "blockbuster_confidence",
    "budgetInflation": "budget_inflation",
}


def _apply_domestic_event_impact(values: dict, modifiers: dict, impact: dict) -> None:
    for raw_key, value in impact.items():
        key = DOMESTIC_EFFECT_KEY_MAP.get(raw_key, raw_key)
        if key in {"theater_demand", "ott_power", "foreign_competition", "korean_film_trust"}:
            values[key] = clamp(int(values.get(key, 50)) + int(value))
        else:
            modifiers[key] = int(modifiers.get(key, 0)) + int(value)


def _write_history_unlocks(conn, event_id: str, unlocks: list[str], year: int, month: int) -> None:
    for unlock in unlocks:
        value = {
            "unlocked": True,
            "sourceEventId": event_id,
        }
        for table in ("story_flags", "save_event_flags"):
            conn.execute(
                f"""
                INSERT OR REPLACE INTO {table} (
                    key, value_json, updated_year, updated_month
                ) VALUES (?, ?, ?, ?)
                """,
                (f"system_unlocked_{unlock}", dumps_json(value), year, month),
            )


FOREIGN_EFFECT_KEY_MAP = {
    "foreignCompetition": "foreign_competition",
    "specialFormatDemand": "special_format_demand",
    "vfxExpectation": "vfx_expectation",
    "familyAdventureDemand": "family_adventure_demand",
    "romanceBlockbusterDemand": "romance_blockbuster_demand",
    "longRunBoxOfficeModel": "long_run_boxoffice_model",
    "koreanBlockbusterPressure": "korean_blockbuster_pressure",
}


def _apply_foreign_release_impact(values: dict, modifiers: dict, impact: dict) -> None:
    for raw_key, value in impact.items():
        key = FOREIGN_EFFECT_KEY_MAP.get(raw_key, raw_key)
        if key in {"theater_demand", "ott_power", "foreign_competition", "korean_film_trust"}:
            values[key] = clamp(int(values.get(key, 50)) + int(value))
        else:
            modifiers[key] = int(modifiers.get(key, 0)) + int(value)
