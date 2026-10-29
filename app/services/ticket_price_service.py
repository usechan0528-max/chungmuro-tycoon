from __future__ import annotations

from typing import Any

from app.database import get_connection
from app.services.economic_service import build_economic_modifiers
from app.services.game_state import clamp


DEFAULT_START_YEAR = 1980
DEFAULT_END_YEAR = 2035
DEFAULT_ANCHOR_YEAR = 2009
DEFAULT_ANCHOR_PRICE = 7365


def ensure_ticket_price_history(
    start_year: int = DEFAULT_START_YEAR,
    end_year: int = DEFAULT_END_YEAR,
) -> dict[str, int]:
    """Backfill missing yearly ticket prices with actual/API rows first, then CPI estimates.

    KOBIS/KOFIC-derived rows are preferred when present. CPI-generated rows are only
    a playable fallback so old eras never borrow a modern ticket price by accident.
    """
    start_year = int(start_year)
    end_year = int(end_year)
    if start_year > end_year:
        start_year, end_year = end_year, start_year

    with get_connection() as conn:
        from_kobis = _upsert_from_kobis_totals(conn, start_year, end_year)
        from_market_reports = _upsert_from_market_yearly_stats(conn, start_year, end_year)
        generated = 0
        anchors = _ticket_price_anchors(conn)
        for year in range(start_year, end_year + 1):
            existing = _ticket_price_row(conn, year)
            if existing and not _is_generated_ticket_price(existing):
                _mirror_ticket_price(conn, year)
                continue
            row = _estimate_ticket_price(conn, year, anchors)
            _upsert_ticket_price(conn, row)
            generated += 1
        conn.commit()
    return {
        "kobis": from_kobis,
        "market_reports": from_market_reports,
        "cpi_estimates": generated,
    }


def get_ticket_price_for_year(year: int) -> dict[str, Any]:
    ensure_ticket_price_history(DEFAULT_START_YEAR, max(DEFAULT_END_YEAR, int(year)))
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT *
            FROM ticket_prices
            WHERE year <= ?
            ORDER BY year DESC
            LIMIT 1
            """,
            (int(year),),
        ).fetchone()
    return dict(row) if row else _fallback_ticket_price(int(year))


def _upsert_from_kobis_totals(conn: Any, start_year: int, end_year: int) -> int:
    count = 0
    rows = conn.execute(
        """
        SELECT year, average_ticket_price, source_type
        FROM staging_kobis_yearly_totals
        WHERE year BETWEEN ? AND ?
          AND average_ticket_price IS NOT NULL
          AND average_ticket_price > 0
        ORDER BY year
        """,
        (start_year, end_year),
    ).fetchall()
    for row in rows:
        price = int(row["average_ticket_price"])
        _upsert_ticket_price(
            conn,
            {
                "year": int(row["year"]),
                "average_ticket_price": price,
                "perceived_ticket_price": _perceived_ticket_price(int(row["year"]), price),
                "premium_format_multiplier": _premium_multiplier(int(row["year"])),
                "audience_price_sensitivity": _audience_price_sensitivity(int(row["year"]), price),
                "source_type": row["source_type"] or "kobis_derived",
            },
        )
        count += 1
    return count


def _upsert_from_market_yearly_stats(conn: Any, start_year: int, end_year: int) -> int:
    count = 0
    rows = conn.execute(
        """
        SELECT year, total_revenue, total_audience, source_file
        FROM market_yearly_stats
        WHERE year BETWEEN ? AND ?
          AND total_revenue IS NOT NULL
          AND total_revenue > 0
          AND total_audience IS NOT NULL
          AND total_audience > 0
        ORDER BY year
        """,
        (start_year, end_year),
    ).fetchall()
    for row in rows:
        year = int(row["year"])
        existing = conn.execute(
            "SELECT source_type FROM ticket_prices WHERE year = ?",
            (year,),
        ).fetchone()
        if existing and not _is_generated_ticket_price(dict(existing)):
            continue
        price = int(round(int(row["total_revenue"]) / max(int(row["total_audience"]), 1)))
        _upsert_ticket_price(
            conn,
            {
                "year": year,
                "average_ticket_price": price,
                "perceived_ticket_price": _perceived_ticket_price(year, price),
                "premium_format_multiplier": _premium_multiplier(year),
                "audience_price_sensitivity": _audience_price_sensitivity(year, price),
                "source_type": "market_yearly_stats_derived",
            },
        )
        count += 1
    return count


def _ticket_price_exists(conn: Any, year: int) -> bool:
    row = conn.execute("SELECT 1 FROM ticket_prices WHERE year = ?", (year,)).fetchone()
    return row is not None


def _ticket_price_row(conn: Any, year: int) -> dict[str, Any] | None:
    row = conn.execute("SELECT * FROM ticket_prices WHERE year = ?", (year,)).fetchone()
    return dict(row) if row else None


def _is_generated_ticket_price(row: dict[str, Any]) -> bool:
    source_type = str(row.get("source_type") or "")
    return source_type in {"cpi_estimate", "fallback_runtime_estimate", "fallback_anchor"}


def _ticket_price_anchors(conn: Any) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT year, average_ticket_price, source_type
        FROM ticket_prices
        WHERE average_ticket_price > 0
          AND COALESCE(source_type, '') NOT IN (
            'cpi_estimate', 'fallback_runtime_estimate', 'fallback_anchor'
          )
        ORDER BY year
        """
    ).fetchall()
    anchors = [dict(row) for row in rows]
    if not anchors:
        anchors = [
            {
                "year": DEFAULT_ANCHOR_YEAR,
                "average_ticket_price": DEFAULT_ANCHOR_PRICE,
                "source_type": "fallback_anchor",
            }
        ]
    return anchors


