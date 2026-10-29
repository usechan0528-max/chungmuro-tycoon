from __future__ import annotations

from typing import Any

from app.database import get_connection, loads_json
from app.services.economic_service import build_economic_modifiers


KEY_ALIASES = {
    "theaterDemand": "theater_demand",
    "ottPower": "ott_power",
    "foreignCompetition": "foreign_competition",
    "middleBudgetRisk": "middle_budget_risk",
    "specialFormatDemand": "special_format_demand",
    "onlineSpreadPower": "online_spread_power",
    "ticketPriceBurden": "ticket_price_burden",
    "majorDistributorPower": "major_distributor_power",
    "screenAccessDifficulty": "screen_access_difficulty",
}


def current_era_rule(year: int) -> dict[str, Any] | None:
    with get_connection() as conn:
        row = _era_rule_row_for_year(conn, year)
    return _row_to_rule(row) if row else None


def era_rule_for_year(conn: Any, year: int) -> dict[str, Any] | None:
    row = _era_rule_row_for_year(conn, year)
    return _row_to_rule(row) if row else None


def build_era_market_modifiers(conn: Any, era: Any, year: int) -> dict[str, Any]:
    era_dict = dict(era)
    rule = era_rule_for_year(conn, year)
    modifiers: dict[str, Any] = {
        "middle_budget_risk": era_dict.get("middle_budget_risk", 50),
        "special_format_demand": era_dict.get("special_format_demand", 0),
        "online_spread_power": era_dict.get("online_spread_power", 0),
        "ticket_price_burden": era_dict.get("ticket_price_burden", 50),
        "unlocked_systems": loads_json(era_dict.get("unlocked_systems_json"), []),
        "locked_systems": loads_json(era_dict.get("locked_systems_json"), []),
    }
    if not rule:
        return modifiers

    market_rules = _normalize_keys(rule.get("marketRules", {}))
    risk_modifiers = _normalize_keys(rule.get("riskModifiers", {}))
    genre_modifiers = _normalize_keys(rule.get("genreModifiers", {}))
    modifiers.update(market_rules)
    economic_modifiers = build_economic_modifiers(year)
    modifiers["economic_modifiers"] = economic_modifiers
    modifiers["production_cost_modifier"] = economic_modifiers["production_cost_modifier"]
    modifiers["currency_real_value_multiplier"] = economic_modifiers["currency_real_value_multiplier"]
    modifiers["audience_affordability_modifier"] = economic_modifiers["audience_affordability_modifier"]
    modifiers["ticket_price_burden"] = _bounded_modifier(
        modifiers.get("ticket_price_burden", 50),
        economic_modifiers["ticket_price_burden_modifier"],
    )
    modifiers["theater_demand"] = _bounded_modifier(
        modifiers.get("theater_demand", era_dict.get("theater_demand", 50)),
        economic_modifiers["theater_demand_modifier"],
    )
    modifiers["era_rule_id"] = rule["id"]
    modifiers["era_rule_name"] = rule.get("name", "")
    modifiers["era_summary"] = rule.get("summary", "")
    modifiers["market_rules"] = market_rules
    modifiers["era_locked_systems"] = rule.get("lockedSystems", [])
    modifiers["era_unlocked_systems"] = rule.get("unlockedSystems", [])
    modifiers["locked_choices"] = rule.get("lockedChoices", [])
    modifiers["strong_choices"] = rule.get("strongChoices", [])
    modifiers["inefficient_choices"] = rule.get("inefficientChoices", [])
    modifiers["era_risk_modifiers"] = risk_modifiers
    modifiers["era_genre_modifiers"] = genre_modifiers
    modifiers["game_over_risks"] = rule.get("gameOverRisks", [])
    modifiers["production_rules"] = rule.get("productionRules", {})
    modifiers["distribution_rules"] = rule.get("distributionRules", {})
    modifiers["marketing_rules"] = rule.get("marketingRules", {})
    modifiers["secondary_market_rules"] = rule.get("secondaryMarketRules", {})
    return modifiers


def choice_state(choice_id: str, year: int) -> dict[str, Any]:
    rule = current_era_rule(year)
    if not rule:
        return {"available": True, "strength": "normal", "warning": ""}
    locked = set(rule.get("lockedChoices", [])) | set(rule.get("lockedSystems", []))
    strong = set(rule.get("strongChoices", [])) | set(rule.get("unlockedSystems", []))
    inefficient = set(rule.get("inefficientChoices", []))
    if choice_id in locked:
        return {"available": False, "strength": "locked", "warning": "현재 시대에는 사용할 수 없는 선택지입니다."}
    if choice_id in inefficient:
        return {"available": True, "strength": "inefficient", "warning": "현재 시대에는 가능하지만 효율이 낮은 선택지입니다."}
    if choice_id in strong:
        return {"available": True, "strength": "strong", "warning": "현재 시대에 강한 선택지입니다."}
    return {"available": True, "strength": "normal", "warning": ""}


def _era_rule_row_for_year(conn: Any, year: int) -> Any:
    row = conn.execute(
        """
        SELECT *
        FROM era_rules
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
        FROM era_rules
        ORDER BY start_year DESC
        LIMIT 1
        """
    ).fetchone()


def _row_to_rule(row: Any) -> dict[str, Any]:
    data = dict(row)
    return {
        "id": data["id"],
        "name": data["name"],
        "startYear": data["start_year"],
        "endYear": data["end_year"],
        "summary": data.get("summary") or "",
        "marketRules": loads_json(data.get("market_rules_json"), {}),
        "productionRules": loads_json(data.get("production_rules_json"), {}),
        "distributionRules": loads_json(data.get("distribution_rules_json"), {}),
        "marketingRules": loads_json(data.get("marketing_rules_json"), {}),
        "secondaryMarketRules": loads_json(data.get("secondary_market_rules_json"), {}),
        "lockedSystems": loads_json(data.get("locked_systems_json"), []),
        "unlockedSystems": loads_json(data.get("unlocked_systems_json"), []),
        "lockedChoices": loads_json(data.get("locked_choices_json"), []),
        "strongChoices": loads_json(data.get("strong_choices_json"), []),
        "inefficientChoices": loads_json(data.get("inefficient_choices_json"), []),
        "genreModifiers": loads_json(data.get("genre_modifiers_json"), {}),
        "riskModifiers": loads_json(data.get("risk_modifiers_json"), {}),
        "gameOverRisks": loads_json(data.get("game_over_risks_json"), []),
        "futureRules": loads_json(data.get("future_rules_json"), {}),
    }


def _normalize_keys(values: dict[str, Any]) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    for key, value in values.items():
        normalized[KEY_ALIASES.get(str(key), _camel_to_snake(str(key)))] = value
    return normalized


def _bounded_modifier(base_value: Any, delta: int) -> int:
    try:
        base = int(base_value)
    except (TypeError, ValueError):
        base = 50
    return max(0, min(100, base + int(delta)))


def _camel_to_snake(value: str) -> str:
    result: list[str] = []
    for char in value:
        if char.isupper() and result:
            result.append("_")
        result.append(char.lower())
    return "".join(result)
