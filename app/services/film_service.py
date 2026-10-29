from __future__ import annotations

import random
import uuid
from typing import Any

from app.database import dumps_json, get_connection, loads_json
from app.services.budget_service import (
    normalize_allocation,
    normalize_allocation_amounts,
    save_project_budget_allocations,
)
from app.services.casting_service import auto_fill_minor_cast
from app.services.economic_service import adjusted_scale_budget
from app.services.finance_service import reserve_project_financing
from app.services.game_state import clamp
from app.services.location_service import apply_location_strategy_to_stats
from app.services.distribution_service import ensure_project_distributor_match
from app.services.progression_service import (
    STAGE_LABELS,
    first_project_stage,
    next_project_stage,
    normalize_planned_shooting_days,
    stage_time_cost_days_for_project,
    sync_shooting_duration_stats,
)
from app.services.production_management_service import (
    initialize_project_operations,
    mark_project_cashflows_for_stage,
)
from app.services.rating_service import initial_content_stats
from app.services.scenario_service import enrich_script_development_stats
from app.services.version_service import initialize_project_versions


ALLOCATION_TO_STATS = {
    "scenario": "scenario_quality",
    "directing": "directing_quality",
    "actors": "acting_quality",
    "shooting": "shooting_quality",
    "art": "art_costume_prop_quality",
    "stunt": "action_stunt_quality",
    "vfx": "vfx_quality",
    "sound": "music_sound_quality",
    "editing": "editing_quality",
    "contingency": "budget_overrun_risk",
}

GENRE_WEIGHT_COLUMNS = {
    "scenario": "scenario_weight",
    "directing": "directing_weight",
    "actors": "actors_weight",
    "shooting": "shooting_weight",
    "art": "art_weight",
    "stunt": "stunt_weight",
    "vfx": "vfx_weight",
    "sound": "sound_weight",
    "editing": "editing_weight",
    "contingency": "contingency_weight",
}

