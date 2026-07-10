"""Shift-swap request workflow service."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone, tzinfo
from typing import Any

from fastapi import HTTPException, status

from app.core.timezones import resolve_office_timezone
from app.models.shift_swap_request import (
    SCHEDULE_IMPACT_POLICY,
    ShiftSwapAssignmentRef,
    ShiftSwapRequestCreate,
    ShiftSwapRequestReview,
    ShiftSwapRequestStatus,
)
from app.repositories.agents_repository import AgentsRepository
from app.repositories.offices_repository import OfficesRepository
from app.repositories.schedules_repository import SchedulesRepository
from app.repositories.shift_swap_requests_repository import ShiftSwapRequestsRepository
from app.repositories.skills_repository import SkillsRepository
from app.services.scheduler_service import SchedulerService


@dataclass(frozen=True)
class AssignmentRef:
    schedule: dict[str, Any]
    assignment: dict[str, Any]

    @property
    def schedule_id(self) -> str:
        return str(self.schedule["id"])

    @property
    def assignment_key(self) -> str:
        return assignment_key(self.assignment)


def _as_utc(value: datetime | str) -> datetime:
    if isinstance(value, str):
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    else:
        dt = value
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def assignment_key(assignment: dict[str, Any]) -> str:
    return "|".join(
        [
            _as_utc(assignment["slot_start"]).isoformat(),
            _as_utc(assignment["slot_end"]).isoformat(),
            str(assignment.get("office_id")),
            str(assignment.get("skill_id")),
        ]
    )


class ShiftSwapRequestService:
    def __init__(self):
        # Lazy repositories keep route tests free of Firebase credentials.
        self._repo: ShiftSwapRequestsRepository | None = None
        self._agents_repo: AgentsRepository | None = None
        self._offices_repo: OfficesRepository | None = None
        self._skills_repo: SkillsRepository | None = None
        self._schedules_repo: SchedulesRepository | None = None

    @property
    def repo(self) -> ShiftSwapRequestsRepository:
        if self._repo is None:
            self._repo = ShiftSwapRequestsRepository()
        return self._repo

    @property
    def agents_repo(self) -> AgentsRepository:
        if self._agents_repo is None:
            self._agents_repo = AgentsRepository()
        return self._agents_repo

    @property
    def offices_repo(self) -> OfficesRepository:
        if self._offices_repo is None:
            self._offices_repo = OfficesRepository()
        return self._offices_repo

    @property
    def skills_repo(self) -> SkillsRepository:
        if self._skills_repo is None:
            self._skills_repo = SkillsRepository()
        return self._skills_repo

    @property
    def schedules_repo(self) -> SchedulesRepository:
        if self._schedules_repo is None:
            self._schedules_repo = SchedulesRepository()
        return self._schedules_repo

    def options_for_agent(self, current_user: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
        requester = self._require_agent_profile(current_user)
        agents = self._active_agents_by_id()
        offices = {office["id"]: office for office in self.offices_repo.list()}
        skills = {skill["id"]: skill for skill in self.skills_repo.list()}
        refs = self._authoritative_assignment_refs()
        blocks = self._build_shift_blocks(refs, agents, offices)

        my_shifts = [
            self._option_for_block(block, offices, skills)
            for block in blocks
            if block["agent_id"] == requester["id"]
        ]
        target_shifts = [
            self._option_for_block(block, offices, skills)
            for block in blocks
            if block["agent_id"] != requester["id"] and str(block["office_id"]) == str(requester.get("office_id"))
        ]

        return {"my_shifts": my_shifts, "target_shifts": target_shifts}

    def list_for_agent(self, current_user: dict[str, Any]) -> list[dict[str, Any]]:
        requester = self._require_agent_profile(current_user)
        rows = self.repo.list(filters=[("requester_agent_id", "==", requester["id"])])
        return self._sort_newest_first(rows)

    def create_for_agent(self, current_user: dict[str, Any], payload: ShiftSwapRequestCreate) -> dict[str, Any]:
        requester = self._require_agent_profile(current_user)
        refs = self._authoritative_assignment_refs()
        agents = self._active_agents_by_id()
        offices = {office["id"]: office for office in self.offices_repo.list()}
        skills = {skill["id"]: skill for skill in self.skills_repo.list()}
        office_timezones = {office_id: resolve_office_timezone(office) for office_id, office in offices.items()}

        source_payload_refs = self._payload_assignment_refs(payload, "source")
        target_payload_refs = self._payload_assignment_refs(payload, "target")
        source_refs = self._find_refs(refs, source_payload_refs)
        target_refs = self._find_refs(refs, target_payload_refs)
        target_agent = agents.get(payload.target_agent_id)
        if not target_agent:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Target agent is not active or does not exist")

        self._validate_swap_blocks(
            refs=refs,
            requester=requester,
            target_agent=target_agent,
            source_refs=source_refs,
            target_refs=target_refs,
            skills=skills,
            office_timezones=office_timezones,
        )
        self._ensure_no_duplicate_pending_request(requester["id"], payload)

        now = datetime.now(timezone.utc)
        data = {
            "requester_agent_id": requester["id"],
            "requester_user_id": requester.get("user_id") or current_user.get("id"),
            "requester_name": requester.get("full_name") or current_user.get("full_name") or "Agent",
            "requester_email": requester.get("email") or current_user.get("email"),
            "target_agent_id": target_agent["id"],
            "target_agent_name": target_agent.get("full_name") or target_agent["id"],
            "target_agent_email": target_agent.get("email"),
            "source_schedule_id": source_refs[0].schedule_id,
            "source_assignment_key": source_refs[0].assignment_key,
            "target_schedule_id": target_refs[0].schedule_id,
            "target_assignment_key": target_refs[0].assignment_key,
            "source_assignment_refs": [self._ref_payload(ref) for ref in source_refs],
            "target_assignment_refs": [self._ref_payload(ref) for ref in target_refs],
            "source_shift": self._shift_snapshot(source_refs, requester, offices, skills),
            "target_shift": self._shift_snapshot(target_refs, target_agent, offices, skills),
            "reason": payload.reason.strip() if payload.reason else None,
            "status": ShiftSwapRequestStatus.PENDING.value,
            "requested_at": now,
            "reviewed_at": None,
            "reviewed_by_user_id": None,
            "reviewed_by_name": None,
            "review_note": None,
            "schedule_impact": SCHEDULE_IMPACT_POLICY,
            "schedule_update": None,
        }
        return self._normalize(self.repo.create(data))

    def list_for_admin(self) -> list[dict[str, Any]]:
        return self._sort_newest_first(self.repo.list())

    def review(self, request_id: str, payload: ShiftSwapRequestReview, current_user: dict[str, Any]) -> dict[str, Any]:
        existing = self.repo.get(request_id)
        if not existing:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shift-swap request not found")
        if existing.get("status") != ShiftSwapRequestStatus.PENDING.value:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only pending shift-swap requests can be reviewed")

        update_data: dict[str, Any] = {
            "status": payload.status.value,
            "review_note": payload.review_note.strip() if payload.review_note else None,
            "reviewed_at": datetime.now(timezone.utc),
            "reviewed_by_user_id": current_user.get("id"),
            "reviewed_by_name": current_user.get("full_name") or current_user.get("email") or "Admin",
            "schedule_impact": SCHEDULE_IMPACT_POLICY,
        }

        if payload.status == ShiftSwapRequestStatus.APPROVED:
            update_data["schedule_update"] = self._apply_approved_swap(existing)

        updated = self.repo.update(request_id, update_data)
        if not updated:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shift-swap request not found")
        return self._normalize(updated)

    def _apply_approved_swap(self, request: dict[str, Any]) -> dict[str, Any]:
        refs = self._authoritative_assignment_refs()
        agents = self._active_agents_by_id()
        offices = {office["id"]: office for office in self.offices_repo.list()}
        skills = {skill["id"]: skill for skill in self.skills_repo.list()}
        office_timezones = {office_id: resolve_office_timezone(office) for office_id, office in offices.items()}

        requester = agents.get(str(request.get("requester_agent_id")))
        target_agent = agents.get(str(request.get("target_agent_id")))
        if not requester or not target_agent:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Requester or target agent is no longer active")

        source_refs = self._find_refs(refs, self._request_assignment_refs(request, "source"))
        target_refs = self._find_refs(refs, self._request_assignment_refs(request, "target"))
        self._validate_swap_blocks(
            refs=refs,
            requester=requester,
            target_agent=target_agent,
            source_refs=source_refs,
            target_refs=target_refs,
            skills=skills,
            office_timezones=office_timezones,
        )

        source_keys = {(ref.schedule_id, ref.assignment_key) for ref in source_refs}
        target_keys = {(ref.schedule_id, ref.assignment_key) for ref in target_refs}
        schedules_by_id = {ref.schedule_id: ref.schedule for ref in [*source_refs, *target_refs]}
        updated_schedule_ids: list[str] = []

        for schedule_id, schedule in schedules_by_id.items():
            assignments = []
            for assignment in schedule.get("assignments", []):
                key = (schedule_id, assignment_key(assignment))
                if key in source_keys:
                    assignments.append(self._copy_assignment_with_swapped_agent(assignment, requester["id"], target_agent["id"]))
                elif key in target_keys:
                    assignments.append(self._copy_assignment_with_swapped_agent(assignment, target_agent["id"], requester["id"]))
                else:
                    assignments.append(assignment)
            self.schedules_repo.update(schedule_id, {"assignments": assignments})
            updated_schedule_ids.append(schedule_id)

        return {
            "applied": True,
            "updated_schedule_ids": sorted(updated_schedule_ids),
            "requester_agent_id": requester["id"],
            "target_agent_id": target_agent["id"],
            "source_assignment_count": len(source_refs),
            "target_assignment_count": len(target_refs),
        }

    def _validate_swap_blocks(
        self,
        refs: list[AssignmentRef],
        requester: dict[str, Any],
        target_agent: dict[str, Any],
        source_refs: list[AssignmentRef],
        target_refs: list[AssignmentRef],
        skills: dict[str, dict[str, Any]],
        office_timezones: dict[str, tzinfo],
    ) -> None:
        if requester["id"] == target_agent["id"]:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Target agent must be different")

        if not source_refs or not target_refs:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Shift blocks must include assignments")

        for ref in source_refs:
            assigned_ids = [str(agent_id) for agent_id in ref.assignment.get("assigned_agent_ids", [])]
            if requester["id"] not in assigned_ids:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Source shift is not assigned to the current agent")

        for ref in target_refs:
            assigned_ids = [str(agent_id) for agent_id in ref.assignment.get("assigned_agent_ids", [])]
            if target_agent["id"] not in assigned_ids:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Target shift is not assigned to the selected target agent")

        shift_office_ids = {str(ref.assignment.get("office_id")) for ref in [*source_refs, *target_refs]}
        if len(shift_office_ids) != 1:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Shift swaps must stay within the same office")

        shift_office_id = next(iter(shift_office_ids))
        if str(requester.get("office_id")) != shift_office_id or str(target_agent.get("office_id")) != shift_office_id:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Shift swaps require both agents to belong to the shift office")

        requester_tz = office_timezones.get(requester.get("office_id"), timezone.utc)
        target_tz = office_timezones.get(target_agent.get("office_id"), timezone.utc)

        source_exceptions = {(ref.schedule_id, ref.assignment_key) for ref in source_refs}
        target_exceptions = {(ref.schedule_id, ref.assignment_key) for ref in target_refs}

        for source_ref in source_refs:
            source_skill_id = str(source_ref.assignment.get("skill_id"))
            source_start = _as_utc(source_ref.assignment["slot_start"])
            source_end = _as_utc(source_ref.assignment["slot_end"])
            if not self._agent_has_skill(target_agent, source_skill_id, skills):
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Target agent does not have the source shift skill")
            if not SchedulerService._agent_is_available(target_agent, source_start, source_end, target_tz):
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Target agent is not available for the source shift")
            if self._has_overlapping_assignment(
                refs=refs,
                agent_id=target_agent["id"],
                slot_start=source_start,
                slot_end=source_end,
                except_keys=target_exceptions,
            ):
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Target agent already has an overlapping assignment")

        for target_ref in target_refs:
            target_skill_id = str(target_ref.assignment.get("skill_id"))
            target_start = _as_utc(target_ref.assignment["slot_start"])
            target_end = _as_utc(target_ref.assignment["slot_end"])
            if not self._agent_has_skill(requester, target_skill_id, skills):
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Requester does not have the target shift skill")
            if not SchedulerService._agent_is_available(requester, target_start, target_end, requester_tz):
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Requester is not available for the target shift")
            if self._has_overlapping_assignment(
                refs=refs,
                agent_id=requester["id"],
                slot_start=target_start,
                slot_end=target_end,
                except_keys=source_exceptions,
            ):
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Requester already has an overlapping assignment")

        for source_ref in source_refs:
            source_start = _as_utc(source_ref.assignment["slot_start"])
            source_end = _as_utc(source_ref.assignment["slot_end"])
            for target_ref in target_refs:
                target_start = _as_utc(target_ref.assignment["slot_start"])
                target_end = _as_utc(target_ref.assignment["slot_end"])
                if self._overlaps(source_start, source_end, target_start, target_end):
                    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Source and target shifts overlap")

    def _find_ref(self, refs: list[AssignmentRef], schedule_id: str, key: str) -> AssignmentRef:
        for ref in refs:
            if ref.schedule_id == schedule_id and ref.assignment_key == key:
                return ref
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shift assignment not found in active schedules")

    def _find_refs(self, refs: list[AssignmentRef], requested_refs: list[ShiftSwapAssignmentRef]) -> list[AssignmentRef]:
        return [self._find_ref(refs, ref.schedule_id, ref.assignment_key) for ref in requested_refs]

    def _authoritative_assignment_refs(self) -> list[AssignmentRef]:
        schedules = self.schedules_repo.list_active(order_by="generated_at")
        seen_slot_keys: set[tuple[str, str, str, str]] = set()
        refs: list[AssignmentRef] = []

        for schedule in reversed(schedules):
            for assignment in schedule.get("assignments", []):
                key = (
                    _as_utc(assignment["slot_start"]).isoformat(),
                    _as_utc(assignment["slot_end"]).isoformat(),
                    str(assignment.get("office_id")),
                    str(assignment.get("skill_id")),
                )
                if key in seen_slot_keys:
                    continue
                seen_slot_keys.add(key)
                refs.append(AssignmentRef(schedule=schedule, assignment=assignment))

        refs.sort(key=lambda ref: _as_utc(ref.assignment["slot_start"]))
        return refs

    def _ensure_no_duplicate_pending_request(self, requester_agent_id: str, payload: ShiftSwapRequestCreate) -> None:
        source_refs = [ref.model_dump() for ref in self._payload_assignment_refs(payload, "source")]
        target_refs = [ref.model_dump() for ref in self._payload_assignment_refs(payload, "target")]
        rows = self.repo.list(filters=[("requester_agent_id", "==", requester_agent_id)])
        for row in rows:
            if row.get("status") != ShiftSwapRequestStatus.PENDING.value:
                continue
            row_source_refs = [ref.model_dump() for ref in self._request_assignment_refs(row, "source")]
            row_target_refs = [ref.model_dump() for ref in self._request_assignment_refs(row, "target")]
            if row_source_refs == source_refs and row_target_refs == target_refs and row.get("target_agent_id") == payload.target_agent_id:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Matching shift-swap request is already pending")

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

    def _active_agents_by_id(self) -> dict[str, dict[str, Any]]:
        return {agent["id"]: agent for agent in self.agents_repo.list() if agent.get("is_active", True)}

    @staticmethod
    def _agent_has_skill(agent: dict[str, Any], skill_id: str, skills: dict[str, dict[str, Any]]) -> bool:
        min_proficiency = int(skills.get(skill_id, {}).get("min_proficiency", 1))
        for entry in agent.get("skills", []):
            if entry.get("skill_id") == skill_id and int(entry.get("proficiency", 0)) >= min_proficiency:
                return True
        return False

    @staticmethod
    def _has_overlapping_assignment(
        refs: list[AssignmentRef],
        agent_id: str,
        slot_start: datetime,
        slot_end: datetime,
        except_keys: set[tuple[str, str]],
    ) -> bool:
        for ref in refs:
            if (ref.schedule_id, ref.assignment_key) in except_keys:
                continue
            assigned_ids = [str(entry) for entry in ref.assignment.get("assigned_agent_ids", [])]
            if agent_id not in assigned_ids:
                continue
            other_start = _as_utc(ref.assignment["slot_start"])
            other_end = _as_utc(ref.assignment["slot_end"])
            if ShiftSwapRequestService._overlaps(slot_start, slot_end, other_start, other_end):
                return True
        return False

    @staticmethod
    def _overlaps(first_start: datetime, first_end: datetime, second_start: datetime, second_end: datetime) -> bool:
        return first_start < second_end and second_start < first_end

    @staticmethod
    def _copy_assignment_with_swapped_agent(assignment: dict[str, Any], old_agent_id: str, new_agent_id: str) -> dict[str, Any]:
        assigned_ids = [str(agent_id) for agent_id in assignment.get("assigned_agent_ids", [])]
        if old_agent_id not in assigned_ids:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Schedule assignment changed before approval")
        if new_agent_id in assigned_ids:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Swap would create duplicate assignment")
        return {
            **assignment,
            "assigned_agent_ids": [new_agent_id if agent_id == old_agent_id else agent_id for agent_id in assigned_ids],
        }

    @staticmethod
    def _sort_newest_first(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return sorted(rows, key=lambda row: str(row.get("requested_at") or row.get("created_at") or ""), reverse=True)

    @staticmethod
    def _normalize(row: dict[str, Any]) -> dict[str, Any]:
        return {**row, "schedule_impact": row.get("schedule_impact") or SCHEDULE_IMPACT_POLICY}

    @staticmethod
    def _ref_payload(ref: AssignmentRef) -> dict[str, str]:
        return {"schedule_id": ref.schedule_id, "assignment_key": ref.assignment_key}

    @staticmethod
    def _payload_assignment_refs(payload: ShiftSwapRequestCreate, side: str) -> list[ShiftSwapAssignmentRef]:
        refs = payload.source_assignment_refs if side == "source" else payload.target_assignment_refs
        if refs:
            return refs
        schedule_id = payload.source_schedule_id if side == "source" else payload.target_schedule_id
        assignment_key_value = payload.source_assignment_key if side == "source" else payload.target_assignment_key
        return [ShiftSwapAssignmentRef(schedule_id=schedule_id, assignment_key=assignment_key_value)]

    @staticmethod
    def _request_assignment_refs(request: dict[str, Any], side: str) -> list[ShiftSwapAssignmentRef]:
        refs_key = f"{side}_assignment_refs"
        refs = request.get(refs_key)
        if refs:
            return [ShiftSwapAssignmentRef.model_validate(ref) for ref in refs]
        return [
            ShiftSwapAssignmentRef(
                schedule_id=str(request[f"{side}_schedule_id"]),
                assignment_key=str(request[f"{side}_assignment_key"]),
            )
        ]

    def _build_shift_blocks(
        self,
        refs: list[AssignmentRef],
        agents: dict[str, dict[str, Any]],
        offices: dict[str, dict[str, Any]],
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for ref in refs:
            office_id = str(ref.assignment.get("office_id"))
            office_tz = resolve_office_timezone(offices.get(office_id, {}))
            slot_start = _as_utc(ref.assignment["slot_start"])
            slot_end = _as_utc(ref.assignment["slot_end"])
            local_start = slot_start.astimezone(office_tz)
            for agent_id in [str(entry) for entry in ref.assignment.get("assigned_agent_ids", [])]:
                agent = agents.get(agent_id)
                if not agent:
                    continue
                rows.append(
                    {
                        "agent_id": agent_id,
                        "agent": agent,
                        "office_id": office_id,
                        "local_date": local_start.date().isoformat(),
                        "slot_start": slot_start,
                        "slot_end": slot_end,
                        "refs": [ref],
                    }
                )

        rows.sort(key=lambda row: (row["agent_id"], row["office_id"], row["local_date"], row["slot_start"], row["slot_end"]))
        blocks: list[dict[str, Any]] = []
        for row in rows:
            if (
                blocks
                and blocks[-1]["agent_id"] == row["agent_id"]
                and blocks[-1]["office_id"] == row["office_id"]
                and blocks[-1]["local_date"] == row["local_date"]
                and blocks[-1]["slot_end"] == row["slot_start"]
            ):
                blocks[-1]["slot_end"] = row["slot_end"]
                blocks[-1]["refs"].extend(row["refs"])
                continue
            blocks.append({**row, "refs": list(row["refs"])})

        blocks.sort(key=lambda row: (row["slot_start"], row["agent_id"], row["office_id"]))
        return blocks

    def _option_for_block(
        self,
        block: dict[str, Any],
        offices: dict[str, dict[str, Any]],
        skills: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        refs = block["refs"]
        first_ref = refs[0]
        skill_ids: list[str] = []
        for ref in refs:
            skill_id = str(ref.assignment.get("skill_id"))
            if skill_id not in skill_ids:
                skill_ids.append(skill_id)
        skill_names = [skills.get(skill_id, {}).get("name", skill_id) for skill_id in skill_ids]
        skill_name = skill_names[0] if len(skill_names) == 1 else f"Multiple skills: {', '.join(skill_names)}"
        office_id = str(block["office_id"])
        agent = block["agent"]
        return {
            "schedule_id": first_ref.schedule_id,
            "assignment_key": first_ref.assignment_key,
            "assignment_refs": [self._ref_payload(ref) for ref in refs],
            "agent_id": agent["id"],
            "agent_name": agent.get("full_name") or agent["id"],
            "slot_start": block["slot_start"],
            "slot_end": block["slot_end"],
            "office_id": office_id,
            "office_name": offices.get(office_id, {}).get("name", office_id),
            "office_timezone": offices.get(office_id, {}).get("timezone"),
            "skill_id": skill_ids[0] if len(skill_ids) == 1 else "multiple",
            "skill_name": skill_name,
            "skill_ids": skill_ids,
            "skill_names": skill_names,
        }

    def _option_for_ref(
        self,
        ref: AssignmentRef,
        agent: dict[str, Any],
        offices: dict[str, dict[str, Any]],
        skills: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        assignment = ref.assignment
        office_id = str(assignment.get("office_id"))
        skill_id = str(assignment.get("skill_id"))
        return {
            "schedule_id": ref.schedule_id,
            "assignment_key": ref.assignment_key,
            "agent_id": agent["id"],
            "agent_name": agent.get("full_name") or agent["id"],
            "slot_start": assignment["slot_start"],
            "slot_end": assignment["slot_end"],
            "office_id": office_id,
            "office_name": offices.get(office_id, {}).get("name", office_id),
            "office_timezone": offices.get(office_id, {}).get("timezone"),
            "skill_id": skill_id,
            "skill_name": skills.get(skill_id, {}).get("name", skill_id),
            "skill_ids": [skill_id],
            "skill_names": [skills.get(skill_id, {}).get("name", skill_id)],
            "assignment_refs": [self._ref_payload(ref)],
        }

    def _shift_snapshot(
        self,
        refs: list[AssignmentRef],
        agent: dict[str, Any],
        offices: dict[str, dict[str, Any]],
        skills: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        blocks = self._build_shift_blocks(refs, {agent["id"]: agent}, offices)
        if len(blocks) == 1:
            return self._option_for_block(blocks[0], offices, skills)
        return self._option_for_ref(refs[0], agent, offices, skills)
