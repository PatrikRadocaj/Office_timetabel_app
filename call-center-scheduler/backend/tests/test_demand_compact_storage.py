"""Demand compact-storage regression tests."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from app.models.demand import DailyDemandForecastCreate
from app.services.catalog_service import DemandService


class RecordingDemandRepository:
    def __init__(self, existing: list[dict[str, Any]] | None = None) -> None:
        self.rows = {row["id"]: {**row} for row in existing or []}
        self.created: list[tuple[str | None, dict[str, Any]]] = []
        self.deleted: list[str] = []
        self.list_calls: list[list[tuple[str, str, Any]] | None] = []
        self.prefix_calls: list[str] = []

    def create(self, data: dict[str, Any], document_id: str | None = None) -> dict[str, Any]:
        doc_id = document_id or f"auto-{len(self.rows) + 1}"
        row = {
            **data,
            "id": doc_id,
            "created_at": datetime(2026, 7, 8, tzinfo=timezone.utc),
            "updated_at": datetime(2026, 7, 8, tzinfo=timezone.utc),
        }
        self.rows[doc_id] = row
        self.created.append((document_id, data))
        return row

    def get(self, document_id: str) -> dict[str, Any] | None:
        return self.rows.get(document_id)

    def update(self, document_id: str, data: dict[str, Any]) -> dict[str, Any] | None:
        if document_id not in self.rows:
            return None
        self.rows[document_id] = {**self.rows[document_id], **data}
        return self.rows[document_id]

    def delete(self, document_id: str) -> bool:
        self.deleted.append(document_id)
        return self.rows.pop(document_id, None) is not None

    def list(
        self,
        filters: list[tuple[str, str, Any]] | None = None,
        order_by: str | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        self.list_calls.append(filters)
        rows = list(self.rows.values())
        for field_name, op, value in filters or []:
            if op != "==":
                raise AssertionError(f"Unsupported test filter op: {op}")
            rows = [row for row in rows if row.get(field_name) == value]
        return rows[:limit] if limit is not None else rows

    def list_by_document_id_prefix(self, prefix: str, limit: int | None = None) -> list[dict[str, Any]]:
        self.prefix_calls.append(prefix)
        rows = [row for doc_id, row in self.rows.items() if doc_id.startswith(prefix)]
        return rows[:limit] if limit is not None else rows


class StaticOfficeRepository:
    def get(self, office_id: str) -> dict[str, Any] | None:
        if office_id != "office-1":
            return None
        return {
            "id": "office-1",
            "name": "Office 1",
            "timezone": "Europe/Zagreb",
            "max_capacity": 50,
        }


class StaticSkillRepository:
    def get(self, skill_id: str) -> dict[str, Any] | None:
        if skill_id not in {"skill-a", "skill-b"}:
            return None
        return {
            "id": skill_id,
            "name": skill_id,
            "min_proficiency": 1,
        }


class EmptyScheduleRepository:
    def list(self, order_by: str | None = None) -> list[dict[str, Any]]:
        return []


def make_service(repo: RecordingDemandRepository) -> DemandService:
    service = object.__new__(DemandService)
    service.repo = repo
    service.office_repo = StaticOfficeRepository()
    service.skill_repo = StaticSkillRepository()
    service.schedule_repo = EmptyScheduleRepository()
    return service


def test_create_daily_writes_one_compact_document_for_whole_day() -> None:
    repo = RecordingDemandRepository()
    service = make_service(repo)
    payload = DailyDemandForecastCreate(
        office_id="office-1",
        date=date(2026, 7, 8),
        interval_minutes=30,
        replace_existing_day=True,
        skill_demands=[
            {
                "skill_id": "skill-a",
                "priority": 4,
                "quantities": [0, 2, *([0] * 46)],
            },
            {
                "skill_id": "skill-b",
                "priority": 3,
                "quantities": [1, *([0] * 47)],
            },
        ],
    )

    result = service.create_daily(payload)

    assert len(repo.created) == 1
    document_id, document = repo.created[0]
    assert document_id == "daily_2026-07-08_office-1_30"
    assert document["storage_model"] == "daily_document_v1"
    assert len(document["skill_demands"]) == 2
    assert result["document_count"] == 1
    assert result["created_count"] == 2
    assert result["represented_slot_count"] == 2


def test_list_expands_compact_daily_documents_to_slot_rows() -> None:
    repo = RecordingDemandRepository(
        [
            {
                "id": "daily_2026-07-08_office-1_30",
                "office_id": "office-1",
                "forecast_date": "2026-07-08",
                "interval_minutes": 30,
                "entry_mode": "daily_grid",
                "storage_model": "daily_document_v1",
                "forecast_batch_id": "batch-1",
                "skill_demands": [
                    {
                        "skill_id": "skill-a",
                        "priority": 4,
                        "quantities": [0, 2, *([0] * 46)],
                    }
                ],
                "created_at": datetime(2026, 7, 8, tzinfo=timezone.utc),
                "updated_at": datetime(2026, 7, 8, tzinfo=timezone.utc),
            }
        ]
    )
    service = make_service(repo)

    rows = service.list()

    assert len(rows) == 1
    assert rows[0]["id"] == "daily_2026-07-08_office-1_30_01_skill-a"
    assert rows[0]["source_document_id"] == "daily_2026-07-08_office-1_30"
    assert rows[0]["office_id"] == "office-1"
    assert rows[0]["skill_id"] == "skill-a"
    assert rows[0]["required_agents"] == 2
    assert rows[0]["time_block"] == "00:30"


def test_create_daily_replace_existing_uses_deterministic_prefix_lookup() -> None:
    base_id = "daily_2026-07-08_office-1_30"
    suffix_id = "daily_2026-07-08_office-1_30_extra"
    colliding_office_id = "daily_2026-07-08_office-1_30x_30"
    other_day_id = "daily_2026-07-09_office-1_30"
    repo = RecordingDemandRepository(
        [
            {
                "id": base_id,
                "office_id": "office-1",
                "forecast_date": "2026-07-08",
                "interval_minutes": 30,
                "storage_model": "daily_document_v1",
                "skill_demands": [{"skill_id": "skill-a", "priority": 3, "quantities": [1, *([0] * 47)]}],
            },
            {
                "id": suffix_id,
                "office_id": "office-1",
                "forecast_date": "2026-07-08",
                "interval_minutes": 30,
                "storage_model": "daily_document_v1",
                "skill_demands": [{"skill_id": "skill-a", "priority": 3, "quantities": [0, 1, *([0] * 46)]}],
            },
            {
                "id": colliding_office_id,
                "office_id": "office-1_30x",
                "forecast_date": "2026-07-08",
                "interval_minutes": 30,
                "storage_model": "daily_document_v1",
                "skill_demands": [{"skill_id": "skill-a", "priority": 3, "quantities": [1, *([0] * 47)]}],
            },
            {
                "id": other_day_id,
                "office_id": "office-1",
                "forecast_date": "2026-07-09",
                "interval_minutes": 30,
                "storage_model": "daily_document_v1",
                "skill_demands": [{"skill_id": "skill-a", "priority": 3, "quantities": [1, *([0] * 47)]}],
            },
        ]
    )
    service = make_service(repo)
    payload = DailyDemandForecastCreate(
        office_id="office-1",
        date=date(2026, 7, 8),
        interval_minutes=30,
        replace_existing_day=True,
        skill_demands=[
            {
                "skill_id": "skill-a",
                "priority": 4,
                "quantities": [0, 2, *([0] * 46)],
            }
        ],
    )

    result = service.create_daily(payload)

    assert repo.prefix_calls == [base_id]
    assert repo.list_calls == []
    assert repo.deleted == [base_id, suffix_id]
    assert colliding_office_id in repo.rows
    assert other_day_id in repo.rows
    assert result["deleted_count"] == 2


def test_day_view_uses_deterministic_prefix_and_preserves_additive_suffixes() -> None:
    base_id = "daily_2026-07-08_office-1_30"
    suffix_id = "daily_2026-07-08_office-1_30_extra"
    repo = RecordingDemandRepository(
        [
            {
                "id": base_id,
                "office_id": "office-1",
                "forecast_date": "2026-07-08",
                "interval_minutes": 30,
                "storage_model": "daily_document_v1",
                "skill_demands": [{"skill_id": "skill-a", "priority": 3, "quantities": [1, *([0] * 47)]}],
            },
            {
                "id": suffix_id,
                "office_id": "office-1",
                "forecast_date": "2026-07-08",
                "interval_minutes": 30,
                "storage_model": "daily_document_v1",
                "skill_demands": [{"skill_id": "skill-a", "priority": 3, "quantities": [2, *([0] * 47)]}],
            },
            {
                "id": "daily_2026-07-09_office-1_30",
                "office_id": "office-1",
                "forecast_date": "2026-07-09",
                "interval_minutes": 30,
                "storage_model": "daily_document_v1",
                "skill_demands": [{"skill_id": "skill-a", "priority": 3, "quantities": [9, *([0] * 47)]}],
            },
        ]
    )
    service = make_service(repo)

    day = service.day_view("office-1", date(2026, 7, 8), 30)

    assert repo.prefix_calls == [base_id]
    assert repo.list_calls == []
    assert day["blocks"][0]["total_required"] == 3
    assert day["blocks"][0]["totals_by_skill"] == {"skill-a": 3}
