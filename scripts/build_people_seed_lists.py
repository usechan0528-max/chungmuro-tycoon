from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.database import get_connection, loads_json


PEOPLE_SEED_DIR = ROOT_DIR / "data" / "seed" / "people"
ACTORS_TARGET = 300
DIRECTORS_TARGET = 150
CRITICS_TARGET = 30


def main() -> int:
    PEOPLE_SEED_DIR.mkdir(parents=True, exist_ok=True)
    actors = _rank_people_from_major_movies("actors_json", ACTORS_TARGET)
    directors = _rank_people_from_major_movies("directors_json", DIRECTORS_TARGET)
    critics = _critic_names()

    _write_ranked_list(PEOPLE_SEED_DIR / "actors_seed_list.txt", actors, "actor", ACTORS_TARGET)
    _write_ranked_list(PEOPLE_SEED_DIR / "directors_seed_list.txt", directors, "director", DIRECTORS_TARGET)
    _write_critic_list(PEOPLE_SEED_DIR / "critics_seed_list.txt", critics)

    print(f"actors_seed_list.txt: {len(actors)} names")
    print(f"directors_seed_list.txt: {len(directors)} names")
    print(f"critics_seed_list.txt: {len(critics)} seeded names / target {CRITICS_TARGET}")
    return 0


def _rank_people_from_major_movies(json_column: str, target: int) -> list[dict[str, Any]]:
    stats: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"name": "", "appearances": 0, "best_audience": 0, "sample_titles": [], "seen_movies": set()}
    )
    with get_connection() as conn:
        rows = conn.execute(
            f"""
            SELECT
                m.source_movie_code,
                COALESCE(NULLIF(d.movie_name_ko, ''), m.title) AS display_title,
                m.max_annual_audience,
                d.{json_column}
            FROM staging_major_korean_movies m
            JOIN staging_kobis_movie_details d ON d.movie_code = m.source_movie_code
            ORDER BY m.max_annual_audience DESC
            """
        ).fetchall()

    for row in rows:
        names = loads_json(row[json_column], [])
        for raw_name in names:
            name = str(raw_name).strip()
            if not name:
                continue
            entry = stats[name]
            movie_code = str(row["source_movie_code"] or row["display_title"])
            if movie_code in entry["seen_movies"]:
                continue
            entry["seen_movies"].add(movie_code)
            entry["name"] = name
            entry["appearances"] += 1
            entry["best_audience"] = max(entry["best_audience"], int(row["max_annual_audience"] or 0))
            title = str(row["display_title"] or "").strip()
            if title and title not in entry["sample_titles"] and len(entry["sample_titles"]) < 3:
                entry["sample_titles"].append(title)

    ranked = sorted(
        stats.values(),
        key=lambda item: (item["appearances"], item["best_audience"], item["name"]),
        reverse=True,
    )
    return ranked[:target]


def _critic_names() -> list[str]:
    names: list[str] = []
    with get_connection() as conn:
        rows = conn.execute("SELECT name_ko FROM critics ORDER BY name_ko").fetchall()
    names.extend(row["name_ko"] for row in rows if row["name_ko"])
    if names:
        return names

    path = PEOPLE_SEED_DIR / "critics_major.json"
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return sorted(item["nameKo"] for item in data if item.get("nameKo"))


def _write_ranked_list(path: Path, rows: list[dict[str, Any]], person_type: str, target: int) -> None:
    lines = [
        f"# {path.name}",
        f"# type: {person_type}",
        f"# target_count: {target}",
        "# source: staging_major_korean_movies + staging_kobis_movie_details",
        "# format: rank<TAB>nameKo<TAB>major_movie_count<TAB>best_annual_audience<TAB>sample_titles",
    ]
    for index, row in enumerate(rows, start=1):
        sample_titles = "; ".join(row["sample_titles"])
        lines.append(
            f"{index}\t{row['name']}\t{row['appearances']}\t{row['best_audience']}\t{sample_titles}"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_critic_list(path: Path, names: list[str]) -> None:
    lines = [
        f"# {path.name}",
        "# type: critic",
        f"# target_count: {CRITICS_TARGET}",
        "# source: people/critics_major.json and current seeded DB",
        "# format: rank<TAB>nameKo<TAB>status",
    ]
    for index, name in enumerate(names, start=1):
        lines.append(f"{index}\t{name}\tseeded")
    for index in range(len(names) + 1, CRITICS_TARGET + 1):
        lines.append(f"{index}\tTODO_CRITIC_{index:03d}\tneeds_public_source")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
