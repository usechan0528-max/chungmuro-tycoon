from __future__ import annotations

from typing import Any

from app.database import get_connection, loads_json
from app.services.world_service import (
    apply_foreign_fixed_events_for_month as _apply_foreign_fixed_events_for_month,
)
from app.services.world_service import (
    apply_historical_events_for_month as _apply_historical_events_for_month,
)
from app.services.world_service import (
    apply_protected_director_films_for_month as _apply_protected_director_films_for_month,
)


def apply_history_for_month(year: int, month: int) -> dict[str, list[str]]:
    return {
        "historical_events": apply_historical_events_for_month(year, month),
        "protected_director_films": apply_protected_director_films_for_month(year, month),
        "foreign_fixed_events": apply_foreign_fixed_events_for_month(year, month),
    }


def apply_historical_events_for_month(year: int, month: int) -> list[str]:
    return _apply_historical_events_for_month(year, month)


def apply_protected_director_films_for_month(year: int, month: int) -> list[str]:
    return _apply_protected_director_films_for_month(year, month)


def apply_foreign_fixed_events_for_month(year: int, month: int) -> list[str]:
    return _apply_foreign_fixed_events_for_month(year, month)


def list_historical_events(
    start_year: int | None = None,
    end_year: int | None = None,
    *,
    until_year: int | None = None,
    until_month: int | None = None,
) -> list[dict[str, Any]]:
    query = "SELECT * FROM historical_events"
    params: list[int] = []
    clauses: list[str] = []
    if start_year is not None:
        clauses.append("year >= ?")
        params.append(start_year)
    if end_year is not None:
        clauses.append("year <= ?")
        params.append(end_year)
    _append_occurred_clause(clauses, params, "year", "month", until_year, until_month)
    if clauses:
        query += " WHERE " + " AND ".join(clauses)
    query += " ORDER BY year, month, title"
    with get_connection() as conn:
        rows = conn.execute(query, params).fetchall()
    events: list[dict[str, Any]] = []
    for row in rows:
        event = dict(row)
        if "effects_json" in event:
            event["effects"] = loads_json(event.pop("effects_json"), {})
        if "unlocks_json" in event:
            event["unlocks"] = loads_json(event.pop("unlocks_json"), [])
        events.append(event)
    return events


def list_protected_director_films(
    *,
    until_year: int | None = None,
    until_month: int | None = None,
) -> list[dict[str, Any]]:
    clauses: list[str] = []
    params: list[int] = []
    _append_occurred_clause(clauses, params, "f.release_year", "f.release_month", until_year, until_month)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    with get_connection() as conn:
        rows = conn.execute(
            f"""
            SELECT f.*, p.name_ko AS director_name
            FROM history_protected_director_films f
            LEFT JOIN people p ON p.id = f.director_id
            {where}
            ORDER BY f.release_year, f.release_month, f.title
            """,
            params,
        ).fetchall()
    films: list[dict[str, Any]] = []
    for row in rows:
        film = dict(row)
        film["metadata"] = loads_json(film.pop("metadata_json"), {})
        films.append(film)
    return films


def list_foreign_fixed_events(
    *,
    until_year: int | None = None,
    until_month: int | None = None,
) -> list[dict[str, Any]]:
    clauses: list[str] = []
    params: list[int] = []
    _append_occurred_clause(clauses, params, "year", "month", until_year, until_month)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    with get_connection() as conn:
        rows = conn.execute(
            f"""
            SELECT * FROM history_foreign_events
            {where}
            ORDER BY year, month, title
            """,
            params,
        ).fetchall()
    events: list[dict[str, Any]] = []
    for row in rows:
        event = dict(row)
        event["effects"] = loads_json(event.pop("effects_json"), {})
        if "same_window_penalties_json" in event:
            event["sameWindowPenalties"] = loads_json(event.pop("same_window_penalties_json"), {})
        if "genre_json" in event:
            event["genre"] = loads_json(event.pop("genre_json"), [])
        events.append(event)
    return events


