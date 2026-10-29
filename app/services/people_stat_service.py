from __future__ import annotations

from collections import defaultdict
from typing import Any

from app.database import dumps_json, get_connection, loads_json


ACTOR_STAT_KEYS = (
    "acting",
    "ticketPower",
    "festivalPower",
    "brandPower",
    "globalRecognition",
    "costLevel",
    "scheduleDifficulty",
    "growthPotential",
)

DIRECTOR_STAT_KEYS = (
    "directing",
    "screenplay",
    "commercialSense",
    "auteurPower",
    "genreControl",
    "budgetControl",
    "festivalPower",
    "globalRecognition",
    "costLevel",
    "scheduleDifficulty",
    "growthPotential",
)

GENRE_IDS = {
    "crime_thriller": "genre_crime_thriller",
    "action": "genre_action",
    "horror_occult": "genre_horror_occult",
    "romance_melodrama": "genre_romance_melodrama",
    "comedy": "genre_comedy",
    "family_human_drama": "genre_family_human_drama",
    "period_historical": "genre_period_historical",
    "social_true_story": "genre_social_true_story",
    "indie_art": "genre_indie_art",
    "sf_disaster_monster": "genre_sf_disaster_monster",
    "fantasy": "genre_fantasy",
    "animation": "genre_animation",
}

GENRE_TAG_ALIASES = {
    "crime": "genre_crime_thriller",
    "crime_thriller": "genre_crime_thriller",
    "thriller": "genre_crime_thriller",
    "noir": "genre_crime_thriller",
    "mystery": "genre_crime_thriller",
    "black_comedy": "genre_comedy",
    "comedy": "genre_comedy",
    "action": "genre_action",
    "war": "genre_action",
    "horror": "genre_horror_occult",
    "horror_occult": "genre_horror_occult",
    "occult": "genre_horror_occult",
    "romance": "genre_romance_melodrama",
    "melodrama": "genre_romance_melodrama",
    "romance_melodrama": "genre_romance_melodrama",
    "drama": "genre_family_human_drama",
    "family_human_drama": "genre_family_human_drama",
    "historical": "genre_period_historical",
    "period_historical": "genre_period_historical",
    "social_true_story": "genre_social_true_story",
    "indie_art": "genre_indie_art",
    "monster": "genre_sf_disaster_monster",
    "sf": "genre_sf_disaster_monster",
    "sf_disaster_monster": "genre_sf_disaster_monster",
    "fantasy": "genre_fantasy",
    "animation": "genre_animation",
}

ACTOR_TIER_BASE = {
    "legend": {"acting": 90, "ticketPower": 85, "festivalPower": 85, "brandPower": 90, "globalRecognition": 70, "costLevel": 90, "growthPotential": 70},
    "top_star": {"acting": 80, "ticketPower": 90, "festivalPower": 65, "brandPower": 90, "globalRecognition": 60, "costLevel": 90, "growthPotential": 75},
    "a_list": {"acting": 75, "ticketPower": 75, "festivalPower": 60, "brandPower": 75, "globalRecognition": 45, "costLevel": 75, "growthPotential": 75},
    "solid_lead": {"acting": 70, "ticketPower": 60, "festivalPower": 50, "brandPower": 60, "globalRecognition": 35, "costLevel": 60, "growthPotential": 70},
    "character_actor": {"acting": 78, "ticketPower": 45, "festivalPower": 55, "brandPower": 55, "globalRecognition": 30, "costLevel": 50, "growthPotential": 65},
    "rising": {"acting": 60, "ticketPower": 35, "festivalPower": 40, "brandPower": 45, "globalRecognition": 25, "costLevel": 40, "growthPotential": 85},
    "newcomer": {"acting": 45, "ticketPower": 20, "festivalPower": 25, "brandPower": 25, "globalRecognition": 15, "costLevel": 20, "growthPotential": 90},
    "veteran": {"acting": 82, "ticketPower": 50, "festivalPower": 65, "brandPower": 65, "globalRecognition": 35, "costLevel": 55, "growthPotential": 40},
}

DIRECTOR_TIER_BASE = {
    "legend": {"directing": 92, "screenplay": 85, "commercialSense": 75, "auteurPower": 90, "genreControl": 82, "budgetControl": 75, "festivalPower": 90, "globalRecognition": 80, "growthPotential": 55},
    "global_auteur": {"directing": 95, "screenplay": 90, "commercialSense": 75, "auteurPower": 98, "genreControl": 88, "budgetControl": 70, "festivalPower": 100, "globalRecognition": 100, "growthPotential": 50},
    "commercial_master": {"directing": 85, "screenplay": 75, "commercialSense": 95, "auteurPower": 60, "genreControl": 82, "budgetControl": 80, "festivalPower": 55, "globalRecognition": 60, "growthPotential": 55},
    "auteur": {"directing": 85, "screenplay": 85, "commercialSense": 45, "auteurPower": 90, "genreControl": 75, "budgetControl": 60, "festivalPower": 80, "globalRecognition": 60, "growthPotential": 55},
    "genre_master": {"directing": 82, "screenplay": 75, "commercialSense": 75, "auteurPower": 70, "genreControl": 86, "budgetControl": 70, "festivalPower": 60, "globalRecognition": 55, "growthPotential": 60},
    "solid_commercial": {"directing": 75, "screenplay": 65, "commercialSense": 80, "auteurPower": 45, "genreControl": 70, "budgetControl": 75, "festivalPower": 40, "globalRecognition": 40, "growthPotential": 60},
    "indie_festival": {"directing": 70, "screenplay": 75, "commercialSense": 35, "auteurPower": 80, "genreControl": 65, "budgetControl": 60, "festivalPower": 75, "globalRecognition": 45, "growthPotential": 70},
    "rising_director": {"directing": 60, "screenplay": 65, "commercialSense": 45, "auteurPower": 60, "genreControl": 58, "budgetControl": 50, "festivalPower": 45, "globalRecognition": 30, "growthPotential": 85},
    "veteran": {"directing": 82, "screenplay": 75, "commercialSense": 60, "auteurPower": 75, "genreControl": 72, "budgetControl": 70, "festivalPower": 70, "globalRecognition": 50, "growthPotential": 40},
}

ACTOR_TAG_MODIFIERS = {
    "연기파": {"acting": 10, "festivalPower": 5},
    "국민배우": {"brandPower": 10, "ticketPower": 5},
    "티켓파워형": {"ticketPower": 15, "costLevel": 10},
    "영화제형": {"festivalPower": 15, "globalRecognition": 5},
    "글로벌형": {"globalRecognition": 15},
    "신스틸러": {"acting": 8, "ticketPower": -5},
    "팬덤형": {"brandPower": 10},
    "성장형": {"growthPotential": 15},
    "브랜드형": {"brandPower": 10},
}

DIRECTOR_TAG_MODIFIERS = {
    "작가주의": {"auteurPower": 15, "festivalPower": 10},
    "상업성": {"commercialSense": 15},
    "글로벌": {"globalRecognition": 20},
    "장르혼합": {"genreControl": 10},
    "액션전문": {"genreControl": 6, "budgetControl": 4},
    "범죄스릴러": {"genreControl": 6},
    "오컬트": {"genreControl": 6, "auteurPower": 4},
    "코미디": {"commercialSense": 5},
    "사극": {"budgetControl": 5, "genreControl": 6},
    "VFX/블록버스터": {"budgetControl": 5, "commercialSense": 5},
    "독립영화": {"festivalPower": 10, "commercialSense": -5},
    "앙상블": {"directing": 3, "genreControl": 4},
    "케이퍼": {"commercialSense": 4, "genreControl": 4},
    "범죄오락": {"commercialSense": 4, "genreControl": 4},
    "영화제형": {"festivalPower": 10},
}

