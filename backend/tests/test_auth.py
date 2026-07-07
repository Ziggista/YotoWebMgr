import pytest
from httpx import ASGITransport, AsyncClient

from app.core.security import hash_password, verify_password
from app.main import app
from app.services.auth import AuthService


pytestmark = pytest.mark.asyncio


async def test_password_hashing_uses_verifiable_hashes() -> None:
    hashed = hash_password("household-secret")

    assert hashed != "household-secret"
    assert verify_password("household-secret", hashed) is True
    assert verify_password("wrong-secret", hashed) is False


async def test_auth_providers_expose_current_and_future_options() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/auth/providers")

    assert response.status_code == 200
    payload = response.json()
    assert {provider["key"] for provider in payload["providers"]} == {
        "household_select",
        "password",
        "oauth2",
    }
    assert {user["slug"] for user in payload["users"]} == {"krystin", "dale"}


async def test_quick_select_session_returns_selected_user() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/v1/auth/session/select", json={"user_slug": "krystin"})

    assert response.status_code == 200
    assert response.json()["user"]["auth_method"] == "household_select"


async def test_password_login_succeeds_when_password_exists() -> None:
    service = AuthService()
    service.set_password_for_user("krystin", "correct horse battery staple")

    session = service.login_with_password("krystin", "correct horse battery staple")

    assert session is not None
    assert session.user.auth_method == "password"


async def test_password_login_endpoint_rejects_unconfigured_users() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/auth/session/password",
            json={"username": "krystin", "password": "anything"},
        )

    assert response.status_code == 401
