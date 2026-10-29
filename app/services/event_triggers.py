from __future__ import annotations

import random
from typing import Any

from app.database import loads_json
from app.services.event_constants import (
    GENRE_ID_ALIASES,
    PROJECT_SCALE_ORDER,
    SCALE_ID_ALIASES,
)


def _is_number(value: Any) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool)


def _dynamic_event_weight(event: dict[str, Any], project: dict[str, Any], context: dict[str, Any]) -> int:
    trigger = event.get("trigger", {}) if isinstance(event.get("trigger"), dict) else {}
    weight = float(event.get("weight", 100) or 100)
    profile = str(
        trigger.get("weightProfile")
        or trigger.get("probabilityProfile")
        or event.get("weightProfile")
        or ""
    )
    project_stats = context.get("project_stats", {})
    reputation = context.get("reputation", {})
    network = context.get("network", {})
    trust = float(context.get("max_relationship_trust", 0) or 0)

    if profile in {"rare", "low_probability"}:
        weight *= 0.35
    elif profile == "actor_dropout":
        weight *= 0.35
        weight *= 1 + (float(project_stats.get("on_set_conflict_risk", 0) or 0) / 90)
        weight *= 1 + (float(project_stats.get("schedule_delay_risk", 0) or 0) / 130)
        if float(reputation.get("creative_reputation", 10) or 10) < 8:
            weight *= 1.45
        if trust < 0:
            weight *= 1.35
        if float(network.get("actor_network", 10) or 10) >= 25 or trust >= 20:
            weight *= 0.55
    elif profile == "actor_adlib":
        weight *= 1 + (float(reputation.get("creative_reputation", 10) or 10) / 90)
        weight *= 1 + (float(network.get("actor_network", 10) or 10) / 110)
        weight *= 1 + (max(0, trust) / 120)
        if context.get("actor_power", 0) >= 75:
            weight *= 1.25
    elif profile == "staff_suggestion":
        weight *= 1 + (float(network.get("production_network", 10) or 10) / 120)
        weight *= 1 + (float(reputation.get("industry_reputation", 10) or 10) / 140)
        if float(context.get("player_stats", {}).get("field_control", 50) or 50) < 40:
            weight *= 1.25
    elif profile == "investor_tailwind":
        weight *= 1 + (float(reputation.get("investor_reputation", 10) or 10) / 80)
        weight *= 1 + (float(context.get("successful_films", 0) or 0) * 0.18)
    elif profile == "investor_cutoff":
        weight *= 0.75
        if float(reputation.get("investor_reputation", 10) or 10) < 8:
            weight *= 1.7
        if int(context.get("flop_films", 0) or 0) > 0:
            weight *= 1 + int(context.get("flop_films", 0)) * 0.35
        if float(project_stats.get("financial_risk", 0) or 0) >= 55:
            weight *= 1.4

    for rule in trigger.get("weightRules", []) if isinstance(trigger.get("weightRules"), list) else []:
        if not isinstance(rule, dict):
            continue
        value = _context_value(rule.get("source"), project, context)
        if value is None:
            continue
        minimum = rule.get("min")
        maximum = rule.get("max")
        if minimum is not None and value < float(minimum):
            continue
        if maximum is not None and value > float(maximum):
            continue
        weight *= float(rule.get("multiplier", 1) or 1)

    genre_weight = _genre_weight_multiplier(trigger, project)
    scale_weight = _scale_weight_multiplier(trigger, project)
    weight *= genre_weight * scale_weight

    return max(1, min(600, int(round(weight))))


def _context_value(source: Any, project: dict[str, Any], context: dict[str, Any]) -> float | None:
    if not isinstance(source, str) or not source:
        return None
    if source.startswith("stats."):
        return _as_float(context.get("project_stats", {}).get(source.removeprefix("stats.")))
    if source.startswith("reputation."):
        return _as_float(context.get("reputation", {}).get(source.removeprefix("reputation.")))
    if source.startswith("network."):
        return _as_float(context.get("network", {}).get(source.removeprefix("network.")))
    if source.startswith("playerStats."):
        return _as_float(context.get("player_stats", {}).get(source.removeprefix("playerStats.")))
    if source.startswith("context."):
        return _as_float(context.get(source.removeprefix("context.")))
    if source.startswith("project."):
        return _as_float(project.get(source.removeprefix("project.")))
    return None


