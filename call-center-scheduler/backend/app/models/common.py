"""Shared models and enums."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel


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

    day_of_week: int
    start_hour: int
    end_hour: int


def utcnow() -> datetime:
    """Return timezone-aware UTC timestamp."""

    return datetime.now(timezone.utc)
