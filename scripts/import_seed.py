from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.config import DB_PATH
from app.database import initialize_database, seed_database
from app.services.people_stat_service import estimate_and_store_people_stats


def main() -> int:
    parser = argparse.ArgumentParser(description="Initialize the game DB from bundled sample JSON seed data.")
    parser.add_argument("--keep-db", action="store_true", help="Do not delete the existing SQLite file first.")
    args = parser.parse_args()

    initialize_database(DB_PATH, reset=not args.keep_db)
    seed_database(DB_PATH, reset_static=True)
    result = estimate_and_store_people_stats()
    print(f"Imported bundled seed data into {DB_PATH}")
    print(
        "Estimated people stats: "
        f"actors={result['actor']}, directors={result['director']}, "
        f"matched_source_data={result['with_source_data']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
