from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.config import DB_PATH, SAVE_DIR
from app.database import initialize_database, seed_database, set_default_database_path
from app.services import save_service
from app.services.boxoffice_service import advance_theatrical_day, start_theatrical_run
from app.services.character_service import create_new_character
from app.services.crew_work_service import get_crew_work_state
from app.services.economic_service import adjusted_scale_budget, adjust_labor_wage_to_year
from app.services.event_service import get_event_for_project
from app.services.film_service import advance_project_stage, apply_event_choice, create_project, get_project
from app.services.game_state import GameStateService
from app.services.history_service import apply_history_for_month
from app.services.market_service import ensure_market_state_for_month
from app.services.distribution_service import get_project_distribution_state
from app.services.casting_service import (
    attach_casting,
    casting_confirmation_status,
    confirm_project_casting,
    default_actor_commitment_for_project,
    discover_generated_actor_candidates,
    get_casting_discovery_options,
    list_casting_candidates,
    list_unseen_casting_responses,
    mark_casting_responses_seen,
    process_due_casting_offers,
    submit_casting_offer,
)
from app.services.people_service import attach_person_to_project, get_person_profile, update_person_project_contract
from app.services.player_filmography_service import get_player_filmography_state
from app.services.progression_service import can_calculate_release, get_stage_flow_for_scale
from app.services.world_boxoffice_service import get_world_boxoffice_state
from app.ui.screen_registry import core_screen_names, validate_core_screens
from app.database import get_connection, loads_json


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="chungmuro_smoke_") as tmp:
        backup_dir = Path(tmp)
        db_backup = backup_dir / "game.db"
        save_backup_dir = backup_dir / "saves"
        had_db = DB_PATH.exists()
        if had_db:
            shutil.copy2(DB_PATH, db_backup)
        if SAVE_DIR.exists():
            save_backup_dir.mkdir(parents=True, exist_ok=True)
            for save_file in SAVE_DIR.glob("save_*.db"):
                shutil.copy2(save_file, save_backup_dir / save_file.name)

        try:
            _run_smoke_loop()
        finally:
            set_default_database_path(DB_PATH)
            _restore_file(db_backup, DB_PATH, had_db)
            _restore_save_dir(save_backup_dir)

    print("smoke play loop ok")
    return 0


def _run_smoke_loop() -> None:
    initialize_database(DB_PATH, reset=True)
    seed_database(DB_PATH, reset_static=True)
    save_service.start_new_runtime(slot=1)
    _assert_core_screen_registry()
    _assert_save_runtime_scope()
    _assert_fixed_history_records()
    _assert_protected_director_history_records()
    _assert_dialogue_event_records()
    _assert_publicity_event_records()
    _assert_rating_censorship_event_records()
    _assert_location_event_records()
    _assert_scenario_event_records()
    _assert_stage_flow_casting_before_announcement()
    _assert_plagiarism_event_records()
    _assert_franchise_event_records()
    _assert_post_release_event_records()
    _assert_world_boxoffice_state()

    state_service = GameStateService()
    references = state_service.get_reference_data()
    era_id = _first_id(references["eras"], "era_2000s")
    genre_id = _first_id(references["genres"], "genre_crime_thriller")
    scale_id = _first_id(references["scales"], "scale_low_budget_genre")
    _assert_capitalist_start_budget()

    create_new_character(
        {
            "name": "Smoke Tester",
            "gender": "비공개",
            "age": 31,
            "era_id": era_id,
            "position": "감독",
            "wealth": "가족 자본",
            "career": "현장 스태프",
            "background": "서울 충무로권",
            "education": "영화 연출",
            "trait": "상업감각",
        }
    )
    dashboard = state_service.get_dashboard_state()
    _assert(dashboard["player"] is not None, "dashboard player missing")
    _assert("멀티플렉스" in (dashboard.get("era_ui") or {}).get("label", ""), "era-specific dashboard UI profile missing")
    _assert_studio_reputation_profile(dashboard)
    _assert(int(dashboard["player"].get("current_day", 0)) == 1, "new game did not start on day 1")
    _assert_selected_era_world_backfill()
    _assert_crew_work_wage_adjustment()
    _assert_people_activity_timeline_rules()
    _assert_long_run_market_rebase(state_service)
    state_service.advance_day()
    dashboard = state_service.get_dashboard_state()
    _assert(int(dashboard["player"]["current_day"]) == 2, "daily progression did not advance one day")

    project_id = create_project(
        title="스모크 테스트 영화",
        genre_id=genre_id,
        scale_id=scale_id,
        production_budget=900_000_000,
        marketing_budget=180_000_000,
        location_strategy="regional_location",
        shooting_duration_days=32,
        allocation={
            "scenario": 10,
            "directing": 10,
            "actors": 20,
            "shooting": 10,
            "art": 8,
            "stunt": 6,
            "vfx": 4,
            "sound": 8,
            "editing": 9,
            "contingency": 5,
        },
    )
    _assert_project_distributor_matching(project_id)
    _assert_shooting_duration_schedule(project_id, expected_days=39)
    _assert_auto_contingency_allocation(project_id)
    _assert_auto_minor_cast(project_id)
    _assert_protected_director_casting_block(project_id)
    _assert_casting_negotiation_gate(project_id)
    _assert_async_casting_response(project_id)
    generated_actor_id = _assert_generated_actor_discovery(project_id)
    _assert_actor_contract_options(project_id)
    _assert_casting_confirmation(project_id)

    result = _advance_until_release(project_id)
    _assert(result["film_id"], "release result missing film id")
    _assert_result_formula_fields(result)
    _assert_player_filmography_record(result["film_id"])
    _assert_generated_actor_filmography(generated_actor_id, result["film_id"], result["title"])

    dashboard = state_service.get_dashboard_state()
    _assert(dashboard["completed_films"], "completed film missing from dashboard")
    _assert_studio_reputation_profile(dashboard)
    save_path = save_service.save_game(slot=1)
    _assert(save_path.exists(), "save file was not created")
    manual_save_path = save_service.save_game(slot=3)
    _assert(manual_save_path.name == "save_003.db", "manual save slot 3 used the wrong filename")
    _assert(manual_save_path.exists(), "manual save slot 3 was not created")
    slots = save_service.list_save_slots()
    _assert(len(slots) >= 3, "less than three save slots were exposed")
    slot_summary = save_service.describe_slot(3)
    _assert("월" in slot_summary and "일" in slot_summary, "save slot summary did not include current date")
    _assert(save_service.latest_save_slot() in {1, 3}, "latest save slot was not detected")
    _assert_calendar_records(project_id)
    _assert_production_management_records(project_id)


