from __future__ import annotations

import re
from typing import Any, Iterable

from app.database import dumps_json, get_connection, loads_json


def bootstrap_world_history_for_start(start_year: int, start_month: int = 1) -> dict[str, int]:
    """Mark fixed history before the selected start date as already happened.

    This is intentionally quiet: it fills world state, filmography, and flags, but
    does not create old news popups for the player who starts later in history.
    """
    start_year = int(start_year)
    start_month = int(start_month or 1)
    with get_connection() as conn:
        counts = {
            "historical_events": _backfill_historical_events(conn, start_year, start_month),
            "protected_films": _backfill_protected_director_films(conn, start_year, start_month),
            "foreign_films": _backfill_foreign_fixed_films(conn, start_year, start_month),
            "kmdb_films": _backfill_kmdb_filmography(conn, start_year, start_month),
            "wikidata_films": _backfill_wikidata_filmography(conn, start_year, start_month),
        }
        _upsert_flag(
            conn,
            "world_bootstrap_until",
            {"year": start_year, "month": start_month, "counts": counts},
            start_year,
            start_month,
        )
        conn.commit()
    return counts


def _backfill_historical_events(conn: Any, start_year: int, start_month: int) -> int:
    count = 0
    rows = conn.execute(
        """
        SELECT *
        FROM historical_events
        WHERE year < ? OR (year = ? AND COALESCE(month, 1) < ?)
        ORDER BY year, COALESCE(month, 1), id
        """,
        (start_year, start_year, start_month),
    ).fetchall()
    for row in rows:
        event_id = str(row["id"])
        if _event_history_exists(conn, event_id, "historical_backfill"):
            continue
        conn.execute(
            """
            INSERT INTO event_history (
                event_id, category, year, month, effects_json
            ) VALUES (?, 'historical_backfill', ?, ?, ?)
            """,
            (event_id, row["year"], row["month"], row["effects_json"]),
        )
        _upsert_flag(
            conn,
            f"history_occurred_{event_id}",
            {
                "title": row["title"],
                "year": row["year"],
                "month": row["month"],
                "fixedLevel": row["fixed_level"],
                "type": row["type"],
                "source": "historical_events",
            },
            row["year"],
            row["month"] or 1,
        )
        unlocks = loads_json(row["unlocks_json"], [])
        for unlock in unlocks if isinstance(unlocks, list) else []:
            _upsert_flag(
                conn,
                f"system_unlocked_{unlock}",
                {"eventId": event_id, "unlocked": True},
                row["year"],
                row["month"] or 1,
            )
        count += 1
    return count


def _backfill_protected_director_films(conn: Any, start_year: int, start_month: int) -> int:
    count = 0
    rows = conn.execute(
        """
        SELECT f.*, p.name_ko AS director_name
        FROM history_protected_director_films f
        LEFT JOIN people p ON p.id = f.director_id
        WHERE f.release_year IS NOT NULL
          AND (
            f.release_year < ?
            OR (f.release_year = ? AND COALESCE(f.release_month, 12) < ?)
          )
        ORDER BY f.release_year, COALESCE(f.release_month, 12), f.id
        """,
        (start_year, start_year, start_month),
    ).fetchall()
    for row in rows:
        metadata = loads_json(row["metadata_json"], {})
        film_id = str(row["id"])
        inserted = _insert_historical_movie(
            conn,
            movie_id=film_id,
            title=row["title"],
            origin="domestic_protected",
            movie_type="historical_protected",
            year=int(row["release_year"]),
            month=int(row["release_month"] or 12),
            genre_id=metadata.get("genreId"),
            scale_id=metadata.get("scaleId"),
            expected_audience=int(metadata.get("expectedAudience", 0) or 0),
            effects=metadata,
            metadata={
                "releaseYear": row["release_year"],
                "releaseMonth": row["release_month"],
                "directorId": row["director_id"],
                "directorName": row["director_name"],
                "origin": "domestic_protected",
            },
            market_origin="protected_domestic",
        )
        if row["director_id"]:
            _insert_timeline_once(
                conn,
                person_id=row["director_id"],
                project_id=film_id,
                role="director",
                year=row["release_year"],
                month=row["release_month"],
                result={
                    "title": row["title"],
                    "summary": "주요 필모그래피",
                    "source": "history_protected_director_films",
                    "releaseYear": row["release_year"],
                    "releaseMonth": row["release_month"],
                },
            )
        if inserted:
            count += 1
    return count


