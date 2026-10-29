from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.database import dumps_json, get_connection, initialize_database


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Promote collected KOBIS yearly box office rows into major Korean movie candidates."
    )
    parser.add_argument("--target", type=int, default=500)
    parser.add_argument("--from-year", type=int)
    parser.add_argument("--to-year", type=int)
    args = parser.parse_args()

    initialize_database()
    count = promote_major_korean_movies(args.target, args.from_year, args.to_year)
    print(f"promoted {count} KOBIS yearly major Korean movie candidates")
    return 0


def promote_major_korean_movies(target: int, from_year: int | None, to_year: int | None) -> int:
    conditions = ["(d.nations_json LIKE '%한국%' OR l.representative_nation = '한국' OR l.nation_alt LIKE '%한국%')"]
    params: list[Any] = []
    if from_year is not None:
        conditions.append("y.year >= ?")
        params.append(from_year)
    if to_year is not None:
        conditions.append("y.year <= ?")
        params.append(to_year)

    query = f"""
        SELECT
            y.year,
            y.movie_code,
            y.movie_name,
            y.normalized_title,
            y.open_date,
            y.sales_amount,
            y.audience_count,
            y.screen_count,
            y.show_count,
            y.raw_json AS yearly_raw_json,
            d.movie_name_ko,
            d.companies_json,
            d.nations_json,
            d.genres_json,
            l.representative_nation,
            l.nation_alt
        FROM staging_kobis_yearly_boxoffice y
        LEFT JOIN staging_kobis_movie_details d ON d.movie_code = y.movie_code
        LEFT JOIN staging_kobis_movie_list l ON l.movie_code = y.movie_code
        WHERE {" AND ".join(conditions)}
        ORDER BY y.audience_count DESC, y.year DESC
    """

    candidates: dict[str, dict[str, Any]] = {}
    with get_connection() as conn:
        rows = conn.execute(query, params).fetchall()
        yearly_rank = _yearly_rank_map(rows)
        for row in rows:
            key = str(row["movie_code"])
            current = candidates.get(key)
            if current is None or int(row["audience_count"] or 0) > int(current["max_annual_audience"] or 0):
                candidates[key] = {
                    "source": "kobis_daily_yearly_boxoffice",
                    "source_movie_code": row["movie_code"],
                    "title": row["movie_name_ko"] or row["movie_name"],
                    "normalized_title": row["normalized_title"],
                    "representative_year": _year_from_open_date(row["open_date"]) or row["year"],
                    "first_seen_year": row["year"],
                    "last_seen_year": row["year"],
                    "release_date": row["open_date"],
                    "country": "한국",
                    "distributor": _representative_distributor(row["companies_json"]),
                    "max_annual_rank": yearly_rank.get((row["year"], row["movie_code"])),
                    "max_annual_audience": int(row["audience_count"] or 0),
                    "max_annual_gross_text": str(row["sales_amount"] or ""),
                    "max_annual_screens": int(row["screen_count"] or 0),
                    "source_url": "KOBIS daily box office API",
                    "raw": {
                        "yearlyRows": [
                            {
                                "year": row["year"],
                                "movieCode": row["movie_code"],
                                "audience": row["audience_count"],
                                "sales": row["sales_amount"],
                                "screenCount": row["screen_count"],
                                "showCount": row["show_count"],
                                "genres": row["genres_json"],
                                "nations": row["nations_json"],
                            }
                        ]
                    },
                }
            else:
                current["first_seen_year"] = min(current["first_seen_year"], row["year"])
                current["last_seen_year"] = max(current["last_seen_year"], row["year"])
                current["raw"]["yearlyRows"].append(
                    {
                        "year": row["year"],
                        "movieCode": row["movie_code"],
                        "audience": row["audience_count"],
                        "sales": row["sales_amount"],
                        "screenCount": row["screen_count"],
                        "showCount": row["show_count"],
                        "genres": row["genres_json"],
                        "nations": row["nations_json"],
                    }
                )

        selected = sorted(
            candidates.values(),
            key=lambda item: (int(item["max_annual_audience"] or 0), int(item["representative_year"] or 0)),
            reverse=True,
        )[:target]
        conn.execute("DELETE FROM staging_major_korean_movies WHERE source = 'kobis_daily_yearly_boxoffice'")
        for movie in selected:
            conn.execute(
                """
                INSERT OR REPLACE INTO staging_major_korean_movies (
                    id, source, source_movie_code, title, normalized_title,
                    representative_year, first_seen_year, last_seen_year,
                    release_date, country, distributor, max_annual_rank,
                    max_annual_audience, max_annual_gross_text,
                    max_annual_screens, source_url, raw_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"korean_major_kobis_{movie['source_movie_code']}",
                    movie["source"],
                    movie["source_movie_code"],
                    movie["title"],
                    movie["normalized_title"],
                    movie["representative_year"],
                    movie["first_seen_year"],
                    movie["last_seen_year"],
                    movie["release_date"],
                    movie["country"],
                    movie["distributor"],
                    movie["max_annual_rank"],
                    movie["max_annual_audience"],
                    movie["max_annual_gross_text"],
                    movie["max_annual_screens"],
                    movie["source_url"],
                    dumps_json(movie["raw"]),
                ),
            )
        conn.commit()
    return len(selected)


def _yearly_rank_map(rows: list[Any]) -> dict[tuple[int, str], int]:
    grouped: dict[int, list[Any]] = {}
    for row in rows:
        grouped.setdefault(int(row["year"]), []).append(row)
    ranks: dict[tuple[int, str], int] = {}
    for year, year_rows in grouped.items():
        sorted_rows = sorted(year_rows, key=lambda item: int(item["audience_count"] or 0), reverse=True)
        for index, row in enumerate(sorted_rows, start=1):
            ranks[(year, str(row["movie_code"]))] = index
    return ranks


def _year_from_open_date(value: str | None) -> int | None:
    if not value or len(value) < 4:
        return None
    try:
        return int(value[:4])
    except ValueError:
        return None


def _representative_distributor(companies_json: str | None) -> str | None:
    if not companies_json:
        return None
    # Keep this deliberately light: company roles differ across KOBIS payloads, and the
    # raw JSON remains available for later richer distributor matching.
    return None


if __name__ == "__main__":
    raise SystemExit(main())
