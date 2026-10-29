from __future__ import annotations

import json
import shutil
import sqlite3
from pathlib import Path
from typing import Any

from app.config import RESOURCE_DIR, SEED_DIR
from app.db_core import dumps_json, get_connection, _resolve_database_path
from app.db_schema import PROJECT_STAGE_SEED, initialize_database, reset_static_data
from app.services.rating_service import content_rating_definitions


def _load_seed_file(filename: str, fallback: str | None = None) -> Any:
    for candidate in (filename, fallback):
        if not candidate:
            continue
        seed_path = SEED_DIR / candidate
        if seed_path.exists():
            with seed_path.open("r", encoding="utf-8") as file:
                return json.load(file)
    raise FileNotFoundError(f"Seed file not found: {filename}")


def _load_optional_seed_file(filename: str, fallback: str | None = None) -> Any:
    for candidate in (filename, fallback):
        if not candidate:
            continue
        seed_path = SEED_DIR / candidate
        if seed_path.exists():
            with seed_path.open("r", encoding="utf-8") as file:
                return json.load(file)
    return []


def _load_many_seed_files(filenames: tuple[str, ...] | list[str]) -> list[Any]:
    items: list[Any] = []
    for filename in filenames:
        loaded = _load_optional_seed_file(filename)
        if isinstance(loaded, list):
            items.extend(loaded)
    return items


def _default_event_title(event: dict[str, Any]) -> str:
    npc_type = event.get("npcType")
    npc_type_labels = {
        "investor": "투자자",
        "actor": "배우",
        "director": "감독",
        "press": "언론",
        "critic": "평론가",
        "distributor": "배급사",
    }
    if npc_type:
        return f"{npc_type_labels.get(npc_type, str(npc_type))}와의 대화"
    return str(event.get("id", "대화 이벤트"))


def _choice_effect_summary(choice: dict[str, Any]) -> dict[str, Any]:
    if "effects" in choice:
        return choice.get("effects") or {}
    if "effectsOnSuccess" in choice or "effectsOnFailure" in choice:
        return {
            "success": choice.get("effectsOnSuccess", {}),
            "failure": choice.get("effectsOnFailure", {}),
        }
    return {}


def _seed_initial_people_rosters(conn: sqlite3.Connection) -> None:
    for rule in _load_optional_seed_file("people/generated_people_rules.json", "future_generation_rules.json"):
        rule_data = rule.get("rule", {})
        seed_count = rule_data.get("seedCount")
        person_type = rule_data.get("type")
        if not seed_count or not person_type:
            continue
        if person_type in {"actor", "director"}:
            _seed_generated_people_roster(conn, person_type, rule_data, int(seed_count))
        elif person_type == "critic":
            _seed_generated_critic_roster(conn, rule_data, int(seed_count))


