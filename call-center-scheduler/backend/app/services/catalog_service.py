"""CRUD and ingestion services for offices, skills, agents, and demand."""

from __future__ import annotations

import csv
import io
import logging
from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import HTTPException, UploadFile, status

from app.core.config import get_settings
from app.core.timezones import resolve_office_timezone
from app.models.agent import AgentCreate, AgentUpdate
from app.models.demand import (
    DailyDemandForecastCreate,
    DemandForecastBulkCreate,
    DemandForecastCreate,
)
from app.models.office import OfficeCreate, OfficeUpdate
from app.models.skill import SkillCreate, SkillUpdate
from app.repositories.agents_repository import AgentsRepository
from app.repositories.demand_repository import DemandForecastsRepository
from app.repositories.offices_repository import OfficesRepository
from app.repositories.schedules_repository import SchedulesRepository
from app.repositories.skills_repository import SkillsRepository

logger = logging.getLogger(__name__)


def _ensure_aware_utc(timestamp: datetime | str) -> datetime:
    if isinstance(timestamp, str):
        dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    else:
        dt = timestamp

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _validate_iana_timezone(timezone_name: Any) -> str:
    if not isinstance(timezone_name, str):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid timezone. Use a valid IANA timezone name such as Europe/Berlin or UTC.",
        )

    normalized = timezone_name.strip()
    if not normalized:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid timezone. Use a valid IANA timezone name such as Europe/Berlin or UTC.",
        )

    try:
        ZoneInfo(normalized)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid timezone. Use a valid IANA timezone name such as Europe/Berlin or UTC.",
        ) from exc
    return normalized