def create_project(
    *,
    title: str,
    genre_id: str,
    scale_id: str,
    production_budget: int,
    marketing_budget: int,
    allocation: dict[str, int],
    allocation_amounts: dict[str, int] | None = None,
    location_strategy: str | None = None,
    shooting_duration_days: int | None = None,
    franchise_context: dict[str, Any] | None = None,
) -> str:
    project_id = f"project_{uuid.uuid4().hex[:10]}"

    project_title = title.strip()
    with get_connection() as conn:
        player = conn.execute("SELECT * FROM player_state WHERE id = 1").fetchone()
        genre = conn.execute("SELECT * FROM genres WHERE id = ?", (genre_id,)).fetchone()
        scale = conn.execute("SELECT * FROM project_scales WHERE id = ?", (scale_id,)).fetchone()
        studio = conn.execute("SELECT * FROM studio_state WHERE id = 1").fetchone()
        if not player or not genre or not scale or not studio:
            raise ValueError("프로젝트 생성에 필요한 게임 상태를 찾을 수 없습니다.")

        scale_data = adjusted_scale_budget(dict(scale), int(player["current_year"]))
        production_budget = _bounded_budget(
            production_budget,
            int(scale_data["min_budget"]),
            int(scale_data["max_budget"]),
        )
        marketing_budget = max(0, int(marketing_budget))
        if allocation_amounts:
            allocation = normalize_allocation_amounts(production_budget, allocation_amounts)
        else:
            allocation = normalize_allocation(allocation)
        initial_stage = first_project_stage(scale_id)
        stats = _generate_initial_stats(dict(genre), scale_data, production_budget, marketing_budget, allocation)
        planned_shooting_days = normalize_planned_shooting_days(scale_id, shooting_duration_days)
        sync_shooting_duration_stats(stats, scale_id, planned_days=planned_shooting_days)
        if franchise_context:
            stats["franchise_context"] = dict(franchise_context)
            stats["ip_value"] = int(franchise_context.get("ipValue", 0) or 0)
            stats["franchise_power"] = int(franchise_context.get("franchisePower", 0) or 0)
            stats["sequel_demand"] = int(franchise_context.get("sequelDemand", 0) or 0)
            stats["series_fatigue"] = int(franchise_context.get("seriesFatigue", 0) or 0)
        enrich_script_development_stats(
            stats,
            genre_id=genre_id,
            scale_id=scale_id,
            allocation=allocation,
            franchise_context=franchise_context,
        )
        stats["currency_real_value_multiplier"] = scale_data["economic_adjustment"]["currency_real_value_multiplier"]
        stats["production_cost_modifier"] = scale_data["economic_adjustment"]["production_cost_modifier"]
        stats["budget_base_year"] = scale_data["economic_adjustment"]["cpi_base_year"]
        stats["budget_year"] = int(player["current_year"])
        stats["base_year_production_budget"] = int(
            production_budget * float(scale_data["economic_adjustment"]["currency_real_value_multiplier"])
        )
        location_profile = apply_location_strategy_to_stats(
            stats,
            location_strategy or "real_location",
            production_budget=production_budget,
            scale_id=scale_id,
            genre_id=genre_id,
        )
        sync_shooting_duration_stats(stats, scale_id)
        total_cost = production_budget + marketing_budget + int(location_profile.get("costImpact", 0) or 0)
        stats["total_cost"] = total_cost

        conn.execute(
            """
            INSERT INTO projects (
                id, title, genre_id, scale_id, status, production_budget,
                marketing_budget, stage, stats_json, created_year
            ) VALUES (?, ?, ?, ?, 'in_production', ?, ?, ?, ?, ?)
            """,
            (
                project_id,
                project_title,
                genre_id,
                scale_id,
                production_budget,
                marketing_budget,
                initial_stage,
                dumps_json(stats),
                player["current_year"],
            ),
        )
        conn.execute(
            """
            INSERT INTO production_projects (
                id, title, genre_id, scale_id, status, production_budget,
                marketing_budget, stage, stats_json, created_year
            ) VALUES (?, ?, ?, ?, 'in_production', ?, ?, ?, ?, ?)
            """,
            (
                project_id,
                project_title,
                genre_id,
                scale_id,
                production_budget,
                marketing_budget,
                initial_stage,
                dumps_json(stats),
                player["current_year"],
            ),
        )
        save_project_budget_allocations(
            project_id,
            production_budget,
            allocation,
            allocation_amounts=allocation_amounts,
            conn=conn,
        )
        financing = reserve_project_financing(conn, project_id, total_cost, player, studio)
        stats.update(
            {
                "own_capital_used": int(financing["ownCapitalUsed"]),
                "investment_used": int(financing["investmentUsed"]),
                "loan_used": int(financing["loanUsed"]),
                "investment_amount": int(financing["investmentUsed"]),
            }
        )
        ensure_project_distributor_match(
            project_id,
            conn=conn,
            project={
                "id": project_id,
                "title": project_title,
                "genre_id": genre_id,
                "scale_id": scale_id,
                "production_budget": production_budget,
                "marketing_budget": marketing_budget,
                "stage": initial_stage,
                "created_year": player["current_year"],
            },
            player=dict(player),
            stats=stats,
        )
        auto_fill_minor_cast(project_id, conn=conn, stats=stats)
        conn.execute("UPDATE projects SET stats_json = ? WHERE id = ?", (dumps_json(stats), project_id))
        conn.execute("UPDATE production_projects SET stats_json = ? WHERE id = ?", (dumps_json(stats), project_id))
        _apply_location_network_effects(conn, player, location_profile)
        initialize_project_operations(
            conn,
            project_id=project_id,
            project_title=project_title,
            genre_id=genre_id,
            scale_id=scale_id,
            production_budget=production_budget,
            marketing_budget=marketing_budget,
            allocation=allocation,
            financing=financing,
            player=player,
            location_profile=location_profile,
            project_stats=stats,
        )
        initialize_project_versions(conn, project_id, scale_id, genre_id)
        conn.commit()

    from app.services.calendar_service import add_calendar_event, schedule_project_calendar

    add_calendar_event(
        title=f"{project_title}: 프로젝트 승인",
        event_type="project_created",
        project_id=project_id,
        description="기획안, 장르, 규모, 순제작비 배분이 확정되었다.",
        metadata={"genreId": genre_id, "scaleId": scale_id, "initialStage": initial_stage},
    )
    schedule_project_calendar(project_id=project_id, project_title=project_title, scale_id=scale_id, stats=stats)
    return project_id


