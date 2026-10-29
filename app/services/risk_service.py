from __future__ import annotations

from app.database import dumps_json, get_connection, loads_json


def evaluate_release_risks(project_id: str, film_id: str) -> None:
    with get_connection() as conn:
        project = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
        player = conn.execute("SELECT current_year, current_month FROM player_state WHERE id = 1").fetchone()
        if not project or not player:
            return
        stats = loads_json(project["stats_json"], {})
        plagiarism_risk = int(stats.get("plagiarism_risk", 0))
        controversy_risk = int(stats.get("controversy_risk", 0))
        if plagiarism_risk < 12 and controversy_risk < 16:
            return
        severity = max(plagiarism_risk, controversy_risk)
        case_type = "plagiarism" if plagiarism_risk >= controversy_risk else "controversy"
        status = "rumor" if severity < 30 else "reported"
        conn.execute(
            """
            INSERT INTO controversy_cases (
                target_type, target_id, case_type, severity, status,
                year, month, effects_json
            ) VALUES ('film', ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                film_id,
                case_type,
                severity,
                status,
                player["current_year"],
                player["current_month"],
                dumps_json({"public_reputation": -2, "critic_reputation": -2}),
            ),
        )
        conn.execute(
            """
            INSERT INTO systems_plagiarism (
                target_type, target_id, case_type, severity, status,
                year, month, effects_json
            ) VALUES ('film', ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                film_id,
                case_type,
                severity,
                status,
                player["current_year"],
                player["current_month"],
                dumps_json({"public_reputation": -2, "critic_reputation": -2}),
            ),
        )
        conn.commit()
