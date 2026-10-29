from __future__ import annotations

from typing import Any

from app.database import get_connection, loads_json


DEFAULT_STAGE_FLOW = (
    "planning",
    "fundraising",
    "casting",
    "shooting",
    "post_production",
    "marketing",
    "release",
)

RELEASE_RESULT_STAGES = {
    "public_submission",
    "festival_or_online",
    "festival",
    "limited_release",
    "festival_limited_release",
    "release",
    "distribution_release",
    "post_release_response",
    "post_release",
    "secondary_market",
    "fan_event",
    "global_ott_franchise",
    "global_secondary_market",
    "franchise_decision",
    "release_ready",
    "completed",
}

STAGE_TIME_COST_DAYS = {
    "funding_simple": 5,
    "capital_application": 7,
    "capital_secured": 7,
    "planning": 10,
    "development": 14,
    "ip_development": 21,
    "screenplay_development": 21,
    "small_investment": 10,
    "fundraising": 14,
    "large_fundraising": 21,
    "large_investment": 24,
    "distribution_predeal": 10,
    "pre_distribution_deal": 10,
    "production_announcement": 3,
    "casting": 14,
    "casting_simple": 7,
    "star_casting": 18,
    "pre_production": 21,
    "large_pre_production": 35,
    "shooting": 30,
    "short_production": 7,
    "indie_production": 21,
    "production": 24,
    "large_shooting": 45,
    "large_scale_production": 45,
    "editing": 7,
    "post_production": 21,
    "vfx_post_production": 35,
    "marketing": 14,
    "large_marketing": 21,
    "release_strategy": 7,
    "special_format_strategy": 7,
    "premium_format_strategy": 7,
    "festival": 14,
    "limited_release": 14,
    "festival_limited_release": 21,
    "post_release": 14,
    "post_release_response": 10,
    "secondary_market": 21,
    "fan_event": 7,
    "global_secondary_market": 21,
    "global_ott_franchise": 21,
    "franchise_decision": 14,
}

SHOOTING_STAGE_ALIASES = {
    "shooting",
    "short_production",
    "indie_production",
    "production",
    "large_shooting",
    "large_scale_production",
}

SHOOTING_DURATION_BOUNDS_BY_SCALE = {
    "scale_short": {"min": 3, "default": 5, "max": 15},
    "short_film": {"min": 3, "default": 5, "max": 15},
    "scale_independent": {"min": 15, "default": 30, "max": 60},
    "independent_film": {"min": 15, "default": 30, "max": 60},
    "scale_low_budget_genre": {"min": 25, "default": 45, "max": 90},
    "low_budget_genre": {"min": 25, "default": 45, "max": 90},
    "scale_mid_commercial": {"min": 45, "default": 75, "max": 130},
    "mid_commercial": {"min": 45, "default": 75, "max": 130},
    "scale_large_commercial": {"min": 70, "default": 100, "max": 180},
    "large_commercial": {"min": 70, "default": 100, "max": 180},
    "scale_tentpole": {"min": 100, "default": 150, "max": 260},
    "tentpole_blockbuster": {"min": 100, "default": 150, "max": 260},
}

SCALE_TIME_MULTIPLIERS = {
    "scale_short": 0.45,
    "scale_independent": 0.7,
    "scale_low_budget_genre": 0.85,
    "scale_mid_commercial": 1.0,
    "scale_large_commercial": 1.2,
    "scale_tentpole": 1.45,
}

SCALE_STAGE_TIME_COST_DAYS = {
    "scale_short": {
        "funding_simple": 7,
        "shooting": 5,
        "editing": 7,
        "festival_or_online": 14,
    },
    "scale_independent": {
        "funding_simple": 30,
        "planning": 45,
        "screenplay_development": 30,
        "casting_simple": 21,
        "shooting": 30,
        "post_production": 45,
        "festival": 30,
        "limited_release": 14,
        "secondary_market": 30,
    },
    "scale_low_budget_genre": {
        "planning": 45,
        "screenplay_development": 45,
        "fundraising": 45,
        "casting": 30,
        "shooting": 45,
        "post_production": 60,
        "marketing": 30,
        "release": 14,
        "secondary_market": 30,
    },
    "scale_mid_commercial": {
        "planning": 60,
        "screenplay_development": 60,
        "fundraising": 90,
        "production_announcement": 7,
        "casting": 45,
        "pre_production": 60,
        "shooting": 75,
        "post_production": 90,
        "marketing": 45,
        "release_strategy": 21,
        "release": 14,
        "post_release": 30,
        "secondary_market": 45,
    },
    "scale_large_commercial": {
        "planning": 90,
        "screenplay_development": 75,
        "large_fundraising": 120,
        "distribution_predeal": 45,
        "production_announcement": 14,
        "star_casting": 60,
        "pre_production": 90,
        "shooting": 100,
        "post_production": 120,
        "large_marketing": 60,
        "release_strategy": 30,
        "release": 21,
        "post_release": 45,
        "secondary_market": 60,
    },
    "scale_tentpole": {
        "ip_development": 180,
        "screenplay_development": 120,
        "large_fundraising": 150,
        "distribution_predeal": 60,
        "production_announcement": 21,
        "star_casting": 90,
        "large_pre_production": 150,
        "large_shooting": 150,
        "vfx_post_production": 240,
        "large_marketing": 90,
        "special_format_strategy": 30,
        "release": 30,
        "fan_event": 30,
        "global_secondary_market": 90,
        "franchise_decision": 60,
    },
}

