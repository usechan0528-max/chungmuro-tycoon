from __future__ import annotations

import uuid
from typing import Any

from app.database import dumps_json, get_connection, loads_json
from app.services.budget_service import recommend_allocation_percentages
from app.services.economic_service import adjusted_scale_budget
from app.services.event_engine import describe_choice_outcome
from app.services.game_state import clamp


IP_COLUMN_EFFECTS = {
    "ip_value",
    "franchise_power",
    "sequel_demand",
    "cult_potential",
    "reevaluation_potential",
}


def evaluate_ip_after_release(film_id: str) -> None:
    with get_connection() as conn:
        existing_entry = conn.execute("SELECT 1 FROM ip_entries WHERE film_id = ?", (film_id,)).fetchone()
        if existing_entry:
            return
        film = conn.execute("SELECT * FROM completed_films WHERE id = ?", (film_id,)).fetchone()
        if not film:
            return
        audience = int(film["final_audience"] or 0)
        break_even = int(film["break_even_audience"] or 1)
        audience_score = int(film["audience_score"] or 0)
        critic_score = int(film["critic_score"] or 0)
        sequel_demand = max(0, min(100, int((audience / max(break_even, 1)) * 35 + audience_score * 0.4)))
        cult_potential = max(0, min(100, int(critic_score * 0.45 + audience_score * 0.25)))
        ip_value = max(sequel_demand, cult_potential)
        if sequel_demand < 45 and cult_potential < 55:
            return
        ip_id = f"ip_{uuid.uuid4().hex[:10]}"
        conn.execute(
            """
            INSERT INTO intellectual_properties (
                id, title, origin_film_id, owner_type, owner_id, ip_type,
                ip_value, franchise_power, sequel_demand, cult_potential,
                reevaluation_potential, status, metadata_json
            ) VALUES (?, ?, ?, 'studio', 'studio_1', 'original', ?, ?, ?, ?, ?, 'active', ?)
            """,
            (
                ip_id,
                film["title"],
                film_id,
                ip_value,
                ip_value,
                sequel_demand,
                cult_potential,
                max(0, 100 - audience_score),
                dumps_json({"createdBy": "release_evaluation"}),
            ),
        )
        conn.execute(
            """
            INSERT INTO systems_franchise (
                id, title, origin_movie_id, owner_type, owner_id, ip_type,
                ip_value, franchise_power, sequel_demand, cult_potential,
                reevaluation_potential, status, metadata_json
            ) VALUES (?, ?, ?, 'studio', 'studio_1', 'original', ?, ?, ?, ?, ?, 'active', ?)
            """,
            (
                ip_id,
                film["title"],
                film_id,
                ip_value,
                ip_value,
                sequel_demand,
                cult_potential,
                max(0, 100 - audience_score),
                dumps_json({"createdBy": "release_evaluation"}),
            ),
        )
        conn.execute(
            """
            INSERT INTO ip_entries (
                ip_id, film_id, entry_type, sequence_no, year, month, result_json
            ) VALUES (?, ?, 'film', 1, ?, ?, ?)
            """,
            (
                ip_id,
                film_id,
                film["release_year"],
                film["release_month"],
                dumps_json({"audience": audience, "audienceScore": audience_score}),
            ),
        )
        conn.execute(
            """
            INSERT INTO movies_post_release_metrics (
                movie_id, metric_type, year, month, value, summary, effects_json
            ) VALUES (?, 'franchise_seed', ?, ?, ?, ?, ?)
            """,
            (
                film_id,
                film["release_year"],
                film["release_month"],
                ip_value,
                "시리즈화 또는 IP 확장 후보로 기록되었다.",
                dumps_json({"ipId": ip_id}),
            ),
        )
        conn.commit()


def list_franchise_offers() -> list[dict[str, Any]]:
    offers: list[dict[str, Any]] = []
    with get_connection() as conn:
        ips = conn.execute(
            """
            SELECT ip.*, film.final_audience, film.release_year, film.release_month
            FROM intellectual_properties ip
            LEFT JOIN completed_films film ON film.id = ip.origin_film_id
            WHERE ip.status = 'active'
            ORDER BY ip.title
            """
        ).fetchall()
        events = _load_franchise_events(conn)

    for ip_row in ips:
        ip = dict(ip_row)
        metadata = loads_json(ip.get("metadata_json"), {})
        if metadata.get("developmentStatus") in {"in_development", "preserved"}:
            continue
        for event in events:
            if _franchise_trigger_matches(event.get("trigger", {}), ip):
                offers.append({"ip": ip, "event": event})
    return offers


