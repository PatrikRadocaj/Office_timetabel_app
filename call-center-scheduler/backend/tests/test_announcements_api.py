"""Announcement CRUD service and route authorization tests."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

import app.api.routers.announcements as announcements_router
from app.api.deps import get_current_user
from app.models.announcement import AnnouncementCreate, AnnouncementUpdate
from app.services.announcement_service import AnnouncementService
from app.services.me_service import MeService

# A minimal app with only the announcements router keeps these tests free of
# Firestore credentials (importing app.main constructs every router's repos).
app = FastAPI()
app.include_router(announcements_router.router, prefix="/api/v1")


class FakeAnnouncementsRepository:
    def __init__(self, rows: list[dict[str, Any]] | None = None) -> None:
        self.rows = rows or []
        self.created_data: dict[str, Any] | None = None
        self.updated_id: str | None = None
        self.updated_data: dict[str, Any] | None = None
        self.deleted_id: str | None = None
        self.exists = True

    def list(self, filters=None, order_by=None, limit=None) -> list[dict[str, Any]]:
        return [dict(row) for row in self.rows]

    def create(self, data: dict[str, Any], document_id: str | None = None) -> dict[str, Any]:
        self.created_data = {**data}
        return {"id": "ann-1", **data}

    def update(self, document_id: str, data: dict[str, Any]) -> dict[str, Any] | None:
        if not self.exists:
            return None
        self.updated_id = document_id
        self.updated_data = {**data}
        base = next((row for row in self.rows if row["id"] == document_id), {"id": document_id})
        return {**base, **data}

    def delete(self, document_id: str) -> bool:
        if not self.exists:
            return False
        self.deleted_id = document_id
        return True


def _service(repo: FakeAnnouncementsRepository) -> AnnouncementService:
    service = AnnouncementService()
    service._repo = repo
    return service


# --- Service behavior -------------------------------------------------------


def test_create_sets_published_at_and_keeps_active_flag() -> None:
    repo = FakeAnnouncementsRepository()
    created = _service(repo).create(AnnouncementCreate(title="Maintenance", message="Window tonight", is_active=False))

    assert repo.created_data is not None
    assert repo.created_data["title"] == "Maintenance"
    assert repo.created_data["is_active"] is False
    assert repo.created_data["published_at"] is not None
    assert created["id"] == "ann-1"


def test_update_sends_only_provided_fields() -> None:
    repo = FakeAnnouncementsRepository(rows=[{"id": "ann-1", "title": "Old", "message": "Old message", "is_active": True}])
    updated = _service(repo).update("ann-1", AnnouncementUpdate(is_active=False))

    assert repo.updated_data == {"is_active": False}
    assert updated["is_active"] is False
    assert updated["title"] == "Old"


def test_update_missing_announcement_raises_404() -> None:
    repo = FakeAnnouncementsRepository()
    repo.exists = False

    with pytest.raises(HTTPException) as exc_info:
        _service(repo).update("missing", AnnouncementUpdate(title="New title"))
    assert exc_info.value.status_code == 404


def test_delete_missing_announcement_raises_404() -> None:
    repo = FakeAnnouncementsRepository()
    repo.exists = False

    with pytest.raises(HTTPException) as exc_info:
        _service(repo).delete("missing")
    assert exc_info.value.status_code == 404


def test_list_returns_newest_first_and_normalizes_legacy_rows() -> None:
    repo = FakeAnnouncementsRepository(
        rows=[
            {"id": "old", "body": "Legacy body only", "created_at": "2026-07-01T00:00:00+00:00"},
            {"id": "new", "title": "Fresh", "message": "Current shape", "created_at": "2026-07-08T00:00:00+00:00"},
        ]
    )
    rows = _service(repo).list()

    assert [row["id"] for row in rows] == ["new", "old"]
    assert rows[1]["title"] == "Notice"
    assert rows[1]["message"] == "Legacy body only"


def test_dashboard_load_announcements_skips_inactive() -> None:
    me = object.__new__(MeService)
    me.announcements_repo = FakeAnnouncementsRepository(
        rows=[
            {"id": "a1", "title": "Visible", "message": "Active entry", "is_active": True},
            {"id": "a2", "title": "Hidden", "message": "Deactivated entry", "is_active": False},
        ]
    )

    announcements = me._load_announcements()

    assert [item["id"] for item in announcements] == ["a1"]


# --- Route authorization ----------------------------------------------------


ADMIN_USER = {"id": "admin-1", "email": "admin@example.com", "full_name": "Admin", "role": "admin", "is_active": True}
AGENT_USER = {"id": "agent-1", "email": "agent@example.com", "full_name": "Agent", "role": "agent", "is_active": True}

client = TestClient(app)


@pytest.fixture(autouse=True)
def _clear_overrides():
    yield
    app.dependency_overrides.clear()


def _login_as(user: dict[str, Any]) -> None:
    app.dependency_overrides[get_current_user] = lambda: user


def test_announcement_routes_require_token() -> None:
    assert client.get("/api/v1/announcements").status_code == 401
    assert client.post("/api/v1/announcements", json={"title": "Hi", "message": "There"}).status_code == 401
    assert client.put("/api/v1/announcements/x", json={"title": "Hi"}).status_code == 401
    assert client.delete("/api/v1/announcements/x").status_code == 401


def test_announcement_routes_reject_non_admin() -> None:
    _login_as(AGENT_USER)
    assert client.get("/api/v1/announcements").status_code == 403
    assert client.post("/api/v1/announcements", json={"title": "Hi", "message": "There"}).status_code == 403
    assert client.put("/api/v1/announcements/x", json={"title": "Hi"}).status_code == 403
    assert client.delete("/api/v1/announcements/x").status_code == 403


def test_admin_can_run_full_announcement_crud(monkeypatch: pytest.MonkeyPatch) -> None:
    repo = FakeAnnouncementsRepository(rows=[{"id": "ann-1", "title": "Fresh", "message": "Current", "is_active": True}])
    monkeypatch.setattr(announcements_router, "service", _service(repo))
    _login_as(ADMIN_USER)

    listed = client.get("/api/v1/announcements")
    assert listed.status_code == 200
    assert listed.json()[0]["id"] == "ann-1"

    created = client.post("/api/v1/announcements", json={"title": "New notice", "message": "Hello agents"})
    assert created.status_code == 200
    assert created.json()["is_active"] is True

    updated = client.put("/api/v1/announcements/ann-1", json={"is_active": False})
    assert updated.status_code == 200
    assert updated.json()["is_active"] is False

    deleted = client.delete("/api/v1/announcements/ann-1")
    assert deleted.status_code == 200
    assert repo.deleted_id == "ann-1"


def test_create_announcement_validates_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    repo = FakeAnnouncementsRepository()
    monkeypatch.setattr(announcements_router, "service", _service(repo))
    _login_as(ADMIN_USER)

    assert client.post("/api/v1/announcements", json={"title": "X", "message": "Too-short title"}).status_code == 422
    assert client.post("/api/v1/announcements", json={"title": "Valid title", "message": ""}).status_code == 422
    assert repo.created_data is None
