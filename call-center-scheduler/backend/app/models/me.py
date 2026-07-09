"""Schemas for agent-facing personal dashboard."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field

from app.models.common import TimeWindow


class AgentSkillView(BaseModel):
    skill_id: str
    skill_name: str
    proficiency: int = Field(ge=1, le=5)
    proficiency_pct: int = Field(ge=0, le=100)


class AgentDayShiftView(BaseModel):
    date: date
    day_name: str
    shift_start: datetime | str | None = None
    shift_end: datetime | str | None = None
    office: str = "-"
    required_skills: list[str] = Field(default_factory=list)
    total_hours: float = 0.0
    break_time: str | None = None


class HoursOverviewView(BaseModel):
    weekly_max_hours: float = 0.0
    hours_worked_week: float = 0.0
    hours_remaining: float = 0.0
    overtime_hours: float = 0.0


class AnnouncementView(BaseModel):
    id: str
    title: str
    message: str
    published_at: datetime | str | None = None


class AgentDashboardRead(BaseModel):
    full_name: str
    today_date: date
    greeting: str
    status_text: str
    is_scheduled_today: bool
    today_shift: AgentDayShiftView | None = None
    weekly_schedule: list[AgentDayShiftView] = Field(default_factory=list)
    hours_overview: HoursOverviewView
    skills: list[AgentSkillView] = Field(default_factory=list)
    availability: list[TimeWindow] = Field(default_factory=list)
    announcements: list[AnnouncementView] = Field(default_factory=list)


class AgentShiftListRead(BaseModel):
    shifts: list[AgentDayShiftView] = Field(default_factory=list)


class AgentAvailabilityRead(BaseModel):
    availability: list[TimeWindow] = Field(default_factory=list)


class AgentAvailabilityUpdate(BaseModel):
    availability: list[TimeWindow] = Field(default_factory=list)
