"""List or cancel active generated schedules by id.

Dry-run mode prints a deterministic summary of currently active schedules.
Execute mode first writes a backup of the targeted schedule documents to
`runtime_logs/`, then sets `status: cancelled` on the requested ids.
"""

from __future__ import annotations

import argparse
import json
import os
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Cancel the schedules identified by --ids. Without this flag, only print the active-schedule summary.",
    )
    parser.add_argument(
        "--ids",
        default="",
        help="Comma-separated schedule ids to cancel when used with --execute.",
    )
    return parser.parse_args()


def load_environment() -> None:
    env_path = BACKEND_DIR / ".env"
    if env_path.exists():
        load_dotenv(env_path)
    if not os.getenv("FIREBASE_PROJECT_ID"):
        raise RuntimeError("Missing FIREBASE_PROJECT_ID in backend/.env or process environment.")


def as_utc(value: datetime | str | None) -> datetime | None:
    if value is None:
        return None
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
    if isinstance(value, dict):
        return {str(key): serialize(item) for key, item in value.items()}
    if isinstance(value, list):
        return [serialize(item) for item in value]
    return value


def parse_ids(raw_value: str) -> list[str]:
    ids = [item.strip() for item in raw_value.split(",") if item.strip()]
    return sorted(dict.fromkeys(ids))


def active_schedule_summary(row: dict[str, Any]) -> dict[str, Any]:
    assignments = row.get("assignments") or []
    return {
        "id": str(row["id"]),
        "generated_at": serialize(as_utc(row.get("generated_at"))),
        "assignment_count": len(assignments),
        "assigned_slot_count": sum(1 for assignment in assignments if assignment.get("assigned_agent_ids")),
        "status": str(row.get("status") or ""),
    }


def sort_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    def key(row: dict[str, Any]) -> tuple[str, str]:
        generated_at = serialize(as_utc(row.get("generated_at"))) or ""
        return (generated_at, str(row["id"]))

    return sorted(rows, key=key)


def backup_rows(rows: list[dict[str, Any]]) -> Path:
    RUNTIME_LOGS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    backup_path = RUNTIME_LOGS_DIR / f"generated-schedules-cancel-backup-{timestamp}.json"
    payload = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "firebase_project_id": os.getenv("FIREBASE_PROJECT_ID"),
        "schedule_count": len(rows),
        "schedules": rows,
    }
    backup_path.write_text(json.dumps(serialize(payload), indent=2, ensure_ascii=True), encoding="utf-8")
    return backup_path


def main() -> None:
    args = parse_args()
    target_ids = parse_ids(args.ids)

    if args.execute and not target_ids:
        raise SystemExit("--execute requires --ids <id,id>")
    if not args.execute and target_ids:
        raise SystemExit("--ids is only supported together with --execute")

    load_environment()
    initialize_firebase()
    db = get_firestore_client()
    collection = db.collection("generated_schedules")

    active_rows = []
    for snapshot in collection.where("status", "==", "active").stream():
        active_rows.append({"id": snapshot.id, **(snapshot.to_dict() or {})})
    active_rows = sort_rows(active_rows)

    summary = {
        "firebase_project_id": os.getenv("FIREBASE_PROJECT_ID"),
        "active_schedule_count": len(active_rows),
        "active_schedules": [active_schedule_summary(row) for row in active_rows],
        "dry_run": not args.execute,
    }
    print(json.dumps(summary, indent=2, ensure_ascii=True, sort_keys=True))

    if not args.execute:
        print("Run again with --execute --ids <id,id> to cancel specific active schedules.")
        return

    active_by_id = {str(row["id"]): row for row in active_rows}
    missing_ids = [schedule_id for schedule_id in target_ids if schedule_id not in active_by_id]
    if missing_ids:
        raise SystemExit(f"These schedule ids are not currently active: {', '.join(missing_ids)}")

    target_rows = [active_by_id[schedule_id] for schedule_id in target_ids]
    backup_path = backup_rows(target_rows)

    cancelled_count = 0
    now = datetime.now(timezone.utc)
    for schedule_id in target_ids:
        collection.document(schedule_id).update({"status": "cancelled", "updated_at": now})
        cancelled_count += 1

    result = {
        "backup_path": str(backup_path),
        "cancelled_count": cancelled_count,
        "cancelled_ids": target_ids,
        "execute": True,
    }
    print(json.dumps(result, indent=2, ensure_ascii=True, sort_keys=True))


if __name__ == "__main__":
    main()