def _apply_location_network_effects(conn: Any, player: Any, location_profile: dict[str, Any]) -> None:
    network_effects = location_profile.get("network") if isinstance(location_profile.get("network"), dict) else {}
    if not network_effects:
        return
    network = loads_json(player["network_json"], {})
    for key, value in network_effects.items():
        network[key] = clamp(float(network.get(key, 10) or 10) + float(value))
    conn.execute("UPDATE player_state SET network_json = ? WHERE id = 1", (dumps_json(network),))

def apply_event_choice(
    project_id: str,
    choice: dict[str, Any],
    event: dict[str, Any] | None = None,
) -> dict[str, Any]:
    from app.services.event_engine import apply_project_event_choice
    from app.services.event_service import get_event_for_project

    return apply_project_event_choice(project_id, event or get_event_for_project(project_id), choice)


def advance_project_stage(project_id: str) -> str:
    with get_connection() as conn:
        project = conn.execute(
            "SELECT id, title, scale_id, stage, stats_json FROM projects WHERE id = ?",
            (project_id,),
        ).fetchone()
        if not project:
            raise ValueError("진행 중인 프로젝트를 찾을 수 없습니다.")

        current_stage = project["stage"]
        next_stage = next_project_stage(project["stage"], project["scale_id"])
        if current_stage == "production_announcement" or next_stage == "production_announcement":
            from app.services.casting_service import casting_confirmation_status

            casting_status = casting_confirmation_status(project_id)
            if not casting_status["is_confirmed"]:
                raise ValueError(
                    "제작 발표회 전에는 공식 출연진 확정이 필요합니다. "
                    "캐스팅/계약 관리에서 필요한 출연진을 확정하세요."
                )
        conn.execute(
            "UPDATE projects SET stage = ? WHERE id = ?",
            (next_stage, project_id),
        )
        conn.execute(
            "UPDATE production_projects SET stage = ? WHERE id = ?",
            (next_stage, project_id),
        )
        player = conn.execute("SELECT * FROM player_state WHERE id = 1").fetchone()
        if player:
            mark_project_cashflows_for_stage(conn, project_id, next_stage, player)
        conn.commit()
    project_stats = loads_json(project["stats_json"], {})
    days = stage_time_cost_days_for_project(current_stage, project["scale_id"], project_stats)
    if days > 0:
        from app.services.calendar_service import record_project_time_spent

        record_project_time_spent(
            project_id=project_id,
            project_title=project["title"],
            stage=current_stage,
            scale_id=project["scale_id"],
            days=days,
            title=f"{STAGE_LABELS.get(current_stage, current_stage)} 진행",
            event_type="stage_progress",
            description=f"{STAGE_LABELS.get(current_stage, current_stage)} 단계가 {days}일 동안 진행되었다.",
        )
    return next_stage


