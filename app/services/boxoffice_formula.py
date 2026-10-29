from __future__ import annotations

import math
from typing import Any

from app.config import STUDIO_RECOVERY_RATE
from app.database import loads_json
from app.services.economic_service import CPI_BASE_YEAR, build_economic_modifiers
from app.services.game_state import clamp, money
from app.services.rating_service import estimate_content_rating, rating_market_effect


SCALE_MARKET_MULTIPLIER = {
    "scale_short": 0.08,
    "scale_independent": 0.22,
    "scale_low_budget_genre": 0.55,
    "scale_mid_commercial": 1.0,
    "scale_large_commercial": 1.35,
    "scale_tentpole": 1.7,
}

ERA_GENRE_ALIASES = {
    "genre_crime_thriller": ("crime_thriller", "crime", "crime_action", "crime_action_franchise", "ott_thriller"),
    "genre_action": ("action", "crime_action", "crime_action_franchise"),
    "genre_horror_occult": ("horror_occult", "horror", "low_budget_horror"),
    "genre_romance_melodrama": ("romance_melodrama", "melodrama", "romance_comedy", "romance_melodrama_theatrical", "romance_melodrama_ott"),
    "genre_comedy": ("comedy", "romance_comedy"),
    "genre_family_human_drama": ("social_drama", "literary_drama", "melodrama"),
    "genre_period_historical": ("historical", "war"),
    "genre_social_true_story": ("social_drama", "social_true_story", "literary_drama"),
    "genre_indie_art": ("independent_art", "independent_art_festival"),
    "genre_sf_disaster_monster": ("sf_disaster", "disaster", "monster"),
    "genre_fantasy": ("fantasy", "fantasy_ip"),
    "genre_animation": ("animation",),
}

FINAL_QUALITY_WEIGHTS = {
    "scenario_quality": 0.20,
    "directing_quality": 0.18,
    "acting_quality": 0.15,
    "casting_fit": 0.10,
    "genre_satisfaction": 0.15,
    "editing_quality": 0.10,
    "music_sound_quality": 0.05,
    "vfx_quality": 0.04,
    "shooting_quality": 0.03,
}

AUDIENCE_SCORE_WEIGHTS = {
    "final_quality": 0.35,
    "genre_satisfaction": 0.25,
    "casting_fit": 0.15,
    "acting_quality": 0.10,
    "pre_release_interest": 0.05,
    "audience_rejection_risk": -0.10,
}