def _advance_until_release(project_id: str) -> dict:
    for _ in range(24):
        project = get_project(project_id)
        _assert(project is not None, "project missing during production")
        if can_calculate_release(project["stage"]):
            state = start_theatrical_run(project_id)
            while state["status"] != "completed":
                state = advance_theatrical_day(state["id"])
            return state["final_result"]

        event = get_event_for_project(project_id)
        if event and event.get("choices"):
            choice = _safe_choice(event["choices"])
            apply_event_choice(project_id, choice, event)
        else:
            advance_project_stage(project_id)

    raise RuntimeError("project did not reach a release-ready stage")


def _assert_studio_reputation_profile(dashboard: dict) -> None:
    studio = dashboard.get("studio") or {}
    profile = studio.get("reputation_profile") or {}
    _assert(profile.get("primaryLabel"), "studio reputation primary label missing")
    _assert(profile.get("secondaryLabel"), "studio reputation secondary label missing")
    _assert(profile.get("summary"), "studio reputation summary missing")
    _assert(isinstance(profile.get("signals"), list), "studio reputation signals must be a list")


def _assert_capitalist_start_budget() -> None:
    create_new_character(
        {
            "name": "Capitalist Smoke",
            "gender": "비공개",
            "age": 42,
            "era_id": "era_2020s",
            "position": "영화인",
            "origin_id": "corporate_finance",
            "education_id": "business_marketing",
            "trait_id": "numbers_strategist",
            "reputation_seed_id": "investor_known",
            "wealth_id": "capitalist",
            "first_contact_id": "theater_part_timer",
            "obsession_id": "ip_world",
            "weakness_id": "safe_choice",
        }
    )
    with get_connection() as conn:
        player = conn.execute("SELECT cash, stats_json FROM player_state WHERE id = 1").fetchone()
        studio = conn.execute("SELECT cash, own_capital, investment_capital FROM studio_state WHERE id = 1").fetchone()
        scale = conn.execute("SELECT * FROM project_scales WHERE id = 'scale_large_commercial'").fetchone()
    adjusted = adjusted_scale_budget(dict(scale), 2020)
    required_cash = int(adjusted["min_budget"] * 1.35)
    stats = loads_json(player["stats_json"], {}) if player else {}
    _assert(player is not None and int(player["cash"]) >= required_cash, "capitalist start did not cover a large film")
    _assert(studio is not None and int(studio["own_capital"]) == int(player["cash"]), "capitalist capital was not stored as own capital")
    _assert(int(studio["investment_capital"]) == 0, "capitalist own money should not be external investment capital")
    _assert(stats.get("wealth") == "자본가", "capitalist wealth label was not stored")
    _assert(stats.get("capitalist_large_film_budget"), "capitalist budget basis was not stored")


def _assert_selected_era_world_backfill() -> None:
    with get_connection() as conn:
        old_ticket_count = conn.execute(
            "SELECT COUNT(*) AS count FROM ticket_prices WHERE year BETWEEN 1980 AND 1999"
        ).fetchone()["count"]
        event_backfill_count = conn.execute(
            """
            SELECT COUNT(*) AS count
            FROM event_history
            WHERE category = 'historical_backfill' AND year < 2000
            """
        ).fetchone()["count"]
        fixed_movie_count = conn.execute(
            """
            SELECT COUNT(*) AS count
            FROM movies_historical
            WHERE release_year < 2000
              AND origin IN ('domestic_protected', 'foreign_fixed', 'kmdb', 'wikidata')
            """
        ).fetchone()["count"]
    _assert(old_ticket_count >= 20, "old-era ticket prices were not backfilled")
    _assert(event_backfill_count > 0, "past history events were not marked as occurred")
    _assert(fixed_movie_count > 0, "past fixed film history was not backfilled")


def _assert_crew_work_wage_adjustment() -> None:
    wage_1980 = adjust_labor_wage_to_year(110_000, to_year=1980)
    wage_2020 = adjust_labor_wage_to_year(110_000, to_year=2020)
    wage_2030 = adjust_labor_wage_to_year(110_000, to_year=2030)
    _assert(10_000 <= wage_1980 < wage_2020 < wage_2030, "labor wage inflation adjustment is not monotonic")
    state = get_crew_work_state()
    option = next((row for row in state["options"] if row["id"] == "production_runner"), None)
    _assert(option is not None, "crew work option missing")
    _assert(option["dailyWage"] == adjust_labor_wage_to_year(110_000, to_year=2000), "crew work wage did not use current-year adjustment")
    _assert("물가 기준" in option.get("wageBasis", ""), "crew work wage basis text missing")


def _assert_people_activity_timeline_rules() -> None:
    cha_1980 = get_person_profile("actor_cha_tae_hyeon", 1980, 12)
    cha_1990 = get_person_profile("actor_cha_tae_hyeon", 1990, 12)
    cha_2000 = get_person_profile("actor_cha_tae_hyeon", 2000, 12)
    _assert(cha_1980["is_available"] is False, "pre-debut actor should not be available")
    _assert("활동 전" in cha_1980["career_stage_label"], "pre-debut actor stage text missing")
    _assert(cha_1990["is_available"] is True, "available-from year actor should become available")
    _assert("신인" in cha_1990["career_stage_label"], "new actor stage was not shown in the 1990s")
    _assert(
        "주요" in cha_2000["career_stage_label"] or "전성기" in cha_2000["career_stage_label"],
        "prime-era actor did not show major activity stage",
    )
    bong_2000 = get_person_profile("director_bong_joon_ho", 2000, 12)
    bong_2019 = get_person_profile("director_bong_joon_ho", 2019, 12)
    _assert("기생충" not in "\n".join(bong_2000["filmography"]), "future protected film leaked into 2000 profile")
    _assert("기생충" in "\n".join(bong_2019["filmography"]), "released protected film missing from 2019 profile")
    _assert(bong_2000["expected_fee"] != bong_2019["expected_fee"], "director fee did not vary by era/career")


