"""Generated schedules repository."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.repositories.firestore_repository import FirestoreRepository


ACTIVE_SCHEDULE_STATUS = "active"
ARCHIVED_SCHEDULE_STATUS = "archived"


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

    def list_active_for_week(self, year: int, week: int) -> list[dict]:
        rows = self.list(
            filters=[
                ("status", "==", ACTIVE_SCHEDULE_STATUS),
                ("year", "==", int(year)),
                ("week", "==", int(week)),
            ]
        )
        rows.sort(key=lambda row: _as_utc(row.get("generated_at", row.get("created_at"))), reverse=True)
        return rows

    def archive_active_for_week(self, year: int, week: int, exclude_ids: list[str] | None = None) -> list[str]:
        excluded = {str(schedule_id) for schedule_id in exclude_ids or []}
        archived_ids: list[str] = []
        for schedule in self.list_active_for_week(year, week):
            schedule_id = str(schedule["id"])
            if schedule_id in excluded:
                continue
            self.update(schedule_id, {"status": ARCHIVED_SCHEDULE_STATUS})
            archived_ids.append(schedule_id)
        return archived_ids
