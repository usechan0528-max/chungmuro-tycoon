from __future__ import annotations

from copy import deepcopy
import random
from typing import Any

from app.database import dumps_json, get_connection, loads_json
from app.services.event_constants import (
    WALK_OUT_BASE_EFFECTS,
    WALK_OUT_CHOICE_ID,
)
from app.services.event_effects import (
    _apply_delta_map,
    _effect_sentence_groups,
    _is_number,
    _merge_effects,
    _resolve_choice_effects,
    _write_story_flags,
)
from app.services.event_triggers import (
    _dynamic_event_weight,
    _stage_aliases,
    _trigger_matches,
)
from app.services.game_state import clamp
from app.services.progression_service import (
    STAGE_LABELS,
    effect_time_cost_days,
    next_project_stage,
    stage_time_cost_days_for_project,
    sync_shooting_duration_stats,
)
from app.services.production_management_service import (
    apply_production_management_effects,
    mark_project_cashflows_for_stage,
)


RECENT_EVENT_HISTORY_LIMIT = 36
RECENT_STAGE_HISTORY_LIMIT = 16


def get_project_event(project_id: str, category: str = "production") -> dict[str, Any] | None:
    with get_connection() as conn:
        project = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
        if not project:
            return None
        if project["stage"] == "production_announcement":
            project_stats = loads_json(project["stats_json"], {})
            if int(project_stats.get("cast_confirmed", 0) or 0) <= 0:
                return None
        context = _event_context(conn, project_id, dict(project))
        seen_event_ids = {
            row["event_id"]
            for row in conn.execute(
                """
                SELECT event_id
                FROM event_history
                WHERE project_id = ? AND category = ?
                """,
                (project_id, category),
            ).fetchall()
        }
        stage_aliases = _stage_aliases(project["stage"])
        placeholders = ", ".join("?" for _ in stage_aliases)
        rows = conn.execute(
            f"""
            SELECT * FROM simulation_events
            WHERE category = ? AND scope = 'project' AND stage IN ({placeholders})
            ORDER BY weight DESC, id
            """,
            (category, *stage_aliases),
        ).fetchall()
        recent_rows = [
            dict(row)
            for row in conn.execute(
                """
                SELECT event_id, category, project_id, year, month
                FROM event_history
                WHERE category = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (category, RECENT_EVENT_HISTORY_LIMIT),
            ).fetchall()
        ]
        stage_recent_rows = [
            dict(row)
            for row in conn.execute(
                f"""
                SELECT eh.event_id, eh.category, eh.project_id, eh.year, eh.month, se.stage
                FROM event_history eh
                JOIN simulation_events se ON se.id = eh.event_id
                WHERE eh.category = ? AND se.stage IN ({placeholders})
                ORDER BY eh.id DESC
                LIMIT ?
                """,
                (category, *stage_aliases, RECENT_STAGE_HISTORY_LIMIT),
            ).fetchall()
        ]

    matching_events = []
    project_data = dict(project)
    for row in rows:
        event = _event_from_row(row)
        if event["id"] in seen_event_ids:
            continue
        if _trigger_matches(event.get("trigger", {}), project_data, context):
            matching_events.append(event)
    if not matching_events:
        return None
    weights = [
        _varied_event_weight(event, _dynamic_event_weight(event, project_data, context), recent_rows, stage_recent_rows, context)
        for event in matching_events
    ]
    if not any(weight > 0 for weight in weights):
        return None
    return random.choices(matching_events, weights=weights, k=1)[0]


def apply_project_event_choice(
    project_id: str,
    event: dict[str, Any] | None,
    choice: dict[str, Any],
    *,
    advance_stage: bool = True,
) -> dict[str, Any]:
    with get_connection() as conn:
        project = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
        player = conn.execute("SELECT * FROM player_state WHERE id = 1").fetchone()
        studio = conn.execute("SELECT * FROM studio_state WHERE id = 1").fetchone()
        if not project or not player:
            raise ValueError("진행 중인 프로젝트를 찾을 수 없습니다.")

        stats = loads_json(project["stats_json"], {})
        reputation = loads_json(player["reputation_json"], {})
        network = loads_json(player["network_json"], {})
        player_stats = loads_json(player["stats_json"], {})
        effects = _resolve_choice_effects(choice, event, player_stats=player_stats)
        outcome_summary = describe_choice_outcome(event, choice, effects)
        current_stage = project["stage"]
        scale_id = project["scale_id"]
        effect_days = effect_time_cost_days(effects)
        base_stage_days = stage_time_cost_days_for_project(current_stage, scale_id, stats) if advance_stage else 0
        time_days = effect_days + base_stage_days

        stat_effects = dict(effects.get("stats", {}) or {})
        shooting_duration_effects = {
            key: stat_effects.pop(key)
            for key in ("shooting_duration", "shooting_duration_delta_days")
            if key in stat_effects
        }
        _apply_delta_map(stats, stat_effects, default=50)
        sync_shooting_duration_stats(stats, scale_id, effect_stats=shooting_duration_effects)
        _apply_delta_map(reputation, effects.get("reputation", {}), default=10)
        _apply_delta_map(network, effects.get("network", {}), default=10)
        _apply_delta_map(player_stats, effects.get("playerStats", {}), default=50)

        next_stage = next_project_stage(project["stage"], project["scale_id"]) if advance_stage else project["stage"]
        if advance_stage and next_stage == "production_announcement":
            from app.services.casting_service import casting_confirmation_status

            casting_status = casting_confirmation_status(project_id)
            if not casting_status["is_confirmed"]:
                raise ValueError(
                    "제작 발표회 전에는 공식 출연진 확정이 필요합니다. "
                    "캐스팅/계약 관리에서 필요한 출연진을 확정하세요."
                )
        management_result = apply_production_management_effects(
            conn,
            project_id=project_id,
            project=project,
            player=player,
            event=event,
            choice=choice,
            effects=effects,
            stats=stats,
        )
        production_budget_delta = int(management_result.get("productionBudgetDelta", 0) or 0)
        marketing_budget_delta = int(management_result.get("marketingBudgetDelta", 0) or 0)
        studio_cash_delta = int(management_result.get("studioCashDelta", 0) or 0)
        next_production_budget = int(project["production_budget"] or 0) + production_budget_delta
        next_marketing_budget = int(project["marketing_budget"] or 0) + marketing_budget_delta
        if production_budget_delta or marketing_budget_delta:
            stats["production_budget"] = next_production_budget
            stats["marketing_budget"] = next_marketing_budget
            stats["total_cost"] = (
                next_production_budget
                + next_marketing_budget
                + int(stats.get("location_cost_impact", 0) or 0)
            )
        if studio_cash_delta:
            studio_effects = effects.setdefault("studio", {})
            studio_effects["cash"] = int(studio_effects.get("cash", 0) or 0) + studio_cash_delta
        conn.execute(
            "UPDATE projects SET stats_json = ?, stage = ?, production_budget = ?, marketing_budget = ? WHERE id = ?",
            (dumps_json(stats), next_stage, next_production_budget, next_marketing_budget, project_id),
        )
        conn.execute(
            "UPDATE production_projects SET stats_json = ?, stage = ?, production_budget = ?, marketing_budget = ? WHERE id = ?",
            (dumps_json(stats), next_stage, next_production_budget, next_marketing_budget, project_id),
        )
        conn.execute(
            """
            UPDATE player_state
            SET stats_json = ?, reputation_json = ?, network_json = ?
            WHERE id = 1
            """,
            (dumps_json(player_stats), dumps_json(reputation), dumps_json(network)),
        )

        if studio and effects.get("studio"):
            from app.services.finance_service import apply_studio_delta

            apply_studio_delta(conn, studio, effects["studio"])

        if effects.get("version"):
            from app.services.version_service import apply_version_effects

            apply_version_effects(conn, project_id, effects["version"])

        investment_delta = int(effects.get("stats", {}).get("investment_amount", 0) or 0)
        if investment_delta:
            from app.services.finance_service import apply_project_investment_effect

            apply_project_investment_effect(conn, project_id, player, investment_delta)

        if advance_stage:
            mark_project_cashflows_for_stage(conn, project_id, next_stage, player)

        _write_story_flags(conn, effects.get("flags", {}), player)
        conn.execute(
            """
            INSERT INTO event_history (
                event_id, category, project_id, choice_id, choice_text,
                year, month, effects_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                (event or {}).get("id", "unknown_event"),
                (event or {}).get("category", "production"),
                project_id,
                choice.get("id"),
                choice.get("text"),
                player["current_year"],
                player["current_month"],
                dumps_json(effects),
            ),
        )
        conn.execute(
            """
            INSERT INTO production_stage_logs (
                event_id, category, project_id, choice_id, choice_text,
                year, month, effects_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                (event or {}).get("id", "unknown_event"),
                (event or {}).get("category", "production"),
                project_id,
                choice.get("id"),
                choice.get("text"),
                player["current_year"],
                player["current_month"],
                dumps_json(effects),
            ),
        )
        conn.commit()

    if time_days > 0:
        from app.services.calendar_service import record_project_time_spent

        event_title = (event or {}).get("title") or choice.get("text") or STAGE_LABELS.get(current_stage, current_stage)
        record_project_time_spent(
            project_id=project_id,
            project_title=project["title"],
            stage=current_stage,
            scale_id=scale_id,
            days=time_days,
            title=str(event_title),
            event_type=(event or {}).get("category", "production"),
            description=outcome_summary,
            metadata={
                "eventId": (event or {}).get("id"),
                "choiceId": choice.get("id"),
                "choiceText": choice.get("text"),
                "baseStageDays": base_stage_days,
                "effectDays": effect_days,
            },
        )

    return {
        "stats": stats,
        "reputation": reputation,
        "network": network,
        "player_stats": player_stats,
        "next_stage": next_stage,
        "outcome_summary": outcome_summary,
    }


def describe_choice_outcome(
    event: dict[str, Any] | None,
    choice: dict[str, Any],
    effects: dict[str, Any],
) -> str:
    if effects.get("flags", {}).get("dialogue_check_passed") is True and choice.get("successText"):
        return _with_consequence_summary(str(choice["successText"]), effects)
    if effects.get("flags", {}).get("dialogue_check_passed") is False and choice.get("failureText"):
        return _with_consequence_summary(str(choice["failureText"]), effects)
    if choice.get("resultText"):
        return _with_consequence_summary(str(choice["resultText"]), effects)

    if choice.get("id") == WALK_OUT_CHOICE_ID:
        if effects.get("flags", {}).get("walk_out_counter_pressure_success"):
            return (
                "대화는 즉시 끝났다. 상대는 불쾌해했지만, 물러서지 않는 태도가 "
                "의외의 압박으로 작용했다. 관계에는 금이 갔고 언론 대응 부담도 남았다."
            )
        return (
            "대화는 즉시 끝났다. 협상 분위기는 얼어붙었고, 상대와의 관계가 나빠졌다. "
            "현장 안팎의 부담과 언론 역풍 위험도 커졌다."
        )

    positive = _effect_sentence_groups(effects, positive=True)
    negative = _effect_sentence_groups(effects, positive=False)

    if positive and negative:
        return f"선택의 효과가 바로 나타났다. {positive[0]} 다만 {negative[0]}"
    if positive:
        return f"대화는 원하는 방향으로 흘렀다. {positive[0]}"
    if negative:
        return f"대화의 여파가 남았다. {negative[0]}"
    return "대화는 큰 파열 없이 마무리됐다. 뚜렷한 변화는 아직 겉으로 드러나지 않는다."


def _with_consequence_summary(base_text: str, effects: dict[str, Any]) -> str:
    positive = _effect_sentence_groups(effects, positive=True)
    negative = _effect_sentence_groups(effects, positive=False)
    if positive and negative:
        return f"{base_text}\n\n결과적으로 {positive[0]} 다만 {negative[0]}"
    if positive:
        return f"{base_text}\n\n결과적으로 {positive[0]}"
    if negative:
        return f"{base_text}\n\n한편 {negative[0]}"
    return base_text


def _varied_event_weight(
    event: dict[str, Any],
    base_weight: int,
    recent_rows: list[dict[str, Any]],
    stage_recent_rows: list[dict[str, Any]],
    context: dict[str, Any],
) -> int:
    if _cooldown_blocks_event(event, recent_rows, context):
        return 0

    event_id = str(event.get("id") or "")
    event_family = _event_family(event_id)
    multiplier = 1.0

    exact_positions = [index for index, row in enumerate(recent_rows) if str(row.get("event_id") or "") == event_id]
    if exact_positions:
        newest = min(exact_positions)
        if newest == 0:
            multiplier *= 0.16
        elif newest <= 2:
            multiplier *= 0.28
        elif newest <= 7:
            multiplier *= 0.46
        else:
            multiplier *= 0.68
        multiplier *= max(0.35, 1.0 - max(0, len(exact_positions) - 1) * 0.12)

    family_positions = [
        index
        for index, row in enumerate(recent_rows)
        if _event_family(str(row.get("event_id") or "")) == event_family
        and str(row.get("event_id") or "") != event_id
    ]
    if event_family and family_positions:
        multiplier *= 0.72 if min(family_positions) <= 5 else 0.88

    stage_exact = any(str(row.get("event_id") or "") == event_id for row in stage_recent_rows)
    stage_family = any(_event_family(str(row.get("event_id") or "")) == event_family for row in stage_recent_rows)
    if stage_exact:
        multiplier *= 0.45
    elif event_family and stage_family:
        multiplier *= 0.78

    jitter = random.uniform(0.86, 1.16)
    return max(1, min(600, int(round(float(base_weight or 1) * multiplier * jitter))))


def _cooldown_blocks_event(event: dict[str, Any], recent_rows: list[dict[str, Any]], context: dict[str, Any]) -> bool:
    cooldown = int(event.get("cooldown_months") or 0)
    if cooldown <= 0:
        return False
    current_year = int(context.get("current_year", 0) or 0)
    current_month = int(context.get("current_month", 1) or 1)
    event_id = str(event.get("id") or "")
    for row in recent_rows:
        if str(row.get("event_id") or "") != event_id:
            continue
        distance = _month_distance(current_year, current_month, row.get("year"), row.get("month"))
        if distance is not None and 0 <= distance < cooldown:
            return True
    return False


def _month_distance(current_year: int, current_month: int, past_year: Any, past_month: Any) -> int | None:
    try:
        return (current_year * 12 + current_month) - (int(past_year) * 12 + int(past_month or 1))
    except (TypeError, ValueError):
        return None


def _event_family(event_id: str) -> str:
    text = event_id
    for prefix in ("dialogue_", "plagiarism_", "franchise_", "late_", "event_"):
        if text.startswith(prefix):
            text = text.removeprefix(prefix)
            break
    parts = [part for part in text.split("_") if part and not part.isdigit()]
    return "_".join(parts[:2]) if len(parts) >= 2 else text


def _event_from_row(row: Any) -> dict[str, Any]:
    row_keys = set(row.keys())
    trigger = loads_json(row["trigger_json"], {})
    dialogue_flow = trigger.pop("_dialogueFlow", {}) if isinstance(trigger, dict) else {}
    choice_style = trigger.pop("_choiceStyle", None) if isinstance(trigger, dict) else None
    relationship_event = trigger.pop("_relationshipEvent", False) if isinstance(trigger, dict) else False
    event = {
        "id": row["id"],
        "category": row["category"],
        "stage": row["stage"],
        "scope": row["scope"],
        "title": row["title"],
        "description": row["description"],
        "fixed_level": row["fixed_level"],
        "weight": row["weight"],
        "cooldown_months": row["cooldown_months"],
        "trigger": trigger,
        "choices": _choice_list(loads_json(row["choices_json"], [])),
    }
    if choice_style:
        event["choiceStyle"] = choice_style
    if relationship_event:
        event["relationshipEvent"] = True
    if isinstance(dialogue_flow, dict) and (dialogue_flow.get("steps") or dialogue_flow.get("negotiation")):
        event["steps"] = dialogue_flow.get("steps", [])
        event["finalOutcomes"] = dialogue_flow.get("finalOutcomes", [])
        event["scoreLabels"] = dialogue_flow.get("scoreLabels", {})
        event["negotiation"] = dialogue_flow.get("negotiation", {})
    if "npc_type" in row_keys:
        event["npcType"] = row["npc_type"]
    if "npc_traits_json" in row_keys:
        event["npcTraits"] = loads_json(row["npc_traits_json"], [])
    if "npc_line" in row_keys:
        event["npcLine"] = row["npc_line"]
    event["choices"] = _with_required_dialogue_choices(event)
    return event


def _with_required_dialogue_choices(event: dict[str, Any]) -> list[dict[str, Any]]:
    choices = [deepcopy(choice) for choice in event.get("choices", [])]
    walk_out_choice = _walk_out_choice_for_event(event)
    for index, choice in enumerate(choices):
        if choice.get("id") == WALK_OUT_CHOICE_ID:
            if choice.get("fixedChoice"):
                choice.setdefault("description", walk_out_choice["description"])
                choices[index] = choice
                return choices
            choices[index] = walk_out_choice
            return choices
    choices.append(walk_out_choice)
    return choices


def _choice_list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [choice for choice in value if isinstance(choice, dict)]


def _walk_out_choice_for_event(event: dict[str, Any]) -> dict[str, Any]:
    effects = deepcopy(WALK_OUT_BASE_EFFECTS)
    _merge_effects(effects, _walk_out_context_effects(event))
    return {
        "id": WALK_OUT_CHOICE_ID,
        "text": "자리를 박차고 나간다",
        "description": (
            "대화를 즉시 끝낸다. 협상 실패 가능성, 상대와의 관계 손상, "
            "언론 역풍 위험을 감수한다. 드물게 강경한 이미지로 역압박에 성공할 수 있다."
        ),
        "effects": effects,
    }


def _walk_out_context_effects(event: dict[str, Any]) -> dict[str, dict[str, int]]:
    stage = str(event.get("stage", ""))
    title = str(event.get("title", ""))
    if stage in {"fundraising", "small_investment", "large_investment"} or "투자" in title:
        return {
            "network": {"investor_network": -3, "distribution_network": -1},
            "reputation": {"investor_reputation": -2},
            "stats": {"financial_risk": 2},
        }
    if stage in {"casting", "star_casting"} or "캐스팅" in title or "배우" in title:
        return {
            "network": {"actor_network": -4, "production_network": -1},
            "reputation": {"industry_reputation": -1},
            "stats": {"casting_fit": -3, "on_set_conflict_risk": 2},
        }
    if stage in {"shooting", "production", "large_scale_production"} or "촬영" in title or "현장" in title:
        return {
            "network": {"production_network": -3, "actor_network": -1},
            "stats": {"schedule_delay_risk": 2, "on_set_conflict_risk": 3},
        }
    if stage in {"marketing", "release", "distribution_release"} or "언론" in title:
        return {
            "network": {"press_network": -3, "distribution_network": -2},
            "stats": {"press_backlash_risk": 3, "pre_release_interest": -2},
        }
    return {}


def _event_context(conn: Any, project_id: str, project: dict[str, Any]) -> dict[str, Any]:
    player = conn.execute("SELECT * FROM player_state WHERE id = 1").fetchone()
    studio = conn.execute("SELECT * FROM studio_state WHERE id = 1").fetchone()
    people = conn.execute(
        """
        SELECT pp.role, pp.status, pp.contribution_json,
               p.id AS person_id, p.type, p.name_ko, p.current_stats_json,
               p.public_profile_json
        FROM project_people pp
        LEFT JOIN people p ON p.id = pp.person_id
        WHERE pp.project_id = ?
        """,
        (project_id,),
    ).fetchall()
    completed_rows = conn.execute(
        """
        SELECT final_audience, break_even_audience
        FROM completed_films
        """
    ).fetchall()

    person_ids = [row["person_id"] for row in people if row["person_id"]]
    trust_values: list[int] = []
    if person_ids:
        placeholders = ", ".join("?" for _ in person_ids)
        relationship_rows = conn.execute(
            f"""
            SELECT target_id, trust, awareness
            FROM relationships
            WHERE target_id IN ({placeholders})
            UNION ALL
            SELECT target_id, trust, awareness
            FROM people_relationships
            WHERE target_id IN ({placeholders})
            """,
            (*person_ids, *person_ids),
        ).fetchall()
        trust_values = [int(row["trust"] or 0) for row in relationship_rows]

    actor_rows = [
        row for row in people
        if row["type"] == "actor" or str(row["role"] or "").endswith("actor")
    ]
    director_rows = [
        row for row in people
        if row["type"] == "director" or str(row["role"] or "") == "director"
    ]
    player_data = dict(player) if player else {}
    studio_data = dict(studio) if studio else {}
    project_stats = loads_json(project.get("stats_json"), {})
    reputation = loads_json(player_data.get("reputation_json"), {}) if player_data else {}
    network = loads_json(player_data.get("network_json"), {}) if player_data else {}
    player_stats = loads_json(player_data.get("stats_json"), {}) if player_data else {}
    current_year = int(player_data.get("current_year") or project.get("created_year") or 2026)

    successful_films = 0
    flop_films = 0
    for row in completed_rows:
        audience = int(row["final_audience"] or 0)
        break_even = int(row["break_even_audience"] or 0)
        if break_even > 0 and audience >= break_even:
            successful_films += 1
        if break_even > 0 and audience < break_even * 0.7:
            flop_films += 1

    return {
        "player": player_data,
        "studio": studio_data,
        "project_stats": project_stats,
        "reputation": reputation,
        "network": network,
        "player_stats": player_stats,
        "current_year": current_year,
        "current_era_id": _era_id(current_year),
        "project_people": [dict(row) for row in people],
        "actor_count": len(actor_rows),
        "director_count": len(director_rows),
        "cast_confirmed": int(project_stats.get("cast_confirmed", 0) or 0),
        "actor_power": _average_people_power(actor_rows),
        "director_power": _average_people_power(director_rows),
        "max_relationship_trust": max(trust_values) if trust_values else 0,
        "min_relationship_trust": min(trust_values) if trust_values else 0,
        "avg_relationship_trust": (sum(trust_values) / len(trust_values)) if trust_values else 0,
        "completed_films": len(completed_rows),
        "successful_films": successful_films,
        "flop_films": flop_films,
        "cash": int((studio_data or player_data).get("cash", 0) or 0),
        "debt": int((studio_data or player_data).get("debt", 0) or 0),
    }


def _average_people_power(rows: list[Any]) -> float:
    values: list[float] = []
    for row in rows:
        contribution = loads_json(row["contribution_json"], {})
        current_stats = loads_json(row["current_stats_json"], {})
        for key in (
            "acting_quality",
            "directing_quality",
            "casting_fit",
            "acting",
            "directing",
            "ticketPower",
            "brandPower",
        ):
            if key in contribution and _is_number(contribution[key]):
                values.append(float(contribution[key]))
            elif key in current_stats and _is_number(current_stats[key]):
                values.append(float(current_stats[key]))
    return sum(values) / len(values) if values else 0


def _era_id(year: int) -> str:
    if year < 1990:
        return "era_1980s"
    if year < 2000:
        return "era_1990s"
    if year < 2010:
        return "era_2000s"
    if year < 2020:
        return "era_2010s"
    return "era_2020s"
