"""Day-off request workflow service."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException, status

from app.models.day_off_request import (
    SCHEDULE_IMPACT_POLICY,
    DayOffRequestCreate,
    DayOffRequestReview,
    DayOffRequestStatus,
)
from app.repositories.agents_repository import AgentsRepository
from app.repositories.day_off_requests_repository import DayOffRequestsRepository


class DayOffRequestService:
    def __init__(self):
        # Lazy repositories keep route tests free of Firebase credentials.
        self._repo: DayOffRequestsRepository | None = None
        self._agents_repo: AgentsRepository | None = None

    @property
    def repo(self) -> DayOffRequestsRepository:
        if self._repo is None:
            self._repo = DayOffRequestsRepository()
        return self._repo

    @property
    def agents_repo(self) -> AgentsRepository:
        if self._agents_repo is None:
            self._agents_repo = AgentsRepository()
        return self._agents_repo

    def list_for_agent(self, current_user: dict[str, Any]) -> list[dict[str, Any]]:
        agent = self._require_agent_profile(current_user)
        rows = self.repo.list(filters=[("agent_id", "==", agent["id"])])
        return self._sort_newest_first(rows)

    def create_for_agent(self, current_user: dict[str, Any], payload: DayOffRequestCreate) -> dict[str, Any]:
        agent = self._require_agent_profile(current_user)
        now = datetime.now(timezone.utc)
        data = {
            "agent_id": agent["id"],
            "user_id": agent.get("user_id") or current_user.get("id"),
            "email": agent.get("email") or current_user.get("email"),
            "full_name": agent.get("full_name") or current_user.get("full_name") or current_user.get("email") or "Agent",
            "office_id": agent.get("office_id"),
            "start_date": payload.start_date.isoformat(),
            "end_date": payload.end_date.isoformat(),
            "reason": payload.reason.strip() if payload.reason else None,
            "status": DayOffRequestStatus.PENDING.value,
            "requested_at": now,
            "reviewed_at": None,
            "reviewed_by_user_id": None,
            "reviewed_by_name": None,
            "review_note": None,
            "schedule_impact": SCHEDULE_IMPACT_POLICY,
        }
        return self._normalize(self.repo.create(data))

    def list_for_admin(self) -> list[dict[str, Any]]:
        return self._sort_newest_first(self.repo.list())

    def review(self, request_id: str, payload: DayOffRequestReview, current_user: dict[str, Any]) -> dict[str, Any]:
        existing = self.repo.get(request_id)
        if not existing:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Day-off request not found")

        if existing.get("status") != DayOffRequestStatus.PENDING.value:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only pending day-off requests can be reviewed")

        updated = self.repo.update(
            request_id,
            {
                "status": payload.status.value,
                "review_note": payload.review_note.strip() if payload.review_note else None,
                "reviewed_at": datetime.now(timezone.utc),
                "reviewed_by_user_id": current_user.get("id"),
                "reviewed_by_name": current_user.get("full_name") or current_user.get("email") or "Admin",
                "schedule_impact": SCHEDULE_IMPACT_POLICY,
            },
        )
        if not updated:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Day-off request not found")
        return self._normalize(updated)

    def _require_agent_profile(self, current_user: dict[str, Any]) -> dict[str, Any]:
        agent = self._resolve_agent_profile(current_user)
        if not agent:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent profile not found")
        return agent

    def _resolve_agent_profile(self, current_user: dict[str, Any]) -> dict[str, Any] | None:
        uid = str(current_user.get("id", ""))
        if uid:
            by_user_id = self.agents_repo.list(filters=[("user_id", "==", uid)], limit=1)
            if by_user_id:
                return by_user_id[0]

        email = str(current_user.get("email", "")).strip().lower()
        if not email:
            return None

        by_email = self.agents_repo.list(filters=[("email", "==", email)], limit=1)
        if not by_email:
            return None

        agent = by_email[0]
        if uid and not agent.get("user_id"):
            updated = self.agents_repo.update(agent["id"], {"user_id": uid})
            if updated:
                return updated
        return agent

    @staticmethod
    def _sort_newest_first(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return sorted(rows, key=lambda row: str(row.get("requested_at") or row.get("created_at") or ""), reverse=True)

    @staticmethod
    def _normalize(row: dict[str, Any]) -> dict[str, Any]:
        return {**row, "schedule_impact": row.get("schedule_impact") or SCHEDULE_IMPACT_POLICY}