def _assert_long_run_market_rebase(state_service: GameStateService) -> None:
    baseline_1980 = ensure_market_state_for_month(1980, 1, refresh=True)
    baseline_1980_modifiers = loads_json(baseline_1980["modifiers_json"], {})
    with get_connection() as conn:
        conn.execute("DELETE FROM market_state WHERE year = 2010 AND month = 1")
        conn.execute("DELETE FROM save_market_state WHERE year = 2010 AND month = 1")
        conn.execute(
            "UPDATE player_state SET current_year = 2009, current_month = 12, current_day = 31 WHERE id = 1"
        )
        conn.execute(
            "UPDATE save_player_state SET current_year = 2009, current_month = 12, current_day = 31 WHERE id = 1"
        )
        conn.commit()

    state_service.advance_day()

    with get_connection() as conn:
        player = conn.execute("SELECT current_year, current_month, current_day FROM player_state WHERE id = 1").fetchone()
        market_2010 = conn.execute("SELECT * FROM market_state WHERE year = 2010 AND month = 1").fetchone()
        ticket_1980 = conn.execute("SELECT average_ticket_price FROM ticket_prices WHERE year = 1980").fetchone()
        ticket_2010 = conn.execute("SELECT average_ticket_price FROM ticket_prices WHERE year = 2010").fetchone()
        conn.execute(
            "UPDATE player_state SET current_year = 2000, current_month = 1, current_day = 1 WHERE id = 1"
        )
        conn.execute(
            "UPDATE save_player_state SET current_year = 2000, current_month = 1, current_day = 1 WHERE id = 1"
        )
        conn.commit()

    _assert(player is not None and int(player["current_year"]) == 2010, "long-run day advance did not cross into 2010")
    _assert(int(player["current_month"]) == 1 and int(player["current_day"]) == 1, "long-run date rollover failed")
    _assert(market_2010 is not None, "2010 market state was not rebuilt on era transition")
    modifiers_2010 = loads_json(market_2010["modifiers_json"], {})
    _assert(modifiers_2010.get("era_rule_id") == "era_2010s", "2010 market state did not use 2010s era rules")
    _assert(
        (modifiers_2010.get("economic_modifiers") or {}).get("year") == 2010,
        "2010 market state did not carry 2010 economic modifiers",
    )
    _assert(
        float(modifiers_2010.get("production_cost_modifier", 1.0))
        != float(baseline_1980_modifiers.get("production_cost_modifier", 1.0)),
        "production cost modifier did not change between 1980 and 2010",
    )
    _assert(ticket_1980 and ticket_2010, "ticket price history missing transition years")
    _assert(
        int(ticket_1980["average_ticket_price"]) < int(ticket_2010["average_ticket_price"]),
        "ticket prices were not adjusted upward across eras",
    )


def _assert_production_management_records(project_id: str) -> None:
    with get_connection() as conn:
        location_count = conn.execute(
            "SELECT COUNT(*) AS count FROM project_location_plans WHERE project_id = ?",
            (project_id,),
        ).fetchone()["count"]
        scenario_count = conn.execute(
            "SELECT COUNT(*) AS count FROM project_scenario_development WHERE project_id = ?",
            (project_id,),
        ).fetchone()["count"]
        scenario_row = conn.execute(
            """
            SELECT *
            FROM project_scenario_development
            WHERE project_id = ? AND step_id = 'table_reading'
            """,
            (project_id,),
        ).fetchone()
        scenario_calendar_count = conn.execute(
            """
            SELECT COUNT(*) AS count
            FROM calendar_events
            WHERE project_id = ? AND event_type = 'scenario_development'
            """,
            (project_id,),
        ).fetchone()["count"]
        regional_location = conn.execute(
            "SELECT * FROM project_location_plans WHERE project_id = ? AND location_strategy = 'regional_location'",
            (project_id,),
        ).fetchone()
        crew_count = conn.execute(
            "SELECT COUNT(*) AS count FROM project_crew_roles WHERE project_id = ?",
            (project_id,),
        ).fetchone()["count"]
        shooting_count = conn.execute(
            "SELECT COUNT(*) AS count FROM shooting_schedule_blocks WHERE project_id = ?",
            (project_id,),
        ).fetchone()["count"]
        cashflow_count = conn.execute(
            "SELECT COUNT(*) AS count FROM project_cashflows WHERE project_id = ?",
            (project_id,),
        ).fetchone()["count"]
        paid_cashflow_count = conn.execute(
            "SELECT COUNT(*) AS count FROM project_cashflows WHERE project_id = ? AND status = 'paid'",
            (project_id,),
        ).fetchone()["count"]
        marketing_asset_count = conn.execute(
            "SELECT COUNT(*) AS count FROM marketing_assets WHERE project_id = ?",
            (project_id,),
        ).fetchone()["count"]
        first_image_count = conn.execute(
            "SELECT COUNT(*) AS count FROM marketing_assets WHERE project_id = ? AND asset_type = 'first_image'",
            (project_id,),
        ).fetchone()["count"]
        version_count = conn.execute(
            "SELECT COUNT(*) AS count FROM project_versions WHERE project_id = ?",
            (project_id,),
        ).fetchone()["count"]
        location_cashflow = conn.execute(
            """
            SELECT COUNT(*) AS count
            FROM project_cashflows
            WHERE project_id = ? AND cashflow_type = 'location_strategy_cost'
            """,
            (project_id,),
        ).fetchone()["count"]
    _assert(scenario_count >= 5, "scenario development steps were not created")
    _assert(scenario_row is not None, "table reading scenario step was not created")
    _assert(scenario_row["diagnosis_text"], "scenario diagnosis text was not stored")
    _assert(scenario_calendar_count >= 5, "scenario development calendar records were not created")
    _assert(location_count > 0, "location plan was not created")
    _assert(regional_location is not None, "selected regional location strategy was not stored")
    _assert(crew_count > 0, "production crew roles were not created")
    _assert(shooting_count > 0, "shooting schedule blocks were not created")
    _assert(cashflow_count > 0, "project cashflow plan was not created")
    _assert(location_cashflow > 0, "location strategy cashflow was not created")
    _assert(paid_cashflow_count > 0, "project cashflow disbursement was not recorded")
    _assert(marketing_asset_count > 0, "marketing asset release plan was not created")
    _assert(first_image_count > 0, "first image reveal plan was not created")
    _assert(version_count >= 3, "project release versions were not created")


def _assert_project_distributor_matching(project_id: str) -> None:
    state = get_project_distribution_state(project_id)
    _assert(state["status"] == "matched", "project did not automatically match an available distributor")
    _assert(state.get("distributorId"), "matched distributor id missing")
    _assert(state.get("summary"), "matched distributor summary missing")
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM project_distribution WHERE project_id = ?", (project_id,)).fetchone()
        project = conn.execute("SELECT stats_json FROM projects WHERE id = ?", (project_id,)).fetchone()
    stats = loads_json(project["stats_json"], {}) if project else {}
    _assert(row is not None and row["distributor_id"], "project_distribution row missing distributor")
    _assert(stats.get("distributor_id") == row["distributor_id"], "project stats did not mirror distributor match")


