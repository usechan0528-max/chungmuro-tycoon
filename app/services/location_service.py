from __future__ import annotations

from typing import Any

from app.services.game_state import clamp, money


LOCATION_STRATEGIES: tuple[dict[str, Any], ...] = (
    {
        "id": "real_location",
        "name": "실제 장소 촬영",
        "locationType": "실제 장소",
        "shortDescription": "현실감과 화면 밀도가 좋지만 허가와 민원 리스크가 있다.",
        "description": "실제 거리, 건물, 상업 공간을 활용한다. 화면은 살아나지만 허가, 소음, 통제 문제가 따라온다.",
        "costRate": 0.00,
        "durationDeltaDays": 0,
        "stats": {
            "shooting_quality": 3,
            "art_costume_prop_quality": 1,
            "schedule_delay_risk": 4,
            "location_permit_risk": 12,
        },
        "network": {"production_network": 1},
        "flags": {"location_shooting": 1},
    },
    {
        "id": "set_build",
        "name": "세트 제작",
        "locationType": "세트",
        "shortDescription": "통제력은 높지만 세트 제작비와 미술비 부담이 크다.",
        "description": "주요 공간을 세트로 제작한다. 일정과 조명 통제가 좋아지는 대신 선제 비용과 미술 완성도 관리가 중요하다.",
        "costRate": 0.08,
        "durationDeltaDays": 5,
        "stats": {
            "shooting_quality": 2,
            "art_costume_prop_quality": 6,
            "budget_overrun_risk": 7,
            "schedule_delay_risk": -2,
            "location_permit_risk": -8,
        },
        "network": {"production_network": 1},
        "flags": {"set_build": 1},
    },
    {
        "id": "regional_location",
        "name": "지방 로케이션",
        "locationType": "지방 로케이션",
        "shortDescription": "지역 협조와 화면 차별화가 생기지만 이동·숙박과 허가 변수가 있다.",
        "description": "서울권 밖의 도시와 지역 공간을 중심으로 촬영한다. 지역 인맥과 풍광을 얻지만 이동, 숙박, 지자체 협의가 제작 기간을 흔든다.",
        "costRate": 0.05,
        "durationDeltaDays": 7,
        "stats": {
            "shooting_quality": 3,
            "art_costume_prop_quality": 3,
            "schedule_delay_risk": 7,
            "location_permit_risk": 8,
            "pre_release_interest": 2,
        },
        "network": {"regional_network": 4, "production_network": 1},
        "flags": {"location_shooting": 1, "regional_location": 1},
    },
    {
        "id": "overseas_location",
        "name": "해외 촬영",
        "locationType": "해외 로케이션",
        "shortDescription": "스케일과 화제성은 크지만 비용, 비자, 통관, 현지 허가 리스크가 높다.",
        "description": "해외 도시와 자연 환경을 활용한다. 제작 발표 단계의 화제성은 크지만 현지 허가, 장비 통관, 환율, 일정 지연에 취약하다.",
        "costRate": 0.22,
        "durationDeltaDays": 14,
        "stats": {
            "shooting_quality": 6,
            "art_costume_prop_quality": 4,
            "pre_release_interest": 6,
            "budget_overrun_risk": 12,
            "schedule_delay_risk": 14,
            "location_permit_risk": 18,
            "financial_risk": 5,
        },
        "reputation": {"global_reputation": 1},
        "network": {"regional_network": 1, "distribution_network": 1},
        "flags": {"location_shooting": 1, "overseas_location": 1},
    },
)


def location_strategy_options(*, scale_id: str | None = None, genre_id: str | None = None) -> list[dict[str, Any]]:
    return [location_strategy_profile(option["id"], scale_id=scale_id, genre_id=genre_id) for option in LOCATION_STRATEGIES]


