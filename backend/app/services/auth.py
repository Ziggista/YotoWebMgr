from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password, verify_password
from app.models import User
from app.schemas.auth import (
    AuthProvider,
    AuthProvidersResponse,
    AuthUserSummary,
    SessionResponse,
    SessionUser,
)


class AuthService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def _get_household_users(self) -> list[User]:
        return list(
            self._session.scalars(
                select(User)
                .where(User.is_household_admin.is_(True))
                .order_by(User.display_name.asc())
            )
        )

    def get_auth_providers(self) -> AuthProvidersResponse:
        users = self._get_household_users()

        return AuthProvidersResponse(
            providers=[
                AuthProvider(
                    key="household_select",
                    type="household_select",
                    label="Quick household sign-in",
                    enabled=True,
                    configured=any(user.can_quick_select for user in users),
                    description="Home-page user selection for household admins.",
                ),
                AuthProvider(
                    key="password",
                    type="password",
                    label="Username and password",
                    enabled=True,
                    configured=any(user.password_hash for user in users),
                    description="Argon2-hashed password login scaffold for local accounts.",
                ),
                AuthProvider(
                    key="oauth2",
                    type="oauth2",
                    label="OAuth 2.0",
                    enabled=False,
                    configured=False,
                    description="Reserved for future external identity providers.",
                ),
            ],
            users=[
                AuthUserSummary(
                    slug=user.slug,
                    display_name=user.display_name,
                    username=user.username,
                    has_password=user.password_hash is not None,
                    can_quick_select=user.can_quick_select,
                )
                for user in users
            ],
        )

    def select_user(self, user_slug: str) -> SessionResponse | None:
        user = self._session.scalar(
            select(User).where(User.slug == user_slug, User.can_quick_select.is_(True))
        )
        if user is None or not user.is_household_admin:
            return None

        return SessionResponse(
            user=SessionUser(
                slug=user.slug,
                display_name=user.display_name,
                username=user.username,
                auth_method="household_select",
            ),
            session_mode="scaffold",
            message="Quick-select session created. Replace with signed sessions when auth hardening lands.",
        )

    def login_with_password(self, username: str, password: str) -> SessionResponse | None:
        user = self._session.scalar(select(User).where(User.username == username))
        if user is None or user.password_hash is None:
            return None
        if not verify_password(password, user.password_hash):
            return None

        return SessionResponse(
            user=SessionUser(
                slug=user.slug,
                display_name=user.display_name,
                username=user.username,
                auth_method="password",
            ),
            session_mode="scaffold",
            message="Password session created. Replace with signed sessions when auth hardening lands.",
        )

    def set_password_for_user(self, user_slug: str, password: str) -> None:
        user = self._session.scalar(select(User).where(User.slug == user_slug))
        if user is None:
            raise KeyError(user_slug)

        user.password_hash = hash_password(password)
        self._session.add(user)
        self._session.commit()
