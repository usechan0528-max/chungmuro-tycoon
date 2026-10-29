from __future__ import annotations

import hashlib
import math
import random
import uuid
from typing import Any

from app.database import dumps_json, get_connection, loads_json
from app.services.economic_service import adjust_money_to_year
from app.services.game_state import clamp, money
from app.services.people_service import attach_person_to_project, list_available_people, update_person_project_contract
from app.services.people_stat_service import effective_stats_for_year
from app.services.relationship_service import adjust_relationship, relationship_snapshot


ROLE_LABELS = {
    "director": "감독",
    "lead_actor": "주연 배우",
    "supporting_actor": "조연 배우",
    "cameo_actor": "특별출연",
    "actor": "배우",
    "minor_actor": "단역/소조연",
    "day_player": "단역",
    "background_actor": "이미지/군중",
}

PRINCIPAL_ACTOR_ROLES = {"lead_actor", "supporting_actor", "cameo_actor", "actor"}
AUTOMATIC_ACTOR_ROLES = {"minor_actor", "day_player", "background_actor"}

CASTING_CONFIRMATION_REQUIREMENTS = {
    "scale_short": {"minActors": 1, "minLeadActors": 0},
    "scale_independent": {"minActors": 1, "minLeadActors": 0},
    "scale_low_budget_genre": {"minActors": 1, "minLeadActors": 1},
    "scale_mid_commercial": {"minActors": 2, "minLeadActors": 1},
    "scale_large_commercial": {"minActors": 3, "minLeadActors": 1},
    "scale_tentpole": {"minActors": 3, "minLeadActors": 1},
    "short_film": {"minActors": 1, "minLeadActors": 0},
    "independent_film": {"minActors": 1, "minLeadActors": 0},
    "low_budget_genre": {"minActors": 1, "minLeadActors": 1},
    "mid_commercial": {"minActors": 2, "minLeadActors": 1},
    "large_commercial": {"minActors": 3, "minLeadActors": 1},
    "tentpole_blockbuster": {"minActors": 3, "minLeadActors": 1},
}

AUTO_MINOR_CAST_COUNTS = {
    "scale_short": 1,
    "scale_independent": 2,
    "scale_low_budget_genre": 4,
    "scale_mid_commercial": 6,
    "scale_large_commercial": 9,
    "scale_tentpole": 12,
    "short_film": 1,
    "independent_film": 2,
    "low_budget_genre": 4,
    "mid_commercial": 6,
    "large_commercial": 9,
    "tentpole_blockbuster": 12,
}


LOW_RESOURCE_SCALES = {
    "short_film",
    "independent_film",
    "low_budget_genre",
    "mid_commercial",
    "scale_short",
    "scale_independent",
    "scale_low_budget_genre",
    "scale_mid_commercial",
}

DISCOVERY_OPTIONS = {
    "film_school": {
        "label": "영화과/동아리 신인 발굴",
        "description": "낮은 비용으로 젊은 배우를 찾는다. 잠재력은 높지만 현장 경험은 부족할 수 있다.",
        "minBudget2020": 2_000_000,
        "candidateCount": 3,
        "ageRange": (19, 26),
        "tier": "newcomer",
        "roleType": ["성장형", "연기파"],
        "genreTags": ["indie_art", "romance_melodrama", "social_true_story"],
    },
    "open_audition": {
        "label": "공개 오디션",
        "description": "예산을 들여 넓은 후보군을 본다. 결과 편차가 크지만 의외의 얼굴을 찾을 수 있다.",
        "minBudget2020": 8_000_000,
        "candidateCount": 5,
        "ageRange": (18, 45),
        "tier": "newcomer",
        "roleType": ["성장형"],
        "genreTags": ["indie_art", "family_human_drama", "crime_thriller"],
    },
    "theater_indie": {
        "label": "연극/독립영화판에서 찾기",
        "description": "인지도는 낮지만 기본기가 있는 배우를 찾는다. 저예산 장르와 예술영화에 잘 맞는다.",
        "minBudget2020": 5_000_000,
        "candidateCount": 4,
        "ageRange": (24, 55),
        "tier": "rising",
        "roleType": ["연기파", "성장형"],
        "genreTags": ["indie_art", "social_true_story", "crime_thriller", "horror_occult"],
    },
    "character_pool": {
        "label": "단역/조연 배우 풀 탐색",
        "description": "조연 경험이 있는 배우 중 배역 궁합이 맞는 사람을 찾는다. 스타성보다 현장 안정성이 강점이다.",
        "minBudget2020": 6_000_000,
        "candidateCount": 4,
        "ageRange": (30, 65),
        "tier": "character_actor",
        "roleType": ["신스틸러", "연기파"],
        "genreTags": ["crime_thriller", "comedy", "family_human_drama"],
    },
    "local_nonprofessional": {
        "label": "지역/비전문 배우 캐스팅",
        "description": "지역성과 사실감을 얻을 수 있다. 발성·카메라 적응은 촬영 중 관리가 필요하다.",
        "minBudget2020": 1_500_000,
        "candidateCount": 3,
        "ageRange": (16, 70),
        "tier": "newcomer",
        "roleType": ["성장형"],
        "genreTags": ["indie_art", "social_true_story", "family_human_drama"],
    },
    "sns_model": {
        "label": "SNS/모델 출신 발굴",
        "description": "첫 이미지와 화제성은 좋지만 연기 검증이 약하다. 2010년대 이후 효율이 오른다.",
        "minBudget2020": 10_000_000,
        "candidateCount": 4,
        "ageRange": (18, 32),
        "tier": "newcomer",
        "roleType": ["팬덤형", "성장형"],
        "genreTags": ["romance_melodrama", "horror_occult", "comedy"],
        "minYear": 2010,
    },
}


def list_casting_candidates(person_type: str, year: int | None = None) -> list[dict[str, Any]]:
    return list_available_people(person_type, year or _current_year())


def get_casting_discovery_options(project_id: str) -> list[dict[str, Any]]:
    with get_connection() as conn:
        project = conn.execute(
            """
            SELECT p.*, s.name AS scale_name
            FROM projects p
            JOIN project_scales s ON s.id = p.scale_id
            WHERE p.id = ?
            """,
            (project_id,),
        ).fetchone()
        player = conn.execute("SELECT current_year FROM player_state WHERE id = 1").fetchone()
    if not project or not player:
        return []
    scale_id = str(project["scale_id"] or "")
    if scale_id not in LOW_RESOURCE_SCALES:
        return []
    year = int(player["current_year"])
    options: list[dict[str, Any]] = []
    for option_id, option in DISCOVERY_OPTIONS.items():
        if int(option.get("minYear", 0) or 0) > year:
            continue
        min_budget = adjust_money_to_year(option["minBudget2020"], to_year=year)
        options.append(
            {
                "id": option_id,
                "label": option["label"],
                "description": option["description"],
                "min_budget": min_budget,
                "recommended_budget": int(min_budget * 2),
                "scale_name": project["scale_name"],
            }
        )
    return options


def default_actor_commitment_for_project(project_id: str) -> dict[str, Any]:
    with get_connection() as conn:
        project = conn.execute("SELECT scale_id, stats_json FROM projects WHERE id = ?", (project_id,)).fetchone()
    if not project:
        return {
            "months": 2,
            "shooting_days": 30,
            "label": "촬영 예정 30일 + 준비/홍보 1개월",
        }
    stats = loads_json(project["stats_json"], {})
    shooting_days = int(
        stats.get("shooting_duration")
        or stats.get("planned_shooting_days")
        or 0
    )
    if shooting_days <= 0:
        from app.services.progression_service import stage_time_cost_days_for_project

        shooting_days = int(stage_time_cost_days_for_project("shooting", project["scale_id"], stats))
    months = max(1, min(36, int(math.ceil(max(1, shooting_days) / 30)) + 1))
    return {
        "months": months,
        "shooting_days": shooting_days,
        "label": f"촬영 예정 {shooting_days}일 + 여유 1개월",
    }