class OfficeService:
    def __init__(self):
        self.repo = OfficesRepository()
        self.agents_repo = AgentsRepository()
        self.demand_repo = DemandForecastsRepository()
        self.schedule_repo = SchedulesRepository()

    def create(self, payload: OfficeCreate) -> dict[str, Any]:
        existing = self.repo.list(filters=[("name", "==", payload.name)], limit=1)
        if existing:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Office name already exists")
        data = payload.model_dump()
        data["timezone"] = _validate_iana_timezone(data["timezone"])
        return self.repo.create(data)

    def list(self) -> list[dict[str, Any]]:
        return self.repo.list(order_by="name")

    def update(self, office_id: str, payload: OfficeUpdate) -> dict[str, Any]:
        update_data = payload.model_dump(exclude_unset=True)
        if "name" in update_data:
            if self.repo.get(office_id) is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Office not found")
            self._ensure_unique_name(update_data["name"], office_id)
        if "timezone" in update_data:
            update_data["timezone"] = _validate_iana_timezone(update_data["timezone"])

        updated = self.repo.update(office_id, update_data)
        if not updated:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Office not found")
        return updated

    def delete(self, office_id: str) -> dict[str, str]:
        if self.repo.get(office_id) is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Office not found")

        counts = self._reference_counts(office_id)
        _raise_referenced_conflict("Office", counts)

        if not self.repo.delete(office_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Office not found")
        return {"message": "Office deleted"}

    def _ensure_unique_name(self, name: str, current_office_id: str) -> None:
        existing = self.repo.list(filters=[("name", "==", name)], limit=2)
        if any(row.get("id") != current_office_id for row in existing):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Office name already exists")

    def _reference_counts(self, office_id: str) -> dict[str, int]:
        return {
            "agents": _count_filtered(self.agents_repo, [("office_id", "==", office_id)]),
            "demand_forecasts": _count_filtered(self.demand_repo, [("office_id", "==", office_id)]),
            "schedules": _count_schedules_referencing(self.schedule_repo, office_id=office_id),
        }


class SkillService:
    def __init__(self):
        self.repo = SkillsRepository()
        self.agents_repo = AgentsRepository()
        self.demand_repo = DemandForecastsRepository()
        self.schedule_repo = SchedulesRepository()

    def create(self, payload: SkillCreate) -> dict[str, Any]:
        existing = self.repo.list(filters=[("name", "==", payload.name)], limit=1)
        if existing:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Skill name already exists")
        return self.repo.create(payload.model_dump())

    def list(self) -> list[dict[str, Any]]:
        return self.repo.list(order_by="name")

    def update(self, skill_id: str, payload: SkillUpdate) -> dict[str, Any]:
        update_data = payload.model_dump(exclude_unset=True)
        if "name" in update_data:
            if self.repo.get(skill_id) is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Skill not found")
            self._ensure_unique_name(update_data["name"], skill_id)

        updated = self.repo.update(skill_id, update_data)
        if not updated:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Skill not found")
        return updated

    def delete(self, skill_id: str) -> dict[str, str]:
        if self.repo.get(skill_id) is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Skill not found")

        counts = self._reference_counts(skill_id)
        _raise_referenced_conflict("Skill", counts)

        if not self.repo.delete(skill_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Skill not found")
        return {"message": "Skill deleted"}

    def _ensure_unique_name(self, name: str, current_skill_id: str) -> None:
        existing = self.repo.list(filters=[("name", "==", name)], limit=2)
        if any(row.get("id") != current_skill_id for row in existing):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Skill name already exists")

    def _reference_counts(self, skill_id: str) -> dict[str, int]:
        return {
            "agents": _count_agents_referencing_skill(self.agents_repo, skill_id),
            "demand_forecasts": _count_demand_referencing_skill(self.demand_repo, skill_id),
            "schedules": _count_schedules_referencing(self.schedule_repo, skill_id=skill_id),
        }


class AgentService:
    def __init__(self):
        self.repo = AgentsRepository()
        self.office_repo = OfficesRepository()
        self.skill_repo = SkillsRepository()
        self.settings = get_settings()

    def create(self, payload: AgentCreate) -> dict[str, Any]:
        self._validate_agent_references(payload.office_id, payload.skills)

        if payload.weekly_max_hours > self.settings.max_weekly_hours_hard_limit:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "weekly_max_hours exceeds hard safety limit "
                    f"({self.settings.max_weekly_hours_hard_limit})"
                ),
            )

        existing = self.repo.list(filters=[("email", "==", str(payload.email))], limit=1)
        if existing:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Agent email already exists")

        return self.repo.create(payload.model_dump())

    def list(self) -> list[dict[str, Any]]:
        return self.repo.list(order_by="full_name")

    def update(self, agent_id: str, payload: AgentUpdate) -> dict[str, Any]:
        update_data = payload.model_dump(exclude_none=True)

        weekly_max_hours = update_data.get("weekly_max_hours")
        if weekly_max_hours is not None and weekly_max_hours > self.settings.max_weekly_hours_hard_limit:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "weekly_max_hours exceeds hard safety limit "
                    f"({self.settings.max_weekly_hours_hard_limit})"
                ),
            )

        office_id = update_data.get("office_id")
        skills = update_data.get("skills")
        if office_id or skills is not None:
            current = self.repo.get(agent_id)
            if current is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

            resolved_office_id = office_id or current.get("office_id")
            resolved_skills = skills if skills is not None else current.get("skills", [])
            self._validate_agent_references(resolved_office_id, resolved_skills)

        updated = self.repo.update(agent_id, update_data)
        if not updated:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
        return updated

    def delete(self, agent_id: str) -> dict[str, str]:
        if not self.repo.delete(agent_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
        return {"message": "Agent deleted"}

    def _validate_agent_references(self, office_id: str, skills: list[dict] | list[Any]) -> None:
        office = self.office_repo.get(office_id)
        if office is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid office_id")

        for skill_entry in skills:
            skill_id = skill_entry["skill_id"] if isinstance(skill_entry, dict) else skill_entry.skill_id
            if self.skill_repo.get(skill_id) is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid skill_id: {skill_id}",
                )


def _count_filtered(repo: Any, filters: list[tuple[str, str, Any]]) -> int:
    if hasattr(repo, "count"):
        return int(repo.count(filters=filters))
    return len(repo.list(filters=filters))


