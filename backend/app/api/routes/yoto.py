import asyncio
import base64
from datetime import datetime, timedelta, timezone
import hashlib
import json
import logging
import mimetypes
from pathlib import Path
from secrets import token_urlsafe
from typing import Annotated, Any
from urllib.parse import urlencode, urljoin
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import get_db_session
from app.integrations.yoto.playlist import build_playlist_preview
from app.models import (
    Job,
    LibraryItem,
    PhysicalCard,
    PlaylistTrack,
    ProcessedAsset,
    Setting,
    VersionEvent,
    YotoCredentialState,
    YotoPlaylistDraft,
    YotoPlaylistVersion,
)
from app.services.yoto_tokens import (
    StoredYotoTokens,
    YotoTokenStoreError,
    delete_tokens_from_secret,
    load_tokens_from_secret,
    save_tokens_to_secret,
)
from app.schemas.foundation import (
    CompleteYotoOAuthRequest,
    CompleteYotoOAuthResponse,
    CreateLiveYotoPlaylistRequest,
    CreateLiveYotoPlaylistResponse,
    JobResponse,
    QueueYotoPlaylistResponse,
    StartYotoOAuthRequest,
    StartYotoOAuthResponse,
    UpdateYotoPlaylistRemoteLinkRequest,
    YotoApiDebugRequest,
    YotoApiDebugResponse,
    YotoConfigResponse,
    YotoCredentialStatusResponse,
    YotoCredentialProbeResponse,
    YotoPlaylistDraftResponse,
    YotoPlaylistPreviewResponse,
    YotoPlaylistRemotePayloadResponse,
    YotoPlaylistVersionResponse,
)


router = APIRouter()
logger = logging.getLogger(__name__)


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


def _authorization_url(db: Session, oauth_state: str, code_challenge: str) -> str:
    auth_base_url = _setting(db, "yoto_auth_base_url", "https://login.yotoplay.com").rstrip("/")
    query = urlencode(
        {
            "audience": _setting(db, "yoto_api_base_url", "https://api.yotoplay.com"),
            "response_type": "code",
            "client_id": _setting(db, "yoto_client_id"),
            "redirect_uri": _setting(db, "yoto_redirect_uri"),
            "scope": _setting(db, "yoto_oauth_scope", "openid offline_access"),
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
            "state": oauth_state,
        }
    )
    return f"{urljoin(auth_base_url + '/', 'authorize')}?{query}"


def _decode_jwt_payload(token: str) -> dict[str, Any]:
    parts = token.split(".")
    if len(parts) < 2:
        return {}
    payload = parts[1]
    padding = "=" * (-len(payload) % 4)
    try:
        decoded = base64.urlsafe_b64decode(f"{payload}{padding}")
        value = json.loads(decoded)
    except (ValueError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


async def _exchange_oauth_code(
    *,
    auth_base_url: str,
    client_id: str,
    redirect_uri: str,
    code: str,
    code_verifier: str,
) -> dict[str, Any]:
    token_url = urljoin(auth_base_url.rstrip("/") + "/", "oauth/token")
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            token_url,
            data={
                "grant_type": "authorization_code",
                "client_id": client_id,
                "code_verifier": code_verifier,
                "code": code,
                "redirect_uri": redirect_uri,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
    if response.status_code >= 400:
        detail = response.text[:500] if response.text else "Yoto token exchange failed."
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=detail)
    payload = response.json()
    if not isinstance(payload, dict) or not payload.get("access_token"):
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Yoto token response did not include an access token.")
    return payload


def _safe_oauth_exchange_summary(*, client_id: str, redirect_uri: str, provider_detail: str) -> str:
    masked_client_id = (
        f"{client_id[:4]}...{client_id[-4:]}" if len(client_id) > 8 else client_id or "missing"
    )
    provider_message = provider_detail.strip() if provider_detail else "unknown provider error"
    if len(provider_message) > 240:
        provider_message = f"{provider_message[:237]}..."

    return (
        "Yoto OAuth token exchange failed. "
        f"Provider said: {provider_message}. "
        f"Client ID: {masked_client_id}. "
        f"Redirect URI: {redirect_uri}. "
        "Most likely causes are a reused authorization code, an exact redirect URI mismatch, or a PKCE verifier mismatch."
    )


def _masked_client_id(client_id: str) -> str:
    return f"{client_id[:4]}...{client_id[-4:]}" if len(client_id) > 8 else client_id or "missing"


def _token_expired(expires_at: datetime | None) -> bool:
    if expires_at is None:
        return False
    expires_at_utc = expires_at.astimezone(timezone.utc) if expires_at.tzinfo else expires_at.replace(tzinfo=timezone.utc)
    return expires_at_utc <= datetime.now(timezone.utc) + timedelta(seconds=60)


async def _refresh_oauth_tokens(
    *,
    auth_base_url: str,
    client_id: str,
    refresh_token: str,
) -> dict[str, Any]:
    token_url = urljoin(auth_base_url.rstrip("/") + "/", "oauth/token")
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            token_url,
            data={
                "grant_type": "refresh_token",
                "client_id": client_id,
                "refresh_token": refresh_token,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
    if response.status_code >= 400:
        detail = response.text[:500] if response.text else "Yoto token refresh failed."
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=detail)
    payload = response.json()
    if not isinstance(payload, dict) or not payload.get("access_token"):
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Yoto refresh response did not include an access token.")
    return payload


def _tokens_from_payload(
    token_payload: dict[str, Any],
    *,
    existing_refresh_token: str | None = None,
) -> StoredYotoTokens:
    access_token = str(token_payload["access_token"])
    decoded = _decode_jwt_payload(access_token)
    expires_in = token_payload.get("expires_in")
    expires_at: datetime | None = None
    if isinstance(decoded.get("exp"), int):
        expires_at = datetime.fromtimestamp(decoded["exp"], tz=timezone.utc)
    elif isinstance(expires_in, int):
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
    return StoredYotoTokens(
        access_token=access_token,
        refresh_token=str(token_payload.get("refresh_token") or existing_refresh_token) if (token_payload.get("refresh_token") or existing_refresh_token) else None,
        token_type=str(token_payload.get("token_type")) if token_payload.get("token_type") else None,
        scope=str(token_payload.get("scope")) if token_payload.get("scope") else None,
        id_token=str(token_payload.get("id_token")) if token_payload.get("id_token") else None,
        expires_at=expires_at,
    )


def _probe_definition(*, granted_scopes: str, configured_scopes: str) -> tuple[str, str]:
    scope_values = set((granted_scopes or configured_scopes).split())
    combined_scope_values = set((f"{granted_scopes} {configured_scopes}").split())
    scope_values = scope_values or combined_scope_values
    if {"user:content:view", "user:content:manage"} & scope_values:
        return ("User MYO content", "/content/mine?showdeleted=false")
    if {"family:library:view", "family:library:manage"} & scope_values:
        return ("Family library groups", "/card/family/library/groups")
    if {"family:devices:view", "family:devices:manage", "family:devices:control"} & scope_values:
        return ("Family devices", "/device-v2/devices/mine")
    logger.warning(
        "Yoto probe scope mismatch: granted_scopes=%s configured_scopes=%s combined_scopes=%s",
        granted_scopes or "<empty>",
        configured_scopes or "<empty>",
        " ".join(sorted(combined_scope_values)) or "<empty>",
    )
    raise HTTPException(
        status_code=409,
        detail="No supported Yoto debug probe matches the currently granted scopes. Add one of: family:library:view, user:content:view, or family:devices:view.",
    )


def _response_excerpt(payload: Any) -> str:
    text = json.dumps(payload, ensure_ascii=True) if not isinstance(payload, str) else payload
    return text[:1000]


def _response_json(payload: Any) -> dict[str, object] | list[object] | None:
    if isinstance(payload, dict):
        return payload
    if isinstance(payload, list):
        return payload
    return None


async def _call_yoto_api(
    *,
    method: str,
    api_base_url: str,
    relative_url: str,
    access_token: str,
    json_body: Any | None = None,
) -> tuple[int, Any]:
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.request(
            method=method,
            url=urljoin(api_base_url.rstrip("/") + "/", relative_url.lstrip("/")),
            headers={"Authorization": f"Bearer {access_token}"},
            json=json_body,
        )
    try:
        payload = response.json()
    except ValueError:
        payload = response.text[:1000] if response.text else ""
    return response.status_code, payload


async def _refresh_stored_tokens(
    *,
    db: Session,
    credential: YotoCredentialState,
    stored_tokens: StoredYotoTokens,
) -> StoredYotoTokens:
    if not stored_tokens.refresh_token:
        raise HTTPException(status_code=409, detail="Stored Yoto access token is expired and no refresh token is available.")
    refresh_payload = await _refresh_oauth_tokens(
        auth_base_url=_setting(db, "yoto_auth_base_url", "https://login.yotoplay.com"),
        client_id=_setting(db, "yoto_client_id"),
        refresh_token=stored_tokens.refresh_token,
    )
    refreshed_tokens = _tokens_from_payload(refresh_payload, existing_refresh_token=stored_tokens.refresh_token)
    credential.token_storage_ref = await save_tokens_to_secret(credential_id=credential.id, tokens=refreshed_tokens)
    credential.last_refreshed_at = datetime.now(timezone.utc)
    credential.expires_at = refreshed_tokens.expires_at
    credential.scopes = str(refresh_payload.get("scope") or credential.scopes)
    return refreshed_tokens


async def _load_live_tokens(
    *,
    db: Session,
    credential: YotoCredentialState,
) -> tuple[StoredYotoTokens, bool]:
    try:
        stored_tokens = await load_tokens_from_secret(credential.token_storage_ref or "")
    except YotoTokenStoreError as error:
        credential.status = "authorization_failed"
        credential.error_summary = f"Unable to load stored Yoto tokens: {error}"
        db.add(credential)
        db.commit()
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=credential.error_summary) from error

    refreshed = False
    if _token_expired(stored_tokens.expires_at):
        stored_tokens = await _refresh_stored_tokens(db=db, credential=credential, stored_tokens=stored_tokens)
        refreshed = True
        logger.info("Yoto live request refreshed expired token for credential=%s", credential.id)

    return stored_tokens, refreshed


