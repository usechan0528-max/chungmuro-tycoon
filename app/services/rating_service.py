from __future__ import annotations

from typing import Any

from app.services.event_constants import GENRE_ID_ALIASES


CONTENT_RATINGS = [
    {
        "id": "all",
        "nameKo": "전체관람가",
        "ageFloor": 0,
        "description": "모든 연령층이 관람할 수 있는 등급.",
        "audienceMultiplier": 1.06,
        "secondaryMarketMultiplier": 1.08,
    },
    {
        "id": "age_12",
        "nameKo": "12세 이상 관람가",
        "ageFloor": 12,
        "description": "어린이 관객 일부가 제한되지만 가족·청소년 관객 접근성은 유지되는 등급.",
        "audienceMultiplier": 1.02,
        "secondaryMarketMultiplier": 1.02,
    },
    {
        "id": "age_15",
        "nameKo": "15세 이상 관람가",
        "ageFloor": 15,
        "description": "대부분의 상업영화가 노리는 현실적인 중간 등급.",
        "audienceMultiplier": 0.96,
        "secondaryMarketMultiplier": 0.99,
    },
    {
        "id": "age_19",
        "nameKo": "청소년 관람불가",
        "ageFloor": 19,
        "description": "청소년 관객과 일부 광고·상영 경로가 제한되는 등급.",
        "audienceMultiplier": 0.72,
        "secondaryMarketMultiplier": 0.93,
    },
    {
        "id": "restricted",
        "nameKo": "제한상영가",
        "ageFloor": 19,
        "description": "일반 상업 개봉이 크게 제한되는 고위험 등급.",
        "audienceMultiplier": 0.34,
        "secondaryMarketMultiplier": 0.72,
    },
]

_RATING_BY_ID = {rating["id"]: rating for rating in CONTENT_RATINGS}

GENRE_RATING_BASE = {
    "genre_crime_thriller": {"violence_intensity": 36, "rating_pressure": 38},
    "genre_action": {"violence_intensity": 36, "rating_pressure": 32},
    "genre_horror_occult": {"horror_intensity": 50, "rating_pressure": 42},
    "genre_romance_melodrama": {"sexual_content": 22, "rating_pressure": 16},
    "genre_comedy": {"rating_pressure": 10},
    "genre_family_human_drama": {"rating_pressure": 4},
    "genre_period_historical": {"violence_intensity": 22, "political_sensitivity": 18, "rating_pressure": 22},
    "genre_social_true_story": {"political_sensitivity": 44, "rating_pressure": 34},
    "genre_indie_art": {"political_sensitivity": 22, "rating_pressure": 22},
    "genre_sf_disaster_monster": {"violence_intensity": 18, "horror_intensity": 12, "rating_pressure": 20},
    "genre_fantasy": {"horror_intensity": 10, "rating_pressure": 14},
    "genre_animation": {"rating_pressure": 2},
}


def content_rating_definitions() -> list[dict[str, Any]]:
    return [dict(rating) for rating in CONTENT_RATINGS]


def rating_label(rating_id: str | None) -> str:
    return str(_RATING_BY_ID.get(str(rating_id or ""), {}).get("nameKo") or "등급 미정")