def location_strategy_profile(
    strategy_id: str | None,
    *,
    scale_id: str | None = None,
    genre_id: str | None = None,
    production_budget: int = 0,
) -> dict[str, Any]:
    option = _strategy_by_id(strategy_id)
    cost_impact = max(0, int(int(production_budget or 0) * float(option.get("costRate", 0.0))))
    profile = {
        "id": option["id"],
        "name": option["name"],
        "locationType": option["locationType"],
        "shortDescription": option["shortDescription"],
        "description": option["description"],
        "costRate": float(option.get("costRate", 0.0)),
        "costImpact": cost_impact,
        "durationDeltaDays": int(option.get("durationDeltaDays", 0) or 0),
        "stats": dict(option.get("stats", {})),
        "reputation": dict(option.get("reputation", {})),
        "network": dict(option.get("network", {})),
        "flags": dict(option.get("flags", {})),
        "availabilityNote": _availability_note(option["id"], scale_id, genre_id),
    }
    profile["impactLine"] = location_impact_line(profile)
    return profile


def apply_location_strategy_to_stats(
    stats: dict[str, Any],
    strategy_id: str | None,
    *,
    production_budget: int,
    scale_id: str | None = None,
    genre_id: str | None = None,
) -> dict[str, Any]:
    profile = location_strategy_profile(
        strategy_id,
        scale_id=scale_id,
        genre_id=genre_id,
        production_budget=production_budget,
    )
    for key, value in profile["stats"].items():
        default = 0 if key in {"location_permit_risk", "production_duration", "shooting_duration"} else 50
        stats[key] = clamp(float(stats.get(key, default) or default) + float(value))
    for key, value in profile["flags"].items():
        stats[key] = int(value)
    stats["location_strategy"] = profile["id"]
    stats["location_strategy_name"] = profile["name"]
    stats["location_type"] = profile["locationType"]
    stats["location_cost_impact"] = int(profile["costImpact"])
    stats["location_duration_delta_days"] = int(profile["durationDeltaDays"])
    stats["shooting_duration_delta_days"] = int(stats.get("shooting_duration_delta_days", 0) or 0) + int(profile["durationDeltaDays"])
    stats["production_duration"] = int(stats.get("production_duration", 0) or 0) + int(profile["durationDeltaDays"])
    stats["shooting_duration"] = int(stats.get("shooting_duration", 0) or 0) + int(profile["durationDeltaDays"])
    stats["total_cost"] = int(stats.get("total_cost", 0) or 0) + int(profile["costImpact"])
    return profile


def location_impact_line(profile: dict[str, Any]) -> str:
    cost = int(profile.get("costImpact") or 0)
    duration = int(profile.get("durationDeltaDays") or 0)
    stats = profile.get("stats") if isinstance(profile.get("stats"), dict) else {}
    parts = []
    if cost:
        parts.append(f"추가 비용 {money(cost)}")
    else:
        parts.append("추가 비용 없음")
    if duration:
        parts.append(f"촬영 일정 +{duration}일")
    permit = int(stats.get("location_permit_risk", 0) or 0)
    if permit > 0:
        parts.append("허가 리스크 상승")
    elif permit < 0:
        parts.append("허가 리스크 완화")
    if int(stats.get("shooting_quality", 0) or 0) > 0:
        parts.append("화면 완성도 상승")
    if int(stats.get("art_costume_prop_quality", 0) or 0) > 0:
        parts.append("미술/공간 완성도 상승")
    return " · ".join(parts)


def _strategy_by_id(strategy_id: str | None) -> dict[str, Any]:
    requested = str(strategy_id or "real_location")
    for option in LOCATION_STRATEGIES:
        if option["id"] == requested:
            return dict(option)
    return dict(LOCATION_STRATEGIES[0])


def _availability_note(strategy_id: str, scale_id: str | None, genre_id: str | None) -> str:
    if strategy_id == "overseas_location" and scale_id in {"scale_short", "scale_independent"}:
        return "작은 규모에서는 매우 공격적인 선택입니다. 비용과 일정 압박이 큽니다."
    if strategy_id == "set_build" and genre_id in {"genre_period_historical", "genre_fantasy", "genre_sf_disaster_monster"}:
        return "장르의 세계관을 통제하기 좋은 선택입니다."
    if strategy_id == "regional_location":
        return "지역 협조를 얻으면 제작비 일부를 방어할 수 있지만 일정 조율이 중요합니다."
    return ""