def discover_generated_actor_candidates(project_id: str, option_id: str, budget: int) -> list[dict[str, Any]]:
    option = DISCOVERY_OPTIONS.get(option_id)
    if not option:
        raise ValueError("알 수 없는 신인 발굴 방식입니다.")
    with get_connection() as conn:
        project = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
        player = conn.execute("SELECT current_year, current_month FROM player_state WHERE id = 1").fetchone()
        genre = None
        if project:
            genre = conn.execute("SELECT * FROM genres WHERE id = ?", (project["genre_id"],)).fetchone()
        if not project or not player:
            raise ValueError("프로젝트 또는 현재 날짜를 찾을 수 없습니다.")
        if str(project["scale_id"] or "") not in LOW_RESOURCE_SCALES:
            raise ValueError("신인 발굴은 단편, 독립, 저예산, 중간예산 프로젝트에서 주로 사용할 수 있습니다.")
        year = int(player["current_year"])
        month = int(player["current_month"])
        min_budget = adjust_money_to_year(option["minBudget2020"], to_year=year)
        if budget < min_budget:
            raise ValueError(f"이 방식은 최소 {min_budget:,}원 정도의 발굴 예산이 필요합니다.")
        budget_factor = max(0.75, min(1.35, budget / max(min_budget * 2, 1)))
        count = max(2, min(6, int(option["candidateCount"] + (1 if budget_factor >= 1.15 else 0))))
        used_names = {row["name_ko"] for row in conn.execute("SELECT name_ko FROM people").fetchall()}
        generated: list[dict[str, Any]] = []
        for _ in range(count):
            actor = _build_generated_actor(
                option_id=option_id,
                option=option,
                year=year,
                month=month,
                genre_id=str(project["genre_id"] or ""),
                genre_name=str(genre["name"] if genre else ""),
                budget_factor=budget_factor,
                used_names=used_names,
            )
            _insert_generated_actor(conn, actor, project_id, budget, option_id)
            generated.append(actor)
        conn.commit()
    return generated


