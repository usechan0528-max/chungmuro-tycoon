from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

from app.config import SEED_DIR
from app.database import dumps_json, get_connection, loads_json


@lru_cache(maxsize=1)
def _historical_domestic_releases() -> dict[str, dict[str, Any]]:
    path = SEED_DIR / "history" / "historical_domestic_releases.json"
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)
    return data if isinstance(data, dict) else {}


def ensure_historical_releases_for_month(year: int, month: int) -> dict[str, int]:
    year = int(year)
    month = int(month)
    with get_connection() as conn:
        protected = _ensure_protected_releases(conn, year, month)
        foreign = _ensure_foreign_releases(conn, year, month)
        domestic = _ensure_domestic_event_releases(conn, year, month)
        conn.commit()
    return {"protected": protected, "foreign": foreign, "domestic_events": domestic}


def backfill_historical_releases_until(start_year: int, start_month: int = 1) -> dict[str, int]:
    """Materialize fixed releases before a late-era start date."""
    start_year = int(start_year)
    start_month = int(start_month or 1)
    with get_connection() as conn:
        months = _past_release_months(conn, start_year, start_month)

    totals = {"protected": 0, "foreign": 0, "domestic_events": 0}
    for year, month in sorted(months):
        result = ensure_historical_releases_for_month(year, month)
        for key in totals:
            totals[key] += int(result.get(key, 0) or 0)
    return totals


def _ensure_protected_releases(conn: Any, year: int, month: int) -> int:
    rows = conn.execute(
        """
        SELECT f.*, p.name_ko AS director_name
        FROM history_protected_director_films f
        LEFT JOIN people p ON p.id = f.director_id
        WHERE f.release_year = ? AND f.release_month = ?
        """,
        (year, month),
    ).fetchall()
    count = 0
    for row in rows:
        data = dict(row)
        metadata = loads_json(data.get("metadata_json"), {})
        payload = {
            **metadata,
            "title": data["title"],
            "releaseDay": int(metadata.get("releaseDay") or 1),
            "runDays": _run_days(metadata.get("scaleId")),
            "directorId": data.get("director_id"),
            "directorName": data.get("director_name"),
            "sourceNote": "보호 한국영화 개봉 기록",
            "description": metadata.get("description") or "게임 내 시간 기준으로 실제 개봉하는 주요 한국영화입니다.",
        }
        if _store_release(
            conn,
            release_id=data["id"],
            title=data["title"],
            market_origin="protected_domestic",
            historical_origin="domestic_protected",
            movie_type="historical_protected",
            year=year,
            month=month,
            genre_id=metadata.get("genreId"),
            scale_id=metadata.get("scaleId"),
            expected=int(metadata.get("expectedAudience", 0) or 0),
            metadata=payload,
        ):
            count += 1
    return count


def _ensure_foreign_releases(conn: Any, year: int, month: int) -> int:
    rows = conn.execute(
        """
        SELECT *
        FROM history_foreign_events
        WHERE year = ? AND (month IS NULL OR month = ?)
        """,
        (year, month),
    ).fetchall()
    count = 0
    for row in rows:
        data = dict(row)
        effects = loads_json(data.get("effects_json"), {})
        genre = loads_json(data.get("genre_json"), [])
        payload = {
            **effects,
            "title": data.get("title_ko") or data.get("title") or data.get("title_en"),
            "releaseDay": int(effects.get("releaseDay") or 1),
            "runDays": 42 if str(data.get("impact_grade") or "").upper() == "S" else 35,
            "genre": genre,
            "titleKo": data.get("title_ko"),
            "titleEn": data.get("title_en"),
            "impactGrade": data.get("impact_grade"),
            "sourceNote": "외화 고정 개봉 기록",
            "description": data.get("description") or "실제 개봉 시기에 맞춰 등장하는 외화 대작입니다.",
        }
        title = payload["title"]
        scale_id = _foreign_scale_id(data)
        expected = int(effects.get("expected_audience") or _foreign_expected(data))
        if _store_release(
            conn,
            release_id=data["id"],
            title=title,
            market_origin="foreign_fixed",
            historical_origin="foreign_fixed",
            movie_type="historical_foreign_fixed",
            year=year,
            month=int(data.get("month") or month),
            genre_id=None,
            scale_id=scale_id,
            expected=expected,
            metadata=payload,
        ):
            count += 1
    return count


