from __future__ import annotations

from typing import Any

from app.database import get_connection, loads_json
from app.services.risk_service import evaluate_release_risks


def list_plagiarism_cases() -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT * FROM controversy_cases
            WHERE case_type = 'plagiarism'
            ORDER BY year DESC, month DESC, id DESC
            """
        ).fetchall()
    cases: list[dict[str, Any]] = []
    for row in rows:
        case = dict(row)
        case["effects"] = loads_json(case.pop("effects_json"), {})
        cases.append(case)
    return cases
