"""Office-local availability matching regression tests."""

from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pytest
from pydantic import ValidationError

from app.models.common import TimeWindow
from app.services.scheduler_service import SchedulerService


BERLIN = ZoneInfo("Europe/Berlin")  # UTC+2 in July (CEST)


def _agent(availability: list[dict[str, int]]) -> dict:
    return {
        "id": "agent-1",
        "office_id": "office-berlin",
        "weekly_max_hours": 40,
        "min_rest_hours": 10,
        "shift_preference": "any",
        "skills": [{"skill_id": "skill-a", "proficiency": 3}],
        "availability": availability,
    }


def _utc(year: int, month: int, day: int, hour: int, minute: int = 0) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=timezone.utc)


MONDAY_9_17 = [{"day_of_week": 0, "start_hour": 9, "end_hour": 17}]


def test_window_matches_office_local_hours_not_utc() -> None:
    agent = _agent(MONDAY_9_17)
    # 2026-07-13 is a Monday; Berlin is UTC+2, so 08:00 UTC is 10:00 local.
    inside = SchedulerService._agent_is_available(
        agent, _utc(2026, 7, 13, 8), _utc(2026, 7, 13, 9), BERLIN
    )
    assert inside is True


def test_window_rejects_slot_before_local_start() -> None:
    agent = _agent(MONDAY_9_17)
    # 06:00 UTC is 08:00 local Monday, one hour before the window opens.
    outside = SchedulerService._agent_is_available(
        agent, _utc(2026, 7, 13, 6), _utc(2026, 7, 13, 7), BERLIN
    )
    assert outside is False


def test_midnight_adjacent_slot_uses_local_weekday() -> None:
    # 22:00 UTC Sunday 2026-07-12 is 00:00 local Monday.
    slot_start = _utc(2026, 7, 12, 22)
    slot_end = _utc(2026, 7, 12, 23)

    monday_night = _agent([{"day_of_week": 0, "start_hour": 0, "end_hour": 8}])
    assert SchedulerService._agent_is_available(monday_night, slot_start, slot_end, BERLIN) is True

    sunday_night = _agent([{"day_of_week": 6, "start_hour": 22, "end_hour": 24}])
    assert SchedulerService._agent_is_available(sunday_night, slot_start, slot_end, BERLIN) is False


def test_slot_ending_at_local_midnight_reads_as_hour_24() -> None:
    # 21:30-22:00 UTC Monday is 23:30-00:00 local; end hour must be 24.0, not 0.0.
    slot_start = _utc(2026, 7, 13, 21, 30)
    slot_end = _utc(2026, 7, 13, 22)

    early_window = _agent([{"day_of_week": 0, "start_hour": 0, "end_hour": 8}])
    assert SchedulerService._agent_is_available(early_window, slot_start, slot_end, BERLIN) is False

    late_window = _agent([{"day_of_week": 0, "start_hour": 16, "end_hour": 24}])
    assert SchedulerService._agent_is_available(late_window, slot_start, slot_end, BERLIN) is True


def test_empty_availability_means_always_available() -> None:
    agent = _agent([])
    assert SchedulerService._agent_is_available(
        agent, _utc(2026, 7, 13, 3), _utc(2026, 7, 13, 4), BERLIN
    ) is True


def test_rank_eligible_agents_localizes_by_agent_office() -> None:
    service = SchedulerService.__new__(SchedulerService)
    agent = _agent(MONDAY_9_17)
    agent_state = {"agent-1": {"weekly_hours": 0.0, "last_slot_start": None, "assignments": []}}
    office_timezones = {"office-berlin": BERLIN}
    skills = {"skill-a": {"min_proficiency": 1}}

    ranked = service._rank_eligible_agents(
        agents=[agent],
        skill_id="skill-a",
        slot_start=_utc(2026, 7, 13, 8),
        slot_end=_utc(2026, 7, 13, 9),
        used_agents_this_slot=set(),
        agent_state=agent_state,
        skills=skills,
        slot_hours=1.0,
        office_timezones=office_timezones,
    )
    assert [entry["id"] for entry in ranked] == ["agent-1"]

    ranked_outside = service._rank_eligible_agents(
        agents=[agent],
        skill_id="skill-a",
        slot_start=_utc(2026, 7, 13, 6),
        slot_end=_utc(2026, 7, 13, 7),
        used_agents_this_slot=set(),
        agent_state=agent_state,
        skills=skills,
        slot_hours=1.0,
        office_timezones=office_timezones,
    )
    assert ranked_outside == []


def test_time_window_accepts_full_day_bounds() -> None:
    window = TimeWindow(day_of_week=6, start_hour=0, end_hour=24)
    assert window.end_hour == 24


@pytest.mark.parametrize(
    "payload",
    [
        {"day_of_week": 7, "start_hour": 9, "end_hour": 17},
        {"day_of_week": -1, "start_hour": 9, "end_hour": 17},
        {"day_of_week": 0, "start_hour": 24, "end_hour": 24},
        {"day_of_week": 0, "start_hour": 9, "end_hour": 25},
        {"day_of_week": 0, "start_hour": 9, "end_hour": 0},
        {"day_of_week": 0, "start_hour": 17, "end_hour": 9},
        {"day_of_week": 0, "start_hour": 9, "end_hour": 9},
    ],
)
def test_time_window_rejects_invalid_payloads(payload: dict[str, int]) -> None:
    with pytest.raises(ValidationError):
        TimeWindow(**payload)
