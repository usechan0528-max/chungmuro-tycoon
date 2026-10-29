from __future__ import annotations

import uuid
from calendar import monthrange
from datetime import date
from typing import Any

from app.database import dumps_json, get_connection
from app.services.progression_service import (
    STAGE_LABELS,
    can_calculate_release,
    get_stage_flow_for_scale,
    stage_time_cost_days_for_project,
)


DateTuple = tuple[int, int, int]


def current_game_date() -> DateTuple:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT current_year, current_month, current_day FROM player_state WHERE id = 1"
        ).fetchone()
    if not row:
        return (1980, 1, 1)
    return (int(row["current_year"]), int(row["current_month"]), int(row["current_day"] or 1))


def advance_days(days: int) -> None:
    days = max(0, int(days))
    if days <= 0:
        return
    from app.services.game_state import GameStateService

    state = GameStateService()
    for _ in range(days):
        state.advance_day()


def add_calendar_event(
    *,
    title: str,
    event_type: str,
    start: DateTuple | None = None,
    end: DateTuple | None = None,
    project_id: str | None = None,
    description: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> str:
    start_date = start or current_game_date()
    end_date = end or start_date
    event_id = f"calendar_{uuid.uuid4().hex[:12]}"
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO calendar_events (
                id, year, month, day, end_year, end_month, end_day,
                title, event_type, project_id, description, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event_id,
                start_date[0],
                start_date[1],
                start_date[2],
                end_date[0],
                end_date[1],
                end_date[2],
                title,
                event_type,
                project_id,
                description,
                dumps_json(metadata or {}),
            ),
        )
        conn.commit()
    return event_id


def record_project_time_spent(
    *,
    project_id: str,
    project_title: str,
    stage: str,
    scale_id: str,
    days: int,
    title: str,
    event_type: str,
    description: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> int:
    days = max(1, int(days))
    start = current_game_date()
    advance_days(days)
    end = current_game_date()
    event_metadata = {
        "stage": stage,
        "stageLabel": STAGE_LABELS.get(stage, stage),
        "scaleId": scale_id,
        "days": days,
        **(metadata or {}),
    }
    add_calendar_event(
        title=f"{project_title}: {title}",
        event_type=event_type,
        start=start,
        end=end,
        project_id=project_id,
        description=description,
        metadata=event_metadata,
    )
    return days


def schedule_project_calendar(
    *,
    project_id: str,
    project_title: str,
    scale_id: str,
    start: DateTuple | None = None,
    stats: dict[str, Any] | None = None,
) -> None:
    start_date = start or current_game_date()
    project_stats = stats or {}
    with get_connection() as conn:
        conn.execute(
            "DELETE FROM calendar_events WHERE project_id = ? AND event_type IN ('planned_stage', 'planned_release')",
            (project_id,),
        )
        cursor = start_date
        for stage in get_stage_flow_for_scale(scale_id):
            stage_label = STAGE_LABELS.get(stage, stage)
            if can_calculate_release(stage):
                _insert_calendar_event(
                    conn,
                    title=f"{project_title}: {stage_label} 예정",
                    event_type="planned_release",
                    start=cursor,
                    end=cursor,
                    project_id=project_id,
                    description="현재 제작 일정 기준으로 산출한 개봉 가능 시점.",
                    metadata={"stage": stage, "stageLabel": stage_label, "scaleId": scale_id},
                )
                break
            days = stage_time_cost_days_for_project(stage, scale_id, project_stats)
            end = add_days_to_date(cursor, days)
            _insert_calendar_event(
                conn,
                title=f"{project_title}: {stage_label}",
                event_type="planned_stage",
                start=cursor,
                end=end,
                project_id=project_id,
                description=f"예상 소요 {days}일.",
                metadata={"stage": stage, "stageLabel": stage_label, "scaleId": scale_id, "days": days},
            )
            cursor = end
        conn.commit()


def list_calendar_events_for_month(year: int, month: int, *, limit: int = 40) -> list[dict[str, Any]]:
    month_start = _date_index((year, month, 1))
    month_end = _date_index((year, month, monthrange(year, month)[1]))
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT c.*, p.title AS project_title
            FROM calendar_events c
            LEFT JOIN projects p ON p.id = c.project_id
            ORDER BY c.year, c.month, c.day, c.created_at
            """
        ).fetchall()
    events = []
    for row in rows:
        data = dict(row)
        start_index = _date_index((int(data["year"]), int(data["month"]), int(data["day"])))
        end_index = _date_index(
            (
                int(data["end_year"] or data["year"]),
                int(data["end_month"] or data["month"]),
                int(data["end_day"] or data["day"]),
            )
        )
        if start_index <= month_end and end_index >= month_start:
            events.append(data)
    return events[:limit]


def next_calendar_event_after(date_value: DateTuple | None = None) -> dict[str, Any] | None:
    current = date_value or current_game_date()
    current_index = _date_index(current)
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT c.*, p.title AS project_title
            FROM calendar_events c
            LEFT JOIN projects p ON p.id = c.project_id
            ORDER BY c.year, c.month, c.day, c.created_at
            """
        ).fetchall()
    for row in rows:
        data = dict(row)
        start = (int(data["year"]), int(data["month"]), int(data["day"]))
        if _date_index(start) > current_index:
            return data
    return None


def days_between_dates(start: DateTuple, end: DateTuple) -> int:
    return max(0, (date(*end) - date(*start)).days)


def add_days_to_date(date_value: DateTuple, days: int) -> DateTuple:
    year, month, day = date_value
    remaining = max(0, int(days))
    while remaining > 0:
        days_in_month = monthrange(year, month)[1]
        available = days_in_month - day
        if remaining <= available:
            day += remaining
            break
        remaining -= available + 1
        day = 1
        month += 1
        if month > 12:
            month = 1
            year += 1
    return (year, month, day)


def _insert_calendar_event(
    conn: Any,
    *,
    title: str,
    event_type: str,
    start: DateTuple,
    end: DateTuple,
    project_id: str | None,
    description: str | None,
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
            start[0],
            start[1],
            start[2],
            end[0],
            end[1],
            end[2],
            title,
            event_type,
            project_id,
            description,
            dumps_json(metadata),
        ),
    )


def _date_index(date_value: DateTuple) -> int:
    year, month, day = date_value
    return year * 372 + month * 31 + day
