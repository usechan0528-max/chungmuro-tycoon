from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from app.config import DB_PATH

_default_database_path = DB_PATH


def dumps_json(value: Any) -> str:
    return json.dumps({} if value is None else value, ensure_ascii=False)


def loads_json(value: str | None, default: Any = None) -> Any:
    if not value:
        return {} if default is None else default
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return {} if default is None else default


def set_default_database_path(path: Path | str) -> None:
    global _default_database_path
    _default_database_path = Path(path)


def default_database_path() -> Path:
    return _default_database_path


def _resolve_database_path(path: Path | str | None = None) -> Path:
    return Path(path) if path is not None else _default_database_path


def get_connection(path: Path | str | None = None) -> sqlite3.Connection:
    db_path = _resolve_database_path(path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn
