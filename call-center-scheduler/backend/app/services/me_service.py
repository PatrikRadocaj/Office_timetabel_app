"""Agent-facing personal dashboard service."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from app.repositories.agents_repository import AgentsRepository
from app.repositories.announcements_repository import AnnouncementsRepository
from app.repositories.offices_repository import OfficesRepository
from app.repositories.schedules_repository import SchedulesRepository
from app.repositories.skills_repository import SkillsRepository


def _as_utc(value: datetime | str) -> datetime:
    if isinstance(value, str):
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    else:
        dt = value
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _resolve_timezone(timezone_name: str | None) -> ZoneInfo | timezone:
    name = str(timezone_name or "UTC")
    try:
        return ZoneInfo(name)
    except Exception:
        return timezone.utc


def _build_greeting(current_local_time: datetime) -> str:
    if current_local_time.hour < 12:
        return "Good morning"
    if current_local_time.hour < 18:
        return "Good afternoon"
    return "Good evening"


class MeService:
    """Builds personal dashboard payload for logged-in agents."""

    def __init__(self):
        self.agents_repo = AgentsRepository()
        self.skills_repo = SkillsRepository()
        self.offices_repo = OfficesRepository()
        self.schedules_repo = SchedulesRepository()
        self.announcements_repo = AnnouncementsRepository()

    def dashboard(self, current_user: dict[str, Any]) -> dict[str, Any]:
        agent = self._resolve_agent_profile(current_user)
        offices = {office["id"]: office for office in self.offices_repo.list()}
        skills = {skill["id"]: skill for skill in self.skills_repo.list()}
        today_utc = datetime.now(timezone.utc)

        if agent and offices.get(agent.get("office_id")):
            office_tz = _resolve_timezone(offices[agent["office_id"]].get("timezone"))
        else:
            office_tz = timezone.utc

        today_local_date = today_utc.astimezone(office_tz).date()
        greeting = _build_greeting(today_utc.astimezone(office_tz))

        weekly_schedule = self._build_weekly_schedule(
            agent=agent,
            offices_by_id=offices,
            skills_by_id=skills,
            week_start=today_local_date,
        )

        today_shift = weekly_schedule[0] if weekly_schedule and weekly_schedule[0]["shift_start"] else None
        is_scheduled_today = today_shift is not None
        status_text = "You are scheduled for today" if is_scheduled_today else "You have a day off today"

        weekly_max_hours = float(agent.get("weekly_max_hours", 0)) if agent else 0.0
        hours_worked_week = round(sum(day["total_hours"] for day in weekly_schedule), 2)
        hours_remaining = round(max(0.0, weekly_max_hours - hours_worked_week), 2)
        overtime_hours = round(max(0.0, hours_worked_week - weekly_max_hours), 2)

        return {
            "full_name": current_user.get("full_name") or current_user.get("email") or "Agent",
            "today_date": today_local_date.isoformat(),
            "greeting": greeting,
            "status_text": status_text,
            "is_scheduled_today": is_scheduled_today,
            "today_shift": today_shift,
            "weekly_schedule": weekly_schedule,
            "hours_overview": {
                "weekly_max_hours": weekly_max_hours,
                "hours_worked_week": hours_worked_week,
                "hours_remaining": hours_remaining,
                "overtime_hours": overtime_hours,
            },
            "skills": self._build_skills(agent=agent, skills_by_id=skills),
            "announcements": self._load_announcements(),
        }

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

    def _collect_agent_slot_assignments(self, agent_id: str) -> list[dict[str, Any]]:
        schedules = self.schedules_repo.list(order_by="generated_at")
        latest_assignment_by_slot: dict[tuple[str, str, str, str], dict[str, Any]] = {}

        for schedule in reversed(schedules):
            for assignment in schedule.get("assignments", []):
                if agent_id not in assignment.get("assigned_agent_ids", []):
                    continue

                key = (
                    str(assignment.get("slot_start")),
                    str(assignment.get("slot_end")),
                    str(assignment.get("office_id")),
                    str(assignment.get("skill_id")),
                )
                if key not in latest_assignment_by_slot:
                    latest_assignment_by_slot[key] = assignment

        values = list(latest_assignment_by_slot.values())
        values.sort(key=lambda entry: _as_utc(entry["slot_start"]))
        return values

    def _build_weekly_schedule(
        self,
        agent: dict[str, Any] | None,
        offices_by_id: dict[str, dict[str, Any]],
        skills_by_id: dict[str, dict[str, Any]],
        week_start: date,
    ) -> list[dict[str, Any]]:
        if not agent:
            return [self._empty_day_row(week_start + timedelta(days=offset)) for offset in range(7)]

        rows_by_day: dict[date, list[dict[str, Any]]] = defaultdict(list)
        week_end = week_start + timedelta(days=6)
        assignments = self._collect_agent_slot_assignments(agent["id"])

        for assignment in assignments:
            office_id = str(assignment.get("office_id"))
            office = offices_by_id.get(office_id, {})
            local_tz = _resolve_timezone(office.get("timezone"))

            slot_start_local = _as_utc(assignment["slot_start"]).astimezone(local_tz)
            slot_end_local = _as_utc(assignment["slot_end"]).astimezone(local_tz)
            local_day = slot_start_local.date()

            if local_day < week_start or local_day > week_end:
                continue

            rows_by_day[local_day].append(
                {
                    "slot_start": slot_start_local,
                    "slot_end": slot_end_local,
                    "office_name": office.get("name", office_id),
                    "skill_name": skills_by_id.get(str(assignment.get("skill_id")), {}).get(
                        "name", str(assignment.get("skill_id"))
                    ),
                }
            )

        weekly_rows: list[dict[str, Any]] = []
        for offset in range(7):
            current_day = week_start + timedelta(days=offset)
            day_entries = rows_by_day.get(current_day, [])
            if not day_entries:
                weekly_rows.append(self._empty_day_row(current_day))
                continue

            day_entries.sort(key=lambda entry: entry["slot_start"])
            earliest = day_entries[0]["slot_start"]
            latest = max(entry["slot_end"] for entry in day_entries)
            offices = sorted({entry["office_name"] for entry in day_entries})
            skills = sorted({entry["skill_name"] for entry in day_entries})
            total_hours = round(sum((entry["slot_end"] - entry["slot_start"]).total_seconds() / 3600 for entry in day_entries), 2)

            weekly_rows.append(
                {
                    "date": current_day.isoformat(),
                    "day_name": current_day.strftime("%A"),
                    "shift_start": earliest.isoformat(),
                    "shift_end": latest.isoformat(),
                    "office": offices[0] if len(offices) == 1 else "Multiple offices",
                    "required_skills": skills,
                    "total_hours": total_hours,
                    "break_time": None,
                }
            )

        return weekly_rows

    @staticmethod
    def _empty_day_row(current_day: date) -> dict[str, Any]:
        return {
            "date": current_day.isoformat(),
            "day_name": current_day.strftime("%A"),
            "shift_start": None,
            "shift_end": None,
            "office": "-",
            "required_skills": [],
            "total_hours": 0.0,
            "break_time": None,
        }

    @staticmethod
    def _build_skills(agent: dict[str, Any] | None, skills_by_id: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
        if not agent:
            return []

        result: list[dict[str, Any]] = []
        for skill in agent.get("skills", []):
            skill_id = str(skill.get("skill_id"))
            proficiency = int(skill.get("proficiency", 1))
            result.append(
                {
                    "skill_id": skill_id,
                    "skill_name": skills_by_id.get(skill_id, {}).get("name", skill_id),
                    "proficiency": proficiency,
                    "proficiency_pct": max(0, min(100, proficiency * 20)),
                }
            )
        return result

    def _load_announcements(self) -> list[dict[str, Any]]:
        rows = self.announcements_repo.list(order_by="created_at")
        rows.reverse()  # newest first

        announcements: list[dict[str, Any]] = []
        for row in rows:
            if row.get("is_active", True) is False:
                continue

            title = str(row.get("title") or "").strip() or "Notice"
            message = str(row.get("message") or row.get("body") or "").strip()
            if not message:
                continue

            announcements.append(
                {
                    "id": row["id"],
                    "title": title,
                    "message": message,
                    "published_at": row.get("published_at") or row.get("created_at"),
                }
            )
            if len(announcements) >= 10:
                break

        return announcements
