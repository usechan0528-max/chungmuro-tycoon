from __future__ import annotations

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.database import initialize_database
from app.services.people_stat_service import estimate_and_store_people_stats


def main() -> int:
    initialize_database()
    result = estimate_and_store_people_stats()
    print(
        "Estimated people stats: "
        f"actors={result['actor']}, directors={result['director']}, "
        f"matched_source_data={result['with_source_data']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
