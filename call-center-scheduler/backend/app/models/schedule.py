"""Scheduling and dashboard schemas."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field, model_validator


class ScheduleGenerationRequest(BaseModel):
    start_at: datetime
    end_at: datetime


class ScheduleWeekGenerationRequest(BaseModel):
    year: int = Field(ge=2000, le=2100)
    week: int = Field(ge=1, le=53)

    @model_validator(mode="after")
    def validate_iso_week(self) -> "ScheduleWeekGenerationRequest":
        try:
            date.fromisocalendar(self.year, self.week, 1)
        except ValueError as exc:
            raise ValueError(f"{self.year} does not have ISO week {self.week}") from exc
        return self


class SlotAssignment(BaseModel):
    slot_start: datetime
    slot_end: datetime
    office_id: str
    skill_id: str
    assigned_agent_ids: list[str] = Field(default_factory=list)
    required_agents: int
    coverage_ratio: float
    gap: int


class ScheduleGenerationResponse(BaseModel):
    schedule_id: str
    assignments: list[SlotAssignment]
    total_required: int
    total_assigned: int
    uncovered_demand: int


class ScheduleWeekGenerationResponse(ScheduleGenerationResponse):
    year: int
    week: int
    week_start: datetime | str
    week_end: datetime | str
    archived_schedule_ids: list[str] = Field(default_factory=list)
    # Week output is persisted as one Firestore document per UTC day so a full
    # ISO week stays under the 1 MiB per-document limit. `schedule_id` carries
    # the shared generation batch id; `schedule_ids` lists the shard documents.
    schedule_ids: list[str] = Field(default_factory=list)
    document_count: int = 1


class CoveragePoint(BaseModel):
    slot_start: datetime | str
    office_id: str
    skill_id: str
    required: int
    assigned: int
    gap: int


class DashboardSummary(BaseModel):
    total_agents: int
    total_offices: int
    total_skills: int
    active_schedule_count: int
    coverage_points: list[CoveragePoint]
