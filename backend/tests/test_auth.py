from collections.abc import Generator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.routes.auth import get_auth_service
from app.core.security import hash_password, verify_password
from app.db.base import Base
from app.main import app
from app.models import User
from app.services.auth import AuthService


pytestmark = pytest.mark.asyncio


@pytest.fixture()
def db_session() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    with TestingSessionLocal() as session:
        session.add_all(
            [
                User(slug="krystin", display_name="Krystin", username="krystin"),
                User(slug="dale", display_name="Dale", username="dale"),
            ]
        )
        session.commit()
        yield session


@pytest.fixture()
def auth_client(db_session: Session) -> Generator[AsyncClient, None, None]:
    async def override_auth_service() -> AuthService:
        return AuthService(db_session)

    app.dependency_overrides[get_auth_service] = override_auth_service
    try:
        yield AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    finally:
        app.dependency_overrides.clear()


async def test_password_hashing_uses_verifiable_hashes() -> None:
    hashed = hash_password("household-secret")

    assert hashed != "household-secret"
    assert verify_password("household-secret", hashed) is True
    assert verify_password("wrong-secret", hashed) is False


async def test_auth_providers_expose_current_and_future_options(auth_client: AsyncClient) -> None:
    async with auth_client as client:
        response = await client.get("/api/v1/auth/providers")

    assert response.status_code == 200
    payload = response.json()
    assert {provider["key"] for provider in payload["providers"]} == {
        "household_select",
        "password",
        "oauth2",
    }
    assert {user["slug"] for user in payload["users"]} == {"krystin", "dale"}
    password_provider = next(
        provider for provider in payload["providers"] if provider["key"] == "password"
    )
    oauth_provider = next(provider for provider in payload["providers"] if provider["key"] == "oauth2")
    assert password_provider["enabled"] is True
    assert password_provider["configured"] is False
    assert oauth_provider["enabled"] is False
    assert oauth_provider["configured"] is False


async def test_quick_select_session_returns_selected_user(auth_client: AsyncClient) -> None:
    async with auth_client as client:
        response = await client.post("/api/v1/auth/session/select", json={"user_slug": "krystin"})

    assert response.status_code == 200
    assert response.json()["user"]["auth_method"] == "household_select"


async def test_password_login_succeeds_when_password_exists(db_session: Session) -> None:
    service = AuthService(db_session)
    service.set_password_for_user("krystin", "correct horse battery staple")

    session = service.login_with_password("krystin", "correct horse battery staple")

    assert session is not None
    assert session.user.auth_method == "password"


async def test_password_provider_is_configured_after_hash_is_stored(
    db_session: Session,
) -> None:
    service = AuthService(db_session)
    service.set_password_for_user("krystin", "correct horse battery staple")

    response = service.get_auth_providers()

    password_provider = next(provider for provider in response.providers if provider.key == "password")
    assert password_provider.configured is True


async def test_password_login_endpoint_rejects_unconfigured_users(auth_client: AsyncClient) -> None:
    async with auth_client as client:
        response = await client.post(
            "/api/v1/auth/session/password",
            json={"username": "krystin", "password": "anything"},
        )

    assert response.status_code == 401
