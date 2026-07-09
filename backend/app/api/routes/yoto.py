from typing import Annotated
import json
from secrets import token_urlsafe
from urllib.parse import urlencode, urljoin

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import get_db_session
from app.integrations.yoto.playlist import build_playlist_preview
from app.models import (
    Job,
    LibraryItem,
    PlaylistTrack,
    Setting,
    VersionEvent,
    YotoCredentialState,
    YotoPlaylistDraft,
    YotoPlaylistVersion,
)
from app.schemas.foundation import (
    JobResponse,
    QueueYotoPlaylistResponse,
    StartYotoOAuthRequest,
    StartYotoOAuthResponse,
    YotoConfigResponse,
    YotoCredentialStatusResponse,
    YotoPlaylistDraftResponse,
    YotoPlaylistPreviewResponse,
    YotoPlaylistVersionResponse,
)


router = APIRouter()


def _setting(db: Session, key: str, fallback: str = "") -> str:
    setting = db.scalar(select(Setting).where(Setting.key == key))
    return setting.value if setting is not None else fallback


def _latest_credential(db: Session) -> YotoCredentialState | None:
    return db.scalar(
        select(YotoCredentialState).order_by(
            YotoCredentialState.updated_at.desc(),
            YotoCredentialState.id.desc(),
        )
    )


def _credential_response(db: Session, credential: YotoCredentialState | None) -> YotoCredentialStatusResponse:
    enabled = _setting(db, "yoto_api_enabled", "false").lower() == "true"
    client_id = _setting(db, "yoto_client_id")
    redirect_uri = _setting(db, "yoto_redirect_uri")
    scopes = _setting(db, "yoto_oauth_scope", "openid offline_access")
    if credential is None:
        return YotoCredentialStatusResponse(
            id=None,
            account_label="Household Yoto",
            status="not_connected",
            token_storage_ref=None,
            masked_account_id=None,
            masked_email=None,
            scopes=scopes,
            authorization_url=None,
            oauth_state=None,
            last_refreshed_at=None,
            expires_at=None,
            error_summary=None,
            enabled=enabled,
            client_id_configured=bool(client_id),
            redirect_uri_configured=bool(redirect_uri),
            live_api_call=False,
        )
    return YotoCredentialStatusResponse(
        id=credential.id,
        account_label=credential.account_label,
        status=credential.status,
        token_storage_ref=credential.token_storage_ref,
        masked_account_id=credential.masked_account_id,
        masked_email=credential.masked_email,
        scopes=credential.scopes,
        authorization_url=credential.authorization_url,
        oauth_state=credential.oauth_state,
        last_refreshed_at=credential.last_refreshed_at,
        expires_at=credential.expires_at,
        error_summary=credential.error_summary,
        enabled=enabled,
        client_id_configured=bool(client_id),
        redirect_uri_configured=bool(redirect_uri),
        live_api_call=False,
    )


def _authorization_url(db: Session, oauth_state: str) -> str:
    auth_base_url = _setting(db, "yoto_auth_base_url", "https://login.yotoplay.com").rstrip("/")
    query = urlencode(
        {
            "response_type": "code",
            "client_id": _setting(db, "yoto_client_id"),
            "redirect_uri": _setting(db, "yoto_redirect_uri"),
            "scope": _setting(db, "yoto_oauth_scope", "openid offline_access"),
            "state": oauth_state,
        }
    )
    return f"{urljoin(auth_base_url + '/', 'oauth2/authorize')}?{query}"


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


def _playlist_version_response(version: YotoPlaylistVersion) -> YotoPlaylistVersionResponse:
    try:
        payload = json.loads(version.payload_json)
    except json.JSONDecodeError:
        payload = {"error": "Stored playlist version payload is not valid JSON."}
    return YotoPlaylistVersionResponse(
        id=version.id,
        playlist_draft_id=version.playlist_draft_id,
        library_item_id=version.library_item_id,
        version_number=version.version_number,
        title=version.title,
        status=version.status,
        summary=version.summary,
        source_event=version.source_event,
        payload=payload if isinstance(payload, dict) else {"payload": payload},
        created_at=version.created_at,
    )


def _next_library_version(db: Session, item_id: int) -> int:
    latest_version = db.scalar(
        select(func.max(VersionEvent.version_number))
        .where(VersionEvent.entity_type == "library_item")
        .where(VersionEvent.entity_id == item_id)
    )
    return (latest_version or 0) + 1


def _next_playlist_version(db: Session, draft_id: int) -> int:
    latest_version = db.scalar(
        select(func.max(YotoPlaylistVersion.version_number)).where(YotoPlaylistVersion.playlist_draft_id == draft_id)
    )
    return (latest_version or 0) + 1


