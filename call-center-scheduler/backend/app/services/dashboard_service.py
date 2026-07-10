"""Dashboard service for aggregating coverage metrics."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.repositories.agents_repository import AgentsRepository
from app.repositories.offices_repository import OfficesRepository
from app.repositories.schedules_repository import SchedulesRepository
from app.repositories.skills_repository import SkillsRepository


def _as_utc(value: datetime | str) -> datetime:
    if isinstance(value, str):
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    else:
        dt = value
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


class DashboardService:
    """Builds dashboard summary and coverage heatmap points."""

    def __init__(self):
        self.agents_repo = AgentsRepository()
        self.offices_repo = OfficesRepository()
        self.skills_repo = SkillsRepository()
        self.schedules_repo = SchedulesRepository()

    def summary(self, start_at: datetime | None = None, end_at: datetime | None = None) -> dict[str, Any]:
        # Read ALL active schedules: week generation persists one shard document
        # per day (7+ docs per week), so a fixed newest-N cutoff would drop days.
        # Actives are bounded by per-week archiving, keeping this scan small.
        schedules = self.schedules_repo.list_active(order_by="generated_at")
        coverage_points: list[dict[str, Any]] = []

        start_utc = _as_utc(start_at) if start_at else None
        end_utc = _as_utc(end_at) if end_at else None

        for schedule in schedules:
            for assignment in schedule.get("assignments", []):
                slot_start = _as_utc(assignment["slot_start"])
                if start_utc and slot_start < start_utc:
                    continue
                if end_utc and slot_start >= end_utc:
                    continue

                coverage_points.append(
                    {
                        "slot_start": slot_start,
                        "office_id": assignment["office_id"],
                        "skill_id": assignment["skill_id"],
                        "required": int(assignment["required_agents"]),
                        "assigned": len(assignment.get("assigned_agent_ids", [])),
                        "gap": int(assignment.get("gap", 0)),
                    }
                )

        return {
            "total_agents": self.agents_repo.count(),
            "total_offices": self.offices_repo.count(),
            "total_skills": self.skills_repo.count(),
            "active_schedule_count": self.schedules_repo.count_active(),
            "coverage_points": coverage_points,
        }