async def _call_authenticated_yoto_api(
    *,
    db: Session,
    credential: YotoCredentialState,
    stored_tokens: StoredYotoTokens,
    method: str,
    relative_url: str,
    json_body: Any | None = None,
) -> tuple[int, Any, StoredYotoTokens, bool]:
    refreshed = False
    http_status, payload = await _call_yoto_api(
        method=method,
        api_base_url=_setting(db, "yoto_api_base_url", "https://api.yotoplay.com"),
        relative_url=relative_url,
        access_token=stored_tokens.access_token,
        json_body=json_body,
    )
    if http_status == 401 and stored_tokens.refresh_token:
        stored_tokens = await _refresh_stored_tokens(db=db, credential=credential, stored_tokens=stored_tokens)
        refreshed = True
        logger.info(
            "Yoto authenticated request retried after 401 for credential=%s method=%s path=%s",
            credential.id,
            method,
            relative_url,
        )
        http_status, payload = await _call_yoto_api(
            method=method,
            api_base_url=_setting(db, "yoto_api_base_url", "https://api.yotoplay.com"),
            relative_url=relative_url,
            access_token=stored_tokens.access_token,
            json_body=json_body,
        )
    return http_status, payload, stored_tokens, refreshed


def _normalize_debug_path(*, api_base_url: str, raw_path: str) -> tuple[str, str]:
    candidate = raw_path.strip()
    if not candidate:
        raise HTTPException(status_code=422, detail="A Yoto API path is required.")

    parsed_base = urlparse(api_base_url)
    parsed_candidate = urlparse(candidate)
    if parsed_candidate.scheme or parsed_candidate.netloc:
        if (parsed_candidate.scheme, parsed_candidate.netloc) != (parsed_base.scheme, parsed_base.netloc):
            raise HTTPException(status_code=422, detail="Custom Yoto debug requests must target the configured Yoto API base URL.")
        relative_path = parsed_candidate.path or "/"
        if parsed_candidate.query:
            relative_path = f"{relative_path}?{parsed_candidate.query}"
        return relative_path, candidate

    relative_path = candidate if candidate.startswith("/") else f"/{candidate}"
    absolute_url = urljoin(api_base_url.rstrip("/") + "/", relative_path.lstrip("/"))
    return relative_path, absolute_url


