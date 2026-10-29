from __future__ import annotations


WALK_OUT_CHOICE_ID = "walk_out"
WALK_OUT_COUNTER_PRESSURE_CHANCE = 8

EFFECT_SECTIONS = {"stats", "reputation", "network", "studio", "playerStats", "flags", "version"}

PROJECT_SCALE_ORDER = [
    "scale_short",
    "scale_independent",
    "scale_low_budget_genre",
    "scale_mid_commercial",
    "scale_large_commercial",
    "scale_tentpole",
]

SCALE_ID_ALIASES = {
    "short_film": "scale_short",
    "independent_film": "scale_independent",
    "low_budget_genre": "scale_low_budget_genre",
    "mid_commercial": "scale_mid_commercial",
    "large_commercial": "scale_large_commercial",
    "tentpole_blockbuster": "scale_tentpole",
}

GENRE_ID_ALIASES = {
    "crime_thriller": "genre_crime_thriller",
    "action": "genre_action",
    "horror_occult": "genre_horror_occult",
    "romance_melodrama": "genre_romance_melodrama",
    "comedy": "genre_comedy",
    "family_human_drama": "genre_family_human_drama",
    "historical_period": "genre_period_historical",
    "period_historical": "genre_period_historical",
    "social_true_story": "genre_social_true_story",
    "indie_art": "genre_indie_art",
    "sf_disaster_monster": "genre_sf_disaster_monster",
    "fantasy": "genre_fantasy",
    "animation": "genre_animation",
}

REPUTATION_EFFECT_KEYS = {
    "public_reputation",
    "industry_reputation",
    "critic_reputation",
    "investor_reputation",
    "creative_reputation",
    "global_reputation",
}

NETWORK_EFFECT_KEYS = {
    "actor_network",
    "director_network",
    "production_network",
    "investor_network",
    "distribution_network",
    "press_network",
    "critic_access",
    "festival_network",
    "school_network",
    "regional_network",
}

STUDIO_EFFECT_KEYS = {
    "cash",
    "debt",
    "fame",
    "own_capital",
    "investment_capital",
    "loan_capital",
    "loan_balance",
    "credit_limit",
    "field_reputation",
    "pay_reputation",
    "creative_freedom",
    "interference_reputation",
    "studio_cash",
    "studio_debt",
    "studio_fame",
    "studio_own_capital",
    "studio_investment_capital",
    "studio_loan_capital",
    "studio_loan_balance",
    "studio_credit_limit",
    "studio_field_reputation",
    "studio_pay_reputation",
    "studio_creative_freedom",
    "studio_interference_reputation",
}

UNBOUNDED_EFFECT_KEYS = {
    "cash",
    "debt",
    "credit_limit",
    "production_budget",
    "marketing_budget",
    "total_cost",
    "investment_amount",
    "break_even_audience",
    "secondary_market_revenue",
    "final_audience",
    "boxoffice_revenue",
    "production_duration",
    "pre_production_duration",
    "shooting_duration",
    "planned_shooting_days",
    "shooting_duration_delta_days",
    "shooting_duration_min_days",
    "shooting_duration_max_days",
    "post_production_duration",
    "marketing_duration",
    "delay_days",
    "actor_commitment_duration",
    "director_commitment_duration",
}

WALK_OUT_BASE_EFFECTS = {
    "stats": {
        "financial_risk": 6,
        "production_shutdown_risk": 6,
        "schedule_delay_risk": 3,
        "on_set_conflict_risk": 4,
        "controversy_risk": 3,
        "press_backlash_risk": 8,
    },
    "reputation": {
        "industry_reputation": -3,
        "investor_reputation": -4,
        "creative_reputation": 1,
        "public_reputation": -1,
    },
    "network": {
        "actor_network": -2,
        "production_network": -3,
        "investor_network": -4,
        "distribution_network": -2,
        "press_network": -3,
    },
    "flags": {
        "dialogue_closed_by_walk_out": True,
        "negotiation_failure_risk": "increased",
        "relationship_damage": "increased",
        "press_backlash_risk": "increased",
    },
}

WALK_OUT_COUNTER_PRESSURE_EFFECTS = {
    "stats": {
        "financial_risk": -3,
        "production_shutdown_risk": -3,
        "pre_release_interest": 4,
        "press_backlash_risk": -2,
    },
    "reputation": {
        "creative_reputation": 5,
        "industry_reputation": 2,
        "investor_reputation": 1,
    },
    "network": {
        "press_network": 2,
    },
    "flags": {
        "walk_out_counter_pressure_success": True,
    },
}

RISK_EFFECT_KEYS = {
    "financial_risk",
    "production_shutdown_risk",
    "schedule_delay_risk",
    "budget_overrun_risk",
    "on_set_conflict_risk",
    "plagiarism_risk",
    "controversy_risk",
    "press_backlash_risk",
    "critic_backlash_risk",
    "audience_rejection_risk",
    "script_structure_issue",
    "script_dialogue_weakness",
    "character_motivation_issue",
    "script_pacing_issue",
    "investor_package_risk",
    "adaptation_rights_risk",
    "game_over_risk",
    "series_fatigue",
}

POSITIVE_EFFECT_SENTENCES = {
    "finance": "재무 여력이 조금 나아졌다.",
    "investment": "투자 논의가 조금 더 유리한 방향으로 움직였다.",
    "quality": "작품의 설득력과 완성도에 긍정적인 변화가 생겼다.",
    "market": "사전 관심과 시장 반응이 살아났다.",
    "reputation": "업계 안팎의 평판이 조금 좋아졌다.",
    "network": "관련 인맥과 협력 관계가 넓어졌다.",
    "risk": "제작 과정의 부담이 조금 줄었다.",
    "time": "일정 부담이 조금 줄었다.",
}

NEGATIVE_EFFECT_SENTENCES = {
    "finance": "현금과 비용 측면의 부담이 생겼다.",
    "time": "일정과 후반 대응에는 부담이 생겼다.",
    "quality": "작품의 일부 완성도에는 부담이 생겼다.",
    "market": "사전 관심과 관객 반응에는 불안 요소가 남았다.",
    "reputation": "평판에는 작은 흠집이 생겼다.",
    "network": "상대와의 관계가 조금 틀어졌다.",
    "risk": "협상 실패와 제작 리스크가 커졌다.",
    "press": "언론 역풍에 대비해야 하는 상황이 됐다.",
}