def get_franchise_offer(ip_id: str) -> dict[str, Any] | None:
    with get_connection() as conn:
        ip_row = conn.execute(
            """
            SELECT ip.*, film.final_audience, film.release_year, film.release_month
            FROM intellectual_properties ip
            LEFT JOIN completed_films film ON film.id = ip.origin_film_id
            WHERE ip.id = ?
            """,
            (ip_id,),
        ).fetchone()
        if not ip_row:
            return None
        ip = dict(ip_row)
        metadata = loads_json(ip.get("metadata_json"), {})
        if metadata.get("developmentStatus") in {"in_development", "preserved"}:
            return None
        for event in _load_franchise_events(conn):
            if _franchise_trigger_matches(event.get("trigger", {}), ip):
                return {"ip": ip, "event": event}
    return None


def apply_franchise_choice(ip_id: str, event: dict[str, Any], choice: dict[str, Any]) -> dict[str, Any]:
    effects = choice.get("effects", {})
    with get_connection() as conn:
        ip = conn.execute("SELECT * FROM intellectual_properties WHERE id = ?", (ip_id,)).fetchone()
        player = conn.execute("SELECT current_year, current_month FROM player_state WHERE id = 1").fetchone()
        if not ip:
            raise ValueError("IP 정보를 찾을 수 없습니다.")

        metadata = loads_json(ip["metadata_json"], {})
        updates = {
            "ip_value": int(ip["ip_value"] or 0),
            "franchise_power": int(ip["franchise_power"] or 0),
            "sequel_demand": int(ip["sequel_demand"] or 0),
            "cult_potential": int(ip["cult_potential"] or 0),
            "reevaluation_potential": int(ip["reevaluation_potential"] or 0),
        }
        for key, delta in effects.items():
            if key in IP_COLUMN_EFFECTS:
                updates[key] = clamp(updates.get(key, 0) + int(delta))
            else:
                metadata[key] = clamp(int(metadata.get(key, 0) or 0) + int(delta))
        metadata["lastFranchiseChoice"] = choice.get("id")
        metadata["lastFranchiseEventId"] = event.get("id")
        if choice.get("id") in {"make_direct_sequel", "make_spinoff"}:
            metadata["developmentStatus"] = "in_development"
        elif choice.get("id") == "preserve_ip":
            metadata["developmentStatus"] = "preserved"

        conn.execute(
            """
            UPDATE intellectual_properties
            SET ip_value = ?, franchise_power = ?, sequel_demand = ?,
                cult_potential = ?, reevaluation_potential = ?, metadata_json = ?
            WHERE id = ?
            """,
            (
                updates["ip_value"],
                updates["franchise_power"],
                updates["sequel_demand"],
                updates["cult_potential"],
                updates["reevaluation_potential"],
                dumps_json(metadata),
                ip_id,
            ),
        )
        conn.execute(
            """
            UPDATE systems_franchise
            SET ip_value = ?, franchise_power = ?, sequel_demand = ?,
                cult_potential = ?, reevaluation_potential = ?, metadata_json = ?
            WHERE id = ?
            """,
            (
                updates["ip_value"],
                updates["franchise_power"],
                updates["sequel_demand"],
                updates["cult_potential"],
                updates["reevaluation_potential"],
                dumps_json(metadata),
                ip_id,
            ),
        )
        year = int(player["current_year"]) if player else 0
        month = int(player["current_month"]) if player else 1
        conn.execute(
            """
            INSERT INTO ip_entries (
                ip_id, film_id, entry_type, sequence_no, year, month, result_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                ip_id,
                ip["origin_film_id"],
                _franchise_entry_type(choice.get("id")),
                _next_ip_sequence(conn, ip_id),
                year,
                month,
                dumps_json({"eventId": event.get("id"), "choiceId": choice.get("id"), "effects": effects}),
            ),
        )
        conn.execute(
            """
            INSERT INTO movies_post_release_metrics (
                movie_id, metric_type, year, month, value, summary, effects_json
            ) VALUES (?, 'franchise_decision', ?, ?, ?, ?, ?)
            """,
            (
                ip["origin_film_id"],
                year,
                month,
                max(updates["ip_value"], updates["franchise_power"], updates["sequel_demand"]),
                choice.get("text", "시리즈화 판단"),
                dumps_json({"eventId": event.get("id"), "choiceId": choice.get("id"), "effects": effects}),
            ),
        )
        ip_for_seed = dict(ip)
        ip_for_seed.update(updates)
        ip_for_seed["metadata_json"] = dumps_json(metadata)
        project_seed = (
            _build_project_seed(conn, ip_for_seed, choice, year)
            if choice.get("id") in {"make_direct_sequel", "make_spinoff"}
            else None
        )
        conn.commit()

    return {
        "ip_id": ip_id,
        "ip": updates,
        "metadata": metadata,
        "project_seed": project_seed,
        "outcome_summary": describe_choice_outcome(event, choice, {"stats": effects}),
    }


def record_franchise_release(project_id: str, film_id: str) -> None:
    with get_connection() as conn:
        project = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
        film = conn.execute("SELECT * FROM completed_films WHERE id = ?", (film_id,)).fetchone()
        if not project or not film:
            return
        stats = loads_json(project["stats_json"], {})
        context = stats.get("franchise_context") if isinstance(stats, dict) else None
        if not isinstance(context, dict) or not context.get("ipId"):
            return
        ip_id = str(context["ipId"])
        existing = conn.execute(
            "SELECT 1 FROM ip_entries WHERE ip_id = ? AND film_id = ?",
            (ip_id, film_id),
        ).fetchone()
        if existing:
            return
        ip = conn.execute("SELECT * FROM intellectual_properties WHERE id = ?", (ip_id,)).fetchone()
        if not ip:
            return

        entry_type = str(context.get("entryType") or "direct_sequel")
        audience = int(film["final_audience"] or 0)
        break_even = max(1, int(film["break_even_audience"] or 1))
        audience_score = int(film["audience_score"] or 0)
        critic_score = int(film["critic_score"] or 0)
        success_pressure = audience / break_even
        ip_value_delta = int(min(12, max(-8, (success_pressure - 1.0) * 10 + (audience_score - 60) / 8)))
        franchise_delta = int(min(14, max(-10, (success_pressure - 1.0) * 12 + (audience_score - 55) / 7)))
        sequel_delta = int(min(12, max(-10, (success_pressure - 1.0) * 11 + (audience_score - 60) / 6)))

        metadata = loads_json(ip["metadata_json"], {})
        metadata["lastReleasedFilmId"] = film_id
        metadata["lastReleasedEntryType"] = entry_type
        metadata["lastReleasedTitle"] = film["title"]
        metadata["developmentStatus"] = "active"
        metadata["seriesFatigue"] = clamp(int(metadata.get("seriesFatigue", 0) or 0) + int(context.get("seriesFatigue", 0) or 0))

        updates = {
            "ip_value": clamp(int(ip["ip_value"] or 0) + ip_value_delta),
            "franchise_power": clamp(int(ip["franchise_power"] or 0) + franchise_delta),
            "sequel_demand": clamp(int(ip["sequel_demand"] or 0) + sequel_delta),
            "cult_potential": clamp(int(ip["cult_potential"] or 0) + max(0, int((critic_score - 65) / 5))),
            "reevaluation_potential": int(ip["reevaluation_potential"] or 0),
        }
        conn.execute(
            """
            UPDATE intellectual_properties
            SET ip_value = ?, franchise_power = ?, sequel_demand = ?,
                cult_potential = ?, reevaluation_potential = ?, metadata_json = ?
            WHERE id = ?
            """,
            (
                updates["ip_value"],
                updates["franchise_power"],
                updates["sequel_demand"],
                updates["cult_potential"],
                updates["reevaluation_potential"],
                dumps_json(metadata),
                ip_id,
            ),
        )
        conn.execute(
            """
            UPDATE systems_franchise
            SET ip_value = ?, franchise_power = ?, sequel_demand = ?,
                cult_potential = ?, reevaluation_potential = ?, metadata_json = ?
            WHERE id = ?
            """,
            (
                updates["ip_value"],
                updates["franchise_power"],
                updates["sequel_demand"],
                updates["cult_potential"],
                updates["reevaluation_potential"],
                dumps_json(metadata),
                ip_id,
            ),
        )
        conn.execute(
            """
            INSERT INTO ip_entries (
                ip_id, film_id, entry_type, sequence_no, year, month, result_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                ip_id,
                film_id,
                entry_type,
                _next_ip_sequence(conn, ip_id),
                film["release_year"],
                film["release_month"],
                dumps_json(
                    {
                        "audience": audience,
                        "audienceScore": audience_score,
                        "criticScore": critic_score,
                        "breakEvenAudience": break_even,
                        "ipValueDelta": ip_value_delta,
                        "franchisePowerDelta": franchise_delta,
                        "sequelDemandDelta": sequel_delta,
                    }
                ),
            ),
        )
        conn.commit()