async def _execute_yoto_api_request(
    *,
    db: Session,
    credential: YotoCredentialState,
    label: str,
    method: str,
    relative_url: str,
    request_url: str,
    json_body: Any | None = None,
) -> YotoApiDebugResponse:
    try:
        stored_tokens = await load_tokens_from_secret(credential.token_storage_ref or "")
    except YotoTokenStoreError as error:
        credential.status = "authorization_failed"
        credential.error_summary = f"Unable to load stored Yoto tokens: {error}"
        db.add(credential)
        db.commit()
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=credential.error_summary) from error

    refreshed = False
    if _token_expired(stored_tokens.expires_at):
        stored_tokens = await _refresh_stored_tokens(db=db, credential=credential, stored_tokens=stored_tokens)
        refreshed = True
        logger.info(
            "Yoto debug request refreshed expired token for credential=%s method=%s path=%s",
            credential.id,
            method,
            relative_url,
        )

    http_status, payload = await _call_yoto_api(
        method=method,
        api_base_url=_setting(db, "yoto_api_base_url", "https://api.yotoplay.com"),
        relative_url=relative_url,
        access_token=stored_tokens.access_token,
        json_body=json_body,
    )
    if http_status == 401 and stored_tokens.refresh_token:
        stored_tokens = await _refresh_stored_tokens(db=db, credential=credential, stored_tokens=stored_tokens)
        refreshed = True
        logger.info(
            "Yoto debug request retried after 401 for credential=%s method=%s path=%s",
            credential.id,
            method,
            relative_url,
        )
        http_status, payload = await _call_yoto_api(
            method=method,
            api_base_url=_setting(db, "yoto_api_base_url", "https://api.yotoplay.com"),
            relative_url=relative_url,
            access_token=stored_tokens.access_token,
            json_body=json_body,
        )

    if 200 <= http_status < 300:
        credential.status = "connected_tested"
        credential.error_summary = f"Last Yoto debug request succeeded against {relative_url} with HTTP {http_status}."
    else:
        credential.status = "connected_error"
        credential.error_summary = f"Last Yoto debug request failed against {relative_url} with HTTP {http_status}."
    logger.info(
        "Yoto debug request finished for credential=%s label=%s method=%s path=%s http_status=%s refreshed=%s response_excerpt=%s",
        credential.id,
        label,
        method,
        relative_url,
        http_status,
        refreshed,
        _response_excerpt(payload),
    )
    db.add(credential)
    db.commit()
    db.refresh(credential)

    return YotoApiDebugResponse(
        credential=_credential_response(db, credential),
        label=label,
        method=method,
        path=relative_url,
        request_url=request_url,
        http_status=http_status,
        ok=200 <= http_status < 300,
        token_refreshed=refreshed,
        response_excerpt=_response_excerpt(payload),
        response_json=_response_json(payload),
        error_detail=None if 200 <= http_status < 300 else _response_excerpt(payload),
        live_api_call=True,
    )


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


def _best_effort_stream_format(url: str) -> str:
    parsed = urlparse(url)
    path = parsed.path.lower()
    if path.endswith(".aac") or path.endswith(".m4a"):
        return "aac"
    if path.endswith(".ogg"):
        return "ogg"
    if path.endswith(".wav"):
        return "wav"
    return "mp3"


def _best_effort_audio_format(*, codec: str | None, path: Path) -> str:
    normalized_codec = (codec or "").strip().lower()
    if normalized_codec in {"mp3", "aac", "m4a", "wav", "ogg", "flac"}:
        return normalized_codec
    extension = path.suffix.lower()
    if extension == ".m4a":
        return "aac"
    if extension.startswith("."):
        return extension[1:] or "mp3"
    return "mp3"


def _best_effort_audio_channels(*, channels: int | str | None) -> str | None:
    if isinstance(channels, str):
        normalized = channels.strip().lower()
        if normalized in {"mono", "stereo"}:
            return normalized
        if normalized == "1":
            return "mono"
        if normalized == "2":
            return "stereo"
        return None
    if channels == 1:
        return "mono"
    if channels == 2:
        return "stereo"
    return None


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _ordered_tracks_for_item(db: Session, item_id: int) -> list[PlaylistTrack]:
    return list(
        db.scalars(
            select(PlaylistTrack)
            .where(PlaylistTrack.library_item_id == item_id)
            .order_by(PlaylistTrack.track_number.asc(), PlaylistTrack.id.asc())
        )
    )


def _latest_processed_asset_by_track(db: Session, item_id: int) -> dict[int, ProcessedAsset]:
    assets = db.scalars(
        select(ProcessedAsset)
        .where(ProcessedAsset.library_item_id == item_id)
        .where(ProcessedAsset.playlist_track_id.is_not(None))
        .order_by(ProcessedAsset.created_at.desc(), ProcessedAsset.id.desc())
    )
    latest_by_track: dict[int, ProcessedAsset] = {}
    for asset in assets:
        if asset.playlist_track_id is None or asset.playlist_track_id in latest_by_track:
            continue
        latest_by_track[asset.playlist_track_id] = asset
    return latest_by_track


def _extract_yoto_upload_descriptor(upload_payload: dict[str, Any]) -> tuple[str | None, str | None]:
    nested_upload = upload_payload.get("upload")
    if isinstance(nested_upload, dict):
        upload_id = nested_upload.get("uploadId")
        upload_url = nested_upload.get("uploadUrl")
    else:
        upload_id = upload_payload.get("uploadId")
        upload_url = upload_payload.get("uploadUrl")

    normalized_upload_id = upload_id.strip() if isinstance(upload_id, str) and upload_id.strip() else None
    normalized_upload_url = upload_url.strip() if isinstance(upload_url, str) and upload_url.strip() else None
    return normalized_upload_id, normalized_upload_url


def _extract_yoto_transcode_descriptor(
    transcode_payload: dict[str, Any],
) -> tuple[str | None, dict[str, Any] | None]:
    nested_transcode = transcode_payload.get("transcode")
    if isinstance(nested_transcode, dict):
        transcoded_sha = nested_transcode.get("transcodedSha256")
        return (
            transcoded_sha.strip() if isinstance(transcoded_sha, str) and transcoded_sha.strip() else None,
            nested_transcode,
        )

    transcoded_sha = transcode_payload.get("transcodedSha256")
    return (
        transcoded_sha.strip() if isinstance(transcoded_sha, str) and transcoded_sha.strip() else None,
        None,
    )


def _match_draft_track(
    *,
    raw_chapter: dict[str, Any],
    ordered_tracks: list[PlaylistTrack],
) -> PlaylistTrack | None:
    chapter_type = str(raw_chapter.get("type") or "audio")
    source_path = raw_chapter.get("source_path")
    stream_url = raw_chapter.get("stream_url")

    for track in ordered_tracks:
        if chapter_type == "stream":
            if track.is_stream and isinstance(stream_url, str) and track.stream_url == stream_url:
                return track
        else:
            if not track.is_stream and isinstance(source_path, str) and track.source_path == source_path:
                return track

    for track in ordered_tracks:
        if chapter_type == "stream" and track.is_stream:
            return track
        if chapter_type != "stream" and not track.is_stream:
            return track
    return None


def _draft_has_processed_assets(db: Session, draft: YotoPlaylistDraft) -> bool:
    ordered_tracks = _ordered_tracks_for_item(db, draft.library_item_id)
    processed_assets = _latest_processed_asset_by_track(db, draft.library_item_id)
    try:
        payload = json.loads(draft.payload_json)
    except json.JSONDecodeError:
        return False
    chapters = payload.get("chapters") if isinstance(payload, dict) else None
    if not isinstance(chapters, list):
        return False

    for raw_chapter in chapters:
        if not isinstance(raw_chapter, dict):
            continue
        if str(raw_chapter.get("type") or "audio") == "stream":
            continue
        matched_track = _match_draft_track(raw_chapter=raw_chapter, ordered_tracks=ordered_tracks)
        if matched_track is not None and matched_track.id in processed_assets:
            return True
    return False


