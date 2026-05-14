"""Agent routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import require_admin
from app.models.agent import AgentCreate, AgentRead, AgentUpdate
from app.services.catalog_service import AgentService

router = APIRouter(prefix="/agents", tags=["agents"])
service = AgentService()


@router.get("", response_model=list[AgentRead])
def list_agents(_: dict = Depends(require_admin)) -> list[dict]:
    return service.list()


@router.post("", response_model=AgentRead)
def create_agent(payload: AgentCreate, _: dict = Depends(require_admin)) -> dict:
    return service.create(payload)


@router.put("/{agent_id}", response_model=AgentRead)
def update_agent(agent_id: str, payload: AgentUpdate, _: dict = Depends(require_admin)) -> dict:
    return service.update(agent_id, payload)


@router.delete("/{agent_id}")
def delete_agent(agent_id: str, _: dict = Depends(require_admin)) -> dict[str, str]:
    return service.delete(agent_id)
