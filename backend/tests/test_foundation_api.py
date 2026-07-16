from collections.abc import AsyncGenerator, Generator
import base64
import json
from pathlib import Path
from urllib.parse import parse_qs, urlparse
import zipfile

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.routes import yoto as yoto_routes
from app.core.config import get_settings
from app.api.routes.library import _playlist_stream_url_from_text
from app.db.base import Base
from app.db.session import get_db_session
from app.main import app
from app.models import (
    ArtworkAsset,
    CardAssignmentEvent,
    Job,
    LibraryItem,
    PhysicalCard,
    PlaylistTrack,
    ProcessedAsset,
    Setting,
    Tag,
    TagAssignment,
    User,
    VersionEvent,
    YotoCredentialState,
    YotoPlaylistDraft,
    YotoPlaylistVersion,
)


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
    assert payload["review_status"] == "needs_review"
    assert payload["related_library_item_id"] is not None
    assert payload["related_job_id"] is not None

    library_item = db_session.scalar(select(LibraryItem).where(LibraryItem.title == "Dragon Stories"))
    job = db_session.scalar(select(Job).where(Job.related_import_id == payload["id"]))
    assert library_item is not None
    assert library_item.status == "import_queued"
    assert job is not None
    assert job.type == "import_from_filesystem"
    assert payload["source_path"] == f"{import_storage_paths['drop']}/dragon-stories.m4b"


async def test_import_review_updates_import_and_library_item(
    api_client: AsyncClient,
    db_session: Session,
) -> None:
    async with api_client as client:
        created = await client.post(
            "/api/v1/imports",
            json={
                "title": "Ruff Title",
                "source_type": "filesystem",
                "source_path": "rough-title.m4b",
                "content_type": "Other Audio",
                "requested_by_user_slug": "krystin",
            },
        )
        reviewed = await client.put(
            f"/api/v1/imports/{created.json()['id']}/review",
            json={
                "title": "Clean Title",
                "content_type": "Audiobook",
                "review_notes": "Corrected during import review.",
                "reviewed_by_user_slug": "dale",
            },
        )
        approved = await client.post(
            f"/api/v1/imports/{created.json()['id']}/approve",
            json={"approved_by_user_slug": "krystin"},
        )

    assert reviewed.status_code == 200
    assert reviewed.json()["title"] == "Clean Title"
    assert reviewed.json()["content_type"] == "Audiobook"
    assert reviewed.json()["review_status"] == "reviewed"
    assert reviewed.json()["review_notes"] == "Corrected during import review."
    assert reviewed.json()["reviewed_at"] is not None
    assert approved.status_code == 200
    assert approved.json()["review_status"] == "approved"
    assert approved.json()["approved_at"] is not None

    library_item = db_session.get(LibraryItem, reviewed.json()["related_library_item_id"])
    assert library_item is not None
    assert library_item.title == "Clean Title"
    assert library_item.content_type == "Audiobook"


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


