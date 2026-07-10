"""Heuristic schedule generation engine."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone, tzinfo
from typing import Any
from uuid import uuid4

from fastapi import HTTPException, status

from app.core.config import get_settings
from app.core.timezones import resolve_office_timezone
from app.models.common import utcnow
from app.models.schedule import ScheduleGenerationRequest, ScheduleWeekGenerationRequest
from app.repositories.agents_repository import AgentsRepository
from app.repositories.offices_repository import OfficesRepository
from app.repositories.schedules_repository import ACTIVE_SCHEDULE_STATUS, SchedulesRepository
from app.repositories.skills_repository import SkillsRepository
from app.services.catalog_service import DemandService


def _as_utc(value: datetime | str) -> datetime:
    if isinstance(value, str):
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    else:
        dt = value

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


class SchedulerService:
    """Produces feasible schedules with business-rule-aware heuristics."""

    def __init__(self):
        self.settings = get_settings()
        self.demand_service = DemandService()
        self.agent_repo = AgentsRepository()
        self.office_repo = OfficesRepository()
        self.skill_repo = SkillsRepository()
        self.schedule_repo = SchedulesRepository()

    def generate(self, payload: ScheduleGenerationRequest) -> dict[str, Any]:
        if payload.end_at <= payload.start_at:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="end_at must be after start_at")

        assignments, total_required, total_assigned = self._compute_assignments(payload.start_at, payload.end_at)
        schedule_doc = self.schedule_repo.create(
            self._schedule_document(
                start_at=payload.start_at,
                end_at=payload.end_at,
                assignments=assignments,
                metadata={},
            ),
            document_id=None,
        )
        return {
            "schedule_id": schedule_doc["id"],
            "assignments": assignments,
            "total_required": total_required,
            "total_assigned": total_assigned,
            "uncovered_demand": max(0, total_required - total_assigned),
        }

    def generate_week(self, payload: ScheduleWeekGenerationRequest) -> dict[str, Any]:
        week_start, week_end = self.iso_week_range(payload.year, payload.week)
        assignments, total_required, total_assigned = self._compute_assignments(week_start, week_end)

        # A full ISO week at production demand exceeds Firestore's 1 MiB document
        # limit, so the week persists as one shard document per UTC day. Every
        # reader (dashboards, me-service, day-view coverage, swaps) consumes
        # schedules via list_active with newest-wins per-slot dedup, so multiple
        # active documents for one week are already handled.
        batch_id = f"schedule_{payload.year}_W{payload.week:02d}_{uuid4().hex[:8]}"
        week_metadata = {
            "year": payload.year,
            "week": payload.week,
            "week_start": week_start,
            "week_end": week_end,
            "generation_scope": "iso_week",
            "generation_batch_id": batch_id,
        }

        # Persist the new shards FIRST; only archive the previous actives once
        # every shard is stored. A persist failure therefore leaves the previous
        # schedules untouched, while an archive failure merely leaves duplicate
        # actives, which newest-wins already tolerates.
        created_ids: list[str] = []
        for day_index, (day_start, day_end, day_assignments) in enumerate(
            self._split_assignments_by_utc_day(assignments, week_start, week_end)
        ):
            shard_doc = self.schedule_repo.create(
                self._schedule_document(
                    start_at=day_start,
                    end_at=day_end,
                    assignments=day_assignments,
                    metadata={**week_metadata, "day_index": day_index},
                ),
                document_id=f"{batch_id}_d{day_index}",
            )
            created_ids.append(str(shard_doc["id"]))

        archived_schedule_ids = self.schedule_repo.archive_active_for_week(
            payload.year, payload.week, exclude_ids=created_ids
        )

        return {
            "schedule_id": batch_id,
            "schedule_ids": created_ids,
            "document_count": len(created_ids),
            "assignments": assignments,
            "total_required": total_required,
            "total_assigned": total_assigned,
            "uncovered_demand": max(0, total_required - total_assigned),
            "year": payload.year,
            "week": payload.week,
            "week_start": week_start,
            "week_end": week_end,
            "archived_schedule_ids": archived_schedule_ids,
        }

    @staticmethod
    def iso_week_range(year: int, week: int) -> tuple[datetime, datetime]:
        try:
            start_date = date.fromisocalendar(int(year), int(week), 1)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"{year} does not have ISO week {week}",
            ) from exc
        start = datetime.combine(start_date, time.min, tzinfo=timezone.utc)
        return start, start + timedelta(days=7)

    def _compute_assignments(self, start_at: datetime, end_at: datetime) -> tuple[list[dict[str, Any]], int, int]:
        demand_rows = self._load_demand(start_at, end_at)
        agents = [agent for agent in self.agent_repo.list() if agent.get("is_active", True)]
        offices = {office["id"]: office for office in self.office_repo.list()}
        skills = {skill["id"]: skill for skill in self.skill_repo.list()}
        office_timezones = {office_id: resolve_office_timezone(office) for office_id, office in offices.items()}

        if not demand_rows:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No demand rows for selected window")
        if not agents:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No active agents available")

        agent_state: dict[str, dict[str, Any]] = {
            agent["id"]: {
                "weekly_hours": 0.0,
                "last_slot_start": None,
                "assignments": [],
            }
            for agent in agents
        }

        assignments: list[dict[str, Any]] = []
        grouped = self._group_demand_by_slot_and_skill(demand_rows)

        for slot_key in sorted(grouped.keys()):
            slot_rows = grouped[slot_key]
            office_usage: dict[str, int] = defaultdict(int)
            used_agents_this_slot: set[str] = set()

            for demand in sorted(slot_rows, key=lambda x: (-int(x["priority"]), -int(x["required_agents"]))):
                office_id = demand["office_id"]
                skill_id = demand["skill_id"]
                required = int(demand["required_agents"])
                slot_start = _as_utc(demand["slot_start"])
                slot_end = _as_utc(demand["slot_end"])
                slot_hours = (slot_end - slot_start).total_seconds() / 3600.0

                capacity = int(offices.get(office_id, {}).get("max_capacity", 0))
                remaining_capacity = max(0, capacity - office_usage[office_id])
                target = min(required, remaining_capacity)

                eligible_agents = self._rank_eligible_agents(
                    agents=agents,
                    demand_office_id=office_id,
                    skill_id=skill_id,
                    slot_start=slot_start,
                    slot_end=slot_end,
                    used_agents_this_slot=used_agents_this_slot,
                    agent_state=agent_state,
                    skills=skills,
                    slot_hours=slot_hours,
                    office_timezones=office_timezones,
                )

                selected_ids: list[str] = []
                for agent in eligible_agents:
                    if len(selected_ids) >= target:
                        break
                    selected_ids.append(agent["id"])
                    used_agents_this_slot.add(agent["id"])
                    office_usage[office_id] += 1

                    state = agent_state[agent["id"]]
                    state["weekly_hours"] += slot_hours
                    state["last_slot_start"] = slot_start
                    state["assignments"].append({
                        "slot_start": slot_start,
                        "slot_end": slot_end,
                        "office_id": office_id,
                        "skill_id": skill_id,
                    })

                assigned = len(selected_ids)
                coverage_ratio = (assigned / required) if required else 1.0
                assignments.append(
                    {
                        "slot_start": slot_start,
                        "slot_end": slot_end,
                        "office_id": office_id,
                        "skill_id": skill_id,
                        "assigned_agent_ids": selected_ids,
                        "required_agents": required,
                        "coverage_ratio": round(coverage_ratio, 4),
                        "gap": max(0, required - assigned),
                    }
                )

        total_required = sum(item["required_agents"] for item in assignments)
        total_assigned = sum(len(item["assigned_agent_ids"]) for item in assignments)
        return assignments, total_required, total_assigned

    def _schedule_document(
        self,
        *,
        start_at: datetime,
        end_at: datetime,
        assignments: list[dict[str, Any]],
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        total_required = sum(item["required_agents"] for item in assignments)
        total_assigned = sum(len(item["assigned_agent_ids"]) for item in assignments)
        return {
            "start_at": _as_utc(start_at),
            "end_at": _as_utc(end_at),
            "generated_at": utcnow(),
            "status": ACTIVE_SCHEDULE_STATUS,
            "algorithm": "greedy-balanced-weekly-capacity-v2",
            "slot_minutes": self.settings.schedule_slot_minutes,
            **metadata,
            "assignments": assignments,
            "metrics": {
                "total_required": total_required,
                "total_assigned": total_assigned,
                "coverage_pct": round((total_assigned / total_required * 100.0), 2) if total_required else 100.0,
                "uncovered_demand": max(0, total_required - total_assigned),
            },
        }

    @staticmethod
    def _split_assignments_by_utc_day(
        assignments: list[dict[str, Any]],
        window_start: datetime,
        window_end: datetime,
    ) -> list[tuple[datetime, datetime, list[dict[str, Any]]]]:
        """Group assignments into per-UTC-day shards, keeping in-day order."""

        by_day: dict[date, list[dict[str, Any]]] = defaultdict(list)
        for assignment in assignments:
            by_day[_as_utc(assignment["slot_start"]).date()].append(assignment)

        shards: list[tuple[datetime, datetime, list[dict[str, Any]]]] = []
        for day in sorted(by_day.keys()):
            day_start = max(datetime.combine(day, time.min, tzinfo=timezone.utc), _as_utc(window_start))
            day_end = min(day_start + timedelta(days=1), _as_utc(window_end))
            shards.append((day_start, day_end, by_day[day]))
        return shards

    def _load_demand(self, start_at: datetime, end_at: datetime) -> list[dict[str, Any]]:
        return self.demand_service.list(start_at=start_at, end_at=end_at)

    @staticmethod
    def _group_demand_by_slot_and_skill(rows: list[dict[str, Any]]) -> dict[tuple[str, str], list[dict[str, Any]]]:
        grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            key = (_as_utc(row["slot_start"]).isoformat(), _as_utc(row["slot_end"]).isoformat())
            grouped[key].append(row)
        return grouped

    def _rank_eligible_agents(
        self,
        agents: list[dict[str, Any]],
        demand_office_id: str,
        skill_id: str,
        slot_start: datetime,
        slot_end: datetime,
        used_agents_this_slot: set[str],
        agent_state: dict[str, dict[str, Any]],
        skills: dict[str, dict[str, Any]],
        slot_hours: float,
        office_timezones: dict[str, tzinfo],
    ) -> list[dict[str, Any]]:
        min_proficiency = int(skills.get(skill_id, {}).get("min_proficiency", 1))

        eligible: list[tuple[float, str, dict[str, Any]]] = []
        for agent in agents:
            agent_id = agent["id"]
            if agent_id in used_agents_this_slot:
                continue

            if str(agent.get("office_id")) != str(demand_office_id):
                continue

            if not self._agent_has_skill(agent, skill_id, min_proficiency):
                continue

            # Availability windows and shift preferences are office-local.
            office_tz = office_timezones.get(agent.get("office_id"), timezone.utc)
            if not self._agent_is_available(agent, slot_start, slot_end, office_tz):
                continue

            state = agent_state[agent_id]
            weekly_max_hours = float(agent["weekly_max_hours"])
            projected_weekly_hours = state["weekly_hours"] + slot_hours
            if projected_weekly_hours > weekly_max_hours:
                continue

            # Soft rest-period guard: if previous slot ended too recently, skip.
            last_slot_start = state["last_slot_start"]
            if last_slot_start is not None:
                min_rest = timedelta(hours=float(agent["min_rest_hours"]))
                approx_last_end = _as_utc(last_slot_start) + timedelta(minutes=self.settings.schedule_slot_minutes)
                if slot_start - approx_last_end < timedelta(0):
                    continue
                if slot_start.date() != approx_last_end.date() and slot_start - approx_last_end < min_rest:
                    continue

            # Lower score is better.
            preference_score = self._shift_preference_penalty(
                agent.get("shift_preference", "any"), slot_start.astimezone(office_tz).hour
            )
            proficiency = self._agent_skill_proficiency(agent, skill_id)
            current_load_ratio = state["weekly_hours"] / weekly_max_hours if weekly_max_hours else 1.0
            remaining_after = max(0.0, weekly_max_hours - projected_weekly_hours)
            score = (
                current_load_ratio * 100.0
                + preference_score * 10.0
                - proficiency * 0.5
                - remaining_after * 0.05
            )
            eligible.append((score, str(agent_id), agent))

        eligible.sort(key=lambda item: (item[0], item[1]))
        return [item[2] for item in eligible]

    @staticmethod
    def _agent_has_skill(agent: dict[str, Any], skill_id: str, min_proficiency: int) -> bool:
        return SchedulerService._agent_skill_proficiency(agent, skill_id) >= min_proficiency

    @staticmethod
    def _agent_skill_proficiency(agent: dict[str, Any], skill_id: str) -> int:
        for skill in agent.get("skills", []):
            if skill.get("skill_id") == skill_id:
                return int(skill.get("proficiency", 0))
        return 0

    @staticmethod
    def _agent_is_available(agent: dict[str, Any], slot_start: datetime, slot_end: datetime, office_tz: tzinfo) -> bool:
        availability = agent.get("availability", [])
        if not availability:
            return True

        local_start = slot_start.astimezone(office_tz)
        weekday = local_start.weekday()
        slot_start_hour = local_start.hour + local_start.minute / 60.0
        # Derive the end from the duration so a slot ending at local midnight reads as 24.0, not 0.0.
        slot_end_hour = slot_start_hour + (slot_end - slot_start).total_seconds() / 3600.0

        for window in availability:
            if int(window.get("day_of_week", -1)) != weekday:
                continue
            start_hour = float(window.get("start_hour", 0))
            end_hour = float(window.get("end_hour", 0))
            if start_hour <= slot_start_hour and slot_end_hour <= end_hour:
                return True
        return False

    @staticmethod
    def _shift_preference_penalty(preference: str, slot_hour: int) -> int:
        if preference == "any":
            return 0
        is_day = 7 <= slot_hour < 19
        if preference == "day" and is_day:
            return 0
        if preference == "night" and not is_day:
            return 0
        return 1
