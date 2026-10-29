from __future__ import annotations

import math
import uuid
from typing import Any

from app.config import STUDIO_RECOVERY_RATE
from app.database import dumps_json, get_connection, loads_json
from app.services.game_state import clamp
from app.services.boxoffice_formula import (
    calculate_audience_score,
    calculate_base_audience,
    calculate_boxoffice,
    calculate_critic_score,
    calculate_final_quality,
    calculate_market_modifier,
    calculate_opening_interest,
    calculate_release_settlement,
    calculate_reputation_changes,
    calculate_second_week_drop,
    calculate_word_of_mouth,
    project_total_cost,
    summarize_result,
)
from app.services.version_service import (
    apply_release_version_modifiers,
    record_released_versions,
)
from app.services.market_service import ensure_market_state_with_connection


SCALE_MARKET_MULTIPLIER = {
    "scale_short": 0.08,
    "scale_independent": 0.22,
    "scale_low_budget_genre": 0.55,
    "scale_mid_commercial": 1.0,
    "scale_large_commercial": 1.35,
    "scale_tentpole": 1.7,
}

ERA_GENRE_ALIASES = {
    "genre_crime_thriller": ("crime_thriller", "crime", "crime_action", "crime_action_franchise", "ott_thriller"),
    "genre_action": ("action", "crime_action", "crime_action_franchise"),
    "genre_horror_occult": ("horror_occult", "horror", "low_budget_horror"),
    "genre_romance_melodrama": ("romance_melodrama", "melodrama", "romance_comedy", "romance_melodrama_theatrical", "romance_melodrama_ott"),
    "genre_comedy": ("comedy", "romance_comedy"),
    "genre_family_human_drama": ("social_drama", "literary_drama", "melodrama"),
    "genre_period_historical": ("historical", "war"),
    "genre_social_true_story": ("social_drama", "social_true_story", "literary_drama"),
    "genre_indie_art": ("independent_art", "independent_art_festival"),
    "genre_sf_disaster_monster": ("sf_disaster", "disaster", "monster"),
    "genre_fantasy": ("fantasy", "fantasy_ip"),
    "genre_animation": ("animation",),
}

FINAL_QUALITY_WEIGHTS = {
    "scenario_quality": 0.20,
    "directing_quality": 0.18,
    "acting_quality": 0.15,
    "casting_fit": 0.10,
    "genre_satisfaction": 0.15,
    "editing_quality": 0.10,
    "music_sound_quality": 0.05,
    "vfx_quality": 0.04,
    "shooting_quality": 0.03,
}

AUDIENCE_SCORE_WEIGHTS = {
    "final_quality": 0.35,
    "genre_satisfaction": 0.25,
    "casting_fit": 0.15,
    "acting_quality": 0.10,
    "pre_release_interest": 0.05,
    "audience_rejection_risk": -0.10,
}

THEATRICAL_RUN_DAYS = {
    "scale_short": 7,
    "scale_independent": 14,
    "scale_low_budget_genre": 21,
    "scale_mid_commercial": 28,
    "scale_large_commercial": 35,
    "scale_tentpole": 42,
}


