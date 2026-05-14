"""Firebase bootstrap helpers used by repositories and auth dependencies."""

from __future__ import annotations

import json
from pathlib import Path

import firebase_admin
from firebase_admin import auth, credentials, firestore

from app.core.config import get_settings


def initialize_firebase() -> firebase_admin.App:
    """Initialize and return the default Firebase app exactly once."""

    try:
        return firebase_admin.get_app()
    except ValueError:
        settings = get_settings()

        if settings.firebase_service_account_json:
            service_account = json.loads(settings.firebase_service_account_json)
            credential = credentials.Certificate(service_account)
        elif settings.firebase_service_account_path:
            credential_path = Path(settings.firebase_service_account_path)
            if not credential_path.is_absolute():
                # Resolve relative paths from backend directory.
                credential_path = (Path(__file__).resolve().parents[2] / credential_path).resolve()
            if not credential_path.exists():
                raise RuntimeError(f"Firebase service account file not found: {credential_path}")
            credential = credentials.Certificate(str(credential_path))
        else:
            credential = credentials.ApplicationDefault()

        options = {"projectId": settings.firebase_project_id}
        return firebase_admin.initialize_app(credential=credential, options=options)


def get_firestore_client() -> firestore.Client:
    """Return the Firestore client bound to the initialized Firebase app."""

    app = initialize_firebase()
    return firestore.client(app=app)


def verify_id_token(id_token: str) -> dict:
    """Verify and decode a Firebase ID token."""

    app = initialize_firebase()
    return auth.verify_id_token(id_token, app=app, check_revoked=True, clock_skew_seconds=30)


def revoke_refresh_tokens(uid: str) -> None:
    """Force logout of all active sessions for a user."""

    app = initialize_firebase()
    auth.revoke_refresh_tokens(uid, app=app)
