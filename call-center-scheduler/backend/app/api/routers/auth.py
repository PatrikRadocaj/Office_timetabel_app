"""Auth API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.models.auth import AuthResponse, LoginRequest, RegisterRequest
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])
service = AuthService()


@router.post("/register", response_model=AuthResponse)
async def register(payload: RegisterRequest) -> AuthResponse:
    return await service.register(payload)


@router.post("/login", response_model=AuthResponse)
async def login(payload: LoginRequest) -> AuthResponse:
    return await service.login(payload)


@router.post("/logout")
def logout(current_user: dict = Depends(get_current_user)) -> dict[str, str]:
    return service.logout(current_user["id"])


@router.get("/me")
def me(current_user: dict = Depends(get_current_user)) -> dict:
    return current_user
