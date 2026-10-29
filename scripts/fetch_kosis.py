from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from _fetch_common import load_project_env, log_fetch_error

from app.database import initialize_database
from app.services.data_collection_service import (
    CollectionConfig,
    CollectionError,
    collect_kosis_statistics,
    collect_kosis_target,
    search_kosis_statistics,
)
from app.services.economic_service import rebuild_economic_yearly_indicators


def main() -> int:
    load_project_env()
    initialize_database()

    parser = argparse.ArgumentParser(description="Fetch KOSIS economic, population, and culture statistics.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    search = subparsers.add_parser("search", help="Search KOSIS statistics tables.")
    search.add_argument("--keyword", required=True)
    search.add_argument("--org-id")
    search.add_argument("--result-count", type=int, default=20)
    search.add_argument("--start-count", type=int, default=1)
    search.add_argument("--sort", default="RANK", choices=["RANK", "DATE"])

    data = subparsers.add_parser("data", help="Fetch one KOSIS statistics table directly.")
    data.add_argument("--target-id", required=True)
    data.add_argument("--category")
    data.add_argument("--org-id", required=True)
    data.add_argument("--tbl-id", required=True)
    data.add_argument("--prd-se", default="Y")
    data.add_argument("--start", dest="start_prd_de")
    data.add_argument("--end", dest="end_prd_de")
    data.add_argument("--newest", dest="new_est_prd_cnt", type=int)
    data.add_argument(
        "--param",
        action="append",
        default=[],
        help="Additional KOSIS parameter as key=value, e.g. --param itmId=T --param objL1=ALL",
    )

    target = subparsers.add_parser("target", help="Fetch a named target from data/kosis_targets.json.")
    target.add_argument("target_id")
    target.add_argument("--start", dest="start_prd_de")
    target.add_argument("--end", dest="end_prd_de")
    target.add_argument("--newest", dest="new_est_prd_cnt", type=int)

    cpi = subparsers.add_parser("cpi", help="Fetch CPI and rebuild yearly economic adjustment indicators.")
    cpi.add_argument("--start", dest="start_prd_de", default="198001")
    cpi.add_argument("--end", dest="end_prd_de", default="202512")
    cpi.add_argument("--from-year", type=int, default=1980)
    cpi.add_argument("--to-year", type=int, default=2035)

    args = parser.parse_args()
    if not CollectionConfig.from_env().kosis_api_key:
        if args.command == "cpi":
            built = rebuild_economic_yearly_indicators(args.from_year, args.to_year)
            print(
                "KOSIS_API_KEY is missing; skipped CPI API collection and "
                f"rebuilt {built} fallback economic indicator rows."
            )
            return 0
        print("KOSIS_API_KEY is missing; skipped KOSIS collection. Existing DB was left unchanged.")
        return 0

    try:
        if args.command == "search":
            count = search_kosis_statistics(
                args.keyword,
                org_id=args.org_id,
                result_count=args.result_count,
                start_count=args.start_count,
                sort=args.sort,
            )
        elif args.command == "data":
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
        elif args.command == "target":
            count = collect_kosis_target(
                args.target_id,
                start_prd_de=args.start_prd_de,
                end_prd_de=args.end_prd_de,
                new_est_prd_cnt=args.new_est_prd_cnt,
            )
        elif args.command == "cpi":
            count = collect_kosis_target(
                "cpi_city_monthly",
                start_prd_de=args.start_prd_de,
                end_prd_de=args.end_prd_de,
            )
            built = rebuild_economic_yearly_indicators(args.from_year, args.to_year)
            print(f"rebuilt {built} yearly economic indicator rows")
        else:
            parser.error(f"Unknown command: {args.command}")
            return 2
    except CollectionError as exc:
        log_fetch_error("fetch_kosis", exc)
        print(f"fetch failed: {exc}")
        return 1

    print(f"stored {count} KOSIS rows")
    return 0


def _parse_params(pairs: list[str]) -> dict[str, str]:
    params: dict[str, str] = {}
    for pair in pairs:
        if "=" not in pair:
            raise CollectionError(f"--param must be key=value: {pair}")
        key, value = pair.split("=", 1)
        params[key] = value
    return params


if __name__ == "__main__":
    raise SystemExit(main())
