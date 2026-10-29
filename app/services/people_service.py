from __future__ import annotations

from typing import Any

from app.database import dumps_json, get_connection, loads_json
from app.services.economic_service import adjust_money_to_year
from app.services.game_state import clamp, money
from app.services.people_stat_service import (
    activity_stage_for_year,
    career_context_for_person,
    contribution_stats_for_project,
    effective_stats_for_year,
    public_person_for_year,
)
from app.services.relationship_service import adjust_relationship, get_relationship_snapshot


PUBLIC_PERSON_DISPLAY_FIELDS = {
    "one_line",
    "current_ability_text",
    "potential_text",
    "fame_text",
    "brand_text",
}

LONG_COMMITMENT_MONTHS = 6


def list_available_people(person_type: str, year: int) -> list[dict[str, Any]]:
    with get_connection() as conn:
        player = conn.execute("SELECT position FROM player_state WHERE id = 1").fetchone()
        player_position = str(player["position"] or "") if player else ""
        rows = conn.execute(
            """
            SELECT * FROM people
            WHERE type = ? AND (available_from IS NULL OR available_from <= ?)
            ORDER BY available_from, name_ko
            """,
            (person_type, year),
        ).fetchall()
        people: list[dict[str, Any]] = []
        for row in rows:
            public = public_person_for_year(row, year)
            raw = dict(row)
            stats = effective_stats_for_year(raw, year)
            stat_profile = loads_json(raw.get("stat_profile_json"), {})
            career_context = career_context_for_person(raw, year)
            public["contract_text"] = _expected_fee_text(raw, stats, stat_profile, year, career_context)
            relation = get_relationship_snapshot(
                conn,
                row["id"],
                row["type"],
                persona_candidate=_persona_candidate_for_player(row["type"], player_position),
            )
            public["relationship_stage"] = relation["label"]
            public["relationship_text"] = relation["description"]
            people.append(public)
    return people