def _assert_casting_confirmation(project_id: str) -> None:
    before = casting_confirmation_status(project_id)
    _assert(before["can_confirm"] is True, "casting confirmation should be available after accepted cast")
    after = confirm_project_casting(project_id)
    _assert(after["is_confirmed"] is True, "casting confirmation did not mark project as confirmed")
    with get_connection() as conn:
        project = conn.execute("SELECT stats_json FROM projects WHERE id = ?", (project_id,)).fetchone()
        timeline_count = conn.execute(
            """
            SELECT COUNT(*) AS count
            FROM people_career_timeline
            WHERE project_id = ? AND status = 'cast_confirmed'
            """,
            (project_id,),
        ).fetchone()["count"]
        calendar_row = conn.execute(
            """
            SELECT *
            FROM calendar_events
            WHERE project_id = ? AND event_type = 'cast_confirmation'
            """,
            (project_id,),
        ).fetchone()
    stats = loads_json(project["stats_json"], {}) if project else {}
    _assert(int(stats.get("cast_confirmed", 0) or 0) == 1, "cast confirmation flag missing")
    _assert(int(timeline_count or 0) > 0, "cast confirmation timeline rows missing")
    _assert(calendar_row is not None, "cast confirmation calendar event missing")


def _assert_stage_flow_casting_before_announcement() -> None:
    for scale_id in ("scale_mid_commercial", "scale_large_commercial", "scale_tentpole"):
        flow = get_stage_flow_for_scale(scale_id)
        _assert("production_announcement" in flow, f"{scale_id} production announcement stage missing")
        cast_indices = [
            index
            for index, stage in enumerate(flow)
            if stage in {"casting", "casting_simple", "star_casting"}
        ]
        _assert(cast_indices, f"{scale_id} casting stage missing")
        _assert(max(cast_indices) < flow.index("production_announcement"), f"{scale_id} announces before casting")


def _assert_shooting_duration_schedule(project_id: str, *, expected_days: int) -> None:
    with get_connection() as conn:
        project = conn.execute("SELECT stats_json FROM projects WHERE id = ?", (project_id,)).fetchone()
        total_planned_days = conn.execute(
            "SELECT COALESCE(SUM(planned_days), 0) AS days FROM shooting_schedule_blocks WHERE project_id = ?",
            (project_id,),
        ).fetchone()["days"]
    stats = loads_json(project["stats_json"], {}) if project else {}
    _assert(int(stats.get("planned_shooting_days") or 0) == 32, "custom shooting duration was not stored")
    _assert(int(stats.get("shooting_duration") or 0) == expected_days, "location-adjusted shooting duration was not stored")
    _assert(int(total_planned_days or 0) == expected_days, "shooting schedule did not use the planned shooting duration")
    default_commitment = default_actor_commitment_for_project(project_id)
    _assert(
        int(default_commitment.get("months") or 0) == 3,
        "actor default commitment should be shooting duration rounded to months plus one month",
    )
    _assert(
        int(default_commitment.get("shooting_days") or 0) == expected_days,
        "actor default commitment used wrong shooting days",
    )


def _assert_auto_contingency_allocation(project_id: str) -> None:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT percentage, amount
            FROM project_budget_allocations
            WHERE project_id = ? AND category = 'contingency'
            """,
            (project_id,),
        ).fetchone()
        total_amount = conn.execute(
            """
            SELECT COALESCE(SUM(amount), 0) AS total_amount
            FROM project_budget_allocations
            WHERE project_id = ?
            """,
            (project_id,),
        ).fetchone()["total_amount"]
        project = conn.execute("SELECT production_budget FROM projects WHERE id = ?", (project_id,)).fetchone()
    _assert(row is not None, "contingency allocation was not stored")
    _assert(int(row["percentage"]) == 15, "contingency was not derived from remaining allocation")
    _assert(int(total_amount) == int(project["production_budget"]), "allocation amounts do not match production budget")


def _assert_generated_actor_discovery(project_id: str) -> str:
    options = get_casting_discovery_options(project_id)
    _assert(options, "generated actor discovery options were not exposed for low-budget project")
    option = next((row for row in options if row["id"] == "film_school"), options[0])
    with get_connection() as conn:
        before = conn.execute("SELECT COUNT(*) AS count FROM save_generated_people").fetchone()["count"]
    generated = discover_generated_actor_candidates(project_id, option["id"], int(option["recommended_budget"]))
    _assert(len(generated) >= 2, "actor discovery did not create enough candidates")
    with get_connection() as conn:
        after = conn.execute("SELECT COUNT(*) AS count FROM save_generated_people").fetchone()["count"]
        first_person = conn.execute("SELECT * FROM people WHERE id = ?", (generated[0]["id"],)).fetchone()
    _assert(after >= before + len(generated), "generated actors were not persisted in save_generated_people")
    _assert(first_person is not None, "generated actor was not inserted into people table")
    candidates = list_casting_candidates("actor", 2000)
    generated_ids = {row["id"] for row in generated}
    visible_ids = {row["id"] for row in candidates}
    _assert(generated_ids & visible_ids, "generated actors were not visible in casting candidates")
    profile = get_person_profile(generated[0]["id"], 2000, 1)
    _assert(profile["is_available"] is True, "generated actor profile was not available in current year")
    _assert("신인" in profile["career_stage_label"], "generated actor did not get newcomer stage text")
    attach_person_to_project(
        project_id,
        generated[0]["id"],
        "supporting_actor",
        contract_fee=5_000_000,
        commitment_months=1,
    )
    return str(generated[0]["id"])


def _assert_auto_minor_cast(project_id: str) -> None:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT pp.role, pp.contract_fee, pp.contract_options_json, p.name_ko
            FROM project_people pp
            JOIN people p ON p.id = pp.person_id
            WHERE pp.project_id = ?
              AND pp.role IN ('minor_actor', 'day_player', 'background_actor')
            """,
            (project_id,),
        ).fetchall()
        project = conn.execute("SELECT stats_json FROM projects WHERE id = ?", (project_id,)).fetchone()
    _assert(len(rows) >= 4, "low-budget project did not auto-fill minor cast")
    for row in rows:
        options = loads_json(row["contract_options_json"], {})
        terms = options.get("terms") or {}
        _assert(terms.get("autoMinorCast") is True, "auto-filled minor cast missing contract marker")
        _assert(int(row["contract_fee"] or 0) > 0, "auto-filled minor cast missing era-adjusted fee")
    stats = loads_json(project["stats_json"], {}) if project else {}
    _assert(int(stats.get("minor_cast_auto_filled", 0) or 0) == len(rows), "minor cast count was not stored in project stats")
    _assert(int(stats.get("minor_cast_cost", 0) or 0) > 0, "minor cast cost was not stored in project stats")
    status = casting_confirmation_status(project_id)
    _assert(int(status["actor_count"]) == 0, "auto-filled minor cast should not satisfy principal casting count")
    _assert(status["can_confirm"] is False, "auto-filled minor cast should not make casting confirmation available")


