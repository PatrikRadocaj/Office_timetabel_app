"""Seed Firestore with demo offices, skills, users, agents, and demand forecasts."""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.firebase import get_firestore_client, initialize_firebase  # noqa: E402


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def parse_datetime(value: str) -> datetime:
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def load_json(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def normalize_payload(collection_name: str, payload: dict[str, Any]) -> dict[str, Any]:
    data = dict(payload)
    if collection_name == "demand_forecasts":
        data["slot_start"] = parse_datetime(data["slot_start"])
        data["slot_end"] = parse_datetime(data["slot_end"])
    data.setdefault("created_at", utcnow())
    data["updated_at"] = utcnow()
    return data


def upsert_collection(db, collection_name: str, records: list[dict[str, Any]]) -> None:
    for entry in records:
        doc_id = entry["id"]
        payload = {k: v for k, v in entry.items() if k != "id"}
        normalized = normalize_payload(collection_name, payload)
        db.collection(collection_name).document(doc_id).set(normalized, merge=True)


def main() -> None:
    env_path = BACKEND_DIR / ".env"
    if env_path.exists():
        load_dotenv(env_path)
    else:
        print(f"Warning: .env not found at {env_path}. Falling back to process env vars.")

    if not os.getenv("FIREBASE_PROJECT_ID"):
        raise RuntimeError("Missing FIREBASE_PROJECT_ID. Configure backend/.env first.")

    initialize_firebase()
    db = get_firestore_client()

    sample_dir = ROOT / "sample_data"
    collections = [
        "offices",
        "skills",
        "users",
        "agents",
        "demand_forecasts",
    ]

    for collection_name in collections:
        records = load_json(sample_dir / f"{collection_name}.json")
        upsert_collection(db, collection_name, records)
        print(f"Seeded {len(records)} records into {collection_name}")

    print("Firestore seed complete.")


if __name__ == "__main__":
    main()
