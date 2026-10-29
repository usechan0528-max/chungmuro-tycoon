from __future__ import annotations

import random
from typing import Any

from app.database import dumps_json, get_connection, loads_json
from app.services.people_stat_service import effective_stats_for_year


GENRE_TITLE_POOLS = {
    "genre_crime_thriller": ("검은 항로", "침묵의 수사", "도시의 밤", "두 번째 증언", "사라진 목격자"),
    "genre_action": ("마지막 추격", "불타는 골목", "강철의 약속", "압구정 추격전", "폭풍 전야"),
    "genre_horror_occult": ("닫힌 방의 제사", "붉은 부적", "귀향 없는 밤", "산 아래 목소리", "그림자 굿"),
    "genre_romance_melodrama": ("여름의 얼굴", "다시 만난 계절", "비 오는 오후", "오래된 편지", "우리의 마지막 장면"),
    "genre_comedy": ("오늘도 무사히", "대충 살아도 봄", "수상한 동거", "웃기는 가족", "동네 대표"),
    "genre_family_human_drama": ("집으로 가는 길목", "아버지의 방", "작은 약속", "삼대의 저녁", "봄날의 가족"),
    "genre_period_historical": ("왕의 그림자", "붉은 깃발", "달빛 장군", "궁궐의 밤", "칼의 이름"),
    "genre_social_true_story": ("증언", "그날의 기록", "법정 밖 사람들", "흔들리는 도시", "침묵을 깨다"),
    "genre_indie_art": ("낮은 방", "멀어진 계절", "빈 의자", "느린 산책", "파도 없는 바다"),
    "genre_sf_disaster_monster": ("한강의 균열", "서울 대피령", "제3구역", "푸른 재난", "괴수의 계절"),
    "genre_fantasy": ("달의 상점", "비밀의 문", "시간의 서랍", "나무 아래 왕국", "밤의 수호자"),
    "genre_animation": ("구름 마을", "꼬마 탐정단", "바다의 노래", "별빛 우체국", "숲의 약속"),
}

SCALE_AUDIENCE_RANGES = {
    "scale_independent": (55_000, 360_000),
    "scale_low_budget_genre": (140_000, 980_000),
    "scale_mid_commercial": (520_000, 2_900_000),
    "scale_large_commercial": (1_400_000, 6_300_000),
    "scale_tentpole": (2_800_000, 9_500_000),
}

SCALE_CHOICES_BY_ERA = {
    "1980s": ("scale_independent", "scale_low_budget_genre", "scale_mid_commercial"),
    "1990s": ("scale_independent", "scale_low_budget_genre", "scale_mid_commercial", "scale_large_commercial"),
    "2000s": ("scale_low_budget_genre", "scale_mid_commercial", "scale_large_commercial"),
    "2010s": ("scale_low_budget_genre", "scale_mid_commercial", "scale_large_commercial", "scale_tentpole"),
    "2020s": ("scale_independent", "scale_low_budget_genre", "scale_mid_commercial", "scale_large_commercial"),
}

RELEASE_DAY_PATTERN = (1, 1, 4, 8, 12, 16, 22, 25)

COMPANY_NAMES = (
    "한강픽처스",
    "청계필름",
    "삼거리영화사",
    "블루문스튜디오",
    "스튜디오 광장",
    "동백필름",
    "시네마공방",
    "새벽제작소",
)