def _record_playlist_version(
    db: Session,
    draft: YotoPlaylistDraft,
    *,
    status: str,
    summary: str,
    source_event: str,
) -> YotoPlaylistVersion:
    version = YotoPlaylistVersion(
        playlist_draft_id=draft.id,
        library_item_id=draft.library_item_id,
        version_number=_next_playlist_version(db, draft.id),
        title=draft.title,
        status=status,
        summary=summary,
        source_event=source_event,
        payload_json=draft.payload_json,
    )
    db.add(version)
    return version


@router.get("/credentials/status", response_model=YotoCredentialStatusResponse)
async def get_yoto_credential_status(
    db: Annotated[Session, Depends(get_db_session)],
) -> YotoCredentialStatusResponse:
    return _credential_response(db, _latest_credential(db))


@router.post("/credentials/start", response_model=StartYotoOAuthResponse, status_code=202)
async def start_yoto_oauth(
    payload: StartYotoOAuthRequest,
    db: Annotated[Session, Depends(get_db_session)],
) -> StartYotoOAuthResponse:
    if not _setting(db, "yoto_client_id"):
        raise HTTPException(status_code=422, detail="Set a Yoto client ID before preparing OAuth.")
    if not _setting(db, "yoto_redirect_uri"):
        raise HTTPException(status_code=422, detail="Set a Yoto redirect URI before preparing OAuth.")

    credential = _latest_credential(db)
    if credential is None:
        credential = YotoCredentialState(account_label=payload.account_label)
    credential.account_label = payload.account_label
    credential.status = "authorization_started"
    credential.scopes = _setting(db, "yoto_oauth_scope", "openid offline_access")
    credential.oauth_state = token_urlsafe(24)
    credential.authorization_url = _authorization_url(db, credential.oauth_state)
    credential.error_summary = None
    db.add(credential)
    db.commit()
    db.refresh(credential)
    return StartYotoOAuthResponse(
        credential=_credential_response(db, credential),
        authorization_url=credential.authorization_url or "",
        live_api_call=False,
    )


@router.post("/credentials/disconnect", response_model=YotoCredentialStatusResponse)
async def disconnect_yoto_credentials(
    db: Annotated[Session, Depends(get_db_session)],
) -> YotoCredentialStatusResponse:
    credential = _latest_credential(db)
    if credential is None:
        return _credential_response(db, None)
    credential.status = "revoked"
    credential.token_storage_ref = None
    credential.authorization_url = None
    credential.oauth_state = None
    credential.error_summary = "Disconnected locally. No live Yoto revoke call was made."
    db.add(credential)
    db.commit()
    db.refresh(credential)
    return _credential_response(db, credential)


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


@router.get("/playlists/{playlist_id}/versions", response_model=list[YotoPlaylistVersionResponse])
async def list_yoto_playlist_versions(
    playlist_id: int,
    db: Annotated[Session, Depends(get_db_session)],
) -> list[YotoPlaylistVersionResponse]:
    draft = db.get(YotoPlaylistDraft, playlist_id)
    if draft is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Yoto playlist draft not found")
    versions = db.scalars(
        select(YotoPlaylistVersion)
        .where(YotoPlaylistVersion.playlist_draft_id == draft.id)
        .order_by(YotoPlaylistVersion.version_number.desc(), YotoPlaylistVersion.id.desc())
    )
    return [_playlist_version_response(version) for version in versions]


@router.post(
    "/playlists/{playlist_id}/versions/{version_id}/restore",
    response_model=YotoPlaylistVersionResponse,
    status_code=201,
)
async def restore_yoto_playlist_version(
    playlist_id: int,
    version_id: int,
    db: Annotated[Session, Depends(get_db_session)],
) -> YotoPlaylistVersionResponse:
    draft = db.get(YotoPlaylistDraft, playlist_id)
    if draft is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Yoto playlist draft not found")
    source_version = db.get(YotoPlaylistVersion, version_id)
    if source_version is None or source_version.playlist_draft_id != draft.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Yoto playlist version not found")

    draft.title = source_version.title
    draft.payload_json = source_version.payload_json
    draft.status = "restored"
    draft.last_error = None
    restored = _record_playlist_version(
        db,
        draft,
        status="restored",
        summary=f"Restored from playlist version {source_version.version_number}.",
        source_event="playlist_version_restored",
    )
    db.commit()
    db.refresh(restored)
    return _playlist_version_response(restored)


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
    _record_playlist_version(
        db,
        draft,
        status="queued",
        summary="Initial local Yoto playlist draft.",
        source_event="yoto_playlist_queued",
    )
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