def _ensure_domestic_event_releases(conn: Any, year: int, month: int) -> int:
    catalog = _historical_domestic_releases()
    if not catalog:
        return 0
    rows = conn.execute(
        """
        SELECT *
        FROM historical_events
        WHERE year = ? AND month = ?
          AND id IN ({})
        """.format(",".join("?" for _ in catalog)),
        (year, month, *catalog.keys()),
    ).fetchall()
    count = 0
    for row in rows:
        event = dict(row)
        info = dict(catalog[event["id"]])
        payload = {
            **info,
            "eventId": event["id"],
            "fixedLevel": event.get("fixed_level"),
            "eventTitle": event.get("title"),
            "marketImpact": loads_json(event.get("effects_json"), {}),
            "runDays": _run_days(info.get("scaleId")),
            "sourceNote": "한국영화 역사 이벤트 개봉 기록",
        }
        if _skip_if_protected_same_title(conn, info["title"], year, month):
            continue
        if _store_release(
            conn,
            release_id=info["filmId"],
            title=info["title"],
            market_origin="historical_domestic",
            historical_origin="domestic_event",
            movie_type="historical_domestic_event",
            year=year,
            month=month,
            genre_id=info.get("genreId"),
            scale_id=info.get("scaleId"),
            expected=int(info.get("expectedAudience") or 0),
            metadata=payload,
        ):
            count += 1
        _insert_timeline_for_named_people(conn, info["filmId"], year, month, payload)
    return count


def _past_release_months(conn: Any, start_year: int, start_month: int) -> set[tuple[int, int]]:
    date_filter = "year < ? OR (year = ? AND COALESCE(month, 12) < ?)"
    catalog = _historical_domestic_releases()
    queries = [
        (
            """
            SELECT DISTINCT release_year AS year, COALESCE(release_month, 12) AS month
            FROM history_protected_director_films
            WHERE release_year < ?
               OR (release_year = ? AND COALESCE(release_month, 12) < ?)
            """,
            (start_year, start_year, start_month),
        ),
        (
            f"""
            SELECT DISTINCT year, COALESCE(month, 12) AS month
            FROM history_foreign_events
            WHERE {date_filter}
            """,
            (start_year, start_year, start_month),
        ),
    ]
    if catalog:
        queries.append(
            (
                """
                SELECT DISTINCT year, COALESCE(month, 12) AS month
                FROM historical_events
                WHERE id IN ({})
                  AND ({})
                """.format(",".join("?" for _ in catalog), date_filter),
                (*catalog.keys(), start_year, start_year, start_month),
            )
        )
    months: set[tuple[int, int]] = set()
    for query, params in queries:
        for row in conn.execute(query, params).fetchall():
            months.add((int(row["year"]), int(row["month"] or 12)))
    return months


def _store_release(
    conn: Any,
    *,
    release_id: str,
    title: str,
    market_origin: str,
    historical_origin: str,
    movie_type: str,
    year: int,
    month: int,
    genre_id: str | None,
    scale_id: str | None,
    expected: int,
    metadata: dict[str, Any],
) -> bool:
    inserted = _upsert_market_release(
        conn,
        release_id=release_id,
        title=title,
        origin=market_origin,
        year=year,
        month=month,
        genre_id=genre_id,
        scale_id=scale_id,
        expected=expected,
        metadata=metadata,
    )
    _upsert_movie_records(
        conn,
        release_id=release_id,
        title=title,
        origin=historical_origin,
        movie_type=movie_type,
        year=year,
        month=month,
        genre_id=genre_id,
        scale_id=scale_id,
        expected=expected,
        metadata=metadata,
    )
    return inserted


def _upsert_market_release(
    conn: Any,
    *,
    release_id: str,
    title: str,
    origin: str,
    year: int,
    month: int,
    genre_id: str | None,
    scale_id: str | None,
    expected: int,
    metadata: dict[str, Any],
) -> bool:
    before = conn.execute("SELECT 1 FROM market_releases WHERE id = ?", (release_id,)).fetchone()
    conn.execute(
        """
        INSERT OR REPLACE INTO market_releases (
            id, title, origin, release_year, release_month, genre_id, scale_id,
            expected_audience, actual_audience, effects_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, ?)
        """,
        (release_id, title, origin, year, month, genre_id, scale_id, int(expected or 0), dumps_json(metadata)),
    )
    return before is None