async def _upload_file_to_yoto_signed_url(upload_url: str, source_path: Path) -> None:
    content_type = mimetypes.guess_type(source_path.name)[0] or "application/octet-stream"
    async with httpx.AsyncClient(timeout=300) as client:
        with source_path.open("rb") as handle:
            response = await client.put(
                upload_url,
                content=handle.read(),
                headers={"Content-Type": content_type},
            )
    if response.status_code >= 400:
        detail = response.text[:500] if response.text else "Upload to Yoto media store failed."
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=detail)


async def _poll_yoto_transcoded_audio(
    *,
    db: Session,
    credential: YotoCredentialState,
    stored_tokens: StoredYotoTokens,
    upload_id: str,
) -> tuple[dict[str, Any], StoredYotoTokens, bool]:
    poll_seconds = max(1, int(_setting(db, "yoto_transcode_poll_seconds", "10") or "10"))
    timeout_minutes = max(1, int(_setting(db, "yoto_transcode_timeout_minutes", "30") or "30"))
    deadline = datetime.now(timezone.utc) + timedelta(minutes=timeout_minutes)
    refreshed_any = False

    while datetime.now(timezone.utc) < deadline:
        http_status, payload, stored_tokens, refreshed = await _call_authenticated_yoto_api(
            db=db,
            credential=credential,
            stored_tokens=stored_tokens,
            method="GET",
            relative_url=f"/media/upload/{upload_id}/transcoded?loudnorm=false",
        )
        refreshed_any = refreshed_any or refreshed
        if http_status >= 400:
            raise HTTPException(
                status_code=http_status,
                detail=_response_excerpt(payload) or "Yoto transcode status request failed.",
            )
        transcoded_sha, _nested_transcode = (
            _extract_yoto_transcode_descriptor(payload) if isinstance(payload, dict) else (None, None)
        )
        if transcoded_sha is not None:
            return payload, stored_tokens, refreshed_any
        await asyncio.sleep(poll_seconds)

    raise HTTPException(
        status_code=status.HTTP_504_GATEWAY_TIMEOUT,
        detail=f"Timed out waiting for Yoto to finish transcoding upload {upload_id}.",
    )


async def _build_live_payload_from_draft(
    *,
    db: Session,
    draft: YotoPlaylistDraft,
    credential: YotoCredentialState,
    stored_tokens: StoredYotoTokens,
) -> tuple[dict[str, object] | None, list[str], bool, StoredYotoTokens, bool]:
    try:
        payload = json.loads(draft.payload_json)
    except json.JSONDecodeError:
        return None, ["Stored playlist payload is not valid JSON."], False, stored_tokens, False

    if not isinstance(payload, dict):
        return None, ["Stored playlist payload must be a JSON object."], False, stored_tokens, False

    content = payload.get("content")
    if isinstance(content, dict) and isinstance(content.get("chapters"), list):
        return payload, [], True, stored_tokens, False

    chapters = payload.get("chapters")
    if not isinstance(chapters, list):
        return None, ["Draft does not include any playlist chapters."], False, stored_tokens, False

    ordered_tracks = _ordered_tracks_for_item(db, draft.library_item_id)
    processed_assets = _latest_processed_asset_by_track(db, draft.library_item_id)
    unmatched_tracks = ordered_tracks.copy()
    remote_chapters: list[dict[str, object]] = []
    warnings: list[str] = []
    total_duration = 0
    refreshed_any = False

    for index, raw_chapter in enumerate(chapters, start=1):
        if not isinstance(raw_chapter, dict):
            warnings.append(f"Chapter {index} is not a JSON object.")
            continue

        chapter_type = str(raw_chapter.get("type") or "audio")
        title = str(raw_chapter.get("title") or f"Track {index}")
        overlay_label = str(raw_chapter.get("display_number") or index)
        matched_track = _match_draft_track(raw_chapter=raw_chapter, ordered_tracks=unmatched_tracks)
        if matched_track is not None and matched_track in unmatched_tracks:
            unmatched_tracks.remove(matched_track)

        if chapter_type == "stream":
            stream_url = raw_chapter.get("stream_url")
            if not isinstance(stream_url, str) or not stream_url.strip():
                warnings.append(f"{title}: stream chapter is missing a playable URL.")
                continue
            duration_value = raw_chapter.get("duration_seconds")
            duration_seconds = int(duration_value) if isinstance(duration_value, int) else None
            if duration_seconds:
                total_duration += duration_seconds
            remote_chapter: dict[str, object] = {
                "key": f"{index:02d}",
                "title": title,
                "overlayLabel": overlay_label,
                "tracks": [
                    {
                        "key": "01",
                        "title": title,
                        "trackUrl": stream_url,
                        "type": "stream",
                        "format": _best_effort_stream_format(stream_url),
                        "overlayLabel": overlay_label,
                    }
                ],
            }
            if duration_seconds is not None:
                remote_chapter["duration"] = duration_seconds
                remote_chapter["tracks"][0]["duration"] = duration_seconds
            remote_chapters.append(remote_chapter)
            continue

        if matched_track is None:
            warnings.append(f"{title}: could not match this draft chapter to a library track.")
            continue

        asset = processed_assets.get(matched_track.id)
        source_path_value = asset.output_path if asset is not None else matched_track.source_path
        if not source_path_value:
            warnings.append(f"{title}: no source or processed file is available for upload.")
            continue

        source_path = Path(source_path_value)
        if not source_path.exists():
            warnings.append(f"{title}: local source file is missing at {source_path}.")
            continue

        checksum = asset.checksum_sha256 if asset is not None and asset.checksum_sha256 else _sha256_file(source_path)
        upload_relative_url = "/media/transcode/audio/uploadUrl?" + urlencode(
            {
                "sha256": checksum,
                "filename": source_path.name,
            }
        )
        http_status, upload_payload, stored_tokens, refreshed = await _call_authenticated_yoto_api(
            db=db,
            credential=credential,
            stored_tokens=stored_tokens,
            method="GET",
            relative_url=upload_relative_url,
        )
        refreshed_any = refreshed_any or refreshed
        if http_status >= 400 or not isinstance(upload_payload, dict):
            raise HTTPException(
                status_code=http_status,
                detail=_response_excerpt(upload_payload) or "Yoto upload URL request failed.",
            )

        upload_id, upload_url = _extract_yoto_upload_descriptor(upload_payload)
        if upload_id is None:
            raise HTTPException(status_code=502, detail="Yoto upload URL response did not include an uploadId.")

        if upload_url is not None:
            await _upload_file_to_yoto_signed_url(upload_url, source_path)

        transcode_payload, stored_tokens, refreshed = await _poll_yoto_transcoded_audio(
            db=db,
            credential=credential,
            stored_tokens=stored_tokens,
            upload_id=upload_id,
        )
        refreshed_any = refreshed_any or refreshed

        transcoded_sha, nested_transcode = _extract_yoto_transcode_descriptor(transcode_payload)
        if transcoded_sha is None:
            raise HTTPException(status_code=502, detail="Yoto transcode response did not include a transcodedSha256.")

        transcoded_info = nested_transcode.get("transcodedInfo") if isinstance(nested_transcode, dict) else None
        duration_seconds = (
            asset.duration_seconds
            if asset is not None and asset.duration_seconds is not None
            else matched_track.duration_seconds
            if matched_track.duration_seconds is not None
            else raw_chapter.get("duration_seconds")
            if isinstance(raw_chapter.get("duration_seconds"), int)
            else None
        )
        size_bytes = asset.size_bytes if asset is not None and asset.size_bytes else source_path.stat().st_size
        audio_format = _best_effort_audio_format(codec=asset.codec if asset is not None else None, path=source_path)
        remote_track: dict[str, object] = {
            "key": "01",
            "uid": f"{matched_track.id}",
            "title": title,
            "trackUrl": f"yoto:#{transcoded_sha}",
            "type": "audio",
            "format": audio_format,
            "fileSize": size_bytes,
            "overlayLabel": overlay_label,
        }
        if isinstance(transcoded_info, dict):
            transcoded_format = transcoded_info.get("format")
            transcoded_file_size = transcoded_info.get("fileSize")
            transcoded_channels = transcoded_info.get("channels")
            if isinstance(transcoded_format, str) and transcoded_format.strip():
                remote_track["format"] = transcoded_format.strip()
            if isinstance(transcoded_file_size, int) and transcoded_file_size > 0:
                remote_track["fileSize"] = transcoded_file_size
            normalized_channels = _best_effort_audio_channels(channels=transcoded_channels)
            if normalized_channels is not None:
                remote_track["channels"] = normalized_channels
        if duration_seconds is not None:
            remote_track["duration"] = duration_seconds
            total_duration += duration_seconds
        if "channels" not in remote_track and asset is not None and asset.channels:
            normalized_channels = _best_effort_audio_channels(channels=asset.channels)
            if normalized_channels is not None:
                remote_track["channels"] = normalized_channels

        remote_chapter = {
            "key": f"{index:02d}",
            "title": title,
            "overlayLabel": overlay_label,
            "tracks": [remote_track],
        }
        if duration_seconds is not None:
            remote_chapter["duration"] = duration_seconds
        remote_chapters.append(remote_chapter)

    if not remote_chapters:
        return None, warnings or ["No live-create-ready chapters were generated from this draft."], False, stored_tokens, refreshed_any

    generated_payload: dict[str, object] = {
        "title": str(payload.get("title") or draft.title),
        "content": {
            "chapters": remote_chapters,
            "playbackType": "linear",
            "config": {
                "resumeTimeout": 2592000,
            },
        },
        "metadata": {
            "description": "Created by YotoWebMgr",
            "media": {
                "duration": total_duration,
            },
        },
    }

    cover_art_path = payload.get("cover_art_path")
    if isinstance(cover_art_path, str) and cover_art_path.startswith(("http://", "https://")):
        metadata = generated_payload.get("metadata")
        if isinstance(metadata, dict):
            metadata["cover"] = {"imageL": cover_art_path}
    elif cover_art_path:
        warnings.append("Cover art is local-only and was not included in the live Yoto payload.")

    return generated_payload, warnings, not warnings, stored_tokens, refreshed_any


