from __future__ import annotations

import argparse

from _fetch_common import load_project_env, log_fetch_error

from app.database import initialize_database
from app.services.data_collection_service import (
    CollectionError,
    build_ticket_prices_from_daily_boxoffice,
    build_ticket_prices_from_yearly_totals,
    import_kobis_yearly_totals_csv,
)
from app.services.ticket_price_service import ensure_ticket_price_history


def main() -> int:
    load_project_env()
    initialize_database()

    parser = argparse.ArgumentParser(description="Build average ticket prices from KOBIS yearly totals.")
    parser.add_argument("--csv", help="CSV with year,total_sales,total_audience columns.")
    parser.add_argument("--year", type=int, help="Restrict build to one year.")
    parser.add_argument(
        "--from-daily",
        action="store_true",
        help="Derive from collected daily box office rows. Use only when the collected rows cover the full year.",
    )
    args = parser.parse_args()

    try:
        if args.csv:
            imported = import_kobis_yearly_totals_csv(args.csv)
            built = build_ticket_prices_from_yearly_totals(args.year)
            count = max(imported, built)
        elif args.from_daily:
            if not args.year:
                raise CollectionError("--from-daily는 --year가 필요합니다.")
            count = build_ticket_prices_from_daily_boxoffice(args.year)
        else:
            count = build_ticket_prices_from_yearly_totals(args.year)
        start_year = args.year if args.year else 1980
        end_year = args.year if args.year else 2035
        fallback = ensure_ticket_price_history(start_year, end_year)
    except CollectionError as exc:
        log_fetch_error("build_ticket_prices", exc)
        print(f"build failed: {exc}")
        return 1

    print(f"stored {count} ticket price rows")
    print(
        "ensured ticket price history: "
        f"kobis={fallback['kobis']}, "
        f"market_reports={fallback['market_reports']}, "
        f"cpi_estimates={fallback['cpi_estimates']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