def list_policy_events(*, until_year: int | None = None, until_month: int | None = None) -> list[dict[str, Any]]:
    return _list_history_category_table("history_policy_events", until_year=until_year, until_month=until_month)


def list_market_events(*, until_year: int | None = None, until_month: int | None = None) -> list[dict[str, Any]]:
    return _list_history_category_table("history_market_events", until_year=until_year, until_month=until_month)


def list_distribution_events(*, until_year: int | None = None, until_month: int | None = None) -> list[dict[str, Any]]:
    return _list_industry_event_table("history_distribution_events", until_year=until_year, until_month=until_month)


def list_theater_events(*, until_year: int | None = None, until_month: int | None = None) -> list[dict[str, Any]]:
    return _list_industry_event_table("history_theater_events", until_year=until_year, until_month=until_month)


def list_premium_format_events(*, until_year: int | None = None, until_month: int | None = None) -> list[dict[str, Any]]:
    return _list_industry_event_table("history_premium_format_events", until_year=until_year, until_month=until_month)


def list_ticket_price_history(*, until_year: int | None = None) -> list[dict[str, Any]]:
    where = "WHERE year <= ?" if until_year is not None else ""
    params = [int(until_year)] if until_year is not None else []
    with get_connection() as conn:
        rows = conn.execute(
            f"""
            SELECT * FROM history_ticket_prices
            {where}
            ORDER BY year
            """,
            params,
        ).fetchall()
    return [dict(row) for row in rows]


def _list_history_category_table(
    table_name: str,
    *,
    until_year: int | None = None,
    until_month: int | None = None,
) -> list[dict[str, Any]]:
    clauses: list[str] = []
    params: list[int] = []
    _append_occurred_clause(clauses, params, "year", "month", until_year, until_month)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    with get_connection() as conn:
        rows = conn.execute(
            f"""
            SELECT * FROM {table_name}
            {where}
            ORDER BY year, month, title
            """,
            params,
        ).fetchall()
    events: list[dict[str, Any]] = []
    for row in rows:
        event = dict(row)
        event["effects"] = loads_json(event.pop("effects_json"), {})
        if "unlocks_json" in event:
            event["unlocks"] = loads_json(event.pop("unlocks_json"), [])
        events.append(event)
    return events


def _list_industry_event_table(
    table_name: str,
    *,
    until_year: int | None = None,
    until_month: int | None = None,
) -> list[dict[str, Any]]:
    clauses: list[str] = []
    params: list[int] = []
    _append_occurred_clause(clauses, params, "year", "month", until_year, until_month)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    with get_connection() as conn:
        rows = conn.execute(
            f"""
            SELECT * FROM {table_name}
            {where}
            ORDER BY year, month, title
            """,
            params,
        ).fetchall()
    events: list[dict[str, Any]] = []
    for row in rows:
        event = dict(row)
        event["effects"] = loads_json(event.pop("effects_json"), {})
        event["unlocks"] = loads_json(event.pop("unlocks_json"), [])
        event["format"] = loads_json(event.pop("format_json"), [])
        event["relatedCompanies"] = loads_json(event.pop("related_companies_json"), [])
        event["organizationId"] = _event_organization_id(event)
        events.append(event)
    return events


def _event_organization_id(event: dict[str, Any]) -> str | None:
    from app.services.organization_service import resolve_organization_id

    candidates = [
        event.get("company"),
        event.get("chain"),
        *(event.get("relatedCompanies") or []),
    ]
    for candidate in candidates:
        org_id = resolve_organization_id(candidate)
        if org_id:
            return org_id
    return None


def _append_occurred_clause(
    clauses: list[str],
    params: list[int],
    year_column: str,
    month_column: str,
    until_year: int | None,
    until_month: int | None,
) -> None:
    if until_year is None:
        return
    month = int(until_month or 12)
    clauses.append(
        f"({year_column} < ? OR ({year_column} = ? AND COALESCE({month_column}, 12) <= ?))"
    )
    params.extend([int(until_year), int(until_year), month])
