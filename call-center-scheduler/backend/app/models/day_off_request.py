"""Day-off request schemas."""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel, Field, model_validator


class DayOffRequestStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


SCHEDULE_IMPACT_POLICY = (
    "Approval records the request status only. Generated schedules and assignments "
    "are not changed automatically."
)


class DayOffRequestCreate(BaseModel):
    start_date: date
    end_date: date
    reason: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def ensure_end_after_start(self) -> "DayOffRequestCreate":
        if self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date")
        return self


class DayOffRequestReview(BaseModel):
    status: DayOffRequestStatus
    review_note: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def ensure_review_status(self) -> "DayOffRequestReview":
        if self.status == DayOffRequestStatus.PENDING:
            raise ValueError("review status must be approved or rejected")
        return self


class DayOffRequestRead(BaseModel):
    id: str
    agent_id: str
    user_id: str | None = None
    email: str | None = None
    full_name: str
    office_id: str | None = None
    start_date: date | str
    end_date: date | str
    reason: str | None = None
    status: DayOffRequestStatus
    requested_at: datetime | str
    reviewed_at: datetime | str | None = None
    reviewed_by_user_id: str | None = None
    reviewed_by_name: str | None = None
    review_note: str | None = None
    schedule_impact: str = SCHEDULE_IMPACT_POLICY
    created_at: datetime | str | None = None
    updated_at: datetime | str | None = None