async def test_tags_can_be_created_assigned_and_used_for_library_filtering(
    api_client: AsyncClient,
    db_session: Session,
) -> None:
    async with api_client as client:
        item = await client.post(
            "/api/v1/library",
            json={"title": "Bedtime Dragon", "content_type": "Story Collection"},
        )
        other_item = await client.post(
            "/api/v1/library",
            json={"title": "Morning Music", "content_type": "Music Album"},
        )
        tag = await client.post("/api/v1/tags", json={"name": "Bedtime", "color": "#90cdf4"})
        tag_id = tag.json()["id"]
        assigned = await client.put(
            f"/api/v1/tags/library-items/{item.json()['id']}",
            json={"tag_ids": [tag_id]},
        )
        filtered = await client.get(f"/api/v1/library?tag_id={tag_id}")
        searched = await client.get("/api/v1/library?search=dragon")

    assert other_item.status_code == 201
    assert tag.status_code == 201
    assert tag.json()["normalized_name"] == "bedtime"
    assert assigned.status_code == 200
    assert assigned.json()[0]["name"] == "Bedtime"
    assert filtered.status_code == 200
    assert [row["title"] for row in filtered.json()] == ["Bedtime Dragon"]
    assert filtered.json()[0]["tags"][0]["name"] == "Bedtime"
    assert searched.status_code == 200
    assert [row["title"] for row in searched.json()] == ["Bedtime Dragon"]

    assert db_session.scalar(select(Tag).where(Tag.normalized_name == "bedtime")) is not None
    assert db_session.scalar(select(TagAssignment).where(TagAssignment.entity_id == item.json()["id"])) is not None


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
        history = await client.get(f"/api/v1/cards/{card.json()['id']}/history")

    assert linked.status_code == 202
    payload = linked.json()
    assert payload["requires_split_plan"] is False
    assert payload["job"]["type"] == "upload_yoto_asset"
    assert payload["job"]["related_card_id"] == card.json()["id"]
    assert payload["card"]["current_library_item_id"] == upload.json()["related_library_item_id"]
    assert payload["card"]["pending_job_id"] == payload["job"]["id"]
    assert payload["card"]["status"] == "upload_queued"
    assert payload["card"]["ready_to_link_in_app"] is True
    assert history.status_code == 200
    assert history.json()[0]["event_type"] == "link_queued"
    assert history.json()[0]["library_item_id"] == upload.json()["related_library_item_id"]
    assert history.json()[0]["job_id"] == payload["job"]["id"]


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
        fetched = await client.get(f"/api/v1/cards/{created.json()['id']}")
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
    assert fetched.status_code == 200
    assert fetched.json()["display_name"] == "Card 01"
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


async def test_card_workflow_can_be_updated_after_scan(api_client: AsyncClient) -> None:
    async with api_client as client:
        created = await client.post(
            "/api/v1/cards",
            json={"card_code": "CARD06", "display_name": "Card 06"},
        )
        updated = await client.patch(
            f"/api/v1/cards/{created.json()['id']}",
            json={
                "programmable_id": "04A1B2C3D4",
                "nfc_technology": "NFC Type 2",
                "chip_type": "MIFARE Ultralight EV1",
                "memory_size_bytes": 48,
                "ndef_prepared": True,
                "programming_app": "NFC Tools",
                "ready_to_link_in_app": True,
                "linked_manually": True,
                "downloaded_to_player_confirmed": True,
                "needs_player_download": True,
                "tested": True,
                "status": "linked",
                "yoto_playlist_uri": "https://my.yotoplay.com/playlist/abc123",
                "notes": "Scanned and tested from Android.",
            },
        )
        history = await client.get(f"/api/v1/cards/{created.json()['id']}/history")

    assert updated.status_code == 200
    payload = updated.json()
    assert payload["programmable_id"] == "04A1B2C3D4"
    assert payload["ndef_prepared"] is True
    assert payload["ready_to_link_in_app"] is True
    assert payload["linked_manually"] is True
    assert payload["downloaded_to_player_confirmed"] is True
    assert payload["needs_player_download"] is False
    assert payload["tested"] is True
    assert payload["status"] == "linked"
    assert payload["last_programmed_at"] is not None
    assert payload["last_linked_at"] is not None
    assert payload["last_tested_at"] is not None
    assert history.status_code == 200
    assert history.json()[0]["event_type"] == "card_workflow_updated"
    assert history.json()[0]["previous_status"] == "available"
    assert history.json()[0]["new_status"] == "linked"


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


async def test_library_version_events_record_mutations(
    api_client: AsyncClient,
    db_session: Session,
) -> None:
    async with api_client as client:
        created = await client.post(
            "/api/v1/library",
            json={"title": "Versioned Story", "content_type": "Audiobook"},
        )
        item_id = created.json()["id"]
        await client.put(
            f"/api/v1/library/{item_id}/settings",
            json={"playlist_shuffle_tracks": True},
        )
        await client.post(
            f"/api/v1/library/{item_id}/tracks",
            json={"title": "Chapter One", "track_number": 1, "duration_seconds": 180},
        )
        versions = await client.get(f"/api/v1/library/{item_id}/versions")

    assert versions.status_code == 200
    payload = versions.json()
    assert [event["version_number"] for event in payload] == [3, 2, 1]
    assert payload[0]["event_type"] == "track_created"
    assert "Chapter One" in payload[0]["snapshot_json"]
    assert payload[1]["event_type"] == "settings_updated"
    assert payload[2]["event_type"] == "library_item_created"

    event_count = len(db_session.scalars(select(VersionEvent)).all())
    assert event_count == 3