def _seed_protected_people(conn: sqlite3.Connection) -> None:
    for entry in _load_optional_seed_file("people/protected_people.json"):
        person_id = entry.get("personId", entry.get("id"))
        if not person_id:
            continue
        conn.execute(
            "UPDATE people SET protection_level = ? WHERE id = ?",
            (entry.get("protectionLevel", "protected"), person_id),
        )
        for schedule in entry.get("schedules", []):
            conn.execute(
                """
                INSERT INTO people_protected_schedules (
                    person_id, start_year, start_month, end_year, end_month,
                    reason, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    person_id,
                    schedule["startYear"],
                    schedule.get("startMonth"),
                    schedule.get("endYear"),
                    schedule.get("endMonth"),
                    schedule.get("reason", entry.get("reason")),
                    dumps_json(schedule.get("metadata", {})),
                ),
            )


def _seed_protected_director_films(conn: sqlite3.Connection) -> None:
    for film in _normalize_protected_director_films(_load_optional_seed_file("history/protected_director_films.json")):
        metadata = film.get("metadata", {})
        director_id = film.get("directorId")
        if director_id and metadata.get("directorProtectionLevel"):
            conn.execute(
                """
                UPDATE people
                SET protection_level = ?, historical_filmography_locked = ?
                WHERE id = ?
                """,
                (
                    metadata["directorProtectionLevel"],
                    1 if metadata.get("historicalFilmographyLocked") else 0,
                    director_id,
                ),
            )
        elif director_id and metadata.get("historicalFilmographyLocked"):
            conn.execute(
                "UPDATE people SET historical_filmography_locked = 1 WHERE id = ?",
                (director_id,),
            )
        if director_id and metadata.get("historicalFilmographyLocked"):
            conn.execute(
                """
                UPDATE people_director_profiles
                SET historical_filmography_locked = 1
                WHERE person_id = ?
                """,
                (director_id,),
            )
        values = (
            film["id"],
            film.get("directorId"),
            film["title"],
            film.get("releaseYear"),
            film.get("releaseMonth"),
            film.get("protectionLevel", "fixed"),
            dumps_json(metadata),
        )
        conn.execute(
            """
            INSERT OR REPLACE INTO history_protected_director_films (
                id, director_id, title, release_year, release_month,
                protection_level, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            values,
        )
        _seed_protected_film_schedule(conn, film)


def _normalize_protected_director_films(seed_data: Any) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    if not isinstance(seed_data, list):
        return normalized

    for entry in seed_data:
        if "works" not in entry:
            normalized.append(entry)
            continue

        director_id = entry["directorId"]
        director_metadata = {
            "directorName": entry.get("directorName", entry.get("name")),
            "directorProtectionLevel": entry.get("protectionLevel"),
            "historicalFilmographyLocked": bool(entry.get("historicalFilmographyLocked", True)),
        }
        for work in entry.get("works", []):
            metadata = {
                key: value
                for key, value in work.items()
                if key
                not in {
                    "filmId",
                    "id",
                    "title",
                    "year",
                    "month",
                    "releaseYear",
                    "releaseMonth",
                    "protectionLevel",
                }
            }
            metadata.update(director_metadata)
            normalized.append(
                {
                    "id": work.get("filmId", work.get("id")),
                    "directorId": director_id,
                    "title": work["title"],
                    "releaseYear": work.get("year", work.get("releaseYear")),
                    "releaseMonth": work.get("month", work.get("releaseMonth")),
                    "protectionLevel": work.get("protectionLevel", entry.get("protectionLevel", "protectedFixed")),
                    "metadata": metadata,
                }
            )
    return normalized


def _seed_protected_film_schedule(conn: sqlite3.Connection, film: dict[str, Any]) -> None:
    director_id = film.get("directorId")
    metadata = film.get("metadata", {})
    protected_window = metadata.get("protectedWindow")
    if director_id and protected_window:
        conn.execute(
            """
            INSERT INTO people_protected_schedules (
                person_id, start_year, start_month, end_year, end_month,
                reason, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                director_id,
                protected_window["startYear"],
                protected_window.get("startMonth"),
                protected_window.get("endYear"),
                protected_window.get("endMonth"),
                f"확정된 제작/개봉 일정: {film['title']}",
                dumps_json({"filmId": film["id"], "title": film["title"]}),
            ),
        )
    for person in metadata.get("corePeople", []):
        person_id = person.get("personId")
        if not person_id or not protected_window:
            continue
        conn.execute(
            """
            INSERT INTO people_protected_schedules (
                person_id, start_year, start_month, end_year, end_month,
                reason, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                person_id,
                protected_window["startYear"],
                protected_window.get("startMonth"),
                protected_window.get("endYear"),
                protected_window.get("endMonth"),
                f"확정된 핵심 참여 일정: {film['title']}",
                dumps_json({"filmId": film["id"], "title": film["title"], "role": person.get("role")}),
            ),
        )


def _seed_generated_people_roster(
    conn: sqlite3.Connection,
    person_type: str,
    rule_data: dict[str, Any],
    target_count: int,
) -> None:
    current_count = conn.execute(
        "SELECT COUNT(*) AS count FROM people WHERE type = ?",
        (person_type,),
    ).fetchone()["count"]
    needed = max(0, target_count - int(current_count))
    if not needed:
        return

    profile_table = "people_actor_profiles" if person_type == "actor" else "people_director_profiles"
    used_names = {
        row["name_ko"]
        for row in conn.execute("SELECT name_ko FROM people WHERE type = ?", (person_type,)).fetchall()
    }
    id_prefix = rule_data.get("idPrefix", f"{person_type}_seed")
    archetypes = rule_data.get("archetypes") or [{}]
    for sequence in range(1, needed + 1):
        index = int(current_count) + sequence
        archetype = archetypes[(index - 1) % len(archetypes)]
        name_ko = _generated_korean_name(rule_data, index, used_names)
        name_en = f"{rule_data.get('englishPrefix', person_type.title())} {sequence:03d}"
        birth_year = _generated_year(rule_data.get("birthYearRange", [1960, 2000]), index, 7)
        available_from = _generated_available_from(rule_data, birth_year, index)
        current_stats = _varied_stats(archetype.get("currentStats", rule_data.get("currentStats", {})), index)
        potential_stats = _varied_stats(
            archetype.get("potentialStats", rule_data.get("potentialStats", {})),
            index + 3,
        )
        genre_fit = _generated_genre_fit(person_type, archetype, rule_data, index)
        for key, value in current_stats.items():
            if key in potential_stats:
                potential_stats[key] = max(int(potential_stats[key]), min(100, int(value) + 4))

        public_profile = _generated_public_profile(person_type, archetype, name_ko, available_from, index)
        person_id = _unique_generated_id(conn, "people", id_prefix, sequence)
        values = (
            person_id,
            name_ko,
            name_en,
            person_type,
            birth_year,
            available_from,
            "active",
            rule_data.get("protectionLevel", "fictional"),
            dumps_json(current_stats),
            dumps_json(potential_stats),
            dumps_json(genre_fit),
            dumps_json(
                {
                    "tier": rule_data.get("tier"),
                    "roleType": rule_data.get("roleType", []),
                    "directorType": rule_data.get("directorType", []),
                    "genreTags": rule_data.get("genreTags", []),
                    "peakEras": [],
                    "primeEras": [],
                    "manualOverride": False,
                    "manualStats": {},
                    "manualStatAdjustments": {},
                    "estimationNotes": "generated_roster_placeholder",
                }
            ),
            dumps_json(public_profile),
        )
        conn.execute(
            """
            INSERT OR REPLACE INTO people (
                id, name_ko, name_en, type, birth_year, available_from,
                status, protection_level, current_stats_json, potential_stats_json,
                genre_fit_json, stat_profile_json, public_profile_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            values,
        )
        conn.execute(
            f"""
            INSERT OR REPLACE INTO {profile_table} (
                person_id, current_stats_json, potential_stats_json,
                genre_fit_json, stat_profile_json, public_profile_json
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (person_id, values[8], values[9], values[10], values[11], values[12]),
        )


def _seed_generated_critic_roster(
    conn: sqlite3.Connection,
    rule_data: dict[str, Any],
    target_count: int,
) -> None:
    current_count = conn.execute("SELECT COUNT(*) AS count FROM critics").fetchone()["count"]
    needed = max(0, target_count - int(current_count))
    if not needed:
        return

    used_names = {row["name_ko"] for row in conn.execute("SELECT name_ko FROM critics").fetchall()}
    id_prefix = rule_data.get("idPrefix", "critic_seed")
    focuses = rule_data.get("focuses") or [{}]
    for sequence in range(1, needed + 1):
        index = int(current_count) + sequence
        focus = focuses[(index - 1) % len(focuses)]
        critic_id = _unique_generated_id(conn, "critics", id_prefix, sequence)
        name_ko = _generated_korean_name(rule_data, index, used_names)
        critic_values = (
            critic_id,
            name_ko,
            "critic",
            rule_data.get("availableFrom", 1980),
            dumps_json(
                {
                    "tone": focus.get("tone", "balanced"),
                    "focus": focus.get("focus", "scenario"),
                    "reviewStyle": focus.get("reviewStyle", "longform"),
                }
            ),
            dumps_json(_varied_stats(focus.get("tasteProfile", {}), index)),
            dumps_json(_varied_stats(focus.get("influence", {}), index + 5)),
            dumps_json(focus.get("scoringStyle", {})),
            focus.get("publicDescription", "영화의 완성도와 시대 감각을 함께 보는 평론가."),
        )
        for table in ("critics", "people_critic_profiles", "systems_critics"):
            conn.execute(
                f"""
                INSERT OR REPLACE INTO {table} (
                    id, name_ko, type, available_from, critic_type_json,
                    taste_profile_json, influence_json, scoring_style_json,
                    public_description
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                critic_values,
            )


def _generated_korean_name(rule_data: dict[str, Any], index: int, used_names: set[str]) -> str:
    family_names = rule_data.get("familyNames") or ["강", "김", "박", "서", "윤", "이", "정", "최", "한"]
    given_names = rule_data.get("givenNames") or ["도윤", "서하", "지안", "민재", "하린", "준서"]
    for attempt in range(max(1, len(family_names) * len(given_names))):
        family = family_names[(index + attempt * 3) % len(family_names)]
        given = given_names[(index * 7 + attempt * 11) % len(given_names)]
        name = f"{family}{given}"
        if name not in used_names:
            used_names.add(name)
            return name
    name = f"{family_names[index % len(family_names)]}{given_names[index % len(given_names)]}{index}"
    used_names.add(name)
    return name


def _generated_year(year_range: list[int], index: int, step: int) -> int:
    start = int(year_range[0])
    end = int(year_range[1])
    return start + ((index * step) % max(1, end - start + 1))


def _generated_available_from(rule_data: dict[str, Any], birth_year: int, index: int) -> int:
    range_start, range_end = rule_data.get("availableFromRange", [1980, 2026])
    career_start_age = int(rule_data.get("careerStartAge", 23))
    career_spread = max(1, int(rule_data.get("careerStartSpread", 8)))
    debut_year = birth_year + career_start_age + ((index * 3) % career_spread)
    return max(int(range_start), min(int(range_end), debut_year))


def _varied_stats(stats: dict[str, Any], index: int) -> dict[str, int]:
    varied: dict[str, int] = {}
    for key, value in stats.items():
        if not isinstance(value, int | float):
            continue
        delta = ((index * 11 + len(key) * 5) % 17) - 8
        varied[key] = _seed_clamp(float(value) + delta)
    return varied


def _generated_genre_fit(
    person_type: str,
    archetype: dict[str, Any],
    rule_data: dict[str, Any],
    index: int,
) -> dict[str, int]:
    base = dict(_default_genre_fit(person_type))
    base.update(rule_data.get("genreFit", {}))
    base.update(archetype.get("genreFit", {}))
    return {
        genre_id: _seed_clamp(float(value) + (((index + offset) * 7) % 13) - 6)
        for offset, (genre_id, value) in enumerate(base.items())
    }


def _default_genre_fit(person_type: str) -> dict[str, int]:
    if person_type == "director":
        return {
            "genre_crime_thriller": 58,
            "genre_action": 54,
            "genre_horror_occult": 52,
            "genre_romance_melodrama": 52,
            "genre_comedy": 50,
            "genre_family_human_drama": 54,
            "genre_period_historical": 50,
            "genre_social_true_story": 56,
            "genre_indie_art": 58,
            "genre_sf_disaster_monster": 46,
            "genre_fantasy": 46,
            "genre_animation": 42,
        }
    return {
        "genre_crime_thriller": 56,
        "genre_action": 54,
        "genre_horror_occult": 50,
        "genre_romance_melodrama": 56,
        "genre_comedy": 52,
        "genre_family_human_drama": 54,
        "genre_period_historical": 48,
        "genre_social_true_story": 54,
        "genre_indie_art": 52,
        "genre_sf_disaster_monster": 46,
        "genre_fantasy": 48,
        "genre_animation": 42,
    }


def _generated_public_profile(
    person_type: str,
    archetype: dict[str, Any],
    name: str,
    available_from: int,
    index: int,
) -> dict[str, str]:
    profile = archetype.get("publicProfile", {})
    role_label = "배우" if person_type == "actor" else "감독"
    trend_options = [
        "업계 관계자 사이에서 다음 작품 선택이 주목받고 있다.",
        "특정 장르에서 반복적으로 제안을 받고 있다.",
        "작품 성과에 따라 인지도 상승 여지가 크다.",
        "현장 평판이 천천히 쌓이는 중이다.",
    ]
    defaults = {
        "oneLine": f"{name}은 안정적인 기본기와 뚜렷한 색을 가진 {role_label}이다.",
        "currentAbilityText": "현재 능력은 장르와 제작 환경에 따라 강점이 다르게 드러난다.",
        "potentialText": "좋은 프로젝트와 만나면 명성과 필모그래피를 함께 끌어올릴 수 있다.",
        "fameText": "업계 안에서는 이름이 알려져 있으나 대중 인지도는 작품 성과에 좌우된다.",
        "brandText": "작품 선택과 현장 평판이 브랜드 이미지를 좌우한다.",
        "recentTrendText": trend_options[index % len(trend_options)],
        "activityStatusText": "활동 가능" if available_from <= 2026 else "향후 등장 예정",
        "informationReliabilityText": "공개 자료와 업계 평판을 교차 확인한 중간 신뢰도 정보다.",
    }
    return {
        key: str(profile.get(key, value)).format(name=name, role=role_label)
        for key, value in defaults.items()
    }


def _unique_generated_id(conn: sqlite3.Connection, table: str, prefix: str, sequence: int) -> str:
    candidate = f"{prefix}_{sequence:03d}"
    while conn.execute(f"SELECT 1 FROM {table} WHERE id = ?", (candidate,)).fetchone():
        sequence += 1
        candidate = f"{prefix}_{sequence:03d}"
    return candidate


def _seed_clamp(value: float, minimum: int = 0, maximum: int = 100) -> int:
    return max(minimum, min(maximum, int(round(value))))


def _era_bounds_from_id(era_id: str) -> tuple[int | None, int | None]:
    era_bounds = {
        "era_1980s": (1980, 1989),
        "era_1990s": (1990, 1999),
        "era_2000s": (2000, 2009),
        "era_2010s": (2010, 2019),
        "era_2020s": (2020, 2029),
    }
    return era_bounds.get(era_id, (None, None))


def seed_database(path: Path | str | None = None, reset_static: bool = True) -> None:
    db_path = _resolve_database_path(path)
    initialize_database(db_path)
    if reset_static:
        reset_static_data(db_path)

    with get_connection(db_path) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO schema_info (key, value) VALUES ('schema_version', '3')"
        )
        for rating in content_rating_definitions():
            conn.execute(
                """
                INSERT OR REPLACE INTO content_ratings (
                    id, name_ko, age_floor, description,
                    audience_multiplier, secondary_market_multiplier
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    rating["id"],
                    rating["nameKo"],
                    rating.get("ageFloor", 0),
                    rating.get("description"),
                    rating.get("audienceMultiplier", 1.0),
                    rating.get("secondaryMarketMultiplier", 1.0),
                ),
            )
        for system in _load_optional_seed_file("system_definitions.json"):
            conn.execute(
                """
                INSERT OR REPLACE INTO system_definitions (
                    id, name, category, implementation_status, description,
                    primary_tables_json, primary_services_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    system["id"],
                    system["name"],
                    system["category"],
                    system.get("implementationStatus", "foundation"),
                    system.get("description"),
                    dumps_json(system.get("primaryTables")),
                    dumps_json(system.get("primaryServices")),
                ),
            )

        for stat in _load_seed_file("core/stats_100.json", "stats.json"):
            if isinstance(stat, str):
                stat_id = stat
                stat_data = {
                    "id": stat_id,
                    "nameKo": stat_id,
                    "category": "core",
                    "hidden": True,
                    "description": "",
                }
            else:
                stat_data = stat
                stat_id = stat_data["id"]
            conn.execute(
                """
                INSERT OR REPLACE INTO stat_definitions (
                    id, name_ko, category, min_value, max_value, hidden,
                    description
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    stat_id,
                    stat_data.get("nameKo", stat_id),
                    stat_data.get("category", "core"),
                    stat_data.get("minValue", 0),
                    stat_data.get("maxValue", 100),
                    1 if stat_data.get("hidden", True) else 0,
                    stat_data.get("description", ""),
                ),
            )
            conn.execute(
                """
                INSERT OR REPLACE INTO core_stats (
                    id, name_ko, category, min_value, max_value, hidden,
                    description
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    stat_id,
                    stat_data.get("nameKo", stat_id),
                    stat_data.get("category", "core"),
                    stat_data.get("minValue", 0),
                    stat_data.get("maxValue", 100),
                    1 if stat_data.get("hidden", True) else 0,
                    stat_data.get("description", ""),
                ),
            )

        for reputation in _load_optional_seed_file("reputation_types.json"):
            conn.execute(
                """
                INSERT OR REPLACE INTO reputation_definitions (
                    id, name_ko, description, low_text, mid_text, high_text
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    reputation["id"],
                    reputation["nameKo"],
                    reputation.get("description"),
                    reputation.get("lowText"),
                    reputation.get("midText"),
                    reputation.get("highText"),
                ),
            )
            conn.execute(
                """
                INSERT OR REPLACE INTO systems_reputation (
                    id, name_ko, description, low_text, mid_text, high_text
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    reputation["id"],
                    reputation["nameKo"],
                    reputation.get("description"),
                    reputation.get("lowText"),
                    reputation.get("midText"),
                    reputation.get("highText"),
                ),
            )

        for network in _load_optional_seed_file("network_types.json"):
            conn.execute(
                """
                INSERT OR REPLACE INTO network_definitions (
                    id, name_ko, target_type, description, low_text, mid_text,
                    high_text
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    network["id"],
                    network["nameKo"],
                    network.get("targetType", "industry"),
                    network.get("description"),
                    network.get("lowText"),
                    network.get("midText"),
                    network.get("highText"),
                ),
            )
            conn.execute(
                """
                INSERT OR REPLACE INTO systems_network (
                    id, name_ko, target_type, description, low_text, mid_text,
                    high_text
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    network["id"],
                    network["nameKo"],
                    network.get("targetType", "industry"),
                    network.get("description"),
                    network.get("lowText"),
                    network.get("midText"),
                    network.get("highText"),
                ),
            )

        for position in _load_optional_seed_file("starting_positions.json"):
            conn.execute(
                """
                INSERT OR REPLACE INTO starting_positions (
                    id, name, description, cash_multiplier,
                    initial_stats_json, initial_reputation_json,
                    initial_network_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    position["id"],
                    position["name"],
                    position.get("description"),
                    position.get("cashMultiplier", 1.0),
                    dumps_json(position.get("initialStats")),
                    dumps_json(position.get("initialReputation")),
                    dumps_json(position.get("initialNetwork")),
                ),
            )

        for option in _load_optional_seed_file("character_options.json"):
            conn.execute(
                """
                INSERT OR REPLACE INTO character_option_sets (
                    category, id, label, description, effects_json
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    option["category"],
                    option["id"],
                    option["label"],
                    option.get("description"),
                    dumps_json(option.get("effects")),
                ),
            )

        production_stages = _load_optional_seed_file("core/production_stages.json")
        if not production_stages:
            production_stages = list(PROJECT_STAGE_SEED)
        for stage in production_stages:
            stage_group = stage.get("stage_group", stage.get("stageGroup", "production"))
            required_for_scales = stage.get("required_for_scales", stage.get("requiredForScales"))
            conn.execute(
                """
                INSERT OR REPLACE INTO project_stage_definitions (
                    id, sequence, name, description, stage_group,
                    required_for_scales_json
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    stage["id"],
                    stage["sequence"],
                    stage["name"],
                    stage.get("description"),
                    stage_group,
                    dumps_json(required_for_scales),
                ),
            )
            conn.execute(
                """
                INSERT OR REPLACE INTO core_production_stages (
                    id, sequence, name, description, stage_group,
                    required_for_scales_json
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    stage["id"],
                    stage["sequence"],
                    stage["name"],
                    stage.get("description"),
                    stage_group,
                    dumps_json(required_for_scales),
                ),
            )

        for era in _load_seed_file("core/eras.json", "eras.json"):
            modifiers = era.get("marketModifiers", {})
            era_values = (
                era["id"],
                era["name"],
                era["startYear"],
                era.get("endYear"),
                era.get("description"),
                modifiers.get("theaterDemand", 50),
                modifiers.get("ottPower", 0),
                modifiers.get("foreignCompetition", 50),
                modifiers.get("middleBudgetRisk", 50),
                modifiers.get("specialFormatDemand", 0),
                modifiers.get("onlineSpreadPower", 0),
                modifiers.get("ticketPriceBurden", 50),
                dumps_json(era.get("unlockedSystems", [])),
                dumps_json(era.get("lockedSystems", [])),
            )
            for table in ("eras", "core_eras"):
                conn.execute(
                    f"""
                    INSERT OR REPLACE INTO {table} (
                        id, name, start_year, end_year, description,
                        theater_demand, ott_power, foreign_competition,
                        middle_budget_risk, special_format_demand,
                        online_spread_power, ticket_price_burden,
                        unlocked_systems_json, locked_systems_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    era_values,
                )

        for rule in _load_optional_seed_file("core/era_rules.json"):
            era_bounds = _era_bounds_from_id(rule["id"])
            market_rules = rule.get("marketRules", rule.get("marketModifiers", {}))
            production_rules = rule.get("productionRules", {})
            if not production_rules:
                production_rules = {
                    "specialRestrictions": rule.get("specialRestrictions", []),
                    "weakChoices": rule.get("weakChoices", []),
                }
            distribution_rules = rule.get("distributionRules", {})
            if not distribution_rules:
                distribution_rules = {
                    "options": rule.get("distributionOptions", []),
                }
            marketing_rules = rule.get("marketingRules", {})
            if not marketing_rules:
                marketing_rules = {
                    "channels": rule.get("marketingChannels", []),
                }
            secondary_market_rules = rule.get("secondaryMarketRules", {})
            if not secondary_market_rules:
                secondary_market_rules = {
                    "options": rule.get("secondaryMarketOptions", []),
                }
            rule_values = (
                rule["id"],
                rule["name"],
                rule.get("startYear", era_bounds[0]),
                rule.get("endYear", era_bounds[1]),
                rule.get("summary") or rule.get("description"),
                dumps_json(market_rules),
                dumps_json(production_rules),
                dumps_json(distribution_rules),
                dumps_json(marketing_rules),
                dumps_json(secondary_market_rules),
                dumps_json(rule.get("lockedSystems", [])),
                dumps_json(rule.get("unlockedSystems", rule.get("unlockedChoices", []))),
                dumps_json(rule.get("lockedChoices", [])),
                dumps_json(rule.get("strongChoices", [])),
                dumps_json(rule.get("inefficientChoices", rule.get("weakChoices", []))),
                dumps_json(rule.get("genreModifiers", {})),
                dumps_json(rule.get("riskModifiers", {})),
                dumps_json(rule.get("gameOverRisks", [])),
                dumps_json(rule.get("futureRules", {})),
            )
            for table in ("era_rules", "core_era_rules"):
                conn.execute(
                    f"""
                    INSERT OR REPLACE INTO {table} (
                        id, name, start_year, end_year, summary,
                        market_rules_json, production_rules_json,
                        distribution_rules_json, marketing_rules_json,
                        secondary_market_rules_json, locked_systems_json,
                        unlocked_systems_json, locked_choices_json,
                        strong_choices_json, inefficient_choices_json,
                        genre_modifiers_json, risk_modifiers_json,
                        game_over_risks_json, future_rules_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    rule_values,
                )

        for genre in _load_seed_file("core/genres.json", "genres.json"):
            weights = genre.get("budgetWeights", {})
            genre_profile = genre.get("profile", {})
            plagiarism_sensitivity = genre.get(
                "plagiarismSensitivity",
                genre_profile.get("plagiarismSensitivity", 50),
            )
            genre_values = (
                genre["id"],
                genre["name"],
                genre.get("description"),
                dumps_json(genre.get("eraFit")),
                weights.get("scenario", 10),
                weights.get("directing", 10),
                weights.get("actors", 10),
                weights.get("shooting", 10),
                weights.get("art", 10),
                weights.get("stunt", 0),
                weights.get("vfx", 0),
                weights.get("sound", 10),
                weights.get("editing", 10),
                weights.get("contingency", 5),
                genre_profile.get("boxofficeWeight", 1.0),
                genre_profile.get("criticWeight", 1.0),
                genre_profile.get("audienceWeight", 1.0),
                dumps_json(genre.get("successFactors", [])),
                dumps_json(genre.get("riskFactors", [])),
                dumps_json(genre.get("majorRisks")),
                genre.get("franchiseFit", genre_profile.get("franchiseFit", 50)),
                genre.get("secondaryMarketFit", genre_profile.get("secondaryMarketFit", 50)),
                plagiarism_sensitivity,
                dumps_json(genre.get("criticWeights", {})),
                dumps_json(genre.get("audienceWeights", {})),
                genre.get("awardCompatibility", 50),
            )
            for table in ("genres", "core_genres"):
                conn.execute(
                    f"""
                    INSERT OR REPLACE INTO {table} (
                        id, name, description, era_fit_json, scenario_weight,
                        directing_weight, actors_weight, shooting_weight,
                        art_weight, stunt_weight, vfx_weight, sound_weight,
                        editing_weight, contingency_weight, boxoffice_weight,
                        critic_weight, audience_weight, success_factors_json,
                        risk_factors_json, major_risks_json, franchise_fit, secondary_market_fit,
                        plagiarism_sensitivity, critic_weights_json,
                        audience_weights_json, award_compatibility
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    genre_values,
                )

        for scale in _load_seed_file("core/project_scales.json", "project_scales.json"):
            event_range = scale.get("eventCountRange", {})
            required_stages = scale.get("requiredStages", scale.get("stageFlow", []))
            scale_values = (
                scale["id"],
                scale["name"],
                scale["minBudget"],
                scale["maxBudget"],
                event_range.get("min", scale.get("minEvents", 1)),
                event_range.get("max", scale.get("maxEvents", 3)),
                scale.get("failureImpact", "normal"),
                dumps_json(required_stages),
                dumps_json(required_stages),
                dumps_json(scale.get("optionalStages", [])),
                scale.get("requiredReputation", 0),
                scale.get("requiredNetwork", 0),
                scale.get("gameOverRiskMultiplier", 1.0),
            )
            for table in ("project_scales", "core_project_scales"):
                conn.execute(
                    f"""
                    INSERT OR REPLACE INTO {table} (
                        id, name, min_budget, max_budget, min_events,
                        max_events, failure_impact, required_stages_json,
                        stage_flow_json, optional_stages_json,
                        required_reputation, required_network,
                        game_over_risk_multiplier
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    scale_values,
                )

        for filename, person_type in (
            ("people/actors_major.json", "actor"),
            ("people/directors_major.json", "director"),
        ):
            fallback = "sample_actors.json" if person_type == "actor" else "sample_directors.json"
            for person in _load_seed_file(filename, fallback):
                current_stats = dumps_json(person.get("currentStats", {}))
                potential_stats = dumps_json(person.get("potentialStats", {}))
                genre_fit = dumps_json(person.get("genreFit", _default_genre_fit(person_type)))
                public_profile = dumps_json(person.get("publicProfile", {}))
                peak_eras = person.get("peakEras", person.get("primeEras", []))
                stat_profile = dumps_json(
                    {
                        "tier": person.get("tier"),
                        "roleType": person.get("roleType", []),
                        "directorType": person.get("directorType", []),
                        "genreTags": person.get("genreTags", []),
                        "peakEras": peak_eras,
                        "primeEras": person.get("primeEras", peak_eras),
                        "globalTag": person.get("globalTag", False),
                        "protectedEventRelated": person.get("protectedEventRelated", False),
                        "manualOverride": person.get("manualOverride", False),
                        "manualStats": person.get("manualStats", {}),
                        "manualStatAdjustments": person.get("manualStatAdjustments", {}),
                        "estimationNotes": person.get("statEstimationNotes", ""),
                    }
                )
                filmography_locked = 1 if person.get("historicalFilmographyLocked", False) else 0
                conn.execute(
                    """
                    INSERT OR REPLACE INTO people (
                        id, name_ko, name_en, type, birth_year, available_from,
                        status, protection_level, current_stats_json,
                        potential_stats_json, genre_fit_json,
                        historical_filmography_locked, stat_profile_json,
                        public_profile_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        person["id"],
                        person["nameKo"],
                        person.get("nameEn"),
                        person.get("type", person_type),
                        person.get("birthYear"),
                        person.get("availableFrom"),
                        person.get("status", "active"),
                        person.get("protectionLevel", "none"),
                        current_stats,
                        potential_stats,
                        genre_fit,
                        filmography_locked,
                        stat_profile,
                        public_profile,
                    ),
                )
                profile_table = "people_actor_profiles" if person_type == "actor" else "people_director_profiles"
                conn.execute(
                    f"""
                    INSERT OR REPLACE INTO {profile_table} (
                        person_id, current_stats_json, potential_stats_json,
                        genre_fit_json, historical_filmography_locked,
                        stat_profile_json, public_profile_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        person["id"],
                        current_stats,
                        potential_stats,
                        genre_fit,
                        filmography_locked,
                        stat_profile,
                        public_profile,
                    ),
                )

        for critic in _load_seed_file("people/critics_major.json", "sample_critics.json"):
            critic_values = (
                critic["id"],
                critic["nameKo"],
                critic.get("type", "critic"),
                critic.get("availableFrom"),
                dumps_json(critic.get("criticType")),
                dumps_json(critic.get("tasteProfile")),
                dumps_json(critic.get("influence")),
                dumps_json(critic.get("scoringStyle", {})),
                critic.get("publicDescription"),
            )
            for table in ("critics", "people_critic_profiles", "systems_critics"):
                conn.execute(
                    f"""
                    INSERT OR REPLACE INTO {table} (
                        id, name_ko, type, available_from, critic_type_json,
                        taste_profile_json, influence_json, scoring_style_json,
                        public_description
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    critic_values,
                )

        _seed_initial_people_rosters(conn)
        _seed_protected_people(conn)
        _seed_protected_director_films(conn)

        organization_seed = SEED_DIR / "sample_organizations.json"
        if organization_seed.exists():
            for organization in _load_seed_file("sample_organizations.json"):
                conn.execute(
                    """
                    INSERT OR REPLACE INTO organizations (
                        id, name_ko, name_en, org_type, available_from, power,
                        reputation_json, strategy_json, public_profile_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        organization["id"],
                        organization["nameKo"],
                        organization.get("nameEn"),
                        organization["orgType"],
                        organization.get("availableFrom"),
                        organization.get("power", 50),
                        dumps_json(organization.get("reputation")),
                        dumps_json(organization.get("strategy")),
                        dumps_json(organization.get("publicProfile")),
                    ),
                )

        award_event_seed = _load_optional_seed_file("history/award_events.json", "awards.json")
        for award in award_event_seed:
            if "name" not in award:
                continue
            award_values = (
                award["id"],
                award["name"],
                award.get("country", "KR"),
                award.get("foundedYear"),
                award.get("prestige", 50),
                dumps_json(award.get("categories")),
                dumps_json(award.get("publicProfile")),
            )
            for table in ("awards", "history_award_events"):
                conn.execute(
                    f"""
                    INSERT OR REPLACE INTO {table} (
                        id, name, country, founded_year, prestige,
                        categories_json, public_profile_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    award_values,
                )

        for result in _load_optional_seed_file("history/award_results_sample.json"):
            conn.execute(
                """
                INSERT INTO history_award_results (
                    award_id, movie_id, year, month, category, result,
                    fixed_level, winner_name, work_title, person_name,
                    source_note, effects_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    result["awardId"],
                    result.get("movieId"),
                    result["year"],
                    result.get("month"),
                    result["category"],
                    result.get("result", "winner"),
                    result.get("fixedLevel", "historical"),
                    result.get("winnerName"),
                    result.get("workTitle"),
                    result.get("personName"),
                    result.get("sourceNote"),
                    dumps_json(result.get("effects")),
                ),
            )

        for rule in _load_optional_seed_file("people/generated_people_rules.json", "future_generation_rules.json"):
            if rule.get("targetType") == "seed_roster" or rule.get("rule", {}).get("seedCount"):
                continue
            rule_values = (
                rule["id"],
                rule["targetType"],
                rule.get("startsYear"),
                rule.get("weight", 100),
                dumps_json(rule.get("rule")),
                rule.get("description"),
            )
            for table in ("future_generation_rules", "systems_future_generation"):
                conn.execute(
                    f"""
                    INSERT OR REPLACE INTO {table} (
                        id, target_type, starts_year, weight, rule_json,
                        description
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    rule_values,
                )

        history_event_sources = (
            ("history_foreign_events", "history/foreign_events_fixed.json", "foreign_events.json"),
            ("history_policy_events", "history/policy_events.json", None),
            ("history_market_events", "history/market_events.json", None),
            ("history_distribution_events", "history/distribution_events.json", None),
            ("history_theater_events", "history/theater_events.json", None),
            ("history_premium_format_events", "history/premium_format_events.json", None),
            ("history_domestic_events", "history/domestic_events_1980s.json", None),
            ("history_domestic_events", "history/domestic_events_1990s.json", None),
            ("history_domestic_events", "history/domestic_events_2000s.json", None),
            ("history_domestic_events", "history/domestic_events_2010s.json", None),
            ("history_domestic_events", "history/domestic_events_2020s.json", None),
        )
        loaded_history_events = []
        for canonical_table, filename, fallback in history_event_sources:
            for event in _load_optional_seed_file(filename, fallback):
                loaded_history_events.append((canonical_table, event))
        loaded_history_events.extend(
            ("history_award_timeline", event)
            for event in award_event_seed
            if "year" in event and "title" in event
        )
        if not any(table == "history_domestic_events" for table, _event in loaded_history_events):
            loaded_history_events.extend(
                ("history_domestic_events", event)
                for event in _load_optional_seed_file("domestic_events.json")
            )

        for canonical_table, event in loaded_history_events:
            event_title = event.get("title", event.get("titleKo"))
            event_description = event.get("description")
            if canonical_table == "history_foreign_events" and event.get("titleEn") and not event_description:
                event_description = f"{event['titleKo']}({event['titleEn']}) 외화 대작 개봉 기록."
            conn.execute(
                """
                INSERT OR REPLACE INTO historical_events (
                    id, year, month, title, type, fixed_level, description,
                    effects_json, unlocks_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event["id"],
                    event["year"],
                    event.get("month"),
                    event_title,
                    event.get("type", "foreign_market" if canonical_table == "history_foreign_events" else "domestic_market"),
                    event.get("fixedLevel", "semiFixed"),
                    event_description,
                    dumps_json(event.get("effects")),
                    dumps_json(event.get("unlocks", [])),
                ),
            )
            if canonical_table == "history_foreign_events":
                conn.execute(
                    """
                    INSERT OR REPLACE INTO history_foreign_events (
                        id, year, month, title, title_ko, title_en,
                        impact_grade, fixed_level, genre_json, description,
                        effects_json, same_window_penalties_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        event["id"],
                        event["year"],
                        event.get("month"),
                        event_title,
                        event.get("titleKo", event_title),
                        event.get("titleEn"),
                        event.get("impactGrade"),
                        event.get("fixedLevel", "semiFixed"),
                        dumps_json(event.get("genre", [])),
                        event_description,
                        dumps_json(event.get("effects")),
                        dumps_json(event.get("sameWindowPenalties", {})),
                    ),
                )
            elif canonical_table in {
                "history_domestic_events",
                "history_policy_events",
                "history_market_events",
                "history_distribution_events",
                "history_theater_events",
                "history_premium_format_events",
            }:
                if canonical_table in {
                    "history_distribution_events",
                    "history_theater_events",
                    "history_premium_format_events",
                }:
                    conn.execute(
                        f"""
                        INSERT OR REPLACE INTO {canonical_table} (
                            id, year, month, title, type, fixed_level,
                            company, chain, location, format_json,
                            related_companies_json, description,
                            effects_json, unlocks_json
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            event["id"],
                            event["year"],
                            event.get("month"),
                            event_title,
                            event.get("type", "industry"),
                            event.get("fixedLevel", "semiFixed"),
                            event.get("company"),
                            event.get("chain"),
                            event.get("location"),
                            dumps_json(event.get("format", [])),
                            dumps_json(event.get("relatedCompanies", [])),
                            event_description,
                            dumps_json(event.get("effects")),
                            dumps_json(event.get("unlocks", [])),
                        ),
                    )
                    continue
                conn.execute(
                    f"""
                    INSERT OR REPLACE INTO {canonical_table} (
                        id, year, month, title, type, fixed_level, description,
                        effects_json, unlocks_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        event["id"],
                        event["year"],
                        event.get("month"),
                        event_title,
                        event.get("type", "domestic_market"),
                        event.get("fixedLevel", "semiFixed"),
                        event_description,
                        dumps_json(event.get("effects")),
                        dumps_json(event.get("unlocks", [])),
                    ),
                )

        for ticket in _load_seed_file("history/ticket_prices.json", "ticket_prices.json"):
            ticket_values = (
                ticket["year"],
                ticket["averageTicketPrice"],
                ticket.get("perceivedTicketPrice"),
                ticket.get("premiumFormatMultiplier", 1.0),
                ticket.get("audiencePriceSensitivity", 50),
                ticket.get("sourceType", "historical"),
            )
            for table in ("ticket_prices", "history_ticket_prices"):
                conn.execute(
                    f"""
                    INSERT OR REPLACE INTO {table} (
                        year, average_ticket_price, perceived_ticket_price,
                        premium_format_multiplier, audience_price_sensitivity,
                        source_type
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    ticket_values,
                )

        production_event_files = (
            ("production/production_choices_planning.json", "production"),
            ("production/production_choices_funding.json", "production"),
            ("production/production_choices_casting.json", "production"),
            ("production/production_choices_shooting.json", "production"),
            ("production/production_choices_postproduction.json", "production"),
            ("production/production_choices_marketing.json", "production"),
            ("production/production_choices_release.json", "production"),
            ("production/dialogue_events.json", "dialogue"),
            ("production/production_events.json", "production"),
            ("production/plagiarism_events.json", "production"),
            ("production/franchise_events.json", "franchise"),
            ("production/post_release_events.json", "post_release"),
        )
        production_events: list[dict[str, Any]] = []
        for filename, default_category in production_event_files:
            for event in _load_optional_seed_file(filename):
                event_data = dict(event)
                event_data["_default_category"] = default_category
                production_events.append(event_data)
        if not production_events:
            production_events = _load_seed_file("production_events.json")

        for event in production_events:
            event_title = event.get("title") or _default_event_title(event)
            event_description = event.get("description") or event.get("npcLine") or ""
            event_category = event.get("category", event.get("_default_category", "production"))
            event_stage = event.get("stage") or (
                "post_release" if event_category in {"franchise", "post_release"} else "planning"
            )
            event_scope = event.get("scope", "project")
            npc_traits_json = dumps_json(event.get("npcTraits", []))
            event_trigger = dict(event.get("trigger") or {})
            if event.get("choiceStyle"):
                event_trigger["_choiceStyle"] = event.get("choiceStyle")
            if event.get("relationshipEvent"):
                event_trigger["_relationshipEvent"] = bool(event.get("relationshipEvent"))
            if event.get("steps") or event.get("negotiation"):
                event_trigger["_dialogueFlow"] = {
                    "steps": event.get("steps", []),
                    "finalOutcomes": event.get("finalOutcomes", []),
                    "scoreLabels": event.get("scoreLabels", {}),
                    "negotiation": event.get("negotiation", {}),
                }
            event_choices = event.get("choices")
            if event_choices is None and "effects" in event:
                event_choices = {"effects": event.get("effects", {})}
            dialogue_values = (
                event["id"],
                event_stage,
                event_title,
                event_description,
                event.get("npcType"),
                npc_traits_json,
                event.get("npcLine"),
                dumps_json(event_trigger),
                dumps_json(event_choices),
            )
            for table in ("production_events", "production_dialogue_events"):
                conn.execute(
                    f"""
                    INSERT OR REPLACE INTO {table} (
                        id, stage, title, description, npc_type,
                        npc_traits_json, npc_line, trigger_json, choices_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    dialogue_values,
                )
            random_values = (
                event["id"],
                event_category,
                event_stage,
                event_scope,
                event_title,
                event_description,
                event.get("fixedLevel", "dynamic"),
                event.get("weight", 100),
                event.get("cooldownMonths", 0),
                event.get("npcType"),
                npc_traits_json,
                event.get("npcLine"),
                dumps_json(event_trigger),
                dumps_json(event_choices),
            )
            for table in ("simulation_events", "production_random_events"):
                conn.execute(
                    f"""
                    INSERT OR REPLACE INTO {table} (
                        id, category, stage, scope, title, description,
                        fixed_level, weight, cooldown_months, npc_type,
                        npc_traits_json, npc_line, trigger_json, choices_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    random_values,
                )
            for choice in event.get("choices", []):
                conn.execute(
                    """
                    INSERT OR REPLACE INTO production_choices (
                        event_id, choice_id, choice_text, effects_json
                    ) VALUES (?, ?, ?, ?)
                    """,
                    (
                        event["id"],
                        choice["id"],
                        choice["text"],
                        dumps_json(_choice_effect_summary(choice)),
                    ),
                )

        conn.commit()


def ensure_database(path: Path | str | None = None) -> None:
    db_path = _resolve_database_path(path)
    _copy_bundled_master_database_if_missing(db_path)
    initialize_database(db_path)
    with get_connection(db_path) as conn:
        row = conn.execute("SELECT COUNT(*) AS count FROM eras").fetchone()
    if not row or row["count"] == 0:
        seed_database(db_path, reset_static=True)


def _copy_bundled_master_database_if_missing(db_path: Path) -> None:
    if db_path.exists():
        return
    bundled_db = RESOURCE_DIR / "data" / "game.db"
    if not bundled_db.is_file():
        return
    try:
        if bundled_db.resolve() == db_path.resolve():
            return
    except FileNotFoundError:
        pass
    db_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(bundled_db, db_path)


def fetch_all(table_name: str, order_by: str = "name") -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(f"SELECT * FROM {table_name} ORDER BY {order_by}").fetchall()
    return [dict(row) for row in rows]
