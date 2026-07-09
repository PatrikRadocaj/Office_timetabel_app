"""Populate current-week demand forecasts with realistic IDnow-inspired needs.

The generated documents use the compact daily-grid storage model: one Firestore
document per office/date/interval, with per-skill quantity arrays inside it.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
from datetime import date, datetime, timedelta, timezone
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
from app.models.demand import DailyDemandForecastCreate  # noqa: E402


INTERVAL_MINUTES = 30
SLOTS_PER_DAY = (24 * 60) // INTERVAL_MINUTES

OFFICE_PROFILES: dict[str, dict[str, int]] = {
    "idnow_munich_hq": {
        "idnow_doc_verification": 9,
        "idnow_videoident": 8,
        "idnow_biometric_liveness": 5,
        "idnow_data_verification": 4,
        "idnow_german_support": 5,
        "idnow_fraud_review": 3,
        "idnow_aml_kyc": 3,
        "idnow_qes": 2,
        "idnow_ident_center_night": 3,
    },
    "idnow_berlin_ident_center": {
        "idnow_doc_verification": 7,
        "idnow_videoident": 7,
        "idnow_biometric_liveness": 4,
        "idnow_data_verification": 3,
        "idnow_german_support": 4,
        "idnow_fraud_review": 2,
        "idnow_ident_center_night": 3,
    },
    "idnow_duesseldorf_operations": {
        "idnow_aml_kyc": 5,
        "idnow_fraud_review": 4,
        "idnow_trust_services": 4,
        "idnow_data_verification": 3,
        "idnow_german_support": 3,
        "idnow_qes": 3,
        "idnow_doc_verification": 3,
    },
    "idnow_london_uk_hub": {
        "idnow_english_support": 5,
        "idnow_fintech_onboarding": 5,
        "idnow_sdk_support": 4,
        "idnow_doc_verification": 4,
        "idnow_data_verification": 3,
        "idnow_biometric_liveness": 2,
    },
    "idnow_rennes_fr_hub": {
        "idnow_french_support": 5,
        "idnow_eid_schemes": 4,
        "idnow_eudi_wallet": 4,
        "idnow_trust_services": 3,
        "idnow_data_verification": 3,
        "idnow_doc_verification": 3,
    },
}

SKILL_PRIORITIES = {
    "idnow_fraud_review": 5,
    "idnow_aml_kyc": 5,
    "idnow_biometric_liveness": 4,
    "idnow_doc_verification": 4,
    "idnow_videoident": 4,
    "idnow_eid_schemes": 4,
    "idnow_eudi_wallet": 4,
    "idnow_trust_services": 4,
    "idnow_qes": 4,
    "idnow_sdk_support": 4,
    "idnow_fintech_onboarding": 4,
    "idnow_ident_center_night": 4,
    "idnow_data_verification": 3,
    "idnow_german_support": 3,
    "idnow_english_support": 3,
    "idnow_french_support": 3,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--week-containing",
        default="2026-07-08",
        help="ISO date inside the target week. Defaults to the current project date, 2026-07-08.",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Write demand forecasts. Without this flag the script prints a dry-run summary.",
    )
    return parser.parse_args()


def load_environment() -> None:
    env_path = BACKEND_DIR / ".env"
    if env_path.exists():
        load_dotenv(env_path)
    if not os.getenv("FIREBASE_PROJECT_ID"):
        raise RuntimeError("Missing FIREBASE_PROJECT_ID in backend/.env or process environment.")


def week_dates(week_containing: str) -> list[date]:
    anchor = date.fromisoformat(week_containing)
    monday = anchor - timedelta(days=anchor.weekday())
    return [monday + timedelta(days=offset) for offset in range(7)]


def day_factor(day: date) -> float:
    # Monday=0, Sunday=6. Identity queues are busiest Monday/Wednesday,
    # taper on Friday, and remain staffed but lower on weekends.
    return {
        0: 1.10,
        1: 1.00,
        2: 1.05,
        3: 1.00,
        4: 0.92,
        5: 0.58,
        6: 0.46,
    }[day.weekday()]


def time_factor(hour: float, skill_id: str, is_weekend: bool) -> float:
    if skill_id == "idnow_ident_center_night":
        if 0 <= hour < 8:
            return 1.00 if not is_weekend else 0.70
        if 20 <= hour < 24:
            return 0.85 if not is_weekend else 0.60
        if 18 <= hour < 20:
            return 0.35
        return 0.0

    if skill_id in {"idnow_sdk_support", "idnow_fintech_onboarding", "idnow_qes", "idnow_trust_services"}:
        if is_weekend:
            if 10 <= hour < 16:
                return 0.30
            return 0.0
        if 8 <= hour < 10:
            return 0.65
        if 10 <= hour < 13:
            return 1.00
        if 13 <= hour < 18:
            return 0.85
        return 0.08

    if skill_id in {"idnow_fraud_review", "idnow_aml_kyc"}:
        if 0 <= hour < 8:
            return 0.15
        if 8 <= hour < 10:
            return 0.70
        if 10 <= hour < 18:
            return 1.00
        if 18 <= hour < 22:
            return 0.45
        return 0.20

    if 0 <= hour < 8:
        return 0.24
    if 8 <= hour < 10:
        return 0.68
    if 10 <= hour < 12:
        return 1.00
    if 12 <= hour < 14:
        return 0.88
    if 14 <= hour < 18:
        return 1.06
    if 18 <= hour < 20:
        return 0.78
    return 0.45


def deterministic_variation(day: date, slot_index: int, skill_id: str, office_id: str) -> float:
    key = f"{day.isoformat()}|{slot_index}|{skill_id}|{office_id}".encode("utf-8")
    raw = hashlib.sha256(key).digest()[0] % 7
    return 0.88 + (raw * 0.04)


def quantity_for_slot(office_id: str, skill_id: str, base: int, target_day: date, slot_index: int) -> int:
    hour = slot_index / 2
    is_weekend = target_day.weekday() >= 5
    factor = day_factor(target_day) * time_factor(hour, skill_id, is_weekend)
    if factor <= 0:
        return 0

    varied = base * factor * deterministic_variation(target_day, slot_index, skill_id, office_id)
    qty = int(math.ceil(varied))

    # Keep critical queues minimally staffed overnight.
    if qty == 0 and skill_id in {"idnow_doc_verification", "idnow_videoident", "idnow_ident_center_night"}:
        qty = 1
    return max(0, qty)


def build_daily_payload(office_id: str, target_day: date) -> DailyDemandForecastCreate:
    skill_demands = []
    for skill_id, base in OFFICE_PROFILES[office_id].items():
        quantities = [
            quantity_for_slot(office_id, skill_id, base, target_day, slot_index)
            for slot_index in range(SLOTS_PER_DAY)
        ]
        if sum(quantities) <= 0:
            continue
        skill_demands.append(
            {
                "skill_id": skill_id,
                "priority": SKILL_PRIORITIES.get(skill_id, 3),
                "quantities": quantities,
            }
        )

    return DailyDemandForecastCreate(
        office_id=office_id,
        date=target_day,
        interval_minutes=INTERVAL_MINUTES,
        replace_existing_day=True,
        skill_demands=skill_demands,
    )


def serialize(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): serialize(item) for key, item in value.items()}
    if isinstance(value, list):
        return [serialize(item) for item in value]
    return value


def backup_demand_collection(db, week: list[date]) -> Path:
    RUNTIME_LOGS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    backup_path = RUNTIME_LOGS_DIR / f"firestore-demand-before-week-seed-{timestamp}.json"
    target_dates = {day.isoformat() for day in week}
    rows = []
    for snapshot in db.collection("demand_forecasts").stream():
        data = snapshot.to_dict()
        if data.get("forecast_date") in target_dates:
            rows.append({"id": snapshot.id, **data})

    payload = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "firebase_project_id": os.getenv("FIREBASE_PROJECT_ID"),
        "week_start": week[0].isoformat(),
        "week_end": week[-1].isoformat(),
        "rows": serialize(rows),
    }
    backup_path.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")
    return backup_path


def validate_seed_prerequisites(db) -> None:
    office_ids = {snapshot.id for snapshot in db.collection("offices").stream()}
    skill_ids = {snapshot.id for snapshot in db.collection("skills").stream()}

    missing_offices = sorted(set(OFFICE_PROFILES) - office_ids)
    missing_skills = sorted({skill_id for profile in OFFICE_PROFILES.values() for skill_id in profile} - skill_ids)

    if missing_offices:
        raise RuntimeError(f"Missing offices: {', '.join(missing_offices)}")
    if missing_skills:
        raise RuntimeError(f"Missing skills: {', '.join(missing_skills)}")


def summarize_payloads(payloads: list[DailyDemandForecastCreate]) -> dict[str, Any]:
    totals_by_date: dict[str, int] = {}
    totals_by_office: dict[str, int] = {}
    totals_by_skill: dict[str, int] = {}
    represented_nonzero_slots = 0

    for payload in payloads:
        date_key = payload.date.isoformat()
        office_total = 0
        for skill_demand in payload.skill_demands:
            skill_total = sum(skill_demand.quantities)
            office_total += skill_total
            represented_nonzero_slots += sum(1 for qty in skill_demand.quantities if qty > 0)
            totals_by_skill[skill_demand.skill_id] = totals_by_skill.get(skill_demand.skill_id, 0) + skill_total
        totals_by_date[date_key] = totals_by_date.get(date_key, 0) + office_total
        totals_by_office[payload.office_id] = totals_by_office.get(payload.office_id, 0) + office_total

    return {
        "daily_payloads": len(payloads),
        "expected_firestore_documents": len(payloads),
        "represented_nonzero_slots": represented_nonzero_slots,
        "total_required_agent_slots": sum(totals_by_date.values()),
        "totals_by_date": totals_by_date,
        "totals_by_office": totals_by_office,
        "totals_by_skill": dict(sorted(totals_by_skill.items())),
    }


def verify_week_counts(db, week: list[date]) -> dict[str, Any]:
    target_dates = {day.isoformat() for day in week}
    documents = [
        snapshot.to_dict()
        for snapshot in db.collection("demand_forecasts").stream()
        if snapshot.to_dict().get("forecast_date") in target_dates
    ]

    by_date: dict[str, int] = {}
    by_office: dict[str, int] = {}
    represented_nonzero_slots = 0
    for document in documents:
        by_date[document["forecast_date"]] = by_date.get(document["forecast_date"], 0) + 1
        by_office[document["office_id"]] = by_office.get(document["office_id"], 0) + 1
        if isinstance(document.get("skill_demands"), list):
            represented_nonzero_slots += sum(
                1
                for skill_demand in document["skill_demands"]
                for qty in skill_demand.get("quantities", [])
                if int(qty) > 0
            )
        else:
            represented_nonzero_slots += 1

    return {
        "verified_documents": len(documents),
        "represented_nonzero_slots": represented_nonzero_slots,
        "documents_by_date": by_date,
        "documents_by_office": by_office,
    }


def delete_week_rows(db, week: list[date], batch_size: int = 400) -> int:
    target_dates = {day.isoformat() for day in week}
    refs_to_delete = []
    for snapshot in db.collection("demand_forecasts").stream():
        if snapshot.to_dict().get("forecast_date") in target_dates:
            refs_to_delete.append(snapshot.reference)

    deleted = 0
    for start in range(0, len(refs_to_delete), batch_size):
        batch = db.batch()
        for ref in refs_to_delete[start:start + batch_size]:
            batch.delete(ref)
            deleted += 1
        batch.commit()
    return deleted


def build_compact_daily_documents(payloads: list[DailyDemandForecastCreate]) -> list[dict[str, Any]]:
    now = datetime.now(timezone.utc)
    records: list[dict[str, Any]] = []

    for payload in payloads:
        forecast_batch_id = f"daily_{payload.office_id}_{payload.date.isoformat()}_{payload.interval_minutes}_idnow_week_seed"
        records.append(
            {
                "id": f"daily_{payload.date.isoformat()}_{payload.office_id}_{payload.interval_minutes}",
                "office_id": payload.office_id,
                "forecast_date": payload.date.isoformat(),
                "interval_minutes": payload.interval_minutes,
                "entry_mode": "daily_grid",
                "storage_model": "daily_document_v1",
                "forecast_batch_id": forecast_batch_id,
                "skill_demands": [
                    {
                        "skill_id": skill_demand.skill_id,
                        "priority": int(skill_demand.priority),
                        "quantities": [int(qty) for qty in skill_demand.quantities],
                    }
                    for skill_demand in sorted(payload.skill_demands, key=lambda item: item.skill_id)
                ],
                "created_at": now,
                "updated_at": now,
            }
        )
    return records


def write_records(db, records: list[dict[str, Any]], batch_size: int = 400) -> int:
    written = 0
    collection = db.collection("demand_forecasts")
    for start in range(0, len(records), batch_size):
        batch = db.batch()
        for record in records[start:start + batch_size]:
            doc_id = record["id"]
            payload = {key: value for key, value in record.items() if key != "id"}
            batch.set(collection.document(doc_id), payload)
            written += 1
        batch.commit()
    return written


def main() -> None:
    args = parse_args()
    load_environment()
    initialize_firebase()
    db = get_firestore_client()
    validate_seed_prerequisites(db)

    week = week_dates(args.week_containing)
    payloads = [
        build_daily_payload(office_id, target_day)
        for target_day in week
        for office_id in OFFICE_PROFILES
    ]
    summary = summarize_payloads(payloads)

    print(f"firebase_project_id={os.getenv('FIREBASE_PROJECT_ID')}")
    print(f"week_start={week[0].isoformat()}")
    print(f"week_end={week[-1].isoformat()}")
    print(json.dumps(summary, indent=2, sort_keys=True))

    if not args.execute:
        print("dry_run=true")
        print("Run again with --execute to replace the week with compact daily-grid documents.")
        return

    backup_path = backup_demand_collection(db, week)
    deleted_rows = delete_week_rows(db, week)
    records = build_compact_daily_documents(payloads)
    written_rows = write_records(db, records)

    verification = verify_week_counts(db, week)
    print(f"backup_path={backup_path}")
    print(
        json.dumps(
            {
                "deleted_current_week_documents": deleted_rows,
                "written_documents": written_rows,
                "verification": verification,
            },
            indent=2,
            sort_keys=True,
        )
    )
    print("current_week_idnow_demand_seed_complete=true")


if __name__ == "__main__":
    main()
