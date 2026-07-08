from collections.abc import AsyncGenerator, Generator
from pathlib import Path
import zipfile

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings
from app.api.routes.library import _playlist_stream_url_from_text
from app.db.base import Base
from app.db.session import get_db_session
from app.main import app
from app.models import Job, LibraryItem, PhysicalCard, PlaylistTrack, Setting, User


pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def import_storage_paths(tmp_path: Path) -> Generator[dict[str, str], None, None]:
    settings = get_settings()
    original_drop_path = settings.import_drop_path
    original_upload_path = settings.browser_upload_path
    original_artwork_path = settings.artwork_path
    paths = {
        "drop": str(tmp_path / "drop"),
        "uploads": str(tmp_path / "uploads"),
        "artwork": str(tmp_path / "artwork"),
    }
    settings.import_drop_path = paths["drop"]
    settings.browser_upload_path = paths["uploads"]
    settings.artwork_path = paths["artwork"]
    try:
        yield paths
    finally:
        settings.import_drop_path = original_drop_path
        settings.browser_upload_path = original_upload_path
        settings.artwork_path = original_artwork_path


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
                Setting(key="yoto_api_enabled", value="false"),
                Setting(key="yoto_api_base_url", value="https://api.yotoplay.com"),
                Setting(key="yoto_auth_base_url", value="https://login.yotoplay.com"),
                Setting(key="yoto_client_id", value=""),
                Setting(key="yoto_redirect_uri", value=""),
                Setting(key="yoto_oauth_scope", value="openid offline_access"),
                Setting(key="yoto_upload_timeout_seconds", value="900"),
                Setting(key="yoto_transcode_poll_seconds", value="10"),
                Setting(key="yoto_transcode_timeout_minutes", value="30"),
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
        assert response.json()["yoto_api_base_url"] == "https://api.yotoplay.com"

        updated = await client.put(
            "/api/v1/settings",
            json={
                "target_size_mb": 470,
                "yoto_api_enabled": True,
                "yoto_transcode_poll_seconds": 15,
            },
        )

    assert updated.status_code == 200
    assert updated.json()["target_size_mb"] == 470
    assert updated.json()["yoto_api_enabled"] is True
    assert updated.json()["yoto_transcode_poll_seconds"] == 15


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
                "source_path": "/tmp/yotowebmgr-outside.m4b",
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


async def test_zip_upload_extracts_album_tracks(
    api_client: AsyncClient,
    db_session: Session,
    tmp_path: Path,
) -> None:
    zip_path = tmp_path / "album.zip"
    with zipfile.ZipFile(zip_path, "w") as archive:
        archive.writestr("02 second.mp3", b"track two")
        archive.writestr("01 first.mp3", b"track one")
        archive.writestr("cover.txt", b"ignored")

    async with api_client as client:
        with zip_path.open("rb") as upload_file:
            response = await client.post(
                "/api/v1/imports/uploads",
                data={"title": "ZIP Album", "content_type": "Music Album"},
                files={"media_file": ("album.zip", upload_file, "application/zip")},
            )
        detail = await client.get(f"/api/v1/library/{response.json()['related_library_item_id']}")

    assert response.status_code == 201
    payload = response.json()
    assert payload["source_path"].endswith("-extracted")
    assert payload["related_job_id"] is not None
    assert detail.status_code == 200
    assert [track["title"] for track in detail.json()["tracks"]] == ["first", "second"]
    tracks = db_session.scalars(select(PlaylistTrack).order_by(PlaylistTrack.track_number)).all()
    assert [track.track_number for track in tracks] == [1, 2]


async def test_library_item_can_be_linked_to_card(api_client: AsyncClient) -> None:
    async with api_client as client:
        upload = await client.post(
            "/api/v1/imports/uploads",
            data={"title": "Small Story", "content_type": "Audiobook"},
            files={"media_file": ("small-story.mp3", b"fake audio", "audio/mpeg")},
        )
        card = await client.post(
            "/api/v1/cards",
            json={"card_code": "CARD02", "display_name": "Card 02"},
        )
        linked = await client.post(
            f"/api/v1/library/{upload.json()['related_library_item_id']}/link-card",
            json={"card_id": card.json()["id"]},
        )

    assert linked.status_code == 202
    payload = linked.json()
    assert payload["requires_split_plan"] is False
    assert payload["job"]["type"] == "upload_yoto_asset"
    assert payload["job"]["related_card_id"] == card.json()["id"]
    assert payload["card"]["current_library_item_id"] == upload.json()["related_library_item_id"]
    assert payload["card"]["pending_job_id"] == payload["job"]["id"]
    assert payload["card"]["status"] == "upload_queued"
    assert payload["card"]["ready_to_link_in_app"] is True


async def test_library_item_link_queues_split_plan_when_source_exceeds_target(
    api_client: AsyncClient,
    db_session: Session,
    import_storage_paths: dict[str, str],
) -> None:
    target_setting = db_session.scalar(select(Setting).where(Setting.key == "target_size_mb"))
    assert target_setting is not None
    target_setting.value = "1"
    db_session.add(target_setting)
    db_session.commit()

    oversized_path = Path(import_storage_paths["drop"]) / "long-story.mp3"
    oversized_path.parent.mkdir(parents=True, exist_ok=True)
    oversized_path.write_bytes(b"0" * 2 * 1024 * 1024)

    async with api_client as client:
        created = await client.post(
            "/api/v1/imports",
            json={
                "title": "Long Story",
                "source_type": "filesystem",
                "source_path": oversized_path.name,
                "content_type": "Audiobook",
            },
        )
        card = await client.post(
            "/api/v1/cards",
            json={"card_code": "CARD03", "display_name": "Card 03"},
        )
        linked = await client.post(
            f"/api/v1/library/{created.json()['related_library_item_id']}/link-card",
            json={"card_id": card.json()["id"]},
        )

    assert linked.status_code == 202
    payload = linked.json()
    assert payload["requires_split_plan"] is True
    assert payload["estimated_source_size_mb"] == 2.0
    assert payload["job"]["type"] == "build_card_plan"
    assert payload["library_item"]["status"] == "card_plan_queued"
    assert payload["card"]["status"] == "planning"


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


async def test_card_inventory_accepts_nfc_workflow_fields(
    api_client: AsyncClient,
    db_session: Session,
) -> None:
    async with api_client as client:
        created = await client.post(
            "/api/v1/cards",
            json={
                "card_code": "CARD01",
                "programmable_id": "yoto:playlist:abc123",
                "display_name": "Card 01",
                "card_kind": "generic_mifare_ultralight_ev1",
                "nfc_technology": "NFC Type 2",
                "chip_type": "MIFARE Ultralight EV1",
                "memory_size_bytes": 48,
                "ndef_prepared": True,
                "ndef_format_command": "A2:03:E1:10:06:00,A2:04:03:04:D8:00,A2:05:00:00:FE:00",
                "programming_app": "NFC Tools",
                "source_card_code": "MYO01",
                "is_reusable_transfer_card": False,
                "ready_to_link_in_app": True,
                "linked_manually": True,
                "overwrite_ok": True,
                "downloaded_to_player_confirmed": True,
                "needs_player_download": False,
                "yoto_playlist_uri": "https://my.yotoplay.com/playlist/abc123",
                "status": "ready_to_link",
                "tested": True,
            },
        )
        duplicate = await client.post(
            "/api/v1/cards",
            json={"card_code": "CARD01", "display_name": "Duplicate"},
        )
        listed = await client.get("/api/v1/cards")

    assert created.status_code == 201
    payload = created.json()
    assert payload["card_code"] == "CARD01"
    assert payload["programmable_id"] == "yoto:playlist:abc123"
    assert payload["chip_type"] == "MIFARE Ultralight EV1"
    assert payload["memory_size_bytes"] == 48
    assert payload["ndef_prepared"] is True
    assert payload["source_card_code"] == "MYO01"
    assert payload["ready_to_link_in_app"] is True
    assert payload["linked_manually"] is True
    assert payload["overwrite_ok"] is True
    assert payload["downloaded_to_player_confirmed"] is True
    assert duplicate.status_code == 409
    assert listed.status_code == 200
    assert listed.json()[0]["display_name"] == "Card 01"
    assert db_session.scalar(select(PhysicalCard).where(PhysicalCard.card_code == "CARD01")) is not None


async def test_card_code_must_be_alphanumeric(api_client: AsyncClient) -> None:
    async with api_client as client:
        response = await client.post(
            "/api/v1/cards",
            json={"card_code": "CARD-01", "display_name": "Card 01"},
        )

    assert response.status_code == 422