def _count_agents_referencing_skill(repo: Any, skill_id: str) -> int:
    return sum(
        1
        for agent in repo.list()
        if any(_skill_entry_id(entry) == skill_id for entry in agent.get("skills", []))
    )


def _count_demand_referencing_skill(repo: Any, skill_id: str) -> int:
    count = 0
    for document in repo.list():
        if document.get("skill_id") == skill_id:
            count += 1
            continue

        if any(_skill_entry_id(entry) == skill_id for entry in document.get("skill_demands", [])):
            count += 1
    return count


def _count_schedules_referencing(
    repo: Any,
    *,
    office_id: str | None = None,
    skill_id: str | None = None,
) -> int:
    count = 0
    for schedule in repo.list():
        assignments = schedule.get("assignments", [])
        if any(_assignment_matches(assignment, office_id=office_id, skill_id=skill_id) for assignment in assignments):
            count += 1
    return count


def _assignment_matches(
    assignment: dict[str, Any],
    *,
    office_id: str | None = None,
    skill_id: str | None = None,
) -> bool:
    if office_id is not None and assignment.get("office_id") == office_id:
        return True
    if skill_id is not None and assignment.get("skill_id") == skill_id:
        return True
    return False


def _skill_entry_id(entry: Any) -> str | None:
    if isinstance(entry, dict):
        return entry.get("skill_id")
    return getattr(entry, "skill_id", None)


def _raise_referenced_conflict(resource_name: str, reference_counts: dict[str, int]) -> None:
    total_references = sum(reference_counts.values())
    if total_references <= 0:
        return

    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={
            "message": f"{resource_name} cannot be deleted because existing records still reference it.",
            "reference_counts": reference_counts,
        },
    )