def _assert_casting_negotiation_gate(project_id: str) -> None:
    actor_id = "actor_song_kang_ho"
    failed = attach_casting(
        project_id,
        actor_id,
        "supporting_actor",
        contract_fee=0,
        commitment_months=1,
    )
    _assert(failed["accepted"] is False, "lowball casting offer should not be accepted")
    with get_connection() as conn:
        rejected_row = conn.execute(
            """
            SELECT *
            FROM project_people
            WHERE project_id = ? AND person_id = ? AND role = 'supporting_actor'
            """,
            (project_id, actor_id),
        ).fetchone()
    _assert(rejected_row is None, "rejected casting negotiation created a confirmed cast row")

    accepted = attach_casting(
        project_id,
        actor_id,
        "supporting_actor",
        contract_fee=3_000_000_000,
        commitment_months=2,
        promotion_obligation=True,
        promotion_days=3,
        contract_terms={
            "runningGuarantee": {"enabled": True, "rate": 0.005, "trigger": "release"},
            "boxOfficeBonus": {"enabled": True, "audience": 1, "amount": 500_000},
        },
    )
    _assert(accepted["accepted"] is True, "favorable casting offer should be accepted")
    with get_connection() as conn:
        accepted_row = conn.execute(
            """
            SELECT *
            FROM project_people
            WHERE project_id = ? AND person_id = ? AND role = 'supporting_actor'
            """,
            (project_id, actor_id),
        ).fetchone()
        log_count = conn.execute(
            """
            SELECT COUNT(*) AS count
            FROM production_stage_logs
            WHERE project_id = ? AND category = 'casting_negotiation'
            """,
            (project_id,),
        ).fetchone()["count"]
    _assert(accepted_row is not None, "accepted casting negotiation did not create a confirmed cast row")
    _assert(int(log_count) >= 2, "casting negotiation attempts were not logged")


def _assert_async_casting_response(project_id: str) -> None:
    actor_id = "actor_choi_min_sik"
    offer = submit_casting_offer(
        project_id,
        actor_id,
        "lead_actor",
        contract_fee=4_000_000_000,
        commitment_months=2,
        promotion_obligation=True,
        promotion_days=3,
        contract_terms={
            "runningGuarantee": {"enabled": True, "rate": 0.01, "trigger": "release"},
            "boxOfficeBonus": {"enabled": True, "audience": 1, "amount": 800_000},
        },
    )
    with get_connection() as conn:
        pending_row = conn.execute(
            "SELECT * FROM casting_offers WHERE id = ? AND status = 'pending'",
            (offer["offer_id"],),
        ).fetchone()
        early_cast = conn.execute(
            """
            SELECT *
            FROM project_people
            WHERE project_id = ? AND person_id = ? AND role = 'lead_actor'
            """,
            (project_id, actor_id),
        ).fetchone()
        current = conn.execute(
            "SELECT current_year, current_month, current_day FROM player_state WHERE id = 1"
        ).fetchone()
        conn.execute(
            """
            UPDATE casting_offers
            SET response_due_year = ?, response_due_month = ?, response_due_day = ?
            WHERE id = ?
            """,
            (current["current_year"], current["current_month"], current["current_day"], offer["offer_id"]),
        )
        conn.commit()
    _assert(pending_row is not None, "async casting offer was not stored as pending")
    _assert(early_cast is None, "pending async casting offer created cast before response")

    resolved = process_due_casting_offers()
    _assert(any(row["id"] == offer["offer_id"] for row in resolved), "due async casting offer was not processed")
    popups = list_unseen_casting_responses()
    _assert(any(row["id"] == offer["offer_id"] for row in popups), "casting response popup was not queued")
    mark_casting_responses_seen([offer["offer_id"]])
    with get_connection() as conn:
        accepted_row = conn.execute(
            """
            SELECT *
            FROM project_people
            WHERE project_id = ? AND person_id = ? AND role = 'lead_actor'
            """,
            (project_id, actor_id),
        ).fetchone()
        seen = conn.execute(
            "SELECT popup_seen FROM casting_offers WHERE id = ?",
            (offer["offer_id"],),
        ).fetchone()
    _assert(accepted_row is not None, "accepted async casting response did not confirm cast")
    _assert(int(seen["popup_seen"]) == 1, "casting response popup was not marked seen")


def _assert_generated_actor_filmography(actor_id: str, film_id: str, title: str) -> None:
    with get_connection() as conn:
        released = conn.execute(
            """
            SELECT release_year, release_month
            FROM completed_films
            WHERE id = ?
            """,
            (film_id,),
        ).fetchone()
    _assert(released is not None, "released film row missing for generated actor filmography check")
    profile = get_person_profile(actor_id, int(released["release_year"]), int(released["release_month"] or 12))
    filmography_text = "\n".join(profile.get("filmography") or [])
    _assert(title in filmography_text, "generated actor filmography did not include released player film")


def _assert_result_formula_fields(result: dict) -> None:
    for key in (
        "opening_week_audience",
        "word_of_mouth",
        "second_week_drop",
        "theatrical_break_even_audience",
        "net_break_even_audience",
        "profit_margin",
        "reputation_deltas",
        "network_deltas",
        "release_version_name",
        "version_profile",
        "talent_backend_payout",
    ):
        _assert(key in result, f"release result missing enhanced formula field: {key}")
    _assert(isinstance(result["reputation_deltas"], dict), "reputation deltas must be a dict")
    _assert("public_reputation" in result["reputation_deltas"], "public reputation delta missing")
    _assert(int(result["talent_backend_payout"] or 0) > 0, "casting backend payout was not applied")


