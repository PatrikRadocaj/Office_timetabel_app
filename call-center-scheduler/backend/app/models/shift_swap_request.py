"""Shift-swap request schemas."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, model_validator


class ShiftSwapRequestStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


SCHEDULE_IMPACT_POLICY = (
    "Approval swaps the two agents in the active generated schedule assignments "
    "after revalidating skills, office, availability, and duplicate-assignment rules."
)


class ShiftSwapAssignmentRef(BaseModel):
    schedule_id: str = Field(min_length=1)
    assignment_key: str = Field(min_length=1)


class ShiftSwapRequestCreate(BaseModel):
    source_schedule_id: str = Field(min_length=1)
    source_assignment_key: str = Field(min_length=1)
    target_schedule_id: str = Field(min_length=1)
    target_assignment_key: str = Field(min_length=1)
    target_agent_id: str = Field(min_length=1)
    source_assignment_refs: list[ShiftSwapAssignmentRef] | None = None
    target_assignment_refs: list[ShiftSwapAssignmentRef] | None = None
    reason: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def ensure_distinct_assignments(self) -> "ShiftSwapRequestCreate":
        source_refs = self.source_assignment_refs or [
            ShiftSwapAssignmentRef(schedule_id=self.source_schedule_id, assignment_key=self.source_assignment_key)
        ]
        target_refs = self.target_assignment_refs or [
            ShiftSwapAssignmentRef(schedule_id=self.target_schedule_id, assignment_key=self.target_assignment_key)
        ]
        if not source_refs:
            raise ValueError("source shift must include at least one assignment")
        if not target_refs:
            raise ValueError("target shift must include at least one assignment")

        source_keys = {(ref.schedule_id, ref.assignment_key) for ref in source_refs}
        target_keys = {(ref.schedule_id, ref.assignment_key) for ref in target_refs}
        if source_keys & target_keys:
            raise ValueError("source and target shifts must be different")
        return self


class ShiftSwapRequestReview(BaseModel):
    status: ShiftSwapRequestStatus
    review_note: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def ensure_review_status(self) -> "ShiftSwapRequestReview":
        if self.status == ShiftSwapRequestStatus.PENDING:
            raise ValueError("review status must be approved or rejected")
        return self


class ShiftSwapOption(BaseModel):
    schedule_id: str
    assignment_key: str
    assignment_refs: list[ShiftSwapAssignmentRef] = Field(default_factory=list)
    agent_id: str
    agent_name: str
    slot_start: datetime | str
    slot_end: datetime | str
    office_id: str
    office_name: str
    office_timezone: str | None = None
    skill_id: str
    skill_name: str
    skill_ids: list[str] = Field(default_factory=list)
    skill_names: list[str] = Field(default_factory=list)


class ShiftSwapOptionsResponse(BaseModel):
    my_shifts: list[ShiftSwapOption]
    target_shifts: list[ShiftSwapOption]


class ShiftSwapRequestRead(BaseModel):
    id: str
    requester_agent_id: str
    requester_user_id: str | None = None
    requester_name: str
    requester_email: str | None = None
    target_agent_id: str
    target_agent_name: str
    target_agent_email: str | None = None
    source_schedule_id: str
    source_assignment_key: str
    target_schedule_id: str
    target_assignment_key: str
    source_assignment_refs: list[ShiftSwapAssignmentRef] | None = None
    target_assignment_refs: list[ShiftSwapAssignmentRef] | None = None
    source_shift: dict[str, Any]
    target_shift: dict[str, Any]
    reason: str | None = None
    status: ShiftSwapRequestStatus
    requested_at: datetime | str
    reviewed_at: datetime | str | None = None
    reviewed_by_user_id: str | None = None
    reviewed_by_name: str | None = None
    review_note: str | None = None
    schedule_impact: str = SCHEDULE_IMPACT_POLICY
    schedule_update: dict[str, Any] | None = None
    created_at: datetime | str | None = None
    updated_at: datetime | str | None = None
