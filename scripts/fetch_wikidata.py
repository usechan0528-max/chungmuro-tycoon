from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.database import initialize_database
from app.services.data_collection_service import (
    CollectionError,
    collect_wikidata_sparql,
    collect_wikidata_target,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch supplemental film data from Wikidata SPARQL.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    target = subparsers.add_parser("target", help="Run a built-in Wikidata target query.")
    target.add_argument("target_id", choices=["korean-films", "korean-film-people"])
    target.add_argument("--limit", type=int, default=100)

    sparql = subparsers.add_parser("sparql", help="Run a SPARQL query file.")
    sparql.add_argument("--target-id", required=True)
    sparql.add_argument("--entity-type")
    sparql.add_argument("--query-file", type=Path, required=True)

    args = parser.parse_args()
    initialize_database()

    try:
        if args.command == "target":
            count = collect_wikidata_target(args.target_id, limit=args.limit)
        elif args.command == "sparql":
            count = collect_wikidata_sparql(
                args.target_id,
                args.query_file.read_text(encoding="utf-8"),
                entity_type=args.entity_type,
            )
        else:
            parser.error(f"Unknown command: {args.command}")
            return 2
    except CollectionError as exc:
        print(f"collection error: {exc}", file=sys.stderr)
        return 1

    print(f"imported {count} Wikidata rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
