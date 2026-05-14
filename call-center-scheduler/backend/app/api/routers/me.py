"""Agent-facing personal endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.models.me import AgentDashboardRead
from app.services.me_service import MeService

router = APIRouter(prefix="/me", tags=["me"])
service = MeService()


@router.get("/dashboard", response_model=AgentDashboardRead)
def my_dashboard(current_user: dict = Depends(get_current_user)) -> dict:
    return service.dashboard(current_user=current_user)

