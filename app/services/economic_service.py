from __future__ import annotations

from typing import Any

from app.database import get_connection


CPI_INDICATOR_ID = "cpi_city_monthly"
CPI_BASE_YEAR = 2020

FALLBACK_CPI_ANCHORS_2020_BASE = {
    1980: 24.0,
    1985: 30.0,
    1990: 39.5,
    1995: 53.0,
    2000: 66.5,
    2005: 76.5,
    2010: 86.0,
    2015: 94.5,
    2020: 100.0,
    2025: 113.0,
    2030: 126.0,
}


def list_kosis_indicator_rows(indicator_id: str | None = None, limit: int = 200) -> list[dict[str, Any]]:
    where = ""
    params: list[Any] = []
    if indicator_id:
        where = "WHERE indicator_id = ?"
        params.append(indicator_id)
    params.append(limit)
    with get_connection() as conn:
        rows = conn.execute(
            f"""
            SELECT *
            FROM staging_kosis_indicator_series
            {where}
            ORDER BY period DESC, region_name, item_name
            LIMIT ?
            """,
            params,
        ).fetchall()
    return [dict(row) for row in rows]


def build_economic_modifiers(year: int) -> dict[str, Any]:
    stored = _stored_indicator(year)
    if stored:
        return stored
    return _build_economic_modifiers_uncached(year)


def _build_economic_modifiers_uncached(year: int) -> dict[str, Any]:

    cpi = _annual_average(CPI_INDICATOR_ID, year)
    base_cpi = _annual_average(CPI_INDICATOR_ID, CPI_BASE_YEAR)
    source = "kosis"
    status = "estimated_from_kosis_cpi"
    if not cpi or not base_cpi:
        cpi = _fallback_cpi(year)
        base_cpi = _fallback_cpi(CPI_BASE_YEAR)
        source = "fallback"
        status = "fallback_estimate_no_kosis_cpi"

    return _modifier_payload(
        year=year,
        cpi=float(cpi),
        base_cpi=float(base_cpi),
        source=source,
        status=status,
    )


def rebuild_economic_yearly_indicators(start_year: int = 1980, end_year: int = 2035) -> int:
    rows = [_build_economic_modifiers_uncached(year) for year in range(start_year, end_year + 1)]
    with get_connection() as conn:
        for row in rows:
            conn.execute(
                """
                INSERT OR REPLACE INTO economic_yearly_indicators (
                    year, cpi, cpi_base_year, cpi_base, production_cost_modifier,
                    currency_real_value_multiplier, audience_affordability_modifier,
                    ticket_price_burden_modifier, theater_demand_modifier,
                    future_economy_modifier, source, source_detail, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """,
                (
                    row["year"],
                    row["cpi"],
                    row["cpi_base_year"],
                    row["cpi_base"],
                    row["production_cost_modifier"],
                    row["currency_real_value_multiplier"],
                    row["audience_affordability_modifier"],
                    row["ticket_price_burden_modifier"],
                    row["theater_demand_modifier"],
                    row["future_economy_modifier"],
                    row["source"],
                    row["status"],
                ),
            )
        conn.commit()
    return len(rows)


def adjusted_scale_budget(scale: dict[str, Any], year: int) -> dict[str, Any]:
    modifiers = build_economic_modifiers(year)
    adjusted = dict(scale)
    original_min = int(adjusted.get("min_budget", 0) or 0)
    original_max = int(adjusted.get("max_budget", 0) or 0)
    multiplier = float(modifiers["production_cost_modifier"])
    adjusted_min = _round_money_unit(original_min * multiplier)
    adjusted_max = max(adjusted_min, _round_money_unit(original_max * multiplier))
    adjusted["base_min_budget"] = original_min
    adjusted["base_max_budget"] = original_max
    adjusted["min_budget"] = adjusted_min
    adjusted["max_budget"] = adjusted_max
    adjusted["economic_adjustment"] = modifiers
    adjusted["budget_year"] = year
    return adjusted


def adjust_money_to_year(value: int | float, *, from_base_year: int = CPI_BASE_YEAR, to_year: int) -> int:
    from_cpi = _effective_cpi(from_base_year)
    to_cpi = _effective_cpi(to_year)
    return _round_money_unit(float(value) * to_cpi / max(from_cpi, 0.001))


def adjust_labor_wage_to_year(value: int | float, *, from_base_year: int = CPI_BASE_YEAR, to_year: int) -> int:
    from_cpi = _effective_cpi(from_base_year)
    to_cpi = _effective_cpi(to_year)
    return _round_living_money_unit(float(value) * to_cpi / max(from_cpi, 0.001))


def money_in_base_year(value: int | float, *, from_year: int, base_year: int = CPI_BASE_YEAR) -> int:
    from_cpi = _effective_cpi(from_year)
    base_cpi = _effective_cpi(base_year)
    return int(round(float(value) * base_cpi / max(from_cpi, 0.001)))


