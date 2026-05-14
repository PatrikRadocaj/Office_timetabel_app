"""Populate Firestore with realistic demo data for offices, skills, agents, and demand forecasts."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "backend"

import sys

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.firebase import get_firestore_client, initialize_firebase  # noqa: E402
from app.models.common import utcnow  # noqa: E402


OFFICES: list[dict[str, Any]] = [
    {
        "id": "demo_office_zagreb_hq",
        "name": "Zagreb HQ",
        "timezone": "Europe/Zagreb",
        "max_capacity": 120,
        "address": "Savska cesta 1, Zagreb",
    },
    {
        "id": "demo_office_split",
        "name": "Split Branch",
        "timezone": "Europe/Zagreb",
        "max_capacity": 75,
        "address": "Riva 20, Split",
    },
    {
        "id": "demo_office_rijeka",
        "name": "Rijeka Satellite",
        "timezone": "Europe/Zagreb",
        "max_capacity": 55,
        "address": "Korzo 9, Rijeka",
    },
]


SKILLS: list[dict[str, Any]] = [
    {
        "id": "demo_skill_english_support",
        "name": "English Support",
        "description": "Inbound customer support in English.",
        "min_proficiency": 3,
    },
    {
        "id": "demo_skill_german_support",
        "name": "German Support",
        "description": "German language support queue.",
        "min_proficiency": 4,
    },
    {
        "id": "demo_skill_billing",
        "name": "Billing",
        "description": "Billing and invoice issue handling.",
        "min_proficiency": 2,
    },
    {
        "id": "demo_skill_tech_support",
        "name": "Technical Support",
        "description": "Technical troubleshooting and diagnostics.",
        "min_proficiency": 4,
    },
    {
        "id": "demo_skill_retention",
        "name": "Retention",
        "description": "Upsell/retention and cancellation prevention.",
        "min_proficiency": 3,
    },
]


AGENT_NAMES = [
    "Ana Kovac",
    "Marko Juric",
    "Iva Basic",
    "Luka Horvat",
    "Petra Marin",
    "Ivan Matic",
    "Sara Novak",
    "Filip Peric",
    "Maja Babic",
    "Karlo Knez",
    "Nina Rogic",
    "Toni Vukic",
    "Dora Pavic",
    "Matej Lovric",
    "Lea Simic",
    "Nikola Bozic",
    "Lucija Kovacevic",
    "Dino Vidic",
    "Tea Jaksic",
    "Bruno Jakovljevic",
    "Mia Bilic",
    "Tomislav Grgic",
    "Ena Santic",
    "Roko Debeljak",
]


SKILL_POOLS = [
    ["demo_skill_english_support", "demo_skill_billing"],
    ["demo_skill_english_support", "demo_skill_retention"],
    ["demo_skill_tech_support", "demo_skill_english_support"],
    ["demo_skill_german_support", "demo_skill_english_support"],
    ["demo_skill_tech_support", "demo_skill_billing"],
    ["demo_skill_retention", "demo_skill_billing"],
]


OFFICE_IDS = [office["id"] for office in OFFICES]
SHIFT_PREFERENCES = ["day", "night", "any"]


def ceil_to_next_half_hour(dt: datetime) -> datetime:
    dt = dt.replace(second=0, microsecond=0)
    if dt.minute in {0, 30}:
        return dt
    minute_delta = 30 - (dt.minute % 30)
    return dt + timedelta(minutes=minute_delta)


def make_availability(shift_preference: str) -> list[dict[str, int]]:
    if shift_preference == "any":
        return []

    windows: list[dict[str, int]] = []
    if shift_preference == "day":
        # Weekday daytime coverage.
        for day in range(0, 5):
            windows.append({"day_of_week": day, "start_hour": 8, "end_hour": 18})
    else:
        # Night-shift windows split into pre-midnight and after-midnight chunks.
        for day in range(0, 7):
            windows.append({"day_of_week": day, "start_hour": 0, "end_hour": 6})
            windows.append({"day_of_week": day, "start_hour": 18, "end_hour": 23})

    return windows


def build_agents() -> list[dict[str, Any]]:
    agents: list[dict[str, Any]] = []
    for idx, full_name in enumerate(AGENT_NAMES, start=1):
        office_id = OFFICE_IDS[(idx - 1) % len(OFFICE_IDS)]
        shift_preference = SHIFT_PREFERENCES[(idx - 1) % len(SHIFT_PREFERENCES)]
        pool = SKILL_POOLS[(idx - 1) % len(SKILL_POOLS)]

        skills = []
        for skill_pos, skill_id in enumerate(pool):
            skills.append(
                {
                    "skill_id": skill_id,
                    "proficiency": min(5, 3 + ((idx + skill_pos) % 3)),
                }
            )

        # Every 4th agent gets a third cross-skill to improve planner flexibility.
        if idx % 4 == 0:
            cross_skill = "demo_skill_tech_support" if "demo_skill_tech_support" not in pool else "demo_skill_billing"
            skills.append({"skill_id": cross_skill, "proficiency": 3})

        first_name = full_name.split(" ")[0].lower()
        last_name = full_name.split(" ")[1].lower()
        email = f"demo.{first_name}.{last_name}@example.com"

        agents.append(
            {
                "id": f"demo_agent_{idx:02d}",
                "full_name": full_name,
                "email": email,
                "office_id": office_id,
                "weekly_max_hours": 36 if idx % 5 == 0 else 40,
                "min_rest_hours": 10,
                "shift_preference": shift_preference,
                "skills": skills,
                "availability": make_availability(shift_preference),
                "is_active": True,
            }
        )

    return agents


def office_scale(office_id: str) -> float:
    if office_id == "demo_office_zagreb_hq":
        return 1.0
    if office_id == "demo_office_split":
        return 0.7
    return 0.5


def generate_demand_forecasts(slot_count: int = 96) -> list[dict[str, Any]]:
    tz = ZoneInfo("Europe/Zagreb")
    now_local = datetime.now(tz)
    start_local = ceil_to_next_half_hour(now_local)

    rows: list[dict[str, Any]] = []
    for slot_index in range(slot_count):
        slot_local = start_local + timedelta(minutes=30 * slot_index)
        slot_start_utc = slot_local.astimezone(timezone.utc)
        slot_end_utc = (slot_local + timedelta(minutes=30)).astimezone(timezone.utc)

        hour = slot_local.hour
        day_mode = 7 <= hour < 19

        for office in OFFICES:
            office_id = office["id"]
            scale = office_scale(office_id)

            if day_mode:
                english_required = max(1, round((5 * scale) + 2))
                billing_required = max(1, round((3 * scale) + 1))

                rows.append(
                    {
                        "id": f"demo_df_{slot_start_utc:%Y%m%dT%H%M}_{office_id}_english",
                        "office_id": office_id,
                        "skill_id": "demo_skill_english_support",
                        "slot_start": slot_start_utc,
                        "slot_end": slot_end_utc,
                        "required_agents": english_required,
                        "priority": 4,
                    }
                )
                rows.append(
                    {
                        "id": f"demo_df_{slot_start_utc:%Y%m%dT%H%M}_{office_id}_billing",
                        "office_id": office_id,
                        "skill_id": "demo_skill_billing",
                        "slot_start": slot_start_utc,
                        "slot_end": slot_end_utc,
                        "required_agents": billing_required,
                        "priority": 3,
                    }
                )

                if 10 <= hour < 18:
                    retention_required = max(1, round((2 * scale) + 1))
                    rows.append(
                        {
                            "id": f"demo_df_{slot_start_utc:%Y%m%dT%H%M}_{office_id}_retention",
                            "office_id": office_id,
                            "skill_id": "demo_skill_retention",
                            "slot_start": slot_start_utc,
                            "slot_end": slot_end_utc,
                            "required_agents": retention_required,
                            "priority": 2,
                        }
                    )
            else:
                tech_required = max(1, round((3 * scale) + 1))
                english_night_required = max(1, round((2 * scale) + 1))

                rows.append(
                    {
                        "id": f"demo_df_{slot_start_utc:%Y%m%dT%H%M}_{office_id}_tech",
                        "office_id": office_id,
                        "skill_id": "demo_skill_tech_support",
                        "slot_start": slot_start_utc,
                        "slot_end": slot_end_utc,
                        "required_agents": tech_required,
                        "priority": 5,
                    }
                )
                rows.append(
                    {
                        "id": f"demo_df_{slot_start_utc:%Y%m%dT%H%M}_{office_id}_english_night",
                        "office_id": office_id,
                        "skill_id": "demo_skill_english_support",
                        "slot_start": slot_start_utc,
                        "slot_end": slot_end_utc,
                        "required_agents": english_night_required,
                        "priority": 3,
                    }
                )

                if office_id == "demo_office_zagreb_hq" and 18 <= hour < 23:
                    rows.append(
                        {
                            "id": f"demo_df_{slot_start_utc:%Y%m%dT%H%M}_{office_id}_german",
                            "office_id": office_id,
                            "skill_id": "demo_skill_german_support",
                            "slot_start": slot_start_utc,
                            "slot_end": slot_end_utc,
                            "required_agents": 2,
                            "priority": 4,
                        }
                    )

    return rows


def upsert_collection(collection_name: str, records: list[dict[str, Any]]) -> int:
    db = get_firestore_client()
    now = utcnow()

    count = 0
    for record in records:
        doc_id = record["id"]
        payload = {k: v for k, v in record.items() if k != "id"}
        payload.setdefault("created_at", now)
        payload["updated_at"] = now
        db.collection(collection_name).document(doc_id).set(payload, merge=True)
        count += 1
    return count


def main() -> None:
    env_path = BACKEND_DIR / ".env"
    if env_path.exists():
        load_dotenv(env_path)

    initialize_firebase()

    agents = build_agents()
    demand = generate_demand_forecasts(slot_count=96)

    offices_written = upsert_collection("offices", OFFICES)
    skills_written = upsert_collection("skills", SKILLS)
    agents_written = upsert_collection("agents", agents)
    demand_written = upsert_collection("demand_forecasts", demand)

    print(f"offices_upserted={offices_written}")
    print(f"skills_upserted={skills_written}")
    print(f"agents_upserted={agents_written}")
    print(f"demand_forecasts_upserted={demand_written}")


if __name__ == "__main__":
    main()