def _remote_payload_preview_from_draft(
    draft: YotoPlaylistDraft,
) -> tuple[dict[str, object] | None, list[str], bool]:
    try:
        payload = json.loads(draft.payload_json)
    except json.JSONDecodeError:
        return None, ["Stored playlist payload is not valid JSON."], False

    if not isinstance(payload, dict):
        return None, ["Stored playlist payload must be a JSON object."], False

    content = payload.get("content")
    if isinstance(content, dict) and isinstance(content.get("chapters"), list):
        return payload, [], True

    chapters = payload.get("chapters")
    if not isinstance(chapters, list):
        return None, ["Draft does not include any playlist chapters."], False

    remote_chapters: list[dict[str, object]] = []
    warnings: list[str] = []
    total_duration = 0

    for index, raw_chapter in enumerate(chapters, start=1):
        if not isinstance(raw_chapter, dict):
            warnings.append(f"Chapter {index} is not a JSON object.")
            continue

        chapter_type = str(raw_chapter.get("type") or "audio")
        title = str(raw_chapter.get("title") or f"Track {index}")
        overlay_label = str(raw_chapter.get("display_number") or index)

        if chapter_type != "stream":
            warnings.append(
                f"{title}: this draft still points at local audio and needs upload/transcode before live Yoto creation."
            )
            continue

        stream_url = raw_chapter.get("stream_url")
        if not isinstance(stream_url, str) or not stream_url.strip():
            warnings.append(f"{title}: stream chapter is missing a playable URL.")
            continue

        duration_value = raw_chapter.get("duration_seconds")
        duration_seconds = int(duration_value) if isinstance(duration_value, int) else None
        if duration_seconds:
            total_duration += duration_seconds

        icon_value = raw_chapter.get("icon_path")
        icon_payload = (
            {"icon16x16": icon_value}
            if isinstance(icon_value, str) and icon_value.startswith(("http://", "https://", "yoto:#"))
            else None
        )

        remote_chapter: dict[str, object] = {
            "key": f"{index:02d}",
            "title": title,
            "overlayLabel": overlay_label,
            "tracks": [
                {
                    "key": "01",
                    "title": title,
                    "trackUrl": stream_url,
                    "type": "stream",
                    "format": _best_effort_stream_format(stream_url),
                    "overlayLabel": overlay_label,
                }
            ],
        }
        if duration_seconds is not None:
            remote_chapter["duration"] = duration_seconds
            track = remote_chapter["tracks"][0]
            if isinstance(track, dict):
                track["duration"] = duration_seconds
        if icon_payload is not None:
            remote_chapter["display"] = icon_payload
            track = remote_chapter["tracks"][0]
            if isinstance(track, dict):
                track["display"] = icon_payload
        remote_chapters.append(remote_chapter)

    if not remote_chapters:
        return None, warnings or ["No live-create-ready chapters were generated from this draft."], False

    generated_payload: dict[str, object] = {
        "title": str(payload.get("title") or draft.title),
        "content": {
            "chapters": remote_chapters,
            "playbackType": "linear",
            "config": {
                "resumeTimeout": 2592000,
            },
        },
        "metadata": {
            "description": "Created by YotoWebMgr",
            "media": {
                "duration": total_duration,
            },
        },
    }

    cover_art_path = payload.get("cover_art_path")
    if isinstance(cover_art_path, str) and cover_art_path.startswith(("http://", "https://")):
        metadata = generated_payload.get("metadata")
        if isinstance(metadata, dict):
            metadata["cover"] = {"imageL": cover_art_path}
    elif cover_art_path:
        warnings.append("Cover art is local-only and was not included in the live Yoto payload.")

    return generated_payload, warnings, not warnings


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
    credential.authorization_url = _authorization_url(db, credential.oauth_state, payload.code_challenge)
    credential.error_summary = None
    logger.info(
        "Yoto OAuth started for credential=%s account_label=%s client_id=%s redirect_uri=%s scopes=%s",
        credential.id or "new",
        credential.account_label,
        _masked_client_id(_setting(db, "yoto_client_id")),
        _setting(db, "yoto_redirect_uri"),
        credential.scopes,
    )
    db.add(credential)
    db.commit()
    db.refresh(credential)
    return StartYotoOAuthResponse(
        credential=_credential_response(db, credential),
        authorization_url=credential.authorization_url or "",
        oauth_state=credential.oauth_state,
        live_api_call=False,
    )


