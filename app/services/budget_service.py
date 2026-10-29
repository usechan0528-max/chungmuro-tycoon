from __future__ import annotations

from typing import Any

from app.database import get_connection


ALLOCATION_LABELS = {
    "scenario": "시나리오",
    "directing": "연출",
    "actors": "배우",
    "shooting": "촬영",
    "art": "미술",
    "stunt": "액션",
    "vfx": "VFX",
    "sound": "음악/음향",
    "editing": "편집",
    "contingency": "예비비",
}

GENRE_WEIGHT_COLUMNS = {
    "scenario": "scenario_weight",
    "directing": "directing_weight",
    "actors": "actors_weight",
    "shooting": "shooting_weight",
    "art": "art_weight",
    "stunt": "stunt_weight",
    "vfx": "vfx_weight",
    "sound": "sound_weight",
    "editing": "editing_weight",
    "contingency": "contingency_weight",
}

BASELINE_RECOMMENDATION = {
    "scenario": 12,
    "directing": 10,
    "actors": 18,
    "shooting": 8,
    "art": 9,
    "stunt": 4,
    "vfx": 5,
    "sound": 8,
    "editing": 10,
    "contingency": 16,
}

CONTINGENCY_CATEGORY = "contingency"
NON_CONTINGENCY_CATEGORIES = tuple(
    category for category in ALLOCATION_LABELS if category != CONTINGENCY_CATEGORY
)


def normalize_allocation(allocation: dict[str, int | float]) -> dict[str, int]:
    """Normalize user-facing production allocation percentages.

    Players allocate the working production categories. Whatever remains from the
    net production budget is treated as contingency, so contingency is derived
    instead of trusted from user input.
    """
    normalized = {
        key: max(0, int(round(float(allocation.get(key, 0) or 0))))
        for key in NON_CONTINGENCY_CATEGORIES
    }
    non_contingency_total = sum(normalized.values())
    if non_contingency_total > 100:
        normalized = _normalize_to_total(normalized, 100)
        non_contingency_total = 100
    normalized[CONTINGENCY_CATEGORY] = max(0, 100 - non_contingency_total)
    return {key: normalized.get(key, 0) for key in ALLOCATION_LABELS}


def normalize_allocation_amounts(
    production_budget: int,
    allocation_amounts: dict[str, int | float],
) -> dict[str, int]:
    rows = calculate_allocation_amounts_from_amounts(production_budget, allocation_amounts)
    return {row["category"]: int(row["percentage"]) for row in rows}


def calculate_allocation_amounts(
    production_budget: int,
    allocation: dict[str, int | float],
) -> list[dict[str, Any]]:
    normalized = normalize_allocation(allocation)
    budget = max(0, int(production_budget))
    rows: list[dict[str, Any]] = []
    assigned = 0
    for category in NON_CONTINGENCY_CATEGORIES:
        percentage = int(normalized.get(category, 0))
        amount = int(budget * percentage / 100)
        assigned += amount
        rows.append(
            {
                "category": category,
                "label": ALLOCATION_LABELS[category],
                "percentage": percentage,
                "amount": amount,
            }
        )
    contingency_percentage = int(normalized.get(CONTINGENCY_CATEGORY, 0))
    rows.append(
        {
            "category": CONTINGENCY_CATEGORY,
            "label": ALLOCATION_LABELS[CONTINGENCY_CATEGORY],
            "percentage": contingency_percentage,
            "amount": max(0, budget - assigned),
        }
    )
    return rows


def calculate_allocation_amounts_from_amounts(
    production_budget: int,
    allocation_amounts: dict[str, int | float],
) -> list[dict[str, Any]]:
    budget = max(0, int(production_budget))
    if budget <= 0:
        return [
            {
                "category": category,
                "label": ALLOCATION_LABELS[category],
                "percentage": 0,
                "amount": 0,
            }
            for category in ALLOCATION_LABELS
        ]

    non_contingency = {
        category: max(0, int(round(float(allocation_amounts.get(category, 0) or 0))))
        for category in NON_CONTINGENCY_CATEGORIES
    }
    non_contingency_total = sum(non_contingency.values())
    if non_contingency_total > budget:
        non_contingency = _normalize_amounts_to_total(non_contingency, budget)
        non_contingency_total = budget

    amounts = {category: non_contingency.get(category, 0) for category in NON_CONTINGENCY_CATEGORIES}
    amounts[CONTINGENCY_CATEGORY] = max(0, budget - non_contingency_total)
    percentages = _normalize_to_100(amounts)
    return [
        {
            "category": category,
            "label": ALLOCATION_LABELS[category],
            "percentage": int(percentages.get(category, 0)),
            "amount": int(amounts.get(category, 0)),
        }
        for category in ALLOCATION_LABELS
    ]


def get_genre_budget_template(genre_id: str) -> list[dict[str, Any]]:
    with get_connection() as conn:
        genre = conn.execute("SELECT * FROM genres WHERE id = ?", (genre_id,)).fetchone()
    if not genre:
        return []
    recommended = recommend_allocation_percentages(genre)
    return [
        {
            "category": category,
            "label": ALLOCATION_LABELS[category],
            "recommended_percentage": int(recommended[category]),
        }
        for category in ALLOCATION_LABELS
    ]


