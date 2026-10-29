from __future__ import annotations

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.config import DB_PATH
from app.database import get_connection, seed_database
from app.services.economic_service import rebuild_economic_yearly_indicators
from app.services.people_stat_service import estimate_and_store_people_stats
from app.services.ticket_price_service import ensure_ticket_price_history


def main() -> None:
    seed_database(DB_PATH, reset_static=True)
    economic_count = rebuild_economic_yearly_indicators(1980, 2035)
    ticket_result = ensure_ticket_price_history(1980, 2035)
    result = estimate_and_store_people_stats()
    print(f"Seeded database: {DB_PATH}")
    for label, count in _import_counts().items():
        print(f"  {label}: {count}")
    print(
        "Estimated people stats: "
        f"actors={result['actor']}, directors={result['director']}, "
        f"matched_source_data={result['with_source_data']}"
    )
    print(f"Built economic indicators: {economic_count}")
    print(
        "Built ticket prices: "
        f"kobis={ticket_result['kobis']}, "
        f"market_reports={ticket_result['market_reports']}, "
        f"cpi_estimates={ticket_result['cpi_estimates']}"
    )


def _import_counts() -> dict[str, int]:
    with get_connection(DB_PATH) as conn:
        counts = {
            "stats": _first_existing_table_count(conn, ("stats", "stat_definitions", "core_stats")),
            "genres": _table_count(conn, "genres"),
            "project_scales": _table_count(conn, "project_scales"),
            "era_rules": _table_count(conn, "era_rules"),
            "history_events": _table_count(conn, "historical_events"),
            "history_distribution_events": _table_count(conn, "history_distribution_events"),
            "history_theater_events": _table_count(conn, "history_theater_events"),
            "history_premium_format_events": _table_count(conn, "history_premium_format_events"),
            "market_yearly_stats": _table_count(conn, "market_yearly_stats"),
            "economic_yearly_indicators": _table_count(conn, "economic_yearly_indicators"),
            "production_events": _simulation_count(conn, "production"),
            "dialogue_events": _simulation_count(conn, "dialogue"),
        }
    return counts


def _table_count(conn, table_name: str) -> int:
    row = conn.execute(f"SELECT COUNT(*) AS count FROM {table_name}").fetchone()
    return int(row["count"] if row else 0)


def _first_existing_table_count(conn, table_names: tuple[str, ...]) -> int:
    for table_name in table_names:
        exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
            (table_name,),
        ).fetchone()
        if exists:
            return _table_count(conn, table_name)
    return 0


def _simulation_count(conn, category: str) -> int:
    row = conn.execute(
        "SELECT COUNT(*) AS count FROM simulation_events WHERE category = ?",
        (category,),
    ).fetchone()
    return int(row["count"] if row else 0)


if __name__ == "__main__":
    main()
