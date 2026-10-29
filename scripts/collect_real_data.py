from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.database import initialize_database
from app.services.annual_report_service import build_and_store_annual_report, list_report_source_years
from app.services.data_collection_service import (
    CollectionError,
    collect_kmdb_movies,
    collect_kobis_daily_boxoffice,
    collect_kosis_statistics,
    collect_wikidata_sparql,
    collect_wikidata_target,
    import_kmdb_json_dump,
    import_kobis_yearly_totals_csv,
    import_kofic_report_directory,
    import_kofic_actors200_csv,
    search_kosis_statistics,
)
from app.services.data_collection_targets import KMDB_KOREAN_MOVIE_START_YEAR


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect or import real Korean film data into staging tables.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    kmdb = subparsers.add_parser("kmdb-movies", help="Collect KMDb movie metadata.")
    kmdb.add_argument("--query", default="", help="KMDb search query.")
    kmdb.add_argument("--year", type=int, help="Release year filter.")
    kmdb.add_argument("--list-count", type=int, default=100)
    kmdb.add_argument("--start-count", type=int, default=0)

    kmdb_json = subparsers.add_parser("kmdb-json", help="Import a local KMDb JSON dump.")
    kmdb_json.add_argument("path", type=Path)
    kmdb_json.add_argument("--from-year", type=int, default=KMDB_KOREAN_MOVIE_START_YEAR)
    kmdb_json.add_argument("--to-year", type=int)
    kmdb_json.add_argument("--include-non-korean", action="store_true")
    kmdb_json.add_argument("--limit", type=int)

    kobis_daily = subparsers.add_parser("kobis-daily", help="Collect KOBIS daily box office.")
    kobis_daily.add_argument("--date", required=True, help="Target date in YYYYMMDD format.")
    kobis_daily.add_argument("--rep-nation-code", help="Optional KOBIS nation code, e.g. K for Korean films.")
    kobis_daily.add_argument("--movie-type-code", help="Optional KOBIS movie type code.")

    kosis_search = subparsers.add_parser("kosis-search", help="Search KOSIS statistics tables.")
    kosis_search.add_argument("--keyword", required=True)
    kosis_search.add_argument("--org-id")
    kosis_search.add_argument("--result-count", type=int, default=20)

    kosis_data = subparsers.add_parser("kosis-data", help="Collect one KOSIS statistics table.")
    kosis_data.add_argument("--target-id", required=True)
    kosis_data.add_argument("--category")
    kosis_data.add_argument("--org-id", required=True)
    kosis_data.add_argument("--tbl-id", required=True)
    kosis_data.add_argument("--prd-se", default="Y")
    kosis_data.add_argument("--start", dest="start_prd_de")
    kosis_data.add_argument("--end", dest="end_prd_de")
    kosis_data.add_argument("--newest", dest="new_est_prd_cnt", type=int)
    kosis_data.add_argument("--param", action="append", default=[])

    ticket_prices = subparsers.add_parser(
        "ticket-prices-csv",
        help="Import KOBIS yearly total sales/audience CSV and derive average ticket prices.",
    )
    ticket_prices.add_argument("path", type=Path)

    actors200 = subparsers.add_parser("actors200-csv", help="Import curated KOFIC Korean Actors 200 CSV.")
    actors200.add_argument("path", type=Path)

    kofic_reports = subparsers.add_parser("kofic-reports", help="Import local KOFIC settlement/statistics files.")
    kofic_reports.add_argument("--downloads", type=Path, default=Path.home() / "Downloads")
    kofic_reports.add_argument("--output-dir", type=Path)
    kofic_reports.add_argument("--from-year", type=int, default=2000)
    kofic_reports.add_argument("--to-year", type=int, default=2026)
    kofic_reports.add_argument("--limit", type=int)
    kofic_reports.add_argument("--promote-events", action="store_true")

    wikidata_target = subparsers.add_parser("wikidata-target", help="Collect a built-in Wikidata SPARQL target.")
    wikidata_target.add_argument("target_id", choices=["korean-films", "korean-film-people"])
    wikidata_target.add_argument("--limit", type=int, default=100)

    wikidata_sparql = subparsers.add_parser("wikidata-sparql", help="Collect Wikidata rows from a SPARQL query file.")
    wikidata_sparql.add_argument("--target-id", required=True)
    wikidata_sparql.add_argument("--entity-type")
    wikidata_sparql.add_argument("--query-file", type=Path, required=True)

    annual_reports = subparsers.add_parser("annual-reports", help="Build yearly industry report snapshots.")
    annual_reports.add_argument("--year", type=int)
    annual_reports.add_argument("--from-year", type=int)
    annual_reports.add_argument("--to-year", type=int)
    annual_reports.add_argument("--all-available", action="store_true")

    args = parser.parse_args()
    initialize_database()

    try:
        if args.command == "kmdb-movies":
            count = collect_kmdb_movies(
                query=args.query,
                year=args.year,
                list_count=args.list_count,
                start_count=args.start_count,
            )
        elif args.command == "kmdb-json":
            count = import_kmdb_json_dump(
                args.path,
                korean_only=not args.include_non_korean,
                from_year=args.from_year,
                to_year=args.to_year,
                limit=args.limit,
            )
        elif args.command == "kobis-daily":
            count = collect_kobis_daily_boxoffice(
                target_date=args.date,
                rep_nation_code=args.rep_nation_code,
                movie_type_code=args.movie_type_code,
            )
        elif args.command == "kosis-search":
            count = search_kosis_statistics(
                args.keyword,
                org_id=args.org_id,
                result_count=args.result_count,
            )
        elif args.command == "kosis-data":
            count = collect_kosis_statistics(
                target_id=args.target_id,
                category=args.category,
                org_id=args.org_id,
                tbl_id=args.tbl_id,
                prd_se=args.prd_se,
                start_prd_de=args.start_prd_de,
                end_prd_de=args.end_prd_de,
                new_est_prd_cnt=args.new_est_prd_cnt,
                params=_parse_params(args.param),
            )
        elif args.command == "ticket-prices-csv":
            count = import_kobis_yearly_totals_csv(args.path)
        elif args.command == "actors200-csv":
            count = import_kofic_actors200_csv(args.path)
        elif args.command == "kofic-reports":
            count = import_kofic_report_directory(
                args.downloads,
                output_dir=args.output_dir,
                year_from=args.from_year,
                year_to=args.to_year,
                limit=args.limit,
                promote_events=args.promote_events,
            )
        elif args.command == "wikidata-target":
            count = collect_wikidata_target(args.target_id, limit=args.limit)
        elif args.command == "wikidata-sparql":
            count = collect_wikidata_sparql(
                args.target_id,
                args.query_file.read_text(encoding="utf-8"),
                entity_type=args.entity_type,
            )
        elif args.command == "annual-reports":
            years = _annual_report_years(args)
            for year in years:
                build_and_store_annual_report(year)
            count = len(years)
        else:
            parser.error(f"Unknown command: {args.command}")
            return 2
    except CollectionError as exc:
        print(f"collection error: {exc}", file=sys.stderr)
        return 1

    print(f"imported {count} rows")
    return 0


def _parse_params(pairs: list[str]) -> dict[str, str]:
    params: dict[str, str] = {}
    for pair in pairs:
        if "=" not in pair:
            raise CollectionError(f"--param must be key=value: {pair}")
        key, value = pair.split("=", 1)
        params[key] = value
    return params


def _annual_report_years(args: argparse.Namespace) -> list[int]:
    source_years = list_report_source_years()
    if args.all_available:
        return source_years
    if args.year:
        return [args.year]
    if args.from_year and args.to_year:
        if args.from_year > args.to_year:
            raise CollectionError("--from-year는 --to-year보다 클 수 없습니다.")
        return list(range(args.from_year, args.to_year + 1))
    return [source_years[-1]] if source_years else []


if __name__ == "__main__":
    raise SystemExit(main())