def calculate_boxoffice(
    stats: dict[str, Any],
    project: dict[str, Any],
    era: dict[str, Any],
    ticket: dict[str, Any],
    genre: dict[str, Any],
) -> dict[str, Any]:
    audience_weight = float(genre.get("audience_weight", 1.0) or 1.0)
    critic_weight = float(genre.get("critic_weight", 1.0) or 1.0)
    boxoffice_weight = float(genre.get("boxoffice_weight", 1.0) or 1.0)

    final_quality = calculate_final_quality(stats)
    audience_score = calculate_audience_score(stats, final_quality) * audience_weight
    critic_score = calculate_critic_score(stats, final_quality, genre) * critic_weight
    opening_interest = calculate_opening_interest(stats, final_quality)
    word_of_mouth = calculate_word_of_mouth(stats, final_quality, audience_score)
    second_week_drop = calculate_second_week_drop(stats, audience_score, word_of_mouth)
    base_audience = calculate_base_audience(
        stats=stats,
        audience_score=audience_score,
        opening_interest=opening_interest,
        word_of_mouth=word_of_mouth,
    )
    economic_modifiers = _economic_modifiers_for_market(era)
    ticket_price_burden = int(era.get("ticket_price_burden") or ticket.get("audience_price_sensitivity", 50))
    theater_demand = int(era["theater_demand"])
    foreign_competition = int(era["foreign_competition"])
    audience_affordability = float(economic_modifiers.get("audience_affordability_modifier", 1.0))
    market_modifier = calculate_market_modifier(
        theater_demand=theater_demand,
        foreign_competition=foreign_competition,
        ticket_price_burden=ticket_price_burden,
        online_spread_power=int(era.get("online_spread_power", 50) or 50),
        special_format_demand=int(era.get("special_format_demand", 0) or 0),
        audience_affordability=audience_affordability,
        project=project,
        stats=stats,
    )
    scale_modifier = SCALE_MARKET_MULTIPLIER.get(project["scale_id"], 1.0)
    era_genre_weight = _era_genre_weight(project, genre, era)
    quality_multiplier = _score_multiplier(audience_score, center=62, step=125, minimum=0.72, maximum=1.35)
    long_tail_multiplier = _long_tail_multiplier(word_of_mouth, second_week_drop, stats)
    final_audience = max(
        0,
        int(
            base_audience
            * market_modifier
            * scale_modifier
            * boxoffice_weight
            * era_genre_weight
            * quality_multiplier
            * long_tail_multiplier
        ),
    )
    content_rating = estimate_content_rating(
        stats,
        genre_id=str(project.get("genre_id") or genre.get("id") or ""),
        era_id=str(era.get("id") or ""),
    )
    rating_effect = rating_market_effect(content_rating["id"], genre_id=str(project.get("genre_id") or genre.get("id") or ""))
    final_audience = max(0, int(final_audience * float(rating_effect["audienceMultiplier"])))
    average_ticket_price = int(ticket["average_ticket_price"])
    total_cost = project_total_cost(project, stats)
    gross_revenue = int(final_audience * average_ticket_price)
    secondary_market_fit = max(_stat(stats, "secondary_market_fit"), float(genre.get("secondary_market_fit", 50) or 50))
    secondary_market_revenue = int(
        gross_revenue
        * (0.018 + secondary_market_fit / 5200)
        * _score_multiplier(final_quality, center=60, step=180, minimum=0.86, maximum=1.18)
        * float(rating_effect["secondaryMarketMultiplier"])
    )
    settlement = calculate_release_settlement(
        final_audience=final_audience,
        average_ticket_price=average_ticket_price,
        studio_recovery_rate=STUDIO_RECOVERY_RATE,
        secondary_market_revenue=secondary_market_revenue,
        total_cost=total_cost,
    )
    opening_week_share = max(
        0.12,
        min(
            0.62,
            0.18
            + _stat(stats, "reservation_rate") / 350
            + opening_interest / 420
            + (100 - second_week_drop) / 800,
        ),
    )
    opening_week_audience = int(final_audience * opening_week_share)
    return {
        "final_quality": clamp(final_quality),
        "audience_score": clamp(audience_score),
        "critic_score": clamp(critic_score),
        "base_audience": int(base_audience),
        "market_modifier": market_modifier,
        "final_audience": final_audience,
        "opening_interest": clamp(opening_interest),
        "opening_week_audience": opening_week_audience,
        "word_of_mouth": clamp(word_of_mouth),
        "second_week_drop": clamp(second_week_drop),
        "quality_multiplier": quality_multiplier,
        "long_tail_multiplier": long_tail_multiplier,
        "average_ticket_price": average_ticket_price,
        "content_rating": content_rating["id"],
        "content_rating_name": content_rating["nameKo"],
        "content_rating_score": content_rating["score"],
        "content_rating_reasons": content_rating["reasons"],
        "content_rating_description": content_rating["description"],
        "content_rating_audience_multiplier": rating_effect["audienceMultiplier"],
        "content_rating_secondary_market_multiplier": rating_effect["secondaryMarketMultiplier"],
        "gross_revenue": settlement["gross_revenue"],
        "studio_revenue": settlement["studio_revenue"],
        "secondary_market_revenue": secondary_market_revenue,
        "total_cost": total_cost,
        "break_even_audience": settlement["break_even_audience"],
        "theatrical_break_even_audience": settlement["theatrical_break_even_audience"],
        "net_break_even_audience": settlement["break_even_audience"],
        "profit": settlement["profit"],
        "profit_margin": settlement["profit_margin"],
        "studio_recovery_rate": STUDIO_RECOVERY_RATE,
        "genre_boxoffice_weight": boxoffice_weight,
        "genre_critic_weight": critic_weight,
        "genre_audience_weight": audience_weight,
        "era_genre_weight": era_genre_weight,
        "economic_modifiers": economic_modifiers,
        "audience_affordability_modifier": audience_affordability,
        "effective_ticket_price_burden": ticket_price_burden,
        "effective_theater_demand": theater_demand,
    }