def auto_fill_minor_cast(
    project_id: str,
    *,
    conn: Any | None = None,
    stats: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if conn is None:
        with get_connection() as own_conn:
            state = _auto_fill_minor_cast(own_conn, project_id, stats=stats)
            own_conn.commit()
            return state
    return _auto_fill_minor_cast(conn, project_id, stats=stats)


def _auto_fill_minor_cast(
    conn: Any,
    project_id: str,
    *,
    stats: dict[str, Any] | None,
) -> dict[str, Any]:
    existing = conn.execute(
        """
        SELECT COUNT(*) AS count
        FROM project_people
        WHERE project_id = ? AND role IN ('minor_actor', 'day_player', 'background_actor')
        """,
        (project_id,),
    ).fetchone()
    if int(existing["count"] or 0) > 0:
        return _minor_cast_state(conn, project_id)

    project = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
    player = conn.execute("SELECT current_year, current_month FROM player_state WHERE id = 1").fetchone()
    if not project or not player:
        return {"filled": False, "count": 0, "summary": "프로젝트 또는 현재 날짜를 찾을 수 없어 단역 자동 충원을 건너뛰었습니다."}

    scale_id = str(project["scale_id"] or "")
    target_count = int(AUTO_MINOR_CAST_COUNTS.get(scale_id, 3))
    if target_count <= 0:
        return {"filled": False, "count": 0, "summary": "이 규모에서는 자동 단역 충원이 필요하지 않습니다."}

    genre = conn.execute("SELECT * FROM genres WHERE id = ?", (project["genre_id"],)).fetchone()
    year = int(player["current_year"])
    month = int(player["current_month"])
    used_names = {row["name_ko"] for row in conn.execute("SELECT name_ko FROM people").fetchall()}
    generated_rows: list[dict[str, Any]] = []
    total_fee = 0
    acting_values: list[int] = []
    role_plan = _minor_role_plan(target_count)

    for index, role in enumerate(role_plan):
        option_id = "character_pool" if role == "minor_actor" else "local_nonprofessional"
        option = DISCOVERY_OPTIONS[option_id]
        actor = _build_generated_actor(
            option_id=option_id,
            option=option,
            year=year,
            month=month,
            genre_id=str(project["genre_id"] or ""),
            genre_name=str(genre["name"] if genre else ""),
            budget_factor=0.82 if role == "minor_actor" else 0.72,
            used_names=used_names,
        )
        actor["statProfile"]["autoMinorCast"] = True
        actor["statProfile"]["sourceProjectId"] = project_id
        actor["publicProfile"]["oneLine"] = _auto_minor_one_line(role)
        fee = _minor_actor_fee(role, year)
        _insert_generated_actor(conn, actor, project_id, fee, "auto_minor_cast")
        contribution = _minor_contribution(actor, role)
        acting_values.append(int(contribution.get("acting_quality", 48)))
        conn.execute(
            """
            INSERT OR REPLACE INTO project_people (
                project_id, person_id, role, contract_fee,
                sequel_option, promotion_obligation, promotion_days,
                schedule_commitment_months, contract_options_json,
                status, contribution_json
            ) VALUES (?, ?, ?, ?, 0, 0, 0, 0, ?, 'attached', ?)
            """,
            (
                project_id,
                actor["id"],
                role,
                fee,
                dumps_json(
                    {
                        "sequelOption": False,
                        "promotionObligation": False,
                        "promotionDays": 0,
                        "scheduleCommitmentMonths": 0,
                        "contractFee": fee,
                        "terms": {"autoMinorCast": True},
                    }
                ),
                dumps_json(contribution),
            ),
        )
        conn.execute(
            """
            INSERT INTO people_career_timeline (
                person_id, project_id, role, year, month, status, result_json
            ) VALUES (?, ?, ?, ?, ?, 'auto_minor_cast', ?)
            """,
            (
                actor["id"],
                project_id,
                role,
                year,
                month,
                dumps_json({"summary": f"{ROLE_LABELS.get(role, role)} 자동 충원"}),
            ),
        )
        generated_rows.append({"id": actor["id"], "name": actor["nameKo"], "role": role, "fee": fee})
        total_fee += fee

    project_stats = stats if stats is not None else loads_json(project["stats_json"], {})
    average_acting = sum(acting_values) / max(1, len(acting_values))
    project_stats["acting_quality"] = clamp(float(project_stats.get("acting_quality", 50)) * 0.94 + average_acting * 0.06)
    project_stats["casting_fit"] = clamp(float(project_stats.get("casting_fit", 50)) + min(4, target_count * 0.35))
    project_stats["minor_cast_auto_filled"] = target_count
    project_stats["minor_cast_cost"] = total_fee
    project_stats["minor_cast_summary"] = _minor_cast_summary(target_count, total_fee)
    payload = dumps_json(project_stats)
    conn.execute("UPDATE projects SET stats_json = ? WHERE id = ?", (payload, project_id))
    conn.execute("UPDATE production_projects SET stats_json = ? WHERE id = ?", (payload, project_id))
    return {
        "filled": True,
        "count": target_count,
        "total_fee": total_fee,
        "summary": project_stats["minor_cast_summary"],
        "rows": generated_rows,
    }


def attach_casting(
    project_id: str,
    person_id: str,
    role: str,
    *,
    contract_fee: int = 0,
    commitment_months: int = 0,
    sequel_option: bool = False,
    promotion_obligation: bool = False,
    promotion_days: int = 0,
    contract_terms: dict[str, Any] | None = None,
) -> dict[str, Any]:
    negotiation = negotiate_casting_offer(
        project_id,
        person_id,
        role,
        contract_fee=contract_fee,
        commitment_months=commitment_months,
        sequel_option=sequel_option,
        promotion_obligation=promotion_obligation,
        promotion_days=promotion_days,
        contract_terms=contract_terms,
    )
    if negotiation["accepted"]:
        attach_person_to_project(
            project_id,
            person_id,
            role,
            contract_fee=contract_fee,
            commitment_months=commitment_months,
            sequel_option=sequel_option,
            promotion_obligation=promotion_obligation,
            promotion_days=promotion_days,
            contract_terms=contract_terms,
        )
    return {
        **negotiation,
        "casting": get_project_casting(project_id),
    }


def negotiate_casting_offer(
    project_id: str,
    person_id: str,
    role: str,
    *,
    contract_fee: int = 0,
    commitment_months: int = 0,
    sequel_option: bool = False,
    promotion_obligation: bool = False,
    promotion_days: int = 0,
    contract_terms: dict[str, Any] | None = None,
) -> dict[str, Any]:
    with get_connection() as conn:
        project = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
        person = conn.execute("SELECT * FROM people WHERE id = ?", (person_id,)).fetchone()
        player = conn.execute("SELECT current_year, current_month FROM player_state WHERE id = 1").fetchone()
        if not project or not person or not player:
            raise ValueError("협상할 프로젝트 또는 인물을 찾을 수 없습니다.")
        year = int(player["current_year"])
        relationship = conn.execute(
            """
            SELECT trust, awareness
            FROM relationships
            WHERE target_id = ? AND target_type = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (person_id, person["type"]),
        ).fetchone()
        relation = relationship_snapshot(
            relationship["trust"] if relationship else 0,
            relationship["awareness"] if relationship else 0,
        )
        person_data = dict(person)
        project_data = dict(project)
        stats = effective_stats_for_year(person_data, year)
        profile = loads_json(person_data.get("stat_profile_json"), {})
        expected_fee = _role_adjusted_expected_fee(
            _expected_contract_fee(person_data, stats, profile, year),
            role,
        )
        terms = _terms_for_negotiation(contract_terms or {})
        offer_value = _effective_offer_value(int(contract_fee or 0), terms, project_data)
        score, notes = _negotiation_score(
            person=person_data,
            project=project_data,
            role=role,
            stats=stats,
            profile=profile,
            expected_fee=expected_fee,
            offer_value=offer_value,
            relationship=relation,
            commitment_months=int(commitment_months or 0),
            sequel_option=sequel_option,
            promotion_obligation=promotion_obligation,
            promotion_days=int(promotion_days or 0),
            terms=terms,
        )
        score += _deterministic_negotiation_roll(project_id, person_id, role, int(contract_fee or 0), terms)
        accepted = score >= 55
        lowball = offer_value < expected_fee * 0.28 and str(person_data.get("protection_level") or "") != "generated"
        if lowball:
            accepted = False
            notes.insert(0, "제시 조건이 상대가 기대하는 최소선에 크게 못 미쳤다.")
        trust_delta = 1 if accepted else -2 if lowball else -1
        awareness_delta = 5 if accepted else 3
        adjust_relationship(
            conn,
            person_id,
            person["type"],
            trust_delta=trust_delta,
            awareness_delta=awareness_delta,
            last_contact_year=year,
        )
        _record_negotiation_log(
            conn,
            project_id=project_id,
            person_id=person_id,
            role=role,
            accepted=accepted,
            notes=notes,
            year=year,
            month=int(player["current_month"]),
            contract_fee=int(contract_fee or 0),
            terms=terms,
        )
        conn.commit()
    return {
        "accepted": accepted,
        "person_id": person_id,
        "name": person["name_ko"],
        "role": role,
        "result_text": _negotiation_result_text(str(person["name_ko"]), role, accepted, notes, offer_value, expected_fee),
        "notes": notes[:4],
    }


def update_casting_contract(
    project_id: str,
    person_id: str,
    role: str,
    *,
    contract_fee: int = 0,
    commitment_months: int = 0,
    sequel_option: bool = False,
    promotion_obligation: bool = False,
    promotion_days: int = 0,
    contract_terms: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    update_person_project_contract(
        project_id,
        person_id,
        role,
        contract_fee=contract_fee,
        commitment_months=commitment_months,
        sequel_option=sequel_option,
        promotion_obligation=promotion_obligation,
        promotion_days=promotion_days,
        contract_terms=contract_terms,
    )
    return get_project_casting(project_id)


def casting_confirmation_status(project_id: str) -> dict[str, Any]:
    with get_connection() as conn:
        project = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
        if not project:
            raise ValueError("프로젝트를 찾을 수 없습니다.")
        stats = loads_json(project["stats_json"], {})
        rows = conn.execute(
            """
            SELECT pp.role, pp.status, p.name_ko, p.type
            FROM project_people pp
            JOIN people p ON p.id = pp.person_id
            WHERE pp.project_id = ?
            ORDER BY pp.role, p.name_ko
            """,
            (project_id,),
        ).fetchall()
        pending_count = conn.execute(
            """
            SELECT COUNT(*) AS count
            FROM casting_offers
            WHERE project_id = ? AND status = 'pending'
            """,
            (project_id,),
        ).fetchone()["count"]
    actor_rows = [
        row for row in rows
        if row["type"] == "actor" and str(row["role"] or "") in PRINCIPAL_ACTOR_ROLES
    ]
    lead_rows = [row for row in actor_rows if str(row["role"] or "") == "lead_actor"]
    requirement = CASTING_CONFIRMATION_REQUIREMENTS.get(
        str(project["scale_id"] or ""),
        {"minActors": 1, "minLeadActors": 0},
    )
    min_actors = int(requirement["minActors"])
    min_leads = int(requirement["minLeadActors"])
    missing: list[str] = []
    if len(actor_rows) < min_actors:
        missing.append(f"배우 {min_actors - len(actor_rows)}명")
    if len(lead_rows) < min_leads:
        missing.append("주연 배우")
    if int(pending_count or 0) > 0:
        missing.append("답변 대기 중인 제안 정리")
    is_confirmed = int(stats.get("cast_confirmed", 0) or 0) > 0
    can_confirm = not is_confirmed and not missing
    cast_names = [str(row["name_ko"]) for row in actor_rows[:5]]
    if len(actor_rows) > 5:
        cast_names.append(f"외 {len(actor_rows) - 5}명")
    if is_confirmed:
        summary = stats.get("cast_summary_text") or "공식 출연진이 확정되어 제작 발표가 가능한 상태입니다."
    elif missing:
        summary = "출연진 확정 전입니다. " + ", ".join(missing) + "이 필요합니다."
    else:
        summary = "현재 확정 계약만으로 공식 출연진을 확정할 수 있습니다."
    return {
        "is_confirmed": is_confirmed,
        "can_confirm": can_confirm,
        "actor_count": len(actor_rows),
        "lead_actor_count": len(lead_rows),
        "director_count": len([row for row in rows if row["type"] == "director" or row["role"] == "director"]),
        "pending_count": int(pending_count or 0),
        "required_actor_count": min_actors,
        "required_lead_actor_count": min_leads,
        "missing": missing,
        "cast_names": cast_names,
        "summary": summary,
        "confirmed_date": {
            "year": stats.get("cast_confirmed_year"),
            "month": stats.get("cast_confirmed_month"),
            "day": stats.get("cast_confirmed_day"),
        },
    }


def confirm_project_casting(project_id: str) -> dict[str, Any]:
    from app.services.calendar_service import add_calendar_event, current_game_date

    status = casting_confirmation_status(project_id)
    if status["is_confirmed"]:
        return status
    if not status["can_confirm"]:
        raise ValueError("출연진을 아직 확정할 수 없습니다. " + ", ".join(status["missing"]))
    today = current_game_date()
    cast_line = ", ".join(status["cast_names"]) if status["cast_names"] else "주요 출연진"
    summary = f"{cast_line} 기준으로 공식 출연진을 확정했습니다. 이제 제작 발표회를 열 수 있습니다."
    with get_connection() as conn:
        project = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
        if not project:
            raise ValueError("프로젝트를 찾을 수 없습니다.")
        stats = loads_json(project["stats_json"], {})
        stats.update(
            {
                "cast_confirmed": 1,
                "cast_confirmed_year": today[0],
                "cast_confirmed_month": today[1],
                "cast_confirmed_day": today[2],
                "cast_confirmed_actor_count": int(status["actor_count"]),
                "cast_confirmed_lead_actor_count": int(status["lead_actor_count"]),
                "cast_summary_text": summary,
                "pre_release_interest": int(stats.get("pre_release_interest", 50) or 50) + 2,
                "production_announcement_ready": 1,
            }
        )
        conn.execute(
            "UPDATE project_people SET status = 'cast_confirmed' WHERE project_id = ? AND status = 'attached'",
            (project_id,),
        )
        conn.execute("UPDATE projects SET stats_json = ? WHERE id = ?", (dumps_json(stats), project_id))
        conn.execute("UPDATE production_projects SET stats_json = ? WHERE id = ?", (dumps_json(stats), project_id))
        rows = conn.execute(
            "SELECT person_id, role FROM project_people WHERE project_id = ?",
            (project_id,),
        ).fetchall()
        for row in rows:
            conn.execute(
                """
                INSERT INTO people_career_timeline (
                    person_id, project_id, role, year, month, status, result_json
                ) VALUES (?, ?, ?, ?, ?, 'cast_confirmed', ?)
                """,
                (
                    row["person_id"],
                    project_id,
                    row["role"],
                    today[0],
                    today[1],
                    dumps_json({"summary": summary}),
                ),
            )
        conn.commit()
    add_calendar_event(
        title=f"{project['title']}: 출연진 확정",
        event_type="cast_confirmation",
        start=today,
        end=today,
        project_id=project_id,
        description=summary,
        metadata={
            "actorCount": status["actor_count"],
            "leadActorCount": status["lead_actor_count"],
            "castNames": status["cast_names"],
        },
    )
    return casting_confirmation_status(project_id)


def get_project_casting(project_id: str) -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT pp.*, p.name_ko, p.name_en, p.type, p.public_profile_json,
                   (
                       SELECT r.trust
                       FROM relationships r
                       WHERE r.target_id = p.id AND r.target_type = p.type
                       ORDER BY r.id DESC
                       LIMIT 1
                   ) AS relationship_trust,
                   (
                       SELECT r.awareness
                       FROM relationships r
                       WHERE r.target_id = p.id AND r.target_type = p.type
                       ORDER BY r.id DESC
                       LIMIT 1
                   ) AS relationship_awareness
            FROM project_people pp
            JOIN people p ON p.id = pp.person_id
            WHERE pp.project_id = ?
            ORDER BY
                CASE pp.role
                    WHEN 'director' THEN 0
                    WHEN 'lead_actor' THEN 1
                    WHEN 'supporting_actor' THEN 2
                    WHEN 'cameo_actor' THEN 3
                    WHEN 'minor_actor' THEN 4
                    WHEN 'day_player' THEN 5
                    WHEN 'background_actor' THEN 6
                    ELSE 9
                END,
                p.name_ko
            """,
            (project_id,),
        ).fetchall()
    return [_public_casting_row(row) for row in rows]


def submit_casting_offer(
    project_id: str,
    person_id: str,
    role: str,
    *,
    contract_fee: int = 0,
    commitment_months: int = 0,
    sequel_option: bool = False,
    promotion_obligation: bool = False,
    promotion_days: int = 0,
    contract_terms: dict[str, Any] | None = None,
) -> dict[str, Any]:
    from app.services.calendar_service import add_calendar_event, add_days_to_date, current_game_date

    terms = _terms_for_negotiation(contract_terms or {})
    sent = current_game_date()
    with get_connection() as conn:
        project = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
        person = conn.execute("SELECT * FROM people WHERE id = ?", (person_id,)).fetchone()
        if not project or not person:
            raise ValueError("협상 제안을 보낼 프로젝트 또는 인물을 찾을 수 없습니다.")
        existing = conn.execute(
            """
            SELECT 1
            FROM project_people
            WHERE project_id = ? AND person_id = ? AND role = ?
            """,
            (project_id, person_id, role),
        ).fetchone()
        if existing:
            raise ValueError("이미 확정된 계약입니다. 조건 변경은 계약 수정에서 진행하세요.")
        year = sent[0]
        stats = effective_stats_for_year(dict(person), year)
        profile = loads_json(person["stat_profile_json"], {})
        delay_days = _casting_response_delay_days(stats, profile)
        due = add_days_to_date(sent, delay_days)
        offer_id = f"casting_offer_{uuid.uuid4().hex[:12]}"
        conn.execute(
            """
            UPDATE casting_offers
            SET status = 'superseded', popup_seen = 1
            WHERE status = 'pending'
              AND project_id = ?
              AND person_id = ?
              AND role = ?
            """,
            (project_id, person_id, role),
        )
        conn.execute(
            """
            INSERT INTO casting_offers (
                id, project_id, person_id, role, contract_fee,
                commitment_months, sequel_option, promotion_obligation,
                promotion_days, contract_terms_json, status,
                sent_year, sent_month, sent_day,
                response_due_year, response_due_month, response_due_day,
                popup_seen
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?, ?, ?, ?, ?, 1)
            """,
            (
                offer_id,
                project_id,
                person_id,
                role,
                int(contract_fee or 0),
                int(commitment_months or 0),
                1 if sequel_option else 0,
                1 if promotion_obligation else 0,
                int(promotion_days or 0),
                dumps_json(terms),
                sent[0],
                sent[1],
                sent[2],
                due[0],
                due[1],
                due[2],
            ),
        )
        _record_offer_sent_log(
            conn,
            project_id=project_id,
            person_id=person_id,
            role=role,
            year=sent[0],
            month=sent[1],
            day=sent[2],
            contract_fee=int(contract_fee or 0),
            terms=terms,
            due=due,
        )
        conn.commit()

    add_calendar_event(
        title=f"{person['name_ko']} 측 캐스팅 답변 예정",
        event_type="casting_response",
        start=due,
        end=due,
        project_id=project_id,
        description="상대 측이 출연 제안 조건을 검토해 답변할 예정입니다.",
        metadata={"offerId": offer_id, "personId": person_id, "role": role},
    )
    return {
        "offer_id": offer_id,
        "person_id": person_id,
        "name": person["name_ko"],
        "role": role,
        "due": {"year": due[0], "month": due[1], "day": due[2]},
        "result_text": (
            f"{person['name_ko']} 측에 {ROLE_LABELS.get(role, role)} 제안을 보냈습니다.\n"
            f"답변 예상일: {due[0]}년 {due[1]}월 {due[2]}일"
        ),
    }


def process_due_casting_offers() -> list[dict[str, Any]]:
    from app.services.calendar_service import current_game_date

    today = current_game_date()
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM casting_offers
            WHERE status = 'pending'
            ORDER BY response_due_year, response_due_month, response_due_day, created_at
            """
        ).fetchall()
    due_rows = [
        dict(row)
        for row in rows
        if _date_index(
            (
                int(row["response_due_year"] or 9999),
                int(row["response_due_month"] or 12),
                int(row["response_due_day"] or 31),
            )
        )
        <= _date_index(today)
    ]
    resolved: list[dict[str, Any]] = []
    for offer in due_rows:
        try:
            terms = loads_json(offer.get("contract_terms_json"), {})
            result = attach_casting(
                str(offer["project_id"]),
                str(offer["person_id"]),
                str(offer["role"]),
                contract_fee=int(offer["contract_fee"] or 0),
                commitment_months=int(offer["commitment_months"] or 0),
                sequel_option=bool(offer["sequel_option"]),
                promotion_obligation=bool(offer["promotion_obligation"]),
                promotion_days=int(offer["promotion_days"] or 0),
                contract_terms=terms,
            )
            accepted = bool(result.get("accepted"))
            result_text = str(result.get("result_text") or "")
            notes = result.get("notes") or []
        except Exception as exc:
            accepted = False
            result_text = f"상대 측 검토 중 일정 또는 조건 문제가 생겨 제안이 성사되지 않았습니다.\n- {exc}"
            notes = [str(exc)]
        with get_connection() as conn:
            conn.execute(
                """
                UPDATE casting_offers
                SET status = ?,
                    responded_year = ?,
                    responded_month = ?,
                    responded_day = ?,
                    accepted = ?,
                    result_text = ?,
                    notes_json = ?,
                    popup_seen = 0
                WHERE id = ?
                """,
                (
                    "accepted" if accepted else "rejected",
                    today[0],
                    today[1],
                    today[2],
                    1 if accepted else 0,
                    result_text,
                    dumps_json(notes),
                    offer["id"],
                ),
            )
            conn.commit()
        resolved.append({"id": offer["id"], "accepted": accepted, "result_text": result_text})
    return resolved


def list_pending_casting_offers(project_id: str | None = None) -> list[dict[str, Any]]:
    where = "WHERE co.status = 'pending'"
    params: tuple[Any, ...] = ()
    if project_id:
        where += " AND co.project_id = ?"
        params = (project_id,)
    with get_connection() as conn:
        rows = conn.execute(
            f"""
            SELECT co.*, p.name_ko, p.name_en, p.type, pr.title AS project_title
            FROM casting_offers co
            JOIN people p ON p.id = co.person_id
            JOIN projects pr ON pr.id = co.project_id
            {where}
            ORDER BY co.response_due_year, co.response_due_month, co.response_due_day, p.name_ko
            """,
            params,
        ).fetchall()
    return [_public_offer_row(row) for row in rows]


def list_unseen_casting_responses(limit: int = 8) -> list[dict[str, Any]]:
    process_due_casting_offers()
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT co.*, p.name_ko, p.name_en, p.type, pr.title AS project_title
            FROM casting_offers co
            JOIN people p ON p.id = co.person_id
            JOIN projects pr ON pr.id = co.project_id
            WHERE co.status IN ('accepted', 'rejected')
              AND co.popup_seen = 0
            ORDER BY co.responded_year, co.responded_month, co.responded_day, co.created_at
            LIMIT ?
            """,
            (int(limit),),
        ).fetchall()
    return [_public_offer_row(row) for row in rows]


