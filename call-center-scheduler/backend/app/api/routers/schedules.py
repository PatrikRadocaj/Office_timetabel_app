"""Schedule generation routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import require_admin
from app.models.schedule import ScheduleGenerationRequest, ScheduleGenerationResponse
from app.services.scheduler_service import SchedulerService

router = APIRouter(prefix="/schedules", tags=["schedules"])
service = SchedulerService()


@router.post("/generate", response_model=ScheduleGenerationResponse)
def generate_schedule(
    payload: ScheduleGenerationRequest,
    _: dict = Depends(require_admin),
) -> dict:
    return service.generate(payload)
