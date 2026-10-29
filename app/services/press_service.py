from __future__ import annotations

from app.database import dumps_json, get_connection


def create_release_news(film_id: str) -> None:
    with get_connection() as conn:
        film = conn.execute("SELECT * FROM completed_films WHERE id = ?", (film_id,)).fetchone()
        if not film:
            return
        if int(film["final_audience"] or 0) >= int(film["break_even_audience"] or 0):
            title = f"'{film['title']}', 손익분기점 돌파"
            body = "개봉 이후 입소문과 안정적인 좌석 판매로 시장의 관심을 모았다."
            effects = {"public_reputation": 3, "investor_reputation": 2}
        else:
            title = f"'{film['title']}', 아쉬운 개봉 성적"
            body = "흥행 추이는 기대에 미치지 못했지만 후속 반응을 지켜봐야 한다."
            effects = {"public_reputation": -1, "investor_reputation": -2}
        conn.execute(
            """
            INSERT INTO news_items (
                year, month, title, body, source_type, target_type,
                target_id, effects_json
            ) VALUES (?, ?, ?, ?, 'press', 'film', ?, ?)
            """,
            (film["release_year"], film["release_month"], title, body, film_id, dumps_json(effects)),
        )
        conn.execute(
            """
            INSERT INTO systems_press (
                year, month, title, body, source_type, target_type,
                target_id, effects_json
            ) VALUES (?, ?, ?, ?, 'press', 'film', ?, ?)
            """,
            (film["release_year"], film["release_month"], title, body, film_id, dumps_json(effects)),
        )
        conn.commit()