def _as_float(value: Any) -> float | None:
    if _is_number(value):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _stage_aliases(stage: str) -> list[str]:
    aliases = {stage}
    if stage in {
        "funding_simple",
        "capital_application",
        "capital_secured",
        "small_investment",
        "large_investment",
        "large_fundraising",
    }:
        aliases.add("fundraising")
    if stage in {"casting_simple", "star_casting"}:
        aliases.add("casting")
    if stage == "screenplay_development":
        aliases.update({"planning", "development"})
    if stage in {"short_production", "indie_production", "production", "large_scale_production", "large_shooting"}:
        aliases.update({"shooting", "production"})
    if stage in {"post_production", "vfx_post_production"}:
        aliases.add("post_production")
    if stage in {"large_marketing"}:
        aliases.add("marketing")
    if stage in {"limited_release", "release_strategy", "special_format_strategy"}:
        aliases.update({"release", "release_strategy"})
    return sorted(aliases)


def _trigger_matches(
    trigger: dict[str, Any],
    project: dict[str, Any],
    context: dict[str, Any] | None = None,
) -> bool:
    if not trigger:
        return True
    context = context or {}
    if trigger.get("requiresActor") and int(context.get("actor_count", 0) or 0) <= 0:
        return False
    if trigger.get("hasDirector") and int(context.get("director_count", 0) or 0) <= 0:
        return False
    min_actor_count = trigger.get("minActorCount")
    if min_actor_count is not None and int(context.get("actor_count", 0) or 0) < int(min_actor_count):
        return False
    min_director_count = trigger.get("minDirectorCount")
    if min_director_count is not None and int(context.get("director_count", 0) or 0) < int(min_director_count):
        return False
    if trigger.get("requiresCastConfirmed") and int(context.get("cast_confirmed", 0) or 0) <= 0:
        return False
    chance_percent = trigger.get("chancePercent")
    if chance_percent is not None and random.randint(1, 100) > int(chance_percent):
        return False
    year_from = trigger.get("yearFrom")
    if year_from is not None and int(context.get("current_year", 0) or 0) < int(year_from):
        return False
    year_to = trigger.get("yearTo")
    if year_to is not None and int(context.get("current_year", 0) or 0) > int(year_to):
        return False
    era_ids = _as_list(trigger.get("eraIds", trigger.get("eras")))
    if era_ids and context.get("current_era_id") not in set(era_ids):
        return False
    min_budget = trigger.get("minBudget")
    if min_budget is not None and int(project["production_budget"]) < int(min_budget):
        return False
    max_budget = trigger.get("maxBudget")
    if max_budget is not None and int(project["production_budget"]) > int(max_budget):
        return False
    min_marketing_budget = trigger.get("minMarketingBudget")
    if min_marketing_budget is not None and int(project["marketing_budget"] or 0) < int(min_marketing_budget):
        return False
    location_flags = {
        "locationShooting": "location_shooting",
        "setBuild": "set_build",
        "regionalLocation": "regional_location",
        "overseasLocation": "overseas_location",
    }
    for trigger_key, stat_id in location_flags.items():
        if trigger_key in trigger and bool(_project_stat(project, stat_id)) != bool(trigger.get(trigger_key)):
            return False
    genre_ids = _as_list(trigger.get("genreIds", trigger.get("genres")))
    if genre_ids and _canonical_genre_id(project["genre_id"]) not in {
        _canonical_genre_id(genre_id) for genre_id in genre_ids
    }:
        return False
    excluded_genre_ids = _as_list(trigger.get("excludeGenreIds", trigger.get("excludeGenres")))
    if excluded_genre_ids and _canonical_genre_id(project["genre_id"]) in {
        _canonical_genre_id(genre_id) for genre_id in excluded_genre_ids
    }:
        return False
    scale_ids = _as_list(trigger.get("scaleIds", trigger.get("minScale")))
    if scale_ids and _canonical_scale_id(project["scale_id"]) not in {
        _canonical_scale_id(scale_id) for scale_id in scale_ids
    }:
        return False
    min_project_scale = trigger.get("minProjectScale")
    if min_project_scale and not _scale_at_least(project["scale_id"], min_project_scale):
        return False
    max_project_scale = trigger.get("maxProjectScale")
    if max_project_scale and not _scale_at_most(project["scale_id"], max_project_scale):
        return False
    min_plagiarism_risk = trigger.get("minPlagiarismRisk")
    if min_plagiarism_risk is not None and _project_stat(project, "plagiarism_risk") < float(min_plagiarism_risk):
        return False
    max_plagiarism_risk = trigger.get("maxPlagiarismRisk")
    if max_plagiarism_risk is not None and _project_stat(project, "plagiarism_risk") > float(max_plagiarism_risk):
        return False
    for trigger_key, stat_id in _project_stat_minimum_keys().items():
        if trigger_key in trigger and _project_stat(project, stat_id) < float(trigger[trigger_key]):
            return False
    for trigger_key, stat_id in _project_stat_maximum_keys().items():
        if trigger_key in trigger and _project_stat(project, stat_id) > float(trigger[trigger_key]):
            return False
    if not _map_thresholds_match(trigger.get("minReputation"), context.get("reputation", {}), minimum=True):
        return False
    if not _map_thresholds_match(trigger.get("maxReputation"), context.get("reputation", {}), minimum=False):
        return False
    if not _map_thresholds_match(trigger.get("minNetwork"), context.get("network", {}), minimum=True):
        return False
    if not _map_thresholds_match(trigger.get("maxNetwork"), context.get("network", {}), minimum=False):
        return False
    if not _map_thresholds_match(trigger.get("minPlayerStats"), context.get("player_stats", {}), minimum=True):
        return False
    if not _map_thresholds_match(trigger.get("maxPlayerStats"), context.get("player_stats", {}), minimum=False):
        return False
    for trigger_key, source in _context_minimum_keys().items():
        if trigger_key in trigger:
            value = _context_value(source, project, context)
            if value is None or value < float(trigger[trigger_key]):
                return False
    for trigger_key, source in _context_maximum_keys().items():
        if trigger_key in trigger:
            value = _context_value(source, project, context)
            if value is None or value > float(trigger[trigger_key]):
                return False
    return True