def _estimate_ticket_price(conn: Any, year: int, anchors: list[dict[str, Any]]) -> dict[str, Any]:
    anchor = min(anchors, key=lambda row: abs(int(row["year"]) - year))
    anchor_year = int(anchor["year"])
    anchor_price = int(anchor["average_ticket_price"])
    year_cpi = _cpi_for_year(conn, year)
    anchor_cpi = _cpi_for_year(conn, anchor_year)
    average = _round_ticket_price(anchor_price * year_cpi / max(anchor_cpi, 0.001))
    return {
        "year": year,
        "average_ticket_price": max(300, average),
        "perceived_ticket_price": _perceived_ticket_price(year, average),
        "premium_format_multiplier": _premium_multiplier(year),
        "audience_price_sensitivity": _audience_price_sensitivity(year, average),
        "source_type": "cpi_estimate",
    }


def _fallback_ticket_price(year: int) -> dict[str, Any]:
    modifiers = build_economic_modifiers(year)
    base = _round_ticket_price(DEFAULT_ANCHOR_PRICE * float(modifiers["cpi"]) / 92.0)
    return {
        "year": year,
        "average_ticket_price": base,
        "perceived_ticket_price": _perceived_ticket_price(year, base),
        "premium_format_multiplier": _premium_multiplier(year),
        "audience_price_sensitivity": _audience_price_sensitivity(year, base),
        "source_type": "fallback_runtime_estimate",
    }


def _cpi_for_year(conn: Any, year: int) -> float:
    row = conn.execute(
        "SELECT cpi FROM economic_yearly_indicators WHERE year = ?",
        (year,),
    ).fetchone()
    if row and row["cpi"] is not None:
        return float(row["cpi"])
    return float(build_economic_modifiers(year).get("cpi") or 100.0)


def _upsert_ticket_price(conn: Any, row: dict[str, Any]) -> None:
    for table_name in ("ticket_prices", "history_ticket_prices"):
        conn.execute(
            f"""
            INSERT OR REPLACE INTO {table_name} (
                year, average_ticket_price, perceived_ticket_price,
                premium_format_multiplier, audience_price_sensitivity,
                source_type
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                int(row["year"]),
                int(row["average_ticket_price"]),
                int(row.get("perceived_ticket_price") or row["average_ticket_price"]),
                float(row.get("premium_format_multiplier") or 1.0),
                int(row.get("audience_price_sensitivity") or 50),
                row.get("source_type") or "unknown",
            ),
        )


def _mirror_ticket_price(conn: Any, year: int) -> None:
    row = conn.execute("SELECT * FROM ticket_prices WHERE year = ?", (year,)).fetchone()
    if row:
        _upsert_ticket_price(conn, dict(row))


def _round_ticket_price(value: float) -> int:
    if value < 2000:
        unit = 10
    elif value < 8000:
        unit = 50
    else:
        unit = 100
    return int(round(float(value) / unit) * unit)


def _perceived_ticket_price(year: int, average: int) -> int:
    if year < 1990:
        multiplier = 1.08
        unit = 100
    elif year < 2000:
        multiplier = 1.12
        unit = 500
    elif year < 2010:
        multiplier = 1.10
        unit = 500
    elif year < 2020:
        multiplier = 1.22
        unit = 1000
    else:
        multiplier = 1.35
        unit = 1000
    return max(unit, int(round((average * multiplier) / unit) * unit))


def _premium_multiplier(year: int) -> float:
    if year < 1998:
        return 1.0
    if year < 2009:
        return 1.1
    if year < 2016:
        return 1.25
    if year < 2020:
        return 1.45
    return 1.6


def _audience_price_sensitivity(year: int, average: int) -> int:
    if year < 1990:
        base = 20
    elif year < 2000:
        base = 25
    elif year < 2010:
        base = 35
    elif year < 2020:
        base = 55
    else:
        base = 75
    perceived = _perceived_ticket_price(year, average)
    gap_bonus = round(max(0, perceived - average) / max(average, 1) * 20)
    return clamp(base + gap_bonus, 15, 90)
