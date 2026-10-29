from __future__ import annotations

import sqlite3
from pathlib import Path

from app.db_core import _resolve_database_path, get_connection


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS schema_info (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS eras (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    start_year INTEGER NOT NULL,
    end_year INTEGER,
    description TEXT,
    theater_demand INTEGER DEFAULT 50,
    ott_power INTEGER DEFAULT 0,
    foreign_competition INTEGER DEFAULT 50,
    middle_budget_risk INTEGER DEFAULT 50,
    special_format_demand INTEGER DEFAULT 0,
    online_spread_power INTEGER DEFAULT 0,
    ticket_price_burden INTEGER DEFAULT 50,
    unlocked_systems_json TEXT,
    locked_systems_json TEXT
);

CREATE TABLE IF NOT EXISTS genres (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    era_fit_json TEXT,
    scenario_weight INTEGER DEFAULT 10,
    directing_weight INTEGER DEFAULT 10,
    actors_weight INTEGER DEFAULT 10,
    shooting_weight INTEGER DEFAULT 10,
    art_weight INTEGER DEFAULT 10,
    stunt_weight INTEGER DEFAULT 0,
    vfx_weight INTEGER DEFAULT 0,
    sound_weight INTEGER DEFAULT 10,
    editing_weight INTEGER DEFAULT 10,
    contingency_weight INTEGER DEFAULT 5,
    boxoffice_weight REAL DEFAULT 1.0,
    critic_weight REAL DEFAULT 1.0,
    audience_weight REAL DEFAULT 1.0,
    success_factors_json TEXT,
    risk_factors_json TEXT,
    major_risks_json TEXT,
    critic_weights_json TEXT,
    audience_weights_json TEXT,
    franchise_fit INTEGER DEFAULT 50,
    secondary_market_fit INTEGER DEFAULT 50,
    plagiarism_sensitivity INTEGER DEFAULT 50,
    award_compatibility INTEGER DEFAULT 50
);

CREATE TABLE IF NOT EXISTS content_ratings (
    id TEXT PRIMARY KEY,
    name_ko TEXT NOT NULL,
    age_floor INTEGER DEFAULT 0,
    description TEXT,
    audience_multiplier REAL DEFAULT 1.0,
    secondary_market_multiplier REAL DEFAULT 1.0
);

CREATE TABLE IF NOT EXISTS system_definitions (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    implementation_status TEXT DEFAULT 'foundation',
    description TEXT,
    primary_tables_json TEXT,
    primary_services_json TEXT
);

CREATE TABLE IF NOT EXISTS stat_definitions (
    id TEXT PRIMARY KEY,
    name_ko TEXT NOT NULL,
    category TEXT NOT NULL,
    min_value INTEGER DEFAULT 0,
    max_value INTEGER DEFAULT 100,
    hidden INTEGER DEFAULT 1,
    description TEXT
);

CREATE TABLE IF NOT EXISTS reputation_definitions (
    id TEXT PRIMARY KEY,
    name_ko TEXT NOT NULL,
    description TEXT,
    low_text TEXT,
    mid_text TEXT,
    high_text TEXT
);

CREATE TABLE IF NOT EXISTS network_definitions (
    id TEXT PRIMARY KEY,
    name_ko TEXT NOT NULL,
    target_type TEXT DEFAULT 'industry',
    description TEXT,
    low_text TEXT,
    mid_text TEXT,
    high_text TEXT
);

CREATE TABLE IF NOT EXISTS starting_positions (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    cash_multiplier REAL DEFAULT 1.0,
    initial_stats_json TEXT,
    initial_reputation_json TEXT,
    initial_network_json TEXT
);

CREATE TABLE IF NOT EXISTS character_option_sets (
    category TEXT NOT NULL,
    id TEXT NOT NULL,
    label TEXT NOT NULL,
    description TEXT,
    effects_json TEXT,
    PRIMARY KEY (category, id)
);

CREATE TABLE IF NOT EXISTS project_scales (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    min_budget INTEGER NOT NULL,
    max_budget INTEGER NOT NULL,
    min_events INTEGER DEFAULT 1,
    max_events INTEGER DEFAULT 3,
    failure_impact TEXT DEFAULT 'normal',
    required_stages_json TEXT,
    stage_flow_json TEXT,
    optional_stages_json TEXT,
    required_reputation INTEGER DEFAULT 0,
    required_network INTEGER DEFAULT 0,
    game_over_risk_multiplier REAL DEFAULT 1.0
);

CREATE TABLE IF NOT EXISTS people (
    id TEXT PRIMARY KEY,
    name_ko TEXT NOT NULL,
    name_en TEXT,
    type TEXT NOT NULL,
    birth_year INTEGER,
    available_from INTEGER,
    status TEXT DEFAULT 'active',
    protection_level TEXT DEFAULT 'none',
    current_stats_json TEXT,
    potential_stats_json TEXT,
    genre_fit_json TEXT,
    historical_filmography_locked INTEGER DEFAULT 0,
    stat_profile_json TEXT,
    public_profile_json TEXT
);

CREATE TABLE IF NOT EXISTS critics (
    id TEXT PRIMARY KEY,
    name_ko TEXT NOT NULL,
    type TEXT DEFAULT 'critic',
    available_from INTEGER,
    critic_type_json TEXT,
    taste_profile_json TEXT,
    influence_json TEXT,
    scoring_style_json TEXT,
    public_description TEXT
);

CREATE TABLE IF NOT EXISTS historical_events (
    id TEXT PRIMARY KEY,
    year INTEGER NOT NULL,
    month INTEGER,
    title TEXT NOT NULL,
    type TEXT NOT NULL,
    fixed_level TEXT DEFAULT 'semiFixed',
    description TEXT,
    effects_json TEXT,
    unlocks_json TEXT
);

CREATE TABLE IF NOT EXISTS ticket_prices (
    year INTEGER PRIMARY KEY,
    average_ticket_price INTEGER NOT NULL,
    perceived_ticket_price INTEGER,
    premium_format_multiplier REAL DEFAULT 1.0,
    audience_price_sensitivity INTEGER DEFAULT 50,
    source_type TEXT DEFAULT 'historical'
);

CREATE TABLE IF NOT EXISTS production_events (
    id TEXT PRIMARY KEY,
    stage TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    npc_type TEXT,
    npc_traits_json TEXT,
    npc_line TEXT,
    trigger_json TEXT,
    choices_json TEXT
);

CREATE TABLE IF NOT EXISTS project_stage_definitions (
    id TEXT PRIMARY KEY,
    sequence INTEGER NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    stage_group TEXT DEFAULT 'production',
    required_for_scales_json TEXT
);

CREATE TABLE IF NOT EXISTS simulation_events (
    id TEXT PRIMARY KEY,
    category TEXT NOT NULL,
    stage TEXT,
    scope TEXT DEFAULT 'project',
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    fixed_level TEXT DEFAULT 'dynamic',
    weight INTEGER DEFAULT 100,
    cooldown_months INTEGER DEFAULT 0,
    npc_type TEXT,
    npc_traits_json TEXT,
    npc_line TEXT,
    trigger_json TEXT,
    choices_json TEXT
);

CREATE TABLE IF NOT EXISTS organizations (
    id TEXT PRIMARY KEY,
    name_ko TEXT NOT NULL,
    name_en TEXT,
    org_type TEXT NOT NULL,
    available_from INTEGER,
    power INTEGER DEFAULT 50,
    reputation_json TEXT,
    strategy_json TEXT,
    public_profile_json TEXT
);

CREATE TABLE IF NOT EXISTS player_state (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    name TEXT NOT NULL,
    gender TEXT,
    age INTEGER,
    current_year INTEGER NOT NULL,
    current_month INTEGER NOT NULL,
    current_day INTEGER NOT NULL DEFAULT 1,
    position TEXT NOT NULL,
    cash INTEGER DEFAULT 0,
    debt INTEGER DEFAULT 0,
    stats_json TEXT,
    reputation_json TEXT,
    network_json TEXT
);

CREATE TABLE IF NOT EXISTS studio_state (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    studio_name TEXT,
    fame INTEGER DEFAULT 0,
    cash INTEGER DEFAULT 0,
    debt INTEGER DEFAULT 0,
    own_capital INTEGER DEFAULT 0,
    investment_capital INTEGER DEFAULT 0,
    loan_capital INTEGER DEFAULT 0,
    loan_balance INTEGER DEFAULT 0,
    credit_limit INTEGER DEFAULT 0,
    field_reputation INTEGER DEFAULT 50,
    pay_reputation INTEGER DEFAULT 50,
    creative_freedom INTEGER DEFAULT 50,
    interference_reputation INTEGER DEFAULT 50,
    reputation_tags_json TEXT,
    reputation_summary TEXT
);

CREATE TABLE IF NOT EXISTS loans (
    id TEXT PRIMARY KEY,
    lender_name TEXT,
    principal INTEGER NOT NULL,
    remaining_principal INTEGER NOT NULL,
    accrued_interest INTEGER DEFAULT 0,
    annual_interest_rate REAL DEFAULT 0.0,
    monthly_payment_amount INTEGER DEFAULT 0,
    payments_made INTEGER DEFAULT 0,
    delinquent_months INTEGER DEFAULT 0,
    start_year INTEGER NOT NULL,
    start_month INTEGER NOT NULL,
    due_year INTEGER,
    due_month INTEGER,
    last_interest_year INTEGER,
    last_interest_month INTEGER,
    next_payment_year INTEGER,
    next_payment_month INTEGER,
    status TEXT DEFAULT 'active',
    purpose TEXT,
    metadata_json TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS finance_transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    year INTEGER,
    month INTEGER,
    day INTEGER,
    transaction_type TEXT NOT NULL,
    amount INTEGER NOT NULL,
    source TEXT,
    target TEXT,
    project_id TEXT,
    loan_id TEXT,
    description TEXT,
    metadata_json TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS crew_work_history (
    id TEXT PRIMARY KEY,
    work_type TEXT NOT NULL,
    title TEXT NOT NULL,
    start_year INTEGER NOT NULL,
    start_month INTEGER NOT NULL,
    start_day INTEGER NOT NULL,
    end_year INTEGER NOT NULL,
    end_month INTEGER NOT NULL,
    end_day INTEGER NOT NULL,
    days_worked INTEGER DEFAULT 0,
    daily_wage INTEGER DEFAULT 0,
    total_pay INTEGER DEFAULT 0,
    stats_delta_json TEXT,
    network_delta_json TEXT,
    summary TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    genre_id TEXT NOT NULL,
    scale_id TEXT NOT NULL,
    status TEXT NOT NULL,
    production_budget INTEGER DEFAULT 0,
    marketing_budget INTEGER DEFAULT 0,
    stage TEXT DEFAULT 'planning',
    stats_json TEXT,
    created_year INTEGER,
    release_year INTEGER,
    release_month INTEGER,
    content_rating TEXT,
    rating_reason_json TEXT
);

CREATE TABLE IF NOT EXISTS project_budget_allocations (
    project_id TEXT NOT NULL,
    category TEXT NOT NULL,
    percentage INTEGER DEFAULT 0,
    amount INTEGER DEFAULT 0,
    notes TEXT,
    PRIMARY KEY (project_id, category)
);

CREATE TABLE IF NOT EXISTS project_financing (
    project_id TEXT PRIMARY KEY,
    total_cost INTEGER DEFAULT 0,
    own_capital_used INTEGER DEFAULT 0,
    investment_used INTEGER DEFAULT 0,
    loan_used INTEGER DEFAULT 0,
    investment_secured INTEGER DEFAULT 0,
    investor_recouped INTEGER DEFAULT 0,
    investor_equity_percent REAL DEFAULT 0.0,
    investor_profit_share REAL DEFAULT 0.0,
    recoupment_priority TEXT DEFAULT 'investor_first',
    loan_interest_estimate INTEGER DEFAULT 0,
    contract_terms_json TEXT,
    financing_json TEXT,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS investment_contracts (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    investor_name TEXT,
    investment_amount INTEGER DEFAULT 0,
    equity_percent REAL DEFAULT 0.0,
    profit_share REAL DEFAULT 0.0,
    recoupment_priority TEXT DEFAULT 'investor_first',
    recoupment_cap INTEGER DEFAULT 0,
    recouped_amount INTEGER DEFAULT 0,
    status TEXT DEFAULT 'active',
    signed_year INTEGER,
    signed_month INTEGER,
    signed_day INTEGER,
    contract_terms_json TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS project_people (
    project_id TEXT NOT NULL,
    person_id TEXT NOT NULL,
    role TEXT NOT NULL,
    contract_fee INTEGER DEFAULT 0,
    sequel_option INTEGER DEFAULT 0,
    promotion_obligation INTEGER DEFAULT 0,
    promotion_days INTEGER DEFAULT 0,
    schedule_commitment_months INTEGER DEFAULT 0,
    contract_options_json TEXT,
    status TEXT DEFAULT 'attached',
    contribution_json TEXT,
    PRIMARY KEY (project_id, person_id, role)
);

CREATE TABLE IF NOT EXISTS casting_offers (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    person_id TEXT NOT NULL,
    role TEXT NOT NULL,
    contract_fee INTEGER DEFAULT 0,
    commitment_months INTEGER DEFAULT 0,
    sequel_option INTEGER DEFAULT 0,
    promotion_obligation INTEGER DEFAULT 0,
    promotion_days INTEGER DEFAULT 0,
    contract_terms_json TEXT,
    status TEXT DEFAULT 'pending',
    sent_year INTEGER,
    sent_month INTEGER,
    sent_day INTEGER,
    response_due_year INTEGER,
    response_due_month INTEGER,
    response_due_day INTEGER,
    responded_year INTEGER,
    responded_month INTEGER,
    responded_day INTEGER,
    accepted INTEGER,
    result_text TEXT,
    notes_json TEXT,
    popup_seen INTEGER DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS project_versions (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    film_id TEXT,
    version_type TEXT NOT NULL,
    name TEXT NOT NULL,
    status TEXT DEFAULT 'planned',
    runtime_minutes INTEGER DEFAULT 0,
    quality_delta INTEGER DEFAULT 0,
    audience_delta INTEGER DEFAULT 0,
    critic_delta INTEGER DEFAULT 0,
    secondary_market_delta INTEGER DEFAULT 0,
    selected_for_theatrical INTEGER DEFAULT 0,
    selected_for_ott INTEGER DEFAULT 0,
    description TEXT,
    metrics_json TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(project_id, version_type)
);

CREATE TABLE IF NOT EXISTS project_scenario_development (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    sequence INTEGER NOT NULL,
    step_id TEXT NOT NULL,
    step_name TEXT NOT NULL,
    planned_stage TEXT,
    start_year INTEGER,
    start_month INTEGER,
    start_day INTEGER,
    end_year INTEGER,
    end_month INTEGER,
    end_day INTEGER,
    status TEXT DEFAULT 'planned',
    diagnosis_label TEXT,
    diagnosis_text TEXT,
    risk_note TEXT,
    suggested_action TEXT,
    internal_metrics_json TEXT,
    metadata_json TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(project_id, step_id)
);

CREATE TABLE IF NOT EXISTS project_crew_roles (
    project_id TEXT NOT NULL,
    role_id TEXT NOT NULL,
    role_name TEXT NOT NULL,
    department TEXT,
    required INTEGER DEFAULT 1,
    filled_status TEXT DEFAULT 'planned',
    seniority TEXT DEFAULT 'mid',
    estimated_fee INTEGER DEFAULT 0,
    assigned_person_id TEXT,
    contribution_json TEXT,
    notes TEXT,
    PRIMARY KEY (project_id, role_id)
);

CREATE TABLE IF NOT EXISTS project_location_plans (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    location_strategy TEXT NOT NULL,
    location_name TEXT NOT NULL,
    location_type TEXT,
    cost_impact INTEGER DEFAULT 0,
    quality_delta INTEGER DEFAULT 0,
    permit_risk_delta INTEGER DEFAULT 0,
    regional_network_delta INTEGER DEFAULT 0,
    duration_delta_days INTEGER DEFAULT 0,
    status TEXT DEFAULT 'selected',
    description TEXT,
    metadata_json TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS shooting_schedule_blocks (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    sequence INTEGER NOT NULL,
    stage TEXT DEFAULT 'shooting',
    start_year INTEGER,
    start_month INTEGER,
    start_day INTEGER,
    end_year INTEGER,
    end_month INTEGER,
    end_day INTEGER,
    unit_name TEXT,
    location_type TEXT,
    planned_days INTEGER DEFAULT 0,
    status TEXT DEFAULT 'planned',
    description TEXT,
    metadata_json TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS project_cashflows (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    planned_stage TEXT,
    planned_year INTEGER,
    planned_month INTEGER,
    planned_day INTEGER,
    due_year INTEGER,
    due_month INTEGER,
    due_day INTEGER,
    paid_year INTEGER,
    paid_month INTEGER,
    paid_day INTEGER,
    amount INTEGER NOT NULL,
    source TEXT,
    target TEXT,
    cashflow_type TEXT,
    status TEXT DEFAULT 'planned',
    description TEXT,
    metadata_json TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS test_screenings (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    screening_type TEXT DEFAULT 'internal',
    year INTEGER,
    month INTEGER,
    day INTEGER,
    audience_type TEXT,
    score_band TEXT,
    result_summary TEXT,
    notes_json TEXT,
    effects_json TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS reshoot_orders (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    reason TEXT,
    planned_days INTEGER DEFAULT 0,
    estimated_cost INTEGER DEFAULT 0,
    status TEXT DEFAULT 'planned',
    year INTEGER,
    month INTEGER,
    day INTEGER,
    metadata_json TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS marketing_assets (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    asset_type TEXT NOT NULL,
    planned_stage TEXT,
    planned_year INTEGER,
    planned_month INTEGER,
    planned_day INTEGER,
    release_year INTEGER,
    release_month INTEGER,
    release_day INTEGER,
    channel TEXT,
    status TEXT DEFAULT 'planned',
    sentiment_band TEXT,
    buzz_score INTEGER DEFAULT 0,
    result_summary TEXT,
    metadata_json TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS marketing_reactions (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    asset_id TEXT,
    reaction_type TEXT,
    year INTEGER,
    month INTEGER,
    day INTEGER,
    sentiment_band TEXT,
    buzz_score INTEGER DEFAULT 0,
    audience_summary TEXT,
    press_summary TEXT,
    online_summary TEXT,
    effects_json TEXT,
    metadata_json TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS stage_greeting_schedules (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    year INTEGER,
    month INTEGER,
    day INTEGER,
    city TEXT,
    venue TEXT,
    event_name TEXT,
    cast_scope TEXT,
    expected_attendance INTEGER DEFAULT 0,
    estimated_cost INTEGER DEFAULT 0,
    status TEXT DEFAULT 'planned',
    result_summary TEXT,
    metadata_json TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS project_distribution (
    project_id TEXT PRIMARY KEY,
    distributor_id TEXT,
    deal_type TEXT,
    marketing_commitment INTEGER DEFAULT 0,
    screen_power INTEGER DEFAULT 0,
    terms_json TEXT
);

CREATE TABLE IF NOT EXISTS completed_films (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    genre_id TEXT,
    scale_id TEXT,
    release_year INTEGER,
    release_month INTEGER,
    production_budget INTEGER,
    marketing_budget INTEGER,
    total_cost INTEGER,
    final_audience INTEGER,
    gross_revenue INTEGER,
    break_even_audience INTEGER,
    critic_score INTEGER,
    audience_score INTEGER,
    content_rating TEXT,
    rating_reason_json TEXT,
    result_summary TEXT
);

CREATE TABLE IF NOT EXISTS theatrical_runs (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    film_id TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    release_year INTEGER NOT NULL,
    release_month INTEGER NOT NULL,
    release_day INTEGER NOT NULL,
    current_day INTEGER DEFAULT 0,
    max_days INTEGER DEFAULT 28,
    forecast_json TEXT,
    daily_plan_json TEXT,
    final_result_json TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS theatrical_daily_results (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    day_number INTEGER NOT NULL,
    year INTEGER NOT NULL,
    month INTEGER NOT NULL,
    day INTEGER NOT NULL,
    daily_audience INTEGER DEFAULT 0,
    cumulative_audience INTEGER DEFAULT 0,
    daily_revenue INTEGER DEFAULT 0,
    cumulative_revenue INTEGER DEFAULT 0,
    note TEXT,
    metrics_json TEXT,
    UNIQUE(run_id, day_number)
);

CREATE TABLE IF NOT EXISTS relationships (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    target_id TEXT NOT NULL,
    target_type TEXT NOT NULL,
    trust INTEGER DEFAULT 0,
    awareness INTEGER DEFAULT 0,
    last_contact_year INTEGER
);

CREATE TABLE IF NOT EXISTS market_state (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    year INTEGER NOT NULL,
    month INTEGER NOT NULL,
    theater_demand INTEGER DEFAULT 50,
    ott_power INTEGER DEFAULT 0,
    foreign_competition INTEGER DEFAULT 50,
    korean_film_trust INTEGER DEFAULT 50,
    genre_trends_json TEXT,
    modifiers_json TEXT,
    UNIQUE (year, month)
);

CREATE TABLE IF NOT EXISTS market_releases (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    origin TEXT NOT NULL,
    release_year INTEGER NOT NULL,
    release_month INTEGER,
    genre_id TEXT,
    scale_id TEXT,
    expected_audience INTEGER DEFAULT 0,
    actual_audience INTEGER,
    effects_json TEXT
);

CREATE TABLE IF NOT EXISTS film_reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    film_id TEXT NOT NULL,
    critic_id TEXT,
    source_type TEXT DEFAULT 'critic',
    score INTEGER,
    quote TEXT,
    effects_json TEXT
);

CREATE TABLE IF NOT EXISTS awards (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    country TEXT DEFAULT 'KR',
    founded_year INTEGER,
    prestige INTEGER DEFAULT 50,
    categories_json TEXT,
    public_profile_json TEXT
);

CREATE TABLE IF NOT EXISTS award_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    award_id TEXT NOT NULL,
    film_id TEXT,
    year INTEGER NOT NULL,
    category TEXT NOT NULL,
    result TEXT NOT NULL,
    effects_json TEXT
);

CREATE TABLE IF NOT EXISTS intellectual_properties (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    origin_film_id TEXT,
    owner_type TEXT DEFAULT 'studio',
    owner_id TEXT,
    ip_type TEXT DEFAULT 'original',
    ip_value INTEGER DEFAULT 0,
    franchise_power INTEGER DEFAULT 0,
    sequel_demand INTEGER DEFAULT 0,
    cult_potential INTEGER DEFAULT 0,
    reevaluation_potential INTEGER DEFAULT 0,
    status TEXT DEFAULT 'active',
    metadata_json TEXT
);

CREATE TABLE IF NOT EXISTS ip_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ip_id TEXT NOT NULL,
    film_id TEXT,
    entry_type TEXT DEFAULT 'film',
    sequence_no INTEGER DEFAULT 1,
    year INTEGER,
    month INTEGER,
    result_json TEXT
);

CREATE TABLE IF NOT EXISTS controversy_cases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    target_type TEXT NOT NULL,
    target_id TEXT NOT NULL,
    case_type TEXT NOT NULL,
    severity INTEGER DEFAULT 0,
    status TEXT DEFAULT 'rumor',
    year INTEGER,
    month INTEGER,
    effects_json TEXT
);

CREATE TABLE IF NOT EXISTS reevaluation_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    film_id TEXT NOT NULL,
    year INTEGER NOT NULL,
    month INTEGER,
    trigger_type TEXT NOT NULL,
    buzz_delta INTEGER DEFAULT 0,
    reputation_delta INTEGER DEFAULT 0,
    summary TEXT,
    effects_json TEXT
);

CREATE TABLE IF NOT EXISTS news_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    year INTEGER NOT NULL,
    month INTEGER NOT NULL,
    day INTEGER DEFAULT 1,
    title TEXT NOT NULL,
    body TEXT,
    source_type TEXT,
    target_type TEXT,
    target_id TEXT,
    importance INTEGER DEFAULT 50,
    reaction_json TEXT,
    popup_seen INTEGER DEFAULT 0,
    effects_json TEXT
);

CREATE TABLE IF NOT EXISTS event_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT NOT NULL,
    category TEXT NOT NULL,
    project_id TEXT,
    choice_id TEXT,
    choice_text TEXT,
    year INTEGER,
    month INTEGER,
    effects_json TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS calendar_events (
    id TEXT PRIMARY KEY,
    year INTEGER NOT NULL,
    month INTEGER NOT NULL,
    day INTEGER NOT NULL,
    end_year INTEGER,
    end_month INTEGER,
    end_day INTEGER,
    title TEXT NOT NULL,
    event_type TEXT NOT NULL,
    project_id TEXT,
    description TEXT,
    metadata_json TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS story_flags (
    key TEXT PRIMARY KEY,
    value_json TEXT,
    updated_year INTEGER,
    updated_month INTEGER
);

CREATE TABLE IF NOT EXISTS future_generation_rules (
    id TEXT PRIMARY KEY,
    target_type TEXT NOT NULL,
    starts_year INTEGER,
    weight INTEGER DEFAULT 100,
    rule_json TEXT,
    description TEXT
);

CREATE TABLE IF NOT EXISTS generated_entities (
    id TEXT PRIMARY KEY,
    entity_type TEXT NOT NULL,
    name TEXT NOT NULL,
    generated_year INTEGER,
    generated_month INTEGER,
    source_rule_id TEXT,
    data_json TEXT
);

CREATE TABLE IF NOT EXISTS core_eras (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    start_year INTEGER NOT NULL,
    end_year INTEGER,
    description TEXT,
    theater_demand INTEGER DEFAULT 50,
    ott_power INTEGER DEFAULT 0,
    foreign_competition INTEGER DEFAULT 50,
    middle_budget_risk INTEGER DEFAULT 50,
    special_format_demand INTEGER DEFAULT 0,
    online_spread_power INTEGER DEFAULT 0,
    ticket_price_burden INTEGER DEFAULT 50,
    unlocked_systems_json TEXT,
    locked_systems_json TEXT
);

CREATE TABLE IF NOT EXISTS era_rules (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    start_year INTEGER NOT NULL,
    end_year INTEGER,
    summary TEXT,
    market_rules_json TEXT,
    production_rules_json TEXT,
    distribution_rules_json TEXT,
    marketing_rules_json TEXT,
    secondary_market_rules_json TEXT,
    locked_systems_json TEXT,
    unlocked_systems_json TEXT,
    locked_choices_json TEXT,
    strong_choices_json TEXT,
    inefficient_choices_json TEXT,
    genre_modifiers_json TEXT,
    risk_modifiers_json TEXT,
    game_over_risks_json TEXT,
    future_rules_json TEXT
);

CREATE TABLE IF NOT EXISTS core_era_rules (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    start_year INTEGER NOT NULL,
    end_year INTEGER,
    summary TEXT,
    market_rules_json TEXT,
    production_rules_json TEXT,
    distribution_rules_json TEXT,
    marketing_rules_json TEXT,
    secondary_market_rules_json TEXT,
    locked_systems_json TEXT,
    unlocked_systems_json TEXT,
    locked_choices_json TEXT,
    strong_choices_json TEXT,
    inefficient_choices_json TEXT,
    genre_modifiers_json TEXT,
    risk_modifiers_json TEXT,
    game_over_risks_json TEXT,
    future_rules_json TEXT
);

CREATE TABLE IF NOT EXISTS core_genres (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    era_fit_json TEXT,
    scenario_weight INTEGER DEFAULT 10,
    directing_weight INTEGER DEFAULT 10,
    actors_weight INTEGER DEFAULT 10,
    shooting_weight INTEGER DEFAULT 10,
    art_weight INTEGER DEFAULT 10,
    stunt_weight INTEGER DEFAULT 0,
    vfx_weight INTEGER DEFAULT 0,
    sound_weight INTEGER DEFAULT 10,
    editing_weight INTEGER DEFAULT 10,
    contingency_weight INTEGER DEFAULT 5,
    boxoffice_weight REAL DEFAULT 1.0,
    critic_weight REAL DEFAULT 1.0,
    audience_weight REAL DEFAULT 1.0,
    success_factors_json TEXT,
    risk_factors_json TEXT,
    major_risks_json TEXT,
    critic_weights_json TEXT,
    audience_weights_json TEXT,
    franchise_fit INTEGER DEFAULT 50,
    secondary_market_fit INTEGER DEFAULT 50,
    plagiarism_sensitivity INTEGER DEFAULT 50,
    award_compatibility INTEGER DEFAULT 50
);

CREATE TABLE IF NOT EXISTS core_project_scales (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    min_budget INTEGER NOT NULL,
    max_budget INTEGER NOT NULL,
    min_events INTEGER DEFAULT 1,
    max_events INTEGER DEFAULT 3,
    failure_impact TEXT DEFAULT 'normal',
    required_stages_json TEXT,
    stage_flow_json TEXT,
    optional_stages_json TEXT,
    required_reputation INTEGER DEFAULT 0,
    required_network INTEGER DEFAULT 0,
    game_over_risk_multiplier REAL DEFAULT 1.0
);

CREATE TABLE IF NOT EXISTS core_stats (
    id TEXT PRIMARY KEY,
    name_ko TEXT NOT NULL,
    category TEXT NOT NULL,
    min_value INTEGER DEFAULT 0,
    max_value INTEGER DEFAULT 100,
    hidden INTEGER DEFAULT 1,
    description TEXT
);

CREATE TABLE IF NOT EXISTS core_production_stages (
    id TEXT PRIMARY KEY,
    sequence INTEGER NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    stage_group TEXT DEFAULT 'production',
    required_for_scales_json TEXT
);

CREATE TABLE IF NOT EXISTS people_actor_profiles (
    person_id TEXT PRIMARY KEY,
    current_stats_json TEXT,
    potential_stats_json TEXT,
    genre_fit_json TEXT,
    historical_filmography_locked INTEGER DEFAULT 0,
    stat_profile_json TEXT,
    public_profile_json TEXT
);

CREATE TABLE IF NOT EXISTS people_director_profiles (
    person_id TEXT PRIMARY KEY,
    current_stats_json TEXT,
    potential_stats_json TEXT,
    genre_fit_json TEXT,
    stat_profile_json TEXT,
    public_profile_json TEXT
);

CREATE TABLE IF NOT EXISTS people_critic_profiles (
    id TEXT PRIMARY KEY,
    name_ko TEXT NOT NULL,
    type TEXT DEFAULT 'critic',
    available_from INTEGER,
    critic_type_json TEXT,
    taste_profile_json TEXT,
    influence_json TEXT,
    scoring_style_json TEXT,
    public_description TEXT
);

CREATE TABLE IF NOT EXISTS people_relationships (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    target_id TEXT NOT NULL,
    target_type TEXT NOT NULL,
    trust INTEGER DEFAULT 0,
    awareness INTEGER DEFAULT 0,
    last_contact_year INTEGER
);

CREATE TABLE IF NOT EXISTS people_career_timeline (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    person_id TEXT NOT NULL,
    project_id TEXT,
    role TEXT,
    year INTEGER,
    month INTEGER,
    status TEXT DEFAULT 'attached',
    result_json TEXT
);

CREATE TABLE IF NOT EXISTS people_protected_schedules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    person_id TEXT NOT NULL,
    start_year INTEGER NOT NULL,
    start_month INTEGER,
    end_year INTEGER,
    end_month INTEGER,
    reason TEXT,
    metadata_json TEXT
);

CREATE TABLE IF NOT EXISTS movies (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    movie_type TEXT NOT NULL,
    genre_id TEXT,
    scale_id TEXT,
    status TEXT DEFAULT 'known',
    metadata_json TEXT
);

CREATE TABLE IF NOT EXISTS movies_historical (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    origin TEXT DEFAULT 'domestic',
    release_year INTEGER NOT NULL,
    release_month INTEGER,
    genre_id TEXT,
    scale_id TEXT,
    expected_audience INTEGER DEFAULT 0,
    actual_audience INTEGER,
    effects_json TEXT
);

CREATE TABLE IF NOT EXISTS movies_player_created (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    genre_id TEXT,
    scale_id TEXT,
    release_year INTEGER,
    release_month INTEGER,
    production_budget INTEGER,
    marketing_budget INTEGER,
    total_cost INTEGER,
    final_audience INTEGER,
    gross_revenue INTEGER,
    break_even_audience INTEGER,
    critic_score INTEGER,
    audience_score INTEGER,
    content_rating TEXT,
    rating_reason_json TEXT,
    result_summary TEXT
);

CREATE TABLE IF NOT EXISTS movies_boxoffice (
    movie_id TEXT PRIMARY KEY,
    final_audience INTEGER DEFAULT 0,
    gross_revenue INTEGER DEFAULT 0,
    studio_revenue INTEGER DEFAULT 0,
    secondary_market_revenue INTEGER DEFAULT 0,
    break_even_audience INTEGER DEFAULT 0,
    profit INTEGER DEFAULT 0,
    metrics_json TEXT
);

CREATE TABLE IF NOT EXISTS movies_reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    movie_id TEXT NOT NULL,
    critic_id TEXT,
    source_type TEXT DEFAULT 'critic',
    score INTEGER,
    quote TEXT,
    effects_json TEXT
);

CREATE TABLE IF NOT EXISTS movies_awards (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    award_id TEXT NOT NULL,
    movie_id TEXT,
    year INTEGER NOT NULL,
    category TEXT NOT NULL,
    result TEXT NOT NULL,
    effects_json TEXT
);

CREATE TABLE IF NOT EXISTS movies_post_release_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    movie_id TEXT NOT NULL,
    metric_type TEXT NOT NULL,
    year INTEGER,
    month INTEGER,
    value INTEGER DEFAULT 0,
    summary TEXT,
    effects_json TEXT
);

CREATE TABLE IF NOT EXISTS player_filmography_records (
    film_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    release_year INTEGER,
    release_month INTEGER,
    genre_id TEXT,
    scale_id TEXT,
    audience INTEGER DEFAULT 0,
    gross_revenue INTEGER DEFAULT 0,
    profit INTEGER DEFAULT 0,
    break_even_audience INTEGER DEFAULT 0,
    audience_score INTEGER DEFAULT 0,
    critic_score INTEGER DEFAULT 0,
    awards_json TEXT,
    reviews_json TEXT,
    collaborations_json TEXT,
    failure_record_json TEXT,
    reevaluation_json TEXT,
    franchise_json TEXT,
    summary_json TEXT,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS history_domestic_events (
    id TEXT PRIMARY KEY,
    year INTEGER NOT NULL,
    month INTEGER,
    title TEXT NOT NULL,
    type TEXT DEFAULT 'domestic_market',
    fixed_level TEXT DEFAULT 'semiFixed',
    description TEXT,
    effects_json TEXT,
    unlocks_json TEXT
);

CREATE TABLE IF NOT EXISTS history_policy_events (
    id TEXT PRIMARY KEY,
    year INTEGER NOT NULL,
    month INTEGER,
    title TEXT NOT NULL,
    type TEXT DEFAULT 'policy',
    fixed_level TEXT DEFAULT 'semiFixed',
    description TEXT,
    effects_json TEXT,
    unlocks_json TEXT
);

CREATE TABLE IF NOT EXISTS history_market_events (
    id TEXT PRIMARY KEY,
    year INTEGER NOT NULL,
    month INTEGER,
    title TEXT NOT NULL,
    type TEXT DEFAULT 'market',
    fixed_level TEXT DEFAULT 'semiFixed',
    description TEXT,
    effects_json TEXT,
    unlocks_json TEXT
);

CREATE TABLE IF NOT EXISTS history_distribution_events (
    id TEXT PRIMARY KEY,
    year INTEGER NOT NULL,
    month INTEGER,
    title TEXT NOT NULL,
    type TEXT DEFAULT 'distribution',
    fixed_level TEXT DEFAULT 'semiFixed',
    company TEXT,
    chain TEXT,
    location TEXT,
    format_json TEXT,
    related_companies_json TEXT,
    description TEXT,
    effects_json TEXT,
    unlocks_json TEXT
);

CREATE TABLE IF NOT EXISTS history_theater_events (
    id TEXT PRIMARY KEY,
    year INTEGER NOT NULL,
    month INTEGER,
    title TEXT NOT NULL,
    type TEXT DEFAULT 'theater',
    fixed_level TEXT DEFAULT 'semiFixed',
    company TEXT,
    chain TEXT,
    location TEXT,
    format_json TEXT,
    related_companies_json TEXT,
    description TEXT,
    effects_json TEXT,
    unlocks_json TEXT
);

CREATE TABLE IF NOT EXISTS history_premium_format_events (
    id TEXT PRIMARY KEY,
    year INTEGER NOT NULL,
    month INTEGER,
    title TEXT NOT NULL,
    type TEXT DEFAULT 'premium_format',
    fixed_level TEXT DEFAULT 'semiFixed',
    company TEXT,
    chain TEXT,
    location TEXT,
    format_json TEXT,
    related_companies_json TEXT,
    description TEXT,
    effects_json TEXT,
    unlocks_json TEXT
);

CREATE TABLE IF NOT EXISTS history_foreign_events (
    id TEXT PRIMARY KEY,
    year INTEGER NOT NULL,
    month INTEGER,
    title TEXT NOT NULL,
    title_ko TEXT,
    title_en TEXT,
    impact_grade TEXT,
    fixed_level TEXT DEFAULT 'semiFixed',
    genre_json TEXT,
    description TEXT,
    effects_json TEXT,
    same_window_penalties_json TEXT
);

CREATE TABLE IF NOT EXISTS history_ticket_prices (
    year INTEGER PRIMARY KEY,
    average_ticket_price INTEGER NOT NULL,
    perceived_ticket_price INTEGER,
    premium_format_multiplier REAL DEFAULT 1.0,
    audience_price_sensitivity INTEGER DEFAULT 50,
    source_type TEXT DEFAULT 'historical'
);

CREATE TABLE IF NOT EXISTS history_protected_director_films (
    id TEXT PRIMARY KEY,
    director_id TEXT,
    title TEXT NOT NULL,
    release_year INTEGER,
    release_month INTEGER,
    protection_level TEXT DEFAULT 'fixed',
    metadata_json TEXT
);

CREATE TABLE IF NOT EXISTS history_award_events (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    country TEXT DEFAULT 'KR',
    founded_year INTEGER,
    prestige INTEGER DEFAULT 50,
    categories_json TEXT,
    public_profile_json TEXT
);

CREATE TABLE IF NOT EXISTS history_award_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    award_id TEXT NOT NULL,
    movie_id TEXT,
    year INTEGER NOT NULL,
    month INTEGER,
    category TEXT NOT NULL,
    result TEXT NOT NULL,
    fixed_level TEXT DEFAULT 'historical',
    winner_name TEXT,
    work_title TEXT,
    person_name TEXT,
    source_note TEXT,
    effects_json TEXT
);

CREATE TABLE IF NOT EXISTS industry_yearly_reports (
    year INTEGER PRIMARY KEY,
    top_boxoffice_json TEXT,
    korean_share_json TEXT,
    foreign_hits_json TEXT,
    actors_of_year_json TEXT,
    directors_of_year_json TEXT,
    award_highlights_json TEXT,
    production_company_rankings_json TEXT,
    distributor_share_json TEXT,
    genre_trends_json TEXT,
    source_summary_json TEXT,
    generated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS market_yearly_stats (
    year INTEGER PRIMARY KEY,
    total_audience INTEGER,
    korean_film_audience INTEGER,
    foreign_film_audience INTEGER,
    total_revenue INTEGER,
    non_theatrical_market_size INTEGER,
    theater_count INTEGER,
    screen_count INTEGER,
    avg_production_cost INTEGER,
    avg_total_cost INTEGER,
    estimated_profit_rate REAL,
    export_amount REAL,
    source_file TEXT
);

CREATE TABLE IF NOT EXISTS economic_yearly_indicators (
    year INTEGER PRIMARY KEY,
    cpi REAL,
    cpi_base_year INTEGER DEFAULT 2020,
    cpi_base REAL,
    production_cost_modifier REAL DEFAULT 1.0,
    currency_real_value_multiplier REAL DEFAULT 1.0,
    audience_affordability_modifier REAL DEFAULT 1.0,
    ticket_price_burden_modifier INTEGER DEFAULT 0,
    theater_demand_modifier INTEGER DEFAULT 0,
    future_economy_modifier INTEGER DEFAULT 0,
    source TEXT DEFAULT 'fallback',
    source_detail TEXT,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS production_projects (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    genre_id TEXT NOT NULL,
    scale_id TEXT NOT NULL,
    status TEXT NOT NULL,
    production_budget INTEGER DEFAULT 0,
    marketing_budget INTEGER DEFAULT 0,
    stage TEXT DEFAULT 'planning',
    stats_json TEXT,
    created_year INTEGER,
    release_year INTEGER,
    release_month INTEGER,
    content_rating TEXT,
    rating_reason_json TEXT
);

CREATE TABLE IF NOT EXISTS production_budget_allocations (
    project_id TEXT NOT NULL,
    category TEXT NOT NULL,
    percentage INTEGER DEFAULT 0,
    amount INTEGER DEFAULT 0,
    notes TEXT,
    PRIMARY KEY (project_id, category)
);

CREATE TABLE IF NOT EXISTS production_choices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT NOT NULL,
    choice_id TEXT NOT NULL,
    choice_text TEXT NOT NULL,
    effects_json TEXT,
    UNIQUE (event_id, choice_id)
);

CREATE TABLE IF NOT EXISTS production_dialogue_events (
    id TEXT PRIMARY KEY,
    stage TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    npc_type TEXT,
    npc_traits_json TEXT,
    npc_line TEXT,
    trigger_json TEXT,
    choices_json TEXT
);

CREATE TABLE IF NOT EXISTS production_random_events (
    id TEXT PRIMARY KEY,
    category TEXT NOT NULL,
    stage TEXT,
    scope TEXT DEFAULT 'project',
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    fixed_level TEXT DEFAULT 'dynamic',
    weight INTEGER DEFAULT 100,
    cooldown_months INTEGER DEFAULT 0,
    npc_type TEXT,
    npc_traits_json TEXT,
    npc_line TEXT,
    trigger_json TEXT,
    choices_json TEXT
);

CREATE TABLE IF NOT EXISTS production_stage_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT NOT NULL,
    category TEXT NOT NULL,
    project_id TEXT,
    choice_id TEXT,
    choice_text TEXT,
    year INTEGER,
    month INTEGER,
    effects_json TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS systems_reputation (
    id TEXT PRIMARY KEY,
    name_ko TEXT NOT NULL,
    description TEXT,
    low_text TEXT,
    mid_text TEXT,
    high_text TEXT
);

CREATE TABLE IF NOT EXISTS systems_network (
    id TEXT PRIMARY KEY,
    name_ko TEXT NOT NULL,
    target_type TEXT DEFAULT 'industry',
    description TEXT,
    low_text TEXT,
    mid_text TEXT,
    high_text TEXT
);

CREATE TABLE IF NOT EXISTS systems_press (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    year INTEGER NOT NULL,
    month INTEGER NOT NULL,
    title TEXT NOT NULL,
    body TEXT,
    source_type TEXT,
    target_type TEXT,
    target_id TEXT,
    effects_json TEXT
);

CREATE TABLE IF NOT EXISTS systems_critics (
    id TEXT PRIMARY KEY,
    name_ko TEXT NOT NULL,
    type TEXT DEFAULT 'critic',
    available_from INTEGER,
    critic_type_json TEXT,
    taste_profile_json TEXT,
    influence_json TEXT,
    scoring_style_json TEXT,
    public_description TEXT
);

CREATE TABLE IF NOT EXISTS systems_plagiarism (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    target_type TEXT NOT NULL,
    target_id TEXT NOT NULL,
    case_type TEXT NOT NULL,
    severity INTEGER DEFAULT 0,
    status TEXT DEFAULT 'rumor',
    year INTEGER,
    month INTEGER,
    effects_json TEXT
);

CREATE TABLE IF NOT EXISTS systems_franchise (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    origin_movie_id TEXT,
    owner_type TEXT DEFAULT 'studio',
    owner_id TEXT,
    ip_type TEXT DEFAULT 'original',
    ip_value INTEGER DEFAULT 0,
    franchise_power INTEGER DEFAULT 0,
    sequel_demand INTEGER DEFAULT 0,
    cult_potential INTEGER DEFAULT 0,
    reevaluation_potential INTEGER DEFAULT 0,
    status TEXT DEFAULT 'active',
    metadata_json TEXT
);

CREATE TABLE IF NOT EXISTS systems_post_release (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    movie_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    year INTEGER,
    month INTEGER,
    summary TEXT,
    effects_json TEXT
);

CREATE TABLE IF NOT EXISTS systems_future_generation (
    id TEXT PRIMARY KEY,
    target_type TEXT NOT NULL,
    starts_year INTEGER,
    weight INTEGER DEFAULT 100,
    rule_json TEXT,
    description TEXT
);

CREATE TABLE IF NOT EXISTS save_player_state (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    name TEXT NOT NULL,
    gender TEXT,
    age INTEGER,
    current_year INTEGER NOT NULL,
    current_month INTEGER NOT NULL,
    current_day INTEGER NOT NULL DEFAULT 1,
    position TEXT NOT NULL,
    cash INTEGER DEFAULT 0,
    debt INTEGER DEFAULT 0,
    stats_json TEXT,
    reputation_json TEXT,
    network_json TEXT
);

CREATE TABLE IF NOT EXISTS save_studio_state (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    studio_name TEXT,
    fame INTEGER DEFAULT 0,
    cash INTEGER DEFAULT 0,
    debt INTEGER DEFAULT 0,
    own_capital INTEGER DEFAULT 0,
    investment_capital INTEGER DEFAULT 0,
    loan_capital INTEGER DEFAULT 0,
    loan_balance INTEGER DEFAULT 0,
    credit_limit INTEGER DEFAULT 0,
    field_reputation INTEGER DEFAULT 50,
    pay_reputation INTEGER DEFAULT 50,
    creative_freedom INTEGER DEFAULT 50,
    interference_reputation INTEGER DEFAULT 50,
    reputation_tags_json TEXT,
    reputation_summary TEXT
);

CREATE TABLE IF NOT EXISTS save_market_state (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    year INTEGER NOT NULL,
    month INTEGER NOT NULL,
    theater_demand INTEGER DEFAULT 50,
    ott_power INTEGER DEFAULT 0,
    foreign_competition INTEGER DEFAULT 50,
    korean_film_trust INTEGER DEFAULT 50,
    genre_trends_json TEXT,
    modifiers_json TEXT,
    UNIQUE (year, month)
);

CREATE TABLE IF NOT EXISTS save_event_flags (
    key TEXT PRIMARY KEY,
    value_json TEXT,
    updated_year INTEGER,
    updated_month INTEGER
);

CREATE TABLE IF NOT EXISTS save_generated_people (
    id TEXT PRIMARY KEY,
    person_type TEXT NOT NULL,
    name TEXT NOT NULL,
    generated_year INTEGER,
    generated_month INTEGER,
    source_rule_id TEXT,
    data_json TEXT
);

CREATE TABLE IF NOT EXISTS save_generated_films (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    generated_year INTEGER,
    generated_month INTEGER,
    source_rule_id TEXT,
    data_json TEXT
);

CREATE TABLE IF NOT EXISTS collection_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    job_type TEXT NOT NULL,
    status TEXT DEFAULT 'running',
    started_at TEXT DEFAULT CURRENT_TIMESTAMP,
    finished_at TEXT,
    params_json TEXT,
    message TEXT,
    rows_collected INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS collection_api_responses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER,
    source TEXT NOT NULL,
    endpoint TEXT NOT NULL,
    request_url TEXT,
    status_code INTEGER,
    collected_at TEXT DEFAULT CURRENT_TIMESTAMP,
    response_json TEXT,
    error_text TEXT
);

CREATE TABLE IF NOT EXISTS staging_kmdb_movies (
    kmdb_id TEXT PRIMARY KEY,
    title_ko TEXT,
    normalized_title TEXT,
    title_en TEXT,
    prod_year INTEGER,
    match_year INTEGER,
    release_date TEXT,
    nation TEXT,
    director_names_json TEXT,
    actor_names_json TEXT,
    production_company TEXT,
    distribution_company TEXT,
    genre TEXT,
    runtime INTEGER,
    rating TEXT,
    plot TEXT,
    keywords_json TEXT,
    awards_json TEXT,
    raw_json TEXT,
    source_url TEXT,
    collected_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS staging_kobis_daily_boxoffice (
    target_date TEXT NOT NULL,
    movie_code TEXT NOT NULL,
    movie_name TEXT NOT NULL,
    open_date TEXT,
    rank INTEGER,
    rank_change INTEGER,
    rank_old_and_new TEXT,
    sales_amount INTEGER DEFAULT 0,
    sales_accumulated INTEGER DEFAULT 0,
    audience_count INTEGER DEFAULT 0,
    audience_accumulated INTEGER DEFAULT 0,
    screen_count INTEGER DEFAULT 0,
    show_count INTEGER DEFAULT 0,
    raw_json TEXT,
    collected_at TEXT DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (target_date, movie_code)
);

CREATE TABLE IF NOT EXISTS staging_kobis_movie_list (
    movie_code TEXT PRIMARY KEY,
    movie_name_ko TEXT,
    normalized_title TEXT,
    movie_name_en TEXT,
    production_year INTEGER,
    open_date TEXT,
    type_name TEXT,
    production_status TEXT,
    nation_alt TEXT,
    genre_alt TEXT,
    representative_nation TEXT,
    representative_genre TEXT,
    directors_json TEXT,
    companies_json TEXT,
    raw_json TEXT,
    collected_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS staging_kobis_movie_details (
    movie_code TEXT PRIMARY KEY,
    movie_name_ko TEXT,
    normalized_title TEXT,
    movie_name_en TEXT,
    original_title TEXT,
    show_time INTEGER,
    production_year INTEGER,
    open_date TEXT,
    production_status TEXT,
    type_name TEXT,
    nations_json TEXT,
    genres_json TEXT,
    directors_json TEXT,
    actors_json TEXT,
    companies_json TEXT,
    audits_json TEXT,
    staffs_json TEXT,
    raw_json TEXT,
    collected_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS staging_kobis_yearly_boxoffice (
    year INTEGER NOT NULL,
    movie_code TEXT NOT NULL,
    movie_name TEXT NOT NULL,
    normalized_title TEXT,
    open_date TEXT,
    sales_amount INTEGER DEFAULT 0,
    audience_count INTEGER DEFAULT 0,
    screen_count INTEGER DEFAULT 0,
    show_count INTEGER DEFAULT 0,
    days_count INTEGER DEFAULT 0,
    first_seen_date TEXT,
    last_seen_date TEXT,
    raw_json TEXT,
    collected_at TEXT DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (year, movie_code)
);

CREATE TABLE IF NOT EXISTS staging_major_korean_movies (
    id TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    source_movie_code TEXT,
    title TEXT NOT NULL,
    normalized_title TEXT,
    representative_year INTEGER,
    first_seen_year INTEGER,
    last_seen_year INTEGER,
    release_date TEXT,
    country TEXT,
    distributor TEXT,
    max_annual_rank INTEGER,
    max_annual_audience INTEGER DEFAULT 0,
    max_annual_gross_text TEXT,
    max_annual_screens INTEGER DEFAULT 0,
    source_url TEXT,
    raw_json TEXT,
    collected_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS staging_kobis_yearly_totals (
    year INTEGER PRIMARY KEY,
    total_sales INTEGER NOT NULL,
    total_audience INTEGER NOT NULL,
    average_ticket_price INTEGER NOT NULL,
    source_type TEXT DEFAULT 'kobis_derived',
    raw_json TEXT,
    collected_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS staging_kosis_statistics (
    id TEXT PRIMARY KEY,
    target_id TEXT,
    org_id TEXT,
    tbl_id TEXT,
    tbl_nm TEXT,
    stat_id TEXT,
    stat_nm TEXT,
    item_id TEXT,
    item_name TEXT,
    unit_name TEXT,
    prd_se TEXT,
    prd_de TEXT,
    value_text TEXT,
    value_numeric REAL,
    c1_id TEXT,
    c1_name TEXT,
    c2_id TEXT,
    c2_name TEXT,
    c3_id TEXT,
    c3_name TEXT,
    c4_id TEXT,
    c4_name TEXT,
    c5_id TEXT,
    c5_name TEXT,
    c6_id TEXT,
    c6_name TEXT,
    c7_id TEXT,
    c7_name TEXT,
    c8_id TEXT,
    c8_name TEXT,
    raw_json TEXT,
    source_url TEXT,
    collected_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS staging_kosis_indicator_series (
    id TEXT PRIMARY KEY,
    indicator_id TEXT NOT NULL,
    indicator_name TEXT,
    category TEXT,
    year INTEGER,
    month INTEGER,
    period TEXT NOT NULL,
    region_code TEXT,
    region_name TEXT,
    item_id TEXT,
    item_name TEXT,
    value REAL,
    unit_name TEXT,
    source_org_id TEXT,
    source_tbl_id TEXT,
    source_tbl_name TEXT,
    raw_json TEXT,
    collected_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS staging_kosis_search_results (
    id TEXT PRIMARY KEY,
    search_name TEXT NOT NULL,
    org_id TEXT,
    org_name TEXT,
    tbl_id TEXT,
    tbl_name TEXT,
    stat_id TEXT,
    stat_name TEXT,
    period_start TEXT,
    period_end TEXT,
    table_path TEXT,
    contents TEXT,
    raw_json TEXT,
    collected_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS staging_wikidata_sparql_results (
    id TEXT PRIMARY KEY,
    target_id TEXT NOT NULL,
    entity_type TEXT,
    qid TEXT,
    label_ko TEXT,
    label_en TEXT,
    description_ko TEXT,
    description_en TEXT,
    date_value TEXT,
    year INTEGER,
    release_date TEXT,
    birth_date TEXT,
    death_date TEXT,
    imdb_id TEXT,
    wikipedia_url TEXT,
    director_json TEXT,
    actor_json TEXT,
    genre_json TEXT,
    country_json TEXT,
    awards_json TEXT,
    work_relationships_json TEXT,
    occupation_json TEXT,
    external_ids_json TEXT,
    linked_entities_json TEXT,
    raw_json TEXT,
    source_url TEXT,
    collected_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS wikidata_movies (
    qid TEXT PRIMARY KEY,
    title_ko TEXT,
    title_en TEXT,
    normalized_title_ko TEXT,
    normalized_title_en TEXT,
    release_date TEXT,
    year INTEGER,
    director_json TEXT,
    actor_json TEXT,
    genre_json TEXT,
    country_json TEXT,
    awards_json TEXT,
    imdb_id TEXT,
    wikipedia_url TEXT,
    match_status TEXT DEFAULT 'unmatched',
    source_priority TEXT DEFAULT 'supplemental_wikidata',
    raw_json TEXT,
    source_url TEXT,
    collected_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS wikidata_people (
    qid TEXT PRIMARY KEY,
    name_ko TEXT,
    name_en TEXT,
    normalized_name_ko TEXT,
    normalized_name_en TEXT,
    birth_date TEXT,
    birth_year INTEGER,
    death_date TEXT,
    death_year INTEGER,
    occupation_json TEXT,
    work_relationships_json TEXT,
    imdb_id TEXT,
    wikipedia_url TEXT,
    match_status TEXT DEFAULT 'unmatched',
    source_priority TEXT DEFAULT 'supplemental_wikidata',
    raw_json TEXT,
    source_url TEXT,
    collected_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS staging_kofic_actors200 (
    id TEXT PRIMARY KEY,
    name_ko TEXT NOT NULL,
    name_en TEXT,
    representative_works_json TEXT,
    introduction TEXT,
    global_tags_json TEXT,
    source_url TEXT,
    raw_json TEXT,
    collected_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS staging_kofic_report_files (
    id TEXT PRIMARY KEY,
    report_year INTEGER,
    title TEXT,
    file_path TEXT NOT NULL,
    file_name TEXT NOT NULL,
    file_type TEXT,
    file_size INTEGER,
    sha1 TEXT,
    page_count INTEGER,
    sheet_count INTEGER,
    extract_status TEXT,
    extracted_text_path TEXT,
    notes TEXT,
    raw_json TEXT,
    collected_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS staging_kofic_industry_metrics (
    id TEXT PRIMARY KEY,
    report_year INTEGER NOT NULL,
    metric_id TEXT NOT NULL,
    metric_name TEXT,
    metric_category TEXT,
    value REAL,
    unit TEXT,
    scope TEXT,
    confidence REAL DEFAULT 0.5,
    source_file_id TEXT,
    source_page INTEGER,
    source_text TEXT,
    raw_json TEXT,
    collected_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS staging_kofic_report_events (
    id TEXT PRIMARY KEY,
    report_year INTEGER NOT NULL,
    month INTEGER,
    event_type TEXT,
    title TEXT NOT NULL,
    fixed_level TEXT DEFAULT 'semiFixed',
    description TEXT,
    effects_json TEXT,
    confidence REAL DEFAULT 0.5,
    source_file_id TEXT,
    source_text TEXT,
    raw_json TEXT,
    collected_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS staging_award_records (
    id TEXT PRIMARY KEY,
    award_name TEXT NOT NULL,
    event_year INTEGER,
    ceremony_no TEXT,
    category TEXT,
    result_type TEXT,
    movie_title TEXT,
    person_name TEXT,
    notes TEXT,
    source_url TEXT,
    raw_json TEXT,
    collected_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS staging_critic_profiles (
    id TEXT PRIMARY KEY,
    name_ko TEXT NOT NULL,
    affiliation TEXT,
    public_tags_json TEXT,
    notes TEXT,
    source_url TEXT,
    raw_json TEXT,
    collected_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS staging_history_events (
    id TEXT PRIMARY KEY,
    year INTEGER NOT NULL,
    month INTEGER,
    title TEXT NOT NULL,
    event_type TEXT,
    description TEXT,
    effects_notes TEXT,
    source_url TEXT,
    raw_json TEXT,
    collected_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""

STATIC_TABLES = (
    "content_ratings",
    "systems_future_generation",
    "systems_critics",
    "systems_network",
    "systems_reputation",
    "production_choices",
    "production_random_events",
    "production_dialogue_events",
    "history_award_results",
    "history_award_events",
    "history_protected_director_films",
    "history_ticket_prices",
    "history_foreign_events",
    "history_premium_format_events",
    "history_theater_events",
    "history_distribution_events",
    "history_market_events",
    "history_policy_events",
    "history_domestic_events",
    "people_critic_profiles",
    "people_director_profiles",
    "people_actor_profiles",
    "people_protected_schedules",
    "core_production_stages",
    "core_stats",
    "core_project_scales",
    "core_genres",
    "core_era_rules",
    "core_eras",
    "future_generation_rules",
    "awards",
    "character_option_sets",
    "starting_positions",
    "network_definitions",
    "reputation_definitions",
    "stat_definitions",
    "system_definitions",
    "simulation_events",
    "project_stage_definitions",
    "production_events",
    "era_rules",
    "ticket_prices",
    "historical_events",
    "organizations",
    "critics",
    "people",
    "project_scales",
    "genres",
    "eras",
)

PROJECT_STAGE_SEED = (
    {
        "id": "development",
        "sequence": 10,
        "name": "기획 개발",
        "description": "아이템, 원작/IP, 시나리오, 패키징 방향을 잡는 단계.",
        "stage_group": "production",
    },
    {
        "id": "fundraising",
        "sequence": 20,
        "name": "투자 유치",
        "description": "투자사, 제작사, 배급사와 제작비 및 권리 구조를 협상하는 단계.",
        "stage_group": "production",
    },
    {
        "id": "casting",
        "sequence": 30,
        "name": "캐스팅",
        "description": "감독, 배우, 주요 스태프를 붙이고 대중성과 적합도의 균형을 맞추는 단계.",
        "stage_group": "production",
    },
    {
        "id": "pre_production",
        "sequence": 40,
        "name": "프리프로덕션",
        "description": "콘티, 로케이션, 미술, 촬영 계획, 제작 일정을 확정하는 단계.",
        "stage_group": "production",
    },
    {
        "id": "shooting",
        "sequence": 50,
        "name": "제작/촬영",
        "description": "촬영 현장에서 품질, 일정, 예산, 관계 리스크를 관리하는 단계.",
        "stage_group": "production",
    },
    {
        "id": "post_production",
        "sequence": 60,
        "name": "후반작업",
        "description": "편집, 음악, 사운드, VFX, 색보정으로 최종 완성도를 끌어올리는 단계.",
        "stage_group": "production",
    },
    {
        "id": "marketing",
        "sequence": 70,
        "name": "마케팅",
        "description": "예고편, 언론 시사, 인터뷰, 온라인 반응을 관리하는 단계.",
        "stage_group": "release",
    },
    {
        "id": "release_ready",
        "sequence": 80,
        "name": "개봉 준비",
        "description": "배급 조건과 개봉 시점을 확정하고 흥행 결과를 계산할 수 있는 단계.",
        "stage_group": "release",
    },
)
RUNTIME_TABLES = (
    "save_generated_films",
    "save_generated_people",
    "save_event_flags",
    "save_market_state",
    "save_studio_state",
    "save_player_state",
    "systems_post_release",
    "systems_franchise",
    "systems_plagiarism",
    "systems_press",
    "production_stage_logs",
    "production_budget_allocations",
    "production_projects",
    "project_scenario_development",
    "project_versions",
    "reshoot_orders",
    "test_screenings",
    "stage_greeting_schedules",
    "marketing_reactions",
    "marketing_assets",
    "project_cashflows",
    "shooting_schedule_blocks",
    "project_location_plans",
    "project_crew_roles",
    "movies_post_release_metrics",
    "movies_awards",
    "movies_reviews",
    "movies_boxoffice",
    "theatrical_daily_results",
    "theatrical_runs",
    "crew_work_history",
    "finance_transactions",
    "investment_contracts",
    "project_financing",
    "loans",
    "player_filmography_records",
    "movies_player_created",
    "movies_historical",
    "movies",
    "people_career_timeline",
    "people_relationships",
    "generated_entities",
    "story_flags",
    "calendar_events",
    "event_history",
    "news_items",
    "reevaluation_events",
    "controversy_cases",
    "ip_entries",
    "intellectual_properties",
    "award_results",
    "film_reviews",
    "market_releases",
    "market_state",
    "project_distribution",
    "casting_offers",
    "project_people",
    "project_budget_allocations",
    "relationships",
    "completed_films",
    "projects",
    "studio_state",
    "player_state",
)

def initialize_database(path: Path | str | None = None, reset: bool = False) -> None:
    db_path = _resolve_database_path(path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if reset and db_path.exists():
        db_path.unlink()
    with get_connection(db_path) as conn:
        conn.executescript(SCHEMA_SQL)
        _ensure_schema_columns(conn)
        conn.commit()


def _ensure_schema_columns(conn: sqlite3.Connection) -> None:
    player_state_columns = {
        "current_day": "INTEGER NOT NULL DEFAULT 1",
    }
    for table in ("player_state", "save_player_state"):
        existing = {
            row["name"]
            for row in conn.execute(f"PRAGMA table_info({table})").fetchall()
        }
        for column, ddl in player_state_columns.items():
            if column not in existing:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")

    studio_state_columns = {
        "own_capital": "INTEGER DEFAULT 0",
        "investment_capital": "INTEGER DEFAULT 0",
        "loan_capital": "INTEGER DEFAULT 0",
        "loan_balance": "INTEGER DEFAULT 0",
        "credit_limit": "INTEGER DEFAULT 0",
        "field_reputation": "INTEGER DEFAULT 50",
        "pay_reputation": "INTEGER DEFAULT 50",
        "creative_freedom": "INTEGER DEFAULT 50",
        "interference_reputation": "INTEGER DEFAULT 50",
        "reputation_tags_json": "TEXT",
        "reputation_summary": "TEXT",
    }
    for table in ("studio_state", "save_studio_state"):
        existing = {
            row["name"]
            for row in conn.execute(f"PRAGMA table_info({table})").fetchall()
        }
        for column, ddl in studio_state_columns.items():
            if column not in existing:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")

    loan_columns = {
        "accrued_interest": "INTEGER DEFAULT 0",
        "monthly_payment_amount": "INTEGER DEFAULT 0",
        "payments_made": "INTEGER DEFAULT 0",
        "delinquent_months": "INTEGER DEFAULT 0",
        "last_interest_year": "INTEGER",
        "last_interest_month": "INTEGER",
        "next_payment_year": "INTEGER",
        "next_payment_month": "INTEGER",
    }
    existing = {
        row["name"]
        for row in conn.execute("PRAGMA table_info(loans)").fetchall()
    }
    for column, ddl in loan_columns.items():
        if column not in existing:
            conn.execute(f"ALTER TABLE loans ADD COLUMN {column} {ddl}")

    project_financing_columns = {
        "investor_equity_percent": "REAL DEFAULT 0.0",
        "recoupment_priority": "TEXT DEFAULT 'investor_first'",
        "contract_terms_json": "TEXT",
    }
    existing = {
        row["name"]
        for row in conn.execute("PRAGMA table_info(project_financing)").fetchall()
    }
    for column, ddl in project_financing_columns.items():
        if column not in existing:
            conn.execute(f"ALTER TABLE project_financing ADD COLUMN {column} {ddl}")

    project_people_columns = {
        "sequel_option": "INTEGER DEFAULT 0",
        "promotion_obligation": "INTEGER DEFAULT 0",
        "promotion_days": "INTEGER DEFAULT 0",
        "schedule_commitment_months": "INTEGER DEFAULT 0",
        "contract_options_json": "TEXT",
    }
    existing = {
        row["name"]
        for row in conn.execute("PRAGMA table_info(project_people)").fetchall()
    }
    for column, ddl in project_people_columns.items():
        if column not in existing:
            conn.execute(f"ALTER TABLE project_people ADD COLUMN {column} {ddl}")

    casting_offer_columns = {
        "commitment_months": "INTEGER DEFAULT 0",
        "sequel_option": "INTEGER DEFAULT 0",
        "promotion_obligation": "INTEGER DEFAULT 0",
        "promotion_days": "INTEGER DEFAULT 0",
        "contract_terms_json": "TEXT",
        "status": "TEXT DEFAULT 'pending'",
        "sent_day": "INTEGER",
        "response_due_day": "INTEGER",
        "responded_year": "INTEGER",
        "responded_month": "INTEGER",
        "responded_day": "INTEGER",
        "accepted": "INTEGER",
        "result_text": "TEXT",
        "notes_json": "TEXT",
        "popup_seen": "INTEGER DEFAULT 0",
    }
    existing = {
        row["name"]
        for row in conn.execute("PRAGMA table_info(casting_offers)").fetchall()
    }
    for column, ddl in casting_offer_columns.items():
        if column not in existing:
            conn.execute(f"ALTER TABLE casting_offers ADD COLUMN {column} {ddl}")

    news_item_columns = {
        "day": "INTEGER DEFAULT 1",
        "importance": "INTEGER DEFAULT 50",
        "reaction_json": "TEXT",
        "popup_seen": "INTEGER DEFAULT 0",
    }
    existing = {
        row["name"]
        for row in conn.execute("PRAGMA table_info(news_items)").fetchall()
    }
    added_popup_seen = False
    for column, ddl in news_item_columns.items():
        if column not in existing:
            conn.execute(f"ALTER TABLE news_items ADD COLUMN {column} {ddl}")
            if column == "popup_seen":
                added_popup_seen = True
    if added_popup_seen:
        conn.execute(
            """
            UPDATE news_items
            SET popup_seen = 1
            WHERE source_type IN (
                'historical', 'protected_history', 'foreign_fixed',
                'policy', 'market', 'distribution', 'theater', 'premium_format'
            )
            """
        )

    era_columns = {
        "ticket_price_burden": "INTEGER DEFAULT 50",
        "unlocked_systems_json": "TEXT",
        "locked_systems_json": "TEXT",
    }
    for table in ("eras", "core_eras"):
        existing = {
            row["name"]
            for row in conn.execute(f"PRAGMA table_info({table})").fetchall()
        }
        for column, ddl in era_columns.items():
            if column not in existing:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")

    genre_columns = {
        "era_fit_json": "TEXT",
        "boxoffice_weight": "REAL DEFAULT 1.0",
        "critic_weight": "REAL DEFAULT 1.0",
        "audience_weight": "REAL DEFAULT 1.0",
        "success_factors_json": "TEXT",
        "risk_factors_json": "TEXT",
        "major_risks_json": "TEXT",
        "critic_weights_json": "TEXT",
        "audience_weights_json": "TEXT",
        "franchise_fit": "INTEGER DEFAULT 50",
        "secondary_market_fit": "INTEGER DEFAULT 50",
        "plagiarism_sensitivity": "INTEGER DEFAULT 50",
        "award_compatibility": "INTEGER DEFAULT 50",
    }
    for table in ("genres", "core_genres"):
        existing = {
            row["name"]
            for row in conn.execute(f"PRAGMA table_info({table})").fetchall()
        }
        for column, ddl in genre_columns.items():
            if column not in existing:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")

    scale_columns = {
        "required_stages_json": "TEXT",
        "stage_flow_json": "TEXT",
        "optional_stages_json": "TEXT",
        "required_reputation": "INTEGER DEFAULT 0",
        "required_network": "INTEGER DEFAULT 0",
        "game_over_risk_multiplier": "REAL DEFAULT 1.0",
    }
    for table in ("project_scales", "core_project_scales"):
        existing = {
            row["name"]
            for row in conn.execute(f"PRAGMA table_info({table})").fetchall()
        }
        for column, ddl in scale_columns.items():
            if column not in existing:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")

    people_columns = {
        "status": "TEXT DEFAULT 'active'",
        "genre_fit_json": "TEXT",
        "historical_filmography_locked": "INTEGER DEFAULT 0",
        "stat_profile_json": "TEXT",
    }
    for table in ("people", "people_actor_profiles", "people_director_profiles"):
        existing = {
            row["name"]
            for row in conn.execute(f"PRAGMA table_info({table})").fetchall()
        }
        for column, ddl in people_columns.items():
            if column not in existing:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")

    critic_columns = {
        "type": "TEXT DEFAULT 'critic'",
        "available_from": "INTEGER",
        "scoring_style_json": "TEXT",
    }
    for table in ("critics", "people_critic_profiles", "systems_critics"):
        existing = {
            row["name"]
            for row in conn.execute(f"PRAGMA table_info({table})").fetchall()
        }
        for column, ddl in critic_columns.items():
            if column not in existing:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")

    foreign_event_columns = {
        "title_ko": "TEXT",
        "title_en": "TEXT",
        "impact_grade": "TEXT",
        "genre_json": "TEXT",
        "same_window_penalties_json": "TEXT",
    }
    existing = {
        row["name"]
        for row in conn.execute("PRAGMA table_info(history_foreign_events)").fetchall()
    }
    for column, ddl in foreign_event_columns.items():
        if column not in existing:
            conn.execute(f"ALTER TABLE history_foreign_events ADD COLUMN {column} {ddl}")

    historical_event_columns = {
        "unlocks_json": "TEXT",
    }
    existing = {
        row["name"]
        for row in conn.execute("PRAGMA table_info(historical_events)").fetchall()
    }
    for column, ddl in historical_event_columns.items():
        if column not in existing:
            conn.execute(f"ALTER TABLE historical_events ADD COLUMN {column} {ddl}")

    market_yearly_stat_columns = {
        "total_audience": "INTEGER",
        "korean_film_audience": "INTEGER",
        "foreign_film_audience": "INTEGER",
        "total_revenue": "INTEGER",
        "non_theatrical_market_size": "INTEGER",
        "theater_count": "INTEGER",
        "screen_count": "INTEGER",
        "avg_production_cost": "INTEGER",
        "avg_total_cost": "INTEGER",
        "estimated_profit_rate": "REAL",
        "export_amount": "REAL",
        "source_file": "TEXT",
    }
    existing = {
        row["name"]
        for row in conn.execute("PRAGMA table_info(market_yearly_stats)").fetchall()
    }
    for column, ddl in market_yearly_stat_columns.items():
        if column not in existing:
            conn.execute(f"ALTER TABLE market_yearly_stats ADD COLUMN {column} {ddl}")

    economic_indicator_columns = {
        "cpi": "REAL",
        "cpi_base_year": "INTEGER DEFAULT 2020",
        "cpi_base": "REAL",
        "production_cost_modifier": "REAL DEFAULT 1.0",
        "currency_real_value_multiplier": "REAL DEFAULT 1.0",
        "audience_affordability_modifier": "REAL DEFAULT 1.0",
        "ticket_price_burden_modifier": "INTEGER DEFAULT 0",
        "theater_demand_modifier": "INTEGER DEFAULT 0",
        "future_economy_modifier": "INTEGER DEFAULT 0",
        "source": "TEXT DEFAULT 'fallback'",
        "source_detail": "TEXT",
        "updated_at": "TEXT DEFAULT CURRENT_TIMESTAMP",
    }
    existing = {
        row["name"]
        for row in conn.execute("PRAGMA table_info(economic_yearly_indicators)").fetchall()
    }
    for column, ddl in economic_indicator_columns.items():
        if column not in existing:
            conn.execute(f"ALTER TABLE economic_yearly_indicators ADD COLUMN {column} {ddl}")

    history_category_event_columns = {
        "type": "TEXT DEFAULT 'domestic_market'",
        "unlocks_json": "TEXT",
    }
    for table in (
        "history_domestic_events",
        "history_policy_events",
        "history_market_events",
        "history_distribution_events",
        "history_theater_events",
        "history_premium_format_events",
    ):
        existing = {
            row["name"]
            for row in conn.execute(f"PRAGMA table_info({table})").fetchall()
        }
        for column, ddl in history_category_event_columns.items():
            if column not in existing:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")

    industry_event_columns = {
        "company": "TEXT",
        "chain": "TEXT",
        "location": "TEXT",
        "format_json": "TEXT",
        "related_companies_json": "TEXT",
    }
    for table in ("history_distribution_events", "history_theater_events", "history_premium_format_events"):
        existing = {
            row["name"]
            for row in conn.execute(f"PRAGMA table_info({table})").fetchall()
        }
        for column, ddl in industry_event_columns.items():
            if column not in existing:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")

    production_event_columns = {
        "npc_type": "TEXT",
        "npc_traits_json": "TEXT",
        "npc_line": "TEXT",
    }
    for table in ("production_events", "production_dialogue_events", "simulation_events", "production_random_events"):
        existing = {
            row["name"]
            for row in conn.execute(f"PRAGMA table_info({table})").fetchall()
        }
        for column, ddl in production_event_columns.items():
            if column not in existing:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")

    award_columns = {
        "public_profile_json": "TEXT",
    }
    for table in ("awards", "history_award_events"):
        existing = {
            row["name"]
            for row in conn.execute(f"PRAGMA table_info({table})").fetchall()
        }
        for column, ddl in award_columns.items():
            if column not in existing:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")

    history_award_result_columns = {
        "month": "INTEGER",
        "winner_name": "TEXT",
        "work_title": "TEXT",
        "person_name": "TEXT",
        "source_note": "TEXT",
    }
    existing = {
        row["name"]
        for row in conn.execute("PRAGMA table_info(history_award_results)").fetchall()
    }
    for column, ddl in history_award_result_columns.items():
        if column not in existing:
            conn.execute(f"ALTER TABLE history_award_results ADD COLUMN {column} {ddl}")

    franchise_columns = {
        "ip_value": "INTEGER DEFAULT 0",
    }
    for table in ("intellectual_properties", "systems_franchise"):
        existing = {
            row["name"]
            for row in conn.execute(f"PRAGMA table_info({table})").fetchall()
        }
        for column, ddl in franchise_columns.items():
            if column not in existing:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")

    project_rating_columns = {
        "content_rating": "TEXT",
        "rating_reason_json": "TEXT",
    }
    for table in ("projects", "production_projects", "completed_films", "movies_player_created"):
        existing = {
            row["name"]
            for row in conn.execute(f"PRAGMA table_info({table})").fetchall()
        }
        for column, ddl in project_rating_columns.items():
            if column not in existing:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")

    staging_kmdb_columns = {
        "normalized_title": "TEXT",
        "match_year": "INTEGER",
        "nation": "TEXT",
    }
    existing = {
        row["name"]
        for row in conn.execute("PRAGMA table_info(staging_kmdb_movies)").fetchall()
    }
    for column, ddl in staging_kmdb_columns.items():
        if column not in existing:
            conn.execute(f"ALTER TABLE staging_kmdb_movies ADD COLUMN {column} {ddl}")

    staging_wikidata_columns = {
        "release_date": "TEXT",
        "birth_date": "TEXT",
        "death_date": "TEXT",
        "imdb_id": "TEXT",
        "wikipedia_url": "TEXT",
        "director_json": "TEXT",
        "actor_json": "TEXT",
        "genre_json": "TEXT",
        "country_json": "TEXT",
        "awards_json": "TEXT",
        "work_relationships_json": "TEXT",
    }
    existing = {
        row["name"]
        for row in conn.execute("PRAGMA table_info(staging_wikidata_sparql_results)").fetchall()
    }
    for column, ddl in staging_wikidata_columns.items():
        if column not in existing:
            conn.execute(f"ALTER TABLE staging_wikidata_sparql_results ADD COLUMN {column} {ddl}")

    wikidata_movie_columns = {
        "normalized_title_ko": "TEXT",
        "normalized_title_en": "TEXT",
        "match_status": "TEXT DEFAULT 'unmatched'",
        "source_priority": "TEXT DEFAULT 'supplemental_wikidata'",
    }
    existing = {
        row["name"]
        for row in conn.execute("PRAGMA table_info(wikidata_movies)").fetchall()
    }
    for column, ddl in wikidata_movie_columns.items():
        if column not in existing:
            conn.execute(f"ALTER TABLE wikidata_movies ADD COLUMN {column} {ddl}")

    wikidata_people_columns = {
        "normalized_name_ko": "TEXT",
        "normalized_name_en": "TEXT",
        "match_status": "TEXT DEFAULT 'unmatched'",
        "source_priority": "TEXT DEFAULT 'supplemental_wikidata'",
    }
    existing = {
        row["name"]
        for row in conn.execute("PRAGMA table_info(wikidata_people)").fetchall()
    }
    for column, ddl in wikidata_people_columns.items():
        if column not in existing:
            conn.execute(f"ALTER TABLE wikidata_people ADD COLUMN {column} {ddl}")


def reset_static_data(path: Path | str | None = None) -> None:
    db_path = _resolve_database_path(path)
    with get_connection(db_path) as conn:
        for table in STATIC_TABLES:
            conn.execute(f"DELETE FROM {table}")
        conn.commit()


def reset_runtime_data(path: Path | str | None = None) -> None:
    db_path = _resolve_database_path(path)
    with get_connection(db_path) as conn:
        for table in RUNTIME_TABLES:
            conn.execute(f"DELETE FROM {table}")
        conn.commit()
