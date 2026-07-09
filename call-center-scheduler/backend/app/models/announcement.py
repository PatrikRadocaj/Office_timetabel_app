"""Announcement schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class AnnouncementCreate(BaseModel):
    title: str = Field(min_length=2, max_length=120)
    message: str = Field(min_length=1, max_length=2000)
    is_active: bool = True


class AnnouncementUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=120)
    message: str | None = Field(default=None, min_length=1, max_length=2000)
    is_active: bool | None = None


class AnnouncementRead(BaseModel):
    # Deliberately unconstrained so legacy Firestore documents (e.g. `body`
    # instead of `message`) still serialize after service-level normalization.
    id: str
    title: str
    message: str
    is_active: bool = True
    published_at: datetime | str | None = None
    created_at: datetime | str | None = None
    updated_at: datetime | str | None = None