def _load_franchise_events(conn: Any) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT * FROM simulation_events
        WHERE category = 'franchise'
        ORDER BY weight DESC, id
        """
    ).fetchall()
    return [
        {
            "id": row["id"],
            "category": row["category"],
            "stage": row["stage"],
            "scope": row["scope"],
            "title": row["title"],
            "description": row["description"],
            "fixed_level": row["fixed_level"],
            "weight": row["weight"],
            "cooldown_months": row["cooldown_months"],
            "trigger": loads_json(row["trigger_json"], {}),
            "choices": loads_json(row["choices_json"], []),
        }
        for row in rows
    ]


def _franchise_trigger_matches(trigger: dict[str, Any], ip: dict[str, Any]) -> bool:
    if int(ip.get("final_audience") or 0) < int(trigger.get("minFinalAudience", 0) or 0):
        return False
    if int(ip.get("ip_value") or 0) < int(trigger.get("minIpValue", 0) or 0):
        return False
    return True


def _franchise_entry_type(choice_id: str | None) -> str:
    if choice_id == "make_direct_sequel":
        return "sequel_plan"
    if choice_id == "make_spinoff":
        return "spinoff_plan"
    if choice_id == "preserve_ip":
        return "ip_preserved"
    return "franchise_decision"


def _next_ip_sequence(conn: Any, ip_id: str) -> int:
    row = conn.execute(
        "SELECT COALESCE(MAX(sequence_no), 0) + 1 AS next_sequence FROM ip_entries WHERE ip_id = ?",
        (ip_id,),
    ).fetchone()
    return int(row["next_sequence"] or 1)


def _build_project_seed(conn: Any, ip: dict[str, Any], choice: dict[str, Any], current_year: int) -> dict[str, Any] | None:
    origin = conn.execute(
        """
        SELECT c.*
        FROM completed_films c
        WHERE c.id = ?
        """,
        (ip.get("origin_film_id"),),
    ).fetchone()
    if not origin:
        return None
    origin_data = dict(origin)
    choice_id = str(choice.get("id") or "")
    is_spinoff = choice_id == "make_spinoff"
    genre_id = origin_data.get("genre_id")
    scale_id = origin_data.get("scale_id")
    scale = conn.execute("SELECT * FROM project_scales WHERE id = ?", (scale_id,)).fetchone()
    base_production = int(origin_data.get("production_budget") or 0)
    base_marketing = int(origin_data.get("marketing_budget") or max(0, base_production * 0.25))
    multiplier = 0.82 if is_spinoff else 1.15
    production_budget = int(base_production * multiplier)
    marketing_budget = int(base_marketing * (0.85 if is_spinoff else 1.1))
    if scale:
        adjusted = adjusted_scale_budget(dict(scale), current_year)
        production_budget = min(
            max(production_budget, int(adjusted["min_budget"])),
            int(adjusted["max_budget"]),
        )
    elif production_budget <= 0:
        production_budget = 1_000_000_000
    if marketing_budget <= 0:
        marketing_budget = int(production_budget * 0.25)

    genre = conn.execute("SELECT * FROM genres WHERE id = ?", (genre_id,)).fetchone()
    allocation = recommend_allocation_percentages(genre or {})
    metadata = loads_json(ip.get("metadata_json"), {})
    fatigue = int(metadata.get("seriesFatigue", metadata.get("series_fatigue", 0)) or 0)
    return {
        "title": _series_project_title(conn, str(ip.get("id")), str(ip.get("title") or origin_data.get("title")), choice_id),
        "genre_id": genre_id,
        "scale_id": scale_id,
        "production_budget": production_budget,
        "marketing_budget": marketing_budget,
        "allocation": allocation,
        "franchise_context": {
            "ipId": ip.get("id"),
            "originFilmId": ip.get("origin_film_id"),
            "originTitle": ip.get("title") or origin_data.get("title"),
            "sourceChoiceId": choice_id,
            "entryType": "spinoff" if is_spinoff else "direct_sequel",
            "ipValue": int(ip.get("ip_value") or 0),
            "franchisePower": int(ip.get("franchise_power") or 0),
            "sequelDemand": int(ip.get("sequel_demand") or 0),
            "seriesFatigue": fatigue + int((choice.get("effects") or {}).get("series_fatigue", 0) or 0),
        },
    }


def _series_project_title(conn: Any, ip_id: str, base_title: str, choice_id: str) -> str:
    if choice_id == "make_spinoff":
        return f"{base_title}: 스핀오프"
    row = conn.execute(
        """
        SELECT COUNT(*) + 1 AS next_no
        FROM ip_entries
        WHERE ip_id = ?
          AND entry_type IN ('film', 'direct_sequel', 'spinoff')
        """,
        (ip_id,),
    ).fetchone()
    next_no = max(2, int(row["next_no"] or 2))
    return f"{base_title} {next_no}"
