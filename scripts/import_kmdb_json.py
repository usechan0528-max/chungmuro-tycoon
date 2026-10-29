from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.database import initialize_database
from app.services.data_collection_service import CollectionError, import_kmdb_json_dump
from app.services.data_collection_targets import KMDB_KOREAN_MOVIE_START_YEAR


def main() -> int:
    parser = argparse.ArgumentParser(description="Import a local KMDb JSON dump into staging_kmdb_movies.")
    parser.add_argument("path", type=Path, help="Path to the KMDb JSON dump.")
    parser.add_argument("--from-year", type=int, default=KMDB_KOREAN_MOVIE_START_YEAR)
    parser.add_argument("--to-year", type=int)
    parser.add_argument("--include-non-korean", action="store_true", help="Import every nation instead of Korean films only.")
    parser.add_argument("--limit", type=int, help="Maximum rows to import after filters.")
    args = parser.parse_args()

    initialize_database()
    try:
        count = import_kmdb_json_dump(
            args.path,
            korean_only=not args.include_non_korean,
            from_year=args.from_year,
            to_year=args.to_year,
            limit=args.limit,
        )
    except CollectionError as exc:
        print(f"import failed: {exc}", file=sys.stderr)
        return 1

    print(f"imported {count} KMDb rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
