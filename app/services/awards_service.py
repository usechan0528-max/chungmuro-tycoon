from __future__ import annotations

from app.database import dumps_json, get_connection, loads_json


def consider_film_for_awards(film_id: str) -> None:
    with get_connection() as conn:
        film = conn.execute("SELECT * FROM completed_films WHERE id = ?", (film_id,)).fetchone()
        if not film:
            return
        awards = conn.execute("SELECT * FROM awards ORDER BY prestige DESC").fetchall()
        for award in awards:
            categories = loads_json(award["categories_json"], [])
            if not categories:
                continue
            category = "작품상" if "작품상" in categories else categories[0]
            critic_score = int(film["critic_score"] or 0)
            audience = int(film["final_audience"] or 0)
            if critic_score >= 78:
                result = "winner"
            elif critic_score >= 68 or audience >= 2_000_000:
                result = "nominee"
            else:
                continue
            conn.execute(
                """
                INSERT INTO award_results (
                    award_id, film_id, year, category, result, effects_json
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    award["id"],
                    film_id,
                    int(film["release_year"] or 0),
                    category,
                    result,
                    dumps_json({"critic_reputation": 4 if result == "winner" else 2}),
                ),
            )
            conn.execute(
                """
                INSERT INTO movies_awards (
                    award_id, movie_id, year, category, result, effects_json
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    award["id"],
                    film_id,
                    int(film["release_year"] or 0),
                    category,
                    result,
                    dumps_json({"critic_reputation": 4 if result == "winner" else 2}),
                ),
            )
            break
        conn.commit()
