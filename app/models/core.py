from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class Era(BaseModel):
    id: str
    name: str
    start_year: int
    end_year: int | None = None
    description: str | None = None
    theater_demand: int = 50
    ott_power: int = 0
    foreign_competition: int = 50
    middle_budget_risk: int = 50
    special_format_demand: int = 0
    online_spread_power: int = 0


class PlayerState(BaseModel):
    name: str
    gender: str | None = None
    age: int = 25
    current_year: int
    current_month: int = 1
    current_day: int = 1
    position: str
    cash: int = 0
    debt: int = 0
    stats: dict[str, Any] = Field(default_factory=dict)
    reputation: dict[str, Any] = Field(default_factory=dict)
    network: dict[str, Any] = Field(default_factory=dict)


class StudioState(BaseModel):
    studio_name: str
    fame: int = 0
    cash: int = 0
    debt: int = 0