def _assert_fixed_history_records() -> None:
    domestic = apply_history_for_month(1998, 4)
    _assert(
        "theater_1998_cgv_gangbyeon11" in domestic["historical_events"],
        "theater historical event was not applied",
    )
    with get_connection() as conn:
        domestic_market = conn.execute("SELECT * FROM market_state WHERE year = 1998 AND month = 4").fetchone()
        unlock = conn.execute(
            "SELECT * FROM save_event_flags WHERE key = 'system_unlocked_multiplex_release'"
        ).fetchone()
    _assert(domestic_market is not None, "domestic historical event did not update market state")
    _assert(int(domestic_market["theater_demand"]) >= 60, "domestic historical event effects were not applied")
    _assert(unlock is not None, "domestic historical event unlock was not stored")

    applied = apply_history_for_month(2009, 12)
    _assert(
        "foreign_2009_avatar" in applied["foreign_fixed_events"],
        "fixed foreign event was not applied as market release",
    )
    with get_connection() as conn:
        market = conn.execute("SELECT * FROM market_state WHERE year = 2009 AND month = 12").fetchone()
        movie = conn.execute("SELECT * FROM movies WHERE id = 'foreign_2009_avatar'").fetchone()
    _assert(market is not None, "fixed foreign event did not update market state")
    _assert(int(market["foreign_competition"]) >= 85, "fixed foreign event effects were not applied")
    modifiers = loads_json(market["modifiers_json"], {})
    _assert(int(modifiers.get("special_format_demand", 0)) >= 40, "fixed foreign event modifiers missing")
    _assert(movie is not None, "fixed foreign movie was not registered")


def _assert_core_screen_registry() -> None:
    validate_core_screens()
    expected = {
        "StartScreen",
        "CharacterCreationScreen",
        "DashboardScreen",
        "CrewWorkScreen",
        "PeopleDatabaseScreen",
        "FinanceScreen",
        "FilmPlanningScreen",
        "BudgetAllocationScreen",
        "CastingScreen",
        "DialogueEventScreen",
        "ProductionProgressScreen",
        "ReleaseStrategyScreen",
        "BoxOfficeResultScreen",
        "HistoryTimelineScreen",
        "IndustryDatabaseScreen",
        "OrganizationProfileScreen",
        "AwardProfileScreen",
        "SaveLoadScreen",
    }
    _assert(set(core_screen_names()) == expected, "core UI screen registry does not match the required screen set")


def _assert_world_boxoffice_state() -> None:
    state = get_world_boxoffice_state()
    _assert(state.get("rows"), "world box office state should always expose at least one market row")
    summary = state.get("summary") or {}
    _assert(int(summary.get("totalScreens") or 0) > 0, "world box office state missing total screen estimate")


def _assert_save_runtime_scope() -> None:
    required_labels = {
        "플레이어 상태",
        "제작사 상태",
        "현재 연도/월",
        "진행 중 프로젝트",
        "완성 영화 목록",
        "명성",
        "인맥",
        "관계도",
        "발생한 역사 이벤트 flag",
        "생성된 미래 인물/영화",
    }
    scope_labels = {item["label"] for item in save_service.save_runtime_scope()}
    missing_labels = required_labels - scope_labels
    _assert(not missing_labels, f"save runtime scope labels missing: {sorted(missing_labels)}")
    missing_tables = save_service.validate_save_runtime_scope()
    _assert(not missing_tables, f"save runtime scope tables missing: {missing_tables}")


def _assert_calendar_records(project_id: str) -> None:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM calendar_events WHERE project_id = ? ORDER BY year, month, day",
            (project_id,),
        ).fetchall()
        stage_rows = conn.execute(
            "SELECT * FROM calendar_events WHERE project_id = ? AND event_type = 'stage_progress'",
            (project_id,),
        ).fetchall()
    _assert(rows, "project calendar records were not created")
    _assert(stage_rows, "project stage progression did not create calendar records")


def _assert_protected_director_history_records() -> None:
    expected_directors = {
        "director_bong_joon_ho": "봉준호",
        "director_park_chan_wook": "박찬욱",
        "director_lee_chang_dong": "이창동",
        "director_kim_ki_young": "김기영",
        "director_choi_dong_hoon": "최동훈",
    }
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT p.id, p.name_ko, p.historical_filmography_locked,
                   COUNT(f.id) AS protected_film_count
            FROM people p
            LEFT JOIN history_protected_director_films f ON f.director_id = p.id
            WHERE p.id IN (?, ?, ?, ?, ?)
            GROUP BY p.id, p.name_ko, p.historical_filmography_locked
            """,
            tuple(expected_directors),
        ).fetchall()
    by_id = {row["id"]: row for row in rows}
    for director_id, name in expected_directors.items():
        row = by_id.get(director_id)
        _assert(row is not None, f"protected director missing: {name}")
        _assert(int(row["historical_filmography_locked"]) == 1, f"protected filmography not locked: {name}")
        _assert(int(row["protected_film_count"]) > 0, f"protected filmography missing works: {name}")

    applied = apply_history_for_month(2003, 4)
    _assert(
        "film_2003_memories_of_murder" in applied["protected_director_films"],
        "protected director film was not applied as fixed history",
    )
    with get_connection() as conn:
        historical = conn.execute(
            "SELECT * FROM movies_historical WHERE id = 'film_2003_memories_of_murder'"
        ).fetchone()
        movie = conn.execute(
            "SELECT * FROM movies WHERE id = 'film_2003_memories_of_murder'"
        ).fetchone()
    _assert(historical is not None, "protected director film was not registered as historical movie")
    _assert(movie is not None and movie["movie_type"] == "historical_protected", "protected movie type missing")


def _assert_protected_director_casting_block(project_id: str) -> None:
    with get_connection() as conn:
        conn.execute("UPDATE player_state SET current_year = 2000, current_month = 1 WHERE id = 1")
        conn.commit()
    try:
        attach_person_to_project(
            project_id,
            "director_bong_joon_ho",
            "director",
            contract_fee=1,
            commitment_months=12,
        )
    except ValueError as exc:
        _assert("확정된 장기 일정" in str(exc), "protected casting block returned wrong message")
    else:
        raise AssertionError("protected director long-term casting was not blocked")


def _assert_actor_contract_options(project_id: str) -> None:
    with get_connection() as conn:
        actor = conn.execute(
            """
            SELECT id
            FROM people
            WHERE type = 'actor'
            ORDER BY available_from, name_ko
            LIMIT 1
            """
        ).fetchone()
    _assert(actor is not None, "actor seed data missing for contract option smoke test")
    actor_id = str(actor["id"])
    attach_person_to_project(
        project_id,
        actor_id,
        "lead_actor",
        contract_fee=120_000_000,
        commitment_months=4,
        sequel_option=True,
        promotion_obligation=True,
        promotion_days=6,
        contract_terms={
            "deferredFee": 10_000_000,
            "runningGuarantee": {"enabled": True, "rate": 0.01, "trigger": "release"},
            "boxOfficeBonus": {"enabled": True, "audience": 1, "amount": 1_000_000},
            "imageRights": True,
        },
    )
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT sequel_option, promotion_obligation, promotion_days,
                   schedule_commitment_months, contract_options_json
            FROM project_people
            WHERE project_id = ? AND person_id = ?
            """,
            (project_id, actor_id),
        ).fetchone()
    _assert(row is not None, "actor contract row was not recorded")
    _assert(int(row["sequel_option"]) == 1, "sequel option was not stored")
    _assert(int(row["promotion_obligation"]) == 1, "promotion obligation was not stored")
    _assert(int(row["promotion_days"]) == 6, "promotion obligation days were not stored")
    _assert(int(row["schedule_commitment_months"]) == 4, "schedule commitment was not stored")
    options = loads_json(row["contract_options_json"], {})
    _assert(options.get("sequelOption") is True, "contract option payload missing sequel option")
    _assert(options.get("promotionObligation") is True, "contract option payload missing promotion obligation")
    terms = options.get("terms") or {}
    _assert((terms.get("runningGuarantee") or {}).get("enabled") is True, "running guarantee terms missing")
    _assert((terms.get("boxOfficeBonus") or {}).get("amount") == 1_000_000, "box-office bonus terms missing")
    _assert(terms.get("deferredFee") == 10_000_000, "deferred fee terms missing")
    update_person_project_contract(
        project_id,
        actor_id,
        "lead_actor",
        contract_fee=90_000_000,
        commitment_months=2,
        sequel_option=False,
        promotion_obligation=True,
        promotion_days=3,
        contract_terms={
            "runningGuarantee": {"enabled": True, "rate": 0.005, "trigger": "release"},
            "boxOfficeBonus": {"enabled": True, "audience": 1, "amount": 500_000},
            "imageRights": True,
        },
    )
    with get_connection() as conn:
        updated = conn.execute(
            """
            SELECT contract_fee, sequel_option, promotion_obligation,
                   promotion_days, schedule_commitment_months, contract_options_json
            FROM project_people
            WHERE project_id = ? AND person_id = ?
            """,
            (project_id, actor_id),
        ).fetchone()
    _assert(updated is not None, "updated actor contract row missing")
    _assert(int(updated["contract_fee"]) == 90_000_000, "contract fee update was not stored")
    _assert(int(updated["sequel_option"]) == 0, "sequel option update was not stored")
    _assert(int(updated["promotion_obligation"]) == 1, "promotion obligation update was not preserved")
    _assert(int(updated["promotion_days"]) == 3, "promotion days update was not stored")
    _assert(int(updated["schedule_commitment_months"]) == 2, "schedule commitment update was not stored")
    updated_options = loads_json(updated["contract_options_json"], {})
    updated_terms = updated_options.get("terms") or {}
    _assert((updated_terms.get("runningGuarantee") or {}).get("rate") == 0.005, "running guarantee update was not stored")