def _upsert_movie_records(
    conn: Any,
    *,
    release_id: str,
    title: str,
    origin: str,
    movie_type: str,
    year: int,
    month: int,
    genre_id: str | None,
    scale_id: str | None,
    expected: int,
    metadata: dict[str, Any],
) -> None:
    conn.execute(
        """
        INSERT OR REPLACE INTO movies_historical (
            id, title, origin, release_year, release_month, genre_id, scale_id,
            expected_audience, actual_audience, effects_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, ?)
        """,
        (release_id, title, origin, year, month, genre_id, scale_id, int(expected or 0), dumps_json(metadata)),
    )
    conn.execute(
        """
        INSERT OR REPLACE INTO movies (
            id, title, movie_type, genre_id, scale_id, status, metadata_json
        ) VALUES (?, ?, ?, ?, ?, 'released', ?)
        """,
        (release_id, title, movie_type, genre_id, scale_id, dumps_json(metadata)),
    )


def _insert_timeline_for_named_people(conn: Any, film_id: str, year: int, month: int, metadata: dict[str, Any]) -> None:
    names = _timeline_names(metadata)
    if not names:
        return
    people_by_name = {
        row["name_ko"]: dict(row)
        for row in conn.execute(
            """
            SELECT id, name_ko, type
            FROM people
            WHERE name_ko IN ({})
            """.format(",".join("?" for _ in names)),
            names,
        ).fetchall()
    }
    if metadata.get("directorName") in people_by_name:
        _insert_timeline_once(conn, people_by_name[metadata["directorName"]]["id"], film_id, "director", year, month, metadata)
    for name in metadata.get("actorNames") or []:
        person = people_by_name.get(name)
        if person:
            _insert_timeline_once(conn, person["id"], film_id, "actor", year, month, metadata)


def _insert_timeline_once(
    conn: Any,
    person_id: str,
    film_id: str,
    role: str,
    year: int,
    month: int,
    metadata: dict[str, Any],
) -> None:
    existing = conn.execute(
        """
        SELECT 1
        FROM people_career_timeline
        WHERE person_id = ? AND project_id = ? AND role = ?
        LIMIT 1
        """,
        (person_id, film_id, role),
    ).fetchone()
    if existing:
        return
    conn.execute(
        """
        INSERT INTO people_career_timeline (
            person_id, project_id, role, year, month, status, result_json
        ) VALUES (?, ?, ?, ?, ?, 'released', ?)
        """,
        (
            person_id,
            film_id,
            role,
            year,
            month,
            dumps_json(
                {
                    "title": metadata["title"],
                    "summary": "역사적 흥행/산업 이벤트 작품",
                    "source": "historical_domestic_release",
                    "eventId": metadata.get("eventId"),
                }
            ),
        ),
    )


def _timeline_names(metadata: dict[str, Any]) -> list[str]:
    names: list[str] = []
    director = metadata.get("directorName")
    if director:
        names.append(str(director))
    for name in metadata.get("actorNames") or []:
        if name and str(name) not in names:
            names.append(str(name))
    return names


def _skip_if_protected_same_title(conn: Any, title: str, year: int, month: int) -> bool:
    return (
        conn.execute(
            """
            SELECT 1
            FROM history_protected_director_films
            WHERE title = ? AND release_year = ? AND release_month = ?
            LIMIT 1
            """,
            (title, year, month),
        ).fetchone()
        is not None
    )


def _run_days(scale_id: Any) -> int:
    return {
        "scale_short": 7,
        "scale_independent": 14,
        "scale_low_budget_genre": 21,
        "scale_mid_commercial": 28,
        "scale_large_commercial": 35,
        "scale_tentpole": 42,
    }.get(str(scale_id or ""), 35)


def _foreign_expected(row: dict[str, Any]) -> int:
    return {
        "S": 8_000_000,
        "A": 5_000_000,
        "B": 3_000_000,
    }.get(str(row.get("impact_grade") or "").upper(), 2_500_000)


def _foreign_scale_id(row: dict[str, Any]) -> str:
    return "scale_tentpole" if str(row.get("impact_grade") or "").upper() == "S" else "scale_large_commercial"