@router.post("/credentials/callback", response_model=CompleteYotoOAuthResponse)
async def complete_yoto_oauth(
    payload: CompleteYotoOAuthRequest,
    db: Annotated[Session, Depends(get_db_session)],
) -> CompleteYotoOAuthResponse:
    credential = db.scalar(select(YotoCredentialState).where(YotoCredentialState.oauth_state == payload.state))
    if credential is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Yoto OAuth state was not found or has expired.")
    if credential.status != "authorization_started":
        raise HTTPException(status_code=409, detail="Yoto OAuth state has already been used.")

    client_id = _setting(db, "yoto_client_id")
    redirect_uri = _setting(db, "yoto_redirect_uri")
    if not client_id or not redirect_uri:
        raise HTTPException(status_code=422, detail="Yoto client ID and redirect URI must be configured before callback exchange.")

    try:
        token_payload = await _exchange_oauth_code(
            auth_base_url=_setting(db, "yoto_auth_base_url", "https://login.yotoplay.com"),
            client_id=client_id,
            redirect_uri=redirect_uri,
            code=payload.code,
            code_verifier=payload.code_verifier,
        )
    except HTTPException as error:
        safe_summary = _safe_oauth_exchange_summary(
            client_id=client_id,
            redirect_uri=redirect_uri,
            provider_detail=str(error.detail),
        )
        credential.status = "authorization_failed"
        credential.error_summary = safe_summary
        db.add(credential)
        db.commit()
        logger.warning(
            "Yoto OAuth exchange failed for credential %s: %s",
            credential.id,
            safe_summary,
        )
        raise HTTPException(
            status_code=error.status_code,
            detail=safe_summary,
        ) from error

    stored_tokens = _tokens_from_payload(token_payload)
    returned_scope = str(token_payload.get("scope") or "")
    logger.info(
        "Yoto OAuth exchange succeeded for credential=%s client_id=%s redirect_uri=%s returned_scope=%s has_refresh_token=%s expires_at=%s",
        credential.id,
        _masked_client_id(client_id),
        redirect_uri,
        returned_scope or "<empty>",
        bool(stored_tokens.refresh_token),
        stored_tokens.expires_at.isoformat() if stored_tokens.expires_at else "<unknown>",
    )
    try:
        token_storage_ref = await save_tokens_to_secret(
            credential_id=credential.id,
            tokens=stored_tokens,
        )
    except YotoTokenStoreError as error:
        credential.status = "authorization_failed"
        credential.error_summary = f"Yoto OAuth exchange succeeded, but saving tokens failed: {error}"
        db.add(credential)
        db.commit()
        logger.warning("Yoto token persistence failed for credential %s: %s", credential.id, error)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Yoto OAuth exchange succeeded, but token persistence into the Kubernetes Secret failed.",
        ) from error

    credential.status = "connected_tested"
    credential.token_storage_ref = token_storage_ref
    decoded = _decode_jwt_payload(stored_tokens.access_token)
    credential.masked_account_id = str(decoded.get("sub"))[-8:] if decoded.get("sub") else None
    credential.masked_email = None
    credential.scopes = str(token_payload.get("scope") or credential.scopes)
    credential.authorization_url = None
    credential.oauth_state = None
    credential.last_refreshed_at = datetime.now(timezone.utc)
    credential.expires_at = stored_tokens.expires_at
    credential.error_summary = "Browser OAuth exchange succeeded and tokens were stored in the Kubernetes Secret."
    logger.info(
        "Yoto OAuth tokens stored for credential=%s storage_ref=%s credential_scopes=%s",
        credential.id,
        credential.token_storage_ref,
        credential.scopes,
    )
    db.add(credential)
    db.commit()
    db.refresh(credential)
    expires_in = token_payload.get("expires_in")
    return CompleteYotoOAuthResponse(
        credential=_credential_response(db, credential),
        token_type=token_payload.get("token_type"),
        scope=token_payload.get("scope"),
        expires_in=expires_in if isinstance(expires_in, int) else None,
        live_api_call=True,
    )


@router.post("/credentials/disconnect", response_model=YotoCredentialStatusResponse)
async def disconnect_yoto_credentials(
    db: Annotated[Session, Depends(get_db_session)],
) -> YotoCredentialStatusResponse:
    credential = _latest_credential(db)
    if credential is None:
        return _credential_response(db, None)
    if credential.token_storage_ref:
        try:
            await delete_tokens_from_secret(credential.token_storage_ref)
        except YotoTokenStoreError as error:
            logger.warning("Failed to delete stored Yoto tokens for credential %s: %s", credential.id, error)
    logger.info("Yoto credential disconnected locally for credential=%s", credential.id)
    credential.status = "revoked"
    credential.token_storage_ref = None
    credential.authorization_url = None
    credential.oauth_state = None
    credential.error_summary = "Disconnected locally and removed the stored token payload from the Kubernetes Secret. No live Yoto revoke call was made."
    db.add(credential)
    db.commit()
    db.refresh(credential)
    return _credential_response(db, credential)