def release_project(project_id: str) -> dict[str, Any]:
    with get_connection() as conn:
        project = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
        player = conn.execute("SELECT * FROM player_state WHERE id = 1").fetchone()
        studio = conn.execute("SELECT * FROM studio_state WHERE id = 1").fetchone()
        if not project or not player or not studio:
            raise ValueError("개봉할 프로젝트를 찾을 수 없습니다.")
        genre = conn.execute("SELECT * FROM genres WHERE id = ?", (project["genre_id"],)).fetchone()
        scale = conn.execute("SELECT * FROM project_scales WHERE id = ?", (project["scale_id"],)).fetchone()

        era = conn.execute(
            """
            SELECT * FROM eras
            WHERE start_year <= ? AND (end_year IS NULL OR end_year >= ?)
            ORDER BY start_year DESC
            LIMIT 1
            """,
            (player["current_year"], player["current_year"]),
        ).fetchone()
        if not era:
            era = conn.execute("SELECT * FROM eras ORDER BY start_year DESC LIMIT 1").fetchone()
        market_state = ensure_market_state_with_connection(
            conn,
            int(player["current_year"]),
            int(player["current_month"]),
        )

        ticket = conn.execute(
            """
            SELECT * FROM ticket_prices
            WHERE year <= ?
            ORDER BY year DESC
            LIMIT 1
            """,
            (player["current_year"],),
        ).fetchone()
        if not ticket:
            ticket = conn.execute("SELECT * FROM ticket_prices ORDER BY year LIMIT 1").fetchone()

        stats, version_profile = apply_release_version_modifiers(
            conn,
            project_id,
            loads_json(project["stats_json"], {}),
        )
        market = dict(era)
        market["year"] = int(player["current_year"])
        if market_state:
            modifiers = loads_json(market_state["modifiers_json"], {})
            market.update(
                {
                    "theater_demand": market_state["theater_demand"],
                    "ott_power": market_state["ott_power"],
                    "foreign_competition": market_state["foreign_competition"],
                    **modifiers,
                }
            )
        calculated = calculate_boxoffice(stats, dict(project), market, dict(ticket), dict(genre) if genre else {})
        calculated["version_profile"] = version_profile
        calculated["release_version_name"] = (version_profile.get("theatrical") or {}).get("name")
        calculated["ott_version_name"] = (version_profile.get("ott") or {}).get("name")
        from app.services.finance_service import add_settlement_to_own_capital, settlement_financing

        _apply_casting_settlement(conn, project_id, calculated)
        calculated = settlement_financing(conn, project_id, calculated)
        reputation_changes = calculate_reputation_changes(calculated)
        fame_delta = int(reputation_changes["studio_fame_delta"])
        calculated["fame_delta"] = fame_delta
        calculated["reputation_deltas"] = reputation_changes["reputation"]
        calculated["network_deltas"] = reputation_changes["network"]
        film_id = f"film_{uuid.uuid4().hex[:10]}"
        result_summary = summarize_result(calculated)

        conn.execute(
            """
            INSERT INTO completed_films (
                id, title, genre_id, scale_id, release_year, release_month,
                production_budget, marketing_budget, total_cost, final_audience,
                gross_revenue, break_even_audience, critic_score,
                audience_score, content_rating, rating_reason_json, result_summary
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                film_id,
                project["title"],
                project["genre_id"],
                project["scale_id"],
                player["current_year"],
                player["current_month"],
                project["production_budget"],
                project["marketing_budget"],
                calculated["total_cost"],
                calculated["final_audience"],
                calculated["gross_revenue"],
                calculated["break_even_audience"],
                calculated["critic_score"],
                calculated["audience_score"],
                calculated.get("content_rating"),
                dumps_json(calculated.get("content_rating_reasons", [])),
                result_summary,
            ),
        )
        conn.execute(
            """
            INSERT INTO movies_player_created (
                id, title, genre_id, scale_id, release_year, release_month,
                production_budget, marketing_budget, total_cost, final_audience,
                gross_revenue, break_even_audience, critic_score,
                audience_score, content_rating, rating_reason_json, result_summary
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                film_id,
                project["title"],
                project["genre_id"],
                project["scale_id"],
                player["current_year"],
                player["current_month"],
                project["production_budget"],
                project["marketing_budget"],
                calculated["total_cost"],
                calculated["final_audience"],
                calculated["gross_revenue"],
                calculated["break_even_audience"],
                calculated["critic_score"],
                calculated["audience_score"],
                calculated.get("content_rating"),
                dumps_json(calculated.get("content_rating_reasons", [])),
                result_summary,
            ),
        )
        conn.execute(
            """
            INSERT OR REPLACE INTO movies (
                id, title, movie_type, genre_id, scale_id, status, metadata_json
            ) VALUES (?, ?, 'player_created', ?, ?, 'released', ?)
            """,
            (
                film_id,
                project["title"],
                project["genre_id"],
                project["scale_id"],
                dumps_json(
                    {
                        "projectId": project_id,
                        "versionProfile": version_profile,
                        "distribution": _project_distribution_metadata(conn, project_id),
                    }
                ),
            ),
        )
        conn.execute(
            """
            INSERT OR REPLACE INTO movies_boxoffice (
                movie_id, final_audience, gross_revenue, studio_revenue,
                secondary_market_revenue, break_even_audience, profit,
                metrics_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                film_id,
                calculated["final_audience"],
                calculated["gross_revenue"],
                calculated["studio_revenue"],
                calculated["secondary_market_revenue"],
                calculated["break_even_audience"],
                calculated["profit"],
                dumps_json(calculated),
            ),
        )

        new_fame = clamp(int(studio["fame"]) + fame_delta)

        reputation = loads_json(player["reputation_json"], {})
        network = loads_json(player["network_json"], {})
        for key, delta in reputation_changes["reputation"].items():
            reputation[key] = clamp(float(reputation.get(key, 10)) + float(delta))
        for key, delta in reputation_changes["network"].items():
            network[key] = clamp(float(network.get(key, 10)) + float(delta))

        add_settlement_to_own_capital(conn, player, project_id, calculated)
        conn.execute("UPDATE studio_state SET fame = ? WHERE id = 1", (new_fame,))
        conn.execute(
            "UPDATE player_state SET reputation_json = ?, network_json = ? WHERE id = 1",
            (dumps_json(reputation), dumps_json(network)),
        )
        conn.execute(
            """
            UPDATE projects
            SET status = 'released', stage = 'completed',
                release_year = ?, release_month = ?,
                content_rating = ?, rating_reason_json = ?
            WHERE id = ?
            """,
            (
                player["current_year"],
                player["current_month"],
                calculated.get("content_rating"),
                dumps_json(calculated.get("content_rating_reasons", [])),
                project_id,
            ),
        )
        conn.execute(
            """
            UPDATE production_projects
            SET status = 'released', stage = 'completed',
                release_year = ?, release_month = ?,
                content_rating = ?, rating_reason_json = ?
            WHERE id = ?
            """,
            (
                player["current_year"],
                player["current_month"],
                calculated.get("content_rating"),
                dumps_json(calculated.get("content_rating_reasons", [])),
                project_id,
            ),
        )
        _record_released_people_careers(
            conn,
            project_id=project_id,
            film_id=film_id,
            title=str(project["title"]),
            year=int(player["current_year"]),
            month=int(player["current_month"]),
            summary=result_summary,
        )
        record_released_versions(conn, project_id, film_id, calculated)
        conn.commit()

    from app.services.calendar_service import add_calendar_event

    add_calendar_event(
        title=f"{project['title']}: 개봉 정산",
        event_type="release_result",
        project_id=project_id,
        description=result_summary,
        metadata={
            "filmId": film_id,
            "finalAudience": calculated["final_audience"],
            "profit": calculated["profit"],
            "breakEvenAudience": calculated["break_even_audience"],
        },
    )
    _run_post_release_systems(project_id, film_id)
    calculated["film_id"] = film_id
    calculated["title"] = project["title"]
    calculated["genre_id"] = project["genre_id"]
    calculated["genre_name"] = genre["name"] if genre else project["genre_id"]
    calculated["scale_id"] = project["scale_id"]
    calculated["scale_name"] = scale["name"] if scale else project["scale_id"]
    calculated["production_budget"] = int(project["production_budget"])
    calculated["marketing_budget"] = int(project["marketing_budget"])
    calculated["result_summary"] = result_summary
    calculated["fame_delta"] = fame_delta
    return calculated


def start_theatrical_run(project_id: str) -> dict[str, Any]:
    existing_run_id: str | None = None
    created_run = False
    with get_connection() as conn:
        existing = conn.execute(
            """
            SELECT id
            FROM theatrical_runs
            WHERE project_id = ?
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (project_id,),
        ).fetchone()
        if existing:
            existing_run_id = str(existing["id"])
        else:
            context = _release_context(conn, project_id)
            project = context["project"]
            player = context["player"]
            forecast = context["forecast"]
            run_id = f"run_{uuid.uuid4().hex[:10]}"
            max_days = _theatrical_run_days(str(project["scale_id"]))
            daily_plan = _daily_audience_plan(int(forecast["final_audience"]), max_days)
            conn.execute(
                """
                INSERT INTO theatrical_runs (
                    id, project_id, status, release_year, release_month,
                    release_day, current_day, max_days, forecast_json,
                    daily_plan_json, final_result_json
                ) VALUES (?, ?, 'active', ?, ?, ?, 0, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    project_id,
                    int(player["current_year"]),
                    int(player["current_month"]),
                    int(player["current_day"] or 1),
                    max_days,
                    dumps_json(forecast),
                    dumps_json(daily_plan),
                    dumps_json({}),
                ),
            )
            conn.execute(
                """
                UPDATE projects
                SET status = 'in_release', stage = 'theatrical_release',
                    release_year = ?, release_month = ?
                WHERE id = ?
                """,
                (int(player["current_year"]), int(player["current_month"]), project_id),
            )
            conn.execute(
                """
                UPDATE production_projects
                SET status = 'in_release', stage = 'theatrical_release',
                    release_year = ?, release_month = ?
                WHERE id = ?
                """,
                (int(player["current_year"]), int(player["current_month"]), project_id),
            )
            conn.commit()
            existing_run_id = run_id
            created_run = True

    from app.services.calendar_service import add_calendar_event

    state = get_theatrical_run_state(existing_run_id)
    if created_run:
        add_calendar_event(
            title=f"{state['project']['title']}: 1차 극장 시장 개봉",
            event_type="theatrical_release_start",
            project_id=project_id,
            description="제작 완료 후 극장 1차 시장 상영을 시작했다.",
            metadata={"runId": existing_run_id, "maxDays": state["max_days"]},
        )
    return state


def get_theatrical_run_state(run_id: str) -> dict[str, Any]:
    with get_connection() as conn:
        run = conn.execute(
            """
            SELECT
                r.*,
                p.title, p.genre_id, p.scale_id, p.production_budget, p.marketing_budget,
                g.name AS genre_name, s.name AS scale_name
            FROM theatrical_runs r
            JOIN projects p ON p.id = r.project_id
            LEFT JOIN genres g ON g.id = p.genre_id
            LEFT JOIN project_scales s ON s.id = p.scale_id
            WHERE r.id = ?
            """,
            (run_id,),
        ).fetchone()
        if not run:
            raise ValueError("상영 중인 1차 시장 기록을 찾을 수 없습니다.")
        daily_rows = conn.execute(
            """
            SELECT *
            FROM theatrical_daily_results
            WHERE run_id = ?
            ORDER BY day_number
            """,
            (run_id,),
        ).fetchall()

    run_data = dict(run)
    forecast = loads_json(run_data.pop("forecast_json", None), {})
    daily_plan = loads_json(run_data.pop("daily_plan_json", None), [])
    final_result = loads_json(run_data.pop("final_result_json", None), {})
    daily_results = [dict(row) for row in daily_rows]
    project = {
        "id": run_data["project_id"],
        "title": run_data.pop("title"),
        "genre_id": run_data.pop("genre_id"),
        "genre_name": run_data.pop("genre_name") or "-",
        "scale_id": run_data.pop("scale_id"),
        "scale_name": run_data.pop("scale_name") or "-",
        "production_budget": int(run_data.pop("production_budget") or 0),
        "marketing_budget": int(run_data.pop("marketing_budget") or 0),
    }
    cumulative_audience = daily_results[-1]["cumulative_audience"] if daily_results else 0
    cumulative_revenue = daily_results[-1]["cumulative_revenue"] if daily_results else 0
    return {
        **run_data,
        "project": project,
        "forecast": forecast,
        "daily_plan": daily_plan,
        "daily_results": daily_results,
        "final_result": final_result,
        "current_day": int(run_data["current_day"] or 0),
        "max_days": int(run_data["max_days"] or len(daily_plan) or 1),
        "cumulative_audience": int(cumulative_audience or 0),
        "cumulative_revenue": int(cumulative_revenue or 0),
    }


def list_active_theatrical_reports(limit: int = 5) -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT
                r.*,
                p.title,
                p.genre_id,
                p.scale_id,
                g.name AS genre_name,
                s.name AS scale_name,
                d.day_number AS latest_day_number,
                d.year AS latest_year,
                d.month AS latest_month,
                d.day AS latest_day,
                d.daily_audience,
                d.cumulative_audience,
                d.daily_revenue,
                d.cumulative_revenue
            FROM theatrical_runs r
            JOIN projects p ON p.id = r.project_id
            LEFT JOIN genres g ON g.id = p.genre_id
            LEFT JOIN project_scales s ON s.id = p.scale_id
            LEFT JOIN theatrical_daily_results d
              ON d.run_id = r.id
             AND d.day_number = (
                SELECT MAX(day_number)
                FROM theatrical_daily_results
                WHERE run_id = r.id
             )
            WHERE r.status = 'active'
            ORDER BY r.created_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    reports: list[dict[str, Any]] = []
    for row in rows:
        data = dict(row)
        forecast = loads_json(data.get("forecast_json"), {})
        daily_plan = loads_json(data.get("daily_plan_json"), [])
        current_day = int(data.get("current_day") or 0)
        max_days = int(data.get("max_days") or len(daily_plan) or 1)
        cumulative_audience = int(data.get("cumulative_audience") or 0)
        cumulative_revenue = int(data.get("cumulative_revenue") or 0)
        latest_daily_audience = int(data.get("daily_audience") or 0)
        expected_final = int(forecast.get("final_audience") or sum(int(value or 0) for value in daily_plan))
        break_even = int(forecast.get("break_even_audience") or 0)
        projected = _projected_run_audience(
            cumulative_audience=cumulative_audience,
            current_day=current_day,
            max_days=max_days,
            fallback_final=expected_final,
        )
        reports.append(
            {
                "id": data["id"],
                "project_id": data["project_id"],
                "title": data["title"],
                "genre_name": data.get("genre_name") or "-",
                "scale_name": data.get("scale_name") or "-",
                "current_day": current_day,
                "max_days": max_days,
                "latest_date": _latest_date_label(data),
                "latest_daily_audience": latest_daily_audience,
                "cumulative_audience": cumulative_audience,
                "cumulative_revenue": cumulative_revenue,
                "forecast_final_audience": expected_final,
                "projected_final_audience": projected,
                "break_even_audience": break_even,
                "pace_label": _run_pace_label(
                    cumulative_audience=cumulative_audience,
                    projected_final=projected,
                    expected_final=expected_final,
                    break_even=break_even,
                    current_day=current_day,
                ),
            }
        )
    return reports


def advance_active_theatrical_runs_for_current_day() -> list[dict[str, Any]]:
    with get_connection() as conn:
        player = conn.execute(
            "SELECT current_year, current_month, current_day FROM player_state WHERE id = 1"
        ).fetchone()
        run_rows = conn.execute(
            """
            SELECT id
            FROM theatrical_runs
            WHERE status = 'active'
            ORDER BY created_at, id
            """
        ).fetchall()
    if not player:
        return []
    year = int(player["current_year"])
    month = int(player["current_month"])
    day = int(player["current_day"] or 1)
    states: list[dict[str, Any]] = []
    for row in run_rows:
        states.append(_record_theatrical_run_day_for_date(str(row["id"]), year, month, day))
    return states


def advance_theatrical_day(run_id: str) -> dict[str, Any]:
    with get_connection() as conn:
        run = conn.execute("SELECT * FROM theatrical_runs WHERE id = ?", (run_id,)).fetchone()
        if not run:
            raise ValueError("진행할 1차 시장 기록을 찾을 수 없습니다.")
        if run["status"] == "completed":
            return get_theatrical_run_state(run_id)
        plan = loads_json(run["daily_plan_json"], [])
        current_day = int(run["current_day"] or 0)
        max_days = int(run["max_days"] or len(plan) or 1)
        if current_day >= max_days:
            return finalize_theatrical_run(run_id)

    from app.services.calendar_service import advance_days

    advance_days(1)
    return get_theatrical_run_state(run_id)


def _latest_date_label(data: dict[str, Any]) -> str:
    if data.get("latest_year") and data.get("latest_month") and data.get("latest_day"):
        return f"{int(data['latest_year'])}.{int(data['latest_month']):02d}.{int(data['latest_day']):02d}"
    if data.get("release_year") and data.get("release_month") and data.get("release_day"):
        return f"{int(data['release_year'])}.{int(data['release_month']):02d}.{int(data['release_day']):02d}"
    return "-"


def _projected_run_audience(
    *,
    cumulative_audience: int,
    current_day: int,
    max_days: int,
    fallback_final: int,
) -> int:
    if current_day <= 0 or cumulative_audience <= 0:
        return max(0, fallback_final)
    progress = max(0.05, min(1.0, current_day / max(1, max_days)))
    projection = int(cumulative_audience / progress)
    if fallback_final <= 0:
        return projection
    return int(projection * 0.55 + fallback_final * 0.45)


def _run_pace_label(
    *,
    cumulative_audience: int,
    projected_final: int,
    expected_final: int,
    break_even: int,
    current_day: int,
) -> str:
    if current_day <= 0:
        return "개봉 대기"
    if break_even and cumulative_audience >= break_even:
        return "손익권 진입"
    if break_even and projected_final >= break_even:
        return "손익권 추격 중"
    if expected_final and projected_final >= expected_final * 1.12:
        return "예상보다 강함"
    if expected_final and projected_final <= expected_final * 0.75:
        return "낙폭 경계"
    return "예상 흐름"


def _record_theatrical_run_day_for_date(run_id: str, year: int, month: int, day: int) -> dict[str, Any]:
    should_finalize = False
    with get_connection() as conn:
        run = conn.execute("SELECT * FROM theatrical_runs WHERE id = ?", (run_id,)).fetchone()
        if not run:
            raise ValueError("진행할 1차 시장 기록을 찾을 수 없습니다.")
        if run["status"] == "completed":
            return get_theatrical_run_state(run_id)
        already_recorded = conn.execute(
            """
            SELECT 1
            FROM theatrical_daily_results
            WHERE run_id = ? AND year = ? AND month = ? AND day = ?
            LIMIT 1
            """,
            (run_id, year, month, day),
        ).fetchone()
        if already_recorded:
            return get_theatrical_run_state(run_id)
        plan = loads_json(run["daily_plan_json"], [])
        current_day = int(run["current_day"] or 0)
        max_days = int(run["max_days"] or len(plan) or 1)
        if current_day >= max_days:
            should_finalize = True
        else:
            day_number = current_day + 1
            daily_audience = int(plan[current_day]) if current_day < len(plan) else 0
            previous = conn.execute(
                """
                SELECT cumulative_audience, cumulative_revenue
                FROM theatrical_daily_results
                WHERE run_id = ?
                ORDER BY day_number DESC
                LIMIT 1
                """,
                (run_id,),
            ).fetchone()
            previous_audience = int(previous["cumulative_audience"] or 0) if previous else 0
            previous_revenue = int(previous["cumulative_revenue"] or 0) if previous else 0
            forecast = loads_json(run["forecast_json"], {})
            average_ticket_price = int(forecast.get("average_ticket_price", 0) or 0)
            daily_revenue = daily_audience * average_ticket_price
            cumulative_audience = previous_audience + daily_audience
            cumulative_revenue = previous_revenue + daily_revenue
            conn.execute(
                """
                INSERT OR REPLACE INTO theatrical_daily_results (
                    id, run_id, day_number, year, month, day, daily_audience,
                    cumulative_audience, daily_revenue, cumulative_revenue,
                    note, metrics_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"daily_{run_id}_{day_number:03d}",
                    run_id,
                    day_number,
                    year,
                    month,
                    day,
                    daily_audience,
                    cumulative_audience,
                    daily_revenue,
                    cumulative_revenue,
                    _daily_note(day_number, max_days),
                    dumps_json({"averageTicketPrice": average_ticket_price, "autoAdvanced": True}),
                ),
            )
            conn.execute(
                "UPDATE theatrical_runs SET current_day = ? WHERE id = ?",
                (day_number, run_id),
            )
            should_finalize = day_number >= max_days
        conn.commit()
    if should_finalize:
        return finalize_theatrical_run(run_id)
    return get_theatrical_run_state(run_id)