def calculate_final_quality(stats: dict[str, Any]) -> float:
    weighted = sum(_stat(stats, stat_id) * weight for stat_id, weight in FINAL_QUALITY_WEIGHTS.items())
    core_values = [
        _stat(stats, "scenario_quality"),
        _stat(stats, "directing_quality"),
        _stat(stats, "acting_quality"),
        _stat(stats, "casting_fit"),
        _stat(stats, "genre_satisfaction"),
        _stat(stats, "editing_quality"),
    ]
    craft_values = [
        _stat(stats, "shooting_quality"),
        _stat(stats, "art_costume_prop_quality"),
        _stat(stats, "music_sound_quality"),
        _stat(stats, "vfx_quality"),
        _stat(stats, "action_stunt_quality"),
    ]
    weakest_link_penalty = max(0.0, 52 - min(core_values)) * 0.16
    craft_synergy = (sum(craft_values) / len(craft_values) - 50) * 0.05
    casting_synergy = max(0.0, min(_stat(stats, "acting_quality"), _stat(stats, "casting_fit")) - 65) * 0.05
    risk_drag = (
        _stat(stats, "budget_overrun_risk", 20) * 0.025
        + _stat(stats, "schedule_delay_risk", 20) * 0.018
        + _stat(stats, "on_set_conflict_risk", 18) * 0.025
        + _stat(stats, "controversy_risk", 0) * 0.035
    )
    return _bounded_score(weighted + craft_synergy + casting_synergy - weakest_link_penalty - risk_drag)


def calculate_audience_score(stats: dict[str, Any], final_quality: float | None = None) -> float:
    quality = calculate_final_quality(stats) if final_quality is None else final_quality
    expectation_gap = max(0.0, _stat(stats, "pre_release_interest") - quality) * 0.10
    score = (
        quality * 0.31
        + _stat(stats, "genre_satisfaction") * 0.22
        + _stat(stats, "casting_fit") * 0.13
        + _stat(stats, "acting_quality") * 0.10
        + _stat(stats, "word_of_mouth") * 0.13
        + _stat(stats, "rewatch_index", 45) * 0.04
        + _stat(stats, "fandom_index", 40) * 0.03
        + _stat(stats, "pre_release_interest") * 0.05
        - _stat(stats, "audience_rejection_risk") * 0.13
        - _stat(stats, "controversy_risk", 0) * 0.05
        - expectation_gap
    )
    return _bounded_score(score)


def calculate_critic_score(stats: dict[str, Any], final_quality: float, genre: dict[str, Any]) -> float:
    artistic_value = _stat(stats, "artistic_sense", _stat(stats, "scenario_quality"))
    technical_craft = (
        _stat(stats, "shooting_quality")
        + _stat(stats, "editing_quality")
        + _stat(stats, "music_sound_quality")
        + _stat(stats, "art_costume_prop_quality")
        + max(_stat(stats, "vfx_quality"), _stat(stats, "action_stunt_quality"))
    ) / 5
    originality = _bounded_score(70 - _stat(stats, "plagiarism_risk") * 0.75)
    award_fit = float(genre.get("award_compatibility", 50) or 50)
    score = (
        final_quality * 0.29
        + _stat(stats, "scenario_quality") * 0.20
        + _stat(stats, "directing_quality") * 0.20
        + artistic_value * 0.10
        + technical_craft * 0.08
        + originality * 0.07
        + award_fit * 0.06
        - _stat(stats, "plagiarism_risk") * 0.11
        - _stat(stats, "controversy_risk") * 0.08
        - _stat(stats, "critic_backlash_risk") * 0.08
    )
    return _bounded_score(score)


def calculate_opening_interest(stats: dict[str, Any], final_quality: float) -> float:
    hype = (
        _stat(stats, "pre_release_interest") * 0.42
        + _stat(stats, "reservation_rate") * 0.28
        + _stat(stats, "online_buzz") * 0.16
        + _stat(stats, "fandom_index", 40) * 0.08
        + final_quality * 0.06
    )
    backlash_drag = _stat(stats, "press_backlash_risk", 0) * 0.08 + _stat(stats, "controversy_risk", 0) * 0.06
    return _bounded_score(hype - backlash_drag)


def calculate_word_of_mouth(stats: dict[str, Any], final_quality: float, audience_score: float) -> float:
    value = (
        _stat(stats, "word_of_mouth") * 0.34
        + audience_score * 0.30
        + final_quality * 0.18
        + _stat(stats, "genre_satisfaction") * 0.12
        + _stat(stats, "online_buzz") * 0.06
        - _stat(stats, "audience_rejection_risk") * 0.10
        - _stat(stats, "controversy_risk") * 0.04
    )
    return _bounded_score(value)


