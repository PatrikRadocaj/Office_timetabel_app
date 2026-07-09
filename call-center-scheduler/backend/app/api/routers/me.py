"""Agent-facing personal endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.models.me import AgentAvailabilityRead, AgentAvailabilityUpdate, AgentDashboardRead, AgentShiftListRead
from app.services.me_service import MeService

router = APIRouter(prefix="/me", tags=["me"])
service = MeService()


@router.get("/dashboard", response_model=AgentDashboardRead)
def my_dashboard(current_user: dict = Depends(get_current_user)) -> dict:
    return service.dashboard(current_user=current_user)


@router.get("/shifts", response_model=AgentShiftListRead)
def my_shifts(current_user: dict = Depends(get_current_user)) -> dict:
    return service.shifts(current_user=current_user)


@router.get("/availability", response_model=AgentAvailabilityRead)
def my_availability(current_user: dict = Depends(get_current_user)) -> dict:
    return service.availability(current_user=current_user)


@router.put("/availability", response_model=AgentAvailabilityRead)
def update_my_availability(payload: AgentAvailabilityUpdate, current_user: dict = Depends(get_current_user)) -> dict:
    return service.update_availability(current_user=current_user, availability=payload.availability)
