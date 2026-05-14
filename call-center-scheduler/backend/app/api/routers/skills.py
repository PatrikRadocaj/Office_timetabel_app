"""Skill routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_current_user, require_admin
from app.models.skill import SkillCreate, SkillRead, SkillUpdate
from app.services.catalog_service import SkillService

router = APIRouter(prefix="/skills", tags=["skills"])
service = SkillService()


@router.get("", response_model=list[SkillRead])
def list_skills(_: dict = Depends(get_current_user)) -> list[dict]:
    return service.list()


@router.post("", response_model=SkillRead)
def create_skill(payload: SkillCreate, _: dict = Depends(require_admin)) -> dict:
    return service.create(payload)


@router.put("/{skill_id}", response_model=SkillRead)
def update_skill(skill_id: str, payload: SkillUpdate, _: dict = Depends(require_admin)) -> dict:
    return service.update(skill_id, payload)


@router.delete("/{skill_id}")
def delete_skill(skill_id: str, _: dict = Depends(require_admin)) -> dict[str, str]:
    return service.delete(skill_id)
