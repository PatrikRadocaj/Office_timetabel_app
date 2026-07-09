"""Firestore repository helper tests."""

from __future__ import annotations

from typing import Any

from app.repositories.firestore_repository import FirestoreRepository


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
