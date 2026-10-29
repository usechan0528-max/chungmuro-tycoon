from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.database import initialize_database
from app.services.annual_report_service import (
    build_and_store_annual_report,
    list_report_source_years,
)


def main() -> int:
    initialize_database()

    parser = argparse.ArgumentParser(description="Build yearly Korean film industry report snapshots.")
    parser.add_argument("--year", type=int, help="Build one report year.")
    parser.add_argument("--from-year", type=int, help="First report year for a range.")
    parser.add_argument("--to-year", type=int, help="Last report year for a range.")
    parser.add_argument("--all-available", action="store_true", help="Build every year with source rows.")
    parser.add_argument("--list-years", action="store_true", help="Print source years without building.")
    args = parser.parse_args()

    source_years = list_report_source_years()
    if args.list_years:
        print(" ".join(str(year) for year in source_years))
        return 0

    years = _select_years(args, source_years)
    if not years:
        print("no report years selected")
        return 0

    for year in years:
        report = build_and_store_annual_report(year)
        summary = report["sourceSummary"]
        print(
            f"{year}: boxoffice_rows={summary['boxofficeRows']} "
            f"awards={summary['awardRows']} precision={summary['precision']}"
        )
    return 0


def _select_years(args: argparse.Namespace, source_years: list[int]) -> list[int]:
    if args.all_available:
        return source_years
    if args.year:
        return [args.year]
    if args.from_year and args.to_year:
        if args.from_year > args.to_year:
            raise SystemExit("--from-year는 --to-year보다 클 수 없습니다.")
        return list(range(args.from_year, args.to_year + 1))
    if source_years:
        return [source_years[-1]]
    return []


if __name__ == "__main__":
    raise SystemExit(main())