def ensure_npc_releases_for_month(year: int, month: int) -> dict[str, int]:
    """Create deterministic monthly NPC releases so the market keeps moving."""
    year = int(year)
    month = int(month)
    with get_connection() as conn:
        existing = conn.execute(
            """
            SELECT COUNT(*) AS count
            FROM market_releases
            WHERE origin = 'npc_generated'
              AND release_year = ?
              AND release_month = ?
            """,
            (year, month),
        ).fetchone()
        if existing and int(existing["count"] or 0) > 0:
            return {"created": 0, "existing": int(existing["count"] or 0)}

        genres = [dict(row) for row in conn.execute("SELECT * FROM genres ORDER BY id").fetchall()]
        scales = [dict(row) for row in conn.execute("SELECT * FROM project_scales ORDER BY min_budget").fetchall()]
        if not genres or not scales:
            return {"created": 0, "existing": 0}

        directors = _available_people(conn, "director", year)
        actors = _available_people(conn, "actor", year)
        market_state = _market_state(conn, year, month)
        rng = random.Random(f"npc-releases:{year:04d}-{month:02d}:v2")
        release_count = _release_count_for_year(year, market_state)
        created = 0
        used_titles: set[str] = set()

        for index in range(release_count):
            genre = _weighted_genre_choice(rng, genres, year)
            scale = _scale_choice(rng, scales, year, market_state)
            director = _weighted_person_choice(rng, directors, year, "director", genre["id"])
            cast = _weighted_actor_sample(rng, actors, year, genre["id"], count=rng.randint(2, 4))
            title = _unique_title(rng, genre["id"], year, month, used_titles)
            release_day = RELEASE_DAY_PATTERN[index % len(RELEASE_DAY_PATTERN)]
            release_id = f"npc_release_{year}_{month:02d}_{index + 1:02d}"
            expected_audience = _expected_audience(
                rng=rng,
                scale_id=scale["id"],
                genre_id=genre["id"],
                year=year,
                market_state=market_state,
                director=director,
                cast=cast,
            )
            metadata = _release_metadata(
                title=title,
                year=year,
                month=month,
                release_day=release_day,
                genre=genre,
                scale=scale,
                expected_audience=expected_audience,
                director=director,
                cast=cast,
                company=COMPANY_NAMES[(index + month + year) % len(COMPANY_NAMES)],
            )
            _insert_release(conn, release_id, title, year, month, genre, scale, expected_audience, metadata)
            _insert_career_entries(conn, release_id, metadata)
            _insert_release_news(conn, release_id, metadata, index)
            created += 1

        conn.commit()
    return {"created": created, "existing": 0}


