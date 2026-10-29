from __future__ import annotations

from app.database import dumps_json, get_connection


def create_reevaluation_candidate(film_id: str, trigger_type: str = "online_buzz") -> None:
    with get_connection() as conn:
        film = conn.execute("SELECT * FROM completed_films WHERE id = ?", (film_id,)).fetchone()
        player = conn.execute("SELECT current_year, current_month FROM player_state WHERE id = 1").fetchone()
        if not film or not player:
            return
        if int(film["audience_score"] or 0) < 65 and int(film["critic_score"] or 0) < 65:
            return
        conn.execute(
            """
            INSERT INTO reevaluation_events (
                film_id, year, month, trigger_type, buzz_delta,
                reputation_delta, summary, effects_json
            ) VALUES (?, ?, ?, ?, 4, 2, ?, ?)
            """,
            (
                film_id,
                player["current_year"],
                player["current_month"],
                trigger_type,
                "개봉 후 반응을 바탕으로 장기 재평가 후보가 되었다.",
                dumps_json({"public_reputation": 1, "critic_reputation": 1}),
            ),
        )
        conn.execute(
            """
            INSERT INTO systems_post_release (
                movie_id, event_type, year, month, summary, effects_json
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                film_id,
                "reevaluation_candidate",
                player["current_year"],
                player["current_month"],
                "개봉 후 반응을 바탕으로 장기 재평가 후보가 되었다.",
                dumps_json({"public_reputation": 1, "critic_reputation": 1}),
            ),
        )
        conn.execute(
            """
            INSERT INTO movies_post_release_metrics (
                movie_id, metric_type, year, month, value, summary, effects_json
            ) VALUES (?, 'reevaluation', ?, ?, 2, ?, ?)
            """,
            (
                film_id,
                player["current_year"],
                player["current_month"],
                "장기 재평가 후보",
                dumps_json({"public_reputation": 1, "critic_reputation": 1}),
            ),
        )
        conn.commit()