STAGE_LABELS = {
    "funding_simple": "자본 확보",
    "capital_application": "자본 확보/공모 제출",
    "short_production": "제작",
    "editing": "편집",
    "festival_or_online": "영화제/온라인 공개",
    "public_submission": "공개/출품",
    "capital_secured": "자본 확보",
    "screenplay_development": "시나리오 개발",
    "casting_simple": "간단 캐스팅",
    "indie_production": "제작",
    "planning": "기획",
    "small_investment": "소규모 투자",
    "development": "기획 개발",
    "fundraising": "투자 유치",
    "large_fundraising": "대형 투자 유치",
    "distribution_predeal": "배급 사전 협상",
    "production_announcement": "제작 발표",
    "casting": "캐스팅",
    "pre_production": "프리프로덕션",
    "large_pre_production": "대형 프리프로덕션",
    "shooting": "제작/촬영",
    "large_shooting": "대규모 촬영",
    "production": "제작",
    "post_production": "후반",
    "vfx_post_production": "VFX 후반",
    "marketing": "마케팅",
    "large_marketing": "대형 마케팅",
    "festival": "영화제",
    "limited_release": "제한 개봉",
    "festival_limited_release": "영화제/제한 개봉",
    "release_strategy": "배급/개봉 전략",
    "release": "개봉",
    "distribution_release": "배급/개봉",
    "post_release_response": "개봉 후 대응",
    "post_release": "개봉 후 대응",
    "secondary_market": "2차 시장",
    "ip_development": "IP 개발",
    "large_investment": "대형 투자",
    "pre_distribution_deal": "배급 사전 협상",
    "star_casting": "스타 캐스팅",
    "large_scale_production": "대규모 제작",
    "premium_format_strategy": "특수관 전략",
    "special_format_strategy": "특수관 전략",
    "fan_event": "팬 이벤트",
    "global_ott_franchise": "해외/OTT/시리즈화",
    "global_secondary_market": "해외/OTT/2차 시장",
    "franchise_decision": "시리즈화 결정",
    "release_ready": "개봉 준비",
    "theatrical_release": "1차 시장 상영",
    "completed": "개봉 완료",
}


def get_stage_flow_for_scale(scale_id: str | None) -> list[str]:
    if not scale_id:
        return list(DEFAULT_STAGE_FLOW)

    with get_connection() as conn:
        row = conn.execute(
            "SELECT required_stages_json, stage_flow_json FROM project_scales WHERE id = ?",
            (scale_id,),
        ).fetchone()
        if not row:
            row = conn.execute(
                "SELECT required_stages_json, stage_flow_json FROM core_project_scales WHERE id = ?",
                (scale_id,),
            ).fetchone()

    if not row:
        return list(DEFAULT_STAGE_FLOW)
    flow = _normalize_stage_flow(row["required_stages_json"]) or _normalize_stage_flow(row["stage_flow_json"]) or list(DEFAULT_STAGE_FLOW)
    return _enforce_casting_before_announcement(flow)


def first_project_stage(scale_id: str | None) -> str:
    flow = get_stage_flow_for_scale(scale_id)
    return flow[0] if flow else DEFAULT_STAGE_FLOW[0]


def next_project_stage(current_stage: str, scale_id: str | None = None) -> str:
    if current_stage == "completed":
        return "completed"

    flow = get_stage_flow_for_scale(scale_id)
    if current_stage not in flow:
        if current_stage == "shooting" and "post_production" in flow:
            return "post_production"
        return flow[0] if flow else DEFAULT_STAGE_FLOW[0]

    index = flow.index(current_stage)
    if index >= len(flow) - 1:
        return "completed"
    return flow[index + 1]


def can_calculate_release(stage: str) -> bool:
    return stage in RELEASE_RESULT_STAGES


