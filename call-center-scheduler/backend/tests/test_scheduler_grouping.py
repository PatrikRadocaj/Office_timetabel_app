"""Scheduler demand grouping regression tests."""

from __future__ import annotations

from datetime import datetime, timezone

from app.services.scheduler_service import SchedulerService


def test_group_demand_normalizes_mixed_slot_datetime_formats() -> None:
    rows = [
        {
            "slot_start": datetime(2026, 7, 13, 6, 0, tzinfo=timezone.utc),
            "slot_end": datetime(2026, 7, 13, 6, 30, tzinfo=timezone.utc),
            "office_id": "office-1",
            "skill_id": "skill-a",
            "required_agents": 1,
            "priority": 3,
        },
        {
            "slot_start": "2026-07-13T06:00:00+00:00",
            "slot_end": "2026-07-13T06:30:00+00:00",
            "office_id": "office-1",
            "skill_id": "skill-b",
            "required_agents": 1,
            "priority": 2,
        },
    ]

    grouped = SchedulerService._group_demand_by_slot_and_skill(rows)

    assert list(grouped.keys()) == [("2026-07-13T06:00:00+00:00", "2026-07-13T06:30:00+00:00")]
    assert grouped[("2026-07-13T06:00:00+00:00", "2026-07-13T06:30:00+00:00")] == rows
