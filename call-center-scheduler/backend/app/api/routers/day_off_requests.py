"""Day-off request routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_current_user, require_admin
from app.models.day_off_request import DayOffRequestCreate, DayOffRequestRead, DayOffRequestReview
from app.services.day_off_request_service import DayOffRequestService

admin_router = APIRouter(prefix="/day-off-requests", tags=["day_off_requests"])
me_router = APIRouter(prefix="/me/day-off-requests", tags=["me"])
service = DayOffRequestService()


@me_router.get("", response_model=list[DayOffRequestRead])
def list_my_day_off_requests(current_user: dict = Depends(get_current_user)) -> list[dict]:
    return service.list_for_agent(current_user)


@me_router.post("", response_model=DayOffRequestRead)
def create_my_day_off_request(
    payload: DayOffRequestCreate,
    current_user: dict = Depends(get_current_user),
) -> dict:
    return service.create_for_agent(current_user, payload)


@admin_router.get("", response_model=list[DayOffRequestRead])
def list_day_off_requests(_: dict = Depends(require_admin)) -> list[dict]:
    return service.list_for_admin()


@admin_router.put("/{request_id}/review", response_model=DayOffRequestRead)
def review_day_off_request(
    request_id: str,
    payload: DayOffRequestReview,
    current_user: dict = Depends(require_admin),
) -> dict:
    return service.review(request_id, payload, current_user)
