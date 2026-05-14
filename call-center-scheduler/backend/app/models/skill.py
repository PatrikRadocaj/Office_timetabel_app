"""Skill schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class SkillBase(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    description: str | None = Field(default=None, max_length=240)
    min_proficiency: int = Field(default=1, ge=1, le=5)


class SkillCreate(SkillBase):
    pass


class SkillUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=100)
    description: str | None = Field(default=None, max_length=240)
    min_proficiency: int | None = Field(default=None, ge=1, le=5)


class SkillRead(SkillBase):
    id: str
    created_at: datetime | str
    updated_at: datetime | str
