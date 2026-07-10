"""ISO week schedule generation tests."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import HTTPException

from app.models.schedule import ScheduleWeekGenerationRequest
from app.services.scheduler_service import SchedulerService


def _dt(day: int, hour: int) -> datetime:
    return datetime(2026, 7, day, hour, 0, tzinfo=timezone.utc)


class StaticRepository:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows

    def list(self) -> list[dict[str, Any]]:
        return [dict(row) for row in self.rows]


class FakeSchedulesRepository:
    def __init__(self, active_week_ids: list[str] | None = None, fail_on_create: bool = False) -> None:
        self.active_week_ids = active_week_ids or []
        self.fail_on_create = fail_on_create
        self.archive_calls: list[tuple[int, int, tuple[str, ...]]] = []
        self.created: list[tuple[str | None, dict[str, Any]]] = []
        self.events: list[str] = []

    def archive_active_for_week(self, year: int, week: int, exclude_ids: list[str] | None = None) -> list[str]:
        self.events.append("archive")
        self.archive_calls.append((year, week, tuple(exclude_ids or [])))
        return list(self.active_week_ids)

    def create(self, data: dict[str, Any], document_id: str | None = None) -> dict[str, Any]:
        if self.fail_on_create:
            raise RuntimeError("persist failed")
        self.events.append("create")
        self.created.append((document_id, {**data}))
        return {"id": document_id or f"schedule-{len(self.created)}", **data}


def _agent(agent_id: str, weekly_max_hours: float = 40.0, office_id: str = "office-1") -> dict[str, Any]:
    return {
        "id": agent_id,
        "office_id": office_id,
        "weekly_max_hours": weekly_max_hours,
        "min_rest_hours": 10,
        "shift_preference": "any",
        "skills": [{"skill_id": "skill-a", "proficiency": 5}],
        "availability": [],
        "is_active": True,
    }


def _demand(day: int, hour: int, office_id: str = "office-1") -> dict[str, Any]:
    return {
        "slot_start": _dt(day, hour),
        "slot_end": _dt(day, hour + 1),
        "office_id": office_id,
        "skill_id": "skill-a",
        "required_agents": 1,
        "priority": 3,
    }


def _service(demand_rows: list[dict[str, Any]], agents: list[dict[str, Any]]) -> SchedulerService:
    service = SchedulerService.__new__(SchedulerService)
    service.settings = SimpleNamespace(schedule_slot_minutes=60)
    service.demand_calls: list[tuple[datetime, datetime]] = []

    def load_demand(start_at: datetime, end_at: datetime) -> list[dict[str, Any]]:
        service.demand_calls.append((start_at, end_at))
        return demand_rows

    service._load_demand = load_demand  # type: ignore[method-assign]
    service.agent_repo = StaticRepository(agents)
    service.office_repo = StaticRepository([{"id": "office-1", "name": "Berlin", "timezone": "UTC", "max_capacity": 10}])
    service.skill_repo = StaticRepository([{"id": "skill-a", "name": "Skill A", "min_proficiency": 1}])
    service.schedule_repo = FakeSchedulesRepository()
    return service


def test_iso_week_range_uses_full_monday_to_next_monday_utc() -> None:
    start, end = SchedulerService.iso_week_range(2026, 28)

    assert start == datetime(2026, 7, 6, 0, 0, tzinfo=timezone.utc)
    assert end == datetime(2026, 7, 13, 0, 0, tzinfo=timezone.utc)


def test_iso_week_range_rejects_invalid_week_number() -> None:
    with pytest.raises(HTTPException) as exc_info:
        SchedulerService.iso_week_range(2027, 53)

    assert exc_info.value.status_code == 422


def test_generate_week_loads_the_full_iso_week_and_stores_metadata() -> None:
    service = _service([_demand(6, 9)], [_agent("agent-1")])
    service.schedule_repo = FakeSchedulesRepository(active_week_ids=["old-schedule"])

    result = service.generate_week(ScheduleWeekGenerationRequest(year=2026, week=28))

    assert service.demand_calls == [(datetime(2026, 7, 6, 0, 0, tzinfo=timezone.utc), datetime(2026, 7, 13, 0, 0, tzinfo=timezone.utc))]
    assert result["year"] == 2026
    assert result["week"] == 28
    assert result["week_start"] == datetime(2026, 7, 6, 0, 0, tzinfo=timezone.utc)
    assert result["week_end"] == datetime(2026, 7, 13, 0, 0, tzinfo=timezone.utc)
    assert result["archived_schedule_ids"] == ["old-schedule"]
    assert result["schedule_id"].startswith("schedule_2026_W28_")
    assert result["schedule_ids"] == [f"{result['schedule_id']}_d0"]
    assert result["document_count"] == 1

    assert len(service.schedule_repo.created) == 1
    document_id, document = service.schedule_repo.created[0]
    assert document_id == f"{result['schedule_id']}_d0"
    assert document["year"] == 2026
    assert document["week"] == 28
    assert document["status"] == "active"
    assert document["generation_scope"] == "iso_week"
    assert document["generation_batch_id"] == result["schedule_id"]
    assert document["day_index"] == 0


def test_generate_week_creates_shards_before_archiving_previous_actives() -> None:
    service = _service([_demand(6, 9)], [_agent("agent-1")])
    service.schedule_repo = FakeSchedulesRepository(active_week_ids=["old-schedule"])

    result = service.generate_week(ScheduleWeekGenerationRequest(year=2026, week=28))

    assert service.schedule_repo.events == ["create", "archive"]
    year, week, exclude_ids = service.schedule_repo.archive_calls[0]
    assert (year, week) == (2026, 28)
    assert exclude_ids == tuple(result["schedule_ids"])


def test_generate_week_splits_assignments_into_one_document_per_utc_day() -> None:
    service = _service(
        [_demand(6, 9), _demand(8, 9), _demand(8, 10)],
        [_agent("agent-1"), _agent("agent-2")],
    )

    result = service.generate_week(ScheduleWeekGenerationRequest(year=2026, week=28))

    assert result["document_count"] == 2
    assert len(service.schedule_repo.created) == 2

    (monday_id, monday_doc), (wednesday_id, wednesday_doc) = service.schedule_repo.created
    assert monday_id.endswith("_d0")
    assert wednesday_id.endswith("_d1")
    assert monday_doc["start_at"] == datetime(2026, 7, 6, 0, 0, tzinfo=timezone.utc)
    assert monday_doc["end_at"] == datetime(2026, 7, 7, 0, 0, tzinfo=timezone.utc)
    assert wednesday_doc["start_at"] == datetime(2026, 7, 8, 0, 0, tzinfo=timezone.utc)
    assert wednesday_doc["end_at"] == datetime(2026, 7, 9, 0, 0, tzinfo=timezone.utc)
    assert len(monday_doc["assignments"]) == 1
    assert len(wednesday_doc["assignments"]) == 2
    assert {slot["slot_start"].date().isoformat() for slot in monday_doc["assignments"]} == {"2026-07-06"}
    assert {slot["slot_start"].date().isoformat() for slot in wednesday_doc["assignments"]} == {"2026-07-08"}
    assert monday_doc["generation_batch_id"] == wednesday_doc["generation_batch_id"] == result["schedule_id"]

    # The response still aggregates the whole week across shards.
    assert len(result["assignments"]) == 3
    assert result["total_required"] == 3
    assert result["total_assigned"] == 3


def test_generate_week_does_not_archive_previous_schedule_when_generation_fails() -> None:
    service = _service([], [_agent("agent-1")])
    service.schedule_repo = FakeSchedulesRepository(active_week_ids=["old-schedule"])

    with pytest.raises(HTTPException):
        service.generate_week(ScheduleWeekGenerationRequest(year=2026, week=28))

    assert service.schedule_repo.archive_calls == []
    assert service.schedule_repo.created == []


def test_generate_week_does_not_archive_previous_schedule_when_persist_fails() -> None:
    service = _service([_demand(6, 9)], [_agent("agent-1")])
    service.schedule_repo = FakeSchedulesRepository(active_week_ids=["old-schedule"], fail_on_create=True)

    with pytest.raises(RuntimeError):
        service.generate_week(ScheduleWeekGenerationRequest(year=2026, week=28))

    assert service.schedule_repo.archive_calls == []
    assert service.schedule_repo.created == []


def test_weekly_max_hours_is_respected_across_generated_week() -> None:
    service = _service([_demand(6, 9), _demand(6, 10)], [_agent("agent-1", weekly_max_hours=1.0)])

    result = service.generate_week(ScheduleWeekGenerationRequest(year=2026, week=28))

    assigned_counts = [len(assignment["assigned_agent_ids"]) for assignment in result["assignments"]]
    assert assigned_counts == [1, 0]
    assert result["total_assigned"] == 1
    assert result["uncovered_demand"] == 1


def test_weekly_generation_balances_sequential_slots_across_available_agents() -> None:
    service = _service(
        [_demand(6, 9), _demand(6, 10)],
        [_agent("agent-a", weekly_max_hours=40.0), _agent("agent-b", weekly_max_hours=40.0)],
    )

    result = service.generate_week(ScheduleWeekGenerationRequest(year=2026, week=28))

    assert result["assignments"][0]["assigned_agent_ids"] == ["agent-a"]
    assert result["assignments"][1]["assigned_agent_ids"] == ["agent-b"]
