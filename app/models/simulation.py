from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class Organization(BaseModel):
    id: str
    name_ko: str
    name_en: str | None = None
    org_type: str
    available_from: int | None = None
    power: int = 50
    reputation: dict[str, Any] = Field(default_factory=dict)
    strategy: dict[str, Any] = Field(default_factory=dict)
    public_profile: dict[str, Any] = Field(default_factory=dict)


class ProjectStageDefinition(BaseModel):
    id: str
    sequence: int
    name: str
    description: str | None = None
    stage_group: str = "production"
    required_for_scales: list[str] = Field(default_factory=list)


class SimulationEvent(BaseModel):
    id: str
    category: str
    stage: str | None = None
    scope: str = "project"
    title: str
    description: str
    fixed_level: str = "dynamic"
    weight: int = 100
    cooldown_months: int = 0
    trigger: dict[str, Any] = Field(default_factory=dict)
    choices: list[dict[str, Any]] = Field(default_factory=list)


class EventHistoryEntry(BaseModel):
    event_id: str
    category: str
    project_id: str | None = None
    choice_id: str | None = None
    choice_text: str | None = None
    year: int | None = None
    month: int | None = None
    effects: dict[str, Any] = Field(default_factory=dict)