def mark_casting_responses_seen(offer_ids: list[str]) -> None:
    if not offer_ids:
        return
    placeholders = ", ".join("?" for _ in offer_ids)
    with get_connection() as conn:
        conn.execute(
            f"UPDATE casting_offers SET popup_seen = 1 WHERE id IN ({placeholders})",
            tuple(offer_ids),
        )
        conn.commit()


def _expected_contract_fee(person: dict[str, Any], stats: dict[str, Any], profile: dict[str, Any], year: int) -> int:
    tier = str(profile.get("tier") or "")
    if person.get("type") == "director":
        base_2020 = {
            "legend": 700_000_000,
            "global_auteur": 900_000_000,
            "commercial_master": 800_000_000,
            "auteur": 350_000_000,
            "genre_master": 300_000_000,
            "solid_commercial": 250_000_000,
            "indie_festival": 90_000_000,
            "rising_director": 70_000_000,
            "veteran": 180_000_000,
        }.get(tier, 120_000_000)
        cost_level = _average(stats, ("costLevel", "commercialSense", "festivalPower", "globalRecognition"))
    else:
        base_2020 = {
            "legend": 900_000_000,
            "top_star": 1_000_000_000,
            "a_list": 550_000_000,
            "solid_lead": 250_000_000,
            "character_actor": 120_000_000,
            "rising": 70_000_000,
            "newcomer": 20_000_000,
            "veteran": 180_000_000,
        }.get(tier, 90_000_000)
        cost_level = _average(stats, ("costLevel", "ticketPower", "brandPower"))
    base = adjust_money_to_year(base_2020, to_year=year)
    multiplier = max(0.45, min(1.65, float(cost_level or 45) / 70))
    if profile.get("generated"):
        multiplier *= 0.65
    return max(1_000_000, int(base * multiplier))


