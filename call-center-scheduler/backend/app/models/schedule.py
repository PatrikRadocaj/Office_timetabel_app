"""Scheduling and dashboard schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ScheduleGenerationRequest(BaseModel):
    start_at: datetime
    end_at: datetime


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
