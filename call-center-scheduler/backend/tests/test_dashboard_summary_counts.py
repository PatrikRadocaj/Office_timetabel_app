"""Dashboard summary read-volume regression tests."""

from __future__ import annotations

from datetime import datetime, timezone

from app.services.dashboard_service import DashboardService


class _CountOnlyRepository:
    def __init__(self, count_value: int) -> None:
        self.count_value = count_value
        self.list_called = False

    def count(self) -> int:
        return self.count_value

    def list(self, *_, **__) -> list[dict]:
        self.list_called = True
        raise AssertionError("Dashboard totals should use count(), not list()")


class _ScheduleRepository:
    def __init__(self) -> None:
        self.count_called = False
        self.list_called = False

    def count_active(self) -> int:
        self.count_called = True
        return 9

    def list_active(self, order_by: str | None = None, limit: int | None = None) -> list[dict]:
        self.list_called = True
        # Week generation shards one document per day, so the summary must read
        # ALL active schedules — a newest-N cutoff would drop days of coverage.
        assert order_by == "generated_at"
        assert limit is None
        return [
            {
                "id": "schedule-1",
                "generated_at": datetime(2026, 7, 9, tzinfo=timezone.utc),
                "status": "active",
                "assignments": [
                    {
                        "slot_start": datetime(2026, 7, 9, 8, 0, tzinfo=timezone.utc),
                        "office_id": "office-1",
                        "skill_id": "skill-1",
                        "required_agents": 2,
                        "assigned_agent_ids": ["agent-1"],
                        "gap": 1,
                    }
                ],
            }
        ]


def test_summary_uses_count_helpers_for_totals() -> None:
    service = object.__new__(DashboardService)
    service.agents_repo = _CountOnlyRepository(10)
    service.offices_repo = _CountOnlyRepository(2)
    service.skills_repo = _CountOnlyRepository(4)
    service.schedules_repo = _ScheduleRepository()

    summary = service.summary()

    assert summary["total_agents"] == 10
    assert summary["total_offices"] == 2
    assert summary["total_skills"] == 4
    assert summary["active_schedule_count"] == 9
    assert summary["coverage_points"] == [
        {
            "slot_start": datetime(2026, 7, 9, 8, 0, tzinfo=timezone.utc),
            "office_id": "office-1",
            "skill_id": "skill-1",
            "required": 2,
            "assigned": 1,
            "gap": 1,
        }
    ]
    assert service.schedules_repo.list_called is True
    assert service.schedules_repo.count_called is True
    assert service.agents_repo.list_called is False
    assert service.offices_repo.list_called is False
    assert service.skills_repo.list_called is False
