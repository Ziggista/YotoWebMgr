from dataclasses import dataclass

from app.core.security import hash_password, verify_password
from app.schemas.auth import (
    AuthProvider,
    AuthProvidersResponse,
    AuthUserSummary,
    SessionResponse,
    SessionUser,
)


@dataclass(frozen=True)
class AuthUserRecord:
    slug: str
    display_name: str
    username: str
    password_hash: str | None
    can_quick_select: bool = True


class AuthService:
    def __init__(self) -> None:
        # Temporary in-memory household users. Replace with database-backed records in Milestone 1 auth.
        self._users = {
            user.slug: user
            for user in (
                AuthUserRecord(
                    slug="krystin",
                    display_name="Krystin",
                    username="krystin",
                    password_hash=None,
                ),
                AuthUserRecord(
                    slug="dale",
                    display_name="Dale",
                    username="dale",
                    password_hash=None,
                ),
            )
        }

    def get_auth_providers(self) -> AuthProvidersResponse:
        return AuthProvidersResponse(
            providers=[
                AuthProvider(
                    key="household_select",
                    type="household_select",
                    label="Quick household sign-in",
                    enabled=True,
                    configured=True,
                    description="Temporary home-page user selection for household admins.",
                ),
                AuthProvider(
                    key="password",
                    type="password",
                    label="Username and password",
                    enabled=True,
                    configured=any(user.password_hash for user in self._users.values()),
                    description="Argon2-hashed password login scaffold for future local accounts.",
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
                for user in self._users.values()
            ],
        )

    def select_user(self, user_slug: str) -> SessionResponse | None:
        user = self._users.get(user_slug)
        if user is None:
            return None

        return SessionResponse(
            user=SessionUser(
                slug=user.slug,
                display_name=user.display_name,
                username=user.username,
                auth_method="household_select",
            ),
            session_mode="scaffold",
            message="Quick-select session created. Replace with persistent sessions once auth storage exists.",
        )

    def login_with_password(self, username: str, password: str) -> SessionResponse | None:
        user = next((entry for entry in self._users.values() if entry.username == username), None)
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
            message="Password session created. Replace with signed tokens once auth persistence is added.",
        )

    def set_password_for_user(self, user_slug: str, password: str) -> None:
        user = self._users[user_slug]
        self._users[user_slug] = AuthUserRecord(
            slug=user.slug,
            display_name=user.display_name,
            username=user.username,
            password_hash=hash_password(password),
            can_quick_select=user.can_quick_select,
        )


auth_service = AuthService()