async def test_library_version_restore_creates_new_version(
    api_client: AsyncClient,
) -> None:
    async with api_client as client:
        created = await client.post(
            "/api/v1/library",
            json={
                "title": "Original Story",
                "content_type": "Audiobook",
                "cover_art_path": "/art/original.png",
                "playlist_shuffle_tracks": False,
            },
        )
        item_id = created.json()["id"]
        first_track = await client.post(
            f"/api/v1/library/{item_id}/tracks",
            json={
                "title": "Original Chapter",
                "track_number": 1,
                "duration_seconds": 120,
                "icon_path": "/icons/original.png",
            },
        )
        await client.post(
            f"/api/v1/library/{item_id}/split-points",
            json={"timestamp_seconds": 60, "title": "Original Split", "part_number": 2},
        )
        versions_before_update = await client.get(f"/api/v1/library/{item_id}/versions")
        restore_target_id = next(
            event["id"]
            for event in versions_before_update.json()
            if event["event_type"] == "track_created"
        )

        await client.put(
            f"/api/v1/library/{item_id}/settings",
            json={
                "cover_art_path": "/art/updated.png",
                "playlist_shuffle_tracks": True,
                "notes": "Updated notes",
            },
        )
        await client.put(
            f"/api/v1/library/{item_id}/tracks/{first_track.json()['id']}",
            json={"title": "Updated Chapter", "track_number": 3},
        )
        await client.post(
            f"/api/v1/library/{item_id}/tracks",
            json={"title": "Extra Chapter", "track_number": 4},
        )

        restored = await client.post(f"/api/v1/library/{item_id}/versions/{restore_target_id}/restore")
        detail = await client.get(f"/api/v1/library/{item_id}")
        versions_after_restore = await client.get(f"/api/v1/library/{item_id}/versions")

    assert restored.status_code == 200
    restored_payload = restored.json()
    assert restored_payload["restored_from_version_id"] == restore_target_id
    assert restored_payload["version_event"]["event_type"] == "version_restored"

    detail_payload = detail.json()
    assert detail_payload["item"]["cover_art_path"] == "/art/original.png"
    assert detail_payload["item"]["playlist_shuffle_tracks"] is False
    assert [track["title"] for track in detail_payload["tracks"]] == ["Original Chapter"]
    assert detail_payload["tracks"][0]["track_number"] == 1
    assert detail_payload["split_points"] == []

    versions_payload = versions_after_restore.json()
    assert versions_payload[0]["event_type"] == "version_restored"
    assert len(versions_payload) == 7


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
                "source_start_seconds": 5,
                "source_end_seconds": 125,
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
    assert updated.json()["source_start_seconds"] == 5
    assert updated.json()["source_end_seconds"] == 125
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


async def test_card_plan_can_be_saved_and_reloaded(api_client: AsyncClient) -> None:
    async with api_client as client:
        created = await client.post(
            "/api/v1/library",
            json={"title": "Planned Book", "content_type": "Audiobook"},
        )
        item_id = created.json()["id"]
        first = await client.post(
            f"/api/v1/library/{item_id}/tracks",
            json={"title": "Chapter 1", "track_number": 1, "duration_seconds": 1200},
        )
        second = await client.post(
            f"/api/v1/library/{item_id}/tracks",
            json={"title": "Chapter 2", "track_number": 2, "duration_seconds": 1800},
        )
        saved = await client.put(
            f"/api/v1/library/{item_id}/card-plan",
            json={
                "parts": [
                    {"part_number": 1, "title": "Planned Book - Part 1", "track_ids": [second.json()["id"]]},
                    {"part_number": 2, "title": "Planned Book - Part 2", "track_ids": [first.json()["id"]]},
                ]
            },
        )
        reloaded = await client.get(f"/api/v1/library/{item_id}/card-plan/saved")
        versions = await client.get(f"/api/v1/library/{item_id}/versions")

    assert saved.status_code == 200
    assert saved.json()["parts"][0]["tracks"][0]["title"] == "Chapter 2"
    assert saved.json()["parts"][1]["tracks"][0]["title"] == "Chapter 1"
    assert reloaded.status_code == 200
    assert reloaded.json()["parts"][0]["title"] == "Planned Book - Part 1"
    assert versions.json()[0]["event_type"] == "card_plan_saved"