def _genre_weight_multiplier(trigger: dict[str, Any], project: dict[str, Any]) -> float:
    genre_weights = trigger.get("genreWeights")
    if not isinstance(genre_weights, dict):
        return 1.0
    project_genre = _canonical_genre_id(project["genre_id"])
    candidates = {
        project["genre_id"],
        project_genre,
        project_genre.removeprefix("genre_"),
    }
    for genre_id in candidates:
        if genre_id in genre_weights:
            return max(0.05, float(genre_weights[genre_id] or 1))
    return max(0.05, float(genre_weights.get("default", 1) or 1))


def _scale_weight_multiplier(trigger: dict[str, Any], project: dict[str, Any]) -> float:
    scale_weights = trigger.get("scaleWeights")
    if not isinstance(scale_weights, dict):
        return 1.0
    project_scale = _canonical_scale_id(project["scale_id"])
    candidates = {
        project["scale_id"],
        project_scale,
        project_scale.removeprefix("scale_"),
    }
    for scale_id in candidates:
        if scale_id in scale_weights:
            return max(0.05, float(scale_weights[scale_id] or 1))
    return max(0.05, float(scale_weights.get("default", 1) or 1))


def _project_stat_minimum_keys() -> dict[str, str]:
    return {
        "minOnSetConflictRisk": "on_set_conflict_risk",
        "minBudgetOverrunRisk": "budget_overrun_risk",
        "minScheduleDelayRisk": "schedule_delay_risk",
        "minFinancialRisk": "financial_risk",
        "minControversyRisk": "controversy_risk",
        "minPressBacklashRisk": "press_backlash_risk",
        "minCriticBacklashRisk": "critic_backlash_risk",
        "minAudienceRejectionRisk": "audience_rejection_risk",
        "minFinalQuality": "final_quality",
        "minAudienceScore": "audience_score",
        "minSecondWeekDrop": "second_week_drop",
        "minPreReleaseInterest": "pre_release_interest",
        "minWordOfMouth": "word_of_mouth",
        "minIpValue": "ip_value",
        "minCultPotential": "cult_potential",
        "minRatingPressure": "rating_pressure",
        "minViolenceIntensity": "violence_intensity",
        "minSexualContent": "sexual_content",
        "minHorrorIntensity": "horror_intensity",
        "minPoliticalSensitivity": "political_sensitivity",
        "minLocationPermitRisk": "location_permit_risk",
        "minScriptDialogueWeakness": "script_dialogue_weakness",
        "minCharacterMotivationIssue": "character_motivation_issue",
        "minScriptPacingIssue": "script_pacing_issue",
        "minInvestorPackageRisk": "investor_package_risk",
        "minAdaptationRightsRisk": "adaptation_rights_risk",
    }


