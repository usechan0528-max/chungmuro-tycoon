from __future__ import annotations

import random
from typing import Any

from app.database import get_connection
from app.services.event_engine import get_project_event


def get_event_for_project(project_id: str) -> dict[str, Any] | None:
    if _production_event_count(project_id) >= _production_event_cap(project_id):
        return None
    candidates = [
        event
        for event in (
            get_project_event(project_id, category="production"),
            get_project_event(project_id, category="dialogue"),
        )
        if event
    ]
    if not candidates:
        return None
    category_context = _project_event_category_context(project_id)
    weights = [
        _category_variety_weight(event, category_context, has_alternatives=len(candidates) > 1)
        for event in candidates
    ]
    return random.choices(candidates, weights=weights, k=1)[0]


def _production_event_count(project_id: str) -> int:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT COUNT(*) AS count
            FROM event_history
            WHERE project_id = ? AND category IN ('production', 'dialogue')
            """,
            (project_id,),
        ).fetchone()
    return int(row["count"] if row else 0)


def _production_event_cap(project_id: str) -> int:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT s.max_events
            FROM projects p
            JOIN project_scales s ON s.id = p.scale_id
            WHERE p.id = ?
            """,
            (project_id,),
        ).fetchone()
    if not row:
        return 3
    return max(1, min(15, int(row["max_events"] or 3)))


def _project_event_category_context(project_id: str) -> dict[str, Any]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT category
            FROM event_history
            WHERE project_id = ? AND category IN ('production', 'dialogue')
            ORDER BY id DESC
            LIMIT 8
            """,
            (project_id,),
        ).fetchall()
    categories = [str(row["category"] or "") for row in rows]
    return {
        "last_category": categories[0] if categories else "",
        "counts": {category: categories.count(category) for category in {"production", "dialogue"}},
    }


def _category_variety_weight(event: dict[str, Any], context: dict[str, Any], *, has_alternatives: bool) -> int:
    weight = float(event.get("weight", 100) or 100)
    category = str(event.get("category") or "")
    counts = context.get("counts") if isinstance(context.get("counts"), dict) else {}
    if has_alternatives and category == context.get("last_category"):
        weight *= 0.58
    other_categories = [value for key, value in counts.items() if key != category]
    own_count = int(counts.get(category, 0) or 0)
    if other_categories and own_count >= min(int(value or 0) for value in other_categories) + 2:
        weight *= 0.75
    if own_count == 0:
        weight *= 1.12
    return max(1, int(round(weight)))