def _role_adjusted_expected_fee(base_fee: int, role: str) -> int:
    multiplier = {
        "lead_actor": 1.0,
        "supporting_actor": 0.55,
        "cameo_actor": 0.2,
        "minor_actor": 0.06,
        "day_player": 0.02,
        "background_actor": 0.01,
        "actor": 0.45,
        "director": 1.0,
    }.get(role, 1.0)
    return max(300_000, int(int(base_fee or 0) * multiplier))


def _terms_for_negotiation(terms: dict[str, Any]) -> dict[str, Any]:
    running = terms.get("runningGuarantee") if isinstance(terms.get("runningGuarantee"), dict) else {}
    bonus = terms.get("boxOfficeBonus") if isinstance(terms.get("boxOfficeBonus"), dict) else {}
    return {
        "deferredFee": max(0, int(terms.get("deferredFee") or 0)),
        "runningGuarantee": {
            "enabled": bool(running.get("enabled")),
            "rate": max(0.0, min(0.2, float(running.get("rate") or 0))),
            "trigger": str(running.get("trigger") or "break_even"),
        },
        "boxOfficeBonus": {
            "enabled": bool(bonus.get("enabled")),
            "audience": max(0, int(bonus.get("audience") or 0)),
            "amount": max(0, int(bonus.get("amount") or 0)),
        },
        "imageRights": bool(terms.get("imageRights")),
    }


def _effective_offer_value(contract_fee: int, terms: dict[str, Any], project: dict[str, Any]) -> int:
    running = terms.get("runningGuarantee") if isinstance(terms.get("runningGuarantee"), dict) else {}
    bonus = terms.get("boxOfficeBonus") if isinstance(terms.get("boxOfficeBonus"), dict) else {}
    production_budget = int(project.get("production_budget") or 0)
    running_value = int(production_budget * 0.22 * float(running.get("rate") or 0)) if running.get("enabled") else 0
    bonus_value = int(int(bonus.get("amount") or 0) * 0.45) if bonus.get("enabled") else 0
    deferred_value = int(int(terms.get("deferredFee") or 0) * 0.65)
    image_value = int(production_budget * 0.005) if terms.get("imageRights") else 0
    return max(0, int(contract_fee or 0) + deferred_value + running_value + bonus_value + image_value)


def _negotiation_score(
    *,
    person: dict[str, Any],
    project: dict[str, Any],
    role: str,
    stats: dict[str, Any],
    profile: dict[str, Any],
    expected_fee: int,
    offer_value: int,
    relationship: dict[str, Any],
    commitment_months: int,
    sequel_option: bool,
    promotion_obligation: bool,
    promotion_days: int,
    terms: dict[str, Any],
) -> tuple[float, list[str]]:
    ratio = offer_value / max(1, expected_fee)
    score = 42 + (ratio - 0.72) * 62
    notes: list[str] = []
    if ratio >= 1.05:
        notes.append("제시 조건이 상대 측 기대치에 근접하거나 그 이상으로 보였다.")
    elif ratio >= 0.72:
        notes.append("기본 조건은 검토 가능한 수준이지만 완전히 여유롭지는 않았다.")
    else:
        notes.append("출연료와 후지급 조건이 상대 측 기대보다 낮게 보였다.")

    trust = int(relationship.get("trust") or 0)
    awareness = int(relationship.get("awareness") or 0)
    score += trust * 0.18 + awareness * 0.05
    if trust >= 20:
        notes.append("기존 관계가 협상장을 부드럽게 만들었다.")
    elif trust < -20:
        notes.append("이전 접점의 불편함이 조건 검토에 악영향을 줬다.")

    schedule_difficulty = float(stats.get("scheduleDifficulty") or 35)
    score -= max(0, commitment_months - 3) * 3
    score -= max(0, schedule_difficulty - 70) * 0.16
    if commitment_months >= 6:
        notes.append("장기 일정 구속은 상대에게 부담으로 받아들여졌다.")
    if promotion_obligation and promotion_days >= 10:
        score -= min(8, promotion_days / 3)
        notes.append("홍보 일정이 길어 스케줄 부담이 커졌다.")
    elif promotion_obligation:
        score -= 1

    running = terms.get("runningGuarantee") if isinstance(terms.get("runningGuarantee"), dict) else {}
    if running.get("enabled") and float(running.get("rate") or 0) > 0:
        score += min(8, float(running["rate"]) * 180)
        notes.append("러닝 개런티가 흥행 참여 동기를 만들었다.")
    bonus = terms.get("boxOfficeBonus") if isinstance(terms.get("boxOfficeBonus"), dict) else {}
    if bonus.get("enabled") and int(bonus.get("amount") or 0) > 0:
        score += 3
        notes.append("흥행 보너스가 협상 조건을 조금 보강했다.")
    if int(terms.get("deferredFee") or 0) > 0:
        score -= 2
        notes.append("이연 지급은 당장 받는 금액보다 불확실하게 받아들여졌다.")
    if terms.get("imageRights"):
        score += 2

    person_type = str(person.get("type") or "")
    tier = str(profile.get("tier") or "")
    scale_id = str(project.get("scale_id") or "")
    if person_type == "actor" and role == "supporting_actor" and tier in {"legend", "top_star", "a_list"}:
        score -= 10
        notes.append("배역 비중이 상대의 현재 위상에 비해 작게 느껴졌다.")
    if person_type == "actor" and role == "cameo_actor":
        if commitment_months <= 1:
            score += 8
            notes.append("짧은 특별출연 조건이라 스케줄 부담이 낮았다.")
        if promotion_obligation and promotion_days > 3:
            score -= 5
            notes.append("특별출연에 비해 홍보 의무가 길게 느껴졌다.")
    if profile.get("generated") or tier in {"newcomer", "rising", "rising_director"}:
        score += 10
        notes.append("기회 자체가 커리어에 도움이 된다는 판단이 있었다.")
    if scale_id in {"scale_short", "short_film", "scale_independent", "independent_film"} and tier in {"legend", "top_star"}:
        score -= 12
        notes.append("프로젝트 규모가 상대의 통상 활동 반경보다 작았다.")
    if sequel_option and person_type == "actor":
        score += 2
    return score, notes


def _deterministic_negotiation_roll(project_id: str, person_id: str, role: str, contract_fee: int, terms: dict[str, Any]) -> int:
    payload = f"{project_id}|{person_id}|{role}|{contract_fee}|{dumps_json(terms)}"
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return int(digest[:4], 16) % 19 - 9


def _record_negotiation_log(
    conn: Any,
    *,
    project_id: str,
    person_id: str,
    role: str,
    accepted: bool,
    notes: list[str],
    year: int,
    month: int,
    contract_fee: int,
    terms: dict[str, Any],
) -> None:
    conn.execute(
        """
        INSERT INTO production_stage_logs (
            event_id, category, project_id, choice_id, choice_text,
            year, month, effects_json
        ) VALUES (?, 'casting_negotiation', ?, ?, ?, ?, ?, ?)
        """,
        (
            f"casting_offer_{person_id}",
            project_id,
            "accepted" if accepted else "rejected",
            f"{ROLE_LABELS.get(role, role)} 계약 {'수락' if accepted else '거절'}",
            year,
            month,
            dumps_json(
                {
                    "personId": person_id,
                    "role": role,
                    "accepted": accepted,
                    "contractFee": contract_fee,
                    "terms": terms,
                    "notes": notes[:4],
                }
            ),
        ),
    )


