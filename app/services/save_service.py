from __future__ import annotations

import shutil
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from app.config import DB_PATH, DEFAULT_SAVE_PATH, MIN_SAVE_SLOTS, SAVE_DIR
from app.database import default_database_path, ensure_database, get_connection, set_default_database_path


SAVE_RUNTIME_SCOPE: tuple[dict[str, Any], ...] = (
    {
        "id": "player_state",
        "label": "플레이어 상태",
        "tables": ("player_state", "save_player_state"),
    },
    {
        "id": "studio_state",
        "label": "제작사 상태",
        "tables": ("studio_state", "save_studio_state"),
    },
    {
        "id": "calendar",
        "label": "현재 연도/월",
        "tables": ("player_state", "save_player_state", "market_state", "save_market_state", "calendar_events"),
    },
    {
        "id": "active_projects",
        "label": "진행 중 프로젝트",
        "tables": (
            "projects",
            "production_projects",
            "project_scenario_development",
            "project_versions",
            "project_budget_allocations",
            "production_budget_allocations",
            "casting_offers",
            "project_people",
            "project_crew_roles",
            "project_location_plans",
            "shooting_schedule_blocks",
            "project_cashflows",
            "test_screenings",
            "reshoot_orders",
            "marketing_assets",
            "marketing_reactions",
            "stage_greeting_schedules",
            "project_distribution",
            "production_stage_logs",
            "theatrical_runs",
            "theatrical_daily_results",
            "project_financing",
        ),
    },
    {
        "id": "completed_films",
        "label": "완성 영화 목록",
        "tables": (
            "completed_films",
            "movies_player_created",
            "player_filmography_records",
            "movies_boxoffice",
            "movies_reviews",
            "movies_awards",
            "movies_post_release_metrics",
        ),
    },
    {
        "id": "reputation",
        "label": "명성",
        "tables": ("player_state", "save_player_state"),
        "json_fields": ("reputation_json",),
    },
    {
        "id": "network",
        "label": "인맥",
        "tables": ("player_state", "save_player_state"),
        "json_fields": ("network_json",),
    },
    {
        "id": "relationships",
        "label": "관계도",
        "tables": ("relationships", "people_relationships"),
    },
    {
        "id": "finance",
        "label": "대출/투자 장부",
        "tables": ("loans", "finance_transactions", "project_financing", "investment_contracts", "project_cashflows"),
    },
    {
        "id": "crew_work",
        "label": "현장 일거리 기록",
        "tables": ("crew_work_history",),
    },
    {
        "id": "history_flags",
        "label": "발생한 역사 이벤트 flag",
        "tables": ("save_event_flags", "event_history", "story_flags"),
    },
    {
        "id": "generated_future",
        "label": "생성된 미래 인물/영화",
        "tables": ("generated_entities", "save_generated_people", "save_generated_films"),
    },
)


def save_path_for_slot(slot: int) -> Path:
    if slot < 1:
        raise ValueError("세이브 슬롯은 1 이상이어야 합니다.")
    return SAVE_DIR / f"save_{slot:03d}.db"


def prepare_master_database() -> Path:
    ensure_database(DB_PATH)
    return DB_PATH


def start_new_runtime(slot: int = 1) -> Path:
    master_path = prepare_master_database()
    save_path = save_path_for_slot(slot)
    SAVE_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(master_path, save_path)
    set_default_database_path(save_path)
    ensure_database(save_path)
    return save_path


def use_save_slot_as_runtime(slot: int = 1) -> Path:
    save_path = save_path_for_slot(slot)
    if not save_path.exists():
        raise FileNotFoundError("저장 파일이 없습니다.")
    set_default_database_path(save_path)
    ensure_database(save_path)
    return save_path


def active_database_path() -> Path:
    return default_database_path()


def save_runtime_scope() -> list[dict[str, Any]]:
    return [
        {
            "id": item["id"],
            "label": item["label"],
            "tables": list(item["tables"]),
            **({"jsonFields": list(item["json_fields"])} if item.get("json_fields") else {}),
        }
        for item in SAVE_RUNTIME_SCOPE
    ]


def validate_save_runtime_scope(path: Path | None = None) -> list[dict[str, Any]]:
    db_path = path or active_database_path()
    ensure_database(db_path)
    missing: list[dict[str, Any]] = []
    with get_connection(db_path) as conn:
        for item in SAVE_RUNTIME_SCOPE:
            missing_tables = [
                table
                for table in item["tables"]
                if not _table_exists(conn, table)
            ]
            if missing_tables:
                missing.append(
                    {
                        "id": item["id"],
                        "label": item["label"],
                        "missingTables": missing_tables,
                    }
                )
    return missing


