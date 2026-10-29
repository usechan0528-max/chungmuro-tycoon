from __future__ import annotations

import uuid
from typing import Any

from app.database import dumps_json, get_connection, loads_json
from app.services.calendar_service import add_days_to_date, current_game_date
from app.services.game_state import money
from app.services.progression_service import STAGE_LABELS, get_stage_flow_for_scale, stage_time_cost_days_for_project
from app.services.scenario_service import scenario_development_plan, status_label as scenario_status_label


SCALE_ORDER = {
    "scale_short": 0,
    "scale_independent": 1,
    "scale_low_budget_genre": 2,
    "scale_mid_commercial": 3,
    "scale_large_commercial": 4,
    "scale_tentpole": 5,
}

CREW_ROLE_TEMPLATES = (
    {"id": "producer", "name": "프로듀서", "department": "제작", "minScale": "scale_short", "share": 0.022, "seniority": "lead"},
    {"id": "line_producer", "name": "라인 프로듀서", "department": "제작", "minScale": "scale_independent", "share": 0.018, "seniority": "lead"},
    {"id": "assistant_director", "name": "조감독", "department": "연출", "minScale": "scale_short", "share": 0.014, "seniority": "mid"},
    {"id": "script_supervisor", "name": "스크립터", "department": "연출", "minScale": "scale_low_budget_genre", "share": 0.008, "seniority": "mid"},
    {"id": "cinematographer", "name": "촬영감독", "department": "촬영", "minScale": "scale_short", "share": 0.026, "seniority": "lead"},
    {"id": "gaffer", "name": "조명감독", "department": "조명", "minScale": "scale_independent", "share": 0.018, "seniority": "lead"},
    {"id": "production_designer", "name": "미술감독", "department": "미술", "minScale": "scale_low_budget_genre", "share": 0.022, "seniority": "lead"},
    {"id": "costume_designer", "name": "의상감독", "department": "의상", "minScale": "scale_mid_commercial", "share": 0.011, "seniority": "mid"},
    {"id": "sound_mixer", "name": "동시녹음", "department": "음향", "minScale": "scale_short", "share": 0.012, "seniority": "mid"},
    {"id": "editor", "name": "편집감독", "department": "후반", "minScale": "scale_short", "share": 0.017, "seniority": "lead"},
    {"id": "music_director", "name": "음악감독", "department": "후반", "minScale": "scale_independent", "share": 0.014, "seniority": "lead"},
    {"id": "vfx_supervisor", "name": "VFX 슈퍼바이저", "department": "VFX", "minScale": "scale_mid_commercial", "share": 0.018, "seniority": "lead"},
    {"id": "stunt_coordinator", "name": "무술감독", "department": "액션", "minScale": "scale_low_budget_genre", "share": 0.015, "seniority": "lead"},
    {"id": "marketing_lead", "name": "마케팅 실장", "department": "마케팅", "minScale": "scale_low_budget_genre", "share": 0.010, "seniority": "lead"},
    {"id": "distribution_manager", "name": "배급 실무 담당", "department": "배급", "minScale": "scale_mid_commercial", "share": 0.008, "seniority": "mid"},
)

SHOOTING_STAGE_ALIASES = {
    "shooting",
    "short_production",
    "indie_production",
    "production",
    "large_shooting",
    "large_scale_production",
}

POST_STAGE_ALIASES = {"post_production", "vfx_post_production", "editing"}
MARKETING_STAGE_ALIASES = {"marketing", "large_marketing"}
RELEASE_STAGE_ALIASES = {"release_strategy", "special_format_strategy", "premium_format_strategy", "release"}


def initialize_project_operations(
    conn: Any,
    *,
    project_id: str,
    project_title: str,
    genre_id: str,
    scale_id: str,
    production_budget: int,
    marketing_budget: int,
    allocation: dict[str, int],
    financing: dict[str, Any],
    player: Any,
    location_profile: dict[str, Any] | None = None,
    project_stats: dict[str, Any] | None = None,
) -> None:
    _reset_project_operations(conn, project_id)
    project_stats = project_stats or {}
    stage_dates = _stage_date_map(scale_id, _player_date(player), project_stats)
    _create_scenario_development_plan(conn, project_id, project_title, genre_id, scale_id, stage_dates)
    _create_crew_roles(conn, project_id, scale_id, int(production_budget), allocation)
    location_profile = location_profile or {}
    _create_location_plan(conn, project_id, project_title, scale_id, stage_dates, location_profile)
    _create_shooting_schedule(
        conn,
        project_id,
        project_title,
        genre_id,
        scale_id,
        stage_dates,
        location_profile,
        project_stats,
    )
    _create_cashflow_plan(
        conn,
        project_id=project_id,
        project_title=project_title,
        scale_id=scale_id,
        production_budget=int(production_budget),
        marketing_budget=int(marketing_budget),
        stage_dates=stage_dates,
        financing=financing,
        location_profile=location_profile,
    )
    _create_marketing_asset_plan(conn, project_id, project_title, scale_id, stage_dates)
    initial_stage = get_stage_flow_for_scale(scale_id)[0]
    mark_project_cashflows_for_stage(conn, project_id, initial_stage, player)


def get_project_operations_state(project_id: str) -> dict[str, Any]:
    with get_connection() as conn:
        crew = conn.execute(
            """
            SELECT *
            FROM project_crew_roles
            WHERE project_id = ?
            ORDER BY required DESC, department, role_name
            """,
            (project_id,),
        ).fetchall()
        shooting = conn.execute(
            """
            SELECT *
            FROM shooting_schedule_blocks
            WHERE project_id = ?
            ORDER BY sequence, start_year, start_month, start_day
            """,
            (project_id,),
        ).fetchall()
        locations = conn.execute(
            """
            SELECT *
            FROM project_location_plans
            WHERE project_id = ?
            ORDER BY created_at, id
            """,
            (project_id,),
        ).fetchall()
        cashflows = conn.execute(
            """
            SELECT *
            FROM project_cashflows
            WHERE project_id = ?
            ORDER BY planned_year, planned_month, planned_day, created_at
            """,
            (project_id,),
        ).fetchall()
        screenings = conn.execute(
            """
            SELECT *
            FROM test_screenings
            WHERE project_id = ?
            ORDER BY year, month, day, created_at
            """,
            (project_id,),
        ).fetchall()
        reshoots = conn.execute(
            """
            SELECT *
            FROM reshoot_orders
            WHERE project_id = ?
            ORDER BY year, month, day, created_at
            """,
            (project_id,),
        ).fetchall()
        marketing_assets = conn.execute(
            """
            SELECT *
            FROM marketing_assets
            WHERE project_id = ?
            ORDER BY planned_year, planned_month, planned_day, created_at
            """,
            (project_id,),
        ).fetchall()
        marketing_reactions = conn.execute(
            """
            SELECT mr.*, ma.asset_type
            FROM marketing_reactions mr
            LEFT JOIN marketing_assets ma ON ma.id = mr.asset_id
            WHERE mr.project_id = ?
            ORDER BY mr.year, mr.month, mr.day, mr.created_at
            """,
            (project_id,),
        ).fetchall()
        stage_greetings = conn.execute(
            """
            SELECT *
            FROM stage_greeting_schedules
            WHERE project_id = ?
            ORDER BY year, month, day, created_at
            """,
            (project_id,),
        ).fetchall()
        contracts = conn.execute(
            """
            SELECT pp.*, p.name_ko, p.type
            FROM project_people pp
            LEFT JOIN people p ON p.id = pp.person_id
            WHERE pp.project_id = ?
            ORDER BY pp.role, p.name_ko
            """,
            (project_id,),
        ).fetchall()
        versions = conn.execute(
            """
            SELECT *
            FROM project_versions
            WHERE project_id = ?
            ORDER BY
                CASE version_type
                    WHEN 'theatrical_cut' THEN 1
                    WHEN 'director_cut' THEN 2
                    WHEN 'ott_cut' THEN 3
                    ELSE 9
                END
            """,
            (project_id,),
        ).fetchall()
        scenario_rows = conn.execute(
            """
            SELECT *
            FROM project_scenario_development
            WHERE project_id = ?
            ORDER BY sequence, start_year, start_month, start_day
            """,
            (project_id,),
        ).fetchall()
    scenario_development_rows = [_scenario_from_row(dict(row)) for row in scenario_rows]
    crew_rows = [_crew_from_row(dict(row)) for row in crew]
    contract_rows = [_contract_from_row(dict(row)) for row in contracts]
    version_rows = [_version_from_row(dict(row)) for row in versions]
    location_rows = [_location_from_row(dict(row)) for row in locations]
    shooting_rows = [_shooting_from_row(dict(row)) for row in shooting]
    cashflow_rows = [_cashflow_from_row(dict(row)) for row in cashflows]
    screening_rows = [_screening_from_row(dict(row)) for row in screenings]
    reshoot_rows = [_reshoot_from_row(dict(row)) for row in reshoots]
    marketing_asset_rows = [_marketing_asset_from_row(dict(row)) for row in marketing_assets]
    marketing_reaction_rows = [_marketing_reaction_from_row(dict(row)) for row in marketing_reactions]
    stage_greeting_rows = [_stage_greeting_from_row(dict(row)) for row in stage_greetings]
    return {
        "crew": crew_rows,
        "contracts": contract_rows,
        "versions": version_rows,
        "scenarioDevelopment": scenario_development_rows,
        "locations": location_rows,
        "shootingSchedule": shooting_rows,
        "cashflows": cashflow_rows,
        "testScreenings": screening_rows,
        "reshoots": reshoot_rows,
        "marketingAssets": marketing_asset_rows,
        "marketingReactions": marketing_reaction_rows,
        "stageGreetings": stage_greeting_rows,
        "summary": _operations_summary(
            scenario_development_rows,
            crew_rows,
            contract_rows,
            version_rows,
            location_rows,
            shooting_rows,
            cashflow_rows,
            screening_rows,
            reshoot_rows,
            marketing_asset_rows,
            marketing_reaction_rows,
            stage_greeting_rows,
        ),
    }


