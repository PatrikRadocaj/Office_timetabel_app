"""Shift-swap request routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_current_user, require_admin
from app.models.shift_swap_request import (
    ShiftSwapOptionsResponse,
    ShiftSwapRequestCreate,
    ShiftSwapRequestRead,
    ShiftSwapRequestReview,
)
from app.services.shift_swap_request_service import ShiftSwapRequestService

admin_router = APIRouter(prefix="/shift-swap-requests", tags=["shift_swap_requests"])
me_router = APIRouter(prefix="/me/shift-swap-requests", tags=["me"])
options_router = APIRouter(prefix="/me/shift-swap-options", tags=["me"])
service = ShiftSwapRequestService()


@options_router.get("", response_model=ShiftSwapOptionsResponse)
def my_shift_swap_options(current_user: dict = Depends(get_current_user)) -> dict[str, list[dict]]:
    return service.options_for_agent(current_user)


@me_router.get("", response_model=list[ShiftSwapRequestRead])
def list_my_shift_swap_requests(current_user: dict = Depends(get_current_user)) -> list[dict]:
    return service.list_for_agent(current_user)


@me_router.post("", response_model=ShiftSwapRequestRead)
def create_my_shift_swap_request(
    payload: ShiftSwapRequestCreate,
    current_user: dict = Depends(get_current_user),
) -> dict:
    return service.create_for_agent(current_user, payload)


@admin_router.get("", response_model=list[ShiftSwapRequestRead])
def list_shift_swap_requests(_: dict = Depends(require_admin)) -> list[dict]:
    return service.list_for_admin()


@admin_router.put("/{request_id}/review", response_model=ShiftSwapRequestRead)
def review_shift_swap_request(
    request_id: str,
    payload: ShiftSwapRequestReview,
    current_user: dict = Depends(require_admin),
) -> dict:
    return service.review(request_id, payload, current_user)
