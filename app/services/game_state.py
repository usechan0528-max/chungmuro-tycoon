from __future__ import annotations

from calendar import monthrange
from typing import Any

from app.database import dumps_json, ensure_database, get_connection, loads_json


def clamp(value: float, minimum: int = 0, maximum: int = 100) -> int:
    return max(minimum, min(maximum, int(round(value))))


def money(value: int | float | None) -> str:
    number = int(value or 0)
    if abs(number) >= 100_000_000:
        return f"{number / 100_000_000:.1f}억 원"
    if abs(number) >= 10_000:
        return f"{number / 10_000:.0f}만 원"
    return f"{number:,}원"


class GameStateService:
    def __init__(self) -> None:
        ensure_database()

    def get_reference_data(self) -> dict[str, list[dict[str, Any]]]:
        with get_connection() as conn:
            player = conn.execute("SELECT current_year FROM player_state WHERE id = 1").fetchone()
            eras = conn.execute("SELECT * FROM eras ORDER BY start_year").fetchall()
            genres = conn.execute("SELECT * FROM genres ORDER BY name").fetchall()
            scales = conn.execute("SELECT * FROM project_scales ORDER BY min_budget").fetchall()
        scale_rows = [dict(row) for row in scales]
        if player:
            from app.services.economic_service import adjusted_scale_budget

            year = int(player["current_year"])
            scale_rows = [adjusted_scale_budget(scale, year) for scale in scale_rows]
        else:
            year = 2026
        from app.services.era_ui_service import era_ui_profile

        return {
            "eras": [dict(row) for row in eras],
            "genres": [dict(row) for row in genres],
            "scales": scale_rows,
            "era_ui": era_ui_profile(year),
        }

    def get_dashboard_state(self) -> dict[str, Any]:
        from app.services.era_service import era_rule_for_year
        from app.services.era_ui_service import era_ui_profile

        with get_connection() as conn:
            player_row = conn.execute("SELECT * FROM player_state WHERE id = 1").fetchone()
            studio_row = conn.execute("SELECT * FROM studio_state WHERE id = 1").fetchone()
            project_rows = conn.execute(
                """
                SELECT p.*, g.name AS genre_name, s.name AS scale_name
                FROM projects p
                JOIN genres g ON g.id = p.genre_id
                JOIN project_scales s ON s.id = p.scale_id
                WHERE p.status != 'released'
                ORDER BY p.created_year DESC, p.title
                """
            ).fetchall()
            completed_rows = conn.execute(
                """
                SELECT c.*, g.name AS genre_name, s.name AS scale_name
                FROM completed_films c
                LEFT JOIN genres g ON g.id = c.genre_id
                LEFT JOIN project_scales s ON s.id = c.scale_id
                ORDER BY c.release_year DESC, c.release_month DESC
                LIMIT 5
                """
            ).fetchall()
            theatrical_rows = conn.execute(
                """
                SELECT r.*, p.title, g.name AS genre_name, s.name AS scale_name
                FROM theatrical_runs r
                JOIN projects p ON p.id = r.project_id
                LEFT JOIN genres g ON g.id = p.genre_id
                LEFT JOIN project_scales s ON s.id = p.scale_id
                WHERE r.status = 'active'
                ORDER BY r.created_at DESC
                """
            ).fetchall()
            era_rule = era_rule_for_year(conn, int(player_row["current_year"])) if player_row else None

        player = dict(player_row) if player_row else None
        if player:
            player["stats"] = loads_json(player.pop("stats_json"), {})
            player["reputation"] = loads_json(player.pop("reputation_json"), {})
            player["network"] = loads_json(player.pop("network_json"), {})
        calendar_events: list[dict[str, Any]] = []
        if player:
            from app.services.calendar_service import list_calendar_events_for_month

            calendar_events = list_calendar_events_for_month(
                int(player["current_year"]),
                int(player["current_month"]),
            )
        economic_modifiers: dict[str, Any] = {}
        if player:
            from app.services.economic_service import build_economic_modifiers

            economic_modifiers = build_economic_modifiers(int(player["current_year"]))
        finance_state: dict[str, Any] = {}
        if player:
            from app.services.finance_service import get_finance_state

            finance_state = get_finance_state()
        news_feed: list[dict[str, Any]] = []
        if player:
            from app.services.news_service import list_news_feed

            news_feed = list_news_feed(limit=8)
        theatrical_reports: list[dict[str, Any]] = []
        if player:
            from app.services.boxoffice_service import list_active_theatrical_reports

            theatrical_reports = list_active_theatrical_reports(limit=5)

        studio = dict(studio_row) if studio_row else None
        if studio:
            from app.services.studio_reputation_service import describe_studio_reputation

            studio["reputation_profile"] = describe_studio_reputation(
                studio,
                player.get("reputation", {}) if player else {},
            )

        return {
            "player": player,
            "studio": studio,
            "finance": finance_state,
            "projects": [self._with_stats(row) for row in project_rows],
            "completed_films": [dict(row) for row in completed_rows],
            "theatrical_runs": theatrical_reports or [dict(row) for row in theatrical_rows],
            "era_rule": era_rule,
            "era_ui": era_ui_profile(int(player["current_year"])) if player else era_ui_profile(2026),
            "calendar_events": calendar_events,
            "economic_modifiers": economic_modifiers,
            "news_feed": news_feed,
        }

    def get_people_database_state(self) -> dict[str, Any]:
        from app.services.people_service import list_available_people, list_public_critics

        with get_connection() as conn:
            player = conn.execute("SELECT current_year FROM player_state WHERE id = 1").fetchone()
        year = int(player["current_year"]) if player else 2026
        return {
            "year": year,
            "actors": list_available_people("actor", year),
            "directors": list_available_people("director", year),
            "critics": list_public_critics(),
        }

    def get_history_timeline_state(self) -> dict[str, Any]:
        from app.services.history_service import (
            list_distribution_events,
            list_foreign_fixed_events,
            list_historical_events,
            list_market_events,
            list_premium_format_events,
            list_policy_events,
            list_protected_director_films,
            list_theater_events,
            list_ticket_price_history,
        )

        with get_connection() as conn:
            player = conn.execute(
                "SELECT current_year, current_month, current_day FROM player_state WHERE id = 1"
            ).fetchone()
        current_year = int(player["current_year"]) if player else 1980
        current_month = int(player["current_month"]) if player else 1
        current_day = int(player["current_day"] or 1) if player else 1
        return {
            "current_date": {
                "year": current_year,
                "month": current_month,
                "day": current_day,
            },
            "protected_films": list_protected_director_films(
                until_year=current_year,
                until_month=current_month,
            ),
            "foreign_events": list_foreign_fixed_events(
                until_year=current_year,
                until_month=current_month,
            ),
            "policy_events": list_policy_events(
                until_year=current_year,
                until_month=current_month,
            ),
            "market_events": list_market_events(
                until_year=current_year,
                until_month=current_month,
            ),
            "distribution_events": list_distribution_events(
                until_year=current_year,
                until_month=current_month,
            ),
            "theater_events": list_theater_events(
                until_year=current_year,
                until_month=current_month,
            ),
            "premium_format_events": list_premium_format_events(
                until_year=current_year,
                until_month=current_month,
            ),
            "ticket_prices": list_ticket_price_history(until_year=current_year),
            "events": list_historical_events(
                until_year=current_year,
                until_month=current_month,
            ),
        }

    def get_industry_database_state(self) -> dict[str, Any]:
        from app.services.organization_service import list_major_industry_organizations

        with get_connection() as conn:
            player = conn.execute(
                "SELECT current_year, current_month FROM player_state WHERE id = 1"
            ).fetchone()
        current_year = int(player["current_year"]) if player else 1980
        current_month = int(player["current_month"]) if player else 1
        return list_major_industry_organizations(
            until_year=current_year,
            until_month=current_month,
        )

    def get_press_and_critics_state(self) -> dict[str, Any]:
        from app.services.people_service import list_public_critics
        from app.services.news_service import list_news_feed

        with get_connection() as conn:
            review_rows = conn.execute(
                """
                SELECT r.*, c.name_ko AS critic_name
                FROM movies_reviews r
                LEFT JOIN critics c ON c.id = r.critic_id
                ORDER BY r.id DESC
                LIMIT 40
                """
            ).fetchall()
        return {
            "press": list_news_feed(limit=40),
            "reviews": [dict(row) for row in review_rows],
            "critics": list_public_critics(),
        }

    def get_awards_state(self) -> dict[str, Any]:
        from app.services.award_service import list_award_results, list_awards

        with get_connection() as conn:
            player = conn.execute(
                "SELECT current_year, current_month FROM player_state WHERE id = 1"
            ).fetchone()
        current_year = int(player["current_year"]) if player else 1980
        current_month = int(player["current_month"]) if player else 1
        results = list_award_results(
            until_year=current_year,
            until_month=current_month,
        )
        return {
            "current_date": {"year": current_year, "month": current_month},
            "awards": list_awards(until_year=current_year),
            "historical_results": results["historical"],
            "player_results": results["player"],
        }

    def get_annual_report_state(self) -> dict[str, Any]:
        from app.services.annual_report_service import list_annual_reports, list_report_source_years

        with get_connection() as conn:
            player = conn.execute("SELECT current_year FROM player_state WHERE id = 1").fetchone()
        current_year = int(player["current_year"]) if player else 1980
        completed_year = current_year - 1
        return {
            "reports": [report for report in list_annual_reports() if int(report.get("year") or 0) <= completed_year],
            "source_years": [year for year in list_report_source_years() if year <= completed_year],
            "current_year": current_year,
        }

    def get_world_boxoffice_state(self) -> dict[str, Any]:
        from app.services.world_boxoffice_service import get_world_boxoffice_state

        return get_world_boxoffice_state()

    def get_player_filmography_state(self) -> dict[str, Any]:
        from app.services.player_filmography_service import get_player_filmography_state

        return get_player_filmography_state()

    def has_player(self) -> bool:
        with get_connection() as conn:
            row = conn.execute("SELECT 1 FROM player_state WHERE id = 1").fetchone()
        return row is not None

    def advance_day(self) -> None:
        with get_connection() as conn:
            player = conn.execute(
                "SELECT current_year, current_month, current_day FROM player_state WHERE id = 1"
            ).fetchone()
            if not player:
                return
            year = int(player["current_year"])
            month = int(player["current_month"])
            day = int(player["current_day"] or 1) + 1
            month_changed = False
            if day > monthrange(year, month)[1]:
                day = 1
                month += 1
                month_changed = True
                if month > 12:
                    month = 1
                    year += 1
            conn.execute(
                "UPDATE player_state SET current_year = ?, current_month = ?, current_day = ? WHERE id = 1",
                (year, month, day),
            )
            conn.execute(
                """
                UPDATE save_player_state
                SET current_year = ?, current_month = ?, current_day = ?
                WHERE id = 1
                """,
                (year, month, day),
            )
            conn.commit()
        from app.services.casting_service import process_due_casting_offers
        from app.services.boxoffice_service import advance_active_theatrical_runs_for_current_day

        process_due_casting_offers()
        advance_active_theatrical_runs_for_current_day()
        if not month_changed:
            return

        from app.services.future_generation_service import generate_for_month
        from app.services.history_service import apply_history_for_month
        from app.services.finance_service import process_monthly_finance
        from app.services.historical_release_service import ensure_historical_releases_for_month
        from app.services.market_service import ensure_market_state_for_month
        from app.services.npc_activity_service import ensure_npc_releases_for_month
        from app.services.post_release_service import apply_post_release_events_for_month

        ensure_market_state_for_month(year, month, refresh=True)
        ensure_historical_releases_for_month(year, month)
        ensure_npc_releases_for_month(year, month)
        process_monthly_finance(year, month)
        apply_history_for_month(year, month)
        apply_post_release_events_for_month(year, month)
        if year >= 2030:
            generate_for_month(year, month)

    def advance_to_next_calendar_event(self) -> int:
        result = self.advance_to_next_schedule_or_project_event()
        return int(result.get("days", 0))

    def advance_to_next_schedule_or_project_event(self) -> dict[str, Any]:
        from app.services.calendar_service import (
            current_game_date,
            days_between_dates,
            next_calendar_event_after,
        )

        interrupting_project_id = self._first_project_with_available_event()
        if interrupting_project_id:
            return {"reason": "project_event", "days": 0, "project_id": interrupting_project_id}

        current = current_game_date()
        calendar_event = next_calendar_event_after(current)
        if not calendar_event:
            self.advance_day()
            interrupting_project_id = self._first_project_with_available_event()
            if interrupting_project_id:
                return {"reason": "project_event", "days": 1, "project_id": interrupting_project_id}
            return {"reason": "day", "days": 1}

        target = (int(calendar_event["year"]), int(calendar_event["month"]), int(calendar_event["day"]))
        days = max(1, days_between_dates(current, target))
        for elapsed in range(1, days + 1):
            self.advance_day()
            interrupting_project_id = self._first_project_with_available_event()
            if interrupting_project_id:
                return {"reason": "project_event", "days": elapsed, "project_id": interrupting_project_id}
        return {"reason": "calendar_event", "days": days, "calendar_event": calendar_event}

    def _first_project_with_available_event(self) -> str | None:
        from app.services.event_service import get_event_for_project

        with get_connection() as conn:
            rows = conn.execute(
                """
                SELECT id
                FROM projects
                WHERE status != 'released'
                ORDER BY created_year, id
                """
            ).fetchall()
        for row in rows:
            if get_event_for_project(row["id"]):
                return str(row["id"])
        return None

    def advance_month(self) -> None:
        self.advance_day()

    def get_database_counts(self) -> dict[str, int]:
        tables = [
            "core_eras",
            "core_genres",
            "core_project_scales",
            "core_stats",
            "core_production_stages",
            "people_actor_profiles",
            "people_director_profiles",
            "people_critic_profiles",
            "people_relationships",
            "people_career_timeline",
            "people_protected_schedules",
            "movies",
            "movies_historical",
            "movies_player_created",
            "movies_boxoffice",
            "movies_reviews",
            "movies_awards",
            "movies_post_release_metrics",
            "player_filmography_records",
            "history_domestic_events",
            "history_foreign_events",
            "history_policy_events",
            "history_market_events",
            "history_distribution_events",
            "history_theater_events",
            "history_premium_format_events",
            "history_ticket_prices",
            "history_protected_director_films",
            "history_award_events",
            "history_award_results",
            "industry_yearly_reports",
            "market_yearly_stats",
            "economic_yearly_indicators",
            "calendar_events",
            "crew_work_history",
            "production_projects",
            "production_budget_allocations",
            "production_choices",
            "production_dialogue_events",
            "production_random_events",
            "production_stage_logs",
            "systems_reputation",
            "systems_network",
            "systems_press",
            "systems_critics",
            "systems_plagiarism",
            "systems_franchise",
            "systems_post_release",
            "systems_future_generation",
            "save_player_state",
            "save_studio_state",
            "save_market_state",
            "save_event_flags",
            "save_generated_people",
            "save_generated_films",
            "eras",
            "genres",
            "project_scales",
            "people",
            "critics",
            "historical_events",
            "production_events",
            "simulation_events",
            "system_definitions",
            "stat_definitions",
            "reputation_definitions",
            "network_definitions",
            "starting_positions",
            "character_option_sets",
            "project_stage_definitions",
            "organizations",
            "awards",
            "future_generation_rules",
            "ticket_prices",
            "projects",
            "project_budget_allocations",
            "project_people",
            "project_versions",
            "project_distribution",
            "market_state",
            "theatrical_runs",
            "theatrical_daily_results",
            "event_history",
            "film_reviews",
            "news_items",
            "award_results",
            "controversy_cases",
            "intellectual_properties",
            "ip_entries",
            "reevaluation_events",
            "generated_entities",
            "completed_films",
        ]
        counts: dict[str, int] = {}
        with get_connection() as conn:
            for table in tables:
                row = conn.execute(f"SELECT COUNT(*) AS count FROM {table}").fetchone()
                counts[table] = int(row["count"])
        return counts

    @staticmethod
    def _with_stats(row: Any) -> dict[str, Any]:
        data = dict(row)
        data["stats"] = loads_json(data.pop("stats_json"), {})
        return data

    @staticmethod
    def _with_metadata(row: Any) -> dict[str, Any]:
        data = dict(row)
        data["metadata"] = loads_json(data.pop("metadata_json", None), {})
        return data