async def test_library_playlist_settings_tracks_icons_and_readiness(
    api_client: AsyncClient,
) -> None:
    async with api_client as client:
        created = await client.post(
            "/api/v1/library",
            json={
                "title": "Bedtime Mix",
                "content_type": "Custom Playlist",
                "cover_art_path": "/art/bedtime.png",
            },
        )
        item_id = created.json()["id"]
        updated = await client.put(
            f"/api/v1/library/{item_id}/settings",
            json={"playlist_always_play_from_start": True, "playlist_hide_track_numbers": True},
        )
        track = await client.post(
            f"/api/v1/library/{item_id}/tracks",
            json={"title": "Opening Story", "track_number": 1, "track_behavior": "pause_for_button"},
        )
        icon_apply = await client.post(
            f"/api/v1/library/{item_id}/tracks/apply-icon",
            json={"icon_path": "/icons/moon.png"},
        )
        card = await client.post("/api/v1/cards", json={"card_code": "CARD04", "display_name": "Card 04"})
        await client.post(f"/api/v1/library/{item_id}/link-card", json={"card_id": card.json()["id"]})
        readiness = await client.get(f"/api/v1/library/{item_id}/readiness")

    assert updated.status_code == 200
    assert updated.json()["playlist_always_play_from_start"] is True
    assert updated.json()["playlist_hide_track_numbers"] is True
    assert track.status_code == 201
    assert track.json()["track_behavior"] == "pause_for_button"
    assert icon_apply.status_code == 200
    assert icon_apply.json()[0]["icon_path"] == "/icons/moon.png"
    assert readiness.status_code == 200
    assert readiness.json()["status"] == "ready"


async def test_radio_stream_creates_validation_job(api_client: AsyncClient, db_session: Session) -> None:
    async with api_client as client:
        created = await client.post(
            "/api/v1/library",
            json={"title": "Kitchen Radio", "content_type": "Radio Play"},
        )
        response = await client.post(
            f"/api/v1/library/{created.json()['id']}/radio-streams",
            json={"title": "Morning Stream", "stream_url": "https://example.test/radio.mp3"},
        )
        library = await client.get("/api/v1/library")
        stream = await client.get(
            f"/api/v1/library/{created.json()['id']}/stream",
            follow_redirects=False,
        )

    assert response.status_code == 201
    assert response.json()["is_stream"] is True
    assert response.json()["stream_url"] == "https://example.test/radio.mp3"
    assert library.json()[0]["stream_url"] == f"/api/v1/library/{created.json()['id']}/stream"
    assert stream.status_code == 307
    assert stream.headers["location"] == "https://example.test/radio.mp3"
    job = db_session.scalar(select(Job).where(Job.type == "validate_radio_stream"))
    assert job is not None
    assert "Wi-Fi" in job.progress_message


async def test_playlist_track_can_be_edited(api_client: AsyncClient) -> None:
    async with api_client as client:
        created = await client.post(
            "/api/v1/library",
            json={"title": "Editable Radio", "content_type": "Radio Play"},
        )
        track = await client.post(
            f"/api/v1/library/{created.json()['id']}/radio-streams",
            json={"title": "Original Stream", "stream_url": "https://example.test/original.mp3"},
        )
        updated = await client.put(
            f"/api/v1/library/{created.json()['id']}/tracks/{track.json()['id']}",
            json={
                "title": "Updated Stream",
                "track_number": 3,
                "duration_seconds": 120,
                "icon_path": "/icons/radio.png",
                "track_behavior": "repeat_track",
                "stream_url": "https://example.test/updated.mp3",
            },
        )
        rejected = await client.put(
            f"/api/v1/library/{created.json()['id']}/tracks/{track.json()['id']}",
            json={"stream_url": "file:///etc/passwd"},
        )
        detail = await client.get(f"/api/v1/library/{created.json()['id']}")

    assert updated.status_code == 200
    assert updated.json()["title"] == "Updated Stream"
    assert updated.json()["track_number"] == 3
    assert updated.json()["duration_seconds"] == 120
    assert updated.json()["icon_path"] == "/icons/radio.png"
    assert updated.json()["track_behavior"] == "repeat_track"
    assert updated.json()["stream_url"] == "https://example.test/updated.mp3"
    assert rejected.status_code == 422
    assert detail.json()["tracks"][0]["title"] == "Updated Stream"


