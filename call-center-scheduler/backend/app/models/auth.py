"""Authentication and user-facing account schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.models.common import UserRole


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)
    full_name: str = Field(min_length=2, max_length=120)
    # Public self-registration must never mint admin privileges.
    role: UserRole = UserRole.AGENT
    office_id: str | None = None

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, value: str) -> str:
        has_upper = any(ch.isupper() for ch in value)
        has_lower = any(ch.islower() for ch in value)
        has_digit = any(ch.isdigit() for ch in value)
        if not (has_upper and has_lower and has_digit):
            raise ValueError("Password must include uppercase, lowercase, and numeric characters")
        return value

    @field_validator("role")
    @classmethod
    def validate_public_role(cls, value: UserRole) -> UserRole:
        if value != UserRole.AGENT:
            raise ValueError("Self-registration role must be 'agent'")
        return value


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)


class UserProfile(BaseModel):
    id: str
    email: EmailStr
    full_name: str
    role: UserRole
    office_id: str | None = None
    is_active: bool = True
    created_at: datetime | str
    updated_at: datetime | str


class AuthResponse(BaseModel):
    user: UserProfile
    id_token: str
    refresh_token: str
    expires_in: int
