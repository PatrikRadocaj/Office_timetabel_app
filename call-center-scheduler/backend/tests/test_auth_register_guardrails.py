"""Guardrail tests for public registration privilege boundaries."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.models.auth import RegisterRequest
from app.models.common import UserRole
from app.services.auth_service import AuthService


def test_register_request_rejects_admin_role_in_public_payload() -> None:
    """Public registration must reject attempts to self-assign admin role."""

    with pytest.raises(ValidationError):
        RegisterRequest(
            email="new-user@example.com",
            password="StrongPass123",
            full_name="New User",
            role="admin",
        )


def test_register_request_defaults_role_to_agent() -> None:
    """When role is omitted, public registration must default to agent."""

    payload = RegisterRequest(
        email="default-role@example.com",
        password="StrongPass123",
        full_name="Default Role User",
    )

    assert payload.role == UserRole.AGENT


def test_register_service_forces_agent_role_even_if_payload_is_tampered(monkeypatch: pytest.MonkeyPatch) -> None:
    """Service layer must persist agent role even if payload object is manipulated."""

    class FakeUsersRepository:
        def __init__(self) -> None:
            self.created_payload: dict | None = None

        def get_by_email(self, _email: str):
            return None

        def create(self, data: dict, document_id: str | None = None):
            self.created_payload = {**data}
            return {
                "id": document_id or "generated-id",
                **data,
            }

    fake_repo = FakeUsersRepository()
    monkeypatch.setattr("app.services.auth_service.UsersRepository", lambda: fake_repo)
    monkeypatch.setattr(
        "app.services.auth_service.get_settings",
        lambda: SimpleNamespace(firebase_web_api_key="fake-api-key"),
    )

    service = AuthService()

    async def fake_identity_toolkit_request(endpoint: str, body: dict):
        assert endpoint == "accounts:signUp"
        assert body["email"] == "tampered-user@example.com"
        return {
            "localId": "firebase-uid-123",
            "idToken": "id-token",
            "refreshToken": "refresh-token",
            "expiresIn": "3600",
        }

    monkeypatch.setattr(service, "_identity_toolkit_request", fake_identity_toolkit_request)

    # This bypasses request-model validation intentionally to test service hardening.
    tampered_payload = SimpleNamespace(
        email="tampered-user@example.com",
        password="StrongPass123",
        full_name="Tampered User",
        role=UserRole.ADMIN,
        office_id=None,
    )

    response = asyncio.run(service.register(tampered_payload))

    assert fake_repo.created_payload is not None
    assert fake_repo.created_payload["role"] == UserRole.AGENT.value
    assert response.user.role == UserRole.AGENT
