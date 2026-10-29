from __future__ import annotations

from typing import Any

from app.services.event_engine import apply_project_event_choice, get_project_event


def get_dialogue_event_for_project(project_id: str) -> dict[str, Any] | None:
    return get_project_event(project_id, category="dialogue")


def apply_dialogue_choice(
    project_id: str,
    event: dict[str, Any] | None,
    choice: dict[str, Any],
    *,
    advance_stage: bool = True,
) -> dict[str, Any]:
    return apply_project_event_choice(
        project_id,
        event,
        choice,
        advance_stage=advance_stage,
    )
