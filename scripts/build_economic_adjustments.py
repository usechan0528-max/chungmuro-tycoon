from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.database import initialize_database
from app.services.economic_service import rebuild_economic_yearly_indicators


def main() -> int:
    parser = argparse.ArgumentParser(description="Build CPI-based yearly economic modifiers for gameplay.")
    parser.add_argument("--from-year", type=int, default=1980)
    parser.add_argument("--to-year", type=int, default=2035)
    args = parser.parse_args()

    initialize_database()
    count = rebuild_economic_yearly_indicators(args.from_year, args.to_year)
    print(f"rebuilt {count} economic indicator rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