def calculate_second_week_drop(stats: dict[str, Any], audience_score: float, word_of_mouth: float) -> float:
    drop = (
        58
        + max(0.0, _stat(stats, "pre_release_interest") - audience_score) * 0.18
        + _stat(stats, "audience_rejection_risk") * 0.16
        + _stat(stats, "press_backlash_risk", 0) * 0.10
        - word_of_mouth * 0.18
        - _stat(stats, "rewatch_index", 45) * 0.08
    )
    return max(18.0, min(82.0, drop))


def calculate_base_audience(
    *,
    stats: dict[str, Any],
    audience_score: float,
    opening_interest: float,
    word_of_mouth: float,
) -> int:
    return int(
        _stat(stats, "pre_release_interest") * 9_000
        + _stat(stats, "reservation_rate") * 11_000
        + opening_interest * 8_500
        + audience_score * 18_000
        + word_of_mouth * 12_000
        + _stat(stats, "online_buzz") * 5_500
        + _stat(stats, "fandom_index", 40) * 4_500
    )


def calculate_market_modifier(
    *,
    theater_demand: int,
    foreign_competition: int,
    ticket_price_burden: int,
    online_spread_power: int,
    special_format_demand: int,
    audience_affordability: float,
    project: dict[str, Any],
    stats: dict[str, Any],
) -> float:
    theater = max(0.35, theater_demand / 100)
    foreign_pressure = max(0.35, 1 - foreign_competition / 230)
    ticket_pressure = max(0.55, 1 - ticket_price_burden / 360)
    online_bonus = 1 + max(-20, online_spread_power - 50) / 450
    special_format_bonus = 1.0
    if str(project.get("scale_id")) in {"scale_large_commercial", "scale_tentpole"}:
        special_format_bonus += special_format_demand / 900
    if _stat(stats, "vfx_quality", 50) >= 70:
        special_format_bonus += special_format_demand / 1500
    return max(
        0.12,
        min(1.65, theater * foreign_pressure * ticket_pressure * online_bonus * special_format_bonus * audience_affordability),
    )


def calculate_release_settlement(
    *,
    final_audience: int,
    average_ticket_price: int,
    studio_recovery_rate: float,
    secondary_market_revenue: int,
    total_cost: int,
) -> dict[str, Any]:
    gross_revenue = int(final_audience * average_ticket_price)
    studio_revenue = int(gross_revenue * studio_recovery_rate)
    theatrical_break_even_audience = math.ceil(total_cost / max(1, average_ticket_price * studio_recovery_rate))
    net_cost = max(0, int(total_cost) - int(secondary_market_revenue * 0.85))
    break_even_audience = math.ceil(net_cost / max(1, average_ticket_price * studio_recovery_rate))
    profit = studio_revenue + secondary_market_revenue - total_cost
    return {
        "gross_revenue": gross_revenue,
        "studio_revenue": studio_revenue,
        "profit": profit,
        "break_even_audience": break_even_audience,
        "theatrical_break_even_audience": theatrical_break_even_audience,
        "profit_margin": round(profit / max(1, total_cost), 4),
    }


def project_total_cost(project: dict[str, Any], stats: dict[str, Any] | None = None) -> int:
    base_total = int(project["production_budget"]) + int(project["marketing_budget"])
    if not isinstance(stats, dict):
        return base_total
    return max(base_total, int(stats.get("total_cost") or base_total))