ACTOR_TAG_GENRE_BONUSES = {
    "코미디형": {"genre_comedy": 20},
    "범죄액션형": {"genre_crime_thriller": 20, "genre_action": 20},
    "로맨스형": {"genre_romance_melodrama": 20},
    "신스틸러": {"genre_crime_thriller": 8, "genre_comedy": 8},
}

DIRECTOR_TAG_GENRE_BONUSES = {
    "액션전문": {"genre_action": 20},
    "범죄스릴러": {"genre_crime_thriller": 20},
    "오컬트": {"genre_horror_occult": 20},
    "코미디": {"genre_comedy": 20},
    "사극": {"genre_period_historical": 20},
    "VFX/블록버스터": {"genre_sf_disaster_monster": 20},
    "케이퍼": {"genre_crime_thriller": 12, "genre_comedy": 8},
    "범죄오락": {"genre_crime_thriller": 12, "genre_action": 8},
    "독립영화": {"genre_indie_art": 18},
}

GLOBAL_SIGNAL_TITLES = {
    "기생충",
    "설국열차",
    "옥자",
    "헤어질 결심",
    "미나리",
    "버닝",
    "올드보이",
    "아가씨",
    "부산행",
}


def estimate_and_store_people_stats() -> dict[str, int]:
    with get_connection() as conn:
        actor_metrics, director_metrics = _collect_metrics(conn)
        people = conn.execute(
            """
            SELECT *
            FROM people
            WHERE type IN ('actor', 'director')
            ORDER BY type, name_ko
            """
        ).fetchall()

        updated = {"actor": 0, "director": 0, "with_source_data": 0}
        for row in people:
            person = dict(row)
            person_type = person["type"]
            metrics = (actor_metrics if person_type == "actor" else director_metrics).get(person["name_ko"], {})
            source_stats = loads_json(person.get("current_stats_json"), {})
            source_potential = loads_json(person.get("potential_stats_json"), {})
            stat_profile = loads_json(person.get("stat_profile_json"), {})

            if person_type == "actor":
                current_stats = estimate_actor_stats(metrics, source_stats, stat_profile, person)
                potential_stats = estimate_actor_potential(metrics, current_stats, source_potential, person)
            else:
                current_stats = estimate_director_stats(metrics, source_stats, stat_profile, person)
                potential_stats = estimate_director_potential(metrics, current_stats, source_potential, person)

            genre_fit = _merge_genre_fit(
                loads_json(person.get("genre_fit_json"), {}),
                metrics.get("genre_counts", {}),
                stat_profile,
                person_type,
            )
            stat_profile = _updated_stat_profile(stat_profile, metrics)
            public_profile = _public_profile_for_stats(
                person_type,
                loads_json(person.get("public_profile_json"), {}),
                current_stats,
                potential_stats,
            )

            conn.execute(
                """
                UPDATE people
                SET current_stats_json = ?, potential_stats_json = ?,
                    genre_fit_json = ?, stat_profile_json = ?, public_profile_json = ?
                WHERE id = ?
                """,
                (
                    dumps_json(current_stats),
                    dumps_json(potential_stats),
                    dumps_json(genre_fit),
                    dumps_json(stat_profile),
                    dumps_json(public_profile),
                    person["id"],
                ),
            )
            profile_table = "people_actor_profiles" if person_type == "actor" else "people_director_profiles"
            conn.execute(
                f"""
                UPDATE {profile_table}
                SET current_stats_json = ?, potential_stats_json = ?,
                    genre_fit_json = ?, stat_profile_json = ?, public_profile_json = ?
                WHERE person_id = ?
                """,
                (
                    dumps_json(current_stats),
                    dumps_json(potential_stats),
                    dumps_json(genre_fit),
                    dumps_json(stat_profile),
                    dumps_json(public_profile),
                    person["id"],
                ),
            )
            updated[person_type] += 1
            if metrics:
                updated["with_source_data"] += 1
        conn.commit()
    return updated


def public_person_for_year(row: Any, year: int, month: int = 12) -> dict[str, Any]:
    person = dict(row)
    stats = effective_stats_for_year(person, year, month)
    potential = loads_json(person.get("potential_stats_json"), {})
    profile = _public_profile_for_stats(person["type"], loads_json(person.get("public_profile_json"), {}), stats, potential)
    activity = activity_stage_for_year(person, year, month)
    return {
        "id": person["id"],
        "name_ko": person["name_ko"],
        "name_en": person["name_en"],
        "type": person["type"],
        "one_line": profile.get("oneLine", "아직 공개 평가가 충분하지 않다."),
        "current_ability_text": profile.get("currentAbilityText", "현재 능력은 업계 자료를 더 확인해야 한다."),
        "potential_text": profile.get("potentialText", "성장 가능성은 작품 선택에 따라 달라질 수 있다."),
        "fame_text": profile.get("fameText", "명성 정보가 제한적이다."),
        "brand_text": profile.get("brandText", "브랜드 평판이 아직 뚜렷하지 않다."),
        "career_stage_label": activity["label"],
        "career_stage_text": activity["description"],
        "is_available": activity["isAvailable"],
    }


