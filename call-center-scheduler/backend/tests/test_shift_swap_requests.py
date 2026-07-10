"""Shift-swap request workflow and route authorization tests."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

import app.api.routers.shift_swap_requests as shift_swap_router
from app.api.deps import get_current_user
from app.models.shift_swap_request import ShiftSwapRequestCreate, ShiftSwapRequestReview, ShiftSwapRequestStatus
from app.services.shift_swap_request_service import ShiftSwapRequestService, assignment_key

app = FastAPI()
app.include_router(shift_swap_router.options_router, prefix="/api/v1")
app.include_router(shift_swap_router.me_router, prefix="/api/v1")
app.include_router(shift_swap_router.admin_router, prefix="/api/v1")


class FakeAgentsRepository:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows

    def list(self, filters=None, limit=None) -> list[dict[str, Any]]:
        rows = [dict(row) for row in self.rows]
        for field_name, op, value in filters or []:
            if op != "==":
                raise AssertionError(f"Unsupported filter op: {op}")
            rows = [row for row in rows if row.get(field_name) == value]
        return rows[:limit] if limit is not None else rows

    def update(self, document_id: str, data: dict[str, Any]) -> dict[str, Any] | None:
        for index, row in enumerate(self.rows):
            if row["id"] == document_id:
                updated = {**row, **data}
                self.rows[index] = updated
                return dict(updated)
        return None


class StaticRepository:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows

    def list(self, filters=None, order_by=None, limit=None) -> list[dict[str, Any]]:
        rows = [dict(row) for row in self.rows]
        for field_name, op, value in filters or []:
            if op != "==":
                raise AssertionError(f"Unsupported filter op: {op}")
            rows = [row for row in rows if row.get(field_name) == value]
        return rows[:limit] if limit is not None else rows


class FakeSchedulesRepository:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows
        self.updated: list[tuple[str, dict[str, Any]]] = []

    def list_active(self, order_by: str | None = None, limit: int | None = None) -> list[dict[str, Any]]:
        rows = [dict(row) for row in self.rows if row.get("status", "active") == "active"]
        if order_by:
            reverse = order_by.startswith("-")
            field_name = order_by[1:] if reverse else order_by
            rows.sort(key=lambda row: row.get(field_name), reverse=reverse)
        return rows[:limit] if limit is not None else rows

    def update(self, document_id: str, data: dict[str, Any]) -> dict[str, Any] | None:
        self.updated.append((document_id, data))
        for index, row in enumerate(self.rows):
            if row["id"] == document_id:
                updated = {**row, **data}
                self.rows[index] = updated
                return dict(updated)
        return None


class FakeShiftSwapRequestsRepository:
    def __init__(self, rows: list[dict[str, Any]] | None = None) -> None:
        self.rows = rows or []
        self.created_data: dict[str, Any] | None = None
        self.updated_id: str | None = None
        self.updated_data: dict[str, Any] | None = None

    def list(self, filters=None, order_by=None, limit=None) -> list[dict[str, Any]]:
        rows = [dict(row) for row in self.rows]
        for field_name, op, value in filters or []:
            if op != "==":
                raise AssertionError(f"Unsupported filter op: {op}")
            rows = [row for row in rows if row.get(field_name) == value]
        return rows[:limit] if limit is not None else rows

    def create(self, data: dict[str, Any], document_id: str | None = None) -> dict[str, Any]:
        self.created_data = {**data}
        created = {"id": document_id or "swap-new", **data}
        self.rows.append(created)
        return dict(created)

    def get(self, document_id: str) -> dict[str, Any] | None:
        row = next((row for row in self.rows if row["id"] == document_id), None)
        return dict(row) if row else None

    def update(self, document_id: str, data: dict[str, Any]) -> dict[str, Any] | None:
        self.updated_id = document_id
        self.updated_data = {**data}
        for index, row in enumerate(self.rows):
            if row["id"] == document_id:
                updated = {**row, **data}
                self.rows[index] = updated
                return dict(updated)
        return None


def _dt(hour: int) -> datetime:
    return datetime(2026, 8, 3, hour, 0, tzinfo=timezone.utc)


def _assignment(start_hour: int, skill_id: str, assigned_agent_ids: list[str], office_id: str = "office-1") -> dict[str, Any]:
    return {
        "slot_start": _dt(start_hour),
        "slot_end": _dt(start_hour + 1),
        "office_id": office_id,
        "skill_id": skill_id,
        "assigned_agent_ids": assigned_agent_ids,
        "required_agents": len(assigned_agent_ids),
        "coverage_ratio": 1.0,
        "gap": 0,
    }


def _assignment_window(
    start: datetime,
    end: datetime,
    skill_id: str,
    assigned_agent_ids: list[str],
    office_id: str = "office-1",
) -> dict[str, Any]:
    return {
        "slot_start": start,
        "slot_end": end,
        "office_id": office_id,
        "skill_id": skill_id,
        "assigned_agent_ids": assigned_agent_ids,
        "required_agents": len(assigned_agent_ids),
        "coverage_ratio": 1.0,
        "gap": 0,
    }


def _agent(
    agent_id: str,
    user_id: str,
    email: str,
    skills: list[str] | None = None,
    availability: list[dict[str, int]] | None = None,
    office_id: str = "office-1",
) -> dict[str, Any]:
    return {
        "id": agent_id,
        "user_id": user_id,
        "email": email,
        "full_name": f"Agent {agent_id}",
        "office_id": office_id,
        "weekly_max_hours": 40,
        "min_rest_hours": 10,
        "skills": [{"skill_id": skill_id, "proficiency": 3} for skill_id in (skills or ["skill-a", "skill-b"])],
        "availability": availability if availability is not None else [{"day_of_week": 0, "start_hour": 8, "end_hour": 18}],
        "is_active": True,
    }


def _schedule(source: dict[str, Any] | None = None, target: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "id": "schedule-1",
        "status": "active",
        "generated_at": "2026-07-09T10:00:00+00:00",
        "assignments": [
            source or _assignment(9, "skill-a", ["agent-1"]),
            target or _assignment(11, "skill-b", ["agent-2"]),
        ],
    }


def _service(
    agents: list[dict[str, Any]] | None = None,
    schedules: list[dict[str, Any]] | None = None,
    requests: list[dict[str, Any]] | None = None,
) -> ShiftSwapRequestService:
    service = ShiftSwapRequestService()
    service._agents_repo = FakeAgentsRepository(
        agents or [_agent("agent-1", "user-1", "agent@example.com"), _agent("agent-2", "user-2", "other@example.com")]
    )
    service._offices_repo = StaticRepository([{"id": "office-1", "name": "Berlin", "timezone": "UTC"}])
    service._skills_repo = StaticRepository(
        [
            {"id": "skill-a", "name": "Skill A", "min_proficiency": 1},
            {"id": "skill-b", "name": "Skill B", "min_proficiency": 1},
        ]
    )
    service._schedules_repo = FakeSchedulesRepository(schedules or [_schedule()])
    service._repo = FakeShiftSwapRequestsRepository(requests)
    return service


def _current_user(user_id: str = "user-1", role: str = "agent") -> dict[str, Any]:
    return {
        "id": user_id,
        "email": f"{user_id}@example.com",
        "full_name": f"User {user_id}",
        "role": role,
        "is_active": True,
    }


def _valid_payload() -> ShiftSwapRequestCreate:
    source, target = _schedule()["assignments"]
    return ShiftSwapRequestCreate(
        source_schedule_id="schedule-1",
        source_assignment_key=assignment_key(source),
        target_schedule_id="schedule-1",
        target_assignment_key=assignment_key(target),
        target_agent_id="agent-2",
        reason="Can we trade?",
    )


def test_options_include_current_agent_shifts_and_same_office_targets() -> None:
    options = _service().options_for_agent(_current_user("user-1"))

    assert len(options["my_shifts"]) == 1
    assert options["my_shifts"][0]["agent_id"] == "agent-1"
    assert len(options["target_shifts"]) == 1
    assert options["target_shifts"][0]["agent_id"] == "agent-2"


def test_options_merge_adjacent_slots_into_one_shift_block() -> None:
    schedule = {
        "id": "schedule-1",
        "status": "active",
        "generated_at": "2026-07-09T10:00:00+00:00",
        "assignments": [
            _assignment(9, "skill-a", ["agent-1"]),
            _assignment(10, "skill-b", ["agent-1"]),
        ],
    }

    options = _service(schedules=[schedule]).options_for_agent(_current_user("user-1"))

    assert len(options["my_shifts"]) == 1
    block = options["my_shifts"][0]
    assert block["slot_start"] == _dt(9)
    assert block["slot_end"] == _dt(11)
    assert len(block["assignment_refs"]) == 2
    assert block["skill_name"] == "Multiple skills: Skill A, Skill B"


def test_options_keep_gapped_slots_as_separate_shift_blocks() -> None:
    schedule = {
        "id": "schedule-1",
        "status": "active",
        "generated_at": "2026-07-09T10:00:00+00:00",
        "assignments": [
            _assignment(9, "skill-a", ["agent-1"]),
            _assignment(11, "skill-a", ["agent-1"]),
        ],
    }

    options = _service(schedules=[schedule]).options_for_agent(_current_user("user-1"))

    assert len(options["my_shifts"]) == 2
    assert [block["slot_start"] for block in options["my_shifts"]] == [_dt(9), _dt(11)]


def test_agent_can_create_valid_shift_swap_request() -> None:
    created = _service().create_for_agent(_current_user("user-1"), _valid_payload())

    assert created["requester_agent_id"] == "agent-1"
    assert created["target_agent_id"] == "agent-2"
    assert created["status"] == "pending"
    assert created["source_shift"]["skill_id"] == "skill-a"
    assert created["target_shift"]["skill_id"] == "skill-b"


def test_create_rejects_source_shift_not_owned_by_requester() -> None:
    payload = _valid_payload()
    agents = [
        _agent("agent-1", "user-1", "agent@example.com"),
        _agent("agent-2", "user-2", "other@example.com"),
        _agent("agent-3", "user-3", "third@example.com"),
    ]

    with pytest.raises(HTTPException) as exc_info:
        _service(agents=agents).create_for_agent(_current_user("user-3"), payload)

    assert exc_info.value.status_code == 403


def test_create_rejects_office_mismatch() -> None:
    source = _assignment(9, "skill-a", ["agent-1"], office_id="office-1")
    target = _assignment(11, "skill-b", ["agent-2"], office_id="office-2")
    service = _service(schedules=[_schedule(source, target)])
    service._offices_repo = StaticRepository(
        [
            {"id": "office-1", "name": "Berlin", "timezone": "UTC"},
            {"id": "office-2", "name": "London", "timezone": "UTC"},
        ]
    )
    payload = ShiftSwapRequestCreate(
        source_schedule_id="schedule-1",
        source_assignment_key=assignment_key(source),
        target_schedule_id="schedule-1",
        target_assignment_key=assignment_key(target),
        target_agent_id="agent-2",
    )

    with pytest.raises(HTTPException) as exc_info:
        service.create_for_agent(_current_user("user-1"), payload)

    assert exc_info.value.status_code == 409
    assert "same office" in str(exc_info.value.detail)


def test_create_rejects_skill_mismatch() -> None:
    agents = [_agent("agent-1", "user-1", "agent@example.com"), _agent("agent-2", "user-2", "other@example.com", skills=["skill-b"])]

    with pytest.raises(HTTPException) as exc_info:
        _service(agents=agents).create_for_agent(_current_user("user-1"), _valid_payload())

    assert exc_info.value.status_code == 409
    assert "source shift skill" in str(exc_info.value.detail)


def test_create_rejects_availability_conflict() -> None:
    agents = [
        _agent("agent-1", "user-1", "agent@example.com"),
        _agent("agent-2", "user-2", "other@example.com", availability=[{"day_of_week": 0, "start_hour": 12, "end_hour": 18}]),
    ]

    with pytest.raises(HTTPException) as exc_info:
        _service(agents=agents).create_for_agent(_current_user("user-1"), _valid_payload())

    assert exc_info.value.status_code == 409
    assert "not available" in str(exc_info.value.detail)


def test_create_rejects_overlapping_source_and_target_shifts() -> None:
    source = _assignment_window(
        datetime(2026, 8, 3, 9, 0, tzinfo=timezone.utc),
        datetime(2026, 8, 3, 10, 0, tzinfo=timezone.utc),
        "skill-a",
        ["agent-1"],
    )
    target = _assignment_window(
        datetime(2026, 8, 3, 9, 30, tzinfo=timezone.utc),
        datetime(2026, 8, 3, 10, 30, tzinfo=timezone.utc),
        "skill-b",
        ["agent-2"],
    )
    payload = ShiftSwapRequestCreate(
        source_schedule_id="schedule-1",
        source_assignment_key=assignment_key(source),
        target_schedule_id="schedule-1",
        target_assignment_key=assignment_key(target),
        target_agent_id="agent-2",
    )

    with pytest.raises(HTTPException) as exc_info:
        _service(schedules=[_schedule(source, target)]).create_for_agent(_current_user("user-1"), payload)

    assert exc_info.value.status_code == 409
    assert "overlap" in str(exc_info.value.detail).lower()


def test_create_rejects_duplicate_pending_request() -> None:
    payload = _valid_payload()
    existing = {
        "id": "swap-existing",
        "requester_agent_id": "agent-1",
        "target_agent_id": "agent-2",
        "source_schedule_id": payload.source_schedule_id,
        "source_assignment_key": payload.source_assignment_key,
        "target_schedule_id": payload.target_schedule_id,
        "target_assignment_key": payload.target_assignment_key,
        "status": ShiftSwapRequestStatus.PENDING.value,
    }

    with pytest.raises(HTTPException) as exc_info:
        _service(requests=[existing]).create_for_agent(_current_user("user-1"), payload)

    assert exc_info.value.status_code == 409
    assert "already pending" in str(exc_info.value.detail)


def test_approval_applies_swap_to_schedule_assignments() -> None:
    service = _service()
    created = service.create_for_agent(_current_user("user-1"), _valid_payload())

    reviewed = service.review(
        created["id"],
        ShiftSwapRequestReview(status=ShiftSwapRequestStatus.APPROVED, review_note="Approved"),
        _current_user("admin-1", "admin"),
    )

    assert reviewed["status"] == "approved"
    schedule = service.schedules_repo.rows[0]
    source, target = schedule["assignments"]
    assert source["assigned_agent_ids"] == ["agent-2"]
    assert target["assigned_agent_ids"] == ["agent-1"]
    assert reviewed["schedule_update"]["applied"] is True


def test_approval_applies_swap_to_all_assignments_in_shift_blocks() -> None:
    schedule = {
        "id": "schedule-1",
        "status": "active",
        "generated_at": "2026-07-09T10:00:00+00:00",
        "assignments": [
            _assignment(9, "skill-a", ["agent-1"]),
            _assignment(10, "skill-b", ["agent-1"]),
            _assignment(12, "skill-a", ["agent-2"]),
            _assignment(13, "skill-b", ["agent-2"]),
        ],
    }
    service = _service(schedules=[schedule])
    options = service.options_for_agent(_current_user("user-1"))
    source = options["my_shifts"][0]
    target = options["target_shifts"][0]

    created = service.create_for_agent(
        _current_user("user-1"),
        ShiftSwapRequestCreate(
            source_schedule_id=source["schedule_id"],
            source_assignment_key=source["assignment_key"],
            source_assignment_refs=source["assignment_refs"],
            target_schedule_id=target["schedule_id"],
            target_assignment_key=target["assignment_key"],
            target_assignment_refs=target["assignment_refs"],
            target_agent_id=target["agent_id"],
        ),
    )
    reviewed = service.review(
        created["id"],
        ShiftSwapRequestReview(status=ShiftSwapRequestStatus.APPROVED),
        _current_user("admin-1", "admin"),
    )

    assignments = service.schedules_repo.rows[0]["assignments"]
    assert [assignment["assigned_agent_ids"] for assignment in assignments] == [
        ["agent-2"],
        ["agent-2"],
        ["agent-1"],
        ["agent-1"],
    ]
    assert reviewed["schedule_update"]["source_assignment_count"] == 2
    assert reviewed["schedule_update"]["target_assignment_count"] == 2


def test_copy_assignment_rejects_duplicate_agent() -> None:
    with pytest.raises(HTTPException) as exc_info:
        ShiftSwapRequestService._copy_assignment_with_swapped_agent(
            _assignment(9, "skill-a", ["agent-1", "agent-2"]),
            "agent-1",
            "agent-2",
        )

    assert exc_info.value.status_code == 409
    assert "duplicate assignment" in str(exc_info.value.detail).lower()


def test_approval_revalidates_current_schedule_state() -> None:
    service = _service(requests=[])
    created = service.create_for_agent(_current_user("user-1"), _valid_payload())
    service.schedules_repo.rows[0]["assignments"][0]["assigned_agent_ids"] = ["agent-3"]

    with pytest.raises(HTTPException) as exc_info:
        service.review(created["id"], ShiftSwapRequestReview(status=ShiftSwapRequestStatus.APPROVED), _current_user("admin-1", "admin"))

    assert exc_info.value.status_code == 403


ADMIN_USER = {"id": "admin-1", "email": "admin@example.com", "full_name": "Admin", "role": "admin", "is_active": True}
AGENT_USER = {"id": "user-1", "email": "agent@example.com", "full_name": "Agent", "role": "agent", "is_active": True}

client = TestClient(app)


@pytest.fixture(autouse=True)
def _clear_overrides():
    yield
    app.dependency_overrides.clear()


def _login_as(user: dict[str, Any]) -> None:
    app.dependency_overrides[get_current_user] = lambda: user


def test_shift_swap_routes_require_token() -> None:
    assert client.get("/api/v1/me/shift-swap-options").status_code == 401
    assert client.get("/api/v1/me/shift-swap-requests").status_code == 401
    assert client.post("/api/v1/me/shift-swap-requests", json={}).status_code == 401
    assert client.get("/api/v1/shift-swap-requests").status_code == 401
    assert client.put("/api/v1/shift-swap-requests/swap-1/review", json={"status": "approved"}).status_code == 401


def test_admin_shift_swap_routes_reject_non_admin() -> None:
    _login_as(AGENT_USER)

    assert client.get("/api/v1/shift-swap-requests").status_code == 403
    assert client.put("/api/v1/shift-swap-requests/swap-1/review", json={"status": "approved"}).status_code == 403


def test_agent_can_create_and_list_shift_swap_requests_via_route(monkeypatch: pytest.MonkeyPatch) -> None:
    service = _service()
    monkeypatch.setattr(shift_swap_router, "service", service)
    _login_as(AGENT_USER)

    payload = _valid_payload().model_dump()
    created = client.post("/api/v1/me/shift-swap-requests", json=payload)
    assert created.status_code == 200
    assert created.json()["requester_agent_id"] == "agent-1"

    listed = client.get("/api/v1/me/shift-swap-requests")
    assert listed.status_code == 200
    assert [row["id"] for row in listed.json()] == ["swap-new"]


def test_admin_can_list_and_review_shift_swap_requests_via_route(monkeypatch: pytest.MonkeyPatch) -> None:
    service = _service()
    created = service.create_for_agent(_current_user("user-1"), _valid_payload())
    monkeypatch.setattr(shift_swap_router, "service", service)
    _login_as(ADMIN_USER)

    listed = client.get("/api/v1/shift-swap-requests")
    assert listed.status_code == 200
    assert listed.json()[0]["id"] == created["id"]

    reviewed = client.put(f"/api/v1/shift-swap-requests/{created['id']}/review", json={"status": "rejected", "review_note": "No"})
    assert reviewed.status_code == 200
    assert reviewed.json()["status"] == "rejected"
