"""Announcement CRUD service for the admin panel."""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException, status

from app.models.announcement import AnnouncementCreate, AnnouncementUpdate
from app.models.common import utcnow
from app.repositories.announcements_repository import AnnouncementsRepository


class AnnouncementService:
    def __init__(self):
        # Lazy so the router module can be imported without Firestore
        # credentials (keeps route-level tests hermetic).
        self._repo: AnnouncementsRepository | None = None

    @property
    def repo(self) -> AnnouncementsRepository:
        if self._repo is None:
            self._repo = AnnouncementsRepository()
        return self._repo

    def list(self) -> list[dict[str, Any]]:
        rows = self.repo.list(order_by="created_at")
        rows.reverse()  # newest first, matching the agent dashboard ordering
        return [self._normalize(row) for row in rows]

    def create(self, payload: AnnouncementCreate) -> dict[str, Any]:
        data = payload.model_dump()
        data["published_at"] = utcnow()
        return self.repo.create(data)

    def update(self, announcement_id: str, payload: AnnouncementUpdate) -> dict[str, Any]:
        updated = self.repo.update(announcement_id, payload.model_dump(exclude_unset=True))
        if not updated:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Announcement not found")
        return self._normalize(updated)

    def delete(self, announcement_id: str) -> dict[str, str]:
        if not self.repo.delete(announcement_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Announcement not found")
        return {"message": "Announcement deleted"}

    @staticmethod
    def _normalize(row: dict[str, Any]) -> dict[str, Any]:
        # Legacy documents may carry `body` instead of `message` and lack a
        # title; mirror MeService's fallbacks so they stay manageable.
        title = str(row.get("title") or "").strip() or "Notice"
        message = str(row.get("message") or row.get("body") or "").strip()
        return {**row, "title": title, "message": message}
