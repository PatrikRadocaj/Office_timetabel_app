"""Shared office timezone resolution."""

from __future__ import annotations

from datetime import timezone, tzinfo
from typing import Any
from zoneinfo import ZoneInfo


def resolve_office_timezone(office: dict[str, Any]) -> tzinfo:
    """Return the office's IANA timezone, falling back to UTC when unset or invalid."""

    timezone_name = str(office.get("timezone") or "UTC")
    try:
        return ZoneInfo(timezone_name)
    except Exception:
        return timezone.utc
