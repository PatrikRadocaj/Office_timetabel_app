"""App-wide settings loaded from environment variables."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings for the API service."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "Call Center Scheduler API"
    api_v1_prefix: str = "/api/v1"
    environment: str = "development"

    cors_origins: str = (
        "http://localhost:8000,http://127.0.0.1:8000,"
        "http://localhost:5173,http://127.0.0.1:5173,"
        "http://localhost:4173,http://127.0.0.1:4173"
    )

    firebase_project_id: str
    firebase_web_api_key: str
    firebase_service_account_path: str | None = None
    firebase_service_account_json: str | None = None

    schedule_slot_minutes: int = Field(default=30, ge=15, le=60)
    default_shift_hours: int = Field(default=8, ge=4, le=12)
    max_weekly_hours_hard_limit: int = Field(default=60, ge=1, le=100)

    @field_validator("schedule_slot_minutes")
    @classmethod
    def validate_slot_minutes(cls, value: int) -> int:
        if value % 15 != 0:
            raise ValueError("SCHEDULE_SLOT_MINUTES must be a multiple of 15")
        return value

    @property
    def parsed_cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached settings to avoid repeated environment parsing."""

    return Settings()
