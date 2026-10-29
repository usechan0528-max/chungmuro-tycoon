from __future__ import annotations

from pathlib import Path
import os
import sys


APP_NAME = "ChungmuroTycoon"


def _runtime_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


def _resource_base_dir() -> Path:
    return Path(getattr(sys, "_MEIPASS", _runtime_base_dir()))


def _user_data_base_dir() -> Path:
    if not getattr(sys, "frozen", False):
        return _runtime_base_dir()
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / APP_NAME
    if sys.platform == "win32":
        return Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / APP_NAME
    return Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / APP_NAME


BASE_DIR = _runtime_base_dir()
RESOURCE_DIR = _resource_base_dir()
USER_DATA_DIR = _user_data_base_dir()
DATA_DIR = USER_DATA_DIR / "data"
SEED_DIR = RESOURCE_DIR / "data" / "seed"
SAVE_DIR = USER_DATA_DIR / "saves"
ASSET_DIR = RESOURCE_DIR / "assets"
DB_PATH = DATA_DIR / "game.db"
MASTER_DB_PATH = DB_PATH
DEFAULT_SAVE_PATH = SAVE_DIR / "save_001.db"
MIN_SAVE_SLOTS = 3

STUDIO_RECOVERY_RATE = 0.35

STATS_100 = [
    "cash",
    "debt",
    "credit_limit",
    "production_budget",
    "marketing_budget",
    "total_cost",
    "investment_amount",
    "studio_recovery_rate",
    "break_even_audience",
    "secondary_market_revenue",
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
    "final_quality",
    "pre_release_interest",
    "reservation_rate",
    "opening_week_audience",
    "audience_score",
    "word_of_mouth",
    "second_week_drop",
    "rewatch_index",
    "fandom_index",
    "online_buzz",
    "final_audience",
    "boxoffice_revenue",
    "price_sensitivity_effect",
    "public_reputation",
    "industry_reputation",
    "critic_reputation",
    "investor_reputation",
    "creative_reputation",
    "global_reputation",
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
    "series_fatigue",
    "game_over_risk",
    "production_duration",
    "pre_production_duration",
    "shooting_duration",
    "post_production_duration",
    "marketing_duration",
    "release_timing",
    "delay_days",
    "actor_commitment_duration",
    "director_commitment_duration",
    "theater_demand",
    "ott_power",
    "foreign_competition",
    "korean_film_trust",
    "genre_trend",
    "genre_fatigue",
    "middle_budget_risk",
    "special_format_demand",
    "ticket_price_burden",
    "online_spread_power",
    "ip_value",
    "franchise_power",
    "world_expansion",
    "character_popularity",
    "sequel_demand",
    "cult_potential",
    "meme_potential",
    "reevaluation_potential",
    "secondary_market_fit",
    "directing_ability",
    "screenplay_sense",
    "market_analysis",
    "fundraising_ability",
    "distribution_negotiation",
    "marketing_sense",
    "field_control",
    "artistic_sense",
    "commercial_sense",
    "learning_ability",
]
