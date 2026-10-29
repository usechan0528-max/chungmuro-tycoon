from __future__ import annotations

from typing import Any

from app.database import dumps_json, get_connection, loads_json
from app.services.economic_service import build_economic_modifiers
from app.services.era_service import build_era_market_modifiers
from app.services.ticket_price_service import ensure_ticket_price_history


def ensure_market_state_for_month(year: int, month: int, *, refresh: bool = False) -> dict[str, Any]:
    """Ensure monthly market baselines follow the current year and era.

    The market row is the bridge between long-running time progression and
    release calculations. It must be rebuilt when a new month starts so an
    1980s save naturally enters 1990s, 2000s, 2010s and later economies.
    """
    year = int(year)
    month = int(month)
    ensure_ticket_price_history(1980, max(2035, year + 5))
    with get_connection() as conn:
        row = ensure_market_state_with_connection(conn, year, month, refresh=refresh)
        conn.commit()
        return _row_to_dict(row)


def ensure_market_state_with_connection(
    conn: Any,
    year: int,
    month: int,
    *,
    refresh: bool = False,
) -> Any:
    year = int(year)
    month = int(month)
    existing = conn.execute(
        "SELECT * FROM market_state WHERE year = ? AND month = ?",
        (year, month),
    ).fetchone()
    if existing and not refresh:
        return existing

    payload = build_market_state_payload(conn, year, month, existing)
    for table in ("market_state", "save_market_state"):
        conn.execute(
            f"""
            INSERT INTO {table} (
                year, month, theater_demand, ott_power, foreign_competition,
                korean_film_trust, genre_trends_json, modifiers_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(year, month) DO UPDATE SET
                theater_demand = excluded.theater_demand,
                ott_power = excluded.ott_power,
                foreign_competition = excluded.foreign_competition,
                korean_film_trust = excluded.korean_film_trust,
                genre_trends_json = excluded.genre_trends_json,
                modifiers_json = excluded.modifiers_json
            """,
            (
                year,
                month,
                payload["theater_demand"],
                payload["ott_power"],
                payload["foreign_competition"],
                payload["korean_film_trust"],
                payload["genre_trends_json"],
                payload["modifiers_json"],
            ),
        )
    return conn.execute(
        "SELECT * FROM market_state WHERE year = ? AND month = ?",
        (year, month),
    ).fetchone()


def build_market_state_payload(conn: Any, year: int, month: int, existing: Any | None = None) -> dict[str, Any]:
    era = _era_for_year(conn, year)
    modifiers: dict[str, Any]
    if era:
        modifiers = build_era_market_modifiers(conn, era, year)
        fallback_theater = int(era["theater_demand"] or 50)
        fallback_ott = int(era["ott_power"] or 0)
        fallback_foreign = int(era["foreign_competition"] or 50)
    else:
        modifiers = {}
        fallback_theater = 50
        fallback_ott = 0
        fallback_foreign = 50

    if "economic_modifiers" not in modifiers:
        economic_modifiers = build_economic_modifiers(year)
        modifiers["economic_modifiers"] = economic_modifiers
        modifiers["production_cost_modifier"] = economic_modifiers["production_cost_modifier"]
        modifiers["currency_real_value_multiplier"] = economic_modifiers["currency_real_value_multiplier"]
        modifiers["audience_affordability_modifier"] = economic_modifiers["audience_affordability_modifier"]

    ticket = _ticket_for_year(conn, year)
    if ticket:
        modifiers["ticket_price"] = {
            "year": int(ticket["year"]),
            "average_ticket_price": int(ticket["average_ticket_price"]),
            "perceived_ticket_price": int(ticket["perceived_ticket_price"] or ticket["average_ticket_price"]),
            "premium_format_multiplier": float(ticket["premium_format_multiplier"] or 1.0),
            "audience_price_sensitivity": int(ticket["audience_price_sensitivity"] or 50),
            "source_type": ticket["source_type"] or "unknown",
        }

    modifiers["market_state_year"] = year
    modifiers["market_state_month"] = month
    modifiers["market_state_source"] = "era_economic_baseline"

    genre_trends_json = "{}"
    korean_film_trust = 50
    if existing:
        genre_trends_json = existing["genre_trends_json"] or "{}"
        korean_film_trust = int(existing["korean_film_trust"] or 50)

    return {
        "theater_demand": _clamp_int(modifiers.get("theater_demand", fallback_theater), 0, 100),
        "ott_power": _clamp_int(modifiers.get("ott_power", fallback_ott), 0, 100),
        "foreign_competition": _clamp_int(modifiers.get("foreign_competition", fallback_foreign), 0, 100),
        "korean_film_trust": _clamp_int(modifiers.get("korean_film_trust", korean_film_trust), 0, 100),
        "genre_trends_json": genre_trends_json,
        "modifiers_json": dumps_json(modifiers),
    }


def market_state_dict(conn: Any, year: int, month: int, *, refresh: bool = False) -> dict[str, Any]:
    row = ensure_market_state_with_connection(conn, year, month, refresh=refresh)
    data = _row_to_dict(row)
    data["modifiers"] = loads_json(data.pop("modifiers_json", None), {})
    data["genreTrends"] = loads_json(data.pop("genre_trends_json", None), {})
    return data


def _era_for_year(conn: Any, year: int) -> Any | None:
    row = conn.execute(
        """
        SELECT *
        FROM eras
        WHERE start_year <= ? AND (end_year IS NULL OR end_year >= ?)
        ORDER BY start_year DESC
        LIMIT 1
        """,
        (year, year),
    ).fetchone()
    if row:
        return row
    return conn.execute(
        """
        SELECT *
        FROM eras
        ORDER BY start_year DESC
        LIMIT 1
        """
    ).fetchone()


def _ticket_for_year(conn: Any, year: int) -> Any | None:
    row = conn.execute(
        """
        SELECT *
        FROM ticket_prices
        WHERE year <= ?
        ORDER BY year DESC
        LIMIT 1
        """,
        (year,),
    ).fetchone()
    if row:
        return row
    return conn.execute("SELECT * FROM ticket_prices ORDER BY year LIMIT 1").fetchone()


def _row_to_dict(row: Any) -> dict[str, Any]:
    return dict(row) if row else {}


def _clamp_int(value: Any, minimum: int, maximum: int) -> int:
    try:
        number = int(round(float(value)))
    except (TypeError, ValueError):
        number = minimum
    return max(minimum, min(maximum, number))