def _backfill_foreign_fixed_films(conn: Any, start_year: int, start_month: int) -> int:
    count = 0
    rows = conn.execute(
        """
        SELECT *
        FROM history_foreign_events
        WHERE year < ? OR (year = ? AND COALESCE(month, 12) < ?)
        ORDER BY year, COALESCE(month, 12), id
        """,
        (start_year, start_year, start_month),
    ).fetchall()
    for row in rows:
        effects = loads_json(row["effects_json"], {})
        genre = loads_json(row["genre_json"], [])
        inserted = _insert_historical_movie(
            conn,
            movie_id=row["id"],
            title=row["title"],
            origin="foreign_fixed",
            movie_type="historical_foreign_fixed",
            year=row["year"],
            month=row["month"] or 12,
            genre_id=None,
            scale_id=None,
            expected_audience=int(effects.get("expected_audience", 0) or 0),
            effects=effects,
            metadata={
                "releaseYear": row["year"],
                "releaseMonth": row["month"],
                "titleKo": row["title_ko"],
                "titleEn": row["title_en"],
                "impactGrade": row["impact_grade"],
                "genre": genre,
                "origin": "foreign_fixed",
            },
            market_origin="foreign_fixed",
        )
        if inserted:
            count += 1
    return count


def _backfill_kmdb_filmography(conn: Any, start_year: int, start_month: int) -> int:
    people_by_name = _people_by_name(conn)
    rows = conn.execute(
        """
        SELECT *
        FROM staging_kmdb_movies
        WHERE COALESCE(match_year, prod_year) IS NOT NULL
          AND (
            COALESCE(match_year, prod_year) < ?
            OR (
              COALESCE(match_year, prod_year) = ?
              AND COALESCE(CAST(substr(release_date, 5, 2) AS INTEGER), 12) < ?
            )
          )
        ORDER BY COALESCE(match_year, prod_year), title_ko
        """,
        (start_year, start_year, start_month),
    ).fetchall()
    count = 0
    for row in rows:
        title = _clean_title(row["title_ko"] or row["title_en"])
        if not title:
            continue
        year, month = _kmdb_year_month(row)
        metadata = {
            "releaseYear": year,
            "releaseMonth": month,
            "titleKo": row["title_ko"],
            "titleEn": row["title_en"],
            "directorNames": loads_json(row["director_names_json"], []),
            "actorNames": loads_json(row["actor_names_json"], []),
            "genre": row["genre"],
            "runtime": row["runtime"],
            "rating": row["rating"],
            "plot": row["plot"],
            "productionCompany": row["production_company"],
            "distributionCompany": row["distribution_company"],
            "origin": "kmdb",
        }
        inserted = _insert_historical_movie(
            conn,
            movie_id=row["kmdb_id"],
            title=title,
            origin="kmdb",
            movie_type="historical_kmdb",
            year=year,
            month=month,
            genre_id=None,
            scale_id=None,
            expected_audience=0,
            effects=metadata,
            metadata=metadata,
            market_origin=None,
        )
        director_names = loads_json(row["director_names_json"], [])
        actor_names = loads_json(row["actor_names_json"], [])
        for name in _names(director_names):
            person = people_by_name.get(_normalize_name(name))
            if person and person["type"] == "director":
                if _has_protected_director_work(conn, person["id"], title, year):
                    continue
                _insert_timeline_once(
                    conn,
                    person_id=person["id"],
                    project_id=row["kmdb_id"],
                    role="director",
                    year=year,
                    month=month,
                    result={"title": title, "summary": "KMDb 필모그래피", "source": "KMDb"},
                )
        for name in _names(actor_names):
            person = people_by_name.get(_normalize_name(name))
            if person and person["type"] == "actor":
                _insert_timeline_once(
                    conn,
                    person_id=person["id"],
                    project_id=row["kmdb_id"],
                    role="actor",
                    year=year,
                    month=month,
                    result={"title": title, "summary": "KMDb 출연 기록", "source": "KMDb"},
                )
        if inserted:
            count += 1
    return count


