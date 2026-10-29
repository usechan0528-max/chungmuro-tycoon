from __future__ import annotations

import sys
import traceback
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Iterator

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - requirements.txt provides python-dotenv.
    def load_dotenv(*_args: object, **_kwargs: object) -> bool:
        return False


LOG_DIR = ROOT_DIR / "logs"
FETCH_ERROR_LOG = LOG_DIR / "fetch_errors.log"


def load_project_env() -> None:
    load_dotenv(ROOT_DIR / ".env")


def initialize_sample_seed(reason: str) -> None:
    from app.config import DB_PATH
    from app.database import initialize_database, seed_database

    initialize_database(DB_PATH, reset=True)
    seed_database(DB_PATH, reset_static=True)
    print(f"{reason} Sample seed DB initialized: {DB_PATH}")


def log_fetch_error(context: str, exc: BaseException) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().isoformat(timespec="seconds")
    message = [
        f"[{timestamp}] {context}",
        f"{type(exc).__name__}: {exc}",
        "".join(traceback.format_exception(type(exc), exc, exc.__traceback__)),
        "",
    ]
    with FETCH_ERROR_LOG.open("a", encoding="utf-8") as file:
        file.write("\n".join(message))


def iter_dates(start_yyyymmdd: str, end_yyyymmdd: str) -> Iterator[str]:
    start = datetime.strptime(start_yyyymmdd, "%Y%m%d").date()
    end = datetime.strptime(end_yyyymmdd, "%Y%m%d").date()
    current = start
    while current <= end:
        yield current.strftime("%Y%m%d")
        current += timedelta(days=1)


def year_bounds(year: int) -> tuple[str, str]:
    return date(year, 1, 1).strftime("%Y%m%d"), date(year, 12, 31).strftime("%Y%m%d")