def stage_time_cost_days(stage: str, scale_id: str | None = None) -> int:
    if can_calculate_release(stage):
        return 0
    scale_overrides = SCALE_STAGE_TIME_COST_DAYS.get(scale_id or "", {})
    if stage in scale_overrides:
        return max(1, int(scale_overrides[stage]))
    base_days = STAGE_TIME_COST_DAYS.get(stage, 7)
    multiplier = SCALE_TIME_MULTIPLIERS.get(scale_id or "", 1.0)
    return max(1, int(round(base_days * multiplier)))


def shooting_duration_bounds(scale_id: str | None) -> dict[str, int]:
    bounds = SHOOTING_DURATION_BOUNDS_BY_SCALE.get(scale_id or "")
    if bounds:
        return dict(bounds)
    default = stage_time_cost_days("shooting", scale_id)
    return {
        "min": max(1, int(round(default * 0.55))),
        "default": default,
        "max": max(default, int(round(default * 1.8))),
    }


def normalize_planned_shooting_days(scale_id: str | None, days: int | None) -> int:
    bounds = shooting_duration_bounds(scale_id)
    requested = int(days or bounds["default"])
    return max(bounds["min"], min(bounds["max"], requested))


def stage_time_cost_days_for_project(
    stage: str,
    scale_id: str | None = None,
    stats: dict[str, Any] | None = None,
) -> int:
    if stage not in SHOOTING_STAGE_ALIASES:
        return stage_time_cost_days(stage, scale_id)
    bounds = shooting_duration_bounds(scale_id)
    stats = stats or {}
    planned = normalize_planned_shooting_days(
        scale_id,
        int(stats.get("planned_shooting_days") or stats.get("shooting_duration") or bounds["default"]),
    )
    delta = int(stats.get("shooting_duration_delta_days") or 0)
    return max(bounds["min"], planned + delta)


def sync_shooting_duration_stats(
    stats: dict[str, Any],
    scale_id: str | None,
    *,
    planned_days: int | None = None,
    effect_stats: dict[str, Any] | None = None,
) -> None:
    bounds = shooting_duration_bounds(scale_id)
    planned = normalize_planned_shooting_days(
        scale_id,
        planned_days if planned_days is not None else int(stats.get("planned_shooting_days") or bounds["default"]),
    )
    current_delta = int(stats.get("shooting_duration_delta_days") or 0)
    effect_stats = effect_stats or {}
    delta = 0
    if "shooting_duration_delta_days" in effect_stats:
        delta += int(effect_stats.get("shooting_duration_delta_days") or 0)
    if "shooting_duration" in effect_stats:
        value = int(effect_stats.get("shooting_duration") or 0)
        delta += value * 7 if abs(value) <= 4 else value
    if planned_days is not None and "shooting_duration_delta_days" not in stats:
        current_delta = int(stats.get("location_duration_delta_days") or 0)
    next_delta = max(bounds["min"] - planned, current_delta + delta)
    stats["planned_shooting_days"] = planned
    stats["shooting_duration_delta_days"] = next_delta
    stats["shooting_duration_min_days"] = bounds["min"]
    stats["shooting_duration_max_days"] = bounds["max"]
    stats["shooting_duration"] = planned + next_delta


def effect_time_cost_days(effects: dict[str, Any]) -> int:
    stats = effects.get("stats", {}) if isinstance(effects, dict) else {}
    if not isinstance(stats, dict):
        return 0
    days = 0
    days += max(0, int(stats.get("delay_days", 0) or 0))
    if stats.get("shooting_duration_delta_days"):
        days += max(0, int(stats.get("shooting_duration_delta_days") or 0))
    if stats.get("shooting_duration"):
        value = int(stats.get("shooting_duration") or 0)
        days += max(0, value * 7 if abs(value) <= 4 else value)
    for key in (
        "production_duration",
        "pre_production_duration",
        "post_production_duration",
        "marketing_duration",
        "release_timing",
    ):
        days += max(0, int(stats.get(key, 0) or 0)) * 30
    return days


def _normalize_stage_flow(value: Any) -> list[str]:
    raw_flow = loads_json(value, []) if isinstance(value, str) else value
    if not isinstance(raw_flow, list):
        return []
    return [str(stage) for stage in raw_flow if stage]


def _enforce_casting_before_announcement(flow: list[str]) -> list[str]:
    if "production_announcement" not in flow:
        return flow
    casting_indices = [
        index
        for index, stage in enumerate(flow)
        if stage in {"casting", "casting_simple", "star_casting"}
    ]
    if not casting_indices:
        return flow
    announcement_index = flow.index("production_announcement")
    last_casting_index = max(casting_indices)
    if announcement_index > last_casting_index:
        return flow
    adjusted = [stage for stage in flow if stage != "production_announcement"]
    last_casting_index = max(
        index
        for index, stage in enumerate(adjusted)
        if stage in {"casting", "casting_simple", "star_casting"}
    )
    adjusted.insert(last_casting_index + 1, "production_announcement")
    return adjusted