def _project_stat_maximum_keys() -> dict[str, str]:
    return {
        "maxOnSetConflictRisk": "on_set_conflict_risk",
        "maxBudgetOverrunRisk": "budget_overrun_risk",
        "maxScheduleDelayRisk": "schedule_delay_risk",
        "maxFinancialRisk": "financial_risk",
        "maxControversyRisk": "controversy_risk",
        "maxPressBacklashRisk": "press_backlash_risk",
        "maxFinalQuality": "final_quality",
        "maxAudienceScore": "audience_score",
        "maxPreReleaseInterest": "pre_release_interest",
        "maxRatingPressure": "rating_pressure",
        "maxViolenceIntensity": "violence_intensity",
        "maxSexualContent": "sexual_content",
        "maxHorrorIntensity": "horror_intensity",
        "maxPoliticalSensitivity": "political_sensitivity",
        "maxLocationPermitRisk": "location_permit_risk",
        "maxScriptDialogueWeakness": "script_dialogue_weakness",
        "maxCharacterMotivationIssue": "character_motivation_issue",
        "maxScriptPacingIssue": "script_pacing_issue",
        "maxInvestorPackageRisk": "investor_package_risk",
        "maxAdaptationRightsRisk": "adaptation_rights_risk",
    }


def _context_minimum_keys() -> dict[str, str]:
    return {
        "minCreativeReputation": "reputation.creative_reputation",
        "minInvestorReputation": "reputation.investor_reputation",
        "minIndustryReputation": "reputation.industry_reputation",
        "minPublicReputation": "reputation.public_reputation",
        "minActorNetwork": "network.actor_network",
        "minInvestorNetwork": "network.investor_network",
        "minProductionNetwork": "network.production_network",
        "minPressNetwork": "network.press_network",
        "minRelationshipTrust": "context.max_relationship_trust",
        "minCompletedFilms": "context.completed_films",
        "minSuccessfulFilms": "context.successful_films",
        "minFlopFilms": "context.flop_films",
        "minStudioCash": "context.cash",
        "minDebt": "context.debt",
    }


def _context_maximum_keys() -> dict[str, str]:
    return {
        "maxCreativeReputation": "reputation.creative_reputation",
        "maxInvestorReputation": "reputation.investor_reputation",
        "maxIndustryReputation": "reputation.industry_reputation",
        "maxActorNetwork": "network.actor_network",
        "maxInvestorNetwork": "network.investor_network",
        "maxProductionNetwork": "network.production_network",
        "maxRelationshipTrust": "context.max_relationship_trust",
        "maxCompletedFilms": "context.completed_films",
        "maxSuccessfulFilms": "context.successful_films",
        "maxFlopFilms": "context.flop_films",
        "maxStudioCash": "context.cash",
        "maxDebt": "context.debt",
    }


def _map_thresholds_match(thresholds: Any, values: dict[str, Any], *, minimum: bool) -> bool:
    if not thresholds:
        return True
    if not isinstance(thresholds, dict):
        return True
    for key, threshold in thresholds.items():
        value = _as_float(values.get(key))
        if value is None:
            value = 0.0
        if minimum and value < float(threshold):
            return False
        if not minimum and value > float(threshold):
            return False
    return True


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list | tuple | set):
        return list(value)
    return [value]


def _project_stat(project: dict[str, Any], stat_id: str) -> float:
    stats = loads_json(project.get("stats_json"), {}) if "stats_json" in project else project.get("stats", {})
    return float(stats.get(stat_id, 0) or 0)


def _scale_at_least(scale_id: str, minimum_scale_id: str) -> bool:
    return _scale_rank(scale_id) >= _scale_rank(minimum_scale_id)


def _scale_at_most(scale_id: str, maximum_scale_id: str) -> bool:
    return _scale_rank(scale_id) <= _scale_rank(maximum_scale_id)


def _scale_rank(scale_id: str) -> int:
    scale_id = _canonical_scale_id(scale_id)
    try:
        return PROJECT_SCALE_ORDER.index(scale_id)
    except ValueError:
        return -1


def _canonical_scale_id(scale_id: str) -> str:
    return SCALE_ID_ALIASES.get(scale_id, scale_id)


def _canonical_genre_id(genre_id: str) -> str:
    return GENRE_ID_ALIASES.get(genre_id, genre_id)