def _backfill_wikidata_filmography(conn: Any, start_year: int, start_month: int) -> int:
    people_by_name = _people_by_name(conn)
    rows = conn.execute(
        """
        SELECT *
        FROM wikidata_movies
        WHERE year IS NOT NULL
          AND (
            year < ?
            OR (
              year = ?
              AND COALESCE(CAST(substr(release_date, 6, 2) AS INTEGER), 12) < ?
            )
          )
        ORDER BY year, title_ko
        """,
        (start_year, start_year, start_month),
    ).fetchall()
    count = 0
    for row in rows:
        title = _clean_title(row["title_ko"] or row["title_en"])
        if not title:
            continue
        year = int(row["year"])
        month = _month_from_date(row["release_date"], default=12)
        metadata = {
            "releaseYear": year,
            "releaseMonth": month,
            "titleKo": row["title_ko"],
            "titleEn": row["title_en"],
            "director": loads_json(row["director_json"], []),
            "actor": loads_json(row["actor_json"], []),
            "genre": loads_json(row["genre_json"], []),
            "country": loads_json(row["country_json"], []),
            "imdbId": row["imdb_id"],
            "wikipediaUrl": row["wikipedia_url"],
            "origin": "wikidata",
        }
        inserted = _insert_historical_movie(
            conn,
            movie_id=row["qid"],
            title=title,
            origin="wikidata",
            movie_type="historical_wikidata",
            year=year,
            month=month,
            genre_id=None,
            scale_id=None,
            expected_audience=0,
            effects=metadata,
            metadata=metadata,
            market_origin=None,
        )
        for name in _wikidata_entity_names(loads_json(row["director_json"], [])):
            person = people_by_name.get(_normalize_name(name))
            if person and person["type"] == "director":
                if _has_protected_director_work(conn, person["id"], title, year):
                    continue
                _insert_timeline_once(
                    conn,
                    person_id=person["id"],
                    project_id=row["qid"],
                    role="director",
                    year=year,
                    month=month,
                    result={"title": title, "summary": "Wikidata 필모그래피", "source": "Wikidata"},
                )
        for name in _wikidata_entity_names(loads_json(row["actor_json"], [])):
            person = people_by_name.get(_normalize_name(name))
            if person and person["type"] == "actor":
                _insert_timeline_once(
                    conn,
                    person_id=person["id"],
                    project_id=row["qid"],
                    role="actor",
                    year=year,
                    month=month,
                    result={"title": title, "summary": "Wikidata 출연 기록", "source": "Wikidata"},
                )
        if inserted:
            count += 1
    return count


