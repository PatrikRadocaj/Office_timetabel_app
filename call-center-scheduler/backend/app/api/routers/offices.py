"""Office routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_current_user, require_admin
from app.models.office import OfficeCreate, OfficeRead, OfficeUpdate
from app.services.catalog_service import OfficeService

router = APIRouter(prefix="/offices", tags=["offices"])
service = OfficeService()


@router.get("", response_model=list[OfficeRead])
def list_offices(_: dict = Depends(get_current_user)) -> list[dict]:
    return service.list()


@router.post("", response_model=OfficeRead)
def create_office(payload: OfficeCreate, _: dict = Depends(require_admin)) -> dict:
    return service.create(payload)


@router.put("/{office_id}", response_model=OfficeRead)
def update_office(office_id: str, payload: OfficeUpdate, _: dict = Depends(require_admin)) -> dict:
    return service.update(office_id, payload)


@router.delete("/{office_id}")
def delete_office(office_id: str, _: dict = Depends(require_admin)) -> dict[str, str]:
    return service.delete(office_id)