def finalize_theatrical_run(run_id: str) -> dict[str, Any]:
    with get_connection() as conn:
        run = conn.execute("SELECT * FROM theatrical_runs WHERE id = ?", (run_id,)).fetchone()
        if not run:
            raise ValueError("정산할 1차 시장 기록을 찾을 수 없습니다.")
        if run["status"] == "completed":
            return get_theatrical_run_state(run_id)
        project = conn.execute("SELECT * FROM projects WHERE id = ?", (run["project_id"],)).fetchone()
        player = conn.execute("SELECT * FROM player_state WHERE id = 1").fetchone()
        studio = conn.execute("SELECT * FROM studio_state WHERE id = 1").fetchone()
        if not project or not player or not studio:
            raise ValueError("1차 시장 정산에 필요한 게임 상태를 찾을 수 없습니다.")
        genre = conn.execute("SELECT * FROM genres WHERE id = ?", (project["genre_id"],)).fetchone()
        scale = conn.execute("SELECT * FROM project_scales WHERE id = ?", (project["scale_id"],)).fetchone()
        last_daily = conn.execute(
            """
            SELECT cumulative_audience, cumulative_revenue
            FROM theatrical_daily_results
            WHERE run_id = ?
            ORDER BY day_number DESC
            LIMIT 1
            """,
            (run_id,),
        ).fetchone()
        forecast = loads_json(run["forecast_json"], {})
        final_audience = int(last_daily["cumulative_audience"] or 0) if last_daily else 0
        gross_revenue = int(last_daily["cumulative_revenue"] or 0) if last_daily else 0
        forecast_audience = max(1, int(forecast.get("final_audience", 0) or 0))
        secondary_market_revenue = int(
            int(forecast.get("secondary_market_revenue", 0) or 0) * final_audience / forecast_audience
        )
        total_cost = int(forecast.get("total_cost") or 0) or project_total_cost(
            dict(project),
            loads_json(project["stats_json"], {}),
        )
        average_ticket_price = int(forecast.get("average_ticket_price", 0) or 0)
        settlement = calculate_release_settlement(
            final_audience=final_audience,
            average_ticket_price=average_ticket_price,
            studio_recovery_rate=STUDIO_RECOVERY_RATE,
            secondary_market_revenue=secondary_market_revenue,
            total_cost=total_cost,
        )
        calculated = {
            **forecast,
            "final_audience": final_audience,
            "gross_revenue": gross_revenue,
            "studio_revenue": settlement["studio_revenue"],
            "secondary_market_revenue": secondary_market_revenue,
            "total_cost": total_cost,
            "break_even_audience": settlement["break_even_audience"],
            "theatrical_break_even_audience": settlement["theatrical_break_even_audience"],
            "net_break_even_audience": settlement["break_even_audience"],
            "profit": settlement["profit"],
            "profit_margin": settlement["profit_margin"],
            "studio_recovery_rate": STUDIO_RECOVERY_RATE,
        }
        from app.services.finance_service import add_settlement_to_own_capital, settlement_financing

        _apply_casting_settlement(conn, str(run["project_id"]), calculated)
        calculated = settlement_financing(conn, str(run["project_id"]), calculated)
        film_id = str(run["film_id"] or f"film_{uuid.uuid4().hex[:10]}")
        reputation_changes = calculate_reputation_changes(calculated)
        fame_delta = int(reputation_changes["studio_fame_delta"])
        calculated["fame_delta"] = fame_delta
        calculated["reputation_deltas"] = reputation_changes["reputation"]
        calculated["network_deltas"] = reputation_changes["network"]
        result_summary = summarize_result(calculated)

        conn.execute(
            """
            INSERT OR REPLACE INTO completed_films (
                id, title, genre_id, scale_id, release_year, release_month,
                production_budget, marketing_budget, total_cost, final_audience,
                gross_revenue, break_even_audience, critic_score,
                audience_score, content_rating, rating_reason_json, result_summary
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                film_id,
                project["title"],
                project["genre_id"],
                project["scale_id"],
                player["current_year"],
                player["current_month"],
                project["production_budget"],
                project["marketing_budget"],
                calculated["total_cost"],
                calculated["final_audience"],
                calculated["gross_revenue"],
                calculated["break_even_audience"],
                calculated["critic_score"],
                calculated["audience_score"],
                calculated.get("content_rating"),
                dumps_json(calculated.get("content_rating_reasons", [])),
                result_summary,
            ),
        )
        conn.execute(
            """
            INSERT OR REPLACE INTO movies_player_created (
                id, title, genre_id, scale_id, release_year, release_month,
                production_budget, marketing_budget, total_cost, final_audience,
                gross_revenue, break_even_audience, critic_score,
                audience_score, content_rating, rating_reason_json, result_summary
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                film_id,
                project["title"],
                project["genre_id"],
                project["scale_id"],
                player["current_year"],
                player["current_month"],
                project["production_budget"],
                project["marketing_budget"],
                calculated["total_cost"],
                calculated["final_audience"],
                calculated["gross_revenue"],
                calculated["break_even_audience"],
                calculated["critic_score"],
                calculated["audience_score"],
                calculated.get("content_rating"),
                dumps_json(calculated.get("content_rating_reasons", [])),
                result_summary,
            ),
        )
        conn.execute(
            """
            INSERT OR REPLACE INTO movies (
                id, title, movie_type, genre_id, scale_id, status, metadata_json
            ) VALUES (?, ?, 'player_created', ?, ?, 'released', ?)
            """,
            (
                film_id,
                project["title"],
                project["genre_id"],
                project["scale_id"],
                dumps_json(
                    {
                        "projectId": run["project_id"],
                        "theatricalRunId": run_id,
                        "versionProfile": forecast.get("version_profile", {}),
                    }
                ),
            ),
        )
        conn.execute(
            """
            INSERT OR REPLACE INTO movies_boxoffice (
                movie_id, final_audience, gross_revenue, studio_revenue,
                secondary_market_revenue, break_even_audience, profit,
                metrics_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                film_id,
                calculated["final_audience"],
                calculated["gross_revenue"],
                calculated["studio_revenue"],
                calculated["secondary_market_revenue"],
                calculated["break_even_audience"],
                calculated["profit"],
                dumps_json(calculated),
            ),
        )

        new_fame = clamp(int(studio["fame"]) + fame_delta)
        reputation = loads_json(player["reputation_json"], {})
        network = loads_json(player["network_json"], {})
        for key, delta in reputation_changes["reputation"].items():
            reputation[key] = clamp(float(reputation.get(key, 10)) + float(delta))
        for key, delta in reputation_changes["network"].items():
            network[key] = clamp(float(network.get(key, 10)) + float(delta))

        final_result = {
            **calculated,
            "film_id": film_id,
            "title": project["title"],
            "genre_id": project["genre_id"],
            "genre_name": genre["name"] if genre else project["genre_id"],
            "scale_id": project["scale_id"],
            "scale_name": scale["name"] if scale else project["scale_id"],
            "production_budget": int(project["production_budget"]),
            "marketing_budget": int(project["marketing_budget"]),
            "result_summary": result_summary,
            "fame_delta": fame_delta,
        }

        add_settlement_to_own_capital(conn, player, str(run["project_id"]), calculated)
        conn.execute("UPDATE studio_state SET fame = ? WHERE id = 1", (new_fame,))
        conn.execute(
            "UPDATE player_state SET reputation_json = ?, network_json = ? WHERE id = 1",
            (dumps_json(reputation), dumps_json(network)),
        )
        conn.execute(
            """
            UPDATE projects
            SET status = 'released', stage = 'completed',
                release_year = ?, release_month = ?,
                content_rating = ?, rating_reason_json = ?
            WHERE id = ?
            """,
            (
                player["current_year"],
                player["current_month"],
                calculated.get("content_rating"),
                dumps_json(calculated.get("content_rating_reasons", [])),
                run["project_id"],
            ),
        )
        conn.execute(
            """
            UPDATE production_projects
            SET status = 'released', stage = 'completed',
                release_year = ?, release_month = ?,
                content_rating = ?, rating_reason_json = ?
            WHERE id = ?
            """,
            (
                player["current_year"],
                player["current_month"],
                calculated.get("content_rating"),
                dumps_json(calculated.get("content_rating_reasons", [])),
                run["project_id"],
            ),
        )
        conn.execute(
            """
            UPDATE theatrical_runs
            SET status = 'completed', film_id = ?, final_result_json = ?
            WHERE id = ?
            """,
            (film_id, dumps_json(final_result), run_id),
        )
        _record_released_people_careers(
            conn,
            project_id=str(run["project_id"]),
            film_id=film_id,
            title=str(project["title"]),
            year=int(player["current_year"]),
            month=int(player["current_month"]),
            summary=result_summary,
        )
        record_released_versions(conn, str(run["project_id"]), film_id, final_result)
        conn.commit()

    from app.services.calendar_service import add_calendar_event

    add_calendar_event(
        title=f"{final_result['title']}: 1차 시장 종료",
        event_type="first_market_complete",
        project_id=str(run["project_id"]),
        description=result_summary,
        metadata={
            "runId": run_id,
            "filmId": film_id,
            "finalAudience": final_result["final_audience"],
            "profit": final_result["profit"],
            "breakEvenAudience": final_result["break_even_audience"],
        },
    )
    _run_post_release_systems(str(run["project_id"]), film_id)
    return get_theatrical_run_state(run_id)


def _run_post_release_systems(project_id: str, film_id: str) -> None:
    from app.services.award_service import consider_film_for_awards
    from app.services.critic_service import create_reviews_for_film
    from app.services.franchise_service import evaluate_ip_after_release, record_franchise_release
    from app.services.plagiarism_service import evaluate_release_risks
    from app.services.player_filmography_service import refresh_player_filmography_record
    from app.services.press_service import create_release_news
    from app.services.reevaluation_service import create_reevaluation_candidate

    evaluate_release_risks(project_id, film_id)
    create_reviews_for_film(film_id)
    create_release_news(film_id)
    consider_film_for_awards(film_id)
    record_franchise_release(project_id, film_id)
    evaluate_ip_after_release(film_id)
    create_reevaluation_candidate(film_id)
    refresh_player_filmography_record(film_id)


def _apply_casting_settlement(conn: Any, project_id: str, calculated: dict[str, Any]) -> None:
    rows = conn.execute(
        """
        SELECT pp.*, p.name_ko
        FROM project_people pp
        JOIN people p ON p.id = pp.person_id
        WHERE pp.project_id = ?
        """,
        (project_id,),
    ).fetchall()
    final_audience = int(calculated.get("final_audience") or 0)
    average_ticket_price = int(calculated.get("average_ticket_price") or 0)
    studio_revenue = int(calculated.get("studio_revenue") or 0)
    secondary_revenue = int(calculated.get("secondary_market_revenue") or 0)
    break_even_audience = int(calculated.get("break_even_audience") or 0)
    pre_backend_profit = int(calculated.get("profit") or 0)
    total_cost = max(1, int(calculated.get("total_cost") or 1))
    details: list[dict[str, Any]] = []
    total_payout = 0
    for row in rows:
        options = loads_json(row["contract_options_json"], {})
        terms = options.get("terms") if isinstance(options.get("terms"), dict) else {}
        payout = 0
        labels: list[str] = []
        deferred_fee = int(terms.get("deferredFee") or 0)
        if deferred_fee:
            payout += deferred_fee
            labels.append("이연 지급")
        bonus = terms.get("boxOfficeBonus") if isinstance(terms.get("boxOfficeBonus"), dict) else {}
        if bonus.get("enabled"):
            threshold = int(bonus.get("audience") or 0)
            amount = int(bonus.get("amount") or 0)
            if amount > 0 and (threshold <= 0 or final_audience >= threshold):
                payout += amount
                labels.append("흥행 보너스")
        running = terms.get("runningGuarantee") if isinstance(terms.get("runningGuarantee"), dict) else {}
        rate = float(running.get("rate") or 0)
        if running.get("enabled") and rate > 0:
            trigger = str(running.get("trigger") or "break_even")
            base = 0
            if trigger == "release":
                base = studio_revenue + secondary_revenue
            elif trigger == "profit":
                base = max(0, pre_backend_profit)
            else:
                surplus_audience = max(0, final_audience - break_even_audience)
                base = int(surplus_audience * average_ticket_price * STUDIO_RECOVERY_RATE)
            running_payout = int(max(0, base) * min(rate, 0.2))
            if running_payout > 0:
                payout += running_payout
                labels.append("러닝 개런티")
        if payout <= 0:
            continue
        total_payout += payout
        details.append(
            {
                "personId": row["person_id"],
                "name": row["name_ko"],
                "role": row["role"],
                "amount": payout,
                "labels": labels,
            }
        )
    if total_payout <= 0:
        calculated["talent_backend_payout"] = 0
        calculated["talent_backend_details"] = []
        return
    calculated["profit_before_talent_backend"] = pre_backend_profit
    calculated["talent_backend_payout"] = total_payout
    calculated["talent_backend_details"] = details
    calculated["profit"] = pre_backend_profit - total_payout
    calculated["profit_margin"] = round(int(calculated["profit"]) / total_cost, 4)


def _project_distribution_metadata(conn: Any, project_id: str) -> dict[str, Any]:
    row = conn.execute(
        """
        SELECT pd.*, o.name_ko
        FROM project_distribution pd
        LEFT JOIN organizations o ON o.id = pd.distributor_id
        WHERE pd.project_id = ?
        """,
        (project_id,),
    ).fetchone()
    if not row:
        return {}
    terms = loads_json(row["terms_json"], {})
    return {
        "distributorId": row["distributor_id"],
        "distributorName": row["name_ko"],
        "dealType": row["deal_type"],
        "screenPower": int(row["screen_power"] or 0),
        "summary": terms.get("summary") or "",
    }


def _record_released_people_careers(
    conn: Any,
    *,
    project_id: str,
    film_id: str,
    title: str,
    year: int,
    month: int,
    summary: str,
) -> None:
    existing_rows = conn.execute(
        """
        SELECT *
        FROM people_career_timeline
        WHERE project_id = ?
        """,
        (project_id,),
    ).fetchall()
    promoted_keys: set[tuple[str, str]] = set()
    for row in existing_rows:
        person_id = str(row["person_id"] or "")
        role = str(row["role"] or "")
        if not person_id or not role or str(row["status"] or "") != "attached":
            continue
        key = (person_id, role)
        result = _released_career_result(
            loads_json(row["result_json"], {}),
            title=title,
            summary=summary,
        )
        if key in promoted_keys:
            conn.execute(
                """
                UPDATE people_career_timeline
                SET status = 'attached_archived', result_json = ?
                WHERE id = ?
                """,
                (dumps_json(result), row["id"]),
            )
            continue
        promoted_keys.add(key)
        conn.execute(
            """
            UPDATE people_career_timeline
            SET project_id = ?, status = 'released', year = ?, month = ?,
                result_json = ?
            WHERE id = ?
            """,
            (film_id, year, month, dumps_json(result), row["id"]),
        )

    cast_rows = conn.execute(
        """
        SELECT *
        FROM project_people
        WHERE project_id = ?
        """,
        (project_id,),
    ).fetchall()
    for row in cast_rows:
        person_id = str(row["person_id"] or "")
        role = str(row["role"] or "")
        if not person_id or not role:
            continue
        contribution = loads_json(row["contribution_json"], {})
        contract_options = loads_json(row["contract_options_json"], {})
        cast_payload = {
            "contribution": contribution if isinstance(contribution, dict) else {},
            "contractFee": int(row["contract_fee"] or 0),
            "contractOptions": contract_options if isinstance(contract_options, dict) else {},
            "title": title,
            "summary": summary,
        }
        existing_released = conn.execute(
            """
            SELECT *
            FROM people_career_timeline
            WHERE person_id = ? AND project_id = ? AND role = ?
              AND status = 'released'
            ORDER BY id
            LIMIT 1
            """,
            (person_id, film_id, role),
        ).fetchone()
        if existing_released:
            result = _released_career_result(
                loads_json(existing_released["result_json"], {}),
                title=title,
                summary=summary,
                extra=cast_payload,
            )
            conn.execute(
                """
                UPDATE people_career_timeline
                SET year = ?, month = ?, result_json = ?
                WHERE id = ?
                """,
                (year, month, dumps_json(result), existing_released["id"]),
            )
            continue
        result = _released_career_result(
            cast_payload,
            title=title,
            summary=summary,
        )
        conn.execute(
            """
            INSERT INTO people_career_timeline (
                person_id, project_id, role, year, month, status, result_json
            ) VALUES (?, ?, ?, ?, ?, 'released', ?)
            """,
            (person_id, film_id, role, year, month, dumps_json(result)),
        )
    conn.execute(
        "UPDATE project_people SET status = 'released' WHERE project_id = ?",
        (project_id,),
    )


def _released_career_result(
    base: Any,
    *,
    title: str,
    summary: str,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    result = base if isinstance(base, dict) else {}
    if extra:
        for key, value in extra.items():
            if key not in {"title", "summary"} and value in ({}, [], None, ""):
                continue
            result[key] = value
    result.update({"title": title, "summary": summary})
    return result


def _release_context(conn: Any, project_id: str) -> dict[str, Any]:
    project = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
    player = conn.execute("SELECT * FROM player_state WHERE id = 1").fetchone()
    if not project or not player:
        raise ValueError("개봉할 프로젝트를 찾을 수 없습니다.")
    genre = conn.execute("SELECT * FROM genres WHERE id = ?", (project["genre_id"],)).fetchone()
    scale = conn.execute("SELECT * FROM project_scales WHERE id = ?", (project["scale_id"],)).fetchone()
    era = conn.execute(
        """
        SELECT * FROM eras
        WHERE start_year <= ? AND (end_year IS NULL OR end_year >= ?)
        ORDER BY start_year DESC
        LIMIT 1
        """,
        (player["current_year"], player["current_year"]),
    ).fetchone()
    if not era:
        era = conn.execute("SELECT * FROM eras ORDER BY start_year DESC LIMIT 1").fetchone()
    market_state = ensure_market_state_with_connection(
        conn,
        int(player["current_year"]),
        int(player["current_month"]),
    )
    ticket = conn.execute(
        """
        SELECT * FROM ticket_prices
        WHERE year <= ?
        ORDER BY year DESC
        LIMIT 1
        """,
        (player["current_year"],),
    ).fetchone()
    if not ticket:
        ticket = conn.execute("SELECT * FROM ticket_prices ORDER BY year LIMIT 1").fetchone()

    market = dict(era) if era else {"theater_demand": 60, "foreign_competition": 60, "ticket_price_burden": 50}
    market["year"] = int(player["current_year"])
    if market_state:
        modifiers = loads_json(market_state["modifiers_json"], {})
        market.update(
            {
                "theater_demand": market_state["theater_demand"],
                "ott_power": market_state["ott_power"],
                "foreign_competition": market_state["foreign_competition"],
                **modifiers,
            }
        )
    ticket_data = dict(ticket) if ticket else {"average_ticket_price": 8000, "audience_price_sensitivity": 50}
    stats, version_profile = apply_release_version_modifiers(
        conn,
        project_id,
        loads_json(project["stats_json"], {}),
    )
    forecast = calculate_boxoffice(
        stats,
        dict(project),
        market,
        ticket_data,
        dict(genre) if genre else {},
    )
    forecast["version_profile"] = version_profile
    forecast["release_version_name"] = (version_profile.get("theatrical") or {}).get("name")
    forecast["ott_version_name"] = (version_profile.get("ott") or {}).get("name")
    return {
        "project": dict(project),
        "player": dict(player),
        "genre": dict(genre) if genre else None,
        "scale": dict(scale) if scale else None,
        "forecast": forecast,
    }


def _theatrical_run_days(scale_id: str) -> int:
    return THEATRICAL_RUN_DAYS.get(scale_id, 28)


def _daily_audience_plan(final_audience: int, max_days: int) -> list[int]:
    final_audience = max(0, int(final_audience))
    max_days = max(1, int(max_days))
    if final_audience <= 0:
        return [0 for _ in range(max_days)]
    weights: list[float] = []
    for day_number in range(1, max_days + 1):
        weekday = (day_number - 1) % 7
        decay = math.exp(-0.105 * (day_number - 1))
        weekend_bonus = 1.35 if weekday in {4, 5, 6} else 1.0
        opening_bonus = 1.55 if day_number <= 3 else 1.0
        second_week_drag = 0.82 if day_number > 10 else 1.0
        weights.append(decay * weekend_bonus * opening_bonus * second_week_drag)
    total_weight = sum(weights) or 1.0
    plan = [int(final_audience * weight / total_weight) for weight in weights]
    remainder = final_audience - sum(plan)
    if plan:
        plan[0] += remainder
    return plan


def _daily_note(day_number: int, max_days: int) -> str:
    if day_number == 1:
        return "개봉일"
    if day_number == 3:
        return "개봉 첫 주말"
    if day_number == 7:
        return "1주차 마감"
    if day_number == 14:
        return "2주차 마감"
    if day_number >= max_days:
        return "1차 시장 종료"
    return "상영 진행"
