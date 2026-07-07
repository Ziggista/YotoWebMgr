from fastapi import APIRouter, HTTPException, status

from app.schemas.auth import (
    AuthProvidersResponse,
    PasswordLoginRequest,
    SessionResponse,
    UserSelectionRequest,
)
from app.services.auth import auth_service


router = APIRouter()


@router.get("/providers", response_model=AuthProvidersResponse)
async def get_auth_providers() -> AuthProvidersResponse:
    return auth_service.get_auth_providers()


@router.post("/session/select", response_model=SessionResponse)
async def select_user_session(payload: UserSelectionRequest) -> SessionResponse:
    session = auth_service.select_user(payload.user_slug)
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return session


@router.post("/session/password", response_model=SessionResponse)
async def password_login(payload: PasswordLoginRequest) -> SessionResponse:
    session = auth_service.login_with_password(payload.username, payload.password)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )
    return session

