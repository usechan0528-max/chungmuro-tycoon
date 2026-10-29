from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.config import DB_PATH
from app.database import initialize_database
from app.services.data_collection_service import CollectionError, import_kofic_report_directory


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Import local KOFIC Korean film industry settlement/statistics files into staging tables."
    )
    parser.add_argument("--downloads", type=Path, default=Path.home() / "Downloads")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--from-year", type=int, default=2000)
    parser.add_argument("--to-year", type=int, default=2026)
    parser.add_argument("--limit", type=int)
    parser.add_argument(
        "--promote-events",
        action="store_true",
        help="Also promote extracted event candidates into history_market_events. Use after manual review.",
    )
    args = parser.parse_args()

    initialize_database()
    try:
        file_count = import_kofic_report_directory(
            args.downloads,
            output_dir=args.output_dir,
            year_from=args.from_year,
            year_to=args.to_year,
            limit=args.limit,
            promote_events=args.promote_events,
        )
    except CollectionError as exc:
        print(f"collection error: {exc}", file=sys.stderr)
        return 1

    summary = _load_summary()
    print(f"indexed {file_count} KOFIC report files")
    print(
        "staging summary: "
        f"{summary['files']} files, {summary['metrics']} metric candidates, "
        f"{summary['events']} event candidates, {summary['market_yearly_stats']} market yearly stats"
    )
    return 0


def _load_summary() -> dict[str, int]:
    with sqlite3.connect(DB_PATH) as conn:
        return {
            "files": _count(conn, "staging_kofic_report_files"),
            "metrics": _count(conn, "staging_kofic_industry_metrics"),
            "events": _count(conn, "staging_kofic_report_events"),
            "market_yearly_stats": _count(conn, "market_yearly_stats"),
        }


def _count(conn: sqlite3.Connection, table: str) -> int:
    return int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])


if __name__ == "__main__":
    raise SystemExit(main())
