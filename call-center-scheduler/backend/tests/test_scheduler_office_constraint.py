"""Scheduler office-assignment constraint regression tests."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any

from app.models.schedule import ScheduleGenerationRequest
from app.services.scheduler_service import SchedulerService


def _dt(hour: int) -> datetime:
    return datetime(2026, 8, 3, hour, 0, tzinfo=timezone.utc)


class StaticRepository:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows

    def list(self) -> list[dict[str, Any]]:
        return [dict(row) for row in self.rows]


class FakeSchedulesRepository:
    def __init__(self) -> None:
        self.created: dict[str, Any] | None = None

    def create(self, data: dict[str, Any]) -> dict[str, Any]:
        self.created = data
        return {"id": "schedule-1", **data}


def _agent(agent_id: str, office_id: str) -> dict[str, Any]:
    return {
        "id": agent_id,
        "office_id": office_id,
        "weekly_max_hours": 40,
        "min_rest_hours": 10,
        "shift_preference": "any",
        "skills": [{"skill_id": "skill-a", "proficiency": 5}],
        "availability": [],
        "is_active": True,
    }


def _demand(office_id: str, required_agents: int = 1) -> dict[str, Any]:
    return {
        "slot_start": _dt(9),
        "slot_end": _dt(10),
        "office_id": office_id,
        "skill_id": "skill-a",
        "required_agents": required_agents,
        "priority": 3,
    }


def _service(demand_rows: list[dict[str, Any]], agents: list[dict[str, Any]]) -> SchedulerService:
    service = SchedulerService.__new__(SchedulerService)
    service.settings = SimpleNamespace(schedule_slot_minutes=60)
    service._load_demand = lambda start_at, end_at: demand_rows  # type: ignore[method-assign]
    service.agent_repo = StaticRepository(agents)
    service.office_repo = StaticRepository(
        [
            {"id": "office-1", "name": "Berlin", "timezone": "UTC", "max_capacity": 10},
            {"id": "office-2", "name": "London", "timezone": "UTC", "max_capacity": 10},
        ]
    )
    service.skill_repo = StaticRepository([{"id": "skill-a", "name": "Skill A", "min_proficiency": 1}])
    service.schedule_repo = FakeSchedulesRepository()
    return service


def test_scheduler_never_assigns_agent_outside_home_office() -> None:
    service = _service(
        demand_rows=[_demand("office-2")],
        agents=[_agent("agent-office-1", "office-1")],
    )

    result = service.generate(ScheduleGenerationRequest(start_at=_dt(9), end_at=_dt(10)))

    assert result["total_required"] == 1
    assert result["total_assigned"] == 0
    assert result["assignments"][0]["office_id"] == "office-2"
    assert result["assignments"][0]["assigned_agent_ids"] == []
    assert result["assignments"][0]["gap"] == 1


def test_scheduler_assigns_only_same_office_agents_when_two_offices_have_demand() -> None:
    service = _service(
        demand_rows=[_demand("office-1"), _demand("office-2")],
        agents=[
            _agent("agent-office-1", "office-1"),
            _agent("agent-office-2", "office-2"),
            _agent("extra-office-1", "office-1"),
        ],
    )

    result = service.generate(ScheduleGenerationRequest(start_at=_dt(9), end_at=_dt(10)))

    by_office = {assignment["office_id"]: assignment for assignment in result["assignments"]}
    assert by_office["office-1"]["assigned_agent_ids"] == ["agent-office-1"]
    assert by_office["office-2"]["assigned_agent_ids"] == ["agent-office-2"]
