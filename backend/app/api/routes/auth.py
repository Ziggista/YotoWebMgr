from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db_session
from app.schemas.auth import (
    AuthProvidersResponse,
    PasswordLoginRequest,
    SessionResponse,
    UserSelectionRequest,
)
from app.services.auth import AuthService


router = APIRouter()


async def get_auth_service(db: Annotated[Session, Depends(get_db_session)]) -> AuthService:
    return AuthService(db)


@router.get("/providers", response_model=AuthProvidersResponse)
async def get_auth_providers(
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> AuthProvidersResponse:
    return auth_service.get_auth_providers()


@router.post("/session/select", response_model=SessionResponse)
async def select_user_session(
    payload: UserSelectionRequest,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> SessionResponse:
    session = auth_service.select_user(payload.user_slug)
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return session


@router.post("/session/password", response_model=SessionResponse)
async def password_login(
    payload: PasswordLoginRequest,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> SessionResponse:
    session = auth_service.login_with_password(payload.username, payload.password)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )
    return session