def calculate_reputation_changes(result: dict[str, Any]) -> dict[str, Any]:
    break_even = max(1, int(result.get("break_even_audience") or 1))
    audience = int(result.get("final_audience") or 0)
    total_cost = max(1, int(result.get("total_cost") or 1))
    profit = int(result.get("profit") or 0)
    audience_ratio = audience / break_even
    profit_margin = profit / total_cost
    audience_scale = math.log1p(audience / 350_000)

    public_delta = round(
        (float(result.get("audience_score", 50)) - 55) / 7
        + (audience_ratio - 1) * 5
        + audience_scale * 1.2
        - float(result.get("second_week_drop", 50)) / 38
    )
    industry_delta = round(
        (float(result.get("final_quality", 50)) - 55) / 8
        + profit_margin * 8
        + min(5.0, audience_scale)
    )
    critic_delta = round(
        (float(result.get("critic_score", 50)) - 55) / 5
        + (float(result.get("final_quality", 50)) - 60) / 14
    )
    investor_delta = round(profit_margin * 13 + (audience_ratio - 1) * 4)
    creative_delta = round(
        (float(result.get("final_quality", 50)) - 55) / 6
        + (float(result.get("critic_score", 50)) - 55) / 12
    )
    global_delta = round(
        max(0.0, float(result.get("critic_score", 50)) - 72) / 6
        + max(0.0, audience - 3_000_000) / 1_800_000
    )
    reputation = {
        "public_reputation": clamp(public_delta, -18, 24),
        "industry_reputation": clamp(industry_delta, -16, 22),
        "critic_reputation": clamp(critic_delta, -16, 22),
        "investor_reputation": clamp(investor_delta, -20, 24),
        "creative_reputation": clamp(creative_delta, -14, 20),
        "global_reputation": clamp(global_delta, -4, 16),
    }
    studio_fame_delta = clamp(
        reputation["public_reputation"] * 0.50
        + reputation["industry_reputation"] * 0.22
        + reputation["critic_reputation"] * 0.18
        + reputation["global_reputation"] * 0.10,
        -20,
        24,
    )
    network = {
        "distribution_network": clamp(audience / 500_000 + profit_margin * 2, -8, 16),
        "investor_network": clamp(profit_margin * 5 + (audience_ratio - 1) * 2, -10, 14),
        "critic_access": clamp((float(result.get("critic_score", 50)) - 60) / 8, -6, 10),
    }
    return {
        "studio_fame_delta": studio_fame_delta,
        "reputation": reputation,
        "network": network,
    }


def _era_genre_weight(project: dict[str, Any], genre: dict[str, Any], era: dict[str, Any]) -> float:
    modifiers = era.get("era_genre_modifiers")
    if isinstance(modifiers, str):
        modifiers = loads_json(modifiers, {})
    if not isinstance(modifiers, dict) or not modifiers:
        return 1.0
    genre_id = str(project.get("genre_id") or genre.get("id") or "")
    values = [
        float(modifiers[key])
        for key in ERA_GENRE_ALIASES.get(genre_id, ())
        if isinstance(modifiers.get(key), int | float)
    ]
    if not values:
        return 1.0
    strongest = max(values, key=lambda value: abs(value))
    return max(0.5, min(1.4, 1 + strongest / 100))


def _score_multiplier(
    value: float,
    *,
    center: float,
    step: float,
    minimum: float,
    maximum: float,
) -> float:
    return max(minimum, min(maximum, 1 + (float(value) - center) / step))


def _long_tail_multiplier(word_of_mouth: float, second_week_drop: float, stats: dict[str, Any]) -> float:
    rewatch = _stat(stats, "rewatch_index", 45)
    cult = _stat(stats, "cult_potential", 35)
    value = 1 + (word_of_mouth - 58) / 210 - (second_week_drop - 48) / 260 + (rewatch - 45) / 500 + cult / 1800
    return max(0.72, min(1.28, value))


def _bounded_score(value: float) -> float:
    return max(0.0, min(100.0, float(value)))


def _economic_modifiers_for_market(era: dict[str, Any]) -> dict[str, Any]:
    modifiers = era.get("economic_modifiers")
    if isinstance(modifiers, str):
        modifiers = loads_json(modifiers, {})
    if isinstance(modifiers, dict) and modifiers:
        return modifiers
    year = era.get("year")
    try:
        return build_economic_modifiers(int(year))
    except (TypeError, ValueError):
        return build_economic_modifiers(CPI_BASE_YEAR)


def _stat(stats: dict[str, Any], key: str, default: float = 50) -> float:
    return float(stats.get(key, default))


def summarize_result(result: dict[str, Any]) -> str:
    rating_id = str(result.get("content_rating") or "")
    rating_note = ""
    if rating_id == "age_19":
        rating_note = "청소년 관람불가 등급으로 관객층은 좁아졌지만 타깃은 분명했다. "
    elif rating_id == "restricted":
        rating_note = "제한상영가 등급이 상업 개봉 규모를 크게 눌렀다. "
    if result["profit"] >= 0 and result["final_audience"] >= result["break_even_audience"]:
        return f"{rating_note}손익분기점을 넘겼다. 정산 기준 수익은 {money(result['profit'])}이다."
    if result["critic_score"] >= 70:
        return f"{rating_note}상업적 성과는 아쉽지만 평단의 지지를 얻었다."
    if result["final_audience"] > result["break_even_audience"] * 0.7:
        return f"{rating_note}크게 실패하지는 않았지만 다음 작품을 위한 설득이 필요하다."
    return f"{rating_note}흥행 실패다. 자본과 신뢰 회복이 다음 과제가 되었다."