async def test_radio_stream_rejects_non_http_urls(api_client: AsyncClient) -> None:
    async with api_client as client:
        created = await client.post(
            "/api/v1/library",
            json={"title": "Bad Radio", "content_type": "Radio Play"},
        )
        response = await client.post(
            f"/api/v1/library/{created.json()['id']}/radio-streams",
            json={"title": "Bad Stream", "stream_url": "file:///etc/passwd"},
        )

    assert response.status_code == 422


async def test_pls_playlist_text_resolves_first_stream_url() -> None:
    playlist_text = """
    [playlist]
    NumberOfEntries=1
    File1=http://example.test/live.mp3
    Title1=Example Radio
    """

    assert _playlist_stream_url_from_text(playlist_text) == "http://example.test/live.mp3"


async def test_podcast_feed_can_parse_supplied_rss_xml(api_client: AsyncClient) -> None:
    rss_xml = """
    <rss><channel>
      <title>Story Feed</title>
      <description>Small stories</description>
      <item>
        <title>Episode One</title>
        <guid>episode-1</guid>
        <enclosure url="https://example.test/episode-1.mp3" />
        <duration>01:02</duration>
      </item>
    </channel></rss>
    """

    async with api_client as client:
        created = await client.post(
            "/api/v1/library",
            json={"title": "Story Podcast", "content_type": "Podcast"},
        )
        response = await client.post(
            f"/api/v1/library/{created.json()['id']}/podcast-feeds",
            json={"rss_url": "https://example.test/feed.xml", "rss_xml": rss_xml},
        )

    assert response.status_code == 201
    payload = response.json()
    assert payload["title"] == "Story Feed"
    assert payload["episodes"][0]["title"] == "Episode One"
    assert payload["episodes"][0]["duration_seconds"] == 62


async def test_manual_split_point_is_saved(api_client: AsyncClient) -> None:
    async with api_client as client:
        created = await client.post(
            "/api/v1/library",
            json={"title": "Long Book", "content_type": "Audiobook"},
        )
        response = await client.post(
            f"/api/v1/library/{created.json()['id']}/split-points",
            json={"timestamp_seconds": 3600, "title": "Part 2", "part_number": 2},
        )
        detail = await client.get(f"/api/v1/library/{created.json()['id']}")

    assert response.status_code == 201
    assert response.json()["timestamp_seconds"] == 3600
    assert detail.json()["split_points"][0]["title"] == "Part 2"


async def test_card_plan_groups_tracks_by_target_duration(
    api_client: AsyncClient,
    db_session: Session,
) -> None:
    target_setting = db_session.scalar(select(Setting).where(Setting.key == "target_duration_hours"))
    assert target_setting is not None
    target_setting.value = "1"
    db_session.add(target_setting)
    db_session.commit()

    async with api_client as client:
        created = await client.post(
            "/api/v1/library",
            json={"title": "Long Book", "content_type": "Audiobook"},
        )
        item_id = created.json()["id"]
        for track_number, duration in enumerate([1800, 2400, 1200], start=1):
            await client.post(
                f"/api/v1/library/{item_id}/tracks",
                json={
                    "title": f"Chapter {track_number}",
                    "track_number": track_number,
                    "duration_seconds": duration,
                },
            )
        response = await client.get(f"/api/v1/library/{item_id}/card-plan")

    assert response.status_code == 200
    payload = response.json()
    assert payload["target_duration_seconds"] == 3600
    assert payload["parts"][0]["track_count"] == 1
    assert payload["parts"][0]["duration_seconds"] == 1800
    assert payload["parts"][1]["track_count"] == 2
    assert payload["parts"][1]["duration_seconds"] == 3600
    assert payload["parts"][0]["tracks"][0]["estimated_size_mb"] == 240


async def test_cover_art_upload_sets_library_cover_path(
    api_client: AsyncClient,
    import_storage_paths: dict[str, str],
) -> None:
    async with api_client as client:
        created = await client.post(
            "/api/v1/library",
            json={"title": "Moon Stories", "content_type": "Story Collection"},
        )
        item_id = created.json()["id"]
        response = await client.post(
            f"/api/v1/library/{item_id}/cover-art",
            files={"artwork_file": ("cover.png", b"png bytes", "image/png")},
        )

    assert response.status_code == 200
    cover_path = response.json()["cover_art_path"]
    assert cover_path.startswith(import_storage_paths["artwork"])
    assert Path(cover_path).read_bytes() == b"png bytes"