def _assert_dialogue_event_records() -> None:
    with get_connection() as conn:
        event = conn.execute(
            "SELECT * FROM simulation_events WHERE id = 'dialogue_investor_budget_concern'"
        ).fetchone()
        dialogue = conn.execute(
            "SELECT * FROM production_dialogue_events WHERE id = 'dialogue_investor_budget_concern'"
        ).fetchone()
    _assert(event is not None, "dialogue event was not seeded")
    _assert(event["category"] == "dialogue", "dialogue event category was not preserved")
    _assert(dialogue is not None and dialogue["npc_type"] == "investor", "dialogue npc metadata missing")
    choices = loads_json(event["choices_json"], [])
    first_choice = next((choice for choice in choices if choice.get("id") == "explain_market_data"), None)
    _assert(first_choice is not None, "dialogue check choice missing")
    _assert("effectsOnSuccess" in first_choice, "dialogue success effects missing")


def _assert_publicity_event_records() -> None:
    with get_connection() as conn:
        announcement = conn.execute(
            "SELECT * FROM simulation_events WHERE id = 'event_production_announcement_conference'"
        ).fetchone()
        first_image = conn.execute(
            "SELECT * FROM simulation_events WHERE id = 'event_first_image_reveal_strategy'"
        ).fetchone()
    _assert(announcement is not None, "production announcement event was not seeded")
    _assert(announcement["stage"] == "production_announcement", "production announcement stage missing")
    announcement_choices = loads_json(announcement["choices_json"], [])
    _assert(
        any((choice.get("effects") or {}).get("flags", {}).get("pressAnnouncement") for choice in announcement_choices),
        "production announcement press flag missing",
    )
    _assert(first_image is not None, "first image reveal event was not seeded")
    image_choices = loads_json(first_image["choices_json"], [])
    _assert(
        any(
            (choice.get("effects") or {}).get("flags", {}).get("pressAnnouncement", {}).get("assetType")
            == "first_image"
            for choice in image_choices
        ),
        "first image reveal flag missing",
    )


def _assert_rating_censorship_event_records() -> None:
    with get_connection() as conn:
        censorship_1990s = conn.execute(
            "SELECT * FROM simulation_events WHERE id = 'event_censorship_script_review_1990s'"
        ).fetchone()
        rating_revision = conn.execute(
            "SELECT * FROM simulation_events WHERE id = 'event_modern_rating_revision_request'"
        ).fetchone()
        sensitive_backlash = conn.execute(
            "SELECT * FROM simulation_events WHERE id = 'event_modern_sensitive_topic_backlash'"
        ).fetchone()
    _assert(censorship_1990s is not None, "1990s censorship review event was not seeded")
    censorship_trigger = loads_json(censorship_1990s["trigger_json"], {})
    _assert("era_1990s" in censorship_trigger.get("eraIds", []), "1990s censorship era trigger missing")
    _assert(
        float(censorship_trigger.get("genreWeights", {}).get("social_true_story", 0)) > 1.5,
        "social true story censorship weighting missing",
    )

    _assert(rating_revision is not None, "modern rating revision event was not seeded")
    rating_trigger = loads_json(rating_revision["trigger_json"], {})
    rating_choices = loads_json(rating_revision["choices_json"], [])
    _assert(rating_trigger.get("minRatingPressure") == 32, "modern rating pressure trigger missing")
    _assert(
        any(choice.get("id") == "separate_ott_cut" for choice in rating_choices),
        "modern rating OTT cut choice missing",
    )

    _assert(sensitive_backlash is not None, "modern sensitive topic backlash event was not seeded")
    backlash_trigger = loads_json(sensitive_backlash["trigger_json"], {})
    _assert(backlash_trigger.get("minControversyRisk") == 30, "modern controversy trigger missing")