def _record_offer_sent_log(
    conn: Any,
    *,
    project_id: str,
    person_id: str,
    role: str,
    year: int,
    month: int,
    day: int,
    contract_fee: int,
    terms: dict[str, Any],
    due: tuple[int, int, int],
) -> None:
    conn.execute(
        """
        INSERT INTO production_stage_logs (
            event_id, category, project_id, choice_id, choice_text,
            year, month, effects_json
        ) VALUES (?, 'casting_offer', ?, 'sent', ?, ?, ?, ?)
        """,
        (
            f"casting_offer_sent_{person_id}",
            project_id,
            f"{ROLE_LABELS.get(role, role)} 제안 발송",
            year,
            month,
            dumps_json(
                {
                    "personId": person_id,
                    "role": role,
                    "contractFee": contract_fee,
                    "terms": terms,
                    "sent": {"year": year, "month": month, "day": day},
                    "due": {"year": due[0], "month": due[1], "day": due[2]},
                }
            ),
        ),
    )


def _casting_response_delay_days(stats: dict[str, Any], profile: dict[str, Any]) -> int:
    tier = str(profile.get("tier") or "")
    schedule = float(stats.get("scheduleDifficulty") or 35)
    delay = 1
    if schedule >= 60:
        delay += 1
    if schedule >= 80:
        delay += 1
    if tier in {"legend", "top_star", "global_auteur", "commercial_master"}:
        delay += 1
    if profile.get("generated") or tier in {"newcomer", "rising", "rising_director"}:
        delay = max(1, delay - 1)
    return max(1, min(5, delay))


def _date_index(date_value: tuple[int, int, int]) -> int:
    year, month, day = date_value
    return year * 372 + month * 31 + day


def _public_offer_row(row: Any) -> dict[str, Any]:
    terms = loads_json(row["contract_terms_json"], {})
    status = str(row["status"] or "pending")
    return {
        "id": row["id"],
        "project_id": row["project_id"],
        "project_title": row["project_title"],
        "person_id": row["person_id"],
        "name_ko": row["name_ko"],
        "name_en": row["name_en"],
        "person_type": row["type"],
        "role": row["role"],
        "role_label": ROLE_LABELS.get(row["role"], row["role"]),
        "status": status,
        "status_label": {
            "pending": "답변 대기",
            "accepted": "수락",
            "rejected": "거절",
            "superseded": "새 제안으로 대체",
        }.get(status, status),
        "contract_fee": int(row["contract_fee"] or 0),
        "commitment_months": int(row["commitment_months"] or 0),
        "sequel_option": bool(row["sequel_option"]),
        "promotion_obligation": bool(row["promotion_obligation"]),
        "promotion_days": int(row["promotion_days"] or 0),
        "contract_terms": terms,
        "sent_date_text": _date_text(row["sent_year"], row["sent_month"], row["sent_day"]),
        "due_date_text": _date_text(row["response_due_year"], row["response_due_month"], row["response_due_day"]),
        "responded_date_text": _date_text(row["responded_year"], row["responded_month"], row["responded_day"]),
        "accepted": bool(row["accepted"]) if row["accepted"] is not None else None,
        "result_text": row["result_text"] or "",
        "notes": loads_json(row["notes_json"], []),
        "offer_text": _offer_text(row, terms),
    }


def _date_text(year: Any, month: Any, day: Any) -> str:
    if not year or not month or not day:
        return "-"
    return f"{int(year)}.{int(month):02d}.{int(day):02d}"


def _offer_text(row: Any, terms: dict[str, Any]) -> str:
    parts = [f"계약금 {money(row['contract_fee'])}"]
    months = int(row["commitment_months"] or 0)
    if months:
        parts.append(f"일정 구속 {months}개월")
    if row["promotion_obligation"]:
        parts.append(f"홍보 {int(row['promotion_days'] or 0)}일")
    if row["sequel_option"]:
        parts.append("후속작 옵션")
    running = terms.get("runningGuarantee") if isinstance(terms.get("runningGuarantee"), dict) else {}
    if running.get("enabled"):
        parts.append(f"러닝 {float(running.get('rate') or 0) * 100:.1f}%")
    bonus = terms.get("boxOfficeBonus") if isinstance(terms.get("boxOfficeBonus"), dict) else {}
    if bonus.get("enabled") and int(bonus.get("amount") or 0) > 0:
        parts.append(f"흥행 보너스 {money(bonus.get('amount'))}")
    deferred = int(terms.get("deferredFee") or 0)
    if deferred:
        parts.append(f"이연 {money(deferred)}")
    return " · ".join(parts)


def _negotiation_result_text(
    name: str,
    role: str,
    accepted: bool,
    notes: list[str],
    offer_value: int,
    expected_fee: int,
) -> str:
    role_label = ROLE_LABELS.get(role, role)
    opening = (
        f"{name} 측이 {role_label} 제안을 수락했습니다. 이제 확정 출연진에 반영됩니다."
        if accepted
        else f"{name} 측이 {role_label} 제안을 보류했습니다. 아직 확정 출연진에는 반영되지 않습니다."
    )
    temperature = "조건 반응: "
    if offer_value >= expected_fee:
        temperature += "상대가 진지하게 검토할 만한 제안으로 받아들였습니다."
    elif offer_value >= expected_fee * 0.65:
        temperature += "협상 여지는 있었지만 몇 가지 조건 보완을 원했습니다."
    else:
        temperature += "조건 격차가 커서 추가 설득이 필요해 보였습니다."
    body = "\n".join(f"- {note}" for note in notes[:3])
    return f"{opening}\n\n{temperature}\n{body}"


def _average(values: dict[str, Any], keys: tuple[str, ...]) -> float:
    picked = [float(values.get(key) or 0) for key in keys if values.get(key) is not None]
    return sum(picked) / len(picked) if picked else 0.0


def _current_year() -> int:
    with get_connection() as conn:
        row = conn.execute("SELECT current_year FROM player_state WHERE id = 1").fetchone()
    return int(row["current_year"]) if row else 2026


def _build_generated_actor(
    *,
    option_id: str,
    option: dict[str, Any],
    year: int,
    month: int,
    genre_id: str,
    genre_name: str,
    budget_factor: float,
    used_names: set[str],
) -> dict[str, Any]:
    age_min, age_max = option["ageRange"]
    age = random.randint(int(age_min), int(age_max))
    birth_year = year - age + 1
    name = _generated_korean_name(year, used_names)
    archetype = _actor_archetype(option_id)
    current_stats = _generated_actor_stats(archetype, budget_factor)
    potential_stats = {
        key: min(100, max(int(value) + random.randint(5, 22), 48))
        for key, value in current_stats.items()
    }
    potential_stats["growthPotential"] = min(100, max(potential_stats.get("growthPotential", 70), current_stats.get("growthPotential", 70) + 8))
    genre_tags = list(dict.fromkeys([_genre_tag_from_id(genre_id), *option.get("genreTags", [])]))
    genre_fit = _generated_genre_fit(genre_id, genre_tags, archetype)
    role_type = list(dict.fromkeys([*option.get("roleType", []), *archetype["roleType"]]))
    actor_id = f"generated_actor_{year}_{month:02d}_{uuid.uuid4().hex[:8]}"
    profile = _generated_actor_profile(
        name=name,
        option_label=str(option["label"]),
        archetype=archetype,
        genre_name=genre_name,
        current_stats=current_stats,
        potential_stats=potential_stats,
    )
    stat_profile = {
        "tier": option.get("tier", "newcomer"),
        "roleType": role_type,
        "genreTags": genre_tags,
        "peakEras": [{"start": year + 3, "end": year + random.randint(6, 11), "modifiers": {"acting": 1.04, "brandPower": 1.03}}],
        "manualOverride": False,
        "generated": True,
        "originType": option_id,
        "generatedAt": {"year": year, "month": month},
    }
    return {
        "id": actor_id,
        "nameKo": name,
        "nameEn": None,
        "type": "actor",
        "birthYear": birth_year,
        "availableFrom": year,
        "status": "active",
        "protectionLevel": "generated",
        "currentStats": current_stats,
        "potentialStats": potential_stats,
        "genreFit": genre_fit,
        "statProfile": stat_profile,
        "publicProfile": profile,
    }