def mark_project_cashflows_for_stage(conn: Any, project_id: str, stage: str, player: Any) -> int:
    rows = conn.execute(
        """
        SELECT *
        FROM project_cashflows
        WHERE project_id = ? AND status = 'planned' AND planned_stage = ?
        ORDER BY planned_year, planned_month, planned_day, created_at
        """,
        (project_id, stage),
    ).fetchall()
    if not rows:
        return 0
    player_date = _player_date(player)
    paid_total = 0
    for row in rows:
        conn.execute(
            """
            UPDATE project_cashflows
            SET status = 'paid', paid_year = ?, paid_month = ?, paid_day = ?
            WHERE id = ?
            """,
            (*player_date, row["id"]),
        )
        conn.execute(
            """
            INSERT INTO finance_transactions (
                year, month, day, transaction_type, amount, source, target,
                project_id, description, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                player_date[0],
                player_date[1],
                player_date[2],
                "project_cashflow_disbursement",
                -int(row["amount"] or 0),
                row["source"],
                row["target"],
                project_id,
                row["description"] or "프로젝트 예산이 해당 단계에 집행되었다.",
                row["metadata_json"] or dumps_json({}),
            ),
        )
        paid_total += int(row["amount"] or 0)
    return paid_total


def apply_production_management_effects(
    conn: Any,
    *,
    project_id: str,
    project: Any,
    player: Any,
    event: dict[str, Any] | None,
    choice: dict[str, Any],
    effects: dict[str, Any],
    stats: dict[str, Any],
) -> dict[str, int]:
    flags = effects.get("flags", {}) if isinstance(effects, dict) else {}
    if not isinstance(flags, dict):
        return {"productionBudgetDelta": 0, "marketingBudgetDelta": 0, "studioCashDelta": 0}
    project_title = project["title"] if hasattr(project, "keys") else str(project.get("title", "프로젝트"))
    player_date = _player_date(player)
    budget_delta = 0
    marketing_budget_delta = 0
    studio_cash_delta = 0

    if flags.get("testScreening"):
        _create_test_screening(conn, project_id, player_date, event, choice, effects, flags)

    marketing_reactions = flags.get("marketingReaction")
    if marketing_reactions:
        for reaction in _as_list(marketing_reactions):
            if isinstance(reaction, dict):
                _create_marketing_reaction(conn, project_id, player_date, event, choice, effects, reaction)

    announcements = flags.get("pressAnnouncement") or flags.get("productionAnnouncement")
    if announcements:
        for announcement in _as_list(announcements):
            if not isinstance(announcement, dict):
                continue
            cost = _create_production_announcement(
                conn,
                project_id,
                project_title,
                player_date,
                event,
                choice,
                effects,
                announcement,
            )
            if cost > 0:
                marketing_budget_delta += cost
                studio_cash_delta -= cost
                _increase_project_financing_total(
                    conn,
                    project_id,
                    cost,
                    reason=str(announcement.get("reason") or "제작 발표회/언론 공개 비용"),
                )
                _insert_paid_cashflow(
                    conn,
                    project_id,
                    player_date,
                    amount=cost,
                    target="production_announcement",
                    cashflow_type="announcement_cost",
                    description=str(announcement.get("cashflowDescription") or "제작 발표회와 언론 공개 비용 집행"),
                    metadata={"eventId": (event or {}).get("id"), "choiceId": choice.get("id")},
                    planned_stage=str(project["stage"] or "production_announcement"),
                )

    stage_greetings = flags.get("stageGreeting")
    if stage_greetings:
        for greeting in _as_list(stage_greetings):
            if not isinstance(greeting, dict):
                continue
            cost = _create_stage_greeting_schedule(conn, project_id, project_title, player_date, event, choice, greeting)
            if cost > 0:
                marketing_budget_delta += cost
                studio_cash_delta -= cost
                _increase_project_financing_total(conn, project_id, cost, reason=str(greeting.get("reason") or "무대인사/팬 이벤트 비용"))
                _insert_paid_cashflow(
                    conn,
                    project_id,
                    add_days_to_date(player_date, int(greeting.get("daysOffset", 0) or 0)),
                    amount=cost,
                    target="stage_greeting",
                    cashflow_type="stage_greeting_cost",
                    description=str(greeting.get("description") or "무대인사 일정 운영비 집행"),
                    metadata={"eventId": (event or {}).get("id"), "choiceId": choice.get("id")},
                    planned_stage="post_release",
                )

    if flags.get("createReshoot"):
        days = max(1, int(flags.get("reshootDays") or 5))
        cost = max(0, int(flags.get("reshootCost") or _default_reshoot_cost(project, days)))
        budget_delta += cost
        studio_cash_delta -= cost
        _create_reshoot_order(conn, project_id, project_title, player_date, days, cost, event, choice, flags)
        _increase_project_financing_total(conn, project_id, cost, reason=str(flags.get("reshootReason") or choice.get("text") or "재촬영 비용"))
        stats["production_budget"] = int(stats.get("production_budget", project["production_budget"]) or 0) + cost
        stats["total_cost"] = int(stats.get("total_cost", 0) or 0) + cost
        stats["budget_overrun_risk"] = min(100, int(stats.get("budget_overrun_risk", 20) or 20) + 5)

    crew_changes = flags.get("crewAdjustments")
    if isinstance(crew_changes, list):
        _apply_crew_adjustments(conn, project_id, crew_changes)

    if flags.get("extendShootingSchedule"):
        days = max(1, int(flags.get("extraShootingDays") or 3))
        _create_extra_shooting_block(
            conn,
            project_id,
            project_title,
            player_date,
            days,
            reason=str(flags.get("scheduleReason") or (event or {}).get("title") or "추가 촬영 일정"),
            metadata={"eventId": (event or {}).get("id"), "choiceId": choice.get("id")},
        )

    return {
        "productionBudgetDelta": budget_delta,
        "marketingBudgetDelta": marketing_budget_delta,
        "studioCashDelta": studio_cash_delta,
    }


def _reset_project_operations(conn: Any, project_id: str) -> None:
    for table in (
        "project_crew_roles",
        "project_scenario_development",
        "project_location_plans",
        "shooting_schedule_blocks",
        "project_cashflows",
        "test_screenings",
        "reshoot_orders",
        "marketing_assets",
        "marketing_reactions",
        "stage_greeting_schedules",
    ):
        conn.execute(f"DELETE FROM {table} WHERE project_id = ?", (project_id,))
    conn.execute(
        """
        DELETE FROM calendar_events
        WHERE project_id = ? AND event_type IN (
            'shooting_block', 'project_cashflow_due', 'reshoot',
            'marketing_asset_release', 'production_announcement',
            'first_image_reveal', 'stage_greeting', 'location_plan',
            'scenario_development'
        )
        """,
        (project_id,),
    )


def _create_crew_roles(
    conn: Any,
    project_id: str,
    scale_id: str,
    production_budget: int,
    allocation: dict[str, int],
) -> None:
    project_rank = SCALE_ORDER.get(scale_id, 2)
    for template in CREW_ROLE_TEMPLATES:
        if project_rank < SCALE_ORDER.get(str(template["minScale"]), 0):
            continue
        role_id = str(template["id"])
        allocation_hint = _allocation_hint_for_role(role_id, allocation)
        fee = int(production_budget * float(template["share"]) * allocation_hint)
        required = 0 if role_id in {"vfx_supervisor", "stunt_coordinator", "distribution_manager"} and fee <= 0 else 1
        conn.execute(
            """
            INSERT OR REPLACE INTO project_crew_roles (
                project_id, role_id, role_name, department, required, filled_status,
                seniority, estimated_fee, contribution_json, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                project_id,
                role_id,
                template["name"],
                template["department"],
                required,
                "planned",
                template["seniority"],
                fee,
                dumps_json({"allocationHint": allocation_hint}),
                "예산 배분과 규모를 기준으로 산정한 기본 제작진 포지션.",
            ),
        )


