"""Migrate legacy per-slot demand docs to compact daily demand docs.

Legacy demand documents store one Firestore document per office/skill/time slot.
Compact documents store one document per office/date/interval with per-skill
quantity arrays. This script preserves existing compact docs, converts legacy
groups only when no compact doc exists for that office/date/interval, backs up
the legacy docs, and deletes the legacy docs after compact writes succeed.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict
from datetime import date, datetime, time, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = ROOT.parent
BACKEND_DIR = ROOT / "backend"
RUNTIME_LOGS_DIR = WORKSPACE_ROOT / "runtime_logs"

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.firebase import get_firestore_client, initialize_firebase  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Write compact docs and delete legacy docs. Without this flag, only print the plan.",
    )
    return parser.parse_args()


def load_environment() -> None:
    env_path = BACKEND_DIR / ".env"
    if env_path.exists():
        load_dotenv(env_path)
    if not os.getenv("FIREBASE_PROJECT_ID"):
        raise RuntimeError("Missing FIREBASE_PROJECT_ID in backend/.env or process environment.")


def as_utc(value: datetime | str) -> datetime:
    if isinstance(value, str):
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    else:
        dt = value
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


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


def is_compact_demand_doc(row: dict[str, Any]) -> bool:
    return row.get("storage_model") == "daily_document_v1" or isinstance(row.get("skill_demands"), list)


def is_legacy_slot_doc(row: dict[str, Any]) -> bool:
    return all(key in row for key in ("office_id", "skill_id", "slot_start", "slot_end", "required_agents"))


def load_office_timezones(db) -> dict[str, ZoneInfo | timezone]:
    zones: dict[str, ZoneInfo | timezone] = {}
    for snapshot in db.collection("offices").stream():
        data = snapshot.to_dict() or {}
        timezone_name = str(data.get("timezone") or "UTC")
        try:
            zones[snapshot.id] = ZoneInfo(timezone_name)
        except Exception:
            zones[snapshot.id] = timezone.utc
    return zones


def compact_doc_id(office_id: str, forecast_date: str, interval_minutes: int) -> str:
    return f"daily_{forecast_date}_{office_id}_{interval_minutes}"


def slot_interval_minutes(row: dict[str, Any]) -> int:
    if row.get("interval_minutes"):
        return int(row["interval_minutes"])
    slot_start = as_utc(row["slot_start"])
    slot_end = as_utc(row["slot_end"])
    return int((slot_end - slot_start).total_seconds() // 60)


def slot_index_for_row(row: dict[str, Any], office_tz: ZoneInfo | timezone, interval_minutes: int) -> int:
    if row.get("time_block"):
        hour, minute = str(row["time_block"]).split(":", 1)
        minute_of_day = int(hour) * 60 + int(minute)
    else:
        slot_start_local = as_utc(row["slot_start"]).astimezone(office_tz)
        minute_of_day = slot_start_local.hour * 60 + slot_start_local.minute
    return minute_of_day // interval_minutes


def forecast_date_for_row(row: dict[str, Any], office_tz: ZoneInfo | timezone) -> str:
    if row.get("forecast_date"):
        return str(row["forecast_date"])
    return as_utc(row["slot_start"]).astimezone(office_tz).date().isoformat()


def build_compact_docs(
    legacy_rows: list[dict[str, Any]],
    existing_compact_keys: set[tuple[str, str, int]],
    office_timezones: dict[str, ZoneInfo | timezone],
) -> tuple[list[dict[str, Any]], int]:
    grouped: dict[tuple[str, str, int], dict[str, Any]] = {}
    skipped_rows = 0

    for row in legacy_rows:
        office_id = str(row["office_id"])
        office_tz = office_timezones.get(office_id, timezone.utc)
        interval_minutes = slot_interval_minutes(row)
        if interval_minutes not in {30, 60}:
            skipped_rows += 1
            continue

        forecast_date = forecast_date_for_row(row, office_tz)
        group_key = (office_id, forecast_date, interval_minutes)
        if group_key in existing_compact_keys:
            skipped_rows += 1
            continue

        slot_count = (24 * 60) // interval_minutes
        slot_index = slot_index_for_row(row, office_tz, interval_minutes)
        if slot_index < 0 or slot_index >= slot_count:
            skipped_rows += 1
            continue

        group = grouped.setdefault(
            group_key,
            {
                "id": compact_doc_id(office_id, forecast_date, interval_minutes),
                "office_id": office_id,
                "forecast_date": forecast_date,
                "interval_minutes": interval_minutes,
                "entry_mode": "daily_grid",
                "storage_model": "daily_document_v1",
                "forecast_batch_id": f"migrated_{office_id}_{forecast_date}_{interval_minutes}",
                "skill_demands": {},
            },
        )

        skill_id = str(row["skill_id"])
        skill_entry = group["skill_demands"].setdefault(
            skill_id,
            {
                "skill_id": skill_id,
                "priority": int(row.get("priority", 3) or 3),
                "quantities": [0] * slot_count,
            },
        )
        skill_entry["priority"] = max(int(skill_entry["priority"]), int(row.get("priority", 3) or 3))
        skill_entry["quantities"][slot_index] += int(row["required_agents"])

    compact_docs: list[dict[str, Any]] = []
    for group in grouped.values():
        skill_demands = list(group["skill_demands"].values())
        compact_docs.append(
            {
                **{key: value for key, value in group.items() if key != "skill_demands"},
                "skill_demands": sorted(skill_demands, key=lambda entry: entry["skill_id"]),
            }
        )
    return sorted(compact_docs, key=lambda row: row["id"]), skipped_rows


def backup_legacy_rows(legacy_rows: list[dict[str, Any]], compact_docs: list[dict[str, Any]], skipped_rows: int) -> Path:
    RUNTIME_LOGS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    backup_path = RUNTIME_LOGS_DIR / f"firestore-demand-legacy-slot-backup-{timestamp}.json"
    payload = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "firebase_project_id": os.getenv("FIREBASE_PROJECT_ID"),
        "legacy_row_count": len(legacy_rows),
        "compact_document_count_to_write": len(compact_docs),
        "legacy_rows_skipped_for_compaction": skipped_rows,
        "legacy_rows": legacy_rows,
    }
    backup_path.write_text(json.dumps(serialize(payload), indent=2, ensure_ascii=True), encoding="utf-8")
    return backup_path


def write_compact_docs(db, compact_docs: list[dict[str, Any]], batch_size: int = 400) -> int:
    collection = db.collection("demand_forecasts")
    written = 0
    now = datetime.now(timezone.utc)
    for start in range(0, len(compact_docs), batch_size):
        batch = db.batch()
        for compact_doc in compact_docs[start:start + batch_size]:
            doc_id = compact_doc["id"]
            payload = {key: value for key, value in compact_doc.items() if key != "id"}
            payload.setdefault("created_at", now)
            payload["updated_at"] = now
            batch.set(collection.document(doc_id), payload)
            written += 1
        batch.commit()
    return written


def delete_legacy_docs(db, legacy_rows: list[dict[str, Any]], batch_size: int = 400) -> int:
    collection = db.collection("demand_forecasts")
    deleted = 0
    for start in range(0, len(legacy_rows), batch_size):
        batch = db.batch()
        for legacy_row in legacy_rows[start:start + batch_size]:
            batch.delete(collection.document(legacy_row["id"]))
            deleted += 1
        batch.commit()
    return deleted


def main() -> None:
    args = parse_args()
    load_environment()
    initialize_firebase()
    db = get_firestore_client()

    office_timezones = load_office_timezones(db)
    legacy_rows: list[dict[str, Any]] = []
    existing_compact_keys: set[tuple[str, str, int]] = set()

    for snapshot in db.collection("demand_forecasts").stream():
        row = {"id": snapshot.id, **(snapshot.to_dict() or {})}
        if is_compact_demand_doc(row):
            existing_compact_keys.add((str(row["office_id"]), str(row["forecast_date"]), int(row["interval_minutes"])))
        elif is_legacy_slot_doc(row):
            legacy_rows.append(row)

    compact_docs, skipped_rows = build_compact_docs(legacy_rows, existing_compact_keys, office_timezones)
    summary = {
        "firebase_project_id": os.getenv("FIREBASE_PROJECT_ID"),
        "legacy_slot_documents_found": len(legacy_rows),
        "compact_documents_to_write": len(compact_docs),
        "legacy_rows_skipped_for_compaction": skipped_rows,
        "existing_compact_groups": len(existing_compact_keys),
    }
    print(json.dumps(summary, indent=2, sort_keys=True))

    if not args.execute:
        print("dry_run=true")
        print("Run again with --execute to write compact docs and delete legacy slot docs.")
        return

    backup_path = backup_legacy_rows(legacy_rows, compact_docs, skipped_rows)
    written = write_compact_docs(db, compact_docs)
    deleted = delete_legacy_docs(db, legacy_rows)
    print(f"backup_path={backup_path}")
    print(f"compact_documents_written={written}")
    print(f"legacy_slot_documents_deleted={deleted}")
    print("demand_legacy_slot_migration_complete=true")


if __name__ == "__main__":
    main()