def list_public_critics() -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, name_ko, public_description
            FROM critics
            ORDER BY name_ko
            """
        ).fetchall()
        critics: list[dict[str, Any]] = []
        for row in rows:
            relation = get_relationship_snapshot(conn, row["id"], "critic")
            critics.append(
                {
                    "id": row["id"],
                    "name_ko": row["name_ko"],
                    "public_description": row["public_description"] or "평론 성향 정보가 아직 충분하지 않다.",
                    "relationship_stage": relation["label"],
                    "relationship_text": relation["description"],
                }
            )
    return critics


def get_critic_profile(critic_id: str) -> dict[str, Any]:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM critics WHERE id = ?", (critic_id,)).fetchone()
        if not row:
            raise ValueError("평론가를 찾을 수 없습니다.")
        raw = dict(row)
        critic_types = loads_json(raw.get("critic_type_json"), [])
        taste = loads_json(raw.get("taste_profile_json"), {})
        influence = loads_json(raw.get("influence_json"), {})
        scoring = loads_json(raw.get("scoring_style_json"), {})
        reviews = _critic_reviews(conn, critic_id)
        relationship = get_relationship_snapshot(conn, critic_id, "critic")

    return {
        "id": critic_id,
        "name": raw["name_ko"],
        "type": "critic",
        "age_text": "연령 정보 미정리",
        "nationality": "대한민국",
        "status_text": _critic_status_text(raw),
        "one_line": _critic_one_line(raw, critic_types, influence),
        "public_description": raw.get("public_description") or "평론 성향 정보가 아직 충분하지 않다.",
        "influence_text": _critic_influence_text(influence),
        "taste_text": _critic_taste_text(taste),
        "scoring_text": _critic_scoring_text(scoring),
        "preferred_films": _critic_preference_text(taste, critic_types),
        "review_history": reviews,
        "relationship_stage": relationship["label"],
        "relationship_text": relationship["description"],
        "career_intro": _critic_career_intro(raw, critic_types, taste, influence, reviews),
    }


def get_person_profile(person_id: str, year: int | None = None, month: int | None = None) -> dict[str, Any]:
    with get_connection() as conn:
        if year is None:
            player = conn.execute("SELECT current_year, current_month, position FROM player_state WHERE id = 1").fetchone()
            year = int(player["current_year"]) if player else 2026
            month = int(player["current_month"]) if player else 12
            player_position = str(player["position"] or "") if player else ""
        else:
            player = conn.execute("SELECT position FROM player_state WHERE id = 1").fetchone()
            player_position = str(player["position"] or "") if player else ""
        if month is None:
            month = 12
        row = conn.execute("SELECT * FROM people WHERE id = ?", (person_id,)).fetchone()
        if not row:
            raise ValueError("인물을 찾을 수 없습니다.")
        person = public_person_for_year(row, year, month)
        raw = dict(row)
        potential_stats = loads_json(raw.get("potential_stats_json"), {})
        stat_profile = loads_json(raw.get("stat_profile_json"), {})
        genre_fit = loads_json(raw.get("genre_fit_json"), {})
        public_profile = loads_json(raw.get("public_profile_json"), {})
        relationship = get_relationship_snapshot(
            conn,
            person_id,
            raw.get("type"),
            persona_candidate=_persona_candidate_for_player(raw.get("type"), player_position),
        )
        timeline = _person_timeline(conn, person_id, until_year=year, until_month=month)
        protected_works = (
            _protected_director_works(conn, person_id, until_year=year, until_month=month)
            if raw.get("type") == "director"
            else []
        )
        awards = _person_awards(conn, person_id, until_year=year, until_month=month)
        career_entries = _career_entries_from_profile_lists(timeline, protected_works)
        stats = effective_stats_for_year(raw, year, month, career_entries)
        career_context = career_context_for_person(raw, year, month, career_entries)
        activity = activity_stage_for_year(raw, year, month, career_entries)

    return {
        "id": person_id,
        "name": _display_name(raw),
        "name_ko": raw["name_ko"],
        "name_en": raw.get("name_en"),
        "type": raw.get("type"),
        "age_text": _age_text(raw.get("birth_year"), year),
        "nationality": _nationality_text(raw),
        "status_text": _status_text(raw, year),
        "career_stage_label": activity["label"],
        "career_stage_text": activity["description"],
        "is_available": activity["isAvailable"],
        "industry_reputation": _industry_reputation_text(stats, stat_profile),
        "public_reputation": _public_reputation_text(stats, stat_profile),
        "fame_text": person.get("fame_text") or public_profile.get("fameText") or _tier_text(stat_profile),
        "potential_text": person.get("potential_text") or public_profile.get("potentialText") or _potential_text(potential_stats, stat_profile),
        "one_line": person.get("one_line") or public_profile.get("oneLine") or _generated_one_line(raw, stat_profile),
        "current_ability_text": person.get("current_ability_text") or public_profile.get("currentAbilityText") or "",
        "brand_text": person.get("brand_text") or public_profile.get("brandText") or "",
        "expected_fee": _expected_fee_text(raw, stats, stat_profile, year, career_context),
        "relationship_stage": relationship["label"],
        "relationship_text": relationship["description"],
        "fee_title": "예상 출연료" if raw.get("type") == "actor" else "예상 연출 계약",
        "preference_title": "선호 배역 및 감독" if raw.get("type") == "actor" else "선호 프로젝트 및 협업 궁합",
        "preferred_roles": _preferred_roles_text(raw, stat_profile, genre_fit),
        "preferred_directors": _preferred_directors_text(raw, stat_profile),
        "filmography": _filmography_entries(timeline, protected_works),
        "awards": awards,
        "career_intro": _career_intro(raw, stat_profile, stats, timeline, protected_works, year),
    }


def attach_person_to_project(
    project_id: str,
    person_id: str,
    role: str,
    contract_fee: int = 0,
    commitment_months: int = 0,
    sequel_option: bool = False,
    promotion_obligation: bool = False,
    promotion_days: int = 0,
    contract_terms: dict[str, Any] | None = None,
) -> None:
    with get_connection() as conn:
        person = conn.execute("SELECT * FROM people WHERE id = ?", (person_id,)).fetchone()
        project = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
        player = conn.execute("SELECT current_year, current_month FROM player_state WHERE id = 1").fetchone()
        if not person or not project:
            raise ValueError("프로젝트 또는 인물을 찾을 수 없습니다.")
        _ensure_person_can_contract(dict(person), int(player["current_year"]) if player else 2026, int(player["current_month"]) if player else 12)
        if (
            int(commitment_months or 0) >= LONG_COMMITMENT_MONTHS
            and player
            and _has_protected_schedule_overlap(
                conn,
                person_id,
                int(player["current_year"]),
                int(player["current_month"]),
                int(commitment_months),
            )
        ):
            raise ValueError(
                "이미 확정된 장기 일정과 겹치는 핵심 인물은 장기 구속 계약을 맺을 수 없습니다. "
                "특별출연, 일정 조정, 대체 캐스팅을 검토하세요."
            )

        contribution = contribution_stats_for_project(
            dict(person),
            role,
            int(player["current_year"]) if player else 2026,
        )
        contract_options = _contract_options_payload(
            role=role,
            person_type=str(person["type"] or ""),
            contract_fee=contract_fee,
            commitment_months=commitment_months,
            sequel_option=sequel_option,
            promotion_obligation=promotion_obligation,
            promotion_days=promotion_days,
            contract_terms=contract_terms,
        )
        project_stats = loads_json(project["stats_json"], {})
        for key, value in contribution.items():
            project_stats[key] = clamp((float(project_stats.get(key, 50)) * 0.7) + (float(value) * 0.3))
        _apply_contract_option_stats(project_stats, contract_options)

        conn.execute(
            """
            INSERT OR REPLACE INTO project_people (
                project_id, person_id, role, contract_fee,
                sequel_option, promotion_obligation, promotion_days,
                schedule_commitment_months, contract_options_json,
                status, contribution_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'attached', ?)
            """,
            (
                project_id,
                person_id,
                role,
                contract_fee,
                1 if contract_options["sequelOption"] else 0,
                1 if contract_options["promotionObligation"] else 0,
                int(contract_options["promotionDays"]),
                int(contract_options["scheduleCommitmentMonths"]),
                dumps_json(contract_options),
                dumps_json(contribution),
            ),
        )
        conn.execute(
            """
            INSERT INTO people_career_timeline (
                person_id, project_id, role, status, result_json
            ) VALUES (?, ?, ?, 'attached', ?)
            """,
            (
                person_id,
                project_id,
                role,
                dumps_json(
                    {
                        "contribution": contribution,
                        "contractFee": contract_fee,
                        "contractOptions": contract_options,
                    }
                ),
            ),
        )
        conn.execute(
            "UPDATE projects SET stats_json = ? WHERE id = ?",
            (dumps_json(project_stats), project_id),
        )
        current_year = int(player["current_year"]) if player else None
        trust_delta = 4 if role == "director" else 3
        awareness_delta = 12 if role == "director" else 10
        adjust_relationship(
            conn,
            person_id,
            person["type"],
            trust_delta=trust_delta,
            awareness_delta=awareness_delta,
            last_contact_year=current_year,
        )
        conn.commit()


def update_person_project_contract(
    project_id: str,
    person_id: str,
    role: str,
    contract_fee: int = 0,
    commitment_months: int = 0,
    sequel_option: bool = False,
    promotion_obligation: bool = False,
    promotion_days: int = 0,
    contract_terms: dict[str, Any] | None = None,
) -> None:
    with get_connection() as conn:
        contract = conn.execute(
            """
            SELECT *
            FROM project_people
            WHERE project_id = ? AND person_id = ? AND role = ?
            """,
            (project_id, person_id, role),
        ).fetchone()
        person = conn.execute("SELECT * FROM people WHERE id = ?", (person_id,)).fetchone()
        project = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
        player = conn.execute("SELECT * FROM player_state WHERE id = 1").fetchone()
        if not contract or not person or not project:
            raise ValueError("수정할 계약을 찾을 수 없습니다.")
        _ensure_person_can_contract(dict(person), int(player["current_year"]) if player else 2026, int(player["current_month"]) if player else 12)
        if (
            int(commitment_months or 0) >= LONG_COMMITMENT_MONTHS
            and player
            and _has_protected_schedule_overlap(
                conn,
                person_id,
                int(player["current_year"]),
                int(player["current_month"]),
                int(commitment_months),
            )
        ):
            raise ValueError(
                "이미 확정된 장기 일정과 겹치는 핵심 인물은 장기 구속 계약으로 수정할 수 없습니다. "
                "홍보 의무, 단기 구속, 특별출연 조건을 검토하세요."
            )

        old_options = loads_json(contract["contract_options_json"], {})
        new_options = _contract_options_payload(
            role=role,
            person_type=str(person["type"] or ""),
            contract_fee=contract_fee,
            commitment_months=commitment_months,
            sequel_option=sequel_option,
            promotion_obligation=promotion_obligation,
            promotion_days=promotion_days,
            contract_terms=contract_terms,
        )
        project_stats = loads_json(project["stats_json"], {})
        max_commitment = _max_project_commitment_after_update(
            conn,
            project_id,
            person_id,
            role,
            int(new_options["scheduleCommitmentMonths"]),
        )
        _apply_contract_update_delta(project_stats, old_options, new_options, max_commitment)

        conn.execute(
            """
            UPDATE project_people
            SET contract_fee = ?, sequel_option = ?, promotion_obligation = ?,
                promotion_days = ?, schedule_commitment_months = ?,
                contract_options_json = ?
            WHERE project_id = ? AND person_id = ? AND role = ?
            """,
            (
                int(contract_fee or 0),
                1 if new_options["sequelOption"] else 0,
                1 if new_options["promotionObligation"] else 0,
                int(new_options["promotionDays"]),
                int(new_options["scheduleCommitmentMonths"]),
                dumps_json(new_options),
                project_id,
                person_id,
                role,
            ),
        )
        conn.execute(
            """
            INSERT INTO people_career_timeline (
                person_id, project_id, role, year, month, status, result_json
            ) VALUES (?, ?, ?, ?, ?, 'contract_updated', ?)
            """,
            (
                person_id,
                project_id,
                role,
                player["current_year"] if player else None,
                player["current_month"] if player else None,
                dumps_json(
                    {
                        "previousContractOptions": old_options,
                        "contractOptions": new_options,
                        "contractFee": int(contract_fee or 0),
                    }
                ),
            ),
        )
        conn.execute(
            "UPDATE projects SET stats_json = ? WHERE id = ?",
            (dumps_json(project_stats), project_id),
        )
        adjust_relationship(
            conn,
            person_id,
            person["type"],
            trust_delta=1,
            awareness_delta=2,
            last_contact_year=int(player["current_year"]) if player else None,
        )
        conn.commit()


def _contract_options_payload(
    *,
    role: str,
    person_type: str,
    contract_fee: int,
    commitment_months: int,
    sequel_option: bool,
    promotion_obligation: bool,
    promotion_days: int,
    contract_terms: dict[str, Any] | None,
) -> dict[str, Any]:
    actor_role = person_type == "actor" or role in {"lead_actor", "supporting_actor", "cameo_actor", "minor_actor", "day_player", "background_actor", "actor"}
    promotion_role = actor_role or person_type == "director" or role == "director"
    default_promotion_days = 6 if role == "lead_actor" else 4 if role == "director" else 3 if promotion_role else 0
    resolved_promotion_days = int(promotion_days or (default_promotion_days if promotion_obligation else 0))
    return {
        "sequelOption": bool(sequel_option and actor_role),
        "promotionObligation": bool(promotion_obligation and promotion_role),
        "promotionDays": max(0, resolved_promotion_days),
        "scheduleCommitmentMonths": max(0, int(commitment_months or 0)),
        "contractFee": int(contract_fee or 0),
        "terms": _normalize_contract_terms(contract_terms or {}),
    }


def _apply_contract_option_stats(project_stats: dict[str, Any], options: dict[str, Any]) -> None:
    if options.get("sequelOption"):
        project_stats["ip_value"] = clamp(float(project_stats.get("ip_value", 45)) + 4)
        project_stats["sequel_demand"] = clamp(float(project_stats.get("sequel_demand", 35)) + 3)
        project_stats["franchise_power"] = clamp(float(project_stats.get("franchise_power", 35)) + 3)
    if options.get("promotionObligation"):
        project_stats["pre_release_interest"] = clamp(float(project_stats.get("pre_release_interest", 45)) + 4)
        project_stats["fandom_index"] = clamp(float(project_stats.get("fandom_index", 40)) + 3)
        project_stats["marketing_sense"] = clamp(float(project_stats.get("marketing_sense", 50)) + 1)
    months = int(options.get("scheduleCommitmentMonths", 0) or 0)
    if months:
        project_stats["actor_commitment_duration"] = max(
            months,
            int(project_stats.get("actor_commitment_duration", 0) or 0),
        )
        project_stats["schedule_delay_risk"] = clamp(float(project_stats.get("schedule_delay_risk", 20)) - min(months, 6))
    for key, delta in _contract_term_stat_deltas(options).items():
        project_stats[key] = clamp(float(project_stats.get(key, 50)) + delta)


def _apply_contract_update_delta(
    project_stats: dict[str, Any],
    old_options: dict[str, Any],
    new_options: dict[str, Any],
    max_commitment: int,
) -> None:
    if bool(old_options.get("sequelOption")) != bool(new_options.get("sequelOption")):
        sign = 1 if new_options.get("sequelOption") else -1
        project_stats["ip_value"] = clamp(float(project_stats.get("ip_value", 45)) + 4 * sign)
        project_stats["sequel_demand"] = clamp(float(project_stats.get("sequel_demand", 35)) + 3 * sign)
        project_stats["franchise_power"] = clamp(float(project_stats.get("franchise_power", 35)) + 3 * sign)
    if bool(old_options.get("promotionObligation")) != bool(new_options.get("promotionObligation")):
        sign = 1 if new_options.get("promotionObligation") else -1
        project_stats["pre_release_interest"] = clamp(float(project_stats.get("pre_release_interest", 45)) + 4 * sign)
        project_stats["fandom_index"] = clamp(float(project_stats.get("fandom_index", 40)) + 3 * sign)
        project_stats["marketing_sense"] = clamp(float(project_stats.get("marketing_sense", 50)) + 1 * sign)
    old_months = int(old_options.get("scheduleCommitmentMonths") or 0)
    new_months = int(new_options.get("scheduleCommitmentMonths") or 0)
    if old_months != new_months:
        project_stats["schedule_delay_risk"] = clamp(
            float(project_stats.get("schedule_delay_risk", 20)) + min(old_months, 6) - min(new_months, 6)
        )
    project_stats["actor_commitment_duration"] = max(0, int(max_commitment or 0))
    old_deltas = _contract_term_stat_deltas(old_options)
    new_deltas = _contract_term_stat_deltas(new_options)
    for key in sorted(set(old_deltas) | set(new_deltas)):
        project_stats[key] = clamp(float(project_stats.get(key, 50)) - old_deltas.get(key, 0) + new_deltas.get(key, 0))


def _normalize_contract_terms(contract_terms: dict[str, Any]) -> dict[str, Any]:
    raw = dict(contract_terms or {})
    running_raw = raw.get("runningGuarantee") if isinstance(raw.get("runningGuarantee"), dict) else {}
    rate = _safe_float(running_raw.get("rate") or raw.get("runningGuaranteeRate") or 0)
    if rate > 1:
        rate = rate / 100
    trigger = str(running_raw.get("trigger") or raw.get("runningGuaranteeTrigger") or "break_even")
    if trigger not in {"release", "break_even", "profit"}:
        trigger = "break_even"
    running_enabled = (
        bool(running_raw.get("enabled"))
        if "enabled" in running_raw
        else bool(raw.get("runningGuaranteeEnabled") or rate > 0)
    )
    bonus_raw = raw.get("boxOfficeBonus") if isinstance(raw.get("boxOfficeBonus"), dict) else {}
    bonus_amount = max(0, int(bonus_raw.get("amount") or raw.get("boxOfficeBonusAmount") or 0))
    bonus_audience = max(0, int(bonus_raw.get("audience") or raw.get("boxOfficeBonusAudience") or 0))
    deferred_fee = max(0, int(raw.get("deferredFee") or 0))
    return {
        "packageId": str(raw.get("packageId") or "custom"),
        "deferredFee": deferred_fee,
        "runningGuarantee": {
            "enabled": running_enabled,
            "rate": max(0.0, min(0.2, rate)),
            "trigger": trigger,
        },
        "boxOfficeBonus": {
            "enabled": bool(bonus_raw.get("enabled") or raw.get("boxOfficeBonusEnabled") or bonus_amount > 0),
            "audience": bonus_audience,
            "amount": bonus_amount,
        },
        "imageRights": bool(raw.get("imageRights")),
    }


def _contract_term_stat_deltas(options: dict[str, Any]) -> dict[str, float]:
    terms = options.get("terms") if isinstance(options.get("terms"), dict) else {}
    deltas: dict[str, float] = {}
    running = terms.get("runningGuarantee") if isinstance(terms.get("runningGuarantee"), dict) else {}
    if running.get("enabled") and float(running.get("rate") or 0) > 0:
        deltas["casting_fit"] = deltas.get("casting_fit", 0) + 2
        deltas["acting_quality"] = deltas.get("acting_quality", 0) + 1
        deltas["financial_risk"] = deltas.get("financial_risk", 0) + 2
    bonus = terms.get("boxOfficeBonus") if isinstance(terms.get("boxOfficeBonus"), dict) else {}
    if bonus.get("enabled") and int(bonus.get("amount") or 0) > 0:
        deltas["pre_release_interest"] = deltas.get("pre_release_interest", 0) + 2
        deltas["fandom_index"] = deltas.get("fandom_index", 0) + 2
    if int(terms.get("deferredFee") or 0) > 0:
        deltas["financial_risk"] = deltas.get("financial_risk", 0) - 1
        deltas["creative_reputation"] = deltas.get("creative_reputation", 0) + 1
    if terms.get("imageRights"):
        deltas["pre_release_interest"] = deltas.get("pre_release_interest", 0) + 2
        deltas["online_buzz"] = deltas.get("online_buzz", 0) + 2
    return deltas


def _safe_float(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _max_project_commitment_after_update(
    conn: Any,
    project_id: str,
    person_id: str,
    role: str,
    new_months: int,
) -> int:
    rows = conn.execute(
        """
        SELECT person_id, role, schedule_commitment_months, contract_options_json
        FROM project_people
        WHERE project_id = ?
        """,
        (project_id,),
    ).fetchall()
    values: list[int] = []
    for row in rows:
        if row["person_id"] == person_id and row["role"] == role:
            values.append(int(new_months or 0))
            continue
        options = loads_json(row["contract_options_json"], {})
        values.append(int(options.get("scheduleCommitmentMonths") or row["schedule_commitment_months"] or 0))
    return max(values or [int(new_months or 0)])


def _persona_candidate_for_player(target_type: str | None, player_position: str | None) -> bool:
    if target_type != "actor":
        return False
    normalized = (player_position or "").lower()
    return any(token in normalized for token in ("director", "감독", "연출"))


def _has_protected_schedule_overlap(
    conn: Any,
    person_id: str,
    start_year: int,
    start_month: int,
    duration_months: int,
) -> bool:
    start_index = start_year * 12 + start_month
    end_index = start_index + max(0, duration_months - 1)
    schedules = conn.execute(
        """
        SELECT * FROM people_protected_schedules
        WHERE person_id = ?
        """,
        (person_id,),
    ).fetchall()
    for schedule in schedules:
        schedule_start = int(schedule["start_year"]) * 12 + int(schedule["start_month"] or 1)
        schedule_end_year = int(schedule["end_year"] or schedule["start_year"])
        schedule_end_month = int(schedule["end_month"] or 12)
        schedule_end = schedule_end_year * 12 + schedule_end_month
        if start_index <= schedule_end and end_index >= schedule_start:
            return True
    return False


def _ensure_person_can_contract(person: dict[str, Any], year: int, month: int) -> None:
    activity = activity_stage_for_year(person, year, month)
    if activity.get("isAvailable"):
        return
    available_from = person.get("available_from")
    if isinstance(available_from, int) and year < available_from:
        raise ValueError(
            f"{person.get('name_ko', '이 인물')}은 {available_from}년 이후부터 활동 가능한 인물입니다. "
            "현재 게임 내 시점에서는 계약 후보로 사용할 수 없습니다."
        )
    raise ValueError(
        f"{person.get('name_ko', '이 인물')}은 현재 게임 내 시점에 새 프로젝트 계약을 맺을 수 없습니다."
    )


def _person_timeline(
    conn: Any,
    person_id: str,
    *,
    until_year: int | None = None,
    until_month: int | None = None,
) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT pct.*, COALESCE(c.title, p.title, m.title) AS title
        FROM people_career_timeline pct
        LEFT JOIN completed_films c ON c.id = pct.project_id
        LEFT JOIN projects p ON p.id = pct.project_id
        LEFT JOIN movies m ON m.id = pct.project_id
        WHERE pct.person_id = ?
          AND pct.status IN ('released', 'completed', 'awarded', 'reviewed')
        ORDER BY COALESCE(pct.year, 9999), COALESCE(pct.month, 12), pct.id
        """,
        (person_id,),
    ).fetchall()
    entries: list[dict[str, Any]] = []
    for row in rows:
        if not _has_occurred(row["year"], row["month"], until_year, until_month):
            continue
        result = loads_json(row["result_json"], {})
        entries.append(
            {
                "title": row["title"] or result.get("title") or "제목 미정 프로젝트",
                "year": row["year"],
                "month": row["month"],
                "role": row["role"],
                "status": row["status"],
                "summary": result.get("summary") or _role_label(row["role"]),
            }
        )
    return entries


