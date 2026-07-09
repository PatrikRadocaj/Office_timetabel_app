"""Catalog update regression tests."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi import HTTPException

from app.models.agent import AgentUpdate
from app.models.office import OfficeUpdate
from app.models.skill import SkillUpdate
from app.services.catalog_service import AgentService, OfficeService, SkillService


class RecordingRepository:
    def __init__(self, existing: dict[str, Any], rows: list[dict[str, Any]] | None = None) -> None:
        self.existing = existing
        self.rows = rows or [existing]
        self.updated_id: str | None = None
        self.updated_data: dict[str, Any] | None = None
        self.deleted_id: str | None = None

    def get(self, document_id: str) -> dict[str, Any] | None:
        return next((row for row in self.rows if row.get("id") == document_id), None)

    def list(
        self,
        filters: list[tuple[str, str, Any]] | None = None,
        order_by: str | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        rows = list(self.rows)
        for field_name, op, value in filters or []:
            if op != "==":
                raise AssertionError(f"Unsupported test filter op: {op}")
            rows = [row for row in rows if row.get(field_name) == value]
        return rows[:limit] if limit is not None else rows

    def count(self, filters: list[tuple[str, str, Any]] | None = None) -> int:
        return len(self.list(filters=filters))

    def update(self, document_id: str, data: dict[str, Any]) -> dict[str, Any]:
        self.updated_id = document_id
        self.updated_data = {**data}
        return {**self.existing, **data, "id": document_id}

    def delete(self, document_id: str) -> bool:
        self.deleted_id = document_id
        before_count = len(self.rows)
        self.rows = [row for row in self.rows if row.get("id") != document_id]
        return len(self.rows) < before_count


class StaticRepository:
    def __init__(self, rows: list[dict[str, Any]] | None = None) -> None:
        self.rows = rows or []

    def list(
        self,
        filters: list[tuple[str, str, Any]] | None = None,
        order_by: str | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        rows = list(self.rows)
        for field_name, op, value in filters or []:
            if op != "==":
                raise AssertionError(f"Unsupported test filter op: {op}")
            rows = [row for row in rows if row.get(field_name) == value]
        return rows[:limit] if limit is not None else rows

    def count(self, filters: list[tuple[str, str, Any]] | None = None) -> int:
        return len(self.list(filters=filters))


class StaticSettings:
    max_weekly_hours_hard_limit = 40


def test_office_update_preserves_explicit_null_address() -> None:
    repo = RecordingRepository(
        {
            "id": "office-1",
            "name": "Zagreb",
            "timezone": "Europe/Zagreb",
            "max_capacity": 50,
            "address": "Old address",
        }
    )
    service = object.__new__(OfficeService)
    service.repo = repo

    updated = service.update("office-1", OfficeUpdate(address=None))

    assert repo.updated_id == "office-1"
    assert repo.updated_data == {"address": None}
    assert updated["address"] is None


def test_office_update_rejects_duplicate_name_except_current_office() -> None:
    repo = RecordingRepository(
        {
            "id": "office-1",
            "name": "Zagreb",
            "timezone": "Europe/Zagreb",
            "max_capacity": 50,
        },
        rows=[
            {"id": "office-1", "name": "Zagreb", "timezone": "Europe/Zagreb", "max_capacity": 50},
            {"id": "office-2", "name": "Split", "timezone": "Europe/Zagreb", "max_capacity": 20},
        ],
    )
    service = object.__new__(OfficeService)
    service.repo = repo

    with pytest.raises(HTTPException) as exc_info:
        service.update("office-1", OfficeUpdate(name="Split"))

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail == "Office name already exists"
    assert repo.updated_id is None


def test_office_delete_rejects_existing_references_with_counts() -> None:
    repo = RecordingRepository(
        {
            "id": "office-1",
            "name": "Zagreb",
            "timezone": "Europe/Zagreb",
            "max_capacity": 50,
        }
    )
    service = object.__new__(OfficeService)
    service.repo = repo
    service.agents_repo = StaticRepository(
        [
            {"id": "agent-1", "office_id": "office-1"},
            {"id": "agent-2", "office_id": "office-2"},
        ]
    )
    service.demand_repo = StaticRepository(
        [
            {"id": "demand-1", "office_id": "office-1"},
            {"id": "demand-2", "office_id": "office-1"},
            {"id": "demand-3", "office_id": "office-2"},
        ]
    )
    service.schedule_repo = StaticRepository(
        [
            {"id": "schedule-1", "assignments": [{"office_id": "office-1", "skill_id": "skill-a"}]},
            {"id": "schedule-2", "assignments": [{"office_id": "office-2", "skill_id": "skill-a"}]},
        ]
    )

    with pytest.raises(HTTPException) as exc_info:
        service.delete("office-1")

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail["reference_counts"] == {
        "agents": 1,
        "demand_forecasts": 2,
        "schedules": 1,
    }
    assert repo.deleted_id is None


def test_skill_update_preserves_explicit_null_description() -> None:
    repo = RecordingRepository(
        {
            "id": "skill-1",
            "name": "Support",
            "description": "Old description",
            "min_proficiency": 3,
        }
    )
    service = object.__new__(SkillService)
    service.repo = repo

    updated = service.update("skill-1", SkillUpdate(description=None))

    assert repo.updated_id == "skill-1"
    assert repo.updated_data == {"description": None}
    assert updated["description"] is None


def test_skill_update_rejects_duplicate_name_except_current_skill() -> None:
    repo = RecordingRepository(
        {
            "id": "skill-1",
            "name": "Support",
            "description": "Old description",
            "min_proficiency": 3,
        },
        rows=[
            {"id": "skill-1", "name": "Support", "min_proficiency": 3},
            {"id": "skill-2", "name": "Billing", "min_proficiency": 2},
        ],
    )
    service = object.__new__(SkillService)
    service.repo = repo

    with pytest.raises(HTTPException) as exc_info:
        service.update("skill-1", SkillUpdate(name="Billing"))

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail == "Skill name already exists"
    assert repo.updated_id is None


def test_skill_delete_rejects_existing_references_with_counts() -> None:
    repo = RecordingRepository(
        {
            "id": "skill-a",
            "name": "Support",
            "description": "Old description",
            "min_proficiency": 3,
        }
    )
    service = object.__new__(SkillService)
    service.repo = repo
    service.agents_repo = StaticRepository(
        [
            {"id": "agent-1", "skills": [{"skill_id": "skill-a", "proficiency": 3}]},
            {"id": "agent-2", "skills": [{"skill_id": "skill-b", "proficiency": 2}]},
        ]
    )
    service.demand_repo = StaticRepository(
        [
            {"id": "legacy-demand", "skill_id": "skill-a"},
            {"id": "daily-demand", "skill_demands": [{"skill_id": "skill-a", "quantities": [1]}]},
            {"id": "other-demand", "skill_demands": [{"skill_id": "skill-b", "quantities": [1]}]},
        ]
    )
    service.schedule_repo = StaticRepository(
        [
            {"id": "schedule-1", "assignments": [{"office_id": "office-1", "skill_id": "skill-a"}]},
            {"id": "schedule-2", "assignments": [{"office_id": "office-1", "skill_id": "skill-b"}]},
        ]
    )

    with pytest.raises(HTTPException) as exc_info:
        service.delete("skill-a")

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail["reference_counts"] == {
        "agents": 1,
        "demand_forecasts": 2,
        "schedules": 1,
    }
    assert repo.deleted_id is None


def test_agent_update_enforces_weekly_hours_hard_limit() -> None:
    repo = RecordingRepository({"id": "agent-1", "weekly_max_hours": 40})
    service = object.__new__(AgentService)
    service.repo = repo
    service.office_repo = StaticRepository()
    service.skill_repo = StaticRepository()
    service.settings = StaticSettings()

    with pytest.raises(HTTPException) as exc_info:
        service.update("agent-1", AgentUpdate(weekly_max_hours=41))

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "weekly_max_hours exceeds hard safety limit (40)"
    assert repo.updated_id is None
