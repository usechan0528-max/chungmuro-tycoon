from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class EventChoice(BaseModel):
    id: str
    text: str
    description: str | None = None
    effects: dict[str, Any] = Field(default_factory=dict)


class ProductionEvent(BaseModel):
    id: str
    stage: str
    title: str
    description: str
    trigger: dict[str, Any] = Field(default_factory=dict)
    choices: list[EventChoice] = Field(default_factory=list)

