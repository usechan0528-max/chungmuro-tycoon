from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class Person(BaseModel):
    id: str
    name_ko: str
    name_en: str | None = None
    type: str
    birth_year: int | None = None
    available_from: int | None = None
    protection_level: str = "none"
    current_stats: dict[str, Any] = Field(default_factory=dict)
    potential_stats: dict[str, Any] = Field(default_factory=dict)
    genre_fit: dict[str, Any] = Field(default_factory=dict)
    public_profile: dict[str, Any] = Field(default_factory=dict)


class Critic(BaseModel):
    id: str
    name_ko: str
    critic_type: dict[str, Any] = Field(default_factory=dict)
    taste_profile: dict[str, Any] = Field(default_factory=dict)
    influence: dict[str, Any] = Field(default_factory=dict)
    public_description: str | None = None
