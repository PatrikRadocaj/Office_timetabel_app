"""Shared models and enums."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field, model_validator


class UserRole(str, Enum):
    """Application roles used for authorization checks."""

    ADMIN = "admin"
    AGENT = "agent"


class ShiftPreference(str, Enum):
    """Agent preference used as a soft optimization signal."""

    DAY = "day"
    NIGHT = "night"
    ANY = "any"


class APIMessage(BaseModel):
    """Simple message wrapper for mutation endpoints."""

    message: str


class TimeWindow(BaseModel):
    """Defines an availability window in local office time."""

    day_of_week: int = Field(ge=0, le=6)
    start_hour: int = Field(ge=0, le=23)
    end_hour: int = Field(ge=1, le=24)

    @model_validator(mode="after")
    def ensure_start_before_end(self) -> "TimeWindow":
        if self.start_hour >= self.end_hour:
            raise ValueError("start_hour must be earlier than end_hour")
        return self


def utcnow() -> datetime:
    """Return timezone-aware UTC timestamp."""

    return datetime.now(timezone.utc)
