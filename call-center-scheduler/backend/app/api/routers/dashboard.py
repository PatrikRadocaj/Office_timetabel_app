"""Dashboard routes."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.models.schedule import DashboardSummary
from app.services.dashboard_service import DashboardService

router = APIRouter(prefix="/dashboard", tags=["dashboard"])
service = DashboardService()


@router.get("/summary", response_model=DashboardSummary)
def summary(
    start_at: datetime | None = None,
    end_at: datetime | None = None,
    _: dict = Depends(get_current_user),
) -> dict:
    return service.summary(start_at=start_at, end_at=end_at)