class DemandService:
    DAILY_STORAGE_MODEL = "daily_document_v1"

    def __init__(self):
        self.repo = DemandForecastsRepository()
        self.office_repo = OfficesRepository()
        self.skill_repo = SkillsRepository()
        self.schedule_repo = SchedulesRepository()

    def create(self, payload: DemandForecastCreate) -> dict[str, Any]:
        data = payload.model_dump()
        slot_start = _ensure_aware_utc(data["slot_start"])
        slot_end = _ensure_aware_utc(data["slot_end"])
        if slot_end <= slot_start:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="slot_end must be after slot_start")

        interval_minutes = int((slot_end - slot_start).total_seconds() // 60)
        if interval_minutes not in {30, 60}:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="slot duration must be 30 or 60 minutes")

        office = self._validate_references(payload.office_id, payload.skill_id)
        office_tz = self._resolve_office_timezone(office)
        slot_start_local = slot_start.astimezone(office_tz)
        minute_of_day = slot_start_local.hour * 60 + slot_start_local.minute
        if slot_start_local.second or slot_start_local.microsecond or minute_of_day % interval_minutes != 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="slot_start must align to the interval")

        slot_index = minute_of_day // interval_minutes
        slot_count = (24 * 60) // interval_minutes
        forecast_date = slot_start_local.date().isoformat()
        doc_id = self._daily_document_id(payload.office_id, forecast_date, interval_minutes)
        existing_doc = self.repo.get(doc_id)
        skill_demands = self._normalize_skill_demands(existing_doc.get("skill_demands", []) if existing_doc else [], slot_count)

        skill_entry = next((entry for entry in skill_demands if entry["skill_id"] == payload.skill_id), None)
        if skill_entry is None:
            skill_entry = {
                "skill_id": payload.skill_id,
                "priority": int(payload.priority),
                "quantities": [0] * slot_count,
            }
            skill_demands.append(skill_entry)

        skill_entry["priority"] = int(payload.priority)
        skill_entry["quantities"][slot_index] = int(payload.required_agents)

        forecast_batch_id = str(
            existing_doc.get("forecast_batch_id")
            if existing_doc
            else f"daily_{payload.office_id}_{forecast_date}_{interval_minutes}_{uuid4().hex[:8]}"
        )
        saved_doc = self._upsert_daily_document(
            doc_id,
            {
                "office_id": payload.office_id,
                "forecast_date": forecast_date,
                "interval_minutes": interval_minutes,
                "entry_mode": "daily_grid",
                "storage_model": self.DAILY_STORAGE_MODEL,
                "forecast_batch_id": forecast_batch_id,
                "skill_demands": sorted(skill_demands, key=lambda entry: entry["skill_id"]),
            },
        )
        rows = self._expand_compact_daily_document(saved_doc, {payload.office_id: office})
        for row in rows:
            if row["skill_id"] == payload.skill_id and row["time_block"] == slot_start_local.strftime("%H:%M"):
                return row

        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to save demand row")

    def create_bulk(self, payload: DemandForecastBulkCreate) -> dict[str, Any]:
        created_ids: list[str] = []
        for item in payload.items:
            created = self.create(item)
            created_ids.append(created["id"])
        return {"message": f"Saved {len(created_ids)} demand rows into compact daily documents", "ids": created_ids}

    def create_daily(self, payload: DailyDemandForecastCreate) -> dict[str, Any]:
        office = self.office_repo.get(payload.office_id)
        if office is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid office_id")

        for skill_demand in payload.skill_demands:
            if self.skill_repo.get(skill_demand.skill_id) is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid skill_id: {skill_demand.skill_id}",
                )

        forecast_date = payload.date.isoformat()
        interval = payload.interval_minutes
        forecast_batch_id = f"daily_{payload.office_id}_{forecast_date}_{interval}_{uuid4().hex[:8]}"

        deleted_count = 0
        if payload.replace_existing_day:
            for row in self._list_daily_documents(payload.office_id, forecast_date, interval):
                if self.repo.delete(row["id"]):
                    deleted_count += 1

        created_count = self._represented_slot_count(payload.skill_demands)
        doc_id = (
            self._daily_document_id(payload.office_id, forecast_date, interval)
            if payload.replace_existing_day
            else f"{self._daily_document_id(payload.office_id, forecast_date, interval)}_{uuid4().hex[:8]}"
        )
        self.repo.create(
            self._daily_document_payload(payload, forecast_batch_id),
            document_id=doc_id,
        )

        return {
            "message": (
                "Saved daily demand as 1 Firestore document "
                f"representing {created_count} demand slots"
            ),
            "office_id": payload.office_id,
            "date": forecast_date,
            "interval_minutes": interval,
            "created_count": created_count,
            "deleted_count": deleted_count,
            "forecast_batch_id": forecast_batch_id,
            "document_count": 1,
            "represented_slot_count": created_count,
        }

    async def ingest_csv(self, file: UploadFile) -> dict[str, Any]:
        if not file.filename or not file.filename.lower().endswith(".csv"):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Please upload a CSV file")

        raw_bytes = await file.read()
        text = raw_bytes.decode("utf-8")
        reader = csv.DictReader(io.StringIO(text))

        required_columns = {
            "office_id",
            "skill_id",
            "slot_start",
            "slot_end",
            "required_agents",
            "priority",
        }
        if not reader.fieldnames or not required_columns.issubset(set(reader.fieldnames)):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "CSV must include columns: office_id, skill_id, slot_start, "
                    "slot_end, required_agents, priority"
                ),
            )

        created_count = 0
        for row in reader:
            payload = DemandForecastCreate(
                office_id=row["office_id"],
                skill_id=row["skill_id"],
                slot_start=datetime.fromisoformat(row["slot_start"].replace("Z", "+00:00")),
                slot_end=datetime.fromisoformat(row["slot_end"].replace("Z", "+00:00")),
                required_agents=int(row["required_agents"]),
                priority=int(row.get("priority", 3) or 3),
            )
            self.create(payload)
            created_count += 1

        return {"message": f"Successfully imported {created_count} demand rows into compact daily documents"}

    def list(self, start_at: datetime | None = None, end_at: datetime | None = None) -> list[dict[str, Any]]:
        rows = self._expand_documents(self.repo.list())

        start_at_utc = _ensure_aware_utc(start_at) if start_at else None
        end_at_utc = _ensure_aware_utc(end_at) if end_at else None

        filtered: list[dict[str, Any]] = []
        for row in rows:
            slot_start = _ensure_aware_utc(row["slot_start"])
            if start_at_utc and slot_start < start_at_utc:
                continue
            if end_at_utc and slot_start >= end_at_utc:
                continue
            filtered.append(row)
        return sorted(filtered, key=lambda row: _ensure_aware_utc(row["slot_start"]))

    def day_view(self, office_id: str, forecast_date: date, interval_minutes: int) -> dict[str, Any]:
        if interval_minutes not in {30, 60}:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="interval_minutes must be 30 or 60")

        office = self.office_repo.get(office_id)
        if office is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid office_id")

        target_date = forecast_date.isoformat()
        office_cache = {office_id: office}
        day_rows = self._expand_documents(
            self._list_daily_documents(office_id, target_date, interval_minutes),
            office_cache,
        )

        slot_count = (24 * 60) // interval_minutes
        office_tz = self._resolve_office_timezone(office)
        day_start_local = datetime.combine(forecast_date, time.min, tzinfo=office_tz)

        block_skill_map: dict[str, dict[str, int]] = defaultdict(dict)
        skill_ids: set[str] = set()
        for row in day_rows:
            block = str(row.get("time_block") or _ensure_aware_utc(row["slot_start"]).strftime("%H:%M"))
            skill_id = str(row["skill_id"])
            qty = int(row.get("required_agents", 0))
            current = block_skill_map[block].get(skill_id, 0)
            block_skill_map[block][skill_id] = current + qty
            skill_ids.add(skill_id)

        coverage_block_skill_map: dict[str, dict[str, int]] = defaultdict(dict)
        coverage_schedule_id: str | None = None
        coverage_generated_at: datetime | str | None = None
        schedules = self.schedule_repo.list_active(order_by="generated_at")
        for schedule in reversed(schedules):
            assignments = schedule.get("assignments", [])
            if not assignments:
                continue

            candidate_map: dict[str, dict[str, int]] = defaultdict(dict)
            has_match = False
            for assignment in assignments:
                if str(assignment.get("office_id")) != office_id:
                    continue

                slot_start_local = _ensure_aware_utc(assignment["slot_start"]).astimezone(office_tz)
                slot_end_local = _ensure_aware_utc(assignment["slot_end"]).astimezone(office_tz)
                slot_minutes = int((slot_end_local - slot_start_local).total_seconds() // 60)
                if slot_minutes != interval_minutes:
                    continue
                if slot_start_local.date() != forecast_date:
                    continue

                has_match = True
                block_label = slot_start_local.strftime("%H:%M")
                skill_id = str(assignment["skill_id"])
                covered = int(len(assignment.get("assigned_agent_ids", [])))
                current = candidate_map[block_label].get(skill_id, 0)
                candidate_map[block_label][skill_id] = current + covered
                skill_ids.add(skill_id)

            if has_match:
                coverage_block_skill_map = candidate_map
                schedule_id_value = schedule.get("id")
                coverage_schedule_id = str(schedule_id_value) if schedule_id_value else None
                coverage_generated_at = schedule.get("generated_at")
                break

        blocks: list[dict[str, Any]] = []
        for slot_index in range(slot_count):
            slot_start_local = day_start_local + timedelta(minutes=slot_index * interval_minutes)
            slot_end_local = slot_start_local + timedelta(minutes=interval_minutes)
            slot_start = slot_start_local.astimezone(timezone.utc)
            slot_end = slot_end_local.astimezone(timezone.utc)
            block_label = slot_start_local.strftime("%H:%M")
            totals_by_skill = block_skill_map.get(block_label, {})
            coverage_by_skill = coverage_block_skill_map.get(block_label, {})
            total_required = sum(totals_by_skill.values())
            total_covered = sum(coverage_by_skill.values())
            coverage_gap = max(0, total_required - total_covered)
            coverage_ratio = round((total_covered / total_required), 4) if total_required else 1.0
            blocks.append(
                {
                    "block_start": block_label,
                    "slot_start": slot_start,
                    "slot_end": slot_end,
                    "totals_by_skill": totals_by_skill,
                    "total_required": total_required,
                    "coverage_by_skill": coverage_by_skill,
                    "total_covered": total_covered,
                    "coverage_gap": coverage_gap,
                    "coverage_ratio": coverage_ratio,
                }
            )

        return {
            "office_id": office_id,
            "date": target_date,
            "interval_minutes": interval_minutes,
            "skill_ids": sorted(skill_ids),
            "blocks": blocks,
            "coverage_schedule_id": coverage_schedule_id,
            "coverage_generated_at": coverage_generated_at,
        }

    @staticmethod
    def _resolve_office_timezone(office: dict[str, Any]):
        return resolve_office_timezone(office)

    def _validate_references(self, office_id: str, skill_id: str) -> dict[str, Any]:
        office = self.office_repo.get(office_id)
        if office is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid office_id")
        if self.skill_repo.get(skill_id) is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid skill_id")
        return office

    @staticmethod
    def _daily_document_id(office_id: str, forecast_date: str, interval_minutes: int) -> str:
        return f"daily_{forecast_date}_{office_id}_{interval_minutes}"

    def _daily_document_payload(self, payload: DailyDemandForecastCreate, forecast_batch_id: str) -> dict[str, Any]:
        return {
            "office_id": payload.office_id,
            "forecast_date": payload.date.isoformat(),
            "interval_minutes": payload.interval_minutes,
            "entry_mode": "daily_grid",
            "storage_model": self.DAILY_STORAGE_MODEL,
            "forecast_batch_id": forecast_batch_id,
            "skill_demands": [
                {
                    "skill_id": entry.skill_id,
                    "priority": int(entry.priority),
                    "quantities": [int(qty) for qty in entry.quantities],
                }
                for entry in sorted(payload.skill_demands, key=lambda item: item.skill_id)
            ],
        }

    @staticmethod
    def _represented_slot_count(skill_demands: list[Any]) -> int:
        return sum(1 for entry in skill_demands for qty in entry.quantities if int(qty) > 0)

    def _list_daily_documents(self, office_id: str, forecast_date: str, interval_minutes: int) -> list[dict[str, Any]]:
        prefix = self._daily_document_id(office_id, forecast_date, interval_minutes)
        if hasattr(self.repo, "list_by_document_id_prefix"):
            documents = self.repo.list_by_document_id_prefix(prefix)
        else:
            documents = self.repo.list(
                filters=[
                    ("office_id", "==", office_id),
                    ("forecast_date", "==", forecast_date),
                    ("interval_minutes", "==", interval_minutes),
                ],
            )

        filtered: list[dict[str, Any]] = []
        for document in documents:
            if str(document.get("office_id")) != office_id:
                continue
            if str(document.get("forecast_date")) != forecast_date:
                continue
            try:
                if int(document.get("interval_minutes")) != int(interval_minutes):
                    continue
            except (TypeError, ValueError):
                continue
            filtered.append(document)
        return filtered

    def _upsert_daily_document(self, document_id: str, data: dict[str, Any]) -> dict[str, Any]:
        existing = self.repo.get(document_id)
        if existing:
            updated = self.repo.update(document_id, data)
            if updated is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Demand forecast not found")
            return updated
        return self.repo.create(data, document_id=document_id)

    @staticmethod
    def _normalize_skill_demands(raw_entries: list[Any], slot_count: int) -> list[dict[str, Any]]:
        normalized: list[dict[str, Any]] = []
        for raw_entry in raw_entries:
            entry = dict(raw_entry)
            quantities = [int(qty) for qty in entry.get("quantities", [])[:slot_count]]
            if len(quantities) < slot_count:
                quantities.extend([0] * (slot_count - len(quantities)))
            normalized.append(
                {
                    "skill_id": str(entry["skill_id"]),
                    "priority": int(entry.get("priority", 3) or 3),
                    "quantities": quantities,
                }
            )
        return normalized

    def _expand_documents(
        self,
        documents: list[dict[str, Any]],
        office_cache: dict[str, dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        cache = office_cache if office_cache is not None else {}
        rows: list[dict[str, Any]] = []
        for document in documents:
            if self._is_compact_daily_document(document):
                rows.extend(self._expand_compact_daily_document(document, cache))
            elif "slot_start" in document and "slot_end" in document and "skill_id" in document:
                rows.append(document)
        return rows

    @staticmethod
    def _is_compact_daily_document(document: dict[str, Any]) -> bool:
        return document.get("storage_model") == DemandService.DAILY_STORAGE_MODEL or isinstance(
            document.get("skill_demands"),
            list,
        )

    def _expand_compact_daily_document(
        self,
        document: dict[str, Any],
        office_cache: dict[str, dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        doc_id_for_log = str(document.get("id") or "<unknown>")
        try:
            office_id = str(document["office_id"])
            forecast_date = str(document["forecast_date"])
            interval = int(document["interval_minutes"])
        except (KeyError, TypeError, ValueError) as exc:
            logger.warning(
                "Skipping malformed compact demand document %s: missing or invalid office_id, forecast_date, or interval_minutes",
                doc_id_for_log,
            )
            return []

        if not office_id.strip():
            logger.warning(
                "Skipping malformed compact demand document %s: missing or invalid office_id, forecast_date, or interval_minutes",
                doc_id_for_log,
            )
            return []

        if interval not in {30, 60}:
            logger.warning(
                "Skipping malformed compact demand document %s: interval_minutes must be 30 or 60",
                doc_id_for_log,
            )
            return []

        skill_demands_raw = document.get("skill_demands")
        if not isinstance(skill_demands_raw, list):
            logger.warning(
                "Skipping malformed compact demand document %s: missing or invalid skill_demands",
                doc_id_for_log,
            )
            return []

        try:
            forecast_day = date.fromisoformat(forecast_date)
        except ValueError:
            logger.warning(
                "Skipping malformed compact demand document %s: forecast_date must be ISO yyyy-mm-dd",
                doc_id_for_log,
            )
            return []

        slot_count = (24 * 60) // interval
        doc_id = str(document.get("id") or self._daily_document_id(office_id, forecast_date, interval))

        cache = office_cache if office_cache is not None else {}
        if office_id not in cache:
            cache[office_id] = self.office_repo.get(office_id) or {}

        office_tz = self._resolve_office_timezone(cache.get(office_id, {}))
        day_start_local = datetime.combine(forecast_day, time.min, tzinfo=office_tz)

        rows: list[dict[str, Any]] = []
        try:
            skill_demands = self._normalize_skill_demands(skill_demands_raw, slot_count)
        except (KeyError, TypeError, ValueError) as exc:
            logger.warning(
                "Skipping malformed compact demand document %s: invalid skill_demands entries",
                doc_id,
            )
            return []

        for skill_demand in skill_demands:
            skill_id = str(skill_demand["skill_id"])
            priority = int(skill_demand.get("priority", 3))
            quantities = skill_demand["quantities"]
            for slot_index, quantity in enumerate(quantities):
                qty = int(quantity)
                if qty <= 0:
                    continue

                slot_start_local = day_start_local + timedelta(minutes=slot_index * interval)
                slot_end_local = slot_start_local + timedelta(minutes=interval)
                rows.append(
                    {
                        "id": f"{doc_id}_{slot_index:02d}_{skill_id}",
                        "source_document_id": doc_id,
                        "office_id": office_id,
                        "skill_id": skill_id,
                        "slot_start": slot_start_local.astimezone(timezone.utc),
                        "slot_end": slot_end_local.astimezone(timezone.utc),
                        "required_agents": qty,
                        "priority": priority,
                        "forecast_date": forecast_date,
                        "interval_minutes": interval,
                        "time_block": slot_start_local.strftime("%H:%M"),
                        "entry_mode": str(document.get("entry_mode") or "daily_grid"),
                        "storage_model": self.DAILY_STORAGE_MODEL,
                        "forecast_batch_id": document.get("forecast_batch_id"),
                        "created_at": document.get("created_at"),
                        "updated_at": document.get("updated_at"),
                    }
                )
        return rows