def recommend_allocation_percentages(genre: Any) -> dict[str, int]:
    ideal = _normalized_genre_weights(genre)
    baseline = dict(BASELINE_RECOMMENDATION)
    for category in ("shooting", "stunt", "vfx"):
        if _source_value(genre, GENRE_WEIGHT_COLUMNS[category], 0) <= 0:
            baseline[category] = 0

    baseline = _normalize_to_100(baseline)
    blended = {
        category: ideal[category] * 0.35 + baseline[category] * 0.65
        for category in ALLOCATION_LABELS
    }
    recommended = _normalize_to_100(blended)
    return _apply_contingency_floor(recommended, floor=10)


def save_project_budget_allocations(
    project_id: str,
    production_budget: int,
    allocation: dict[str, int | float],
    allocation_amounts: dict[str, int | float] | None = None,
    *,
    conn: Any | None = None,
) -> list[dict[str, Any]]:
    if allocation_amounts is not None:
        rows = calculate_allocation_amounts_from_amounts(production_budget, allocation_amounts)
    else:
        rows = calculate_allocation_amounts(production_budget, allocation)
    if conn is None:
        with get_connection() as owned_conn:
            _write_allocations(owned_conn, project_id, rows)
            owned_conn.commit()
    else:
        _write_allocations(conn, project_id, rows)
    return rows


def get_project_budget_allocations(project_id: str) -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT * FROM project_budget_allocations
            WHERE project_id = ?
            ORDER BY category
            """,
            (project_id,),
        ).fetchall()
    return [
        {
            "project_id": row["project_id"],
            "category": row["category"],
            "label": ALLOCATION_LABELS.get(row["category"], row["category"]),
            "percentage": int(row["percentage"] or 0),
            "amount": int(row["amount"] or 0),
            "notes": row["notes"],
        }
        for row in rows
    ]


def _write_allocations(conn: Any, project_id: str, rows: list[dict[str, Any]]) -> None:
    for row in rows:
        values = (project_id, row["category"], row["percentage"], row["amount"])
        conn.execute(
            """
            INSERT OR REPLACE INTO project_budget_allocations (
                project_id, category, percentage, amount
            ) VALUES (?, ?, ?, ?)
            """,
            values,
        )
        conn.execute(
            """
            INSERT OR REPLACE INTO production_budget_allocations (
                project_id, category, percentage, amount
            ) VALUES (?, ?, ?, ?)
            """,
            values,
        )


def _normalized_genre_weights(genre: Any) -> dict[str, int]:
    weights = {
        category: max(0, float(_source_value(genre, column, 0) or 0))
        for category, column in GENRE_WEIGHT_COLUMNS.items()
    }
    return _normalize_to_100(weights)


def _normalize_to_100(weights: dict[str, int | float]) -> dict[str, int]:
    positive = {category: max(0.0, float(weights.get(category, 0))) for category in ALLOCATION_LABELS}
    total = sum(positive.values())
    if total <= 0:
        return {category: 100 // len(ALLOCATION_LABELS) for category in ALLOCATION_LABELS}

    raw = {category: positive[category] / total * 100 for category in ALLOCATION_LABELS}
    normalized = {category: int(raw[category]) for category in ALLOCATION_LABELS}
    remainder = 100 - sum(normalized.values())
    fractions = sorted(
        ALLOCATION_LABELS,
        key=lambda category: raw[category] - int(raw[category]),
        reverse=True,
    )
    for category in fractions[:remainder]:
        normalized[category] += 1
    return normalized


def _normalize_to_total(weights: dict[str, int | float], target_total: int) -> dict[str, int]:
    positive = {category: max(0.0, float(value)) for category, value in weights.items()}
    total = sum(positive.values())
    if total <= 0:
        return {category: 0 for category in weights}
    raw = {category: positive[category] / total * target_total for category in weights}
    normalized = {category: int(raw[category]) for category in weights}
    remainder = target_total - sum(normalized.values())
    fractions = sorted(
        weights,
        key=lambda category: raw[category] - int(raw[category]),
        reverse=True,
    )
    for category in fractions[:remainder]:
        normalized[category] += 1
    return normalized


def _normalize_amounts_to_total(amounts: dict[str, int | float], target_total: int) -> dict[str, int]:
    target_total = max(0, int(target_total))
    if target_total <= 0:
        return {category: 0 for category in amounts}
    positive = {category: max(0.0, float(value)) for category, value in amounts.items()}
    total = sum(positive.values())
    if total <= 0:
        return {category: 0 for category in amounts}
    raw = {category: positive[category] / total * target_total for category in amounts}
    normalized = {category: int(raw[category]) for category in amounts}
    remainder = target_total - sum(normalized.values())
    fractions = sorted(
        amounts,
        key=lambda category: raw[category] - int(raw[category]),
        reverse=True,
    )
    for category in fractions[:remainder]:
        normalized[category] += 1
    return normalized


def _apply_contingency_floor(allocation: dict[str, int], *, floor: int) -> dict[str, int]:
    current = int(allocation.get("contingency", 0))
    if current >= floor:
        return allocation
    needed = floor - current
    allocation = dict(allocation)
    allocation["contingency"] = floor
    donors = sorted(
        (category for category in allocation if category != "contingency"),
        key=lambda category: allocation[category],
        reverse=True,
    )
    for category in donors:
        if needed <= 0:
            break
        take = min(needed, max(0, allocation[category] - 1))
        allocation[category] -= take
        needed -= take
    return allocation


def _source_value(source: Any, key: str, default: Any = None) -> Any:
    if hasattr(source, "keys") and key in source.keys():
        return source[key]
    if isinstance(source, dict):
        return source.get(key, default)
    return default