async def test_library_processing_can_be_queued(api_client: AsyncClient) -> None:
    async with api_client as client:
        created = await client.post(
            "/api/v1/library",
            json={"title": "Ready Book", "content_type": "Audiobook"},
        )
        item_id = created.json()["id"]
        empty_response = await client.post(f"/api/v1/library/{item_id}/process")
        await client.post(
            f"/api/v1/library/{item_id}/tracks",
            json={
                "title": "Chapter One",
                "source_path": "/imports/book.m4b",
                "source_start_seconds": 0,
                "source_end_seconds": 60,
                "track_number": 1,
                "duration_seconds": 60,
            },
        )
        queued = await client.post(f"/api/v1/library/{item_id}/process")
        detail = await client.get(f"/api/v1/library/{item_id}")

    assert empty_response.status_code == 409
    assert queued.status_code == 202
    assert queued.json()["type"] == "transcode_audio"
    assert queued.json()["related_library_item_id"] == item_id
    assert detail.json()["item"]["status"] == "processing_queued"


async def test_library_detail_includes_processed_assets(
    api_client: AsyncClient,
    db_session: Session,
) -> None:
    item = LibraryItem(title="Processed Detail", content_type="Audiobook", status="processed")
    db_session.add(item)
    db_session.flush()
    asset = ProcessedAsset(
        library_item_id=item.id,
        source_path="/imports/book.m4b",
        output_path="/processed/book.mp3",
        codec="mp3",
        bitrate_kbps=96,
        channels=1,
        duration_seconds=60,
        size_bytes=1234,
        checksum_sha256="a" * 64,
        profile="spoken_word",
        settings_json='{"profile":"spoken_word"}',
    )
    db_session.add(asset)
    db_session.commit()

    async with api_client as client:
        detail = await client.get(f"/api/v1/library/{item.id}")

    assert detail.status_code == 200
    assert detail.json()["processed_assets"][0]["output_path"] == "/processed/book.mp3"
    assert detail.json()["processed_assets"][0]["bitrate_kbps"] == 96


