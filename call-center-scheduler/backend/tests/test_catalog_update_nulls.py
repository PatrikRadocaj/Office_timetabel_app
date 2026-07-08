"""Catalog update regression tests."""

from __future__ import annotations

from typing import Any

from app.models.office import OfficeUpdate
from app.models.skill import SkillUpdate
from app.services.catalog_service import OfficeService, SkillService


class RecordingRepository:
    def __init__(self, existing: dict[str, Any]) -> None:
        self.existing = existing
        self.updated_id: str | None = None
        self.updated_data: dict[str, Any] | None = None

    def update(self, document_id: str, data: dict[str, Any]) -> dict[str, Any]:
        self.updated_id = document_id
        self.updated_data = {**data}
        return {**self.existing, **data, "id": document_id}


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
