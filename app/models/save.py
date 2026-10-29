from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel


class SaveSlot(BaseModel):
    path: Path
    exists: bool
    label: str = "save_001"

