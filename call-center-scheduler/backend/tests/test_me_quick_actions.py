"""Agent-facing quick action service tests."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import pytest
from fastapi import HTTPException

from app.models.common import TimeWindow
from app.services.me_service import MeService


class FakeAgentsRepository:
    def __init__(self, agent: dict[str, Any] | None) -> None:
        self.agent = agent
        self.updated_id: str | None = None
        self.updated_data: dict[str, Any] | None = None

    def list(self, filters=None, limit=None) -> list[dict[str, Any]]:
        if self.agent is None:
            return []

        for field_name, op, value in filters or []:
            if op != "==":
                continue
            if self.agent.get(field_name) != value:
                return []
        return [dict(self.agent)]

    def update(self, document_id: str, data: dict[str, Any]) -> dict[str, Any] | None:
        if self.agent is None or self.agent["id"] != document_id:
            return None
        self.updated_id = document_id
        self.updated_data = {**data}
        self.agent = {**self.agent, **data}
        return dict(self.agent)


class StaticRepository:
    def __init__(self, rows: list[dict[str, Any]] | None = None) -> None:
        self.rows = rows or []
        self.list_calls: list[dict[str, Any]] = []

    def list(self, filters=None, order_by: str | None = None, limit: int | None = None) -> list[dict[str, Any]]:
        self.list_calls.append({"filters": filters, "order_by": order_by, "limit": limit})
        rows = [dict(row) for row in self.rows]
        for field_name, op, value in filters or []:
            if op != "==":
                raise AssertionError(f"Unsupported test filter op: {op}")
            rows = [row for row in rows if row.get(field_name) == value]
        if order_by:
            reverse = order_by.startswith("-")
            field_name = order_by[1:] if reverse else order_by
            rows.sort(key=lambda row: row.get(field_name), reverse=reverse)
        return rows[:limit] if limit is not None else rows

    def list_active(self, order_by: str | None = None, limit: int | None = None) -> list[dict[str, Any]]:
        return self.list(filters=[("status", "==", "active")], order_by=order_by, limit=limit)


def _service(agent: dict[str, Any] | None, schedules: list[dict[str, Any]] | None = None) -> MeService:
    service = object.__new__(MeService)
    service.agents_repo = FakeAgentsRepository(agent)
    service.skills_repo = StaticRepository(
        [
            {"id": "skill-a", "name": "Skill A"},
            {"id": "skill-b", "name": "Skill B"},
        ]
    )
    service.offices_repo = StaticRepository(
        [
            {"id": "office-1", "name": "Berlin", "timezone": "Europe/Berlin"},
            {"id": "office-2", "name": "London", "timezone": "Europe/London"},
        ]
    )
    service.schedules_repo = StaticRepository(schedules or [])
    service.announcements_repo = StaticRepository()
    return service


def _current_user() -> dict[str, Any]:
    return {"id": "user-1", "email": "agent@example.com", "full_name": "Agent User", "role": "agent"}


def _agent() -> dict[str, Any]:
    return {
        "id": "agent-1",
        "user_id": "user-1",
        "email": "agent@example.com",
        "full_name": "Agent User",
        "office_id": "office-1",
        "weekly_max_hours": 40,
        "skills": [{"skill_id": "skill-a", "proficiency": 4}],
        "availability": [{"day_of_week": 0, "start_hour": 9, "end_hour": 17}],
    }


def _assignment(
    slot_start: datetime,
    slot_end: datetime,
    office_id: str,
    skill_id: str,
    assigned_agent_ids: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "slot_start": slot_start,
        "slot_end": slot_end,
        "office_id": office_id,
        "skill_id": skill_id,
        "assigned_agent_ids": assigned_agent_ids or ["agent-1"],
        "required_agents": 1,
        "coverage_ratio": 1.0,
        "gap": 0,
    }


def test_dashboard_includes_current_agent_availability() -> None:
    payload = _service(_agent()).dashboard(_current_user())

    assert payload["availability"] == [{"day_of_week": 0, "start_hour": 9, "end_hour": 17}]


def test_shifts_returns_all_assigned_days_without_empty_placeholders() -> None:
    schedules = [
        {
            "id": "schedule-old",
            "generated_at": "2026-07-01T00:00:00+00:00",
            "status": "active",
            "assignments": [
                _assignment(
                    datetime(2026, 7, 13, 8, 0, tzinfo=timezone.utc),
                    datetime(2026, 7, 13, 9, 0, tzinfo=timezone.utc),
                    "office-1",
                    "skill-a",
                ),
                _assignment(
                    datetime(2026, 8, 3, 9, 0, tzinfo=timezone.utc),
                    datetime(2026, 8, 3, 11, 0, tzinfo=timezone.utc),
                    "office-2",
                    "skill-b",
                ),
            ],
        }
    ]

    payload = _service(_agent(), schedules=schedules).shifts(_current_user())

    assert [shift["date"] for shift in payload["shifts"]] == ["2026-07-13", "2026-08-03"]
    assert payload["shifts"][0]["office"] == "Berlin"
    assert payload["shifts"][0]["required_skills"] == ["Skill A"]
    assert payload["shifts"][1]["office"] == "London"
    assert payload["shifts"][1]["total_hours"] == 2.0


def test_newer_same_slot_assignment_without_current_agent_hides_older_shift() -> None:
    slot_start = datetime(2026, 7, 13, 8, 0, tzinfo=timezone.utc)
    slot_end = datetime(2026, 7, 13, 9, 0, tzinfo=timezone.utc)
    schedules = [
        {
            "id": "schedule-old",
            "generated_at": "2026-07-01T00:00:00+00:00",
            "status": "active",
            "assignments": [_assignment(slot_start, slot_end, "office-1", "skill-a", ["agent-1"])],
        },
        {
            "id": "schedule-new",
            "generated_at": "2026-07-02T00:00:00+00:00",
            "status": "active",
            "assignments": [_assignment(slot_start, slot_end, "office-1", "skill-a", ["agent-2"])],
        },
    ]

    payload = _service(_agent(), schedules=schedules).shifts(_current_user())

    assert payload["shifts"] == []


def test_cancelled_newer_same_slot_assignment_does_not_hide_active_shift() -> None:
    slot_start = datetime(2026, 7, 13, 8, 0, tzinfo=timezone.utc)
    slot_end = datetime(2026, 7, 13, 9, 0, tzinfo=timezone.utc)
    schedules = [
        {
            "id": "schedule-old",
            "generated_at": "2026-07-01T00:00:00+00:00",
            "status": "active",
            "assignments": [_assignment(slot_start, slot_end, "office-1", "skill-a", ["agent-1"])],
        },
        {
            "id": "schedule-new-cancelled",
            "generated_at": "2026-07-02T00:00:00+00:00",
            "status": "cancelled",
            "assignments": [_assignment(slot_start, slot_end, "office-1", "skill-a", ["agent-2"])],
        },
    ]

    payload = _service(_agent(), schedules=schedules).shifts(_current_user())

    assert [shift["date"] for shift in payload["shifts"]] == ["2026-07-13"]
    assert payload["shifts"][0]["office"] == "Berlin"


def test_shifts_queries_only_active_schedules() -> None:
    slot_start = datetime(2026, 7, 13, 8, 0, tzinfo=timezone.utc)
    slot_end = datetime(2026, 7, 13, 9, 0, tzinfo=timezone.utc)
    service = _service(
        _agent(),
        schedules=[
            {
                "id": "schedule-active",
                "generated_at": "2026-07-01T00:00:00+00:00",
                "status": "active",
                "assignments": [_assignment(slot_start, slot_end, "office-1", "skill-a", ["agent-1"])],
            }
        ],
    )

    payload = service.shifts(_current_user())

    assert payload["shifts"]
    assert service.schedules_repo.list_calls[-1] == {
        "filters": [("status", "==", "active")],
        "order_by": "generated_at",
        "limit": None,
    }


def test_dashboard_week_omits_shift_when_newer_same_slot_reassigned_to_other_agent() -> None:
    slot_start = datetime.now(timezone.utc).replace(hour=10, minute=0, second=0, microsecond=0)
    slot_end = slot_start + timedelta(hours=1)
    schedules = [
        {
            "id": "schedule-old",
            "generated_at": "2026-07-01T00:00:00+00:00",
            "status": "active",
            "assignments": [_assignment(slot_start, slot_end, "office-1", "skill-a", ["agent-1"])],
        },
        {
            "id": "schedule-new",
            "generated_at": "2026-07-02T00:00:00+00:00",
            "status": "active",
            "assignments": [_assignment(slot_start, slot_end, "office-1", "skill-a", ["agent-2"])],
        },
    ]

    payload = _service(_agent(), schedules=schedules).dashboard(_current_user())

    assert payload["is_scheduled_today"] is False
    assert all(day["shift_start"] is None for day in payload["weekly_schedule"])


def test_update_availability_writes_current_agent_only() -> None:
    service = _service(_agent())
    result = service.update_availability(
        _current_user(),
        [
            TimeWindow(day_of_week=1, start_hour=10, end_hour=18),
            TimeWindow(day_of_week=3, start_hour=12, end_hour=20),
        ],
    )

    assert service.agents_repo.updated_id == "agent-1"
    assert service.agents_repo.updated_data == {
        "availability": [
            {"day_of_week": 1, "start_hour": 10, "end_hour": 18},
            {"day_of_week": 3, "start_hour": 12, "end_hour": 20},
        ]
    }
    assert result["availability"] == service.agents_repo.updated_data["availability"]


def test_update_availability_without_agent_profile_raises_404() -> None:
    with pytest.raises(HTTPException) as exc_info:
        _service(None).update_availability(_current_user(), [TimeWindow(day_of_week=0, start_hour=9, end_hour=17)])

    assert exc_info.value.status_code == 404


def test_get_availability_without_agent_profile_raises_404() -> None:
    with pytest.raises(HTTPException) as exc_info:
        _service(None).availability(_current_user())

    assert exc_info.value.status_code == 404