@router.post("/credentials/probe", response_model=YotoCredentialProbeResponse)
async def probe_yoto_credentials(
    db: Annotated[Session, Depends(get_db_session)],
) -> YotoCredentialProbeResponse:
    credential = _latest_credential(db)
    if credential is None or not credential.token_storage_ref:
        raise HTTPException(status_code=409, detail="Connect a Yoto account before running a live API probe.")

    try:
        stored_tokens = await load_tokens_from_secret(credential.token_storage_ref)
    except YotoTokenStoreError as error:
        credential.status = "authorization_failed"
        credential.error_summary = f"Unable to load stored Yoto tokens: {error}"
        db.add(credential)
        db.commit()
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=credential.error_summary) from error

    configured_scopes = _setting(db, "yoto_oauth_scope", "openid offline_access")
    probe_label, probe_url = _probe_definition(
        granted_scopes=credential.scopes,
        configured_scopes=configured_scopes,
    )
    logger.info(
        "Yoto probe starting for credential=%s granted_scopes=%s configured_scopes=%s probe_url=%s expires_at=%s",
        credential.id,
        credential.scopes or "<empty>",
        configured_scopes,
        probe_url,
        stored_tokens.expires_at.isoformat() if stored_tokens.expires_at else "<unknown>",
    )
    refreshed = False
    if _token_expired(stored_tokens.expires_at):
        stored_tokens = await _refresh_stored_tokens(db=db, credential=credential, stored_tokens=stored_tokens)
        refreshed = True
        logger.info(
            "Yoto probe refreshed expired token for credential=%s returned_scope=%s",
            credential.id,
            credential.scopes or "<empty>",
        )

    http_status, payload = await _call_yoto_api(
        method="GET",
        api_base_url=_setting(db, "yoto_api_base_url", "https://api.yotoplay.com"),
        relative_url=probe_url,
        access_token=stored_tokens.access_token,
    )
    if http_status == 401 and stored_tokens.refresh_token:
        stored_tokens = await _refresh_stored_tokens(db=db, credential=credential, stored_tokens=stored_tokens)
        refreshed = True
        logger.info(
            "Yoto probe retried after 401 for credential=%s returned_scope=%s",
            credential.id,
            credential.scopes or "<empty>",
        )
        http_status, payload = await _call_yoto_api(
            method="GET",
            api_base_url=_setting(db, "yoto_api_base_url", "https://api.yotoplay.com"),
            relative_url=probe_url,
            access_token=stored_tokens.access_token,
        )

    if 200 <= http_status < 300:
        credential.status = "connected_tested"
        credential.error_summary = f"Last Yoto probe succeeded against {probe_url} with HTTP {http_status}."
    else:
        credential.status = "connected_error"
        credential.error_summary = f"Last Yoto probe failed against {probe_url} with HTTP {http_status}."
    logger.info(
        "Yoto probe finished for credential=%s http_status=%s refreshed=%s response_excerpt=%s",
        credential.id,
        http_status,
        refreshed,
        _response_excerpt(payload),
    )
    db.add(credential)
    db.commit()
    db.refresh(credential)

    return YotoCredentialProbeResponse(
        credential=_credential_response(db, credential),
        probe_label=probe_label,
        probe_url=urljoin(_setting(db, "yoto_api_base_url", "https://api.yotoplay.com").rstrip("/") + "/", probe_url.lstrip("/")),
        http_status=http_status,
        ok=200 <= http_status < 300,
        token_refreshed=refreshed,
        response_excerpt=_response_excerpt(payload),
        error_detail=None if 200 <= http_status < 300 else _response_excerpt(payload),
        live_api_call=True,
    )


@router.post("/debug/request", response_model=YotoApiDebugResponse)
async def debug_yoto_api_request(
    payload: YotoApiDebugRequest,
    db: Annotated[Session, Depends(get_db_session)],
) -> YotoApiDebugResponse:
    credential = _latest_credential(db)
    if credential is None or not credential.token_storage_ref:
        raise HTTPException(status_code=409, detail="Connect a Yoto account before sending a custom Yoto API request.")

    relative_url, request_url = _normalize_debug_path(
        api_base_url=_setting(db, "yoto_api_base_url", "https://api.yotoplay.com"),
        raw_path=payload.path,
    )
    parsed_body: Any | None = None
    if payload.body_json and payload.body_json.strip():
        try:
            parsed_body = json.loads(payload.body_json)
        except json.JSONDecodeError as error:
            raise HTTPException(status_code=422, detail=f"Custom Yoto request body is not valid JSON: {error.msg}") from error

    label = payload.label.strip() if payload.label else f"{payload.method} {relative_url}"
    logger.info(
        "Yoto debug request starting for credential=%s label=%s method=%s path=%s has_body=%s",
        credential.id,
        label,
        payload.method,
        relative_url,
        parsed_body is not None,
    )
    return await _execute_yoto_api_request(
        db=db,
        credential=credential,
        label=label,
        method=payload.method,
        relative_url=relative_url,
        request_url=request_url,
        json_body=parsed_body,
    )


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


@router.get("/playlists/{playlist_id}/remote-payload", response_model=YotoPlaylistRemotePayloadResponse)
async def get_yoto_playlist_remote_payload(
    playlist_id: int,
    db: Annotated[Session, Depends(get_db_session)],
) -> YotoPlaylistRemotePayloadResponse:
    draft = db.get(YotoPlaylistDraft, playlist_id)
    if draft is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Yoto playlist draft not found")

    payload, warnings, can_create_live = _remote_payload_preview_from_draft(draft)
    if not can_create_live and _draft_has_processed_assets(db, draft):
        warnings = [
            "Processed Yoto-ready assets exist for this draft, but the preview endpoint still shows the older local-only source payload."
        ]
    return YotoPlaylistRemotePayloadResponse(
        playlist_draft_id=draft.id,
        can_create_live=can_create_live or _draft_has_processed_assets(db, draft),
        payload=payload,
        warnings=warnings,
        live_api_call=False,
    )