def _available_people(conn: Any, person_type: str, year: int) -> list[dict[str, Any]]:
    if person_type == "director":
        rows = conn.execute(
            """
            SELECT *
            FROM people
            WHERE type = 'director'
              AND COALESCE(available_from, 9999) <= ?
              AND COALESCE(status, 'active') NOT IN ('retired', 'deceased')
              AND COALESCE(historical_filmography_locked, 0) = 0
            ORDER BY name_ko
            """,
            (year,),
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT *
            FROM people
            WHERE type = 'actor'
              AND COALESCE(available_from, 9999) <= ?
              AND COALESCE(status, 'active') NOT IN ('retired', 'deceased')
            ORDER BY name_ko
            """,
            (year,),
        ).fetchall()
    return [dict(row) for row in rows]


def _market_state(conn: Any, year: int, month: int) -> dict[str, Any]:
    row = conn.execute(
        """
        SELECT *
        FROM market_state
        WHERE year = ? AND month = ?
        """,
        (year, month),
    ).fetchone()
    if row:
        return dict(row)
    return {
        "theater_demand": 55 if year >= 2020 else 90 if year >= 2010 else 80 if year >= 2000 else 55,
        "foreign_competition": 75 if year >= 2010 else 65 if year >= 2000 else 55,
        "middle_budget_risk": 85 if year >= 2020 else 65 if year >= 2010 else 45,
        "korean_film_trust": 60 if year >= 2000 else 45,
    }


def _release_count_for_year(year: int, market_state: dict[str, Any]) -> int:
    base = 2
    if year >= 1990:
        base = 3
    if year >= 2000:
        base = 4
    if year >= 2010:
        base = 5
    if year >= 2020:
        base = 4
    theater_demand = int(market_state.get("theater_demand") or 50)
    if theater_demand >= 80:
        base += 1
    if theater_demand <= 45:
        base -= 1
    return max(2, min(6, base))


def _weighted_genre_choice(rng: random.Random, genres: list[dict[str, Any]], year: int) -> dict[str, Any]:
    era_key = _era_key(year)
    weighted: list[tuple[dict[str, Any], float]] = []
    for genre in genres:
        era_fit = loads_json(genre.get("era_fit_json"), {})
        fit = int(era_fit.get(era_key, 55) or 55)
        if genre["id"] == "genre_romance_melodrama" and year >= 2020:
            fit -= 20
        if genre["id"] == "genre_horror_occult" and year >= 2020:
            fit += 20
        if genre["id"] in {"genre_crime_thriller", "genre_action"} and year >= 2010:
            fit += 15
        if genre["id"] in {"genre_sf_disaster_monster", "genre_fantasy"} and year < 2000:
            fit -= 30
        weighted.append((genre, max(5.0, float(fit))))
    return _weighted_choice(rng, weighted)


def _scale_choice(
    rng: random.Random,
    scales: list[dict[str, Any]],
    year: int,
    market_state: dict[str, Any],
) -> dict[str, Any]:
    scale_map = {scale["id"]: scale for scale in scales}
    allowed = [scale_id for scale_id in SCALE_CHOICES_BY_ERA.get(_era_key(year), ()) if scale_id in scale_map]
    if not allowed:
        allowed = [scale["id"] for scale in scales if scale["id"] != "scale_short"] or [scales[0]["id"]]
    weights: list[tuple[dict[str, Any], float]] = []
    middle_risk = int(market_state.get("middle_budget_risk") or 50)
    for scale_id in allowed:
        weight = {
            "scale_independent": 1.5,
            "scale_low_budget_genre": 2.4,
            "scale_mid_commercial": 2.1,
            "scale_large_commercial": 1.4,
            "scale_tentpole": 0.7,
        }.get(scale_id, 1.0)
        if scale_id == "scale_mid_commercial" and middle_risk >= 75:
            weight *= 0.55
        if scale_id in {"scale_large_commercial", "scale_tentpole"} and year < 2000:
            weight *= 0.35
        weights.append((scale_map[scale_id], weight))
    return _weighted_choice(rng, weights)


def _weighted_person_choice(
    rng: random.Random,
    people: list[dict[str, Any]],
    year: int,
    person_type: str,
    genre_id: str,
) -> dict[str, Any] | None:
    if not people:
        return None
    weighted = []
    for person in people:
        stats = effective_stats_for_year(person, year)
        genre_fit = loads_json(person.get("genre_fit_json"), {})
        base = _person_market_score(stats, person_type)
        fit = int(genre_fit.get(genre_id, 55) or 55)
        weight = max(1.0, base * 0.65 + fit * 0.35)
        weighted.append((person, weight))
    return _weighted_choice(rng, weighted)


def _weighted_actor_sample(
    rng: random.Random,
    actors: list[dict[str, Any]],
    year: int,
    genre_id: str,
    *,
    count: int,
) -> list[dict[str, Any]]:
    pool = list(actors)
    selected: list[dict[str, Any]] = []
    for _ in range(min(count, len(pool))):
        actor = _weighted_person_choice(rng, pool, year, "actor", genre_id)
        if not actor:
            break
        selected.append(actor)
        pool = [candidate for candidate in pool if candidate["id"] != actor["id"]]
    return selected


def _expected_audience(
    *,
    rng: random.Random,
    scale_id: str,
    genre_id: str,
    year: int,
    market_state: dict[str, Any],
    director: dict[str, Any] | None,
    cast: list[dict[str, Any]],
) -> int:
    low, high = SCALE_AUDIENCE_RANGES.get(scale_id, (120_000, 1_200_000))
    base = rng.randint(low, high)
    theater = int(market_state.get("theater_demand") or 55)
    trust = int(market_state.get("korean_film_trust") or 55)
    foreign = int(market_state.get("foreign_competition") or 55)
    market_modifier = (0.72 + theater / 180) * (0.78 + trust / 220) * (1.08 - foreign / 420)
    person_bonus = 1.0
    if director:
        stats = effective_stats_for_year(director, year)
        person_bonus += (stats.get("commercialSense", 50) - 50) / 260
        person_bonus += (stats.get("directing", 50) - 50) / 360
    actor_scores = []
    for actor in cast[:3]:
        stats = effective_stats_for_year(actor, year)
        actor_scores.append(max(stats.get("ticketPower", 40), stats.get("brandPower", 40)))
    if actor_scores:
        person_bonus += (sum(actor_scores) / len(actor_scores) - 50) / 230
    if genre_id == "genre_horror_occult" and year >= 2020:
        market_modifier *= 1.12
    if genre_id in {"genre_sf_disaster_monster", "genre_fantasy"} and year < 2000:
        market_modifier *= 0.65
    return max(6_000, int(base * market_modifier * person_bonus))


def _release_metadata(
    *,
    title: str,
    year: int,
    month: int,
    release_day: int,
    genre: dict[str, Any],
    scale: dict[str, Any],
    expected_audience: int,
    director: dict[str, Any] | None,
    cast: list[dict[str, Any]],
    company: str,
) -> dict[str, Any]:
    run_days = _run_days_for_scale(scale["id"])
    director_name = director.get("name_ko") if director else "신예 감독"
    actor_names = [actor.get("name_ko") for actor in cast if actor.get("name_ko")]
    description = (
        f"{company}가 준비한 {genre.get('name')} 계열의 {scale.get('name')}입니다. "
        f"{director_name} 연출, {', '.join(actor_names[:3]) or '신인 배우진'} 출연으로 "
        "동시기 시장에서 관객 반응을 시험합니다."
    )
    return {
        "title": title,
        "releaseDay": release_day,
        "runDays": run_days,
        "genreId": genre["id"],
        "genreName": genre.get("name"),
        "scaleId": scale["id"],
        "scaleName": scale.get("name"),
        "expectedAudience": expected_audience,
        "directorId": director.get("id") if director else None,
        "directorName": director_name,
        "actorIds": [actor.get("id") for actor in cast if actor.get("id")],
        "actorNames": actor_names,
        "productionCompany": company,
        "description": description,
        "sourceNote": "게임 내 NPC 자동 활동",
        "audienceBand": _audience_band(expected_audience),
        "careerSummary": f"{year}년 {month}월 개봉한 {genre.get('name')} 경쟁작.",
    }


def _insert_release(
    conn: Any,
    release_id: str,
    title: str,
    year: int,
    month: int,
    genre: dict[str, Any],
    scale: dict[str, Any],
    expected_audience: int,
    metadata: dict[str, Any],
) -> None:
    conn.execute(
        """
        INSERT OR REPLACE INTO market_releases (
            id, title, origin, release_year, release_month, genre_id, scale_id,
            expected_audience, actual_audience, effects_json
        ) VALUES (?, ?, 'npc_generated', ?, ?, ?, ?, ?, NULL, ?)
        """,
        (
            release_id,
            title,
            year,
            month,
            genre["id"],
            scale["id"],
            expected_audience,
            dumps_json(metadata),
        ),
    )
    conn.execute(
        """
        INSERT OR REPLACE INTO movies (
            id, title, movie_type, genre_id, scale_id, status, metadata_json
        ) VALUES (?, ?, 'npc_generated', ?, ?, 'released', ?)
        """,
        (release_id, title, genre["id"], scale["id"], dumps_json(metadata)),
    )
    conn.execute(
        """
        INSERT OR REPLACE INTO generated_entities (
            id, entity_type, name, generated_year, generated_month,
            source_rule_id, data_json
        ) VALUES (?, 'film', ?, ?, ?, 'npc_monthly_release', ?)
        """,
        (release_id, title, year, month, dumps_json(metadata)),
    )
    conn.execute(
        """
        INSERT OR REPLACE INTO save_generated_films (
            id, title, generated_year, generated_month, source_rule_id, data_json
        ) VALUES (?, ?, ?, ?, 'npc_monthly_release', ?)
        """,
        (release_id, title, year, month, dumps_json(metadata)),
    )


def _insert_career_entries(conn: Any, release_id: str, metadata: dict[str, Any]) -> None:
    year, month = _release_year_month(release_id)
    people = [(metadata["directorId"], "director")] if metadata.get("directorId") else []
    people.extend((actor_id, "actor") for actor_id in metadata.get("actorIds") or [] if actor_id)
    for person_id, role in people:
        _insert_career_entry_once(
            conn,
            person_id=person_id,
            release_id=release_id,
            role=role,
            year=year,
            month=month,
            result={
                "title": metadata["title"],
                "summary": metadata.get("careerSummary"),
                "source": "npc_generated_release",
                "audienceBand": metadata.get("audienceBand"),
            },
        )


def _insert_release_news(conn: Any, release_id: str, metadata: dict[str, Any], index: int) -> None:
    if index > 2:
        return
    existing = conn.execute(
        """
        SELECT 1
        FROM news_items
        WHERE source_type = 'npc_release'
          AND target_id = ?
        LIMIT 1
        """,
        (release_id,),
    ).fetchone()
    if existing:
        return
    title = f"{metadata['title']} 개봉"
    body = (
        f"{metadata.get('directorName')} 감독과 {', '.join(metadata.get('actorNames')[:2]) or '신인 배우진'}이 "
        f"{metadata.get('genreName')} 경쟁작으로 극장가에 합류했습니다."
    )
    year, month = _release_year_month(release_id)
    conn.execute(
        """
        INSERT INTO news_items (
            year, month, day, title, body, source_type, target_type,
            target_id, importance, reaction_json, effects_json
        ) VALUES (?, ?, ?, ?, ?, 'npc_release', 'film', ?, ?, ?, ?)
        """,
        (
            year,
            month,
            int(metadata.get("releaseDay") or 1),
            title,
            body,
            release_id,
            52 + index * 4,
            dumps_json(
                [
                    {"speaker": "관객", "text": "이번 주 선택지가 꽤 많아졌다."},
                    {"speaker": "배급 관계자", "text": "스크린 경쟁이 조금 더 치열해질 것 같다."},
                ]
            ),
            dumps_json({"market_competition": 3, "screen_access_pressure": 2}),
        ),
    )


def _person_market_score(stats: dict[str, int], person_type: str) -> float:
    if person_type == "director":
        return (
            stats.get("directing", 50) * 0.35
            + stats.get("commercialSense", 50) * 0.25
            + stats.get("auteurPower", 50) * 0.15
            + stats.get("genreControl", 50) * 0.25
        )
    return (
        stats.get("acting", 50) * 0.35
        + stats.get("ticketPower", 45) * 0.25
        + stats.get("brandPower", 45) * 0.25
        + stats.get("festivalPower", 35) * 0.15
    )


def _insert_career_entry_once(
    conn: Any,
    *,
    person_id: str,
    release_id: str,
    role: str,
    year: int,
    month: int,
    result: dict[str, Any],
) -> None:
    existing = conn.execute(
        """
        SELECT 1
        FROM people_career_timeline
        WHERE person_id = ? AND project_id = ? AND role = ?
        LIMIT 1
        """,
        (person_id, release_id, role),
    ).fetchone()
    if existing:
        return
    conn.execute(
        """
        INSERT INTO people_career_timeline (
            person_id, project_id, role, year, month, status, result_json
        ) VALUES (?, ?, ?, ?, ?, 'released', ?)
        """,
        (person_id, release_id, role, year, month, dumps_json(result)),
    )


def _release_year_month(release_id: str) -> tuple[int, int]:
    parts = str(release_id).split("_")
    return int(parts[2]), int(parts[3])


def _unique_title(
    rng: random.Random,
    genre_id: str,
    year: int,
    month: int,
    used_titles: set[str],
) -> str:
    pool = GENRE_TITLE_POOLS.get(genre_id) or ("새 영화", "겨울의 약속", "도시의 얼굴")
    for _ in range(20):
        title = rng.choice(pool)
        if title not in used_titles:
            used_titles.add(title)
            return title
    title = f"{rng.choice(pool)} {year % 100:02d}-{month:02d}"
    used_titles.add(title)
    return title


def _run_days_for_scale(scale_id: str) -> int:
    return {
        "scale_short": 7,
        "scale_independent": 14,
        "scale_low_budget_genre": 21,
        "scale_mid_commercial": 28,
        "scale_large_commercial": 35,
        "scale_tentpole": 42,
    }.get(scale_id, 28)


def _audience_band(expected_audience: int) -> str:
    if expected_audience >= 5_000_000:
        return "대형 흥행권"
    if expected_audience >= 2_000_000:
        return "상업영화 흥행권"
    if expected_audience >= 700_000:
        return "중간 흥행권"
    if expected_audience >= 150_000:
        return "제한 흥행권"
    return "소규모 개봉권"


def _era_key(year: int) -> str:
    if year < 1990:
        return "1980s"
    if year < 2000:
        return "1990s"
    if year < 2010:
        return "2000s"
    if year < 2020:
        return "2010s"
    return "2020s"


def _weighted_choice(rng: random.Random, weighted: list[tuple[Any, float]]) -> Any:
    if not weighted:
        return None
    total = sum(max(0.0, weight) for _, weight in weighted)
    if total <= 0:
        return weighted[0][0]
    cursor = rng.uniform(0, total)
    seen = 0.0
    for item, weight in weighted:
        seen += max(0.0, weight)
        if cursor <= seen:
            return item
    return weighted[-1][0]