async def test_cover_art_upload_sets_library_cover_path(
    api_client: AsyncClient,
    db_session: Session,
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
        detail = await client.get(f"/api/v1/library/{item_id}")

    assert response.status_code == 200
    cover_path = response.json()["cover_art_path"]
    assert cover_path.startswith(import_storage_paths["artwork"])
    assert Path(cover_path).read_bytes() == b"png bytes"

    assert detail.status_code == 200
    assert detail.json()["artwork_assets"][0]["kind"] == "source"
    assert db_session.scalar(select(ArtworkAsset).where(ArtworkAsset.library_item_id == item_id)) is not None


async def test_artwork_pixelise_can_be_queued(api_client: AsyncClient) -> None:
    async with api_client as client:
        created = await client.post(
            "/api/v1/library",
            json={
                "title": "Pixel Cover",
                "content_type": "Story Collection",
                "cover_art_path": "/art/source.png",
            },
        )
        item_id = created.json()["id"]
        response = await client.post(f"/api/v1/library/{item_id}/artwork/pixelise")

    assert response.status_code == 202
    payload = response.json()
    assert payload["type"] == "pixelise_artwork"
    assert payload["related_library_item_id"] == item_id


async def test_yoto_config_and_playlist_preview(api_client: AsyncClient) -> None:
    async with api_client as client:
        config = await client.get("/api/v1/yoto/config")
        created = await client.post(
            "/api/v1/library",
            json={
                "title": "Bedtime Mix",
                "content_type": "Custom Playlist",
                "cover_art_path": "/art/bedtime.png",
                "playlist_always_play_from_start": True,
            },
        )
        item_id = created.json()["id"]
        await client.post(
            f"/api/v1/library/{item_id}/tracks",
            json={
                "title": "Story One",
                "track_number": 1,
                "duration_seconds": 120,
                "icon_path": "/icons/story.png",
            },
        )
        preview = await client.get(f"/api/v1/yoto/library/{item_id}/playlist-preview")

    assert config.status_code == 200
    assert config.json()["enabled"] is False
    assert config.json()["api_base_url"] == "https://api.yotoplay.com"
    assert preview.status_code == 200
    payload = preview.json()
    assert payload["live_api_call"] is False
    assert payload["payload"]["title"] == "Bedtime Mix"
    assert payload["payload"]["playback"]["always_play_from_start"] is True
    assert payload["payload"]["chapters"][0]["title"] == "Story One"
    assert payload["payload"]["chapters"][0]["offline_available"] is True


async def test_yoto_oauth_scaffold_records_local_credential_state(
    api_client: AsyncClient,
    db_session: Session,
) -> None:
    async with api_client as client:
        initial = await client.get("/api/v1/yoto/credentials/status")
        missing_config = await client.post(
            "/api/v1/yoto/credentials/start",
            json={
                "account_label": "Family Yoto",
                "code_challenge": "a" * 43,
                "code_challenge_method": "S256",
            },
        )
        await client.put(
            "/api/v1/settings",
            json={
                "yoto_client_id": "client-test",
                "yoto_redirect_uri": "http://localhost:5175/settings/yoto/callback",
                "yoto_oauth_scope": "openid offline_access playlist.write",
            },
        )
        started = await client.post(
            "/api/v1/yoto/credentials/start",
            json={
                "account_label": "Family Yoto",
                "code_challenge": "b" * 43,
                "code_challenge_method": "S256",
            },
        )
        status_response = await client.get("/api/v1/yoto/credentials/status")
        disconnected = await client.post("/api/v1/yoto/credentials/disconnect")

    assert initial.status_code == 200
    assert initial.json()["status"] == "not_connected"
    assert missing_config.status_code == 422
    assert started.status_code == 202
    payload = started.json()
    assert payload["live_api_call"] is False
    parsed_auth_url = urlparse(payload["authorization_url"])
    auth_params = parse_qs(parsed_auth_url.query)
    assert parsed_auth_url.path == "/authorize"
    assert auth_params["audience"] == ["https://api.yotoplay.com"]
    assert auth_params["client_id"] == ["client-test"]
    assert auth_params["redirect_uri"] == ["http://localhost:5175/settings/yoto/callback"]
    assert auth_params["code_challenge"] == ["b" * 43]
    assert auth_params["code_challenge_method"] == ["S256"]
    assert auth_params["scope"] == ["openid offline_access playlist.write"]
    assert payload["oauth_state"] == auth_params["state"][0]
    assert payload["credential"]["status"] == "authorization_started"
    assert status_response.json()["account_label"] == "Family Yoto"
    assert disconnected.json()["status"] == "revoked"

    credential = db_session.scalar(select(YotoCredentialState))
    assert credential is not None
    assert credential.token_storage_ref is None
    assert credential.status == "revoked"


async def test_yoto_oauth_callback_exchanges_code_without_persisting_tokens(
    api_client: AsyncClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    header = base64.urlsafe_b64encode(json.dumps({"alg": "none"}).encode()).decode().rstrip("=")
    body = base64.urlsafe_b64encode(json.dumps({"sub": "family-account-12345678", "exp": 4_102_444_800}).encode()).decode().rstrip("=")
    access_token = f"{header}.{body}."

    async def fake_exchange_oauth_code(**_: object) -> dict[str, object]:
        return {
            "access_token": access_token,
            "refresh_token": "refresh-token-not-stored",
            "token_type": "Bearer",
            "scope": "openid offline_access family:library:view",
            "expires_in": 3600,
        }

    monkeypatch.setattr(yoto_routes, "_exchange_oauth_code", fake_exchange_oauth_code)

    async with api_client as client:
        await client.put(
            "/api/v1/settings",
            json={
                "yoto_client_id": "client-test",
                "yoto_redirect_uri": "http://localhost:5175/settings/yoto/callback",
                "yoto_oauth_scope": "openid offline_access family:library:view",
            },
        )
        started = await client.post(
            "/api/v1/yoto/credentials/start",
            json={
                "account_label": "Family Yoto",
                "code_challenge": "c" * 43,
                "code_challenge_method": "S256",
            },
        )
        completed = await client.post(
            "/api/v1/yoto/credentials/callback",
            json={
                "code": "auth-code",
                "state": started.json()["oauth_state"],
                "code_verifier": "v" * 43,
            },
        )

    assert completed.status_code == 200
    payload = completed.json()
    assert payload["live_api_call"] is True
    assert payload["credential"]["status"] == "connected_tested"
    assert payload["credential"]["token_storage_ref"].startswith("not_persisted:browser_pkce:")
    assert payload["credential"]["masked_account_id"] == "12345678"
    assert "not persisted" in payload["credential"]["error_summary"]

    credential = db_session.scalar(select(YotoCredentialState))
    assert credential is not None
    assert credential.oauth_state is None
    assert credential.authorization_url is None
    assert credential.token_storage_ref == f"not_persisted:browser_pkce:{credential.id}"


async def test_yoto_playlist_queue_persists_draft_and_job(
    api_client: AsyncClient,
    db_session: Session,
) -> None:
    async with api_client as client:
        created = await client.post(
            "/api/v1/library",
            json={"title": "Queue Mix", "content_type": "Custom Playlist"},
        )
        item_id = created.json()["id"]
        await client.post(
            f"/api/v1/library/{item_id}/tracks",
            json={"title": "Chapter One", "track_number": 1, "duration_seconds": 60},
        )
        queued = await client.post(f"/api/v1/yoto/library/{item_id}/playlists")
        listed = await client.get(f"/api/v1/yoto/library/{item_id}/playlists")

    assert queued.status_code == 202
    payload = queued.json()
    assert payload["live_api_call"] is False
    assert payload["playlist"]["status"] == "queued"
    assert payload["playlist"]["payload"]["chapters"][0]["title"] == "Chapter One"
    assert payload["job"]["type"] == "create_yoto_playlist"
    assert listed.status_code == 200
    assert listed.json()[0]["title"] == "Queue Mix"

    draft = db_session.scalar(select(YotoPlaylistDraft).where(YotoPlaylistDraft.library_item_id == item_id))
    job = db_session.scalar(select(Job).where(Job.related_library_item_id == item_id).where(Job.type == "create_yoto_playlist"))
    item = db_session.get(LibraryItem, item_id)
    assert draft is not None
    assert job is not None
    assert draft.related_job_id == job.id
    assert item is not None
    assert item.status == "yoto_playlist_queued"


async def test_yoto_playlist_versions_are_recorded_and_restorable(
    api_client: AsyncClient,
    db_session: Session,
) -> None:
    async with api_client as client:
        created = await client.post(
            "/api/v1/library",
            json={"title": "Versioned Mix", "content_type": "Custom Playlist"},
        )
        item_id = created.json()["id"]
        await client.post(
            f"/api/v1/library/{item_id}/tracks",
            json={"title": "First", "track_number": 1, "duration_seconds": 60},
        )
        queued = await client.post(f"/api/v1/yoto/library/{item_id}/playlists")
        playlist_id = queued.json()["playlist"]["id"]
        versions = await client.get(f"/api/v1/yoto/playlists/{playlist_id}/versions")

        draft = db_session.get(YotoPlaylistDraft, playlist_id)
        assert draft is not None
        draft.title = "Changed Mix"
        draft.payload_json = '{"title":"Changed Mix","chapters":[]}'
        db_session.add(
            YotoPlaylistVersion(
                playlist_draft_id=draft.id,
                library_item_id=item_id,
                version_number=2,
                title=draft.title,
                status="edited",
                summary="Edited locally.",
                source_event="manual_test_edit",
                payload_json=draft.payload_json,
            )
        )
        db_session.commit()

        restored = await client.post(f"/api/v1/yoto/playlists/{playlist_id}/versions/{versions.json()[0]['id']}/restore")
        restored_versions = await client.get(f"/api/v1/yoto/playlists/{playlist_id}/versions")

    assert versions.status_code == 200
    assert versions.json()[0]["version_number"] == 1
    assert versions.json()[0]["payload"]["title"] == "Versioned Mix"
    assert restored.status_code == 201
    assert restored.json()["version_number"] == 3
    assert restored.json()["status"] == "restored"
    assert restored.json()["payload"]["title"] == "Versioned Mix"
    assert restored_versions.json()[0]["version_number"] == 3

    refreshed_draft = db_session.get(YotoPlaylistDraft, playlist_id)
    assert refreshed_draft is not None
    assert refreshed_draft.title == "Versioned Mix"