def sync_runtime_save_mirrors(path: Path | None = None) -> None:
    db_path = path or active_database_path()
    ensure_database(db_path)
    with get_connection(db_path) as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO save_player_state (
                id, name, gender, age, current_year, current_month, current_day, position,
                cash, debt, stats_json, reputation_json, network_json
            )
            SELECT
                id, name, gender, age, current_year, current_month, current_day, position,
                cash, debt, stats_json, reputation_json, network_json
            FROM player_state
            WHERE id = 1
            """
        )
        conn.execute(
            """
            INSERT OR REPLACE INTO save_studio_state (
                id, studio_name, fame, cash, debt,
                own_capital, investment_capital, loan_capital, loan_balance, credit_limit,
                field_reputation, pay_reputation, creative_freedom,
                interference_reputation, reputation_tags_json, reputation_summary
            )
            SELECT
                id, studio_name, fame, cash, debt,
                own_capital, investment_capital, loan_capital, loan_balance, credit_limit,
                field_reputation, pay_reputation, creative_freedom,
                interference_reputation, reputation_tags_json, reputation_summary
            FROM studio_state
            WHERE id = 1
            """
        )
        conn.execute(
            """
            INSERT OR REPLACE INTO save_market_state (
                year, month, theater_demand, ott_power, foreign_competition,
                korean_film_trust, genre_trends_json, modifiers_json
            )
            SELECT
                year, month, theater_demand, ott_power, foreign_competition,
                korean_film_trust, genre_trends_json, modifiers_json
            FROM market_state
            """
        )
        conn.commit()


def save_game(save_path: Path | None = None, *, slot: int = 1) -> Path:
    if save_path is None:
        save_path = save_path_for_slot(slot)
    source_path = active_database_path()
    ensure_database(source_path)
    sync_runtime_save_mirrors(source_path)
    missing = validate_save_runtime_scope(source_path)
    if missing:
        labels = ", ".join(item["label"] for item in missing)
        raise RuntimeError(f"세이브 DB 필수 범위가 누락되었습니다: {labels}")
    SAVE_DIR.mkdir(parents=True, exist_ok=True)
    if source_path.resolve() != save_path.resolve():
        shutil.copy2(source_path, save_path)
    return save_path


def load_game(save_path: Path | None = None, *, slot: int = 1) -> Path:
    if save_path is None:
        save_path = save_path_for_slot(slot)
    if not save_path.exists():
        raise FileNotFoundError("저장 파일이 없습니다.")
    set_default_database_path(save_path)
    ensure_database(save_path)
    sync_runtime_save_mirrors(save_path)
    return save_path


def has_save(save_path: Path = DEFAULT_SAVE_PATH) -> bool:
    return save_path.exists()


def has_save_slot(slot: int) -> bool:
    return save_path_for_slot(slot).exists()


def has_any_save() -> bool:
    return any(slot["exists"] for slot in list_save_slots())


def latest_save_slot() -> int | None:
    existing = [slot for slot in list_save_slots() if slot["exists"]]
    if not existing:
        return None
    return int(max(existing, key=lambda slot: slot["modified_timestamp"])["slot"])


def list_save_slots(min_slots: int = MIN_SAVE_SLOTS) -> list[dict[str, Any]]:
    SAVE_DIR.mkdir(parents=True, exist_ok=True)
    slot_numbers = set(range(1, min_slots + 1))
    for path in SAVE_DIR.glob("save_*.db"):
        slot = _slot_from_path(path)
        if slot is not None:
            slot_numbers.add(slot)
    return [_slot_info(slot) for slot in sorted(slot_numbers)]


def describe_slot(slot: int) -> str:
    return str(_slot_info(slot)["summary"])


def _slot_info(slot: int) -> dict[str, Any]:
    path = save_path_for_slot(slot)
    exists = path.exists()
    modified_timestamp = path.stat().st_mtime if exists else 0.0
    modified_at = (
        datetime.fromtimestamp(modified_timestamp).strftime("%Y-%m-%d %H:%M")
        if exists
        else ""
    )
    metadata = _read_save_metadata(path) if exists else {}
    return {
        "slot": slot,
        "label": f"슬롯 {slot:03d}",
        "path": path,
        "exists": exists,
        "modified_at": modified_at,
        "modified_timestamp": modified_timestamp,
        "summary": _summary_from_metadata(metadata),
        "metadata": metadata,
    }


def _summary_from_metadata(metadata: dict[str, Any]) -> str:
    if not metadata:
        return "비어 있음"
    if metadata.get("read_error"):
        return "세이브 정보를 읽을 수 없음"
    player_name = metadata.get("player_name") or "플레이어 정보 없음"
    position = metadata.get("position") or "직책 미상"
    current_year = metadata.get("current_year")
    current_month = metadata.get("current_month")
    current_day = metadata.get("current_day") or 1
    if current_year and current_month:
        return f"{player_name} · {position} · {current_year}년 {current_month}월 {current_day}일"
    return f"{player_name} · {position}"


def _read_save_metadata(path: Path) -> dict[str, Any]:
    try:
        with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as conn:
            conn.row_factory = sqlite3.Row
            player_columns = {
                row["name"] for row in conn.execute("PRAGMA table_info(player_state)").fetchall()
            }
            day_expression = "current_day" if "current_day" in player_columns else "1 AS current_day"
            player = conn.execute(
                f"""
                SELECT name, position, current_year, current_month, {day_expression}
                FROM player_state
                WHERE id = 1
                """
            ).fetchone()
            studio = conn.execute(
                """
                SELECT studio_name, fame, cash, debt
                FROM studio_state
                WHERE id = 1
                """
            ).fetchone()
    except sqlite3.Error:
        return {"read_error": True}

    metadata: dict[str, Any] = {}
    if player:
        metadata.update(
            {
                "player_name": player["name"],
                "position": player["position"],
                "current_year": player["current_year"],
                "current_month": player["current_month"],
                "current_day": player["current_day"],
            }
        )
    if studio:
        metadata.update(
            {
                "studio_name": studio["studio_name"],
                "studio_fame": studio["fame"],
                "studio_cash": studio["cash"],
                "studio_debt": studio["debt"],
            }
        )
    return metadata


def _table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone()
    return row is not None


def _slot_from_path(path: Path) -> int | None:
    stem = path.stem
    if not stem.startswith("save_"):
        return None
    try:
        return int(stem.removeprefix("save_"))
    except ValueError:
        return None
