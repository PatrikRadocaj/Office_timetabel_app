"""Firestore repository helper tests."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.repositories.firestore_repository import FirestoreRepository
from app.repositories.schedules_repository import SchedulesRepository


class _AggregationValue:
    def __init__(self, value: int) -> None:
        self.value = value


class _AggregationQuery:
    def __init__(self, value: int) -> None:
        self.value = value

    def get(self) -> list[list[_AggregationValue]]:
        return [[_AggregationValue(self.value)]]


class _CountableQuery:
    def __init__(self, value: int) -> None:
        self.value = value
        self.count_alias: str | None = None
        self.stream_called = False

    def count(self, alias: str | None = None) -> _AggregationQuery:
        self.count_alias = alias
        return _AggregationQuery(self.value)

    def stream(self) -> list[Any]:
        self.stream_called = True
        return []


class _StreamOnlyQuery:
    def __init__(self, stream_size: int) -> None:
        self.stream_size = stream_size

    def stream(self) -> list[object]:
        return [object() for _ in range(self.stream_size)]


class _BadAggregationQuery:
    def get(self) -> str:
        return "unexpected"


class _BadAggregationCountableQuery:
    def __init__(self, stream_size: int) -> None:
        self.stream_size = stream_size

    def count(self, alias: str | None = None) -> _BadAggregationQuery:
        return _BadAggregationQuery()

    def stream(self) -> list[object]:
        return [object() for _ in range(self.stream_size)]


class _DocSnapshot:
    def __init__(self, document_id: str, payload: dict[str, Any]) -> None:
        self.id = document_id
        self._payload = payload

    def to_dict(self) -> dict[str, Any]:
        return dict(self._payload)


class _FilterOnlyQuery:
    def __init__(self, rows: list[_DocSnapshot]) -> None:
        self.rows = rows
        self.where_calls: list[tuple[str, str, Any]] = []

    def where(self, field_name: str, op: str, value: Any) -> "_FilterOnlyQuery":
        self.where_calls.append((field_name, op, value))
        return self

    def stream(self) -> list[_DocSnapshot]:
        active_value = None
        for field_name, _, value in self.where_calls:
            if field_name == "status":
                active_value = value
        if active_value is None:
            return list(self.rows)
        return [row for row in self.rows if row.to_dict().get("status") == active_value]


def test_count_uses_firestore_aggregation_when_available() -> None:
    repo = object.__new__(FirestoreRepository)
    repo.collection = _CountableQuery(42)

    count = repo.count()

    assert count == 42
    assert repo.collection.count_alias == "total"
    assert repo.collection.stream_called is False


def test_count_falls_back_to_stream_when_aggregation_is_unavailable() -> None:
    repo = object.__new__(FirestoreRepository)
    repo.collection = _StreamOnlyQuery(3)

    assert repo.count() == 3


def test_count_logs_debug_when_aggregation_result_shape_is_unsupported(caplog) -> None:
    repo = object.__new__(FirestoreRepository)
    repo.collection_name = "test-collection"
    repo.collection = _BadAggregationCountableQuery(4)

    with caplog.at_level("DEBUG"):
        count = repo.count()

    assert count == 4
    assert "Falling back to streaming count for collection 'test-collection'" in caplog.text


def test_schedules_list_active_sorts_in_memory_without_order_by_query() -> None:
    repo = object.__new__(SchedulesRepository)
    repo.collection = _FilterOnlyQuery(
        [
            _DocSnapshot(
                "schedule-2",
                {
                    "generated_at": datetime(2026, 7, 9, 12, 0, tzinfo=timezone.utc),
                    "status": "active",
                },
            ),
            _DocSnapshot(
                "schedule-1",
                {
                    "generated_at": "2026-07-08T12:00:00+00:00",
                    "status": "active",
                },
            ),
            _DocSnapshot(
                "schedule-cancelled",
                {
                    "generated_at": datetime(2026, 7, 10, 12, 0, tzinfo=timezone.utc),
                    "status": "cancelled",
                },
            ),
        ]
    )

    rows = repo.list_active(order_by="-generated_at", limit=1)

    assert [row["id"] for row in rows] == ["schedule-2"]
    assert repo.collection.where_calls == [("status", "==", "active")]