def _insert_generated_actor(
    conn: Any,
    actor: dict[str, Any],
    project_id: str,
    budget: int,
    option_id: str,
) -> None:
    values = (
        actor["id"],
        actor["nameKo"],
        actor.get("nameEn"),
        "actor",
        actor["birthYear"],
        actor["availableFrom"],
        actor["status"],
        actor["protectionLevel"],
        dumps_json(actor["currentStats"]),
        dumps_json(actor["potentialStats"]),
        dumps_json(actor["genreFit"]),
        dumps_json(actor["statProfile"]),
        dumps_json(actor["publicProfile"]),
    )
    conn.execute(
        """
        INSERT INTO people (
            id, name_ko, name_en, type, birth_year, available_from,
            status, protection_level, current_stats_json, potential_stats_json,
            genre_fit_json, stat_profile_json, public_profile_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        values,
    )
    conn.execute(
        """
        INSERT INTO people_actor_profiles (
            person_id, current_stats_json, potential_stats_json,
            genre_fit_json, stat_profile_json, public_profile_json
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        (actor["id"], values[8], values[9], values[10], values[11], values[12]),
    )
    data = {
        **actor,
        "sourceProjectId": project_id,
        "discoveryBudget": budget,
        "sourceRuleId": option_id,
    }
    conn.execute(
        """
        INSERT INTO save_generated_people (
            id, person_type, name, generated_year, generated_month,
            source_rule_id, data_json
        ) VALUES (?, 'actor', ?, ?, ?, ?, ?)
        """,
        (actor["id"], actor["nameKo"], actor["availableFrom"], actor["statProfile"]["generatedAt"]["month"], option_id, dumps_json(data)),
    )
    conn.execute(
        """
        INSERT INTO generated_entities (
            id, entity_type, name, generated_year, generated_month,
            source_rule_id, data_json
        ) VALUES (?, 'person', ?, ?, ?, ?, ?)
        """,
        (actor["id"], actor["nameKo"], actor["availableFrom"], actor["statProfile"]["generatedAt"]["month"], option_id, dumps_json(data)),
    )


def _minor_cast_state(conn: Any, project_id: str) -> dict[str, Any]:
    rows = conn.execute(
        """
        SELECT pp.role, pp.contract_fee, p.name_ko, p.id
        FROM project_people pp
        JOIN people p ON p.id = pp.person_id
        WHERE pp.project_id = ? AND pp.role IN ('minor_actor', 'day_player', 'background_actor')
        ORDER BY pp.role, p.name_ko
        """,
        (project_id,),
    ).fetchall()
    total_fee = sum(int(row["contract_fee"] or 0) for row in rows)
    return {
        "filled": bool(rows),
        "count": len(rows),
        "total_fee": total_fee,
        "summary": _minor_cast_summary(len(rows), total_fee) if rows else "자동 충원된 단역이 아직 없습니다.",
        "rows": [
            {"id": row["id"], "name": row["name_ko"], "role": row["role"], "fee": int(row["contract_fee"] or 0)}
            for row in rows
        ],
    }


def _minor_role_plan(count: int) -> list[str]:
    if count <= 1:
        return ["day_player"]
    minor_count = max(1, count // 3)
    day_count = max(1, count // 2)
    background_count = max(0, count - minor_count - day_count)
    return ["minor_actor"] * minor_count + ["day_player"] * day_count + ["background_actor"] * background_count


def _minor_actor_fee(role: str, year: int) -> int:
    base_2020 = {
        "minor_actor": 3_000_000,
        "day_player": 700_000,
        "background_actor": 200_000,
    }.get(role, 500_000)
    return adjust_money_to_year(base_2020, to_year=year)


def _minor_contribution(actor: dict[str, Any], role: str) -> dict[str, int]:
    current = actor.get("currentStats") or {}
    acting = int(current.get("acting", 48) or 48)
    role_weight = {"minor_actor": 0.45, "day_player": 0.25, "background_actor": 0.12}.get(role, 0.2)
    return {
        "acting_quality": int(42 + (acting - 42) * role_weight),
        "casting_fit": int(44 + role_weight * 12),
    }


def _auto_minor_one_line(role: str) -> str:
    if role == "minor_actor":
        return "작은 조연과 장면 연결을 안정적으로 채우는 현장형 배우."
    if role == "day_player":
        return "짧은 대사와 단역 장면을 맡는 자동 충원 배우."
    return "거리감과 화면 밀도를 채우는 이미지·군중 출연 배우."


def _minor_cast_summary(count: int, total_fee: int) -> str:
    return f"단역과 작은 조연 {count}명을 자동 충원했습니다. 예상 단역 계약 총액은 {money(total_fee)}입니다."


def _actor_archetype(option_id: str) -> dict[str, Any]:
    archetypes = {
        "film_school": [
            {"label": "감정 집중형", "roleType": ["성장형"], "bias": {"acting": 4, "growthPotential": 10, "scheduleDifficulty": -8}},
            {"label": "카메라 존재감형", "roleType": ["팬덤형"], "bias": {"brandPower": 6, "growthPotential": 8, "acting": -2}},
            {"label": "대사 불안정형", "roleType": ["성장형"], "bias": {"acting": -4, "growthPotential": 14, "costLevel": -6}},
        ],
        "open_audition": [
            {"label": "균형형", "roleType": ["성장형"], "bias": {"acting": 2, "brandPower": 2}},
            {"label": "스타성 원석", "roleType": ["팬덤형"], "bias": {"brandPower": 9, "ticketPower": 4, "acting": -3}},
            {"label": "생활 연기형", "roleType": ["연기파"], "bias": {"acting": 7, "festivalPower": 3}},
        ],
        "theater_indie": [
            {"label": "연극 기본기형", "roleType": ["연기파"], "bias": {"acting": 10, "festivalPower": 5, "brandPower": -4}},
            {"label": "독립영화 얼굴", "roleType": ["연기파", "성장형"], "bias": {"acting": 6, "growthPotential": 8, "ticketPower": -5}},
        ],
        "character_pool": [
            {"label": "강한 조연형", "roleType": ["신스틸러"], "bias": {"acting": 8, "ticketPower": -5, "scheduleDifficulty": -4}},
            {"label": "현장 안정형", "roleType": ["연기파"], "bias": {"acting": 5, "costLevel": -3, "scheduleDifficulty": -8}},
        ],
        "local_nonprofessional": [
            {"label": "생활감 원석", "roleType": ["성장형"], "bias": {"acting": -6, "brandPower": -8, "growthPotential": 15, "costLevel": -10}},
            {"label": "지역성 강한 얼굴", "roleType": ["성장형"], "bias": {"castingFit": 8, "growthPotential": 12, "scheduleDifficulty": -6}},
        ],
        "sns_model": [
            {"label": "화제성 원석", "roleType": ["팬덤형"], "bias": {"brandPower": 12, "ticketPower": 5, "acting": -7}},
            {"label": "이미지 강점형", "roleType": ["성장형"], "bias": {"brandPower": 8, "growthPotential": 8, "festivalPower": -5}},
        ],
    }
    return random.choice(archetypes.get(option_id, archetypes["open_audition"]))


def _generated_actor_stats(archetype: dict[str, Any], budget_factor: float) -> dict[str, int]:
    base = {
        "acting": random.randint(38, 64),
        "ticketPower": random.randint(10, 30),
        "festivalPower": random.randint(25, 55),
        "brandPower": random.randint(15, 42),
        "globalRecognition": random.randint(3, 18),
        "costLevel": random.randint(8, 32),
        "scheduleDifficulty": random.randint(15, 42),
        "growthPotential": random.randint(62, 92),
    }
    for key, value in archetype.get("bias", {}).items():
        mapped = "casting_fit" if key == "castingFit" else key
        if mapped in base:
            base[mapped] = _clamp(base[mapped] + int(value))
    quality_bonus = int((budget_factor - 0.9) * 10)
    for key in ("acting", "brandPower", "growthPotential"):
        base[key] = _clamp(base[key] + quality_bonus)
    return base


def _generated_genre_fit(genre_id: str, genre_tags: list[str], archetype: dict[str, Any]) -> dict[str, int]:
    genre_ids = {
        "crime_thriller": "genre_crime_thriller",
        "action": "genre_action",
        "horror_occult": "genre_horror_occult",
        "romance_melodrama": "genre_romance_melodrama",
        "comedy": "genre_comedy",
        "family_human_drama": "genre_family_human_drama",
        "historical_period": "genre_period_historical",
        "social_true_story": "genre_social_true_story",
        "indie_art": "genre_indie_art",
        "sf_disaster_monster": "genre_sf_disaster_monster",
        "fantasy": "genre_fantasy",
        "animation": "genre_animation",
    }
    all_ids = set(genre_ids.values()) | {genre_id}
    fit = {item: random.randint(36, 58) for item in all_ids if item}
    for tag in genre_tags:
        mapped = genre_ids.get(tag, tag if str(tag).startswith("genre_") else "")
        if mapped:
            fit[mapped] = random.randint(58, 78)
    if genre_id:
        fit[genre_id] = max(fit.get(genre_id, 55), random.randint(62, 82))
    if "신스틸러" in archetype.get("roleType", []):
        fit["genre_crime_thriller"] = max(fit.get("genre_crime_thriller", 50), random.randint(62, 80))
        fit["genre_comedy"] = max(fit.get("genre_comedy", 50), random.randint(58, 76))
    return fit


def _generated_actor_profile(
    *,
    name: str,
    option_label: str,
    archetype: dict[str, Any],
    genre_name: str,
    current_stats: dict[str, int],
    potential_stats: dict[str, int],
) -> dict[str, str]:
    label = archetype["label"]
    if current_stats.get("acting", 0) >= 62:
        current = "기본기가 비교적 단단하고 감정 장면에서 설득력을 보인다."
    elif current_stats.get("brandPower", 0) >= 40:
        current = "연기 경험은 더 필요하지만 카메라 앞에서 시선을 끄는 힘이 있다."
    else:
        current = "아직 거칠지만 현장 지도를 받아들이는 속도가 중요해 보인다."
    if potential_stats.get("growthPotential", 0) >= 82:
        potential = "좋은 배역과 감독을 만나면 빠르게 이름을 알릴 가능성이 있다."
    else:
        potential = "작품 선택과 현장 경험이 쌓이면 안정적인 조연 또는 독립영화 얼굴로 성장할 수 있다."
    genre_text = f"{genre_name} 프로젝트" if genre_name else "현재 프로젝트"
    return {
        "oneLine": f"{name}은 {option_label}에서 발견된 {label} 신인 배우.",
        "currentAbilityText": current,
        "potentialText": potential,
        "fameText": "대중 인지도는 거의 없고, 이번 작품이 첫 평가 무대에 가깝다.",
        "brandText": f"제작 발표 단계의 화제성은 낮지만 {genre_text}에서 발견의 재미를 만들 수 있다.",
        "recentTrendText": "오디션과 미팅 반응을 바탕으로 생성된 후보라 실제 평판은 작품 결과에 따라 형성된다.",
        "activityStatusText": "활동 가능",
        "informationReliabilityText": "오디션 관찰과 제한된 면담을 바탕으로 한 낮은~중간 신뢰도 정보다.",
    }


def _generated_korean_name(year: int, used_names: set[str]) -> str:
    family_names = ["김", "이", "박", "최", "정", "강", "조", "윤", "장", "임", "한", "오", "서", "신", "권", "황", "안", "송", "류", "홍"]
    if year < 1990:
        given_names = ["영수", "성호", "민수", "정훈", "은주", "미경", "혜진", "선영", "지영", "현숙", "재호", "상민"]
    elif year < 2010:
        given_names = ["민재", "지훈", "태준", "현우", "서연", "지민", "유진", "수진", "다혜", "은지", "준호", "나영"]
    else:
        given_names = ["도현", "서윤", "지우", "하린", "민서", "시우", "예린", "도윤", "하은", "수아", "준서", "채원"]
    for _ in range(200):
        name = f"{random.choice(family_names)}{random.choice(given_names)}"
        if name not in used_names:
            used_names.add(name)
            return name
    name = f"{random.choice(family_names)}{random.choice(given_names)}{len(used_names)}"
    used_names.add(name)
    return name


def _genre_tag_from_id(genre_id: str) -> str:
    return {
        "genre_crime_thriller": "crime_thriller",
        "crime_thriller": "crime_thriller",
        "genre_action": "action",
        "action": "action",
        "genre_horror_occult": "horror_occult",
        "horror_occult": "horror_occult",
        "genre_romance_melodrama": "romance_melodrama",
        "romance_melodrama": "romance_melodrama",
        "genre_comedy": "comedy",
        "comedy": "comedy",
        "genre_family_human_drama": "family_human_drama",
        "family_human_drama": "family_human_drama",
        "genre_period_historical": "historical_period",
        "historical_period": "historical_period",
        "genre_social_true_story": "social_true_story",
        "social_true_story": "social_true_story",
        "genre_indie_art": "indie_art",
        "indie_art": "indie_art",
        "genre_sf_disaster_monster": "sf_disaster_monster",
        "sf_disaster_monster": "sf_disaster_monster",
        "genre_fantasy": "fantasy",
        "fantasy": "fantasy",
        "genre_animation": "animation",
        "animation": "animation",
    }.get(genre_id, "indie_art")


def _clamp(value: int | float, minimum: int = 0, maximum: int = 100) -> int:
    return max(minimum, min(maximum, int(round(value))))


def _public_casting_row(row: Any) -> dict[str, Any]:
    profile = loads_json(row["public_profile_json"], {})
    options = loads_json(row["contract_options_json"], {})
    terms = options.get("terms") if isinstance(options.get("terms"), dict) else {}
    relation = relationship_snapshot(row["relationship_trust"], row["relationship_awareness"])
    return {
        "project_id": row["project_id"],
        "person_id": row["person_id"],
        "name_ko": row["name_ko"],
        "name_en": row["name_en"],
        "type": row["type"],
        "role": row["role"],
        "role_label": ROLE_LABELS.get(row["role"], row["role"]),
        "status": row["status"],
        "contract_fee": int(row["contract_fee"] or 0),
        "sequel_option": bool(row["sequel_option"]),
        "promotion_obligation": bool(row["promotion_obligation"]),
        "promotion_days": int(row["promotion_days"] or 0),
        "commitment_months": int(row["schedule_commitment_months"] or 0),
        "contract_terms": terms,
        "automatic_cast": bool(terms.get("autoMinorCast")) or row["role"] in AUTOMATIC_ACTOR_ROLES,
        "one_line": profile.get("oneLine", "공개 평가가 아직 충분하지 않다."),
        "current_ability_text": profile.get("currentAbilityText", "현재 능력은 업계 자료를 더 확인해야 한다."),
        "potential_text": profile.get("potentialText", "성장 가능성은 작품 선택에 따라 달라질 수 있다."),
        "fame_text": profile.get("fameText", "명성 정보가 제한적이다."),
        "brand_text": profile.get("brandText", "브랜드 평판이 아직 뚜렷하지 않다."),
        "relationship_stage": relation["label"],
        "relationship_text": relation["description"],
        "contract_text": _contract_text(row),
    }


def _contract_text(row: Any) -> str:
    options = loads_json(row["contract_options_json"], {})
    terms = options.get("terms") if isinstance(options.get("terms"), dict) else {}
    if terms.get("autoMinorCast") or row["role"] in AUTOMATIC_ACTOR_ROLES:
        return f"자동 충원 · 계약금 {int(row['contract_fee'] or 0):,}원"
    parts = [f"계약금 {int(row['contract_fee'] or 0):,}원"]
    if options.get("sequelOption") or row["sequel_option"]:
        parts.append("후속작 옵션 포함")
    if options.get("promotionObligation") or row["promotion_obligation"]:
        days = int(options.get("promotionDays") or row["promotion_days"] or 0)
        parts.append(f"홍보 의무 {days}일")
    months = int(options.get("scheduleCommitmentMonths") or row["schedule_commitment_months"] or 0)
    if months:
        parts.append(f"일정 구속 {months}개월")
    deferred_fee = int(terms.get("deferredFee") or 0)
    if deferred_fee:
        parts.append(f"이연 지급 {deferred_fee:,}원")
    running = terms.get("runningGuarantee") if isinstance(terms.get("runningGuarantee"), dict) else {}
    if running.get("enabled") and float(running.get("rate") or 0) > 0:
        parts.append(f"러닝 개런티 {float(running['rate']) * 100:.1f}%({_running_trigger_label(running.get('trigger'))})")
    bonus = terms.get("boxOfficeBonus") if isinstance(terms.get("boxOfficeBonus"), dict) else {}
    if bonus.get("enabled") and int(bonus.get("amount") or 0) > 0:
        audience = int(bonus.get("audience") or 0)
        audience_text = f"{audience // 10000:,}만 관객" if audience else "흥행 조건"
        parts.append(f"{audience_text} 보너스 {int(bonus['amount']):,}원")
    if terms.get("imageRights"):
        parts.append("스틸컷/예고편 활용 동의")
    return " · ".join(parts)


def _running_trigger_label(trigger: Any) -> str:
    return {
        "release": "개봉 수익 기준",
        "break_even": "손익분기 이후",
        "profit": "순이익 발생 시",
    }.get(str(trigger or "break_even"), "손익분기 이후")
