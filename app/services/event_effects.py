from __future__ import annotations

from copy import deepcopy
import random
from typing import Any

from app.config import STATS_100
from app.database import dumps_json
from app.services.event_constants import (
    EFFECT_SECTIONS,
    NETWORK_EFFECT_KEYS,
    NEGATIVE_EFFECT_SENTENCES,
    POSITIVE_EFFECT_SENTENCES,
    REPUTATION_EFFECT_KEYS,
    RISK_EFFECT_KEYS,
    STUDIO_EFFECT_KEYS,
    UNBOUNDED_EFFECT_KEYS,
    WALK_OUT_CHOICE_ID,
    WALK_OUT_COUNTER_PRESSURE_CHANCE,
    WALK_OUT_COUNTER_PRESSURE_EFFECTS,
)
from app.services.game_state import clamp


def _resolve_choice_effects(
    choice: dict[str, Any],
    event: dict[str, Any] | None,
    *,
    player_stats: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if choice.get("check"):
        passed = _dialogue_check_passes(choice["check"], player_stats or {})
        effect_key = "effectsOnSuccess" if passed else "effectsOnFailure"
        effects = _normalize_choice_effects(deepcopy(choice.get(effect_key, {})))
        if choice.get("id") != WALK_OUT_CHOICE_ID:
            _ensure_choice_tradeoff_effects(effects, event, choice)
        flags = effects.setdefault("flags", {})
        flags["dialogue_check_passed"] = passed
        flags["dialogue_check_stat"] = choice["check"].get("stat")
        return effects

    effects = _normalize_choice_effects(deepcopy(choice.get("effects", {})))
    if choice.get("id") != WALK_OUT_CHOICE_ID:
        _ensure_choice_tradeoff_effects(effects, event, choice)
        return effects

    flags = effects.setdefault("flags", {})
    flags["walk_out_counter_pressure_success"] = False
    if random.randint(1, 100) <= WALK_OUT_COUNTER_PRESSURE_CHANCE:
        _merge_effects(effects, WALK_OUT_COUNTER_PRESSURE_EFFECTS)
    if event:
        flags["walk_out_event_id"] = event.get("id")
        flags["walk_out_stage"] = event.get("stage")
    return effects


def _ensure_choice_tradeoff_effects(
    effects: dict[str, Any],
    event: dict[str, Any] | None,
    choice: dict[str, Any],
) -> None:
    if choice.get("disableAutoTradeoff"):
        return
    has_positive = bool(_effect_sentence_groups(effects, positive=True))
    has_negative = bool(_effect_sentence_groups(effects, positive=False))
    if has_positive and has_negative:
        return
    stage = str((event or {}).get("stage") or "")
    if not has_negative:
        _merge_effects(effects, _stage_downside_effect(stage))
        effects.setdefault("flags", {})["auto_tradeoff_downside"] = True
    if not has_positive:
        _merge_effects(effects, _stage_upside_effect(stage))
        effects.setdefault("flags", {})["auto_tradeoff_upside"] = True


def _stage_downside_effect(stage: str) -> dict[str, dict[str, int]]:
    if stage in {"planning", "development", "ip_development", "screenplay_development"}:
        return {"stats": {"delay_days": 2, "financial_risk": 1}}
    if stage in {"fundraising", "large_fundraising", "funding_simple"}:
        return {"stats": {"financial_risk": 2}, "reputation": {"creative_reputation": -1}}
    if stage in {"casting", "casting_simple", "star_casting"}:
        return {"stats": {"schedule_delay_risk": 2}, "network": {"actor_network": -1}}
    if stage in {"shooting", "production", "large_shooting", "large_scale_production"}:
        return {"stats": {"delay_days": 1, "on_set_conflict_risk": 2}}
    if stage in {"post_production", "vfx_post_production"}:
        return {"stats": {"post_production_duration": 1, "budget_overrun_risk": 2}}
    if stage in {"marketing", "large_marketing"}:
        return {"stats": {"marketing_budget": -20_000_000, "press_backlash_risk": 2}}
    if stage in {"release", "release_strategy", "special_format_strategy"}:
        return {"stats": {"marketing_budget": -20_000_000, "audience_rejection_risk": 1}}
    if stage == "post_release":
        return {"stats": {"marketing_budget": -10_000_000, "second_week_drop": 1}}
    return {"stats": {"financial_risk": 1}}


def _stage_upside_effect(stage: str) -> dict[str, dict[str, int]]:
    if stage in {"planning", "development", "ip_development", "screenplay_development"}:
        return {"stats": {"learning_ability": 1, "scenario_quality": 1}}
    if stage in {"fundraising", "large_fundraising", "funding_simple"}:
        return {"network": {"investor_network": 1}, "stats": {"market_analysis": 1}}
    if stage in {"casting", "casting_simple", "star_casting"}:
        return {"network": {"actor_network": 1}, "stats": {"casting_fit": 1}}
    if stage in {"shooting", "production", "large_shooting", "large_scale_production"}:
        return {"network": {"production_network": 1}, "stats": {"field_control": 1}}
    if stage in {"post_production", "vfx_post_production"}:
        return {"stats": {"editing_quality": 1}}
    if stage in {"marketing", "large_marketing"}:
        return {"stats": {"online_buzz": 1, "marketing_sense": 1}}
    if stage in {"release", "release_strategy", "special_format_strategy"}:
        return {"stats": {"word_of_mouth": 1}}
    if stage == "post_release":
        return {"stats": {"secondary_market_fit": 1, "cult_potential": 1}}
    return {"stats": {"learning_ability": 1}}


def _dialogue_check_passes(check: dict[str, Any], player_stats: dict[str, Any]) -> bool:
    stat_id = check.get("stat")
    difficulty = float(check.get("difficulty", 50) or 50)
    value = float(player_stats.get(stat_id, 0) or 0)
    return value >= difficulty


def _normalize_choice_effects(effects: dict[str, Any]) -> dict[str, Any]:
    if any(section in effects for section in EFFECT_SECTIONS):
        normalized = dict(effects)
        for section in EFFECT_SECTIONS:
            if section in normalized and normalized[section] is None:
                normalized[section] = {}
        flat = {
            key: value
            for key, value in effects.items()
            if key not in EFFECT_SECTIONS
        }
        if flat:
            _merge_effects(normalized, _route_flat_effects(flat))
        return normalized
    return _route_flat_effects(effects)


def _route_flat_effects(effects: dict[str, Any]) -> dict[str, Any]:
    routed: dict[str, dict[str, Any]] = {
        "stats": {},
        "reputation": {},
        "network": {},
        "studio": {},
    }
    for raw_key, value in effects.items():
        key = _normalize_studio_key(raw_key)
        if raw_key in STUDIO_EFFECT_KEYS:
            routed["studio"][key] = value
        elif raw_key in REPUTATION_EFFECT_KEYS:
            routed["reputation"][raw_key] = value
        elif raw_key in NETWORK_EFFECT_KEYS:
            routed["network"][raw_key] = value
        elif raw_key in STATS_100:
            routed["stats"][raw_key] = value
        else:
            routed["stats"][raw_key] = value
    return {section: values for section, values in routed.items() if values}


def _normalize_studio_key(key: str) -> str:
    studio_prefix_map = {
        "studio_cash": "cash",
        "studio_debt": "debt",
        "studio_fame": "fame",
        "studio_own_capital": "own_capital",
        "studio_investment_capital": "investment_capital",
        "studio_loan_capital": "loan_capital",
        "studio_loan_balance": "loan_balance",
        "studio_credit_limit": "credit_limit",
        "studio_field_reputation": "field_reputation",
        "studio_pay_reputation": "pay_reputation",
        "studio_creative_freedom": "creative_freedom",
        "studio_interference_reputation": "interference_reputation",
    }
    if key in studio_prefix_map:
        return studio_prefix_map[key]
    return key


def _effect_sentence_groups(effects: dict[str, Any], *, positive: bool) -> list[str]:
    groups: list[str] = []
    stat_effects = effects.get("stats", {})
    reputation_effects = effects.get("reputation", {})
    network_effects = effects.get("network", {})
    studio_effects = effects.get("studio", {})

    if positive:
        if _has_finance_direction(stat_effects, studio_effects, positive=True):
            groups.append(POSITIVE_EFFECT_SENTENCES["finance"])
        if _has_time_direction(stat_effects, positive=True):
            groups.append(POSITIVE_EFFECT_SENTENCES["time"])
        if _has_direction(stat_effects, {"investment_amount"}, positive=True):
            groups.append(POSITIVE_EFFECT_SENTENCES["investment"])
        if _has_quality_direction(stat_effects, positive=True):
            groups.append(POSITIVE_EFFECT_SENTENCES["quality"])
        if _has_market_direction(stat_effects, positive=True):
            groups.append(POSITIVE_EFFECT_SENTENCES["market"])
        if _has_risk_direction(stat_effects, positive=True):
            groups.append(POSITIVE_EFFECT_SENTENCES["risk"])
        if _has_any_direction(reputation_effects, positive=True) or _has_studio_reputation(studio_effects, positive=True):
            groups.append(POSITIVE_EFFECT_SENTENCES["reputation"])
        if _has_any_direction(network_effects, positive=True):
            groups.append(POSITIVE_EFFECT_SENTENCES["network"])
    else:
        if _has_finance_direction(stat_effects, studio_effects, positive=False):
            groups.append(NEGATIVE_EFFECT_SENTENCES["finance"])
        if _has_time_direction(stat_effects, positive=False):
            groups.append(NEGATIVE_EFFECT_SENTENCES["time"])
        if _has_quality_direction(stat_effects, positive=False):
            groups.append(NEGATIVE_EFFECT_SENTENCES["quality"])
        if _has_market_direction(stat_effects, positive=False):
            groups.append(NEGATIVE_EFFECT_SENTENCES["market"])
        if _has_risk_direction(stat_effects, positive=False):
            groups.append(NEGATIVE_EFFECT_SENTENCES["risk"])
        if _has_direction(stat_effects, {"press_backlash_risk", "controversy_risk"}, positive=False):
            groups.append(NEGATIVE_EFFECT_SENTENCES["press"])
        if _has_any_direction(reputation_effects, positive=False) or _has_studio_reputation(studio_effects, positive=False):
            groups.append(NEGATIVE_EFFECT_SENTENCES["reputation"])
        if _has_any_direction(network_effects, positive=False):
            groups.append(NEGATIVE_EFFECT_SENTENCES["network"])
    return _dedupe(groups)


def _has_finance_direction(
    stat_effects: dict[str, Any],
    studio_effects: dict[str, Any],
    *,
    positive: bool,
) -> bool:
    positive_keys = {
        "cash",
        "own_capital",
        "investment_capital",
        "loan_capital",
        "investment_amount",
        "secondary_market_revenue",
        "credit_limit",
    }
    if positive:
        if _has_direction(studio_effects, {"cash", "own_capital", "investment_capital", "loan_capital", "credit_limit", "fame"}, positive=True):
            return True
        if _has_direction(stat_effects, positive_keys, positive=True):
            return True
        if _has_direction(stat_effects, {"financial_risk", "budget_overrun_risk"}, positive=False):
            return True
        return False
    if _has_direction(studio_effects, {"cash", "own_capital", "investment_capital", "loan_capital", "credit_limit"}, positive=False):
        return True
    if _has_direction(studio_effects, {"debt", "loan_balance"}, positive=True):
        return True
    if _has_direction(stat_effects, positive_keys, positive=False):
        return True
    if _has_direction(stat_effects, {"debt", "production_budget", "total_cost"}, positive=True):
        return True
    if _has_direction(stat_effects, {"marketing_budget"}, positive=False):
        return True
    if _has_direction(stat_effects, {"financial_risk", "budget_overrun_risk"}, positive=True):
        return True
    return False


def _has_time_direction(values: dict[str, Any], *, positive: bool) -> bool:
    time_keys = {
        "production_duration",
        "pre_production_duration",
        "shooting_duration",
        "shooting_duration_delta_days",
        "post_production_duration",
        "marketing_duration",
        "release_timing",
        "delay_days",
        "actor_commitment_duration",
        "director_commitment_duration",
    }
    return _has_direction(values, time_keys, positive=not positive)


def _has_quality_direction(values: dict[str, Any], *, positive: bool) -> bool:
    quality_keys = {
        "scenario_quality",
        "directing_quality",
        "acting_quality",
        "casting_fit",
        "shooting_quality",
        "art_costume_prop_quality",
        "action_stunt_quality",
        "vfx_quality",
        "music_sound_quality",
        "editing_quality",
        "genre_satisfaction",
        "word_of_mouth",
        "script_structure",
        "script_dialogue",
        "script_character_motivation",
        "script_pacing",
        "script_originality",
        "investor_package_readiness",
        "adaptation_rights_clarity",
    }
    return _has_direction(values, quality_keys, positive=positive)


def _has_market_direction(values: dict[str, Any], *, positive: bool) -> bool:
    market_keys = {
        "pre_release_interest",
        "reservation_rate",
        "online_buzz",
        "fandom_index",
        "rewatch_index",
        "ip_value",
        "franchise_power",
        "world_expansion",
        "character_popularity",
        "sequel_demand",
    }
    return _has_direction(values, market_keys, positive=positive)


def _has_risk_direction(values: dict[str, Any], *, positive: bool) -> bool:
    for key, value in values.items():
        if key not in RISK_EFFECT_KEYS or not _is_number(value):
            continue
        if positive and value < 0:
            return True
        if not positive and value > 0:
            return True
    return False


def _has_any_direction(values: dict[str, Any], *, positive: bool) -> bool:
    return any(_matches_direction(value, positive=positive) for value in values.values())


def _has_direction(values: dict[str, Any], keys: set[str], *, positive: bool) -> bool:
    return any(_matches_direction(values.get(key), positive=positive) for key in keys)


def _has_studio_reputation(values: dict[str, Any], *, positive: bool) -> bool:
    reputation_keys = {"fame", "field_reputation", "pay_reputation", "creative_freedom"}
    if _has_direction(values, reputation_keys, positive=positive):
        return True
    return _matches_direction(values.get("interference_reputation"), positive=not positive)


def _matches_direction(value: Any, *, positive: bool) -> bool:
    if not _is_number(value):
        return False
    return value > 0 if positive else value < 0


def _dedupe(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        if value not in result:
            result.append(value)
    return result


def _merge_effects(target: dict[str, Any], source: dict[str, Any]) -> None:
    for section, values in source.items():
        if not isinstance(values, dict):
            target[section] = values
            continue
        section_values = target.setdefault(section, {})
        for key, value in values.items():
            if _is_number(value) and _is_number(section_values.get(key)):
                section_values[key] = section_values[key] + value
            else:
                section_values[key] = value


def _is_number(value: Any) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool)


def _apply_delta_map(target: dict[str, Any], deltas: dict[str, Any], default: int) -> None:
    for key, delta in deltas.items():
        if key in UNBOUNDED_EFFECT_KEYS:
            value = float(target.get(key, 0) or 0) + float(delta)
            target[key] = int(value) if value.is_integer() else value
        else:
            target[key] = clamp(float(target.get(key, default)) + float(delta))


def _write_story_flags(conn: Any, flags: dict[str, Any], player: Any) -> None:
    for key, value in flags.items():
        conn.execute(
            """
            INSERT OR REPLACE INTO story_flags (
                key, value_json, updated_year, updated_month
            ) VALUES (?, ?, ?, ?)
            """,
            (key, dumps_json(value), player["current_year"], player["current_month"]),
        )
        conn.execute(
            """
            INSERT OR REPLACE INTO save_event_flags (
                key, value_json, updated_year, updated_month
            ) VALUES (?, ?, ?, ?)
            """,
            (key, dumps_json(value), player["current_year"], player["current_month"]),
        )
