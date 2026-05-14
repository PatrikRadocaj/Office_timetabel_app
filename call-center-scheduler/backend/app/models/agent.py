"""Agent schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.models.common import ShiftPreference, TimeWindow


class AgentSkill(BaseModel):
    skill_id: str
    proficiency: int = Field(ge=1, le=5)


class AgentBase(BaseModel):
    full_name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    office_id: str
    weekly_max_hours: int = Field(default=40, ge=1, le=60)
    min_rest_hours: int = Field(default=10, ge=1, le=24)
    shift_preference: ShiftPreference = ShiftPreference.ANY
    skills: list[AgentSkill] = Field(default_factory=list)
    availability: list[TimeWindow] = Field(default_factory=list)

    @field_validator("skills")
    @classmethod
    def ensure_unique_skill_ids(cls, value: list[AgentSkill]) -> list[AgentSkill]:
        skill_ids = [entry.skill_id for entry in value]
        if len(skill_ids) != len(set(skill_ids)):
            raise ValueError("Each skill can be listed only once per agent")
        return value


class AgentCreate(AgentBase):
    user_id: str | None = None


class AgentUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=120)
    office_id: str | None = None
    weekly_max_hours: int | None = Field(default=None, ge=1, le=60)
    min_rest_hours: int | None = Field(default=None, ge=1, le=24)
    shift_preference: ShiftPreference | None = None
    skills: list[AgentSkill] | None = None
    availability: list[TimeWindow] | None = None


class AgentRead(AgentBase):
    id: str
    user_id: str | None = None
    is_active: bool = True
    created_at: datetime | str
    updated_at: datetime | str
