"""CRUD and ingestion services for offices, skills, agents, and demand."""

from __future__ import annotations

import csv
import io
from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo

from fastapi import HTTPException, UploadFile, status

from app.core.config import get_settings
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


def _ensure_aware_utc(timestamp: datetime | str) -> datetime:
    if isinstance(timestamp, str):
        dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    else:
        dt = timestamp

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


class OfficeService:
    def __init__(self):
        self.repo = OfficesRepository()

    def create(self, payload: OfficeCreate) -> dict[str, Any]:
        existing = self.repo.list(filters=[("name", "==", payload.name)], limit=1)
        if existing:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Office name already exists")
        return self.repo.create(payload.model_dump())

    def list(self) -> list[dict[str, Any]]:
        return self.repo.list(order_by="name")

    def update(self, office_id: str, payload: OfficeUpdate) -> dict[str, Any]:
        updated = self.repo.update(office_id, payload.model_dump(exclude_unset=True))
        if not updated:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Office not found")
        return updated

    def delete(self, office_id: str) -> dict[str, str]:
        if not self.repo.delete(office_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Office not found")
        return {"message": "Office deleted"}


class SkillService:
    def __init__(self):
        self.repo = SkillsRepository()

    def create(self, payload: SkillCreate) -> dict[str, Any]:
        existing = self.repo.list(filters=[("name", "==", payload.name)], limit=1)
        if existing:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Skill name already exists")
        return self.repo.create(payload.model_dump())

    def list(self) -> list[dict[str, Any]]:
        return self.repo.list(order_by="name")

    def update(self, skill_id: str, payload: SkillUpdate) -> dict[str, Any]:
        updated = self.repo.update(skill_id, payload.model_dump(exclude_unset=True))
        if not updated:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Skill not found")
        return updated

    def delete(self, skill_id: str) -> dict[str, str]:
        if not self.repo.delete(skill_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Skill not found")
        return {"message": "Skill deleted"}


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


class DemandService:
    def __init__(self):
        self.repo = DemandForecastsRepository()
        self.office_repo = OfficesRepository()
        self.skill_repo = SkillsRepository()
        self.schedule_repo = SchedulesRepository()

    def create(self, payload: DemandForecastCreate) -> dict[str, Any]:
        self._validate_references(payload.office_id, payload.skill_id)
        data = payload.model_dump()
        data["slot_start"] = _ensure_aware_utc(data["slot_start"])
        data["slot_end"] = _ensure_aware_utc(data["slot_end"])
        if data["slot_end"] <= data["slot_start"]:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="slot_end must be after slot_start")
        return self.repo.create(data)

    def create_bulk(self, payload: DemandForecastBulkCreate) -> dict[str, Any]:
        created_ids: list[str] = []
        for item in payload.items:
            created = self.create(item)
            created_ids.append(created["id"])
        return {"message": f"Created {len(created_ids)} demand rows", "ids": created_ids}

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
        office_tz = self._resolve_office_timezone(office)
        day_start_local = datetime.combine(payload.date, time.min, tzinfo=office_tz)
        slot_count = (24 * 60) // interval
        forecast_batch_id = f"daily_{payload.office_id}_{forecast_date}_{interval}_{uuid4().hex[:8]}"

        deleted_count = 0
        if payload.replace_existing_day:
            existing_rows = self.repo.list(filters=[("office_id", "==", payload.office_id)])
            rows_to_delete = [
                row
                for row in existing_rows
                if row.get("forecast_date") == forecast_date and int(row.get("interval_minutes", interval)) == interval
            ]
            for row in rows_to_delete:
                if self.repo.delete(row["id"]):
                    deleted_count += 1

        created_count = 0
        for slot_index in range(slot_count):
            slot_start_local = day_start_local + timedelta(minutes=slot_index * interval)
            slot_end_local = slot_start_local + timedelta(minutes=interval)
            slot_start = slot_start_local.astimezone(timezone.utc)
            slot_end = slot_end_local.astimezone(timezone.utc)
            time_block = slot_start_local.strftime("%H:%M")

            for skill_demand in payload.skill_demands:
                quantity = int(skill_demand.quantities[slot_index])
                if quantity <= 0:
                    continue

                row = {
                    "office_id": payload.office_id,
                    "skill_id": skill_demand.skill_id,
                    "slot_start": slot_start,
                    "slot_end": slot_end,
                    "required_agents": quantity,
                    "priority": int(skill_demand.priority),
                    "forecast_date": forecast_date,
                    "interval_minutes": interval,
                    "time_block": time_block,
                    "entry_mode": "daily_grid",
                    "forecast_batch_id": forecast_batch_id,
                }
                self.repo.create(row)
                created_count += 1

        return {
            "message": f"Created {created_count} demand rows from daily demand grid",
            "office_id": payload.office_id,
            "date": forecast_date,
            "interval_minutes": interval,
            "created_count": created_count,
            "deleted_count": deleted_count,
            "forecast_batch_id": forecast_batch_id,
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

        return {"message": f"Successfully imported {created_count} demand rows"}

    def list(self, start_at: datetime | None = None, end_at: datetime | None = None) -> list[dict[str, Any]]:
        rows = self.repo.list(order_by="slot_start")
        if start_at is None and end_at is None:
            return rows

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
        return filtered

    def day_view(self, office_id: str, forecast_date: date, interval_minutes: int) -> dict[str, Any]:
        if interval_minutes not in {30, 60}:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="interval_minutes must be 30 or 60")

        office = self.office_repo.get(office_id)
        if office is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid office_id")

        rows = self.repo.list(filters=[("office_id", "==", office_id)])
        target_date = forecast_date.isoformat()
        day_rows = [
            row
            for row in rows
            if row.get("forecast_date") == target_date and int(row.get("interval_minutes", interval_minutes)) == interval_minutes
        ]

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
        schedules = self.schedule_repo.list(order_by="generated_at")
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
        timezone_name = str(office.get("timezone") or "UTC")
        try:
            return ZoneInfo(timezone_name)
        except Exception:
            return timezone.utc

    def _validate_references(self, office_id: str, skill_id: str) -> None:
        if self.office_repo.get(office_id) is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid office_id")
        if self.skill_repo.get(skill_id) is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid skill_id")