def get_project(project_id: str) -> dict[str, Any] | None:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT p.*, g.name AS genre_name, s.name AS scale_name
            FROM projects p
            JOIN genres g ON g.id = p.genre_id
            JOIN project_scales s ON s.id = p.scale_id
            WHERE p.id = ?
            """,
            (project_id,),
        ).fetchone()
    if not row:
        return None
    project = dict(row)
    project["stats"] = loads_json(project.pop("stats_json"), {})
    project["distribution"] = ensure_project_distributor_match(project_id, project=project, stats=project["stats"])
    return project


def _bounded_budget(value: int, minimum: int, maximum: int) -> int:
    return min(max(int(value), minimum), maximum)


def _generate_initial_stats(
    genre: dict[str, Any],
    scale: dict[str, Any],
    production_budget: int,
    marketing_budget: int,
    allocation: dict[str, int],
) -> dict[str, int]:
    min_budget = int(scale["min_budget"])
    max_budget = int(scale["max_budget"])
    budget_position = 0.5 if max_budget == min_budget else (production_budget - min_budget) / (max_budget - min_budget)
    total_allocation = max(sum(max(0, int(value)) for value in allocation.values()), 1)

    stats: dict[str, int] = {
        "production_budget": production_budget,
        "marketing_budget": marketing_budget,
        "total_cost": production_budget + marketing_budget,
        "studio_recovery_rate": 35,
        "financial_risk": clamp(60 - budget_position * 30),
        "production_shutdown_risk": clamp(18 - budget_position * 8),
        "schedule_delay_risk": 20,
        "budget_overrun_risk": 24,
        "on_set_conflict_risk": 18,
        "plagiarism_risk": clamp(random.randint(0, 7) + (int(genre.get("plagiarism_sensitivity", 50)) - 50) / 10),
        "plagiarism_sensitivity": int(genre.get("plagiarism_sensitivity", 50)),
        "controversy_risk": random.randint(0, 8),
        "audience_rejection_risk": 20,
        "secondary_market_fit": int(genre.get("secondary_market_fit", 50)),
        "franchise_fit": int(genre.get("franchise_fit", 50)),
    }
    stats.update(initial_content_stats(str(genre.get("id", "")), controversy_risk=int(stats["controversy_risk"])))

    ideal_targets = _ideal_allocation_targets(genre)
    fit_scores: list[int] = []
    for allocation_key, stat_key in ALLOCATION_TO_STATS.items():
        chosen = max(0, int(allocation.get(allocation_key, 0))) / total_allocation * 100
        ideal = max(0.0, float(ideal_targets.get(allocation_key, 10)))
        fit = max(0.0, 1.0 - abs(chosen - ideal) / 18.0)
        if allocation_key != "contingency":
            fit_scores.append(int(fit * 100))
            stats[stat_key] = clamp(40 + budget_position * 18 + fit * 20 + random.randint(-4, 5))
        else:
            stats[stat_key] = clamp(28 - fit * 12)

    fit_average = sum(fit_scores) / max(len(fit_scores), 1)
    stats["budget_allocation_fit"] = clamp(fit_average)
    marketing_power = min(30, marketing_budget / max(production_budget, 1) * 45)
    actor_allocation = max(0, int(allocation.get("actors", 0))) / total_allocation * 100
    stats["casting_fit"] = clamp(stats.get("acting_quality", 50) * 0.7 + actor_allocation * 0.6)
    stats["genre_satisfaction"] = clamp(35 + fit_average * 0.28 + budget_position * 14)
    stats["pre_release_interest"] = clamp(22 + marketing_power + actor_allocation * 0.25 + budget_position * 16)
    stats["reservation_rate"] = clamp(stats["pre_release_interest"] * 0.55 + marketing_power * 0.45)
    stats["word_of_mouth"] = clamp((stats["scenario_quality"] + stats["acting_quality"] + stats["genre_satisfaction"]) / 3)
    stats["online_buzz"] = clamp(stats["pre_release_interest"] * 0.6 + marketing_power * 0.8)
    return stats


def _ideal_allocation_targets(genre: dict[str, Any]) -> dict[str, float]:
    weights = {
        key: max(0.0, float(genre.get(column, 0) or 0))
        for key, column in GENRE_WEIGHT_COLUMNS.items()
    }
    total = sum(weights.values()) or 1.0
    return {key: value / total * 100 for key, value in weights.items()}