def activity_stage_for_year(
    person: dict[str, Any],
    year: int,
    month: int = 12,
    career_entries: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    available_from = int(person.get("available_from") or year)
    person_type = str(person.get("type") or "actor")
    if year < available_from:
        return {
            "label": "활동 전",
            "description": f"{available_from}년 이후부터 게임 내 캐스팅 후보로 등장한다.",
            "isAvailable": False,
        }
    status = str(person.get("status") or "active")
    if status == "deceased":
        return {
            "label": "캐스팅 불가",
            "description": "게임 내 현재 시점에는 새 프로젝트 계약을 맺을 수 없는 상태다.",
            "isAvailable": False,
        }
    context = career_context_for_person(person, year, month, career_entries)
    stats_profile = loads_json(person.get("stat_profile_json"), {})
    prime_eras = stats_profile.get("peakEras") or stats_profile.get("primeEras", [])
    first_prime_start = min((int(era.get("start", 9999)) for era in prime_eras), default=None)
    last_prime_end = max((int(era.get("end", -1)) for era in prime_eras), default=None)
    in_prime = any(int(era.get("start", 9999)) <= year <= int(era.get("end", -1)) for era in prime_eras)
    years_active = max(0, year - available_from)
    years_since_latest = context.get("yearsSinceLatest")
    released_count = int(context.get("releasedCount") or 0)
    hit_count = int(context.get("hitCount") or 0)
    major_hit_count = int(context.get("majorHitCount") or 0)
    birth_year = person.get("birth_year")
    age = year - int(birth_year) + 1 if birth_year else None

    if isinstance(age, int) and age >= 70 and person_type == "actor":
        return {
            "label": "원로/특별출연 중심",
            "description": "명성은 남아 있지만 장기 구속보다 특별출연이나 조연 활용이 현실적이다.",
            "isAvailable": status != "retired",
        }
    if isinstance(years_since_latest, int) and years_since_latest >= 10 and released_count > 0:
        return {
            "label": "활동 공백기",
            "description": "최근 필모그래피 공백이 길어 계약료와 스케줄 조건은 보수적으로 산정된다.",
            "isAvailable": status != "retired",
        }
    if in_prime:
        if major_hit_count or hit_count >= 2:
            label = "전성기/핵심 인물"
            desc = "게임 내 현재 시점의 필모그래피와 흥행 흐름상 프로젝트의 중심축으로 평가된다."
        else:
            label = "전성기/주요 활동기" if person_type == "actor" else "전성기/주요 감독"
            desc = "활동 흐름이 강해지는 시기라 캐스팅 기대치와 계약료가 함께 오른다."
        return {"label": label, "description": desc, "isAvailable": status != "retired"}
    if first_prime_start and year < first_prime_start:
        if years_active <= 4:
            label = "신인/활동 초기"
            desc = "아직 검증은 제한적이지만 잠재력과 조건 대비 효율을 보고 쓰는 시기다."
        else:
            label = "상승세"
            desc = "전성기 전 단계로, 좋은 배역이나 작품을 만나면 평가가 빠르게 달라질 수 있다."
        return {"label": label, "description": desc, "isAvailable": True}
    if last_prime_end and year > last_prime_end:
        if person_type == "director":
            label = "브랜드 안정기"
            desc = "이미 쌓인 필모그래피가 계약 조건을 만들지만, 작품 선택과 제작 규모 궁합을 더 따진다."
        else:
            label = "안정기/주요 배우"
            desc = "대중적 이미지는 남아 있고, 배역 비중과 장르 궁합에 따라 활용도가 갈린다."
        return {"label": label, "description": desc, "isAvailable": status != "retired"}
    if years_active <= 4:
        return {
            "label": "신인/활동 초기",
            "description": "게임 내 공개 필모그래피가 많지 않아 잠재력과 배역 궁합 중심으로 판단해야 한다.",
            "isAvailable": True,
        }
    if released_count >= 6 or hit_count:
        return {
            "label": "주요 활동기",
            "description": "필모그래피가 쌓이며 업계 평가와 계약 조건이 본격적으로 형성된 시기다.",
            "isAvailable": status != "retired",
        }
    return {
        "label": "검증 중",
        "description": "활동은 가능하지만 아직 대표 필모그래피와 시장 반응이 충분히 쌓이지 않았다.",
        "isAvailable": status != "retired",
    }


def effective_stats_for_year(
    person: dict[str, Any],
    year: int,
    month: int = 12,
    career_entries: list[dict[str, Any]] | None = None,
) -> dict[str, int]:
    stats = {key: _to_int(value, 50) for key, value in loads_json(person.get("current_stats_json"), {}).items()}
    stat_profile = loads_json(person.get("stat_profile_json"), {})
    stat_keys = DIRECTOR_STAT_KEYS if person.get("type") == "director" else ACTOR_STAT_KEYS
    for key in stat_keys:
        stats.setdefault(key, 50)
    available_from = int(person.get("available_from") or year)
    birth_year = person.get("birth_year")

    if year < available_from:
        years_before = min(15, available_from - year)
        for key in stats:
            stats[key] = clamp(stats[key] - 2 * years_before)
        if "growthPotential" in stats:
            stats["growthPotential"] = clamp(stats["growthPotential"] + years_before)

    prime_eras = stat_profile.get("peakEras") or stat_profile.get("primeEras", [])
    prime_starts = [int(era.get("start", 9999)) for era in prime_eras]
    prime_ends = [int(era.get("end", -1)) for era in prime_eras]
    first_prime_start = min(prime_starts) if prime_starts else None
    last_prime_end = max(prime_ends) if prime_ends else None
    if first_prime_start and year < first_prime_start:
        early_gap = min(8, first_prime_start - year)
        for key in stats:
            if key != "growthPotential":
                stats[key] = clamp(stats[key] - (8 + early_gap * 2))
        if "growthPotential" in stats:
            stats["growthPotential"] = clamp(stats["growthPotential"] + 12)
    elif last_prime_end and year > last_prime_end + 4:
        late_gap = min(10, year - last_prime_end)
        for key in ("ticketPower", "commercialSense", "brandPower", "costLevel", "scheduleDifficulty"):
            if key in stats:
                stats[key] = clamp(stats[key] - late_gap)

    for era in prime_eras:
        if int(era.get("start", 9999)) <= year <= int(era.get("end", -1)):
            for key, multiplier in (era.get("modifiers") or {}).items():
                if key in stats:
                    stats[key] = clamp(stats[key] * float(multiplier))

    if birth_year:
        age = year - int(birth_year)
        if age >= 58:
            for key in ("ticketPower", "costLevel", "scheduleDifficulty"):
                if key in stats:
                    stats[key] = clamp(stats[key] - 4)
        elif age <= 30 and "growthPotential" in stats:
            stats["growthPotential"] = clamp(stats["growthPotential"] + 6)
    career_context = career_context_for_person(person, year, month, career_entries)
    _apply_career_context(stats, person, career_context)
    return stats


def contribution_stats_for_project(person: dict[str, Any], role: str, year: int) -> dict[str, int]:
    stats = effective_stats_for_year(person, year)
    if role in {"lead_actor", "supporting_actor", "cameo_actor", "minor_actor", "day_player", "background_actor", "actor"}:
        acting = stats.get("acting", stats.get("acting_quality", 55))
        casting_fit = max(acting, stats.get("brandPower", acting))
        pre_interest = max(stats.get("ticketPower", 45), stats.get("brandPower", 45), stats.get("globalRecognition", 30))
        if role == "cameo_actor":
            return {
                "acting_quality": int(acting * 0.45 + 42 * 0.55),
                "casting_fit": int(casting_fit * 0.5 + 45 * 0.5),
                "pre_release_interest": int(pre_interest * 0.55 + 35 * 0.45),
            }
        if role in {"minor_actor", "day_player", "background_actor"}:
            weight = {"minor_actor": 0.28, "day_player": 0.15, "background_actor": 0.08}.get(role, 0.12)
            return {
                "acting_quality": int(44 + (acting - 44) * weight),
                "casting_fit": int(45 + (casting_fit - 45) * weight),
                "pre_release_interest": 0,
            }
        return {
            "acting_quality": int(acting),
            "casting_fit": int(casting_fit),
            "pre_release_interest": int(pre_interest),
        }
    if role in {"director", "main_director"}:
        directing = stats.get("directing", stats.get("directing_quality", 55))
        return {
            "directing_quality": int(directing),
            "field_control": int(max(stats.get("genreControl", 50), stats.get("budgetControl", 50))),
            "artistic_sense": int(max(stats.get("auteurPower", directing), stats.get("festivalPower", 40))),
        }
    return {key: int(value) for key, value in stats.items() if isinstance(value, int | float)}


def career_context_for_person(
    person: dict[str, Any],
    year: int,
    month: int = 12,
    career_entries: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    entries = career_entries if career_entries is not None else _career_entries_until(person, year, month)
    occurred = [_normalize_career_entry(entry) for entry in entries]
    occurred = [entry for entry in occurred if _career_entry_occurred(entry, year, month)]
    occurred = _dedupe_career_entries(occurred)
    if person.get("type") == "director":
        occurred = [entry for entry in occurred if str(entry.get("role") or "director") in {"director", "main_director"}]

    released_count = len(occurred)
    latest_year = max((entry["year"] for entry in occurred if isinstance(entry.get("year"), int)), default=None)
    recent_count = sum(1 for entry in occurred if isinstance(entry.get("year"), int) and year - int(entry["year"]) <= 4)
    hit_count = 0
    major_hit_count = 0
    best_audience = 0
    festival_signal_count = 0
    global_signal_count = 0
    for entry in occurred:
        audience = _career_audience(entry)
        best_audience = max(best_audience, audience)
        if audience >= 1_000_000:
            hit_count += 1
        if audience >= 5_000_000:
            major_hit_count += 1
        title = str(entry.get("title") or "")
        source = str(entry.get("source") or "")
        awards = entry.get("awards") if isinstance(entry.get("awards"), list) else []
        summary = str(entry.get("summary") or "")
        if title in GLOBAL_SIGNAL_TITLES or awards or "영화제" in summary or "수상" in summary:
            festival_signal_count += 1
        if title in GLOBAL_SIGNAL_TITLES or "Wikidata" in source or "global" in summary.lower():
            global_signal_count += 1

    available_from = int(person.get("available_from") or year)
    first_year = min((entry["year"] for entry in occurred if isinstance(entry.get("year"), int)), default=None)
    years_since_latest = year - latest_year if isinstance(latest_year, int) else None
    return {
        "entries": occurred,
        "releasedCount": released_count,
        "recentCount": recent_count,
        "hitCount": hit_count,
        "majorHitCount": major_hit_count,
        "bestAudience": best_audience,
        "bestAudienceMillion": best_audience / 1_000_000,
        "festivalSignalCount": festival_signal_count,
        "globalSignalCount": global_signal_count,
        "latestYear": latest_year,
        "firstYear": first_year,
        "yearsSinceLatest": years_since_latest,
        "preBreakout": released_count == 0 and year <= available_from + 2,
    }


def _career_entries_until(person: dict[str, Any], year: int, month: int) -> list[dict[str, Any]]:
    person_id = str(person.get("id") or "")
    if not person_id:
        return []
    entries: list[dict[str, Any]] = []
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT pct.*, COALESCE(c.title, p.title, m.title, mh.title, mp.title) AS joined_title
            FROM people_career_timeline pct
            LEFT JOIN completed_films c ON c.id = pct.project_id
            LEFT JOIN projects p ON p.id = pct.project_id
            LEFT JOIN movies m ON m.id = pct.project_id
            LEFT JOIN movies_historical mh ON mh.id = pct.project_id
            LEFT JOIN movies_player_created mp ON mp.id = pct.project_id
            WHERE pct.person_id = ?
              AND pct.status IN ('released', 'completed', 'awarded', 'reviewed')
              AND (
                pct.year < ?
                OR (pct.year = ? AND COALESCE(pct.month, 12) <= ?)
                OR pct.year IS NULL
              )
            ORDER BY COALESCE(pct.year, 9999), COALESCE(pct.month, 12), pct.id
            """,
            (person_id, year, year, month),
        ).fetchall()
        for row in rows:
            payload = loads_json(row["result_json"], {})
            if not isinstance(payload, dict):
                payload = {}
            entries.append(
                {
                    **payload,
                    "title": row["joined_title"] or payload.get("title"),
                    "year": row["year"],
                    "month": row["month"],
                    "role": row["role"],
                    "status": row["status"],
                    "source": payload.get("source"),
                }
            )
        if person.get("type") == "director":
            protected_rows = conn.execute(
                """
                SELECT title, release_year, release_month, metadata_json
                FROM history_protected_director_films
                WHERE director_id = ?
                  AND (
                    release_year < ?
                    OR (release_year = ? AND COALESCE(release_month, 12) <= ?)
                  )
                ORDER BY release_year, COALESCE(release_month, 12), title
                """,
                (person_id, year, year, month),
            ).fetchall()
            for row in protected_rows:
                metadata = loads_json(row["metadata_json"], {})
                entries.append(
                    {
                        **metadata,
                        "title": row["title"],
                        "year": row["release_year"],
                        "month": row["release_month"],
                        "role": "director",
                        "status": "released",
                        "source": "history_protected_director_films",
                        "summary": "주요 필모그래피",
                    }
                )
    return entries


def _dedupe_career_entries(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    seen: set[tuple[str, int | None, str]] = set()
    for entry in entries:
        key = (
            str(entry.get("title") or "").strip(),
            entry.get("year") if isinstance(entry.get("year"), int) else None,
            str(entry.get("role") or ""),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(entry)
    return deduped


def _normalize_career_entry(entry: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(entry)
    result = normalized.get("result")
    if isinstance(result, dict):
        normalized.update({key: value for key, value in result.items() if key not in normalized})
    normalized["year"] = _to_optional_int(
        normalized.get("year") or normalized.get("releaseYear") or normalized.get("release_year")
    )
    normalized["month"] = _to_optional_int(
        normalized.get("month") or normalized.get("releaseMonth") or normalized.get("release_month")
    )
    return normalized


def _career_entry_occurred(entry: dict[str, Any], year: int, month: int) -> bool:
    entry_year = entry.get("year")
    if not isinstance(entry_year, int):
        return True
    if entry_year < year:
        return True
    if entry_year > year:
        return False
    return int(entry.get("month") or 12) <= month


def _career_audience(entry: dict[str, Any]) -> int:
    keys = (
        "finalAudience",
        "final_audience",
        "audience",
        "expectedAudience",
        "expected_audience",
        "totalAudience",
        "total_audience",
    )
    for key in keys:
        value = entry.get(key)
        parsed = _to_optional_int(value)
        if parsed is not None:
            return max(0, parsed)
    return 0


def _apply_career_context(stats: dict[str, int], person: dict[str, Any], context: dict[str, Any]) -> None:
    released_count = int(context.get("releasedCount") or 0)
    recent_count = int(context.get("recentCount") or 0)
    hit_count = int(context.get("hitCount") or 0)
    major_hit_count = int(context.get("majorHitCount") or 0)
    festival_count = int(context.get("festivalSignalCount") or 0)
    global_count = int(context.get("globalSignalCount") or 0)
    best_million = float(context.get("bestAudienceMillion") or 0)
    years_since_latest = context.get("yearsSinceLatest")

    if person.get("type") == "director":
        _add_stat(stats, "directing", min(12, released_count * 0.7 + festival_count * 2.0))
        _add_stat(stats, "screenplay", min(8, released_count * 0.4 + festival_count * 1.0))
        _add_stat(stats, "commercialSense", min(18, hit_count * 2.0 + major_hit_count * 3.0 + best_million * 0.65))
        _add_stat(stats, "auteurPower", min(14, festival_count * 2.5 + global_count * 1.5))
        _add_stat(stats, "festivalPower", min(18, festival_count * 3.0 + global_count * 1.5))
        _add_stat(stats, "globalRecognition", min(22, global_count * 4.0 + major_hit_count * 1.5))
        _add_stat(stats, "budgetControl", min(9, released_count * 0.5 + hit_count * 0.8))
        _add_stat(stats, "costLevel", min(20, hit_count * 1.4 + major_hit_count * 2.8 + global_count * 2.5 + recent_count * 0.8))
        _add_stat(stats, "scheduleDifficulty", min(18, hit_count * 1.2 + major_hit_count * 2.2 + global_count * 2.0 + recent_count * 0.9))
    else:
        _add_stat(stats, "acting", min(12, released_count * 0.35 + festival_count * 2.0 + global_count * 1.0))
        _add_stat(stats, "ticketPower", min(20, hit_count * 1.8 + major_hit_count * 3.0 + best_million * 0.75))
        _add_stat(stats, "brandPower", min(18, hit_count * 1.5 + major_hit_count * 2.5 + global_count * 2.0 + recent_count * 0.7))
        _add_stat(stats, "festivalPower", min(16, festival_count * 2.6 + global_count * 1.2))
        _add_stat(stats, "globalRecognition", min(20, global_count * 4.5 + major_hit_count * 1.2))
        _add_stat(stats, "costLevel", min(18, hit_count * 1.3 + major_hit_count * 2.5 + global_count * 2.0 + recent_count * 0.8))
        _add_stat(stats, "scheduleDifficulty", min(18, hit_count * 1.1 + major_hit_count * 2.1 + global_count * 2.0 + recent_count * 0.9))

    if released_count == 0:
        for key in ("ticketPower", "brandPower", "costLevel", "scheduleDifficulty", "commercialSense", "globalRecognition"):
            if key in stats:
                stats[key] = clamp(stats[key] - 10)
        if "growthPotential" in stats:
            stats["growthPotential"] = clamp(stats["growthPotential"] + 10)
    elif isinstance(years_since_latest, int):
        if years_since_latest >= 10:
            penalty = min(18, years_since_latest - 4)
            for key in ("ticketPower", "brandPower", "commercialSense", "costLevel", "scheduleDifficulty"):
                if key in stats:
                    stats[key] = clamp(stats[key] - penalty)
        elif years_since_latest <= 2:
            for key in ("brandPower", "ticketPower", "commercialSense", "scheduleDifficulty"):
                if key in stats:
                    stats[key] = clamp(stats[key] + 4)


def _add_stat(stats: dict[str, int], key: str, value: float) -> None:
    if key in stats:
        stats[key] = clamp(stats[key] + value)


def _to_optional_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(float(str(value).replace(",", "")))
    except (TypeError, ValueError):
        return None


def ability_text(value: int | float, field: str) -> str:
    label = _field_label(field)
    score = int(value)
    if score >= 90:
        return f"{label}은 해당 시대를 대표하는 수준으로 평가된다."
    if score >= 75:
        return f"{label}은 업계 상위권 역량을 가진 것으로 평가된다."
    if score >= 60:
        return f"{label}은 안정적인 업계 수준으로 평가된다."
    if score >= 40:
        return f"{label}은 기본기는 있으나 아직 검증이 더 필요하다."
    if score >= 20:
        return f"{label}은 가능성은 있으나 불안정하다."
    return f"{label}은 아직 뚜렷하게 검증되지 않았다."


def _legacy_actor_estimate(
    metrics: dict[str, Any],
    seed_stats: dict[str, Any],
    person: dict[str, Any],
) -> dict[str, int]:
    appearances = int(metrics.get("appearances", 0))
    lead_hits = int(metrics.get("lead_hit_count", 0))
    support_hits = int(metrics.get("supporting_hit_count", 0))
    avg_lead = float(metrics.get("avg_lead_audience_million", 0.0))
    genre_diversity = int(metrics.get("genre_diversity_score", 0))
    recent_hits = int(metrics.get("recent_public_hits", 0))
    best_million = float(metrics.get("best_audience", 0)) / 1_000_000
    global_projects = int(metrics.get("global_signal_count", 0))

    acting = 45 + appearances * 0.45 + genre_diversity * 2.0 + min(25, _activity_span(person, metrics)) * 0.45
    ticket_power = 30 + lead_hits * 8 + support_hits * 3 + avg_lead * 4 + recent_hits * 4
    festival_power = 20 + int(metrics.get("auteur_collaboration_count", 0)) * 4 + genre_diversity * 1.2
    brand_power = 30 + (lead_hits + support_hits) * 3 + best_million * 1.4 + recent_hits * 5
    global_recognition = 10 + global_projects * 9 + int(metrics.get("foreign_market_signal", 0)) * 5
    return {
        "acting": _best_seed(seed_stats, "acting", "acting_quality", acting),
        "ticketPower": _best_seed(seed_stats, "ticketPower", "ticket_power", ticket_power),
        "festivalPower": _best_seed(seed_stats, "festivalPower", "festival_power", festival_power),
        "brandPower": _best_seed(seed_stats, "brandPower", "public_reputation", brand_power),
        "globalRecognition": _best_seed(seed_stats, "globalRecognition", "global_reputation", global_recognition),
    }


def _legacy_director_estimate(
    metrics: dict[str, Any],
    seed_stats: dict[str, Any],
    person: dict[str, Any],
) -> dict[str, int]:
    films = int(metrics.get("film_count", 0))
    hit_films = int(metrics.get("hit_films", 0))
    avg_audience = float(metrics.get("avg_audience_million", 0.0))
    genre_diversity = int(metrics.get("genre_diversity_score", 0))
    best_million = float(metrics.get("best_audience", 0)) / 1_000_000
    global_projects = int(metrics.get("global_signal_count", 0))

    directing = 45 + films * 2.1 + genre_diversity * 2.0 + best_million * 1.2
    screenplay = 40 + films * 1.2 + genre_diversity * 1.5
    commercial_sense = 30 + hit_films * 8 + avg_audience * 3 + best_million * 1.4
    auteur_power = 30 + genre_diversity * 2.5 + int(metrics.get("critic_discourse_signal", 0)) * 5
    festival_power = 20 + int(metrics.get("auteur_collaboration_count", 0)) * 5 + global_projects * 5
    global_recognition = 10 + global_projects * 10 + int(metrics.get("foreign_market_signal", 0)) * 4
    return {
        "directing": _best_seed(seed_stats, "directing", "directing_quality", directing),
        "screenplay": _best_seed(seed_stats, "screenplay", "screenplay_sense", screenplay),
        "commercialSense": _best_seed(seed_stats, "commercialSense", "commercial_sense", commercial_sense),
        "auteurPower": _best_seed(seed_stats, "auteurPower", "artistic_sense", auteur_power),
        "genreControl": _best_seed(seed_stats, "genreControl", "field_control", 45 + genre_diversity * 4 + films * 1.4),
        "budgetControl": _best_seed(seed_stats, "budgetControl", "field_control", 45 + hit_films * 4 + films * 0.9),
        "festivalPower": _best_seed(seed_stats, "festivalPower", "critic_reputation", festival_power),
        "globalRecognition": _best_seed(seed_stats, "globalRecognition", "global_reputation", global_recognition),
    }


def _apply_actor_metric_adjustments(stats: dict[str, Any], metrics: dict[str, Any], person: dict[str, Any]) -> None:
    appearances = int(metrics.get("appearances", 0))
    lead_hits = int(metrics.get("lead_hit_count", 0))
    support_hits = int(metrics.get("supporting_hit_count", 0))
    avg_lead = float(metrics.get("avg_lead_audience_million", 0.0))
    genre_diversity = int(metrics.get("genre_diversity_score", 0))
    recent_hits = int(metrics.get("recent_public_hits", 0))
    best_million = float(metrics.get("best_audience", 0)) / 1_000_000
    global_projects = int(metrics.get("global_signal_count", 0))
    active_span = _activity_span(person, metrics)

    stats["acting"] = clamp(stats.get("acting", 50) + min(10, appearances * 0.18 + genre_diversity * 0.8 + active_span * 0.08))
    stats["ticketPower"] = clamp(stats.get("ticketPower", 40) + min(15, lead_hits * 2.2 + support_hits * 0.8 + avg_lead * 0.8 + recent_hits * 1.5))
    stats["festivalPower"] = clamp(stats.get("festivalPower", 35) + min(10, int(metrics.get("auteur_collaboration_count", 0)) * 1.5 + genre_diversity * 0.7))
    stats["brandPower"] = clamp(stats.get("brandPower", 40) + min(12, (lead_hits + support_hits) * 1.1 + best_million * 0.6 + recent_hits * 2))
    stats["globalRecognition"] = clamp(stats.get("globalRecognition", 25) + min(12, global_projects * 5 + int(metrics.get("foreign_market_signal", 0)) * 3))


def _apply_director_metric_adjustments(stats: dict[str, Any], metrics: dict[str, Any]) -> None:
    films = int(metrics.get("film_count", 0))
    hit_films = int(metrics.get("hit_films", 0))
    avg_audience = float(metrics.get("avg_audience_million", 0.0))
    genre_diversity = int(metrics.get("genre_diversity_score", 0))
    best_million = float(metrics.get("best_audience", 0)) / 1_000_000
    global_projects = int(metrics.get("global_signal_count", 0))

    stats["directing"] = clamp(stats.get("directing", 50) + min(10, films * 0.8 + genre_diversity * 0.8 + best_million * 0.35))
    stats["screenplay"] = clamp(stats.get("screenplay", 45) + min(8, films * 0.4 + genre_diversity * 0.8))
    stats["commercialSense"] = clamp(stats.get("commercialSense", 40) + min(15, hit_films * 2.2 + avg_audience * 0.8 + best_million * 0.45))
    stats["auteurPower"] = clamp(stats.get("auteurPower", 40) + min(10, genre_diversity * 0.8 + int(metrics.get("critic_discourse_signal", 0)) * 2))
    stats["genreControl"] = clamp(stats.get("genreControl", 45) + min(10, genre_diversity * 1.2 + films * 0.35))
    stats["budgetControl"] = clamp(stats.get("budgetControl", 45) + min(10, hit_films * 1.4 + films * 0.3))
    stats["festivalPower"] = clamp(stats.get("festivalPower", 35) + min(10, int(metrics.get("auteur_collaboration_count", 0)) * 2 + global_projects * 3))
    stats["globalRecognition"] = clamp(stats.get("globalRecognition", 25) + min(12, global_projects * 5 + int(metrics.get("foreign_market_signal", 0)) * 2))


def estimate_actor_stats(
    metrics: dict[str, Any],
    seed_stats: dict[str, Any],
    stat_profile: dict[str, Any],
    person: dict[str, Any],
) -> dict[str, int]:
    tier = stat_profile.get("tier")
    if tier:
        stats = dict(ACTOR_TIER_BASE.get(str(tier), ACTOR_TIER_BASE["solid_lead"]))
        _apply_named_modifiers(stats, stat_profile.get("roleType", []), ACTOR_TAG_MODIFIERS)
        _apply_actor_metric_adjustments(stats, metrics, person)
    else:
        stats = _legacy_actor_estimate(metrics, seed_stats, person)

    _apply_manual(stats, stat_profile.get("manualStatAdjustments") or {})
    recent_hits = int(metrics.get("recent_public_hits", 0))
    stats["costLevel"] = clamp(max(
        stats.get("costLevel", 0),
        stats.get("ticketPower", 45) * 0.35 + stats.get("brandPower", 45) * 0.35 + recent_hits * 4,
    ))
    protected_bonus = 8 if person.get("protection_level") not in {None, "none", "fictional"} else 0
    stats["scheduleDifficulty"] = clamp(stats["brandPower"] * 0.35 + stats["costLevel"] * 0.25 + protected_bonus)
    if "growthPotential" not in stats:
        stats["growthPotential"] = _growth_potential(person, stats, seed_stats)
    _apply_manual_override(stats, stat_profile, ACTOR_STAT_KEYS)
    return clamp_all(stats, ACTOR_STAT_KEYS)


def estimate_actor_potential(
    metrics: dict[str, Any],
    current_stats: dict[str, int],
    seed_potential: dict[str, Any],
    person: dict[str, Any],
) -> dict[str, int]:
    growth = current_stats.get("growthPotential", 55)
    return clamp_all(
        {
            "acting": max(current_stats["acting"], _to_int(seed_potential.get("acting"), current_stats["acting"]) + 2),
            "ticketPower": max(current_stats["ticketPower"], current_stats["ticketPower"] + growth * 0.08),
            "festivalPower": max(current_stats["festivalPower"], current_stats["festivalPower"] + growth * 0.06),
            "brandPower": max(current_stats["brandPower"], current_stats["brandPower"] + growth * 0.06),
            "globalRecognition": max(current_stats["globalRecognition"], current_stats["globalRecognition"] + growth * 0.08),
            "growthPotential": growth,
        },
        ("acting", "ticketPower", "festivalPower", "brandPower", "globalRecognition", "growthPotential"),
    )


def estimate_director_stats(
    metrics: dict[str, Any],
    seed_stats: dict[str, Any],
    stat_profile: dict[str, Any],
    person: dict[str, Any],
) -> dict[str, int]:
    tier = stat_profile.get("tier")
    if tier:
        stats = dict(DIRECTOR_TIER_BASE.get(str(tier), DIRECTOR_TIER_BASE["solid_commercial"]))
        _apply_named_modifiers(stats, stat_profile.get("directorType", []), DIRECTOR_TAG_MODIFIERS)
        _apply_director_metric_adjustments(stats, metrics)
    else:
        stats = _legacy_director_estimate(metrics, seed_stats, person)

    _apply_manual(stats, stat_profile.get("manualStatAdjustments") or {})
    stats["costLevel"] = clamp(max(
        stats.get("costLevel", 0),
        stats.get("commercialSense", 45) * 0.35
        + stats.get("auteurPower", 45) * 0.20
        + stats.get("globalRecognition", 35) * 0.20,
    ))
    protected_bonus = 10 if person.get("protection_level") not in {None, "none", "fictional"} else 0
    stats["scheduleDifficulty"] = clamp(stats["costLevel"] * 0.35 + stats["globalRecognition"] * 0.25 + protected_bonus)
    if "growthPotential" not in stats:
        stats["growthPotential"] = _growth_potential(person, stats, seed_stats)
    _apply_manual_override(stats, stat_profile, DIRECTOR_STAT_KEYS)
    return clamp_all(stats, DIRECTOR_STAT_KEYS)


def estimate_director_potential(
    metrics: dict[str, Any],
    current_stats: dict[str, int],
    seed_potential: dict[str, Any],
    person: dict[str, Any],
) -> dict[str, int]:
    growth = current_stats.get("growthPotential", 55)
    return clamp_all(
        {
            "directing": max(current_stats["directing"], _to_int(seed_potential.get("directing"), current_stats["directing"]) + 2),
            "screenplay": max(current_stats["screenplay"], current_stats["screenplay"] + growth * 0.06),
            "commercialSense": max(current_stats["commercialSense"], current_stats["commercialSense"] + growth * 0.08),
            "auteurPower": max(current_stats["auteurPower"], current_stats["auteurPower"] + growth * 0.07),
            "genreControl": max(current_stats["genreControl"], current_stats["genreControl"] + growth * 0.06),
            "budgetControl": max(current_stats["budgetControl"], current_stats["budgetControl"] + growth * 0.05),
            "festivalPower": max(current_stats["festivalPower"], current_stats["festivalPower"] + growth * 0.06),
            "globalRecognition": max(current_stats["globalRecognition"], current_stats["globalRecognition"] + growth * 0.08),
            "growthPotential": growth,
        },
        (
            "directing",
            "screenplay",
            "commercialSense",
            "auteurPower",
            "genreControl",
            "budgetControl",
            "festivalPower",
            "globalRecognition",
            "growthPotential",
        ),
    )


def _collect_metrics(conn: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    actor_metrics: dict[str, dict[str, Any]] = defaultdict(_empty_actor_metrics)
    director_metrics: dict[str, dict[str, Any]] = defaultdict(_empty_director_metrics)
    rows = conn.execute(
        """
        SELECT
            m.title,
            m.representative_year,
            m.max_annual_audience,
            d.movie_name_ko,
            d.actors_json,
            d.directors_json,
            d.genres_json
        FROM staging_major_korean_movies m
        JOIN staging_kobis_movie_details d ON d.movie_code = m.source_movie_code
        """
    ).fetchall()
    for row in rows:
        title = str(row["movie_name_ko"] or row["title"] or "")
        audience = int(row["max_annual_audience"] or 0)
        audience_million = audience / 1_000_000
        year = int(row["representative_year"] or 0)
        genres = _normalize_genres(loads_json(row["genres_json"], []))
        global_signal = int(title in GLOBAL_SIGNAL_TITLES)
        auteur_signal = int(any(genre in {"indie_art", "social_true_story"} for genre in genres))

        seen_actors: set[str] = set()
        for index, raw_name in enumerate(loads_json(row["actors_json"], [])):
            name = str(raw_name).strip()
            if not name or name in seen_actors:
                continue
            seen_actors.add(name)
            metric = actor_metrics[name]
            metric["appearances"] += 1
            metric["best_audience"] = max(metric["best_audience"], audience)
            metric["active_years"].add(year)
            metric["genres"].update(genres)
            for genre in genres:
                metric["genre_counts"][GENRE_IDS[genre]] += 1
            if index <= 1:
                metric["lead_count"] += 1
                metric["lead_audience_total"] += audience_million
                if audience >= 1_000_000:
                    metric["lead_hit_count"] += 1
            elif index <= 7:
                metric["supporting_count"] += 1
                if audience >= 3_000_000:
                    metric["supporting_hit_count"] += 1
            if year >= 2018 and audience >= 1_000_000:
                metric["recent_public_hits"] += 1
            metric["global_signal_count"] += global_signal
            metric["auteur_collaboration_count"] += auteur_signal

        seen_directors: set[str] = set()
        for raw_name in loads_json(row["directors_json"], []):
            name = str(raw_name).strip()
            if not name or name in seen_directors:
                continue
            seen_directors.add(name)
            metric = director_metrics[name]
            metric["film_count"] += 1
            metric["audience_total"] += audience_million
            metric["best_audience"] = max(metric["best_audience"], audience)
            metric["active_years"].add(year)
            metric["genres"].update(genres)
            for genre in genres:
                metric["genre_counts"][GENRE_IDS[genre]] += 1
            if audience >= 1_000_000:
                metric["hit_films"] += 1
            if year >= 2018 and audience >= 1_000_000:
                metric["recent_public_hits"] += 1
            metric["global_signal_count"] += global_signal
            metric["auteur_collaboration_count"] += auteur_signal
            metric["critic_discourse_signal"] += auteur_signal

    for metric in actor_metrics.values():
        lead_count = max(1, int(metric["lead_count"]))
        metric["avg_lead_audience_million"] = float(metric["lead_audience_total"]) / lead_count
        metric["genre_diversity_score"] = len(metric["genres"])
        metric["active_span"] = _span(metric["active_years"])
    for metric in director_metrics.values():
        film_count = max(1, int(metric["film_count"]))
        metric["avg_audience_million"] = float(metric["audience_total"]) / film_count
        metric["genre_diversity_score"] = len(metric["genres"])
        metric["active_span"] = _span(metric["active_years"])
    return actor_metrics, director_metrics


def _empty_actor_metrics() -> dict[str, Any]:
    return {
        "appearances": 0,
        "lead_count": 0,
        "supporting_count": 0,
        "lead_hit_count": 0,
        "supporting_hit_count": 0,
        "lead_audience_total": 0.0,
        "best_audience": 0,
        "recent_public_hits": 0,
        "global_signal_count": 0,
        "foreign_market_signal": 0,
        "auteur_collaboration_count": 0,
        "genres": set(),
        "genre_counts": defaultdict(int),
        "active_years": set(),
    }


def _empty_director_metrics() -> dict[str, Any]:
    return {
        "film_count": 0,
        "hit_films": 0,
        "audience_total": 0.0,
        "best_audience": 0,
        "recent_public_hits": 0,
        "global_signal_count": 0,
        "foreign_market_signal": 0,
        "auteur_collaboration_count": 0,
        "critic_discourse_signal": 0,
        "genres": set(),
        "genre_counts": defaultdict(int),
        "active_years": set(),
    }


def _updated_stat_profile(stat_profile: dict[str, Any], metrics: dict[str, Any]) -> dict[str, Any]:
    profile = dict(stat_profile)
    profile["estimationMethod"] = "tier_tags_plus_actual_data_plus_manual_override"
    profile["dataCoverage"] = {
        "source": "staging_major_korean_movies + staging_kobis_movie_details",
        "matchedFilmCount": int(metrics.get("appearances", metrics.get("film_count", 0)) or 0),
        "bestAudience": int(metrics.get("best_audience", 0) or 0),
        "genreDiversity": int(metrics.get("genre_diversity_score", 0) or 0),
    }
    if profile.get("peakEras") and not profile.get("primeEras"):
        profile["primeEras"] = profile["peakEras"]
    return profile


def _public_profile_for_stats(
    person_type: str,
    profile: dict[str, Any],
    stats: dict[str, int],
    potential: dict[str, int],
) -> dict[str, str]:
    one_line = profile.get("oneLine") or ("한국영화 산업 데이터베이스에 등록된 배우." if person_type == "actor" else "한국영화 산업 데이터베이스에 등록된 감독.")
    if person_type == "actor":
        current_parts = [
            ability_text(stats.get("acting", 50), "acting"),
            ability_text(max(stats.get("ticketPower", 40), stats.get("brandPower", 40)), "actor_market"),
        ]
        potential_value = potential.get("growthPotential", stats.get("growthPotential", 50))
        fame_value = max(stats.get("ticketPower", 40), stats.get("festivalPower", 40), stats.get("brandPower", 40))
        brand_value = max(stats.get("brandPower", 40), stats.get("globalRecognition", 20))
    else:
        current_parts = [
            ability_text(stats.get("directing", 50), "directing"),
            ability_text(max(stats.get("commercialSense", 40), stats.get("auteurPower", 40)), "director_identity"),
        ]
        potential_value = potential.get("growthPotential", stats.get("growthPotential", 50))
        fame_value = max(stats.get("commercialSense", 40), stats.get("festivalPower", 40), stats.get("globalRecognition", 30))
        brand_value = max(stats.get("auteurPower", 40), stats.get("commercialSense", 40), stats.get("globalRecognition", 30))

    return {
        "oneLine": one_line,
        "currentAbilityText": " ".join(current_parts),
        "potentialText": _potential_text(int(potential_value)),
        "fameText": _fame_text(int(fame_value)),
        "brandText": _brand_text(int(brand_value)),
    }


def _potential_text(value: int) -> str:
    if value >= 85:
        return "조건이 맞으면 현재 평가를 크게 뛰어넘을 수 있는 잠재력이 있다."
    if value >= 70:
        return "좋은 작품과 만나면 뚜렷한 도약 가능성이 있다."
    if value >= 55:
        return "성장 가능성은 있으나 작품 선택과 시장 흐름의 영향을 크게 받는다."
    return "잠재력보다는 현재 검증된 범위 안에서 활용하는 편이 안정적이다."


def _fame_text(value: int) -> str:
    if value >= 90:
        return "한국 영화계를 대표하는 이름으로 평가된다."
    if value >= 75:
        return "업계와 관객 모두에게 강한 인지도를 가진 인물이다."
    if value >= 60:
        return "업계 안에서 안정적인 인지도를 확보한 인물이다."
    if value >= 40:
        return "인지도는 있으나 작품 성과에 따라 평가가 크게 달라진다."
    return "아직 대중적 명성은 제한적이다."


def _brand_text(value: int) -> str:
    if value >= 90:
        return "이름만으로도 제작 발표와 투자 검토 단계에서 큰 관심을 만든다."
    if value >= 75:
        return "캐스팅 또는 참여 발표가 마케팅과 언론 노출에 뚜렷한 힘을 보탠다."
    if value >= 60:
        return "작품의 신뢰도와 홍보 안정성에 긍정적으로 작용한다."
    if value >= 40:
        return "브랜드 효과는 제한적이며 작품 자체의 설득력이 더 중요하다."
    return "브랜드 평판은 아직 뚜렷하게 형성되지 않았다."


def _field_label(field: str) -> str:
    return {
        "acting": "연기력",
        "actor_market": "흥행과 브랜드 영향력",
        "directing": "연출력",
        "director_identity": "상업성과 작가성",
    }.get(field, "해당 역량")


def _merge_genre_fit(
    existing: dict[str, Any],
    genre_counts: dict[str, int],
    stat_profile: dict[str, Any],
    person_type: str,
) -> dict[str, int]:
    result = {key: _to_int(value, 50) for key, value in existing.items() if isinstance(value, int | float)}
    for genre_id, bonus in _genre_fit_from_profile(stat_profile, person_type).items():
        result[genre_id] = clamp(max(result.get(genre_id, 50), 55 + bonus))
    if not genre_counts:
        return result
    max_count = max(genre_counts.values()) or 1
    for genre_id, count in genre_counts.items():
        result[genre_id] = clamp(max(result.get(genre_id, 0), 45 + (count / max_count) * 40 + min(10, count * 2)))
    return result


def _genre_fit_from_profile(stat_profile: dict[str, Any], person_type: str) -> dict[str, int]:
    bonuses: dict[str, int] = {}
    for raw_tag in stat_profile.get("genreTags") or []:
        genre_id = GENRE_TAG_ALIASES.get(str(raw_tag))
        if genre_id:
            bonuses[genre_id] = max(bonuses.get(genre_id, 0), 18)
    tag_bonus_source = ACTOR_TAG_GENRE_BONUSES if person_type == "actor" else DIRECTOR_TAG_GENRE_BONUSES
    type_field = "roleType" if person_type == "actor" else "directorType"
    for tag in stat_profile.get(type_field) or []:
        for genre_id, bonus in tag_bonus_source.get(str(tag), {}).items():
            bonuses[genre_id] = max(bonuses.get(genre_id, 0), bonus)
    return bonuses


def _normalize_genres(raw_genres: list[Any]) -> set[str]:
    result: set[str] = set()
    for item in raw_genres:
        name = str(item.get("genreNm", item) if isinstance(item, dict) else item)
        if "범죄" in name or "스릴러" in name or "느와르" in name or "미스터리" in name:
            result.add("crime_thriller")
        if "액션" in name or "전쟁" in name:
            result.add("action")
        if "공포" in name or "호러" in name:
            result.add("horror_occult")
        if "멜로" in name or "로맨스" in name:
            result.add("romance_melodrama")
        if "코미디" in name:
            result.add("comedy")
        if "드라마" in name or "가족" in name:
            result.add("family_human_drama")
        if "사극" in name or "시대" in name:
            result.add("period_historical")
        if "다큐" in name or "실화" in name:
            result.add("social_true_story")
        if "예술" in name or "독립" in name:
            result.add("indie_art")
        if "SF" in name or "재난" in name or "괴수" in name:
            result.add("sf_disaster_monster")
        if "판타지" in name:
            result.add("fantasy")
        if "애니" in name:
            result.add("animation")
    return result or {"family_human_drama"}


def _activity_span(person: dict[str, Any], metrics: dict[str, Any]) -> int:
    if metrics.get("active_span"):
        return int(metrics["active_span"])
    available_from = person.get("available_from")
    if not available_from:
        return 0
    return max(0, 2026 - int(available_from))


def _growth_potential(person: dict[str, Any], stats: dict[str, int], seed_stats: dict[str, Any]) -> int:
    if "growthPotential" in seed_stats:
        return _to_int(seed_stats.get("growthPotential"), 55)
    available_from = int(person.get("available_from") or 2000)
    birth_year = person.get("birth_year")
    recency_bonus = max(0, 2026 - available_from)
    base = 70 if available_from >= 2015 else 60 if available_from >= 2005 else 50
    if birth_year:
        age = 2026 - int(birth_year)
        if age <= 32:
            base += 10
        elif age >= 58:
            base -= 10
    current_peak = max(stats.values()) if stats else 50
    if current_peak >= 88:
        base -= 8
    return clamp(base + min(8, recency_bonus // 3))


def _best_seed(seed_stats: dict[str, Any], primary: str, fallback: str, estimated: float) -> int:
    seed_value = seed_stats.get(primary, seed_stats.get(fallback))
    if isinstance(seed_value, int | float):
        return clamp(max(float(seed_value), estimated))
    return clamp(estimated)


def _apply_manual(stats: dict[str, int], manual: dict[str, Any]) -> None:
    for key, delta in manual.items():
        if isinstance(delta, int | float):
            stats[key] = clamp(stats.get(key, 50) + float(delta))


def _apply_named_modifiers(
    stats: dict[str, Any],
    tags: list[Any] | tuple[Any, ...],
    modifiers: dict[str, dict[str, int]],
) -> None:
    for raw_tag in tags or []:
        for key, delta in modifiers.get(str(raw_tag), {}).items():
            stats[key] = clamp(stats.get(key, 50) + delta)


def _apply_manual_override(stats: dict[str, Any], stat_profile: dict[str, Any], keys: tuple[str, ...]) -> None:
    if not stat_profile.get("manualOverride"):
        return
    manual_stats = stat_profile.get("manualStats") or {}
    for key in keys:
        value = manual_stats.get(key)
        if isinstance(value, int | float):
            stats[key] = clamp(value)


def _span(years: set[int]) -> int:
    clean = {year for year in years if year}
    if not clean:
        return 0
    return max(clean) - min(clean) + 1


def _to_int(value: Any, default: int = 0) -> int:
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return default


def clamp(value: float, minimum: int = 0, maximum: int = 100) -> int:
    return max(minimum, min(maximum, int(round(value))))


def clamp_all(stats: dict[str, Any], keys: tuple[str, ...]) -> dict[str, int]:
    return {key: clamp(float(stats.get(key, 0))) for key in keys if key in stats}
