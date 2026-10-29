from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class Genre(BaseModel):
    id: str
    name: str
    description: str | None = None
    era_fit: dict[str, int] = Field(default_factory=dict)
    scenario_weight: int = 10
    directing_weight: int = 10
    actors_weight: int = 10
    shooting_weight: int = 10
    art_weight: int = 10
    stunt_weight: int = 0
    vfx_weight: int = 0
    sound_weight: int = 10
    editing_weight: int = 10
    contingency_weight: int = 5
    boxoffice_weight: float = 1.0
    critic_weight: float = 1.0
    audience_weight: float = 1.0
    major_risks: list[str] = Field(default_factory=list)
    franchise_fit: int = 50
    secondary_market_fit: int = 50
    plagiarism_sensitivity: int = 50


class ProjectScale(BaseModel):
    id: str
    name: str
    min_budget: int
    max_budget: int
    min_events: int = 1
    max_events: int = 3
    failure_impact: str = "normal"


class Project(BaseModel):
    id: str
    title: str
    genre_id: str
    scale_id: str
    status: str
    production_budget: int = 0
    marketing_budget: int = 0
    stage: str = "planning"
    stats: dict[str, Any] = Field(default_factory=dict)
    created_year: int | None = None
    release_year: int | None = None
    release_month: int | None = None
