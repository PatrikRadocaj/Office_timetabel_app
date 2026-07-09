"""Reset Firestore demo data and seed an IDnow-inspired operating model.

This script preserves the `users` collection, backs up all deleted non-user
collections to `runtime_logs`, deletes every other top-level collection, and
then seeds offices, skills, and 150 fictional agents.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = ROOT.parent
BACKEND_DIR = ROOT / "backend"
RUNTIME_LOGS_DIR = WORKSPACE_ROOT / "runtime_logs"

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.firebase import get_firestore_client, initialize_firebase  # noqa: E402
from app.models.common import utcnow  # noqa: E402


RNG = random.Random(20260708)


OFFICES: list[dict[str, Any]] = [
    {
        "id": "idnow_munich_hq",
        "name": "IDnow Munich HQ",
        "timezone": "Europe/Berlin",
        "max_capacity": 180,
        "address": "Auenstrasse 100, 80469 Munich, Germany",
    },
    {
        "id": "idnow_berlin_ident_center",
        "name": "IDnow Berlin Ident-Center",
        "timezone": "Europe/Berlin",
        "max_capacity": 120,
        "address": "Berlin, Germany",
    },
    {
        "id": "idnow_duesseldorf_operations",
        "name": "IDnow Duesseldorf Operations",
        "timezone": "Europe/Berlin",
        "max_capacity": 90,
        "address": "Duesseldorf, Germany",
    },
    {
        "id": "idnow_london_uk_hub",
        "name": "IDnow London UK Hub",
        "timezone": "Europe/London",
        "max_capacity": 60,
        "address": "London, United Kingdom",
    },
    {
        "id": "idnow_rennes_fr_hub",
        "name": "IDnow Rennes FR Hub",
        "timezone": "Europe/Paris",
        "max_capacity": 90,
        "address": "Rennes, France",
    },
]


SKILLS: list[dict[str, Any]] = [
    {
        "id": "idnow_doc_verification",
        "name": "Document Verification",
        "description": "Identity document capture, inspection, and validity checks.",
        "min_proficiency": 3,
    },
    {
        "id": "idnow_biometric_liveness",
        "name": "Biometric Liveness",
        "description": "Face match, liveness, and biometric verification review.",
        "min_proficiency": 4,
    },
    {
        "id": "idnow_eid_schemes",
        "name": "eID Schemes",
        "description": "Electronic identity scheme onboarding and support.",
        "min_proficiency": 4,
    },
    {
        "id": "idnow_eudi_wallet",
        "name": "EUDI Wallet",
        "description": "European digital identity wallet support workflows.",
        "min_proficiency": 4,
    },
    {
        "id": "idnow_data_verification",
        "name": "Data Verification",
        "description": "Customer data cross-checking and quality control.",
        "min_proficiency": 3,
    },
    {
        "id": "idnow_trust_services",
        "name": "Trust Services",
        "description": "Qualified trust-service and assurance process support.",
        "min_proficiency": 4,
    },
    {
        "id": "idnow_videoident",
        "name": "VideoIdent Operations",
        "description": "Human-assisted identity verification sessions.",
        "min_proficiency": 3,
    },
    {
        "id": "idnow_fraud_review",
        "name": "Fraud Review",
        "description": "Document fraud, spoofing, and suspicious case escalation.",
        "min_proficiency": 5,
    },
    {
        "id": "idnow_aml_kyc",
        "name": "AML/KYC Escalation",
        "description": "Regulated onboarding, KYC, and compliance escalation handling.",
        "min_proficiency": 4,
    },
    {
        "id": "idnow_qes",
        "name": "Qualified E-Signature",
        "description": "Qualified electronic signature support and validation.",
        "min_proficiency": 4,
    },
    {
        "id": "idnow_sdk_support",
        "name": "SDK Integration Support",
        "description": "Customer integration, mobile SDK, and API troubleshooting.",
        "min_proficiency": 4,
    },
    {
        "id": "idnow_ident_center_night",
        "name": "Ident-Center Night Service",
        "description": "Night-shift coverage for identity verification queues.",
        "min_proficiency": 3,
    },
    {
        "id": "idnow_german_support",
        "name": "German Customer Support",
        "description": "German-language applicant and client support.",
        "min_proficiency": 3,
    },
    {
        "id": "idnow_english_support",
        "name": "English Customer Support",
        "description": "English-language applicant and client support.",
        "min_proficiency": 3,
    },
    {
        "id": "idnow_french_support",
        "name": "French Customer Support",
        "description": "French-language applicant and client support.",
        "min_proficiency": 3,
    },
    {
        "id": "idnow_fintech_onboarding",
        "name": "Fintech Onboarding",
        "description": "Banking, fintech, and regulated onboarding workflows.",
        "min_proficiency": 4,
    },
]


FIRST_NAMES = [
    "Anna",
    "Ben",
    "Clara",
    "Daniel",
    "Eva",
    "Felix",
    "Greta",
    "Hannah",
    "Jonas",
    "Laura",
    "Leon",
    "Mara",
    "Nico",
    "Paula",
    "Simon",
    "Sofia",
    "Tobias",
    "Lena",
    "Julian",
    "Mia",
    "Noah",
    "Emma",
    "Finn",
    "Lea",
    "Max",
    "Marie",
    "Paul",
    "Sarah",
    "Tom",
    "Lisa",
]

LAST_NAMES = [
    "Weber",
    "Schneider",
    "Fischer",
    "Meyer",
    "Wagner",
    "Becker",
    "Hoffmann",
    "Schulz",
    "Koch",
    "Bauer",
    "Richter",
    "Klein",
    "Wolf",
    "Schroeder",
    "Neumann",
    "Schwarz",
    "Zimmermann",
    "Braun",
    "Krueger",
    "Hartmann",
    "Lange",
    "Werner",
    "Schmitt",
    "Krause",
    "Lehmann",
    "Huber",
    "Keller",
    "Berger",
    "Roth",
    "Frank",
]

OFFICE_COUNTS = {
    "idnow_munich_hq": 55,
    "idnow_berlin_ident_center": 35,
    "idnow_duesseldorf_operations": 25,
    "idnow_london_uk_hub": 15,
    "idnow_rennes_fr_hub": 20,
}

OFFICE_LANGUAGE_SKILL = {
    "idnow_munich_hq": "idnow_german_support",
    "idnow_berlin_ident_center": "idnow_german_support",
    "idnow_duesseldorf_operations": "idnow_german_support",
    "idnow_london_uk_hub": "idnow_english_support",
    "idnow_rennes_fr_hub": "idnow_french_support",
}

ROLE_SKILL_POOLS = [
    ["idnow_videoident", "idnow_doc_verification", "idnow_data_verification"],
    ["idnow_doc_verification", "idnow_biometric_liveness", "idnow_fraud_review"],
    ["idnow_eid_schemes", "idnow_eudi_wallet", "idnow_data_verification"],
    ["idnow_trust_services", "idnow_qes", "idnow_aml_kyc"],
    ["idnow_sdk_support", "idnow_fintech_onboarding", "idnow_english_support"],
    ["idnow_ident_center_night", "idnow_doc_verification", "idnow_videoident"],
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually delete and seed Firestore. Without this flag the script prints a plan only.",
    )
    return parser.parse_args()


def load_environment() -> None:
    env_path = BACKEND_DIR / ".env"
    if env_path.exists():
        load_dotenv(env_path)
    if not os.getenv("FIREBASE_PROJECT_ID"):
        raise RuntimeError("Missing FIREBASE_PROJECT_ID in backend/.env or process environment.")


def serialize(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat()
    if isinstance(value, dict):
        return {str(key): serialize(item) for key, item in value.items()}
    if isinstance(value, list):
        return [serialize(item) for item in value]
    return value


def collection_docs(db, collection_name: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for snapshot in db.collection(collection_name).stream():
        rows.append({"id": snapshot.id, **snapshot.to_dict()})
    return rows


def backup_non_user_collections(db, collections_to_delete: list[str], user_count: int) -> Path:
    RUNTIME_LOGS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    backup_path = RUNTIME_LOGS_DIR / f"firestore-idnow-reset-backup-{timestamp}.json"

    backup = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "firebase_project_id": os.getenv("FIREBASE_PROJECT_ID"),
        "preserved_collection": "users",
        "preserved_users_count": user_count,
        "deleted_collections": {},
    }

    for collection_name in collections_to_delete:
        backup["deleted_collections"][collection_name] = serialize(collection_docs(db, collection_name))

    backup_path.write_text(json.dumps(backup, indent=2, ensure_ascii=True), encoding="utf-8")
    return backup_path


def delete_collection(db, collection_name: str, batch_size: int = 400) -> int:
    deleted = 0
    collection_ref = db.collection(collection_name)

    while True:
        snapshots = list(collection_ref.limit(batch_size).stream())
        if not snapshots:
            break

        batch = db.batch()
        for snapshot in snapshots:
            batch.delete(snapshot.reference)
            deleted += 1
        batch.commit()

    return deleted


def make_availability(shift_preference: str) -> list[dict[str, int]]:
    if shift_preference == "day":
        return [{"day_of_week": day, "start_hour": 8, "end_hour": 18} for day in range(0, 5)]
    if shift_preference == "night":
        windows: list[dict[str, int]] = []
        for day in range(0, 7):
            windows.append({"day_of_week": day, "start_hour": 0, "end_hour": 8})
            windows.append({"day_of_week": day, "start_hour": 18, "end_hour": 24})
        return windows
    return []


def make_agent_name(index: int) -> tuple[str, str]:
    first = FIRST_NAMES[(index - 1) % len(FIRST_NAMES)]
    last = LAST_NAMES[((index - 1) // len(FIRST_NAMES) + index - 1) % len(LAST_NAMES)]
    return first, last


def build_agent_skills(index: int, office_id: str, shift_preference: str) -> list[dict[str, Any]]:
    base_pool = ROLE_SKILL_POOLS[(index - 1) % len(ROLE_SKILL_POOLS)]
    selected = list(dict.fromkeys([OFFICE_LANGUAGE_SKILL[office_id], *base_pool]))

    if shift_preference == "night" and "idnow_ident_center_night" not in selected:
        selected.append("idnow_ident_center_night")
    if index % 7 == 0 and "idnow_fraud_review" not in selected:
        selected.append("idnow_fraud_review")
    if index % 11 == 0 and "idnow_aml_kyc" not in selected:
        selected.append("idnow_aml_kyc")

    selected = selected[:4]
    skills = []
    for pos, skill_id in enumerate(selected):
        proficiency = 3 + ((index + pos) % 3)
        if skill_id in {"idnow_fraud_review", "idnow_biometric_liveness"}:
            proficiency = max(4, proficiency)
        skills.append({"skill_id": skill_id, "proficiency": min(5, proficiency)})
    return skills


def build_agents(existing_users: list[dict[str, Any]]) -> list[dict[str, Any]]:
    now = utcnow()
    agents: list[dict[str, Any]] = []
    index = 1

    for office_id, count in OFFICE_COUNTS.items():
        for _ in range(count):
            first, last = make_agent_name(index)
            shift_preference = ["day", "day", "any", "night", "any"][index % 5]
            weekly_hours = 32 if index % 10 == 0 else 36 if index % 6 == 0 else 40
            email = f"idnow.demo.agent{index:03d}@example.com"

            agents.append(
                {
                    "id": f"idnow_agent_{index:03d}",
                    "full_name": f"{first} {last}",
                    "email": email,
                    "office_id": office_id,
                    "weekly_max_hours": weekly_hours,
                    "min_rest_hours": 11 if shift_preference == "night" else 10,
                    "shift_preference": shift_preference,
                    "skills": build_agent_skills(index, office_id, shift_preference),
                    "availability": make_availability(shift_preference),
                    "is_active": True,
                    "created_at": now,
                    "updated_at": now,
                }
            )
            index += 1

    agent_users = [
        user for user in existing_users
        if str(user.get("role", "")).lower() == "agent" and str(user.get("email", "")).strip()
    ]
    for agent, user in zip(agents, agent_users):
        agent["user_id"] = user["id"]
        agent["email"] = str(user["email"]).strip()
        if str(user.get("full_name", "")).strip():
            agent["full_name"] = str(user["full_name"]).strip()

    RNG.shuffle(agents)
    return agents


def write_collection(db, collection_name: str, records: list[dict[str, Any]]) -> int:
    now = utcnow()
    written = 0

    for record in records:
        doc_id = record["id"]
        payload = {key: value for key, value in record.items() if key != "id"}
        payload.setdefault("created_at", now)
        payload["updated_at"] = now
        db.collection(collection_name).document(doc_id).set(payload)
        written += 1

    return written


def main() -> None:
    args = parse_args()
    load_environment()
    initialize_firebase()
    db = get_firestore_client()

    all_collections = sorted(collection.id for collection in db.collections())
    collections_to_delete = [name for name in all_collections if name != "users"]
    existing_users = collection_docs(db, "users") if "users" in all_collections else []

    print(f"firebase_project_id={os.getenv('FIREBASE_PROJECT_ID')}")
    print(f"users_preserved={len(existing_users)}")
    print(f"collections_to_delete={collections_to_delete}")
    print(f"offices_to_seed={len(OFFICES)}")
    print(f"skills_to_seed={len(SKILLS)}")
    print("agents_to_seed=150")

    if not args.execute:
        print("dry_run=true")
        print("Run again with --execute to apply changes.")
        return

    backup_path = backup_non_user_collections(db, collections_to_delete, len(existing_users))
    print(f"backup_path={backup_path}")

    deleted_counts: dict[str, int] = {}
    for collection_name in collections_to_delete:
        deleted_counts[collection_name] = delete_collection(db, collection_name)

    agents = build_agents(existing_users)
    written_counts = {
        "offices": write_collection(db, "offices", OFFICES),
        "skills": write_collection(db, "skills", SKILLS),
        "agents": write_collection(db, "agents", agents),
    }

    print(f"deleted_counts={json.dumps(deleted_counts, sort_keys=True)}")
    print(f"written_counts={json.dumps(written_counts, sort_keys=True)}")
    print("firestore_idnow_reset_complete=true")


if __name__ == "__main__":
    main()