@router.post("/playlists/{playlist_id}/create-live", response_model=CreateLiveYotoPlaylistResponse)
async def create_live_yoto_playlist(
    playlist_id: int,
    payload: CreateLiveYotoPlaylistRequest,
    db: Annotated[Session, Depends(get_db_session)],
) -> CreateLiveYotoPlaylistResponse:
    draft = db.get(YotoPlaylistDraft, playlist_id)
    if draft is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Yoto playlist draft not found")

    item = db.get(LibraryItem, draft.library_item_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Library item not found")

    credential = _latest_credential(db)
    if credential is None or not credential.token_storage_ref:
        raise HTTPException(status_code=409, detail="Connect a Yoto account before creating a live playlist.")

    stored_tokens, token_refreshed = await _load_live_tokens(db=db, credential=credential)
    request_payload = payload.request_payload
    if request_payload is None:
        request_payload, warnings, _can_create_live, stored_tokens, build_refreshed = await _build_live_payload_from_draft(
            db=db,
            draft=draft,
            credential=credential,
            stored_tokens=stored_tokens,
        )
        token_refreshed = token_refreshed or build_refreshed
        if request_payload is None:
            raise HTTPException(
                status_code=422,
                detail=" ".join(warnings) if warnings else "This draft is not ready for live Yoto playlist creation.",
            )

    if not isinstance(request_payload, dict):
        raise HTTPException(status_code=422, detail="The live Yoto payload must be a JSON object.")

    http_status, response_payload, stored_tokens, create_refreshed = await _call_authenticated_yoto_api(
        db=db,
        credential=credential,
        stored_tokens=stored_tokens,
        method="POST",
        relative_url="/content",
        json_body=request_payload,
    )
    token_refreshed = token_refreshed or create_refreshed
    if not (200 <= http_status < 300):
        credential.status = "connected_error"
        credential.error_summary = f"Live Yoto playlist creation failed against /content with HTTP {http_status}."
        db.add(credential)
        db.commit()
        raise HTTPException(
            status_code=http_status or 502,
            detail=_response_excerpt(response_payload) or "Yoto playlist creation failed.",
        )

    credential.status = "connected_tested"
    credential.error_summary = f"Live Yoto playlist creation succeeded against /content with HTTP {http_status}."

    remote_card_id: str | None = None
    if isinstance(response_payload, dict):
        card_payload = response_payload.get("card")
        if isinstance(card_payload, dict):
            remote_card_id_value = card_payload.get("cardId")
            if isinstance(remote_card_id_value, str) and remote_card_id_value.strip():
                remote_card_id = remote_card_id_value.strip()

    draft.payload_json = json.dumps(request_payload, sort_keys=True)
    draft.status = "remote_created"
    draft.remote_playlist_id = remote_card_id
    draft.last_error = None
    item.status = "yoto_remote_created"
    item.readiness_status = "yoto_remote_created"
    item.readiness_detail = (
        f"Created live Yoto content with card ID {remote_card_id}. Use the direct blank-card write flow from this app to program linked cards."
        if remote_card_id
        else "Created live Yoto content. Use the direct blank-card write flow from this app to program linked cards."
    )

    if payload.mark_linked_cards_ready:
        linked_cards = db.scalars(select(PhysicalCard).where(PhysicalCard.current_library_item_id == item.id))
        for card in linked_cards:
            card.ready_to_link_in_app = True
            if card.status in {"upload_queued", "planning", "available", "ready_to_link"}:
                card.status = "ready_to_link"
            if remote_card_id:
                existing_notes = card.notes.strip() if card.notes else ""
                note_line = f"Linked live Yoto card ID: {remote_card_id}"
                card.notes = f"{existing_notes}\n{note_line}".strip() if existing_notes and note_line not in existing_notes else (existing_notes or note_line)
            db.add(card)

    _record_playlist_version(
        db,
        draft,
        status="remote_created",
        summary="Created live Yoto content from this draft.",
        source_event="yoto_remote_created",
    )
    db.add(
        VersionEvent(
            entity_type="library_item",
            entity_id=item.id,
            version_number=_next_library_version(db, item.id),
            event_type="yoto_remote_created",
            summary="Created live Yoto content from this draft.",
            snapshot_json=json.dumps(
                {
                    "playlist_draft_id": draft.id,
                    "remote_card_id": remote_card_id,
                    "mark_linked_cards_ready": payload.mark_linked_cards_ready,
                },
                sort_keys=True,
            ),
        )
    )
    db.add(draft)
    db.add(item)
    db.add(credential)
    db.commit()
    db.refresh(draft)
    db.refresh(item)
    db.refresh(credential)

    return CreateLiveYotoPlaylistResponse(
        playlist=_draft_response(draft),
        credential=_credential_response(db, credential),
        remote_card_id=remote_card_id,
        remote_content_response=_response_json(response_payload),
        http_status=http_status,
        token_refreshed=token_refreshed,
        response_excerpt=_response_excerpt(response_payload),
        error_detail=None,
        live_api_call=True,
    )


@router.patch("/playlists/{playlist_id}/remote-link", response_model=YotoPlaylistDraftResponse)
async def update_yoto_playlist_remote_link(
    playlist_id: int,
    payload: UpdateYotoPlaylistRemoteLinkRequest,
    db: Annotated[Session, Depends(get_db_session)],
) -> YotoPlaylistDraftResponse:
    draft = db.get(YotoPlaylistDraft, playlist_id)
    if draft is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Yoto playlist draft not found")

    remote_playlist_id = payload.remote_playlist_id.strip() if payload.remote_playlist_id else None
    remote_playlist_uri = payload.remote_playlist_uri.strip() if payload.remote_playlist_uri else None
    if not remote_playlist_id and not remote_playlist_uri:
        raise HTTPException(status_code=422, detail="Provide a remote Yoto playlist ID or playlist URI.")

    item = db.get(LibraryItem, draft.library_item_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Library item not found")

    draft.remote_playlist_id = remote_playlist_id
    draft.remote_playlist_uri = remote_playlist_uri
    draft.status = "remote_linked"
    draft.last_error = None
    item.status = "yoto_remote_linked"
    item.readiness_status = "yoto_remote_linked"
    item.readiness_detail = (
        f"Mapped to Yoto playlist {remote_playlist_uri or remote_playlist_id}. "
        "Card linking and NFC verification can now use this remote playlist reference."
    )

    if remote_playlist_uri:
        linked_cards = db.scalars(select(PhysicalCard).where(PhysicalCard.current_library_item_id == item.id))
        now = datetime.now(timezone.utc)
        for card in linked_cards:
            card.yoto_playlist_uri = remote_playlist_uri
            card.ready_to_link_in_app = True
            if payload.mark_linked_manually and not card.linked_manually:
                card.linked_manually = True
                card.last_linked_at = now
            db.add(card)

    _record_playlist_version(
        db,
        draft,
        status="remote_linked",
        summary="Recorded Yoto remote playlist mapping.",
        source_event="yoto_remote_link_saved",
    )
    db.add(
        VersionEvent(
            entity_type="library_item",
            entity_id=item.id,
            version_number=_next_library_version(db, item.id),
            event_type="yoto_remote_link_saved",
            summary="Recorded Yoto remote playlist mapping.",
            snapshot_json=json.dumps(
                {
                    "playlist_draft_id": draft.id,
                    "remote_playlist_id": remote_playlist_id,
                    "remote_playlist_uri": remote_playlist_uri,
                    "mark_linked_manually": payload.mark_linked_manually,
                },
                sort_keys=True,
            ),
        )
    )
    db.add(draft)
    db.add(item)
    db.commit()
    db.refresh(draft)
    return _draft_response(draft)


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
        progress_message="Queued local Yoto playlist draft for remote mapping",
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
    item.readiness_detail = "Yoto playlist draft queued. This job will prepare the local payload for remote Yoto playlist mapping."
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