def _stage_date_map(
    scale_id: str,
    start_date: tuple[int, int, int],
    stats: dict[str, Any] | None = None,
) -> dict[str, tuple[tuple[int, int, int], tuple[int, int, int]]]:
    result: dict[str, tuple[tuple[int, int, int], tuple[int, int, int]]] = {}
    cursor = start_date
    stats = stats or {}
    for stage in get_stage_flow_for_scale(scale_id):
        days = stage_time_cost_days_for_project(stage, scale_id, stats)
        end = add_days_to_date(cursor, days)
        result[stage] = (cursor, end)
        cursor = end
    return result


def _create_scenario_development_plan(
    conn: Any,
    project_id: str,
    project_title: str,
    genre_id: str,
    scale_id: str,
    stage_dates: dict[str, tuple[tuple[int, int, int], tuple[int, int, int]]],
) -> None:
    project = conn.execute("SELECT stats_json FROM projects WHERE id = ?", (project_id,)).fetchone()
    stats = loads_json(project["stats_json"], {}) if project else {}
    franchise_context = stats.get("franchise_context") if isinstance(stats.get("franchise_context"), dict) else None
    for step in scenario_development_plan(
        stats=stats,
        genre_id=genre_id,
        scale_id=scale_id,
        franchise_context=franchise_context,
    ):
        stage = _first_existing_stage(stage_dates, step["stageCandidates"]) or next(iter(stage_dates))
        stage_start, _stage_end = stage_dates[stage]
        offset = max(0, int(step.get("sequence", 10) or 10) // 10 - 1) * 2
        start = add_days_to_date(stage_start, offset)
        end = add_days_to_date(start, max(0, int(step.get("durationDays", 1) or 1) - 1))
        step_id = f"script_{uuid.uuid4().hex[:10]}"
        diagnosis = str(step.get("diagnosis") or "")
        risk_note = str(step.get("riskNote") or "")
        conn.execute(
            """
            INSERT OR REPLACE INTO project_scenario_development (
                id, project_id, sequence, step_id, step_name, planned_stage,
                start_year, start_month, start_day, end_year, end_month, end_day,
                status, diagnosis_label, diagnosis_text, risk_note,
                suggested_action, internal_metrics_json, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                step_id,
                project_id,
                int(step["sequence"]),
                str(step["stepId"]),
                str(step["stepName"]),
                stage,
                start[0], start[1], start[2],
                end[0], end[1], end[2],
                str(step.get("status") or "planned"),
                str(step.get("stepName") or "시나리오"),
                diagnosis,
                risk_note,
                str(step.get("suggestedAction") or ""),
                dumps_json(step.get("metrics") or {}),
                dumps_json({"scaleId": scale_id, "genreId": genre_id}),
            ),
        )
        _insert_calendar_event(
            conn,
            title=f"{project_title}: {step['stepName']}",
            event_type="scenario_development",
            start=start,
            end=end,
            project_id=project_id,
            description=f"{diagnosis} {risk_note}".strip(),
            metadata={"scenarioStepId": step_id, "stepId": step["stepId"], "stage": stage},
        )


def _create_location_plan(
    conn: Any,
    project_id: str,
    project_title: str,
    scale_id: str,
    stage_dates: dict[str, tuple[tuple[int, int, int], tuple[int, int, int]]],
    location_profile: dict[str, Any],
) -> None:
    if not location_profile:
        return
    stats = location_profile.get("stats") if isinstance(location_profile.get("stats"), dict) else {}
    network = location_profile.get("network") if isinstance(location_profile.get("network"), dict) else {}
    location_id = f"location_{uuid.uuid4().hex[:10]}"
    conn.execute(
        """
        INSERT INTO project_location_plans (
            id, project_id, location_strategy, location_name, location_type,
            cost_impact, quality_delta, permit_risk_delta, regional_network_delta,
            duration_delta_days, status, description, metadata_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'selected', ?, ?)
        """,
        (
            location_id,
            project_id,
            str(location_profile.get("id") or "real_location"),
            str(location_profile.get("name") or "실제 장소 촬영"),
            str(location_profile.get("locationType") or "로케이션"),
            int(location_profile.get("costImpact") or 0),
            int(stats.get("shooting_quality", 0) or 0),
            int(stats.get("location_permit_risk", 0) or 0),
            int(network.get("regional_network", 0) or 0),
            int(location_profile.get("durationDeltaDays") or 0),
            str(location_profile.get("description") or ""),
            dumps_json(
                {
                    "scaleId": scale_id,
                    "impactLine": location_profile.get("impactLine"),
                    "stats": stats,
                    "network": network,
                    "flags": location_profile.get("flags") or {},
                }
            ),
        ),
    )
    stage = _first_existing_stage(stage_dates, ["pre_production", "large_pre_production", "planning"]) or next(iter(stage_dates))
    start, _end = stage_dates[stage]
    _insert_calendar_event(
        conn,
        title=f"{project_title}: {location_profile.get('name', '로케이션 전략')} 확정",
        event_type="location_plan",
        start=start,
        end=start,
        project_id=project_id,
        description=str(location_profile.get("impactLine") or location_profile.get("description") or "로케이션 전략이 확정되었다."),
        metadata={"locationPlanId": location_id, "strategy": location_profile.get("id"), "stage": stage},
    )


def _create_shooting_schedule(
    conn: Any,
    project_id: str,
    project_title: str,
    genre_id: str,
    scale_id: str,
    stage_dates: dict[str, tuple[tuple[int, int, int], tuple[int, int, int]]],
    location_profile: dict[str, Any],
    project_stats: dict[str, Any] | None = None,
) -> None:
    shooting_stage = next((stage for stage in stage_dates if stage in SHOOTING_STAGE_ALIASES), None)
    if not shooting_stage:
        return
    start, _end = stage_dates[shooting_stage]
    total_days = max(1, stage_time_cost_days_for_project(shooting_stage, scale_id, project_stats or {}))
    blocks = _shooting_blocks_for_genre(genre_id, total_days, location_profile)
    cursor = start
    for sequence, block in enumerate(blocks, start=1):
        days = max(1, int(block["days"]))
        end = add_days_to_date(cursor, max(0, days - 1))
        block_id = f"shoot_{uuid.uuid4().hex[:10]}"
        conn.execute(
            """
            INSERT INTO shooting_schedule_blocks (
                id, project_id, sequence, stage, start_year, start_month, start_day,
                end_year, end_month, end_day, unit_name, location_type,
                planned_days, status, description, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'planned', ?, ?)
            """,
            (
                block_id,
                project_id,
                sequence,
                shooting_stage,
                cursor[0], cursor[1], cursor[2],
                end[0], end[1], end[2],
                block["unit"],
                block["location"],
                days,
                block["description"],
                dumps_json({"genreId": genre_id, "scaleId": scale_id, "locationStrategy": location_profile.get("id")}),
            ),
        )
        _insert_calendar_event(
            conn,
            title=f"{project_title}: {block['unit']}",
            event_type="shooting_block",
            start=cursor,
            end=end,
            project_id=project_id,
            description=block["description"],
            metadata={"shootingBlockId": block_id, "stage": shooting_stage, "plannedDays": days},
        )
        cursor = add_days_to_date(end, 1)


def _create_cashflow_plan(
    conn: Any,
    *,
    project_id: str,
    project_title: str,
    scale_id: str,
    production_budget: int,
    marketing_budget: int,
    stage_dates: dict[str, tuple[tuple[int, int, int], tuple[int, int, int]]],
    financing: dict[str, Any],
    location_profile: dict[str, Any],
) -> None:
    items = _cashflow_items(scale_id, production_budget, marketing_budget, location_profile)
    total = max(1, production_budget + marketing_budget + int(location_profile.get("costImpact") or 0))
    for item in items:
        stage = _first_existing_stage(stage_dates, item["stageCandidates"]) or next(iter(stage_dates))
        start, _end = stage_dates[stage]
        amount = int(item["amount"])
        if amount <= 0:
            continue
        cashflow_id = f"cashflow_{uuid.uuid4().hex[:10]}"
        metadata = {
            "stageLabel": STAGE_LABELS.get(stage, stage),
            "fundingMix": _funding_mix(amount, total, financing),
        }
        conn.execute(
            """
            INSERT INTO project_cashflows (
                id, project_id, planned_stage, planned_year, planned_month, planned_day,
                due_year, due_month, due_day, amount, source, target,
                cashflow_type, status, description, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'planned', ?, ?)
            """,
            (
                cashflow_id,
                project_id,
                stage,
                start[0], start[1], start[2],
                start[0], start[1], start[2],
                amount,
                "reserved_project_funds",
                item["target"],
                item["type"],
                item["description"],
                dumps_json(metadata),
            ),
        )
        _insert_calendar_event(
            conn,
            title=f"{project_title}: {item['title']}",
            event_type="project_cashflow_due",
            start=start,
            end=start,
            project_id=project_id,
            description=f"{item['description']} 예상 집행액 {money(amount)}.",
            metadata={"cashflowId": cashflow_id, "stage": stage, "amount": amount, **metadata},
        )


def _cashflow_items(
    scale_id: str,
    production_budget: int,
    marketing_budget: int,
    location_profile: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    larger = SCALE_ORDER.get(scale_id, 2) >= SCALE_ORDER["scale_mid_commercial"]
    location_profile = location_profile or {}
    location_cost = int(location_profile.get("costImpact") or 0)
    items = [
        {
            "title": "기획개발비 집행",
            "stageCandidates": ["planning", "development", "ip_development", "screenplay_development", "funding_simple"],
            "amount": int(production_budget * (0.08 if larger else 0.10)),
            "target": "development",
            "type": "development_cost",
            "description": "각본, 자료조사, 패키징 초기비용 집행",
        },
        {
            "title": "캐스팅/계약금 집행",
            "stageCandidates": ["casting", "star_casting", "casting_simple"],
            "amount": int(production_budget * (0.15 if larger else 0.12)),
            "target": "cast_and_key_staff",
            "type": "contract_deposit",
            "description": "주요 배우와 핵심 제작진 계약금 집행",
        },
        {
            "title": "프리프로덕션 집행",
            "stageCandidates": ["pre_production", "large_pre_production"],
            "amount": int(production_budget * (0.17 if larger else 0.15)),
            "target": "pre_production",
            "type": "pre_production_cost",
            "description": "로케이션, 미술 준비, 장비 예약 비용 집행",
        },
        {
            "title": "본촬영비 집행",
            "stageCandidates": ["shooting", "short_production", "indie_production", "production", "large_shooting", "large_scale_production"],
            "amount": int(production_budget * (0.40 if larger else 0.42)),
            "target": "shooting_unit",
            "type": "principal_photography",
            "description": "촬영 회차, 스태프 인건비, 장비/로케이션 비용 집행",
        },
        {
            "title": "후반작업비 집행",
            "stageCandidates": ["post_production", "vfx_post_production", "editing"],
            "amount": max(0, production_budget - int(production_budget * (0.08 if larger else 0.10)) - int(production_budget * (0.15 if larger else 0.12)) - int(production_budget * (0.17 if larger else 0.15)) - int(production_budget * (0.40 if larger else 0.42))),
            "target": "post_production",
            "type": "post_production_cost",
            "description": "편집, 사운드, 색보정, VFX 비용 집행",
        },
        {
            "title": "마케팅 1차 집행",
            "stageCandidates": ["marketing", "large_marketing"],
            "amount": int(marketing_budget * 0.70),
            "target": "marketing",
            "type": "marketing_spend",
            "description": "예고편, 언론, 온라인, 옥외 광고 비용 집행",
        },
        {
            "title": "개봉주 배급/홍보 집행",
            "stageCandidates": ["release_strategy", "special_format_strategy", "premium_format_strategy", "release", "festival_or_online", "limited_release"],
            "amount": max(0, marketing_budget - int(marketing_budget * 0.70)),
            "target": "release_campaign",
            "type": "release_spend",
            "description": "개봉 직전 배급/홍보와 현장 이벤트 비용 집행",
        },
    ]
    if location_cost > 0:
        items.insert(
            3,
            {
                "title": f"{location_profile.get('name', '로케이션 전략')} 비용 집행",
                "stageCandidates": ["pre_production", "large_pre_production", "planning"],
                "amount": location_cost,
                "target": "location_unit",
                "type": "location_strategy_cost",
                "description": str(location_profile.get("impactLine") or "로케이션/세트 전략에 따른 추가 비용 집행"),
            },
        )
    return items


def _create_marketing_asset_plan(
    conn: Any,
    project_id: str,
    project_title: str,
    scale_id: str,
    stage_dates: dict[str, tuple[tuple[int, int, int], tuple[int, int, int]]],
) -> None:
    for template in _marketing_asset_templates(scale_id):
        stage = _first_existing_stage(stage_dates, template["stageCandidates"]) or next(iter(stage_dates))
        start, _end = stage_dates[stage]
        planned = add_days_to_date(start, int(template["offsetDays"]))
        asset_id = f"asset_{uuid.uuid4().hex[:10]}"
        conn.execute(
            """
            INSERT INTO marketing_assets (
                id, project_id, asset_type, planned_stage, planned_year, planned_month, planned_day,
                channel, status, result_summary, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'planned', ?, ?)
            """,
            (
                asset_id,
                project_id,
                template["assetType"],
                stage,
                planned[0], planned[1], planned[2],
                template["channel"],
                template["summary"],
                dumps_json({"stageLabel": STAGE_LABELS.get(stage, stage), "scaleId": scale_id}),
            ),
        )
        event_type = str(template.get("eventType") or "marketing_asset_release")
        _insert_calendar_event(
            conn,
            title=f"{project_title}: {_asset_type_label(template['assetType'])} 공개 예정",
            event_type=event_type,
            start=planned,
            end=planned,
            project_id=project_id,
            description=template["summary"],
            metadata={"assetId": asset_id, "assetType": template["assetType"], "stage": stage},
        )


def _marketing_asset_templates(scale_id: str) -> list[dict[str, Any]]:
    rank = SCALE_ORDER.get(scale_id, 2)
    base = [
        {
            "assetType": "first_image",
            "stageCandidates": [
                "production_announcement",
                "marketing",
                "large_marketing",
                "festival",
                "festival_or_online",
                "release_strategy",
            ],
            "offsetDays": 1,
            "channel": "press_online",
            "summary": "첫 이미지 공개로 영화의 톤, 배우의 캐릭터 인상, 장르 분위기를 처음 드러낸다.",
            "eventType": "first_image_reveal",
        },
        {
            "assetType": "still_cut",
            "stageCandidates": ["marketing", "large_marketing", "festival", "release_strategy", "festival_or_online"],
            "offsetDays": 0,
            "channel": "press_online",
            "summary": "첫 스틸컷 공개로 영화의 톤과 배우 이미지를 전달한다.",
        },
        {
            "assetType": "main_poster",
            "stageCandidates": ["marketing", "large_marketing", "release_strategy", "festival_or_online"],
            "offsetDays": 5,
            "channel": "poster_press_online",
            "summary": "메인 포스터 공개로 장르와 카피 반응을 확인한다.",
        },
    ]
    if rank >= SCALE_ORDER["scale_mid_commercial"]:
        base.insert(
            0,
            {
                "assetType": "production_announcement",
                "stageCandidates": ["production_announcement", "large_marketing", "marketing"],
                "offsetDays": 0,
                "channel": "press_conference",
                "summary": "주요 캐스팅과 제작 의도를 공개하는 제작 발표회. 언론, 투자자, 팬덤의 첫 공식 반응을 만든다.",
                "eventType": "production_announcement",
            },
        )
    if rank >= SCALE_ORDER["scale_low_budget_genre"]:
        base.append(
            {
                "assetType": "main_trailer",
                "stageCandidates": ["marketing", "large_marketing", "release_strategy"],
                "offsetDays": 10,
                "channel": "trailer_online_theater",
                "summary": "메인 예고편 공개로 예매 전 온라인 반응을 확인한다.",
            }
        )
    if rank >= SCALE_ORDER["scale_large_commercial"]:
        base.insert(
            2,
            {
                "assetType": "teaser_trailer",
                "stageCandidates": ["large_marketing", "marketing"],
                "offsetDays": 3,
                "channel": "trailer_online",
                "summary": "티저 예고편으로 대형 프로젝트의 첫 인상을 만든다.",
            },
        )
    return base


def _create_production_announcement(
    conn: Any,
    project_id: str,
    project_title: str,
    player_date: tuple[int, int, int],
    event: dict[str, Any] | None,
    choice: dict[str, Any],
    effects: dict[str, Any],
    announcement: dict[str, Any],
) -> int:
    cost = max(0, int(announcement.get("cost", announcement.get("estimatedCost", 0)) or 0))
    asset_type = str(announcement.get("assetType") or "production_announcement")
    reaction = {
        "assetType": asset_type,
        "channel": announcement.get("channel") or "press_conference",
        "reactionType": announcement.get("reactionType") or "production_announcement",
        "sentimentBand": announcement.get("sentimentBand") or "mixed",
        "buzzScore": announcement.get("buzzScore", 55),
        "resultSummary": announcement.get("resultSummary") or choice.get("resultText") or "제작 발표가 언론에 공개되었다.",
        "pressSummary": announcement.get("pressSummary") or announcement.get("body") or "",
        "onlineSummary": announcement.get("onlineSummary") or announcement.get("body") or "",
        "audienceSummary": announcement.get("audienceSummary") or "",
    }
    _create_marketing_reaction(conn, project_id, player_date, event, choice, effects, reaction)

    title = str(announcement.get("title") or f"'{project_title}' 제작 발표")
    body = str(
        announcement.get("body")
        or announcement.get("pressSummary")
        or "주요 제작진과 캐스팅, 제작 방향이 공개되며 업계의 관심을 받기 시작했다."
    )
    effects_json = dumps_json({key: value for key, value in effects.items() if key != "flags"})
    conn.execute(
        """
        INSERT INTO news_items (
            year, month, day, title, body, source_type, target_type,
            target_id, importance, reaction_json, effects_json
        ) VALUES (?, ?, ?, ?, ?, 'press', 'project', ?, ?, ?, ?)
        """,
        (
            player_date[0],
            player_date[1],
            player_date[2],
            title,
            body,
            project_id,
            int(announcement.get("importance", 62) or 62),
            dumps_json(_announcement_reactions(announcement)),
            effects_json,
        ),
    )
    conn.execute(
        """
        INSERT INTO systems_press (
            year, month, title, body, source_type, target_type,
            target_id, effects_json
        ) VALUES (?, ?, ?, ?, 'press', 'project', ?, ?)
        """,
        (player_date[0], player_date[1], title, body, project_id, effects_json),
    )
    _insert_calendar_event(
        conn,
        title=title,
        event_type="production_announcement" if asset_type == "production_announcement" else "first_image_reveal",
        start=player_date,
        end=player_date,
        project_id=project_id,
        description=body,
        metadata={
            "eventId": (event or {}).get("id"),
            "choiceId": choice.get("id"),
            "assetType": asset_type,
            "estimatedCost": cost,
        },
    )
    return cost


def _announcement_reactions(announcement: dict[str, Any]) -> list[dict[str, str]]:
    reactions = announcement.get("reactions")
    if isinstance(reactions, list):
        return [dict(item) for item in reactions if isinstance(item, dict)]
    return [
        {
            "speaker": "언론",
            "text": str(announcement.get("pressReaction") or "제작 규모와 캐스팅을 두고 기대와 검증이 함께 붙고 있다."),
        },
        {
            "speaker": "관객",
            "text": str(announcement.get("audienceReaction") or "사진과 발표 문구를 보고 영화의 분위기를 가늠하기 시작했다."),
        },
    ]


def _create_test_screening(
    conn: Any,
    project_id: str,
    player_date: tuple[int, int, int],
    event: dict[str, Any] | None,
    choice: dict[str, Any],
    effects: dict[str, Any],
    flags: dict[str, Any],
) -> None:
    screening_id = f"screening_{uuid.uuid4().hex[:10]}"
    conn.execute(
        """
        INSERT INTO test_screenings (
            id, project_id, screening_type, year, month, day,
            audience_type, score_band, result_summary, notes_json, effects_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            screening_id,
            project_id,
            str(flags.get("screeningType") or "test_preview"),
            player_date[0], player_date[1], player_date[2],
            str(flags.get("audienceType") or "일반 관객 표본"),
            str(flags.get("scoreBand") or "mixed"),
            str(flags.get("screeningSummary") or choice.get("resultText") or (event or {}).get("title") or "테스트 시사회 반응이 기록되었다."),
            dumps_json({"eventId": (event or {}).get("id"), "choiceId": choice.get("id")}),
            dumps_json(effects),
        ),
    )


def _create_marketing_reaction(
    conn: Any,
    project_id: str,
    player_date: tuple[int, int, int],
    event: dict[str, Any] | None,
    choice: dict[str, Any],
    effects: dict[str, Any],
    reaction: dict[str, Any],
) -> None:
    asset_type = str(reaction.get("assetType") or "main_trailer")
    asset_id = _ensure_marketing_asset(conn, project_id, asset_type, player_date, reaction)
    sentiment = str(reaction.get("sentimentBand") or reaction.get("sentiment") or "mixed")
    buzz_score = max(0, min(100, int(reaction.get("buzzScore", 50) or 0)))
    result_summary = str(
        reaction.get("resultSummary")
        or reaction.get("onlineSummary")
        or choice.get("resultText")
        or "마케팅 소재 반응이 기록되었다."
    )
    conn.execute(
        """
        UPDATE marketing_assets
        SET status = 'released',
            release_year = ?,
            release_month = ?,
            release_day = ?,
            sentiment_band = ?,
            buzz_score = ?,
            result_summary = ?
        WHERE id = ?
        """,
        (player_date[0], player_date[1], player_date[2], sentiment, buzz_score, result_summary, asset_id),
    )
    conn.execute(
        """
        INSERT INTO marketing_reactions (
            id, project_id, asset_id, reaction_type, year, month, day,
            sentiment_band, buzz_score, audience_summary, press_summary,
            online_summary, effects_json, metadata_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            f"reaction_{uuid.uuid4().hex[:10]}",
            project_id,
            asset_id,
            str(reaction.get("reactionType") or "public_reaction"),
            player_date[0], player_date[1], player_date[2],
            sentiment,
            buzz_score,
            str(reaction.get("audienceSummary") or ""),
            str(reaction.get("pressSummary") or ""),
            str(reaction.get("onlineSummary") or result_summary),
            dumps_json(effects),
            dumps_json({"eventId": (event or {}).get("id"), "choiceId": choice.get("id"), "assetType": asset_type}),
        ),
    )


def _ensure_marketing_asset(
    conn: Any,
    project_id: str,
    asset_type: str,
    date_value: tuple[int, int, int],
    reaction: dict[str, Any],
) -> str:
    row = conn.execute(
        """
        SELECT id
        FROM marketing_assets
        WHERE project_id = ? AND asset_type = ?
        ORDER BY planned_year, planned_month, planned_day, created_at
        LIMIT 1
        """,
        (project_id, asset_type),
    ).fetchone()
    if row:
        return str(row["id"])
    asset_id = f"asset_{uuid.uuid4().hex[:10]}"
    conn.execute(
        """
        INSERT INTO marketing_assets (
            id, project_id, asset_type, planned_stage, planned_year, planned_month, planned_day,
            channel, status, result_summary, metadata_json
        ) VALUES (?, ?, ?, 'marketing', ?, ?, ?, ?, 'released', ?, ?)
        """,
        (
            asset_id,
            project_id,
            asset_type,
            date_value[0], date_value[1], date_value[2],
            str(reaction.get("channel") or "press_online"),
            str(reaction.get("resultSummary") or "이벤트 선택으로 공개된 마케팅 소재."),
            dumps_json({"createdByReaction": True}),
        ),
    )
    return asset_id


def _create_stage_greeting_schedule(
    conn: Any,
    project_id: str,
    project_title: str,
    player_date: tuple[int, int, int],
    event: dict[str, Any] | None,
    choice: dict[str, Any],
    greeting: dict[str, Any],
) -> int:
    date_value = add_days_to_date(player_date, int(greeting.get("daysOffset", 1) or 1))
    cost = max(0, int(greeting.get("estimatedCost", greeting.get("cost", 0)) or 0))
    greeting_id = f"greeting_{uuid.uuid4().hex[:10]}"
    city = str(greeting.get("city") or "서울")
    venue = str(greeting.get("venue") or "주요 극장")
    event_name = str(greeting.get("eventName") or f"{project_title} 무대인사")
    result_summary = str(greeting.get("resultSummary") or "개봉 후 관객을 직접 만나는 일정이 잡혔다.")
    conn.execute(
        """
        INSERT INTO stage_greeting_schedules (
            id, project_id, year, month, day, city, venue, event_name,
            cast_scope, expected_attendance, estimated_cost, status,
            result_summary, metadata_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'planned', ?, ?)
        """,
        (
            greeting_id,
            project_id,
            date_value[0], date_value[1], date_value[2],
            city,
            venue,
            event_name,
            str(greeting.get("castScope") or "감독/주연 배우 일부"),
            int(greeting.get("expectedAttendance", 0) or 0),
            cost,
            result_summary,
            dumps_json({"eventId": (event or {}).get("id"), "choiceId": choice.get("id")}),
        ),
    )
    _insert_calendar_event(
        conn,
        title=f"{project_title}: {city} 무대인사",
        event_type="stage_greeting",
        start=date_value,
        end=date_value,
        project_id=project_id,
        description=f"{venue} · {result_summary}",
        metadata={"stageGreetingId": greeting_id, "city": city, "venue": venue, "estimatedCost": cost},
    )
    return cost


def _create_reshoot_order(
    conn: Any,
    project_id: str,
    project_title: str,
    player_date: tuple[int, int, int],
    days: int,
    cost: int,
    event: dict[str, Any] | None,
    choice: dict[str, Any],
    flags: dict[str, Any],
) -> None:
    reshoot_id = f"reshoot_{uuid.uuid4().hex[:10]}"
    reason = str(flags.get("reshootReason") or choice.get("text") or "재촬영 필요")
    conn.execute(
        """
        INSERT INTO reshoot_orders (
            id, project_id, reason, planned_days, estimated_cost,
            status, year, month, day, metadata_json
        ) VALUES (?, ?, ?, ?, ?, 'planned', ?, ?, ?, ?)
        """,
        (
            reshoot_id,
            project_id,
            reason,
            days,
            cost,
            player_date[0], player_date[1], player_date[2],
            dumps_json({"eventId": (event or {}).get("id"), "choiceId": choice.get("id")}),
        ),
    )
    _create_extra_shooting_block(
        conn,
        project_id,
        project_title,
        player_date,
        days,
        reason=f"재촬영: {reason}",
        metadata={"reshootId": reshoot_id, "estimatedCost": cost},
    )
    _insert_paid_cashflow(
        conn,
        project_id,
        player_date,
        amount=cost,
        target="reshoot_unit",
        cashflow_type="reshoot_cost",
        description=f"재촬영 비용 집행: {reason}",
        metadata={"reshootId": reshoot_id},
    )


def _create_extra_shooting_block(
    conn: Any,
    project_id: str,
    project_title: str,
    start: tuple[int, int, int],
    days: int,
    *,
    reason: str,
    metadata: dict[str, Any] | None = None,
) -> None:
    sequence = int(
        conn.execute(
            "SELECT COALESCE(MAX(sequence), 0) + 1 AS next_sequence FROM shooting_schedule_blocks WHERE project_id = ?",
            (project_id,),
        ).fetchone()["next_sequence"]
    )
    end = add_days_to_date(start, max(0, days - 1))
    block_id = f"shoot_{uuid.uuid4().hex[:10]}"
    conn.execute(
        """
        INSERT INTO shooting_schedule_blocks (
            id, project_id, sequence, stage, start_year, start_month, start_day,
            end_year, end_month, end_day, unit_name, location_type,
            planned_days, status, description, metadata_json
        ) VALUES (?, ?, ?, 'reshoot', ?, ?, ?, ?, ?, ?, ?, ?, ?, 'planned', ?, ?)
        """,
        (
            block_id,
            project_id,
            sequence,
            start[0], start[1], start[2],
            end[0], end[1], end[2],
            "추가 촬영/재촬영",
            "보강 촬영",
            days,
            reason,
            dumps_json(metadata or {}),
        ),
    )
    _insert_calendar_event(
        conn,
        title=f"{project_title}: 추가 촬영",
        event_type="reshoot",
        start=start,
        end=end,
        project_id=project_id,
        description=reason,
        metadata={"shootingBlockId": block_id, "plannedDays": days, **(metadata or {})},
    )


def _insert_paid_cashflow(
    conn: Any,
    project_id: str,
    date_value: tuple[int, int, int],
    *,
    amount: int,
    target: str,
    cashflow_type: str,
    description: str,
    metadata: dict[str, Any] | None = None,
    planned_stage: str = "post_production",
) -> None:
    if amount <= 0:
        return
    cashflow_id = f"cashflow_{uuid.uuid4().hex[:10]}"
    conn.execute(
        """
        INSERT INTO project_cashflows (
            id, project_id, planned_stage, planned_year, planned_month, planned_day,
            due_year, due_month, due_day, paid_year, paid_month, paid_day,
            amount, source, target, cashflow_type, status, description, metadata_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'reserved_project_funds', ?, ?, 'paid', ?, ?)
        """,
        (
            cashflow_id,
            project_id,
            planned_stage,
            date_value[0], date_value[1], date_value[2],
            date_value[0], date_value[1], date_value[2],
            date_value[0], date_value[1], date_value[2],
            amount,
            target,
            cashflow_type,
            description,
            dumps_json(metadata or {}),
        ),
    )
    conn.execute(
        """
        INSERT INTO finance_transactions (
            year, month, day, transaction_type, amount, source, target,
            project_id, description, metadata_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            date_value[0], date_value[1], date_value[2],
            "project_cashflow_disbursement",
            -amount,
            "reserved_project_funds",
            target,
            project_id,
            description,
            dumps_json(metadata or {}),
        ),
    )


def _increase_project_financing_total(conn: Any, project_id: str, amount: int, *, reason: str) -> None:
    if amount <= 0:
        return
    row = conn.execute("SELECT * FROM project_financing WHERE project_id = ?", (project_id,)).fetchone()
    if not row:
        return
    financing_json = loads_json(row["financing_json"], {})
    extra_costs = financing_json.get("extraProductionCosts")
    if not isinstance(extra_costs, list):
        extra_costs = []
    extra_costs.append({"amount": amount, "reason": reason})
    financing_json["extraProductionCosts"] = extra_costs
    financing_json["totalCost"] = int(row["total_cost"] or 0) + amount
    financing_json["ownCapitalUsed"] = int(row["own_capital_used"] or 0) + amount
    conn.execute(
        """
        UPDATE project_financing
        SET total_cost = total_cost + ?,
            own_capital_used = own_capital_used + ?,
            financing_json = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE project_id = ?
        """,
        (amount, amount, dumps_json(financing_json), project_id),
    )


def _apply_crew_adjustments(conn: Any, project_id: str, changes: list[Any]) -> None:
    for change in changes:
        if not isinstance(change, dict):
            continue
        role_id = str(change.get("roleId") or "")
        if not role_id:
            continue
        fields = []
        values: list[Any] = []
        if change.get("filledStatus"):
            fields.append("filled_status = ?")
            values.append(str(change["filledStatus"]))
        if change.get("seniority"):
            fields.append("seniority = ?")
            values.append(str(change["seniority"]))
        if change.get("notes"):
            fields.append("notes = ?")
            values.append(str(change["notes"]))
        if not fields:
            continue
        values.extend([project_id, role_id])
        conn.execute(
            f"UPDATE project_crew_roles SET {', '.join(fields)} WHERE project_id = ? AND role_id = ?",
            tuple(values),
        )


def _shooting_blocks_for_genre(
    genre_id: str,
    total_days: int,
    location_profile: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    location_profile = location_profile or {}
    strategy = str(location_profile.get("id") or "real_location")
    if total_days <= 7:
        location = str(location_profile.get("locationType") or "소규모 로케이션")
        return [{"unit": "본촬영", "location": location, "days": total_days, "description": "핵심 장면을 짧은 회차 안에 촬영한다."}]
    if strategy == "set_build":
        first = max(1, int(total_days * 0.24))
        second = max(1, int(total_days * 0.46))
        third = max(1, int(total_days * 0.18))
        fourth = max(1, total_days - first - second - third)
        return [
            {"unit": "세트 조립/동선 리허설", "location": "주요 세트", "days": first, "description": "주요 공간의 세트를 세우고 조명, 동선, 미술 디테일을 맞춘다."},
            {"unit": "세트 본촬영", "location": "세트", "days": second, "description": "통제된 공간에서 핵심 장면을 집중 촬영한다."},
            {"unit": "실제 장소 보강 촬영", "location": "보강 로케이션", "days": third, "description": "세트가 줄 수 없는 외부 질감을 보강한다."},
            {"unit": "픽업/미술 보강 촬영", "location": "세트", "days": fourth, "description": "후반 연결을 위한 인서트와 세트 보강 컷을 확보한다."},
        ]
    if strategy == "regional_location":
        first = max(1, int(total_days * 0.18))
        second = max(1, int(total_days * 0.52))
        third = max(1, int(total_days * 0.18))
        fourth = max(1, total_days - first - second - third)
        return [
            {"unit": "지방 로케이션 답사/허가", "location": "지방 로케이션", "days": first, "description": "지역 기관, 극장, 상인회와 촬영 협조를 조율한다."},
            {"unit": "지방 로케이션 본촬영", "location": "지방 로케이션", "days": second, "description": "지역 공간과 풍광을 영화의 주요 이미지로 확보한다."},
            {"unit": "이동/숙박 포함 야외 촬영", "location": "지방 야외", "days": third, "description": "이동과 숙박을 포함한 야외 회차를 소화한다."},
            {"unit": "서울권 보강 촬영", "location": "보강 촬영", "days": fourth, "description": "누락 장면, 인서트, 후반 연결용 컷을 확보한다."},
        ]
    if strategy == "overseas_location":
        first = max(1, int(total_days * 0.18))
        second = max(1, int(total_days * 0.48))
        third = max(1, int(total_days * 0.20))
        fourth = max(1, total_days - first - second - third)
        return [
            {"unit": "출국/현지 세팅", "location": "해외 로케이션", "days": first, "description": "비자, 장비 통관, 현지 스태프와 촬영 동선을 맞춘다."},
            {"unit": "해외 로케이션 본촬영", "location": "해외 로케이션", "days": second, "description": "해외 공간의 스케일과 시각적 차별성을 확보한다."},
            {"unit": "현지 보강/예비 회차", "location": "해외 보강 촬영", "days": third, "description": "날씨와 허가 변수를 감안한 보강 회차를 둔다."},
            {"unit": "국내 연결 촬영", "location": "국내 보강 촬영", "days": fourth, "description": "국내 장면과 해외 장면의 연결을 맞춘다."},
        ]
    action_block = "액션/야간 촬영" if genre_id in {"genre_action", "genre_crime_thriller", "genre_horror_occult"} else "감정/대사 집중 촬영"
    first = max(1, int(total_days * 0.22))
    second = max(1, int(total_days * 0.38))
    third = max(1, int(total_days * 0.24))
    fourth = max(1, total_days - first - second - third)
    return [
        {"unit": "리허설/초반 세팅", "location": "주요 세트", "days": first, "description": "동선, 톤, 촬영 리듬을 맞추는 초반 회차."},
        {"unit": "주요 로케이션 촬영", "location": "로케이션", "days": second, "description": "영화의 중심 장면을 집중적으로 촬영한다."},
        {"unit": action_block, "location": "혼합", "days": third, "description": "장르적 인상을 만드는 고난도 장면을 촬영한다."},
        {"unit": "보강/픽업 촬영", "location": "보강 촬영", "days": fourth, "description": "누락 장면, 인서트, 후반 연결용 컷을 확보한다."},
    ]


def _insert_calendar_event(
    conn: Any,
    *,
    title: str,
    event_type: str,
    start: tuple[int, int, int],
    end: tuple[int, int, int],
    project_id: str,
    description: str,
    metadata: dict[str, Any],
) -> None:
    conn.execute(
        """
        INSERT INTO calendar_events (
            id, year, month, day, end_year, end_month, end_day,
            title, event_type, project_id, description, metadata_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            f"calendar_{uuid.uuid4().hex[:12]}",
            start[0], start[1], start[2],
            end[0], end[1], end[2],
            title,
            event_type,
            project_id,
            description,
            dumps_json(metadata),
        ),
    )


def _first_existing_stage(stage_dates: dict[str, Any], candidates: list[str]) -> str | None:
    for stage in candidates:
        if stage in stage_dates:
            return stage
    return None


def _funding_mix(amount: int, total: int, financing: dict[str, Any]) -> dict[str, int]:
    own = int(financing.get("ownCapitalUsed", 0) or 0)
    investment = int(financing.get("investmentUsed", 0) or 0)
    loan = int(financing.get("loanUsed", 0) or 0)
    base = max(1, own + investment + loan, total)
    return {
        "ownCapital": int(amount * own / base),
        "investment": int(amount * investment / base),
        "loan": int(amount * loan / base),
    }


def _allocation_hint_for_role(role_id: str, allocation: dict[str, int]) -> float:
    mapping = {
        "cinematographer": "shooting",
        "gaffer": "shooting",
        "production_designer": "art",
        "costume_designer": "art",
        "sound_mixer": "sound",
        "editor": "editing",
        "music_director": "sound",
        "vfx_supervisor": "vfx",
        "stunt_coordinator": "stunt",
        "assistant_director": "directing",
        "script_supervisor": "scenario",
    }
    key = mapping.get(role_id)
    if not key:
        return 1.0
    value = max(0, int(allocation.get(key, 10) or 0))
    return max(0.55, min(1.55, value / 10))


def _default_reshoot_cost(project: Any, days: int) -> int:
    production_budget = int(project["production_budget"] if hasattr(project, "keys") else project.get("production_budget", 0) or 0)
    return max(20_000_000, int(production_budget * 0.006 * max(1, days)))


def _player_date(player: Any) -> tuple[int, int, int]:
    if player:
        return (int(player["current_year"]), int(player["current_month"]), int(player["current_day"] or 1))
    return current_game_date()


def _scenario_from_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row.get("id"),
        "sequence": int(row.get("sequence") or 0),
        "stepId": row.get("step_id") or "",
        "stepName": row.get("step_name") or "시나리오",
        "plannedStage": row.get("planned_stage") or "",
        "date": _date_range(row),
        "status": row.get("status") or "planned",
        "statusLabel": scenario_status_label(row.get("status")),
        "diagnosisLabel": row.get("diagnosis_label") or "",
        "diagnosisText": row.get("diagnosis_text") or "",
        "riskNote": row.get("risk_note") or "",
        "suggestedAction": row.get("suggested_action") or "",
    }


def _crew_from_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "roleId": row["role_id"],
        "roleName": row["role_name"],
        "department": row.get("department"),
        "required": bool(row.get("required")),
        "filledStatus": row.get("filled_status"),
        "seniority": row.get("seniority"),
        "estimatedFee": int(row.get("estimated_fee") or 0),
        "notes": row.get("notes") or "",
    }


def _contract_from_row(row: dict[str, Any]) -> dict[str, Any]:
    options = loads_json(row.get("contract_options_json"), {})
    terms = options.get("terms") if isinstance(options.get("terms"), dict) else {}
    sequel_option = bool(options.get("sequelOption") or row.get("sequel_option"))
    promotion = bool(options.get("promotionObligation") or row.get("promotion_obligation"))
    promotion_days = int(options.get("promotionDays") or row.get("promotion_days") or 0)
    commitment_months = int(options.get("scheduleCommitmentMonths") or row.get("schedule_commitment_months") or 0)
    parts = []
    if sequel_option:
        parts.append("후속작 옵션")
    if promotion:
        parts.append(f"홍보 {promotion_days}일")
    if commitment_months:
        parts.append(f"일정 구속 {commitment_months}개월")
    running = terms.get("runningGuarantee") if isinstance(terms.get("runningGuarantee"), dict) else {}
    if running.get("enabled") and float(running.get("rate") or 0) > 0:
        parts.append(f"러닝 {float(running['rate']) * 100:.1f}%")
    bonus = terms.get("boxOfficeBonus") if isinstance(terms.get("boxOfficeBonus"), dict) else {}
    if bonus.get("enabled") and int(bonus.get("amount") or 0) > 0:
        parts.append(f"흥행 보너스 {money(int(bonus['amount']))}")
    if int(terms.get("deferredFee") or 0) > 0:
        parts.append(f"이연 {money(int(terms['deferredFee']))}")
    if terms.get("imageRights"):
        parts.append("이미지 활용")
    return {
        "personId": row.get("person_id"),
        "name": row.get("name_ko") or row.get("person_id"),
        "type": row.get("type") or "",
        "role": row.get("role") or "",
        "contractFee": int(row.get("contract_fee") or 0),
        "sequelOption": sequel_option,
        "promotionObligation": promotion,
        "promotionDays": promotion_days,
        "scheduleCommitmentMonths": commitment_months,
        "contractTerms": terms,
        "summary": " · ".join(parts) if parts else "기본 출연 계약",
    }


def _version_from_row(row: dict[str, Any]) -> dict[str, Any]:
    labels = {
        "theatrical_cut": "극장판",
        "director_cut": "감독판",
        "ott_cut": "OTT판",
    }
    status_labels = {
        "planned": "준비 중",
        "selected": "선택됨",
        "released": "공개됨",
        "held": "보류",
    }
    return {
        "id": row.get("id"),
        "versionType": row.get("version_type"),
        "name": row.get("name") or labels.get(str(row.get("version_type") or ""), "판본"),
        "status": row.get("status") or "planned",
        "statusLabel": status_labels.get(str(row.get("status") or "planned"), str(row.get("status") or "planned")),
        "runtimeMinutes": int(row.get("runtime_minutes") or 0),
        "qualityDelta": int(row.get("quality_delta") or 0),
        "audienceDelta": int(row.get("audience_delta") or 0),
        "criticDelta": int(row.get("critic_delta") or 0),
        "secondaryMarketDelta": int(row.get("secondary_market_delta") or 0),
        "selectedForTheatrical": bool(row.get("selected_for_theatrical")),
        "selectedForOtt": bool(row.get("selected_for_ott")),
        "description": row.get("description") or "",
    }


def _location_from_row(row: dict[str, Any]) -> dict[str, Any]:
    metadata = loads_json(row.get("metadata_json"), {})
    return {
        "id": row.get("id"),
        "strategy": row.get("location_strategy") or "",
        "name": row.get("location_name") or "로케이션 전략",
        "locationType": row.get("location_type") or "",
        "costImpact": int(row.get("cost_impact") or 0),
        "qualityDelta": int(row.get("quality_delta") or 0),
        "permitRiskDelta": int(row.get("permit_risk_delta") or 0),
        "regionalNetworkDelta": int(row.get("regional_network_delta") or 0),
        "durationDeltaDays": int(row.get("duration_delta_days") or 0),
        "status": row.get("status") or "selected",
        "description": row.get("description") or "",
        "impactLine": metadata.get("impactLine") or "",
    }


def _shooting_from_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "sequence": int(row.get("sequence") or 0),
        "date": _date_range(row),
        "unitName": row.get("unit_name") or "촬영",
        "locationType": row.get("location_type") or "-",
        "plannedDays": int(row.get("planned_days") or 0),
        "status": row.get("status") or "planned",
        "description": row.get("description") or "",
    }


def _cashflow_from_row(row: dict[str, Any]) -> dict[str, Any]:
    metadata = loads_json(row.get("metadata_json"), {})
    return {
        "id": row["id"],
        "date": _single_date(row.get("planned_year"), row.get("planned_month"), row.get("planned_day")),
        "paidDate": _single_date(row.get("paid_year"), row.get("paid_month"), row.get("paid_day")),
        "stage": row.get("planned_stage"),
        "stageLabel": metadata.get("stageLabel") or STAGE_LABELS.get(str(row.get("planned_stage") or ""), row.get("planned_stage") or "-"),
        "amount": int(row.get("amount") or 0),
        "source": row.get("source") or "-",
        "target": row.get("target") or "-",
        "cashflowType": row.get("cashflow_type") or "-",
        "status": row.get("status") or "planned",
        "description": row.get("description") or "",
        "fundingMix": metadata.get("fundingMix") or {},
    }


def _screening_from_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "date": _single_date(row.get("year"), row.get("month"), row.get("day")),
        "screeningType": row.get("screening_type"),
        "audienceType": row.get("audience_type"),
        "scoreBand": row.get("score_band"),
        "resultSummary": row.get("result_summary") or "",
    }


def _reshoot_from_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "date": _single_date(row.get("year"), row.get("month"), row.get("day")),
        "reason": row.get("reason") or "",
        "plannedDays": int(row.get("planned_days") or 0),
        "estimatedCost": int(row.get("estimated_cost") or 0),
        "status": row.get("status") or "planned",
    }


def _marketing_asset_from_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "assetType": row.get("asset_type") or "",
        "assetLabel": _asset_type_label(str(row.get("asset_type") or "")),
        "plannedDate": _single_date(row.get("planned_year"), row.get("planned_month"), row.get("planned_day")),
        "releaseDate": _single_date(row.get("release_year"), row.get("release_month"), row.get("release_day")),
        "channel": row.get("channel") or "-",
        "status": row.get("status") or "planned",
        "sentimentBand": row.get("sentiment_band") or "",
        "buzzScore": int(row.get("buzz_score") or 0),
        "resultSummary": row.get("result_summary") or "",
    }


def _marketing_reaction_from_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "assetType": row.get("asset_type") or "",
        "assetLabel": _asset_type_label(str(row.get("asset_type") or "")),
        "date": _single_date(row.get("year"), row.get("month"), row.get("day")),
        "reactionType": row.get("reaction_type") or "",
        "sentimentBand": row.get("sentiment_band") or "",
        "buzzScore": int(row.get("buzz_score") or 0),
        "audienceSummary": row.get("audience_summary") or "",
        "pressSummary": row.get("press_summary") or "",
        "onlineSummary": row.get("online_summary") or "",
    }


def _stage_greeting_from_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "date": _single_date(row.get("year"), row.get("month"), row.get("day")),
        "city": row.get("city") or "",
        "venue": row.get("venue") or "",
        "eventName": row.get("event_name") or "무대인사",
        "castScope": row.get("cast_scope") or "",
        "expectedAttendance": int(row.get("expected_attendance") or 0),
        "estimatedCost": int(row.get("estimated_cost") or 0),
        "status": row.get("status") or "planned",
        "resultSummary": row.get("result_summary") or "",
    }


def _operations_summary(
    scenario_development: list[dict[str, Any]],
    crew: list[dict[str, Any]],
    contracts: list[dict[str, Any]],
    versions: list[dict[str, Any]],
    locations: list[dict[str, Any]],
    shooting: list[dict[str, Any]],
    cashflows: list[dict[str, Any]],
    screenings: list[dict[str, Any]],
    reshoots: list[dict[str, Any]],
    marketing_assets: list[dict[str, Any]],
    marketing_reactions: list[dict[str, Any]],
    stage_greetings: list[dict[str, Any]],
) -> str:
    required = sum(1 for item in crew if item.get("required"))
    planned_spend = sum(int(item.get("amount") or 0) for item in cashflows)
    paid_spend = sum(int(item.get("amount") or 0) for item in cashflows if item.get("status") == "paid")
    shooting_days = sum(int(item.get("plannedDays") or 0) for item in shooting)
    released_assets = sum(1 for item in marketing_assets if item.get("status") == "released")
    option_count = sum(1 for item in contracts if item.get("sequelOption") or item.get("promotionObligation"))
    selected_versions = [item["name"] for item in versions if item.get("selectedForTheatrical")]
    version_text = ", ".join(selected_versions) if selected_versions else "미정"
    location_text = locations[0]["name"] if locations else "미정"
    script_text = _scenario_summary_text(scenario_development)
    return (
        f"시나리오 {script_text} · 로케이션 {location_text} · 핵심 제작진 {required}개 포지션 · 촬영 {shooting_days}일 계획 · "
        f"집행 {money(paid_spend)} / 예정 {money(planned_spend)} · "
        f"테스트 시사회 {len(screenings)}회 · 재촬영 {len(reshoots)}건 · "
        f"마케팅 소재 {released_assets}/{len(marketing_assets)}개 공개 · "
        f"반응 기록 {len(marketing_reactions)}건 · 무대인사 {len(stage_greetings)}건 · "
        f"계약 옵션 {option_count}건 · 개봉 판본 {version_text}"
    )


def _scenario_summary_text(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "미정"
    in_progress = next((row for row in rows if row.get("status") == "in_progress"), None)
    row = in_progress or rows[0]
    text = str(row.get("diagnosisText") or row.get("riskNote") or row.get("stepName") or "개발 중")
    return text if len(text) <= 42 else f"{text[:42]}..."


def _date_range(row: dict[str, Any]) -> str:
    start = _single_date(row.get("start_year"), row.get("start_month"), row.get("start_day"))
    end = _single_date(row.get("end_year"), row.get("end_month"), row.get("end_day"))
    if start and end and start != end:
        return f"{start}~{end}"
    return start or "미정"


def _single_date(year: Any, month: Any, day: Any) -> str:
    if not year or not month or not day:
        return ""
    return f"{int(year)}.{int(month):02d}.{int(day):02d}"


def _asset_type_label(asset_type: str) -> str:
    labels = {
        "production_announcement": "제작 발표회",
        "first_image": "첫 이미지",
        "still_cut": "스틸컷",
        "main_poster": "메인 포스터",
        "teaser_poster": "티저 포스터",
        "main_trailer": "메인 예고편",
        "teaser_trailer": "티저 예고편",
        "behind_cut": "비하인드 컷",
    }
    return labels.get(asset_type, asset_type or "마케팅 소재")


def _as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    return [value]
