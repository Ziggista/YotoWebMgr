from collections.abc import AsyncGenerator, Generator
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings
from app.db.base import Base
from app.db.session import get_db_session
from app.main import app
from app.models import Job, LibraryItem, Setting, User


pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def import_storage_paths(tmp_path: Path) -> Generator[dict[str, str], None, None]:
    settings = get_settings()
    original_drop_path = settings.import_drop_path
    original_upload_path = settings.browser_upload_path
    paths = {
        "drop": str(tmp_path / "drop"),
        "uploads": str(tmp_path / "uploads"),
    }
    settings.import_drop_path = paths["drop"]
    settings.browser_upload_path = paths["uploads"]
    try:
        yield paths
    finally:
        settings.import_drop_path = original_drop_path
        settings.browser_upload_path = original_upload_path


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
                Setting(key="target_duration_hours", value="4.9"),
                Setting(key="target_size_mb", value="480"),
                Setting(key="normalise_loudness_default", value="true"),
                Setting(key="audiobook_bitrate_kbps", value="96"),
                Setting(key="music_bitrate_kbps", value="128"),
            ]
        )
        session.commit()
        yield session


@pytest.fixture()
def api_client(db_session: Session) -> Generator[AsyncClient, None, None]:
    async def override_db_session() -> AsyncGenerator[Session, None]:
        yield db_session

    app.dependency_overrides[get_db_session] = override_db_session
    try:
        yield AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    finally:
        app.dependency_overrides.clear()


async def test_settings_can_be_read_and_updated(api_client: AsyncClient) -> None:
    async with api_client as client:
        response = await client.get("/api/v1/settings")
        assert response.status_code == 200
        assert response.json()["target_size_mb"] == 480

        updated = await client.put("/api/v1/settings", json={"target_size_mb": 470})

    assert updated.status_code == 200
    assert updated.json()["target_size_mb"] == 470


async def test_import_creates_library_item_and_job(
    api_client: AsyncClient,
    db_session: Session,
    import_storage_paths: dict[str, str],
) -> None:
    async with api_client as client:
        response = await client.post(
            "/api/v1/imports",
            json={
                "title": "Dragon Stories",
                "source_type": "filesystem",
                "source_path": "dragon-stories.m4b",
                "content_type": "Audiobook",
                "requested_by_user_slug": "krystin",
            },
        )

    assert response.status_code == 201
    payload = response.json()
    assert payload["status"] == "queued"
    assert payload["related_library_item_id"] is not None
    assert payload["related_job_id"] is not None

    library_item = db_session.scalar(select(LibraryItem).where(LibraryItem.title == "Dragon Stories"))
    job = db_session.scalar(select(Job).where(Job.related_import_id == payload["id"]))
    assert library_item is not None
    assert library_item.status == "import_queued"
    assert job is not None
    assert job.type == "import_from_filesystem"
    assert payload["source_path"] == f"{import_storage_paths['drop']}/dragon-stories.m4b"


async def test_import_sources_exposes_mounted_paths(
    api_client: AsyncClient,
    import_storage_paths: dict[str, str],
) -> None:
    async with api_client as client:
        response = await client.get("/api/v1/imports/sources")

    assert response.status_code == 200
    payload = response.json()
    assert payload["filesystem_drop_path"] == import_storage_paths["drop"]
    assert payload["browser_upload_path"] == import_storage_paths["uploads"]
    assert ".m4b" in payload["allowed_extensions"]


async def test_filesystem_import_rejects_paths_outside_drop_area(
    api_client: AsyncClient,
) -> None:
    async with api_client as client:
        response = await client.post(
            "/api/v1/imports",
            json={
                "title": "Outside File",
                "source_type": "filesystem",
                "source_path": "/media/originals/outside.m4b",
                "content_type": "Audiobook",
            },
        )

    assert response.status_code == 422


async def test_upload_import_stages_file(
    api_client: AsyncClient,
) -> None:
    async with api_client as client:
        response = await client.post(
            "/api/v1/imports/uploads",
            data={
                "title": "Uploaded Song",
                "content_type": "Music Album",
                "requested_by_user_slug": "dale",
            },
            files={"media_file": ("uploaded song.mp3", b"fake audio", "audio/mpeg")},
        )
        library_response = await client.get("/api/v1/library")

    assert response.status_code == 201
    payload = response.json()
    assert payload["source_type"] == "browser_upload"
    assert payload["related_job_id"] is not None
    assert Path(payload["source_path"]).exists()
    assert library_response.status_code == 200
    assert library_response.json()[0]["media_url"] == "/api/v1/library/1/media"


async def test_hide_import_marks_import_and_job_pending_delete(
    api_client: AsyncClient,
) -> None:
    async with api_client as client:
        created = await client.post(
            "/api/v1/imports",
            json={
                "title": "Hidden Import",
                "source_type": "filesystem",
                "source_path": "hidden.m4b",
                "content_type": "Audiobook",
            },
        )
        hidden = await client.post(f"/api/v1/imports/{created.json()['id']}/hide")
        visible_imports = await client.get("/api/v1/imports")
        hidden_imports = await client.get("/api/v1/imports?include_pending_delete=true")
        visible_jobs = await client.get("/api/v1/jobs")
        hidden_jobs = await client.get("/api/v1/jobs?include_pending_delete=true")

    assert hidden.status_code == 200
    assert hidden.json()["pending_delete"] is True
    assert visible_imports.json() == []
    assert hidden_imports.json()[0]["status"] == "pending_delete"
    assert visible_jobs.json() == []
    assert hidden_jobs.json()[0]["pending_delete"] is True


async def test_job_retry_requeues_failed_job(api_client: AsyncClient, db_session: Session) -> None:
    job = Job(
        type="inspect_media",
        status="failed",
        retry_count=0,
        max_retries=3,
        progress_percent=50,
        progress_message="Failed",
        error_summary="Bad media",
    )
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)

    async with api_client as client:
        response = await client.post(f"/api/v1/jobs/{job.id}/retry")

    assert response.status_code == 200
    assert response.json()["status"] == "queued"
    assert response.json()["retry_count"] == 1
