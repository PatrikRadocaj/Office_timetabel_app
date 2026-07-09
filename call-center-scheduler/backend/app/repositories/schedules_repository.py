"""Generated schedules repository."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.repositories.firestore_repository import FirestoreRepository


ACTIVE_SCHEDULE_STATUS = "active"


def _as_utc(value: datetime | str) -> datetime:
    if isinstance(value, str):
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    else:
        dt = value

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


class SchedulesRepository(FirestoreRepository):
    def __init__(self):
        super().__init__("generated_schedules")

    def list_active(self, order_by: str | None = None, limit: int | None = None) -> list[dict]:
        """List active schedules without requiring Firestore composite indexes.

        Firestore requires a composite index for `status == "active"` combined
        with `order_by("generated_at")`. The schedules collection is small, so
        we keep the query index-free by filtering in Firestore and applying any
        generated_at ordering and limiting in Python.
        """

        rows = self.list(filters=[("status", "==", ACTIVE_SCHEDULE_STATUS)])
        if not order_by:
            return rows[:limit] if limit is not None else rows

        reverse = order_by.startswith("-")
        field_name = order_by[1:] if reverse else order_by

        if field_name == "generated_at":
            rows.sort(key=lambda row: _as_utc(row[field_name]), reverse=reverse)
        else:
            rows.sort(key=lambda row: row.get(field_name), reverse=reverse)

        return rows[:limit] if limit is not None else rows

    def count_active(self) -> int:
        return self.count(filters=[("status", "==", ACTIVE_SCHEDULE_STATUS)])
