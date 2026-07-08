from typing import Annotated
import json

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import get_db_session
from app.integrations.yoto.playlist import build_playlist_preview
from app.models import Job, LibraryItem, PlaylistTrack, Setting, VersionEvent, YotoPlaylistDraft
from app.schemas.foundation import (
    JobResponse,
    QueueYotoPlaylistResponse,
    YotoConfigResponse,
    YotoPlaylistDraftResponse,
    YotoPlaylistPreviewResponse,
)


router = APIRouter()


def _setting(db: Session, key: str, fallback: str = "") -> str:
    setting = db.scalar(select(Setting).where(Setting.key == key))
    return setting.value if setting is not None else fallback


def _tracks_for_item(db: Session, item: LibraryItem) -> list[PlaylistTrack]:
    return list(
        db.scalars(
            select(PlaylistTrack)
            .where(PlaylistTrack.library_item_id == item.id)
            .order_by(PlaylistTrack.track_number.asc(), PlaylistTrack.id.asc())
        )
    )


def _draft_response(draft: YotoPlaylistDraft) -> YotoPlaylistDraftResponse:
    try:
        payload = json.loads(draft.payload_json)
    except json.JSONDecodeError:
        payload = {"error": "Stored playlist payload is not valid JSON."}
    return YotoPlaylistDraftResponse(
        id=draft.id,
        library_item_id=draft.library_item_id,
        related_job_id=draft.related_job_id,
        title=draft.title,
        status=draft.status,
        payload=payload if isinstance(payload, dict) else {"payload": payload},
        remote_playlist_id=draft.remote_playlist_id,
        remote_playlist_uri=draft.remote_playlist_uri,
        last_error=draft.last_error,
        created_at=draft.created_at,
    )


def _next_library_version(db: Session, item_id: int) -> int:
    latest_version = db.scalar(
        select(func.max(VersionEvent.version_number))
        .where(VersionEvent.entity_type == "library_item")
        .where(VersionEvent.entity_id == item_id)
    )
    return (latest_version or 0) + 1


@router.get("/config", response_model=YotoConfigResponse)
async def get_yoto_config(db: Annotated[Session, Depends(get_db_session)]) -> YotoConfigResponse:
    return YotoConfigResponse(
        enabled=_setting(db, "yoto_api_enabled", "false").lower() == "true",
        api_base_url=_setting(db, "yoto_api_base_url", "https://api.yotoplay.com"),
        auth_base_url=_setting(db, "yoto_auth_base_url", "https://login.yotoplay.com"),
        client_id_configured=bool(_setting(db, "yoto_client_id")),
        redirect_uri_configured=bool(_setting(db, "yoto_redirect_uri")),
        oauth_scope=_setting(db, "yoto_oauth_scope", "openid offline_access"),
    )


@router.get("/library/{item_id}/playlist-preview", response_model=YotoPlaylistPreviewResponse)
async def preview_yoto_playlist(
    item_id: int,
    db: Annotated[Session, Depends(get_db_session)],
) -> YotoPlaylistPreviewResponse:
    item = db.get(LibraryItem, item_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Library item not found")
    tracks = _tracks_for_item(db, item)
    return YotoPlaylistPreviewResponse(
        library_item_id=item.id,
        payload=build_playlist_preview(item, tracks),
        live_api_call=False,
    )


@router.get("/library/{item_id}/playlists", response_model=list[YotoPlaylistDraftResponse])
async def list_yoto_playlists(
    item_id: int,
    db: Annotated[Session, Depends(get_db_session)],
) -> list[YotoPlaylistDraftResponse]:
    item = db.get(LibraryItem, item_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Library item not found")
    drafts = db.scalars(
        select(YotoPlaylistDraft)
        .where(YotoPlaylistDraft.library_item_id == item.id)
        .order_by(YotoPlaylistDraft.created_at.desc(), YotoPlaylistDraft.id.desc())
    )
    return [_draft_response(draft) for draft in drafts]


@router.post("/library/{item_id}/playlists", response_model=QueueYotoPlaylistResponse, status_code=202)
async def queue_yoto_playlist(
    item_id: int,
    db: Annotated[Session, Depends(get_db_session)],
) -> QueueYotoPlaylistResponse:
    item = db.get(LibraryItem, item_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Library item not found")

    tracks = _tracks_for_item(db, item)
    if not tracks:
        raise HTTPException(status_code=422, detail="Add or inspect tracks before creating a Yoto playlist.")

    payload = build_playlist_preview(item, tracks)
    draft = YotoPlaylistDraft(
        library_item_id=item.id,
        title=str(payload.get("title") or item.title),
        status="queued",
        payload_json=json.dumps(payload, sort_keys=True),
    )
    db.add(draft)
    db.flush()

    job = Job(
        type="create_yoto_playlist",
        status="queued",
        progress_percent=0,
        progress_message="Queued local Yoto playlist draft upload",
        related_library_item_id=item.id,
    )
    db.add(job)
    db.flush()

    draft.related_job_id = job.id
    item.status = "yoto_playlist_queued"
    item.readiness_status = "yoto_playlist_queued"
    item.readiness_detail = "Yoto playlist draft queued. Live upload will be added behind this job."
    db.add(
        VersionEvent(
            entity_type="library_item",
            entity_id=item.id,
            version_number=_next_library_version(db, item.id),
            event_type="yoto_playlist_queued",
            summary="Queued local Yoto playlist draft.",
            snapshot_json=json.dumps({"item_id": item.id, "playlist_draft_id": draft.id}, sort_keys=True),
        )
    )
    db.commit()
    db.refresh(draft)
    db.refresh(job)
    db.refresh(item)

    return QueueYotoPlaylistResponse(
        playlist=_draft_response(draft),
        job=JobResponse.model_validate(job, from_attributes=True),
        live_api_call=False,
    )
