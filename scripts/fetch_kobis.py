from __future__ import annotations

import argparse

from _fetch_common import initialize_sample_seed, iter_dates, load_project_env, log_fetch_error, year_bounds

from app.database import initialize_database
from app.services.data_collection_service import (
    CollectionError,
    CollectionConfig,
    aggregate_kobis_yearly_boxoffice,
    collect_kobis_daily_boxoffice,
    collect_kobis_movie_details_from_staging,
    collect_kobis_movie_info,
    collect_kobis_movie_list,
)
from app.services.data_collection_targets import KOBIS_BOXOFFICE_START_YEAR, current_collection_year


def main() -> int:
    load_project_env()
    initialize_database()

    parser = argparse.ArgumentParser(description="Fetch KOBIS box office, movie codes, and movie details.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    daily = subparsers.add_parser("daily", help="Fetch daily box office rows.")
    daily.add_argument("--date", help="Single target date in YYYYMMDD.")
    daily.add_argument("--from-date", help="Start date in YYYYMMDD.")
    daily.add_argument("--to-date", help="End date in YYYYMMDD.")
    daily.add_argument("--rep-nation-code", help="Optional KOBIS nation code, e.g. K.")
    daily.add_argument("--movie-type-code", help="Optional KOBIS movie type code.")

    yearly = subparsers.add_parser("yearly", help="Fetch daily rows for a year and aggregate them by movie.")
    yearly.add_argument("--year", type=int, required=True)
    yearly.add_argument("--rep-nation-code", help="Optional KOBIS nation code, e.g. K.")
    yearly.add_argument("--movie-type-code", help="Optional KOBIS movie type code.")

    yearly_range = subparsers.add_parser(
        "yearly-range",
        help="Fetch daily rows for a year range and aggregate each year.",
    )
    yearly_range.add_argument("--from-year", type=int, default=KOBIS_BOXOFFICE_START_YEAR)
    yearly_range.add_argument("--to-year", type=int, default=current_collection_year())
    yearly_range.add_argument("--rep-nation-code", help="Optional KOBIS nation code, e.g. K.")
    yearly_range.add_argument("--movie-type-code", help="Optional KOBIS movie type code.")
    yearly_range.add_argument("--dry-run", action="store_true", help="Print planned request count without fetching.")

    aggregate = subparsers.add_parser("aggregate-yearly", help="Aggregate already collected daily rows by year.")
    aggregate.add_argument("--year", type=int, required=True)

    movie_list = subparsers.add_parser("movie-list", help="Fetch KOBIS movie code list.")
    movie_list.add_argument("--year", type=int, help="Production year filter.")
    movie_list.add_argument("--movie-name", help="Movie title search.")
    movie_list.add_argument("--open-start-date", help="Open start date in YYYYMMDD.")
    movie_list.add_argument("--open-end-date", help="Open end date in YYYYMMDD.")
    movie_list.add_argument("--page-start", type=int, default=1)
    movie_list.add_argument("--page-end", type=int, default=1)
    movie_list.add_argument("--item-per-page", type=int, default=100)
    movie_list.add_argument("--rep-nation-code", help="Optional KOBIS nation code, e.g. K.")
    movie_list.add_argument("--movie-type-code", help="Optional KOBIS movie type code.")

    movie_list_range = subparsers.add_parser("movie-list-range", help="Fetch KOBIS movie code lists by year range.")
    movie_list_range.add_argument("--from-year", type=int, default=KOBIS_BOXOFFICE_START_YEAR)
    movie_list_range.add_argument("--to-year", type=int, default=current_collection_year())
    movie_list_range.add_argument("--page-start", type=int, default=1)
    movie_list_range.add_argument("--page-end", type=int, default=5)
    movie_list_range.add_argument("--item-per-page", type=int, default=100)
    movie_list_range.add_argument("--rep-nation-code", help="Optional KOBIS nation code, e.g. K.")
    movie_list_range.add_argument("--movie-type-code", help="Optional KOBIS movie type code.")
    movie_list_range.add_argument("--dry-run", action="store_true", help="Print planned request count without fetching.")

    movie_info = subparsers.add_parser("movie-info", help="Fetch one KOBIS movie detail row.")
    movie_info.add_argument("--movie-code", required=True)

    details = subparsers.add_parser("details-from-staging", help="Fetch details for collected movie codes.")
    details.add_argument("--limit", type=int, default=100)
    details.add_argument("--include-existing", action="store_true")

    korean_details = subparsers.add_parser(
        "details-from-korean-list",
        help="Fetch details for collected Korean movie-list candidates.",
    )
    korean_details.add_argument("--limit", type=int, default=500)
    korean_details.add_argument("--from-year", type=int)
    korean_details.add_argument("--to-year", type=int)
    korean_details.add_argument(
        "--order",
        choices=("recent", "oldest"),
        default="recent",
        help="Collection order by production year.",
    )
    korean_details.add_argument("--include-existing", action="store_true")

    major_details = subparsers.add_parser("details-from-major", help="Fetch details for major Korean movie candidates.")
    major_details.add_argument("--limit", type=int, default=500)
    major_details.add_argument("--include-existing", action="store_true")

    args = parser.parse_args()
    config = CollectionConfig.from_env()
    if _requires_kobis_api(args.command) and not config.kobis_api_key:
        initialize_sample_seed("KOBIS_API_KEY is missing; skipped KOBIS collection.")
        return 0

    try:
        if args.command == "daily":
            dates = _daily_dates(args.date, args.from_date, args.to_date)
            count = 0
            for target_date in dates:
                count += collect_kobis_daily_boxoffice(
                    target_date=target_date,
                    rep_nation_code=args.rep_nation_code,
                    movie_type_code=args.movie_type_code,
                )
        elif args.command == "yearly":
            start, end = year_bounds(args.year)
            count = 0
            for target_date in iter_dates(start, end):
                count += collect_kobis_daily_boxoffice(
                    target_date=target_date,
                    rep_nation_code=args.rep_nation_code,
                    movie_type_code=args.movie_type_code,
                )
            aggregate_kobis_yearly_boxoffice(args.year)
        elif args.command == "yearly-range":
            if args.dry_run:
                planned = sum(1 for year in _year_range(args.from_year, args.to_year) for _date in iter_dates(*year_bounds(year)))
                print(f"planned {planned} daily KOBIS requests for {args.from_year}-{args.to_year}")
                return 0
            count = 0
            for year in _year_range(args.from_year, args.to_year):
                start, end = year_bounds(year)
                for target_date in iter_dates(start, end):
                    count += collect_kobis_daily_boxoffice(
                        target_date=target_date,
                        rep_nation_code=args.rep_nation_code,
                        movie_type_code=args.movie_type_code,
                    )
                aggregate_kobis_yearly_boxoffice(year)
        elif args.command == "aggregate-yearly":
            count = aggregate_kobis_yearly_boxoffice(args.year)
        elif args.command == "movie-list":
            count = 0
            for page in range(args.page_start, args.page_end + 1):
                count += collect_kobis_movie_list(
                    year=args.year,
                    movie_name=args.movie_name,
                    current_page=page,
                    item_per_page=args.item_per_page,
                    open_start_date=args.open_start_date,
                    open_end_date=args.open_end_date,
                    rep_nation_code=args.rep_nation_code,
                    movie_type_code=args.movie_type_code,
                )
        elif args.command == "movie-list-range":
            planned = (args.to_year - args.from_year + 1) * (args.page_end - args.page_start + 1)
            if args.dry_run:
                print(f"planned {planned} KOBIS movie-list requests for {args.from_year}-{args.to_year}")
                return 0
            count = 0
            for year in _year_range(args.from_year, args.to_year):
                for page in range(args.page_start, args.page_end + 1):
                    count += collect_kobis_movie_list(
                        year=year,
                        current_page=page,
                        item_per_page=args.item_per_page,
                        rep_nation_code=args.rep_nation_code,
                        movie_type_code=args.movie_type_code,
                    )
        elif args.command == "movie-info":
            count = collect_kobis_movie_info(args.movie_code)
        elif args.command == "details-from-staging":
            count = collect_kobis_movie_details_from_staging(
                limit=args.limit,
                missing_only=not args.include_existing,
            )
        elif args.command == "details-from-korean-list":
            count = _collect_korean_movie_list_details(
                limit=args.limit,
                from_year=args.from_year,
                to_year=args.to_year,
                order=args.order,
                missing_only=not args.include_existing,
            )
        elif args.command == "details-from-major":
            count = _collect_major_movie_details(
                limit=args.limit,
                missing_only=not args.include_existing,
            )
        else:
            parser.error(f"Unknown command: {args.command}")
            return 2
    except CollectionError as exc:
        log_fetch_error(f"fetch_kobis {args.command}", exc)
        print(f"fetch failed: {exc}")
        return 1

    print(f"stored {count} rows")
    return 0


def _requires_kobis_api(command: str) -> bool:
    return command in {
        "daily",
        "yearly",
        "yearly-range",
        "movie-list",
        "movie-list-range",
        "movie-info",
        "details-from-staging",
        "details-from-major",
    }


def _year_range(from_year: int, to_year: int) -> range:
    if from_year > to_year:
        raise CollectionError("--from-year는 --to-year보다 클 수 없습니다.")
    return range(from_year, to_year + 1)


def _daily_dates(single_date: str | None, from_date: str | None, to_date: str | None) -> list[str]:
    if single_date:
        return [single_date]
    if from_date and to_date:
        return list(iter_dates(from_date, to_date))
    raise CollectionError("--date 또는 --from-date/--to-date가 필요합니다.")


def _collect_major_movie_details(limit: int, missing_only: bool = True) -> int:
    from app.database import get_connection

    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT source_movie_code AS movie_code
            FROM staging_major_korean_movies
            WHERE source_movie_code IS NOT NULL AND source_movie_code != ''
            ORDER BY max_annual_audience DESC, representative_year DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        existing = set()
        if missing_only:
            existing = {
                row["movie_code"]
                for row in conn.execute("SELECT movie_code FROM staging_kobis_movie_details").fetchall()
            }
    count = 0
    for row in rows:
        movie_code = row["movie_code"]
        if missing_only and movie_code in existing:
            continue
        count += collect_kobis_movie_info(movie_code)
    return count


def _collect_korean_movie_list_details(
    *,
    limit: int,
    from_year: int | None = None,
    to_year: int | None = None,
    order: str = "recent",
    missing_only: bool = True,
) -> int:
    from app.database import get_connection

    order_direction = "DESC" if order == "recent" else "ASC"
    conditions = [
        "movie_code IS NOT NULL",
        "movie_code != ''",
        "(representative_nation = '한국' OR nation_alt LIKE '%한국%')",
    ]
    params: list[object] = []
    if from_year is not None:
        conditions.append("production_year >= ?")
        params.append(from_year)
    if to_year is not None:
        conditions.append("production_year <= ?")
        params.append(to_year)
    params.append(limit)

    with get_connection() as conn:
        rows = conn.execute(
            f"""
            SELECT movie_code
            FROM staging_kobis_movie_list
            WHERE {" AND ".join(conditions)}
            ORDER BY COALESCE(production_year, 0) {order_direction},
                     COALESCE(open_date, '') {order_direction},
                     movie_code {order_direction}
            LIMIT ?
            """,
            params,
        ).fetchall()
        existing = set()
        if missing_only:
            existing = {
                row["movie_code"]
                for row in conn.execute("SELECT movie_code FROM staging_kobis_movie_details").fetchall()
            }

    count = 0
    for row in rows:
        movie_code = row["movie_code"]
        if missing_only and movie_code in existing:
            continue
        count += collect_kobis_movie_info(movie_code)
    return count


if __name__ == "__main__":
    raise SystemExit(main())