def _protected_director_works(
    conn: Any,
    person_id: str,
    *,
    until_year: int | None = None,
    until_month: int | None = None,
) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT title, release_year, release_month, protection_level, metadata_json
        FROM history_protected_director_films
        WHERE director_id = ?
        ORDER BY release_year, COALESCE(release_month, 12), title
        """,
        (person_id,),
    ).fetchall()
    return [
        {
            **loads_json(row["metadata_json"], {}),
            "title": row["title"],
            "year": row["release_year"],
            "month": row["release_month"],
            "role": "director",
            "status": "released",
            "summary": "주요 필모그래피",
        }
        for row in rows
        if _has_occurred(row["release_year"], row["release_month"], until_year, until_month)
    ]


def _career_entries_from_profile_lists(
    timeline: list[dict[str, Any]],
    protected_works: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    seen: set[tuple[str, int | None, str]] = set()
    for item in protected_works + timeline:
        title = str(item.get("title") or "")
        year = item.get("year") if isinstance(item.get("year"), int) else None
        role = str(item.get("role") or "")
        key = (title, year, role)
        if key in seen:
            continue
        seen.add(key)
        entries.append(dict(item))
    return entries


def _person_awards(
    conn: Any,
    person_id: str,
    *,
    until_year: int | None = None,
    until_month: int | None = None,
) -> list[str]:
    rows = conn.execute(
        """
        SELECT year, month, result_json
        FROM people_career_timeline
        WHERE person_id = ?
          AND status IN ('released', 'completed', 'awarded', 'reviewed')
        ORDER BY COALESCE(year, 9999), COALESCE(month, 12), id
        """,
        (person_id,),
    ).fetchall()
    awards: list[str] = []
    for row in rows:
        if not _has_occurred(row["year"], row["month"], until_year, until_month):
            continue
        result = loads_json(row["result_json"], {})
        for award in result.get("awards", []) if isinstance(result, dict) else []:
            if isinstance(award, str) and award:
                awards.append(award)
            elif isinstance(award, dict):
                label = " · ".join(str(award.get(key)) for key in ("year", "name", "category", "result") if award.get(key))
                if label:
                    awards.append(label)
    return awards[:8]


def _has_occurred(year: Any, month: Any, until_year: int | None, until_month: int | None) -> bool:
    if until_year is None:
        return True
    if not isinstance(year, int):
        return True
    if year < until_year:
        return True
    if year > until_year:
        return False
    effective_month = int(month or 12)
    return effective_month <= int(until_month or 12)


def _critic_reviews(conn: Any, critic_id: str) -> list[str]:
    rows = conn.execute(
        """
        SELECT r.*, COALESCE(c.title, m.title, mh.title, mp.title, r.movie_id) AS title
        FROM movies_reviews r
        LEFT JOIN completed_films c ON c.id = r.movie_id
        LEFT JOIN movies m ON m.id = r.movie_id
        LEFT JOIN movies_historical mh ON mh.id = r.movie_id
        LEFT JOIN movies_player_created mp ON mp.id = r.movie_id
        WHERE r.critic_id = ?
        ORDER BY r.id DESC
        LIMIT 8
        """,
        (critic_id,),
    ).fetchall()
    reviews: list[str] = []
    for row in rows:
        quote = str(row["quote"] or "평론 요약 미정리")
        reviews.append(f"{row['title']} · {quote}")
    return reviews


def _display_name(row: dict[str, Any]) -> str:
    if row.get("name_en"):
        return f"{row['name_ko']} · {row['name_en']}"
    return str(row["name_ko"])


def _age_text(birth_year: Any, year: int) -> str:
    if not isinstance(birth_year, int):
        return "연령 정보 미정리"
    age = max(0, year - birth_year + 1)
    return f"{age}세 추정"


def _nationality_text(row: dict[str, Any]) -> str:
    profile = loads_json(row.get("public_profile_json"), {})
    return str(profile.get("nationality") or "대한민국")


def _status_text(row: dict[str, Any], year: int) -> str:
    available_from = row.get("available_from")
    status = str(row.get("status") or "active")
    if isinstance(available_from, int) and year < available_from:
        return f"{available_from}년 이후 활동 가능"
    labels = {
        "active": "활동 가능",
        "limited": "제한 활동",
        "retired": "은퇴",
        "deceased": "사망 후 캐스팅 불가",
    }
    return labels.get(status, status)


def _critic_status_text(row: dict[str, Any]) -> str:
    available_from = row.get("available_from")
    if isinstance(available_from, int):
        return f"{available_from}년 이후 평론 활동 데이터에 등장"
    return "활동 시기 정보 미정리"


def _industry_reputation_text(stats: dict[str, Any], profile: dict[str, Any]) -> str:
    tier = str(profile.get("tier") or "")
    value = _average(stats, ("acting", "festivalPower", "brandPower", "directing", "auteurPower", "budgetControl"))
    if tier in {"legend", "global_auteur", "commercial_master"} or value >= 88:
        return "업계 안에서 매우 강한 신뢰와 상징성을 가진 인물로 통한다."
    if value >= 74:
        return "업계에서 안정적으로 신뢰받는 축에 속한다."
    if value >= 58:
        return "업계 평판은 무난하지만 작품 선택과 현장 궁합을 더 본다."
    return "업계 평판은 아직 충분히 검증되지 않았다."


def _public_reputation_text(stats: dict[str, Any], profile: dict[str, Any]) -> str:
    value = _average(stats, ("ticketPower", "brandPower", "globalRecognition"))
    role_tags = profile.get("roleType") or profile.get("directorType") or []
    if "국민배우" in role_tags or value >= 88:
        return "대중에게 이름만으로도 강한 기대를 만드는 인물이다."
    if value >= 72:
        return "대중 인지도와 호감이 비교적 뚜렷하다."
    if value >= 55:
        return "영화 팬과 업계 중심으로 인지도가 형성되어 있다."
    return "대중 인지도는 아직 제한적이다."


def _tier_text(profile: dict[str, Any]) -> str:
    tier = str(profile.get("tier") or "")
    tier_labels = {
        "legend": "한국 영화사에서 대표급으로 분류되는 이름이다.",
        "top_star": "최상위 스타급으로 취급된다.",
        "a_list": "A급 주연급으로 분류된다.",
        "solid_lead": "안정적 주연급으로 분류된다.",
        "character_actor": "강한 조연/캐릭터 배우로 분류된다.",
        "rising": "상승세 배우로 분류된다.",
        "veteran": "중견·원로 축의 인물로 분류된다.",
        "global_auteur": "글로벌 작가주의 감독으로 분류된다.",
        "commercial_master": "상업영화 대표 감독으로 분류된다.",
        "auteur": "작가주의 감독으로 분류된다.",
        "genre_master": "장르 특화 감독으로 분류된다.",
    }
    return tier_labels.get(tier, "현재 명성은 추가 데이터가 쌓이면서 정교해진다.")


def _potential_text(stats: dict[str, Any], profile: dict[str, Any]) -> str:
    value = _average(stats, ("growthPotential", "acting", "ticketPower", "directing", "screenplay"))
    if value >= 82:
        return "조건이 맞으면 큰 도약을 만들 가능성이 높다."
    if value >= 66:
        return "작품 선택과 장르 궁합에 따라 성장 여지가 있다."
    if value >= 48:
        return "잠재력보다는 현재 포지션과 경험 활용이 중요하다."
    return "성장보다 역할 전환과 안정적 활용이 더 중요해 보인다."


def _generated_one_line(row: dict[str, Any], profile: dict[str, Any]) -> str:
    if row.get("type") == "actor":
        tags = profile.get("roleType") or []
        if "신스틸러" in tags:
            return "충무로의 감초 역할을 하는 중인 조연 배우."
        if "티켓파워형" in tags:
            return "제작 발표 단계에서 관심을 만들 수 있는 흥행형 배우."
        if "연기파" in tags:
            return "작품의 밀도를 받쳐주는 연기파 배우."
        return "한국영화 캐스팅 풀에서 활용 가능한 배우."
    return "작품의 방향성과 제작 환경을 좌우하는 영화감독."


def _expected_fee_text(
    row: dict[str, Any],
    stats: dict[str, Any],
    profile: dict[str, Any],
    year: int,
    career_context: dict[str, Any] | None = None,
) -> str:
    career_context = career_context or {}
    if row.get("type") != "actor":
        cost = int(_average(stats, ("costLevel", "commercialSense", "festivalPower", "globalRecognition")) or 45)
        tier = str(profile.get("tier") or "")
        base_2020 = {
            "legend": 700000000,
            "global_auteur": 900000000,
            "commercial_master": 800000000,
            "auteur": 350000000,
            "genre_master": 300000000,
            "solid_commercial": 250000000,
            "indie_festival": 90000000,
            "rising_director": 70000000,
            "veteran": 180000000,
        }.get(tier, 120000000)
        base = adjust_money_to_year(base_2020, to_year=year)
        multiplier = max(0.55, min(1.6, cost / 70))
        career_multiplier = _career_fee_multiplier(career_context, row.get("type"))
        estimate = int(base * multiplier * career_multiplier)
        low = int(estimate * 0.75)
        high = int(estimate * 1.25)
        return (
            f"상업 장편 연출 계약 기준 {money(low)}~{money(high)} 수준으로 추정된다. "
            "게임 내 현재 시점까지 공개된 필모그래피, 물가, 제작 규모, 최종 편집권 조건에 따라 달라진다."
        )
    cost = int(_average(stats, ("costLevel", "ticketPower", "brandPower")) or 45)
    tier = str(profile.get("tier") or "")
    base_2020 = {
        "legend": 900000000,
        "top_star": 1000000000,
        "a_list": 550000000,
        "solid_lead": 250000000,
        "character_actor": 120000000,
        "rising": 70000000,
        "newcomer": 20000000,
        "veteran": 180000000,
    }.get(tier, 90000000)
    base = adjust_money_to_year(base_2020, to_year=year)
    multiplier = max(0.55, min(1.45, cost / 70))
    career_multiplier = _career_fee_multiplier(career_context, row.get("type"))
    estimate = int(base * multiplier * career_multiplier)
    low = int(estimate * 0.75)
    high = int(estimate * 1.25)
    return (
        f"상업 장편 기준 {money(low)}~{money(high)} 수준으로 추정된다. "
        "게임 내 현재 시점까지 공개된 필모그래피, 물가, 배역 비중, 촬영 기간에 따라 달라진다."
    )


def _career_fee_multiplier(context: dict[str, Any], person_type: Any) -> float:
    released_count = int(context.get("releasedCount") or 0)
    hit_count = int(context.get("hitCount") or 0)
    major_hit_count = int(context.get("majorHitCount") or 0)
    global_count = int(context.get("globalSignalCount") or 0)
    recent_count = int(context.get("recentCount") or 0)
    years_since_latest = context.get("yearsSinceLatest")
    if released_count <= 0:
        multiplier = 0.58
    elif released_count <= 2:
        multiplier = 0.78
    elif released_count <= 6:
        multiplier = 0.92
    else:
        multiplier = 1.0
    multiplier += min(0.32, hit_count * 0.04 + major_hit_count * 0.08)
    multiplier += min(0.24, global_count * 0.06)
    multiplier += min(0.10, recent_count * 0.025)
    if isinstance(years_since_latest, int):
        if years_since_latest <= 2 and released_count > 0:
            multiplier += 0.08
        elif years_since_latest >= 10:
            multiplier -= min(0.28, (years_since_latest - 8) * 0.035)
    if person_type == "director" and major_hit_count:
        multiplier += min(0.12, major_hit_count * 0.03)
    return max(0.42, min(1.85, multiplier))


def _preferred_roles_text(row: dict[str, Any], profile: dict[str, Any], genre_fit: dict[str, Any]) -> str:
    if row.get("type") == "director":
        return _preferred_projects_text(profile, genre_fit)
    tags = list(profile.get("roleType") or profile.get("directorType") or [])
    genres = list(profile.get("genreTags") or [])
    if not genres and genre_fit:
        genres = list(genre_fit)[:4]
    labels = [_genre_label(genre) for genre in genres[:4]]
    role_phrases: list[str] = []
    if "신스틸러" in tags or str(profile.get("tier")) == "character_actor":
        role_phrases.append("강한 조연과 장면 장악형 배역")
    if "연기파" in tags:
        role_phrases.append("감정 밀도가 높은 드라마 배역")
    if "티켓파워형" in tags or "국민배우" in tags:
        role_phrases.append("제작 발표 단계에서 관객 기대를 끌어올리는 중심 배역")
    if "코미디형" in tags:
        role_phrases.append("생활 코미디와 리듬감 있는 캐릭터")
    if "범죄액션형" in tags:
        role_phrases.append("범죄·액션 장르의 선 굵은 캐릭터")
    if not role_phrases:
        role_phrases.append("현재 이미지와 장르 궁합이 맞는 배역")
    if labels:
        return f"{', '.join(role_phrases)}에 잘 맞는다. 선호 장르는 {', '.join(labels)} 쪽으로 정리된다."
    return f"{', '.join(role_phrases)}에 잘 맞는다."


def _preferred_directors_text(row: dict[str, Any], profile: dict[str, Any]) -> str:
    if row.get("type") == "director":
        return _preferred_collaborators_text(profile)
    tags = set(profile.get("roleType") or [])
    genre_tags = set(profile.get("genreTags") or [])
    preferences: list[str] = []
    if "연기파" in tags or {"drama", "indie_art"} & genre_tags:
        preferences.append("배우의 해석을 존중하는 작가주의·드라마형 감독")
    if "티켓파워형" in tags or {"action", "crime_thriller"} & genre_tags:
        preferences.append("현장 장악력과 장르 통제력이 강한 상업영화 감독")
    if "코미디형" in tags:
        preferences.append("배우의 타이밍과 애드리브를 살리는 코미디 감각의 감독")
    if "글로벌형" in tags:
        preferences.append("해외 영화제나 글로벌 플랫폼 경험이 있는 감독")
    if not preferences:
        preferences.append("배역 설명이 명확하고 현장 소통이 안정적인 감독")
    return ", ".join(preferences) + "과 궁합이 좋다."


def _preferred_projects_text(profile: dict[str, Any], genre_fit: dict[str, Any]) -> str:
    tags = set(profile.get("directorType") or [])
    genres = list(profile.get("genreTags") or [])
    if not genres and genre_fit:
        genres = list(genre_fit)[:4]
    project_types: list[str] = []
    if "작가주의" in tags:
        project_types.append("연출자의 주제와 형식이 강하게 드러나는 작가주의 영화")
    if "상업성" in tags:
        project_types.append("명확한 관객 타깃과 장르 쾌감이 있는 상업영화")
    if "장르혼합" in tags:
        project_types.append("여러 장르를 섞어 새 톤을 만드는 프로젝트")
    if "글로벌" in tags:
        project_types.append("해외 영화제와 글로벌 플랫폼을 동시에 의식하는 프로젝트")
    if "VFX/블록버스터" in tags:
        project_types.append("VFX와 대형 제작 관리가 필요한 프로젝트")
    if not project_types:
        project_types.append("감독의 장점과 제작 규모가 맞는 프로젝트")
    genre_text = ", ".join(_genre_label(genre) for genre in genres[:4])
    if genre_text:
        return f"{', '.join(project_types)}에 강점이 있다. 우선 검토 장르는 {genre_text}다."
    return f"{', '.join(project_types)}에 강점이 있다."


def _preferred_collaborators_text(profile: dict[str, Any]) -> str:
    tags = set(profile.get("directorType") or [])
    collaborators: list[str] = []
    if "작가주의" in tags:
        collaborators.append("감정과 리듬을 오래 맞춰볼 수 있는 연기파 배우")
    if "상업성" in tags:
        collaborators.append("대중 인지도와 현장 대응력이 있는 스타/제작자")
    if "장르혼합" in tags:
        collaborators.append("장르 실험을 받아줄 수 있는 촬영·미술·편집 스태프")
    if "글로벌" in tags:
        collaborators.append("해외 세일즈와 영화제 경험이 있는 프로듀서")
    if not collaborators:
        collaborators.append("제작 방향을 명확히 공유하는 배우와 프로듀서")
    return ", ".join(collaborators) + "와 궁합이 좋다."


def _filmography_entries(timeline: list[dict[str, Any]], protected_works: list[dict[str, Any]]) -> list[str]:
    source = _career_entries_from_profile_lists(timeline, protected_works)
    entries: list[str] = []
    for item in source[:12]:
        date = str(item.get("year") or "연도 미정")
        if item.get("month"):
            date = f"{date}.{int(item['month']):02d}"
        role = _role_label(item.get("role"))
        summary = item.get("summary")
        if summary and summary != role:
            entries.append(f"{date} · {item['title']} · {role} · {summary}")
        else:
            entries.append(f"{date} · {item['title']} · {role}")
    return entries


def _career_intro(
    row: dict[str, Any],
    profile: dict[str, Any],
    stats: dict[str, Any],
    timeline: list[dict[str, Any]],
    protected_works: list[dict[str, Any]],
    year: int,
) -> str:
    start = row.get("available_from")
    tier = str(profile.get("tier") or "")
    tags = profile.get("roleType") or profile.get("directorType") or []
    genres = [_genre_label(genre) for genre in (profile.get("genreTags") or [])[:3]]
    career_count = len(_career_entries_from_profile_lists(timeline, protected_works))
    sentences: list[str] = []
    if isinstance(start, int):
        if year < start:
            sentences.append(f"{start}년 이후 본격적으로 등장할 인물로 분류된다.")
        else:
            sentences.append(f"{start}년 무렵부터 한국영화 데이터베이스에 등장하는 인물이다.")
    else:
        sentences.append("활동 시작 연도는 아직 정밀하게 정리되지 않았다.")
    if tier:
        sentences.append(_tier_text(profile))
    if tags:
        sentences.append(f"게임 데이터상 주요 유형은 {', '.join(map(str, tags[:4]))} 쪽으로 잡혀 있다.")
    if genres:
        sentences.append(f"장르 활용도는 {', '.join(genres)}에서 먼저 검토된다.")
    if career_count:
        sentences.append(f"게임 내 현재 시점까지 연결된 커리어 기록은 {career_count}건이며, 이후 실제 DB 수집에 따라 세부 필모그래피가 보강된다.")
    else:
        sentences.append("아직 실제 필모그래피 연결은 부족하지만, 티어·태그·시대 보정으로 초기 평가가 생성되어 있다.")
    if _average(stats, ("globalRecognition", "festivalPower")) >= 78:
        sentences.append("해외 영화제나 글로벌 유통에서도 활용 가치가 있는 인물로 분류된다.")
    return " ".join(sentences)


def _critic_one_line(row: dict[str, Any], critic_types: list[Any], influence: dict[str, Any]) -> str:
    tags = ", ".join(str(tag) for tag in critic_types[:2])
    public = float(influence.get("public") or 0)
    cinephile = float(influence.get("cinephile") or 0)
    if public >= 68 and cinephile >= 68:
        return f"대중 관객과 시네필 양쪽에 영향을 주는 {tags or '복합형'} 평론가."
    if cinephile >= public:
        return f"시네필과 평론 담론에 강한 {tags or '비평 중심'} 평론가."
    return f"대중 반응과 관람 선택에 영향을 주는 {tags or '대중 영향형'} 평론가."


def _critic_influence_text(influence: dict[str, Any]) -> str:
    parts = []
    for key, label in (
        ("public", "대중 영향력"),
        ("cinephile", "시네필 영향력"),
        ("awards", "시상식 영향력"),
        ("online", "온라인 확산력"),
    ):
        parts.append(f"{label}: {_influence_phrase(influence.get(key))}")
    return "\n".join(parts)


def _critic_taste_text(taste: dict[str, Any]) -> str:
    if not taste:
        return "세부 취향 데이터가 아직 정리되지 않았다."
    labels = {
        "narrative": "서사 구조",
        "directing": "연출 완성도",
        "emotion": "감정선",
        "genreCraft": "장르 완성도",
        "auteurism": "작가주의",
        "commercialEntertainment": "상업 오락성",
        "socialMeaning": "사회적 의미",
        "technicalCraft": "기술 완성도",
    }
    ranked = sorted(
        ((key, value) for key, value in taste.items() if isinstance(value, int | float)),
        key=lambda item: float(item[1]),
        reverse=True,
    )
    strengths = [labels.get(key, key) for key, _ in ranked[:3]]
    softer = [labels.get(key, key) for key, _ in ranked[-2:]]
    text = f"우선 검토 축은 {', '.join(strengths)} 쪽이다." if strengths else "평가 축이 아직 뚜렷하지 않다."
    if softer:
        text += f" 상대적으로 {', '.join(softer)} 항목은 작품마다 유연하게 평가한다."
    return text


def _critic_scoring_text(scoring: dict[str, Any]) -> str:
    if not scoring:
        return "별점과 한줄평 스타일은 아직 정리되지 않았다."
    strictness = float(scoring.get("strictness") or 0)
    impact = float(scoring.get("oneLineImpact") or 0)
    depth = float(scoring.get("reviewDepth") or 0)
    phrases = []
    if strictness >= 70:
        phrases.append("평점은 비교적 엄격한 편이다")
    elif strictness >= 55:
        phrases.append("평점은 균형형에 가깝다")
    else:
        phrases.append("평점 운용은 비교적 유연한 편이다")
    if impact >= 68:
        phrases.append("한줄평의 파급력이 크다")
    if depth >= 68:
        phrases.append("장문 리뷰와 해석의 영향도 남는다")
    return ". ".join(phrases) + "."


def _critic_preference_text(taste: dict[str, Any], critic_types: list[Any]) -> str:
    preferences: list[str] = []
    if float(taste.get("auteurism") or 0) >= 65 or "시네필형" in critic_types:
        preferences.append("감독의 세계관과 형식이 분명한 작품")
    if float(taste.get("narrative") or 0) >= 65:
        preferences.append("서사 구조와 인물 설계가 탄탄한 작품")
    if float(taste.get("genreCraft") or 0) >= 65:
        preferences.append("장르 문법을 정확히 이해한 영화")
    if float(taste.get("emotion") or 0) >= 65:
        preferences.append("감정선이 섬세하게 축적되는 영화")
    if float(taste.get("socialMeaning") or 0) >= 65:
        preferences.append("시대와 사회를 해석할 여지가 있는 영화")
    if float(taste.get("commercialEntertainment") or 0) >= 65:
        preferences.append("대중 오락성과 완성도를 함께 갖춘 영화")
    if not preferences:
        preferences.append("완성도와 태도가 분명한 영화")
    return ", ".join(preferences) + "에 더 적극적으로 반응할 가능성이 있다."


def _critic_career_intro(
    row: dict[str, Any],
    critic_types: list[Any],
    taste: dict[str, Any],
    influence: dict[str, Any],
    reviews: list[str],
) -> str:
    sentences: list[str] = []
    available_from = row.get("available_from")
    if isinstance(available_from, int):
        sentences.append(f"{available_from}년 이후 평론 데이터에 등장하는 평론가다.")
    else:
        sentences.append("활동 시작 시점은 아직 정밀하게 정리되지 않았다.")
    if critic_types:
        sentences.append(f"게임 데이터상 유형 데이터는 {', '.join(map(str, critic_types))}다.")
    sentences.append(_critic_taste_text(taste))
    if _average(influence, ("public", "cinephile", "online")) >= 65:
        sentences.append("플레이어 영화의 초반 인식과 온라인 회자에 영향을 줄 수 있다.")
    elif float(influence.get("awards") or 0) >= 60:
        sentences.append("대중 화제성보다 시상식과 평론 담론 쪽 영향이 더 중요하다.")
    else:
        sentences.append("영향력은 제한적이지만 특정 관객층의 해석에는 의미가 있다.")
    if reviews:
        sentences.append("연결된 리뷰 기록은 이후 영화별 평론 반응 시스템에서 누적된다.")
    else:
        sentences.append("아직 실제 리뷰 기록은 연결되지 않았고, 성향 태그를 바탕으로 가상 평론을 생성한다.")
    return " ".join(sentences)


def _influence_phrase(value: Any) -> str:
    if not isinstance(value, int | float):
        return "자료 부족"
    if value >= 80:
        return "매우 강함"
    if value >= 65:
        return "강한 편"
    if value >= 50:
        return "보통 이상"
    if value >= 35:
        return "제한적"
    return "낮음"


def _average(values: dict[str, Any], keys: tuple[str, ...]) -> float:
    nums = [float(values[key]) for key in keys if isinstance(values.get(key), int | float)]
    if not nums:
        return 0.0
    return sum(nums) / len(nums)


def _genre_label(genre_id: Any) -> str:
    labels = {
        "drama": "드라마",
        "family_human_drama": "가족/휴먼드라마",
        "crime_thriller": "범죄 스릴러",
        "crime": "범죄",
        "action": "액션",
        "comedy": "코미디",
        "horror_occult": "공포/오컬트",
        "romance_melodrama": "로맨스/멜로",
        "historical_period": "사극/시대극",
        "historical": "사극/시대극",
        "period_historical": "사극/시대극",
        "social_true_story": "사회고발/실화극",
        "indie_art": "독립/예술영화",
        "sf": "SF",
        "sf_disaster_monster": "SF/재난/괴수",
        "fantasy": "판타지",
        "black_comedy": "블랙코미디",
        "monster": "괴수",
        "noir": "누아르",
    }
    return labels.get(str(genre_id), str(genre_id).replace("_", " "))


def _role_label(role: Any) -> str:
    labels = {
        "lead_actor": "주연",
        "supporting_actor": "조연",
        "cameo_actor": "특별출연",
        "minor_actor": "단역/소조연",
        "day_player": "단역",
        "background_actor": "이미지/군중",
        "actor": "배우",
        "director": "감독",
        "main_director": "감독",
        "attached": "참여",
    }
    return labels.get(str(role), str(role or "참여"))


def _public_person(row: Any) -> dict[str, Any]:
    profile = loads_json(row["public_profile_json"], {})
    return {
        "id": row["id"],
        "name_ko": row["name_ko"],
        "name_en": row["name_en"],
        "type": row["type"],
        "one_line": profile.get("oneLine", "아직 공개 평가가 충분하지 않다."),
        "current_ability_text": profile.get("currentAbilityText", "현재 능력은 업계 자료를 더 확인해야 한다."),
        "potential_text": profile.get("potentialText", "성장 가능성은 작품 선택에 따라 달라질 수 있다."),
        "fame_text": profile.get("fameText", "명성 정보가 제한적이다."),
        "brand_text": profile.get("brandText", "브랜드 평판이 아직 뚜렷하지 않다."),
    }


def _contribution_for_role(role: str, stats: dict[str, Any]) -> dict[str, int]:
    if role in {"lead_actor", "supporting_actor", "cameo_actor", "minor_actor", "day_player", "background_actor", "actor"}:
        acting_quality = stats.get("acting_quality", stats.get("acting", 55))
        casting_fit = stats.get("casting_fit", stats.get("brandPower", acting_quality))
        pre_release_interest = stats.get(
            "public_reputation",
            max(
                stats.get("ticketPower", 45),
                stats.get("brandPower", 45),
                stats.get("globalRecognition", 45),
            ),
        )
        return {
            "acting_quality": int(acting_quality),
            "casting_fit": int(casting_fit),
            "pre_release_interest": int(pre_release_interest),
        }
    if role in {"director", "main_director"}:
        directing_quality = stats.get("directing_quality", stats.get("directing", 55))
        field_control = stats.get("field_control", max(stats.get("commercialSense", 50), stats.get("festivalPower", 50)))
        artistic_sense = stats.get("artistic_sense", stats.get("auteurPower", directing_quality))
        return {
            "directing_quality": int(directing_quality),
            "field_control": int(field_control),
            "artistic_sense": int(artistic_sense),
        }
    return {key: int(value) for key, value in stats.items() if isinstance(value, int | float)}