def _insert_historical_movie(
    conn: Any,
    *,
    movie_id: str,
    title: str,
    origin: str,
    movie_type: str,
    year: int,
    month: int | None,
    genre_id: str | None,
    scale_id: str | None,
    expected_audience: int,
    effects: dict[str, Any],
    metadata: dict[str, Any],
    market_origin: str | None,
) -> bool:
    if market_origin:
        conn.execute(
            """
            INSERT OR IGNORE INTO market_releases (
                id, title, origin, release_year, release_month, genre_id,
                scale_id, expected_audience, effects_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (movie_id, title, market_origin, year, month, genre_id, scale_id, expected_audience, dumps_json(effects)),
        )
    inserted = conn.execute(
        """
        INSERT OR IGNORE INTO movies_historical (
            id, title, origin, release_year, release_month, genre_id,
            scale_id, expected_audience, effects_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (movie_id, title, origin, year, month, genre_id, scale_id, expected_audience, dumps_json(effects)),
    ).rowcount
    conn.execute(
        """
        INSERT OR IGNORE INTO movies (
            id, title, movie_type, genre_id, scale_id, status, metadata_json
        ) VALUES (?, ?, ?, ?, ?, 'released', ?)
        """,
        (movie_id, title, movie_type, genre_id, scale_id, dumps_json(metadata)),
    )
    return bool(inserted)


def _insert_timeline_once(
    conn: Any,
    *,
    person_id: str,
    project_id: str,
    role: str,
    year: int | None,
    month: int | None,
    result: dict[str, Any],
) -> None:
    exists = conn.execute(
        """
        SELECT 1
        FROM people_career_timeline
        WHERE person_id = ? AND project_id = ? AND role = ? AND status = 'released'
        LIMIT 1
        """,
        (person_id, project_id, role),
    ).fetchone()
    if exists:
        return
    if _timeline_title_exists(conn, person_id, role, year, result.get("title")):
        return
    conn.execute(
        """
        INSERT INTO people_career_timeline (
            person_id, project_id, role, year, month, status, result_json
        ) VALUES (?, ?, ?, ?, ?, 'released', ?)
        """,
        (person_id, project_id, role, year, month, dumps_json(result)),
    )


def _has_protected_director_work(conn: Any, person_id: str, title: str, year: int | None) -> bool:
    rows = conn.execute(
        """
        SELECT title
        FROM history_protected_director_films
        WHERE director_id = ?
          AND release_year = ?
        """,
        (person_id, year),
    ).fetchall()
    normalized_title = _normalize_title(title)
    return any(_normalize_title(row["title"]) == normalized_title for row in rows)


def _timeline_title_exists(
    conn: Any,
    person_id: str,
    role: str,
    year: int | None,
    title: Any,
) -> bool:
    normalized_title = _normalize_title(title)
    if not normalized_title:
        return False
    rows = conn.execute(
        """
        SELECT result_json
        FROM people_career_timeline
        WHERE person_id = ?
          AND role = ?
          AND status = 'released'
          AND COALESCE(year, 0) = COALESCE(?, 0)
        """,
        (person_id, role, year),
    ).fetchall()
    for row in rows:
        result = loads_json(row["result_json"], {})
        if _normalize_title(result.get("title")) == normalized_title:
            return True
    return False


def _event_history_exists(conn: Any, event_id: str, category: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM event_history WHERE event_id = ? AND category = ? LIMIT 1",
        (event_id, category),
    ).fetchone()
    return row is not None


def _upsert_flag(conn: Any, key: str, value: dict[str, Any], year: int | None, month: int | None) -> None:
    for table_name in ("story_flags", "save_event_flags"):
        conn.execute(
            f"""
            INSERT OR REPLACE INTO {table_name} (
                key, value_json, updated_year, updated_month
            ) VALUES (?, ?, ?, ?)
            """,
            (key, dumps_json(value), year, month),
        )


def _people_by_name(conn: Any) -> dict[str, dict[str, Any]]:
    rows = conn.execute("SELECT id, name_ko, name_en, type FROM people").fetchall()
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        data = dict(row)
        for name in (row["name_ko"], row["name_en"]):
            normalized = _normalize_name(name)
            if normalized:
                result.setdefault(normalized, data)
    return result


def _kmdb_year_month(row: Any) -> tuple[int, int]:
    year = int(row["match_year"] or row["prod_year"] or 1980)
    month = _month_from_kmdb_date(row["release_date"], default=12)
    return year, month


def _month_from_kmdb_date(value: Any, default: int = 12) -> int:
    text = str(value or "")
    if len(text) >= 6 and text[:6].isdigit():
        month = int(text[4:6])
        return month if 1 <= month <= 12 else default
    return default


def _month_from_date(value: Any, default: int = 12) -> int:
    text = str(value or "")
    match = re.match(r"^\d{4}-(\d{2})", text)
    if match:
        month = int(match.group(1))
        return month if 1 <= month <= 12 else default
    return _month_from_kmdb_date(text.replace("-", ""), default=default)


def _names(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if not isinstance(value, Iterable):
        return []
    names: list[str] = []
    for item in value:
        if isinstance(item, str):
            names.append(item)
        elif isinstance(item, dict):
            for key in ("nameKo", "name_ko", "labelKo", "name", "label", "nameEn", "name_en"):
                if item.get(key):
                    names.append(str(item[key]))
                    break
    return [_clean_title(name) for name in names if _clean_title(name)]


def _wikidata_entity_names(value: Any) -> list[str]:
    return _names(value)


def _clean_title(value: Any) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    text = re.sub(r"<!HS>|<!HE>|!HS|!HE", "", text).strip()
    return text


def _normalize_name(value: Any) -> str:
    return re.sub(r"[\s·.\-_/()]+", "", str(value or "").strip()).lower()


def _normalize_title(value: Any) -> str:
    text = _clean_title(value)
    return re.sub(r"[\s·.\-_/():,.'\"!?]+", "", text).lower()