def _assert_location_event_records() -> None:
    with get_connection() as conn:
        set_event = conn.execute(
            "SELECT * FROM simulation_events WHERE id = 'event_set_build_detail_overrun'"
        ).fetchone()
        regional_event = conn.execute(
            "SELECT * FROM simulation_events WHERE id = 'event_regional_location_support_offer'"
        ).fetchone()
        overseas_event = conn.execute(
            "SELECT * FROM simulation_events WHERE id = 'event_overseas_location_permit_customs'"
        ).fetchone()
    _assert(set_event is not None, "set build location event was not seeded")
    _assert(loads_json(set_event["trigger_json"], {}).get("setBuild") is True, "set build trigger missing")
    _assert(regional_event is not None, "regional location event was not seeded")
    _assert(loads_json(regional_event["trigger_json"], {}).get("regionalLocation") is True, "regional location trigger missing")
    _assert(overseas_event is not None, "overseas location event was not seeded")
    _assert(loads_json(overseas_event["trigger_json"], {}).get("overseasLocation") is True, "overseas location trigger missing")


def _assert_scenario_event_records() -> None:
    expected = {
        "event_scenario_first_draft_diagnosis": "screenplay_development",
        "event_scenario_rewrite_crossroads": "screenplay_development",
        "event_table_reading_dialogue_gap": "casting",
        "event_investor_package_logline_gap": "fundraising",
        "event_adaptation_rights_contract_pressure": "screenplay_development",
    }
    with get_connection() as conn:
        for event_id, stage in expected.items():
            event = conn.execute("SELECT * FROM simulation_events WHERE id = ?", (event_id,)).fetchone()
            _assert(event is not None, f"scenario development event was not seeded: {event_id}")
            _assert(event["stage"] == stage, f"scenario development event stage mismatch: {event_id}")
        table_reading = conn.execute(
            "SELECT * FROM simulation_events WHERE id = 'event_table_reading_dialogue_gap'"
        ).fetchone()
        package = conn.execute(
            "SELECT * FROM simulation_events WHERE id = 'event_investor_package_logline_gap'"
        ).fetchone()
    _assert(loads_json(table_reading["trigger_json"], {}).get("minScriptDialogueWeakness") == 38, "table reading script trigger missing")
    _assert(loads_json(package["trigger_json"], {}).get("minInvestorPackageRisk") == 35, "investor package trigger missing")


def _assert_plagiarism_event_records() -> None:
    with get_connection() as conn:
        event = conn.execute(
            "SELECT * FROM simulation_events WHERE id = 'plagiarism_warning_similar_plot'"
        ).fetchone()
    _assert(event is not None, "plagiarism warning event was not seeded")
    trigger = loads_json(event["trigger_json"], {})
    choices = loads_json(event["choices_json"], [])
    _assert(trigger.get("minPlagiarismRisk") == 40, "plagiarism trigger missing")
    _assert(any(choice.get("id") == "legal_review" for choice in choices), "plagiarism legal review choice missing")


def _assert_franchise_event_records() -> None:
    with get_connection() as conn:
        event = conn.execute(
            "SELECT * FROM simulation_events WHERE id = 'franchise_sequel_offer'"
        ).fetchone()
    _assert(event is not None, "franchise sequel event was not seeded")
    _assert(event["category"] == "franchise", "franchise event category was not preserved")
    _assert(event["stage"] == "post_release", "franchise event default stage missing")
    trigger = loads_json(event["trigger_json"], {})
    choices = loads_json(event["choices_json"], [])
    _assert(trigger.get("minFinalAudience") == 2_000_000, "franchise audience trigger missing")
    _assert(trigger.get("minIpValue") == 60, "franchise IP value trigger missing")
    _assert(any(choice.get("id") == "make_direct_sequel" for choice in choices), "franchise sequel choice missing")


def _assert_player_filmography_record(film_id: str) -> None:
    state = get_player_filmography_state()
    films = state.get("films", [])
    record = next((film for film in films if film.get("filmId") == film_id), None)
    _assert(record is not None, "player filmography record was not created")
    _assert(record.get("audience") is not None, "player filmography audience missing")
    _assert("profit" in record, "player filmography profit missing")
    _assert("reviews" in record, "player filmography reviews section missing")
    _assert("collaborations" in record, "player filmography collaborations section missing")
    _assert("failureRecord" in record, "player filmography failure section missing")
    _assert("reevaluation" in record, "player filmography reevaluation section missing")
    _assert("franchise" in record, "player filmography franchise section missing")


def _assert_post_release_event_records() -> None:
    with get_connection() as conn:
        cult = conn.execute(
            "SELECT * FROM simulation_events WHERE id = 'late_cult_following'"
        ).fetchone()
        ott = conn.execute(
            "SELECT * FROM simulation_events WHERE id = 'ott_rediscovery'"
        ).fetchone()
    _assert(cult is not None, "late cult following event was not seeded")
    _assert(cult["category"] == "post_release", "post-release event category was not preserved")
    _assert(cult["stage"] == "post_release", "post-release event default stage missing")
    cult_trigger = loads_json(cult["trigger_json"], {})
    cult_effects = loads_json(cult["choices_json"], {}).get("effects", {})
    _assert(cult_trigger.get("minYearsAfterRelease") == 3, "post-release years trigger missing")
    _assert(cult_effects.get("secondary_market_revenue") == 100_000_000, "post-release revenue effect missing")

    _assert(ott is not None, "OTT rediscovery event was not seeded")
    ott_trigger = loads_json(ott["trigger_json"], {})
    ott_effects = loads_json(ott["choices_json"], {}).get("effects", {})
    _assert(ott_trigger.get("availableOnOtt") is True, "OTT availability trigger missing")
    _assert(ott_effects.get("ip_value") == 5, "OTT rediscovery IP effect missing")


def _safe_choice(choices: list[dict]) -> dict:
    for choice in choices:
        if choice.get("id") != "walk_out":
            return choice
    return choices[0]


def _first_id(rows: list[dict], preferred: str) -> str:
    for row in rows:
        if row["id"] == preferred:
            return row["id"]
    if not rows:
        raise RuntimeError("reference data missing")
    return rows[0]["id"]


def _restore_file(backup: Path, target: Path, existed: bool) -> None:
    if existed:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(backup, target)
    elif target.exists():
        target.unlink()


def _restore_save_dir(backup_dir: Path) -> None:
    SAVE_DIR.mkdir(parents=True, exist_ok=True)
    for save_file in SAVE_DIR.glob("save_*.db"):
        save_file.unlink()
    if backup_dir.exists():
        for save_file in backup_dir.glob("save_*.db"):
            shutil.copy2(save_file, SAVE_DIR / save_file.name)


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    raise SystemExit(main())
