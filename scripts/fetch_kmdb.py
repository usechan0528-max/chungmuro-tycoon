from __future__ import annotations

import argparse
from pathlib import Path

from _fetch_common import initialize_sample_seed, load_project_env, log_fetch_error

from app.database import get_connection, initialize_database
from app.services.data_collection_service import (
    CollectionConfig,
    CollectionError,
    collect_kmdb_movies,
    import_kmdb_json_dump,
)
from app.services.data_collection_targets import KMDB_KOREAN_MOVIE_START_YEAR, current_collection_year


def main() -> int:
    load_project_env()
    initialize_database()

    parser = argparse.ArgumentParser(description="Fetch KMDb movie metadata.")
    parser.add_argument("--query", default="", help="KMDb search query.")
    parser.add_argument("--year", type=int, help="Release year filter.")
    parser.add_argument("--from-year", type=int, help="Release year range start.")
    parser.add_argument("--to-year", type=int, help="Release year range end.")
    parser.add_argument("--list-count", type=int, default=100)
    parser.add_argument("--start-count", type=int, default=0)
    parser.add_argument("--max-pages", type=int, default=1)
    parser.add_argument("--korean-only", action="store_true", help="Store Korean films first by filtering KMDb nation fields.")
    parser.add_argument("--from-json", type=Path, help="Import a local KMDb JSON dump instead of calling the API.")
    parser.add_argument(
        "--include-non-korean",
        action="store_true",
        help="When used with --from-json, import every nation instead of the Korean-film default.",
    )
    parser.add_argument("--json-limit", type=int, help="Maximum rows to import from --from-json after filters.")
    parser.add_argument("--default-korean-range", action="store_true", help="Fetch 1980-current Korean film pages.")
    parser.add_argument(
        "--from-kobis",
        action="store_true",
        help="Fetch KMDb rows by using collected KOBIS movie names and production/open years.",
    )
    parser.add_argument("--limit", type=int, default=100, help="KOBIS rows to use with --from-kobis.")
    args = parser.parse_args()
    config = CollectionConfig.from_env()
    if args.from_json:
        try:
            count = import_kmdb_json_dump(
                args.from_json,
                korean_only=not args.include_non_korean,
                from_year=args.from_year if args.from_year is not None else KMDB_KOREAN_MOVIE_START_YEAR,
                to_year=args.to_year,
                limit=args.json_limit,
            )
        except CollectionError as exc:
            log_fetch_error("fetch_kmdb_json", exc)
            print(f"import failed: {exc}")
            return 1
        print(f"stored {count} rows from local KMDb JSON")
        return 0

    if not config.kmdb_api_key:
        initialize_sample_seed("KMDB_API_KEY is missing; skipped KMDb collection.")
        return 0

    try:
        if args.from_kobis:
            count = _fetch_from_kobis_staging(args.limit, args.list_count)
        elif args.default_korean_range:
            count = _fetch_year_range(
                from_year=KMDB_KOREAN_MOVIE_START_YEAR,
                to_year=current_collection_year(),
                list_count=args.list_count,
                max_pages=args.max_pages,
                korean_only=True,
            )
        elif args.from_year or args.to_year:
            count = _fetch_year_range(
                from_year=args.from_year or KMDB_KOREAN_MOVIE_START_YEAR,
                to_year=args.to_year or current_collection_year(),
                list_count=args.list_count,
                max_pages=args.max_pages,
                korean_only=args.korean_only,
            )
        else:
            count = collect_kmdb_movies(
                query=args.query,
                year=args.year,
                list_count=args.list_count,
                start_count=args.start_count,
                korean_only=args.korean_only,
            )
    except CollectionError as exc:
        log_fetch_error("fetch_kmdb", exc)
        print(f"fetch failed: {exc}")
        return 1

    print(f"stored {count} rows")
    return 0


def _fetch_from_kobis_staging(limit: int, list_count: int) -> int:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT
                movie_name_ko,
                COALESCE(
                    NULLIF(substr(open_date, 1, 4), ''),
                    NULLIF(production_year, 0)
                ) AS match_year
            FROM staging_kobis_movie_list
            WHERE movie_name_ko IS NOT NULL AND movie_name_ko != ''
            ORDER BY movie_code
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    count = 0
    for row in rows:
        year = int(row["match_year"]) if row["match_year"] else None
        count += collect_kmdb_movies(query=row["movie_name_ko"], year=year, list_count=list_count, korean_only=True)
    return count


def _fetch_year_range(from_year: int, to_year: int, list_count: int, max_pages: int, korean_only: bool) -> int:
    if from_year > to_year:
        raise CollectionError("--from-year는 --to-year보다 클 수 없습니다.")
    count = 0
    for year in range(from_year, to_year + 1):
        for page in range(max_pages):
            fetched = collect_kmdb_movies(
                year=year,
                list_count=list_count,
                start_count=page * list_count,
                korean_only=korean_only,
            )
            count += fetched
            if fetched == 0:
                break
    return count


if __name__ == "__main__":
    raise SystemExit(main())
