"""Announcement routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import require_admin
from app.models.announcement import AnnouncementCreate, AnnouncementRead, AnnouncementUpdate
from app.services.announcement_service import AnnouncementService

router = APIRouter(prefix="/announcements", tags=["announcements"])
service = AnnouncementService()


@router.get("", response_model=list[AnnouncementRead])
def list_announcements(_: dict = Depends(require_admin)) -> list[dict]:
    # Admin-only: this listing includes inactive/draft announcements.
    # Agents read active announcements through /me/dashboard.
    return service.list()


@router.post("", response_model=AnnouncementRead)
def create_announcement(payload: AnnouncementCreate, _: dict = Depends(require_admin)) -> dict:
    return service.create(payload)


@router.put("/{announcement_id}", response_model=AnnouncementRead)
def update_announcement(announcement_id: str, payload: AnnouncementUpdate, _: dict = Depends(require_admin)) -> dict:
    return service.update(announcement_id, payload)


@router.delete("/{announcement_id}")
def delete_announcement(announcement_id: str, _: dict = Depends(require_admin)) -> dict[str, str]:
    return service.delete(announcement_id)
