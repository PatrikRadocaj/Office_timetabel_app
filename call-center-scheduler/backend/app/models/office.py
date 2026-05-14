"""Office schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class OfficeBase(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    timezone: str = Field(default="UTC", min_length=2, max_length=60)
    max_capacity: int = Field(ge=1, le=100000)
    address: str | None = Field(default=None, max_length=200)


class OfficeCreate(OfficeBase):
    pass


class OfficeUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    timezone: str | None = Field(default=None, min_length=2, max_length=60)
    max_capacity: int | None = Field(default=None, ge=1, le=100000)
    address: str | None = Field(default=None, max_length=200)


class OfficeRead(OfficeBase):
    id: str
    created_at: datetime | str
    updated_at: datetime | str