def initial_content_stats(genre_id: str, *, controversy_risk: int = 0) -> dict[str, int]:
    base = {
        "rating_pressure": 8,
        "violence_intensity": 0,
        "sexual_content": 0,
        "horror_intensity": 0,
        "political_sensitivity": 0,
    }
    base.update(GENRE_RATING_BASE.get(_canonical_genre_id(genre_id), {}))
    base["rating_pressure"] = _clamp(int(base.get("rating_pressure", 0)) + max(0, int(controversy_risk) // 3))
    return {key: _clamp(int(value)) for key, value in base.items()}


def estimate_content_rating(
    stats: dict[str, Any],
    *,
    genre_id: str | None = None,
    era_id: str | None = None,
) -> dict[str, Any]:
    if stats.get("content_rating"):
        rating_id = str(stats["content_rating"])
        return _rating_result(rating_id, _rating_reasons(stats, genre_id, era_id), _rating_score(stats, genre_id, era_id))

    score = _rating_score(stats, genre_id, era_id)
    if score >= 86:
        rating_id = "restricted"
    elif score >= 62:
        rating_id = "age_19"
    elif score >= 38:
        rating_id = "age_15"
    elif score >= 18:
        rating_id = "age_12"
    else:
        rating_id = "all"
    return _rating_result(rating_id, _rating_reasons(stats, genre_id, era_id), score)


def rating_market_effect(rating_id: str | None, *, genre_id: str | None = None) -> dict[str, float]:
    rating = _RATING_BY_ID.get(str(rating_id or ""), _RATING_BY_ID["age_15"])
    canonical_genre_id = _canonical_genre_id(genre_id)
    audience_multiplier = float(rating.get("audienceMultiplier", 1.0))
    secondary_multiplier = float(rating.get("secondaryMarketMultiplier", 1.0))
    if canonical_genre_id in {"genre_family_human_drama", "genre_animation"} and rating["id"] in {"all", "age_12"}:
        audience_multiplier *= 1.05
        secondary_multiplier *= 1.04
    if canonical_genre_id in {"genre_crime_thriller", "genre_horror_occult"} and rating["id"] == "age_19":
        secondary_multiplier *= 1.04
    return {
        "audienceMultiplier": round(audience_multiplier, 4),
        "secondaryMarketMultiplier": round(secondary_multiplier, 4),
    }


def _rating_score(stats: dict[str, Any], genre_id: str | None, era_id: str | None) -> int:
    genre_base = GENRE_RATING_BASE.get(_canonical_genre_id(genre_id), {})
    violence = _value(stats, "violence_intensity", genre_base.get("violence_intensity", 0))
    sexual = _value(stats, "sexual_content", genre_base.get("sexual_content", 0))
    horror = _value(stats, "horror_intensity", genre_base.get("horror_intensity", 0))
    politics = _value(stats, "political_sensitivity", genre_base.get("political_sensitivity", 0))
    pressure = _value(stats, "rating_pressure", genre_base.get("rating_pressure", 8))
    controversy = _value(stats, "controversy_risk", 0)
    era_bonus = 6 if str(era_id) in {"era_1980s", "era_1990s"} and politics >= 20 else 0
    score = (
        pressure * 0.45
        + violence * 0.34
        + sexual * 0.34
        + horror * 0.30
        + politics * 0.26
        + controversy * 0.18
        + era_bonus
    )
    return _clamp(int(round(score)))


def _rating_reasons(stats: dict[str, Any], genre_id: str | None, era_id: str | None) -> list[str]:
    reasons: list[str] = []
    genre_base = GENRE_RATING_BASE.get(_canonical_genre_id(genre_id), {})
    values = {
        "폭력성": _value(stats, "violence_intensity", genre_base.get("violence_intensity", 0)),
        "선정성": _value(stats, "sexual_content", genre_base.get("sexual_content", 0)),
        "공포감": _value(stats, "horror_intensity", genre_base.get("horror_intensity", 0)),
        "사회·정치적 민감성": _value(stats, "political_sensitivity", genre_base.get("political_sensitivity", 0)),
        "논란 가능성": _value(stats, "controversy_risk", 0),
    }
    for label, value in values.items():
        if value >= 45:
            reasons.append(f"{label}이 심의 판단에 크게 작용했다.")
        elif value >= 25:
            reasons.append(f"{label}에 대한 검토가 있었다.")
    if str(era_id) in {"era_1980s", "era_1990s"} and values["사회·정치적 민감성"] >= 20:
        reasons.append("시대적 심의 기조가 판단을 더 보수적으로 만들었다.")
    if not reasons:
        reasons.append("심의상 큰 제한 요소는 발견되지 않았다.")
    return reasons


def _rating_result(rating_id: str, reasons: list[str], score: int) -> dict[str, Any]:
    rating = _RATING_BY_ID.get(rating_id, _RATING_BY_ID["age_15"])
    return {
        "id": rating["id"],
        "nameKo": rating["nameKo"],
        "ageFloor": rating["ageFloor"],
        "description": rating["description"],
        "score": score,
        "reasons": reasons,
    }


def _value(stats: dict[str, Any], key: str, default: Any = 0) -> float:
    try:
        return float(stats.get(key, default) or 0)
    except (TypeError, ValueError):
        return 0.0


def _clamp(value: int, minimum: int = 0, maximum: int = 100) -> int:
    return max(minimum, min(maximum, int(value)))


def _canonical_genre_id(genre_id: str | None) -> str:
    raw = str(genre_id or "")
    return GENRE_ID_ALIASES.get(raw, raw)