def _modifier_payload(
    *,
    year: int,
    cpi: float,
    base_cpi: float,
    source: str,
    status: str,
) -> dict[str, Any]:
    inflation_ratio = cpi / max(base_cpi, 0.001)
    real_value_multiplier = base_cpi / max(cpi, 0.001)
    ticket_burden = round((inflation_ratio - 1.0) * 60)
    theater_demand = round((1.0 - inflation_ratio) * 20)
    audience_affordability = _clamp_float(1.0 + (1.0 - inflation_ratio) * 0.08, 0.82, 1.08)
    return {
        "source": source,
        "status": status,
        "year": year,
        "cpi": round(cpi, 3),
        "cpi_base_year": CPI_BASE_YEAR,
        "cpi_base": round(base_cpi, 3),
        "production_cost_modifier": round(inflation_ratio, 4),
        "currency_real_value_multiplier": round(real_value_multiplier, 4),
        "audience_affordability_modifier": round(audience_affordability, 4),
        "ticket_price_burden_modifier": _clamp(ticket_burden, -20, 40),
        "theater_demand_modifier": _clamp(theater_demand, -20, 20),
        "future_economy_modifier": _clamp(round((inflation_ratio - 1.0) * 25), -20, 20),
    }


def _stored_indicator(year: int) -> dict[str, Any] | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM economic_yearly_indicators WHERE year = ?",
            (year,),
        ).fetchone()
    if not row:
        return None
    data = dict(row)
    return {
        "source": data.get("source") or "stored",
        "status": data.get("source_detail") or "stored_economic_indicator",
        "year": int(data["year"]),
        "cpi": float(data["cpi"]) if data.get("cpi") is not None else None,
        "cpi_base_year": int(data.get("cpi_base_year") or CPI_BASE_YEAR),
        "cpi_base": float(data["cpi_base"]) if data.get("cpi_base") is not None else None,
        "production_cost_modifier": float(data.get("production_cost_modifier") or 1.0),
        "currency_real_value_multiplier": float(data.get("currency_real_value_multiplier") or 1.0),
        "audience_affordability_modifier": float(data.get("audience_affordability_modifier") or 1.0),
        "ticket_price_burden_modifier": int(data.get("ticket_price_burden_modifier") or 0),
        "theater_demand_modifier": int(data.get("theater_demand_modifier") or 0),
        "future_economy_modifier": int(data.get("future_economy_modifier") or 0),
    }


def _annual_average(indicator_id: str, year: int) -> float | None:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT AVG(value) AS average_value
            FROM staging_kosis_indicator_series
            WHERE indicator_id = ?
              AND year = ?
              AND value IS NOT NULL
              AND (
                  region_name IN ('전국', '전국평균', '전체')
                  OR region_name = ''
                  OR region_name IS NULL
              )
            """,
            (indicator_id, year),
        ).fetchone()
        if row and row["average_value"] is not None:
            return float(row["average_value"])
        row = conn.execute(
            """
            SELECT AVG(value) AS average_value
            FROM staging_kosis_indicator_series
            WHERE indicator_id = ?
              AND year = ?
              AND value IS NOT NULL
            """,
            (indicator_id, year),
        ).fetchone()
    return float(row["average_value"]) if row and row["average_value"] is not None else None


def _effective_cpi(year: int) -> float:
    row = build_economic_modifiers(year)
    cpi = row.get("cpi")
    return float(cpi) if cpi else _fallback_cpi(year)


def _fallback_cpi(year: int) -> float:
    year = int(year)
    anchors = sorted(FALLBACK_CPI_ANCHORS_2020_BASE.items())
    if year <= anchors[0][0]:
        return anchors[0][1]
    if year >= anchors[-1][0]:
        last_year, last_value = anchors[-1]
        previous_year, previous_value = anchors[-2]
        annual_growth = (last_value / previous_value) ** (1 / (last_year - previous_year))
        return last_value * (annual_growth ** (year - last_year))
    for index, (left_year, left_value) in enumerate(anchors[:-1]):
        right_year, right_value = anchors[index + 1]
        if left_year <= year <= right_year:
            span = max(1, right_year - left_year)
            position = (year - left_year) / span
            return left_value + (right_value - left_value) * position
    return 100.0


def _round_money_unit(value: float) -> int:
    if value <= 0:
        return 0
    unit = 100_000 if value < 100_000_000 else 10_000_000
    return max(unit, int(round(value / unit) * unit))


def _round_living_money_unit(value: float) -> int:
    if value <= 0:
        return 0
    if value < 10_000:
        unit = 100
    elif value < 100_000:
        unit = 1_000
    elif value < 500_000:
        unit = 5_000
    else:
        unit = 10_000
    return max(unit, int(round(value / unit) * unit))


def _clamp(value: int, minimum: int, maximum: int) -> int:
    return max(minimum, min(maximum, value))


def _clamp_float(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))
