from __future__ import annotations

from app.database import dumps_json, get_connection, loads_json
from app.services.game_state import clamp


def create_reviews_for_film(film_id: str) -> None:
    with get_connection() as conn:
        film = conn.execute("SELECT * FROM completed_films WHERE id = ?", (film_id,)).fetchone()
        if not film:
            return
        critics = conn.execute("SELECT * FROM critics ORDER BY id").fetchall()
        for critic in critics:
            taste = loads_json(critic["taste_profile_json"], {})
            scoring_style = loads_json(critic["scoring_style_json"], {})
            influence = loads_json(critic["influence_json"], {})
            taste_bonus = _taste_bonus(taste, scoring_style)
            score = clamp(int(film["critic_score"] or 50) + taste_bonus - 2)
            if score >= 75:
                quote = "장르의 익숙함 속에서도 창작자의 태도가 선명하다."
            elif score >= 55:
                quote = "완성도에는 장단이 공존하지만 관객과 만날 지점이 있다."
            else:
                quote = "기획의 의도에 비해 결과물의 설득력이 부족하다."
            conn.execute(
                """
                INSERT INTO film_reviews (
                    film_id, critic_id, source_type, score, quote, effects_json
                ) VALUES (?, ?, 'critic', ?, ?, ?)
                """,
                (film_id, critic["id"], score, quote, dumps_json(influence)),
            )
            conn.execute(
                """
                INSERT INTO movies_reviews (
                    movie_id, critic_id, source_type, score, quote, effects_json
                ) VALUES (?, ?, 'critic', ?, ?, ?)
                """,
                (film_id, critic["id"], score, quote, dumps_json(influence)),
            )
        conn.commit()


def _taste_bonus(taste_profile: dict[str, object], scoring_style: dict[str, object]) -> int:
    legacy_keys = ("scenario_quality", "directing_quality", "genre_satisfaction")
    if any(key in taste_profile for key in legacy_keys):
        values = [float(taste_profile.get(key, 50) or 50) for key in legacy_keys]
        anchor = sum(values) / len(values)
    else:
        weights = {
            "narrative": 0.18,
            "directing": 0.18,
            "emotion": 0.12,
            "genreCraft": 0.16,
            "auteurism": 0.12,
            "commercialEntertainment": 0.10,
            "socialMeaning": 0.08,
            "technicalCraft": 0.06,
        }
        anchor = sum(float(taste_profile.get(key, 65) or 65) * weight for key, weight in weights.items())

    strictness = float(scoring_style.get("strictness", 70) or 70)
    return int(round((anchor - 70) / 8 - (strictness - 70) / 12))
