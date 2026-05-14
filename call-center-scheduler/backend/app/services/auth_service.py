"""Authentication service that proxies Firebase Auth through our API."""

from __future__ import annotations

from typing import Any

import httpx
from fastapi import HTTPException, status
from firebase_admin import auth as firebase_auth

from app.core.config import get_settings
from app.core.exceptions import DependencyUnavailableError
from app.core.firebase import initialize_firebase, revoke_refresh_tokens
from app.models.auth import AuthResponse, LoginRequest, RegisterRequest, UserProfile
from app.models.common import UserRole, utcnow
from app.repositories.users_repository import UsersRepository


class AuthService:
    """Handles register/login/logout plus local profile storage."""

    def __init__(self):
        self.settings = get_settings()
        self.users_repo = UsersRepository()

    async def register(self, payload: RegisterRequest) -> AuthResponse:
        existing = self.users_repo.get_by_email(payload.email)
        if existing:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email is already registered")

        firebase_data = await self._identity_toolkit_request(
            endpoint="accounts:signUp",
            body={
                "email": payload.email,
                "password": payload.password,
                "returnSecureToken": True,
            },
        )

        uid = firebase_data["localId"]
        user_doc = {
            "email": payload.email,
            "full_name": payload.full_name.strip(),
            # Never trust incoming role in public registration.
            "role": UserRole.AGENT.value,
            "office_id": payload.office_id,
            "is_active": True,
            "created_at": utcnow(),
            "updated_at": utcnow(),
        }

        try:
            persisted_user = self.users_repo.create(user_doc, document_id=uid)
        except Exception:
            # Rollback auth user if profile persistence fails.
            app = initialize_firebase()
            firebase_auth.delete_user(uid, app=app)
            raise

        return self._build_auth_response(persisted_user, firebase_data)

    async def login(self, payload: LoginRequest) -> AuthResponse:
        firebase_data = await self._identity_toolkit_request(
            endpoint="accounts:signInWithPassword",
            body={
                "email": payload.email,
                "password": payload.password,
                "returnSecureToken": True,
            },
        )

        uid = firebase_data["localId"]
        user_doc = self.users_repo.get(uid)

        if user_doc is None:
            # Create fallback profile for externally created Firebase users.
            user_doc = self.users_repo.create(
                {
                    "email": firebase_data.get("email", payload.email),
                    "full_name": firebase_data.get("displayName") or payload.email.split("@")[0],
                    "role": UserRole.AGENT.value,
                    "office_id": None,
                    "is_active": True,
                },
                document_id=uid,
            )

        if not user_doc.get("is_active", True):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is disabled")

        return self._build_auth_response(user_doc, firebase_data)

    def logout(self, uid: str) -> dict[str, str]:
        revoke_refresh_tokens(uid)
        return {"message": "Logged out successfully"}

    async def _identity_toolkit_request(self, endpoint: str, body: dict[str, Any]) -> dict[str, Any]:
        url = f"https://identitytoolkit.googleapis.com/v1/{endpoint}?key={self.settings.firebase_web_api_key}"
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(url, json=body)
        except httpx.HTTPError as exc:
            raise DependencyUnavailableError(
                dependency="firebase_auth",
                detail="Firebase Auth service is unreachable. Retry later.",
                status_code=503,
            ) from exc

        if response.is_success:
            return response.json()

        error_payload = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
        error_code = error_payload.get("error", {}).get("message", "UNKNOWN_ERROR")
        mapped_detail, status_code = self._map_auth_error(error_code)
        raise HTTPException(status_code=status_code, detail=mapped_detail)

    @staticmethod
    def _map_auth_error(error_code: str) -> tuple[str, int]:
        if error_code == "EMAIL_EXISTS":
            return "Email is already in use", status.HTTP_409_CONFLICT
        if error_code in {"INVALID_PASSWORD", "EMAIL_NOT_FOUND", "INVALID_LOGIN_CREDENTIALS"}:
            return "Invalid email or password", status.HTTP_401_UNAUTHORIZED
        if error_code == "USER_DISABLED":
            return "Account is disabled", status.HTTP_403_FORBIDDEN
        if error_code == "OPERATION_NOT_ALLOWED":
            return "Email/password auth is not enabled in Firebase", status.HTTP_400_BAD_REQUEST
        return f"Authentication failed: {error_code}", status.HTTP_400_BAD_REQUEST

    @staticmethod
    def _build_auth_response(user_doc: dict[str, Any], firebase_data: dict[str, Any]) -> AuthResponse:
        user_model = UserProfile.model_validate(user_doc)
        return AuthResponse(
            user=user_model,
            id_token=firebase_data["idToken"],
            refresh_token=firebase_data["refreshToken"],
            expires_in=int(firebase_data.get("expiresIn", 3600)),
        )
