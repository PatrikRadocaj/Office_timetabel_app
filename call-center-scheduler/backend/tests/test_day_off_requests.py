"""Day-off request workflow service and route authorization tests."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

import app.api.routers.day_off_requests as day_off_requests_router
from app.api.deps import get_current_user
from app.models.day_off_request import DayOffRequestCreate, DayOffRequestReview, DayOffRequestStatus
from app.services.day_off_request_service import DayOffRequestService

app = FastAPI()
app.include_router(day_off_requests_router.me_router, prefix="/api/v1")
app.include_router(day_off_requests_router.admin_router, prefix="/api/v1")


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


class FakeDayOffRequestsRepository:
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
        created = {"id": document_id or "day-off-new", **data}
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


def _service(
    agents: list[dict[str, Any]] | None = None,
    requests: list[dict[str, Any]] | None = None,
) -> DayOffRequestService:
    service = DayOffRequestService()
    service._agents_repo = FakeAgentsRepository(agents or [_agent("agent-1", "user-1", "agent@example.com")])
    service._repo = FakeDayOffRequestsRepository(requests)
    return service


def _agent(agent_id: str, user_id: str, email: str) -> dict[str, Any]:
    return {
        "id": agent_id,
        "user_id": user_id,
        "email": email,
        "full_name": f"Agent {agent_id}",
        "office_id": "office-1",
    }


def _request(request_id: str, agent_id: str, status: str = "pending") -> dict[str, Any]:
    return {
        "id": request_id,
        "agent_id": agent_id,
        "user_id": f"user-for-{agent_id}",
        "email": f"{agent_id}@example.com",
        "full_name": f"Agent {agent_id}",
        "office_id": "office-1",
        "start_date": "2026-08-01",
        "end_date": "2026-08-02",
        "reason": "Family event",
        "status": status,
        "requested_at": "2026-07-09T10:00:00+00:00",
    }


def _current_user(user_id: str = "user-1", role: str = "agent") -> dict[str, Any]:
    return {
        "id": user_id,
        "email": f"{user_id}@example.com",
        "full_name": f"User {user_id}",
        "role": role,
        "is_active": True,
    }


def test_agent_lists_only_own_day_off_requests() -> None:
    service = _service(
        agents=[_agent("agent-1", "user-1", "agent@example.com"), _agent("agent-2", "user-2", "other@example.com")],
        requests=[_request("own", "agent-1"), _request("other", "agent-2")],
    )

    rows = service.list_for_agent(_current_user("user-1"))

    assert [row["id"] for row in rows] == ["own"]


def test_agent_create_uses_current_agent_profile() -> None:
    service = _service()

    created = service.create_for_agent(
        {"id": "user-1", "email": "agent@example.com", "full_name": "Agent One", "role": "agent"},
        DayOffRequestCreate(start_date="2026-08-01", end_date="2026-08-03", reason="Vacation"),
    )

    assert created["agent_id"] == "agent-1"
    assert created["status"] == "pending"
    assert created["reason"] == "Vacation"
    assert created["schedule_impact"].startswith("Approval records")


def test_create_without_agent_profile_raises_404() -> None:
    service = _service(agents=[])

    with pytest.raises(HTTPException) as exc_info:
        service.create_for_agent(_current_user("missing"), DayOffRequestCreate(start_date="2026-08-01", end_date="2026-08-01"))

    assert exc_info.value.status_code == 404


def test_admin_can_review_any_pending_request() -> None:
    service = _service(requests=[_request("req-1", "agent-2")])

    reviewed = service.review(
        "req-1",
        DayOffRequestReview(status=DayOffRequestStatus.APPROVED, review_note="Approved"),
        _current_user("admin-1", "admin"),
    )

    assert reviewed["status"] == "approved"
    assert reviewed["review_note"] == "Approved"
    assert reviewed["reviewed_by_user_id"] == "admin-1"


def test_review_rejects_non_pending_request() -> None:
    service = _service(requests=[_request("req-1", "agent-2", status="approved")])

    with pytest.raises(HTTPException) as exc_info:
        service.review("req-1", DayOffRequestReview(status=DayOffRequestStatus.REJECTED), _current_user("admin-1", "admin"))

    assert exc_info.value.status_code == 400


ADMIN_USER = {"id": "admin-1", "email": "admin@example.com", "full_name": "Admin", "role": "admin", "is_active": True}
AGENT_USER = {"id": "agent-user-1", "email": "agent@example.com", "full_name": "Agent", "role": "agent", "is_active": True}

client = TestClient(app)


@pytest.fixture(autouse=True)
def _clear_overrides():
    yield
    app.dependency_overrides.clear()


def _login_as(user: dict[str, Any]) -> None:
    app.dependency_overrides[get_current_user] = lambda: user


def test_day_off_routes_require_token() -> None:
    assert client.get("/api/v1/me/day-off-requests").status_code == 401
    assert client.post("/api/v1/me/day-off-requests", json={"start_date": "2026-08-01", "end_date": "2026-08-01"}).status_code == 401
    assert client.get("/api/v1/day-off-requests").status_code == 401
    assert client.put("/api/v1/day-off-requests/req-1/review", json={"status": "approved"}).status_code == 401


def test_admin_review_routes_reject_non_admin() -> None:
    _login_as(AGENT_USER)

    assert client.get("/api/v1/day-off-requests").status_code == 403
    assert client.put("/api/v1/day-off-requests/req-1/review", json={"status": "approved"}).status_code == 403


def test_agent_can_create_and_list_own_requests_via_route(monkeypatch: pytest.MonkeyPatch) -> None:
    service = _service(agents=[_agent("agent-1", "agent-user-1", "agent@example.com")])
    monkeypatch.setattr(day_off_requests_router, "service", service)
    _login_as(AGENT_USER)

    created = client.post("/api/v1/me/day-off-requests", json={"start_date": "2026-08-01", "end_date": "2026-08-01", "reason": "Doctor"})
    assert created.status_code == 200
    assert created.json()["agent_id"] == "agent-1"

    listed = client.get("/api/v1/me/day-off-requests")
    assert listed.status_code == 200
    assert [row["id"] for row in listed.json()] == ["day-off-new"]


def test_admin_can_list_and_review_requests_via_route(monkeypatch: pytest.MonkeyPatch) -> None:
    service = _service(requests=[_request("req-1", "agent-1")])
    monkeypatch.setattr(day_off_requests_router, "service", service)
    _login_as(ADMIN_USER)

    listed = client.get("/api/v1/day-off-requests")
    assert listed.status_code == 200
    assert listed.json()[0]["id"] == "req-1"

    reviewed = client.put("/api/v1/day-off-requests/req-1/review", json={"status": "rejected", "review_note": "Coverage gap"})
    assert reviewed.status_code == 200
    assert reviewed.json()["status"] == "rejected"
    assert reviewed.json()["review_note"] == "Coverage gap"
