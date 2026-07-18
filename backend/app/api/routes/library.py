from typing import Annotated
import json
from pathlib import Path
from uuid import uuid4
import xml.etree.ElementTree as ET
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db_session
from app.models import (
    ArtworkAsset,
    CardAssignmentEvent,
    CardPlanPart,
    CardPlanTrackAssignment,
    ImportRequest,
    Job,
    LibraryItem,
    PhysicalCard,
    PlaylistTrack,
    PodcastEpisode,
    PodcastFeed,
    ProcessedAsset,
    Setting,
    SplitPoint,
    Tag,
    TagAssignment,
    User,
    VersionEvent,
    YotoPlaylistDraft,
)
from app.schemas.foundation import (
    ArtworkAssetResponse,
    CardPlanPartResponse,
    CardPlanResponse,
    CardPlanSaveRequest,
    CardPlanTrackResponse,
    CardResponse,
    JobResponse,
    LibraryItemDetailResponse,
    LibraryItemCreate,
    LibraryItemResponse,
    LibraryItemSettingsUpdate,
    LinkCardRequest,
    LinkCardResponse,
    PlaylistTrackCreate,
    PlaylistTrackResponse,
    PlaylistTrackUpdate,
    PodcastEpisodeResponse,
    PodcastFeedCreate,
    PodcastFeedResponse,
    ProcessedAssetResponse,
    RadioStreamCreate,
    ReadinessCheck,
    ReadinessResponse,
    SplitPointCreate,
    SplitPointResponse,
    TagResponse,
    TrackIconApplyRequest,
    VersionRestoreResponse,
    VersionEventResponse,
)


router = APIRouter()
allowed_artwork_extensions = {".jpg", ".jpeg", ".png", ".webp"}


def _is_allowed_media_path(path: Path) -> bool:
    settings = get_settings()
    allowed_roots = [
        Path(settings.import_drop_path).resolve(strict=False),
        Path(settings.browser_upload_path).resolve(strict=False),
    ]
    resolved = path.resolve(strict=False)
    return any(resolved == root or root in resolved.parents for root in allowed_roots)


def _media_url_for_item(db: Session, item: LibraryItem) -> str | None:
    if item.source_import_id is None:
        return None
    import_request = db.get(ImportRequest, item.source_import_id)
    if not import_request or not import_request.source_path:
        return None
    source_path = Path(import_request.source_path)
    if not _is_allowed_media_path(source_path) or not source_path.exists() or not source_path.is_file():
        return None
    return f"/api/v1/library/{item.id}/media"


def _stream_track_for_item(db: Session, item: LibraryItem) -> PlaylistTrack | None:
    return db.scalar(
        select(PlaylistTrack)
        .where(PlaylistTrack.library_item_id == item.id)
        .where(PlaylistTrack.is_stream.is_(True))
        .where(PlaylistTrack.stream_url.is_not(None))
        .order_by(PlaylistTrack.track_number.asc(), PlaylistTrack.id.asc())
    )


def _stream_url_for_item(db: Session, item: LibraryItem) -> str | None:
    if _stream_track_for_item(db, item) is None:
        return None
    return f"/api/v1/library/{item.id}/stream"


def _safe_artwork_filename(filename: str) -> str:
    source_name = Path(filename).name
    suffix = Path(source_name).suffix.lower()
    if suffix not in allowed_artwork_extensions:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unsupported artwork extension: {suffix or 'none'}.",
        )
    stem = "".join(character if character.isalnum() or character in "._-" else "-" for character in Path(source_name).stem)
    return f"{stem.strip('.-') or 'cover'}-{uuid4().hex[:12]}{suffix}"


def _tag_responses_for_entity(db: Session, entity_type: str, entity_id: int) -> list[TagResponse]:
    usage_subquery = (
        select(TagAssignment.tag_id, func.count(TagAssignment.id).label("usage_count"))
        .group_by(TagAssignment.tag_id)
        .subquery()
    )
    rows = db.execute(
        select(Tag, func.coalesce(usage_subquery.c.usage_count, 0))
        .join(TagAssignment, TagAssignment.tag_id == Tag.id)
        .outerjoin(usage_subquery, usage_subquery.c.tag_id == Tag.id)
        .where(TagAssignment.entity_type == entity_type)
        .where(TagAssignment.entity_id == entity_id)
        .order_by(Tag.name.asc())
    ).all()
    return [
        TagResponse(
            id=tag.id,
            name=tag.name,
            normalized_name=tag.normalized_name,
            color=tag.color,
            usage_count=usage_count,
            created_at=tag.created_at,
        )
        for tag, usage_count in rows
    ]


def _build_library_item_response(db: Session, item: LibraryItem) -> LibraryItemResponse:
    return LibraryItemResponse(
        id=item.id,
        title=item.title,
        content_type=item.content_type,
        status=item.status,
        cover_art_path=item.cover_art_path,
        playlist_always_play_from_start=item.playlist_always_play_from_start,
        playlist_shuffle_tracks=item.playlist_shuffle_tracks,
        playlist_hide_track_numbers=item.playlist_hide_track_numbers,
        readiness_status=item.readiness_status,
        readiness_detail=item.readiness_detail,
        notes=item.notes,
        created_at=item.created_at,
        media_url=_media_url_for_item(db, item),
        stream_url=_stream_url_for_item(db, item),
        tags=_tag_responses_for_entity(db, "library_item", item.id),
    )


def _build_card_response(card: PhysicalCard) -> CardResponse:
    return CardResponse(
        id=card.id,
        card_code=card.card_code,
        programmable_id=card.programmable_id,
        nfc_serial_number=card.nfc_serial_number,
        ndef_payload_text=card.ndef_payload_text,
        ndef_payload_hex=card.ndef_payload_hex,
        scan_source=card.scan_source,
        display_name=card.display_name,
        card_kind=card.card_kind,
        nfc_technology=card.nfc_technology,
        chip_type=card.chip_type,
        memory_size_bytes=card.memory_size_bytes,
        ndef_prepared=card.ndef_prepared,
        ndef_format_command=card.ndef_format_command,
        programming_app=card.programming_app,
        source_card_code=card.source_card_code,
        is_reusable_transfer_card=card.is_reusable_transfer_card,
        ready_to_link_in_app=card.ready_to_link_in_app,
        linked_manually=card.linked_manually,
        overwrite_ok=card.overwrite_ok,
        downloaded_to_player_confirmed=card.downloaded_to_player_confirmed,
        needs_player_download=card.needs_player_download,
        current_library_item_id=card.current_library_item_id,
        pending_job_id=card.pending_job_id,
        yoto_playlist_uri=card.yoto_playlist_uri,
        status=card.status,
        label_color=card.label_color,
        tested=card.tested,
        last_scanned_at=card.last_scanned_at,
        last_linked_at=card.last_linked_at,
        last_programmed_at=card.last_programmed_at,
        last_tested_at=card.last_tested_at,
        notes=card.notes,
        created_at=card.created_at,
    )


def _source_path_for_item(db: Session, item: LibraryItem) -> Path | None:
    if item.source_import_id is None:
        return None
    import_request = db.get(ImportRequest, item.source_import_id)
    if import_request is None or not import_request.source_path:
        return None
    return Path(import_request.source_path)


def _source_size_mb(db: Session, item: LibraryItem) -> float | None:
    source_path = _source_path_for_item(db, item)
    if source_path is None or not _is_allowed_media_path(source_path) or not source_path.exists():
        return None
    if source_path.is_dir():
        total_size = sum(path.stat().st_size for path in source_path.rglob("*") if path.is_file())
    else:
        total_size = source_path.stat().st_size
    return round(total_size / 1024 / 1024, 2)


def _target_size_mb(db: Session) -> int:
    setting = db.scalar(select(Setting).where(Setting.key == "target_size_mb"))
    if setting is None:
        return 480
    try:
        return int(setting.value)
    except ValueError:
        return 480


def _target_duration_seconds(db: Session) -> int:
    setting = db.scalar(select(Setting).where(Setting.key == "target_duration_hours"))
    if setting is None:
        return round(4.9 * 3600)
    try:
        return round(float(setting.value) * 3600)
    except ValueError:
        return round(4.9 * 3600)


def _build_track_response(track: PlaylistTrack) -> PlaylistTrackResponse:
    return PlaylistTrackResponse.model_validate(track, from_attributes=True)


def _build_split_point_response(split_point: SplitPoint) -> SplitPointResponse:
    return SplitPointResponse.model_validate(split_point, from_attributes=True)


def _build_podcast_episode_response(episode: PodcastEpisode) -> PodcastEpisodeResponse:
    return PodcastEpisodeResponse.model_validate(episode, from_attributes=True)


def _build_podcast_feed_response(db: Session, feed: PodcastFeed) -> PodcastFeedResponse:
    episodes = db.scalars(
        select(PodcastEpisode)
        .where(PodcastEpisode.feed_id == feed.id)
        .order_by(PodcastEpisode.id.asc())
    )
    response = PodcastFeedResponse.model_validate(feed, from_attributes=True)
    response.episodes = [_build_podcast_episode_response(episode) for episode in episodes]
    return response


def _build_processed_asset_response(asset: ProcessedAsset) -> ProcessedAssetResponse:
    return ProcessedAssetResponse.model_validate(asset, from_attributes=True)


def _build_artwork_asset_response(asset: ArtworkAsset) -> ArtworkAssetResponse:
    return ArtworkAssetResponse.model_validate(asset, from_attributes=True)


def _detail_for_item(db: Session, item: LibraryItem) -> LibraryItemDetailResponse:
    tracks = db.scalars(
        select(PlaylistTrack)
        .where(PlaylistTrack.library_item_id == item.id)
        .order_by(PlaylistTrack.track_number.asc(), PlaylistTrack.id.asc())
    )
    feeds = db.scalars(
        select(PodcastFeed)
        .where(PodcastFeed.library_item_id == item.id)
        .order_by(PodcastFeed.id.asc())
    )
    split_points = db.scalars(
        select(SplitPoint)
        .where(SplitPoint.library_item_id == item.id)
        .order_by(SplitPoint.timestamp_seconds.asc(), SplitPoint.id.asc())
    )
    processed_assets = db.scalars(
        select(ProcessedAsset)
        .where(ProcessedAsset.library_item_id == item.id)
        .order_by(ProcessedAsset.created_at.desc(), ProcessedAsset.id.desc())
    )
    artwork_assets = db.scalars(
        select(ArtworkAsset)
        .where(ArtworkAsset.library_item_id == item.id)
        .order_by(ArtworkAsset.created_at.desc(), ArtworkAsset.id.desc())
    )
    return LibraryItemDetailResponse(
        item=_build_library_item_response(db, item),
        tracks=[_build_track_response(track) for track in tracks],
        podcast_feeds=[_build_podcast_feed_response(db, feed) for feed in feeds],
        split_points=[_build_split_point_response(split_point) for split_point in split_points],
        processed_assets=[_build_processed_asset_response(asset) for asset in processed_assets],
        artwork_assets=[_build_artwork_asset_response(asset) for asset in artwork_assets],
    )


def _version_snapshot(db: Session, item: LibraryItem) -> str:
    tracks = list(
        db.scalars(
            select(PlaylistTrack)
            .where(PlaylistTrack.library_item_id == item.id)
            .order_by(PlaylistTrack.track_number.asc(), PlaylistTrack.id.asc())
        )
    )
    split_points = list(
        db.scalars(
            select(SplitPoint)
            .where(SplitPoint.library_item_id == item.id)
            .order_by(SplitPoint.timestamp_seconds.asc(), SplitPoint.id.asc())
        )
    )
    feeds = list(
        db.scalars(
            select(PodcastFeed)
            .where(PodcastFeed.library_item_id == item.id)
            .order_by(PodcastFeed.id.asc())
        )
    )
    snapshot = {
        "item": {
            "id": item.id,
            "title": item.title,
            "content_type": item.content_type,
            "status": item.status,
            "cover_art_path": item.cover_art_path,
            "playlist_always_play_from_start": item.playlist_always_play_from_start,
            "playlist_shuffle_tracks": item.playlist_shuffle_tracks,
            "playlist_hide_track_numbers": item.playlist_hide_track_numbers,
            "readiness_status": item.readiness_status,
            "readiness_detail": item.readiness_detail,
            "notes": item.notes,
            "source_import_id": item.source_import_id,
        },
        "tracks": [
            {
                "id": track.id,
                "title": track.title,
                "track_number": track.track_number,
                "duration_seconds": track.duration_seconds,
                "source_start_seconds": track.source_start_seconds,
                "source_end_seconds": track.source_end_seconds,
                "icon_path": track.icon_path,
                "track_behavior": track.track_behavior,
                "is_stream": track.is_stream,
                "source_path": track.source_path,
                "source_url": track.source_url,
                "stream_url": track.stream_url,
                "podcast_episode_guid": track.podcast_episode_guid,
            }
            for track in tracks
        ],
        "podcast_feeds": [
            {
                "id": feed.id,
                "rss_url": feed.rss_url,
                "title": feed.title,
                "description": feed.description,
                "artwork_url": feed.artwork_url,
            }
            for feed in feeds
        ],
        "split_points": [
            {
                "id": split_point.id,
                "timestamp_seconds": split_point.timestamp_seconds,
                "title": split_point.title,
                "part_number": split_point.part_number,
            }
            for split_point in split_points
        ],
    }
    return json.dumps(snapshot, sort_keys=True)


def _record_library_version(
    db: Session,
    item: LibraryItem,
    event_type: str,
    summary: str,
    created_by_user_id: int | None = None,
) -> VersionEvent:
    latest_version = db.scalar(
        select(func.max(VersionEvent.version_number))
        .where(VersionEvent.entity_type == "library_item")
        .where(VersionEvent.entity_id == item.id)
    )
    event = VersionEvent(
        entity_type="library_item",
        entity_id=item.id,
        version_number=(latest_version or 0) + 1,
        event_type=event_type,
        summary=summary,
        snapshot_json=_version_snapshot(db, item),
        created_by_user_id=created_by_user_id,
    )
    db.add(event)
    return event


def _restore_library_item_from_snapshot(db: Session, item: LibraryItem, snapshot_json: str) -> None:
    try:
        snapshot = json.loads(snapshot_json)
    except json.JSONDecodeError as error:
        raise HTTPException(status_code=422, detail="Version snapshot is not valid JSON.") from error

    if not isinstance(snapshot, dict) or not isinstance(snapshot.get("item"), dict):
        raise HTTPException(status_code=422, detail="Version snapshot cannot be restored.")

    item_snapshot = snapshot["item"]
    for key in [
        "title",
        "content_type",
        "status",
        "cover_art_path",
        "playlist_always_play_from_start",
        "playlist_shuffle_tracks",
        "playlist_hide_track_numbers",
        "readiness_status",
        "readiness_detail",
        "notes",
        "source_import_id",
    ]:
        if key in item_snapshot:
            setattr(item, key, item_snapshot[key])
    db.add(item)

    feed_ids = list(
        db.scalars(select(PodcastFeed.id).where(PodcastFeed.library_item_id == item.id))
    )
    if feed_ids:
        db.execute(delete(PodcastEpisode).where(PodcastEpisode.feed_id.in_(feed_ids)))
    db.execute(delete(PodcastFeed).where(PodcastFeed.library_item_id == item.id))
    db.execute(delete(PlaylistTrack).where(PlaylistTrack.library_item_id == item.id))
    db.execute(delete(SplitPoint).where(SplitPoint.library_item_id == item.id))
    db.flush()

    for track_snapshot in snapshot.get("tracks", []):
        if not isinstance(track_snapshot, dict):
            continue
        db.add(
            PlaylistTrack(
                library_item_id=item.id,
                title=str(track_snapshot.get("title") or "Untitled track")[:240],
                source_path=track_snapshot.get("source_path"),
                source_url=track_snapshot.get("source_url"),
                source_start_seconds=track_snapshot.get("source_start_seconds"),
                source_end_seconds=track_snapshot.get("source_end_seconds"),
                track_number=int(track_snapshot.get("track_number") or 1),
                duration_seconds=track_snapshot.get("duration_seconds"),
                icon_path=track_snapshot.get("icon_path"),
                track_behavior=track_snapshot.get("track_behavior") or "continue",
                is_stream=bool(track_snapshot.get("is_stream")),
                stream_url=track_snapshot.get("stream_url"),
                podcast_episode_guid=track_snapshot.get("podcast_episode_guid"),
            )
        )

    for feed_snapshot in snapshot.get("podcast_feeds", []):
        if not isinstance(feed_snapshot, dict) or not feed_snapshot.get("rss_url"):
            continue
        db.add(
            PodcastFeed(
                library_item_id=item.id,
                rss_url=feed_snapshot["rss_url"],
                title=feed_snapshot.get("title"),
                description=feed_snapshot.get("description"),
                artwork_url=feed_snapshot.get("artwork_url"),
            )
        )

    for split_snapshot in snapshot.get("split_points", []):
        if not isinstance(split_snapshot, dict):
            continue
        db.add(
            SplitPoint(
                library_item_id=item.id,
                timestamp_seconds=int(split_snapshot.get("timestamp_seconds") or 0),
                title=str(split_snapshot.get("title") or "Split point")[:240],
                part_number=split_snapshot.get("part_number"),
            )
        )


def _estimate_track_size_mb(
    duration_seconds: int | None,
    target_duration_seconds: int,
    target_size_mb: int,
) -> float | None:
    if duration_seconds is None:
        return None
    return round((duration_seconds / target_duration_seconds) * target_size_mb, 2)


def _build_card_plan(db: Session, item: LibraryItem) -> CardPlanResponse:
    tracks = list(
        db.scalars(
            select(PlaylistTrack)
            .where(PlaylistTrack.library_item_id == item.id)
            .where(PlaylistTrack.is_stream.is_(False))
            .order_by(PlaylistTrack.track_number.asc(), PlaylistTrack.id.asc())
        )
    )
    split_seconds = [
        split_point.timestamp_seconds
        for split_point in db.scalars(
            select(SplitPoint)
            .where(SplitPoint.library_item_id == item.id)
            .order_by(SplitPoint.timestamp_seconds.asc(), SplitPoint.id.asc())
        )
    ]
    target_duration_seconds = _target_duration_seconds(db)
    target_size_mb = _target_size_mb(db)
    warnings: list[str] = []
    parts: list[CardPlanPartResponse] = []
    current_tracks: list[CardPlanTrackResponse] = []
    current_duration = 0
    current_size = 0.0
    cumulative_start = 0
    next_split_index = 0

    def finish_part() -> None:
        nonlocal current_tracks, current_duration, current_size
        if not current_tracks:
            return
        part_number = len(parts) + 1
        part_warnings: list[str] = []
        if current_duration > target_duration_seconds:
            part_warnings.append("Part exceeds target duration.")
        if current_size > target_size_mb:
            part_warnings.append("Part exceeds estimated target size.")
        parts.append(
            CardPlanPartResponse(
                part_number=part_number,
                title=f"{item.title} - Part {part_number}",
                duration_seconds=current_duration,
                estimated_size_mb=round(current_size, 2),
                track_count=len(current_tracks),
                tracks=current_tracks,
                warnings=part_warnings,
            )
        )
        current_tracks = []
        current_duration = 0
        current_size = 0.0

    for track in tracks:
        duration = track.duration_seconds or 0
        while next_split_index < len(split_seconds) and cumulative_start >= split_seconds[next_split_index]:
            finish_part()
            next_split_index += 1

        estimated_size = _estimate_track_size_mb(track.duration_seconds, target_duration_seconds, target_size_mb)
        if track.duration_seconds is None:
            warnings.append(f"{track.title} has no duration, so estimates may be incomplete.")
        if duration > target_duration_seconds:
            warnings.append(f"{track.title} is longer than the target card duration.")
        if current_tracks and duration and current_duration + duration > target_duration_seconds:
            finish_part()

        current_tracks.append(
            CardPlanTrackResponse(
                track_id=track.id,
                title=track.title,
                track_number=track.track_number,
                duration_seconds=track.duration_seconds,
                estimated_size_mb=estimated_size,
            )
        )
        current_duration += duration
        current_size += estimated_size or 0
        cumulative_start += duration

    finish_part()
    total_duration = sum(part.duration_seconds for part in parts)
    return CardPlanResponse(
        library_item_id=item.id,
        target_duration_seconds=target_duration_seconds,
        target_size_mb=target_size_mb,
        total_duration_seconds=total_duration,
        estimated_total_size_mb=round(sum(part.estimated_size_mb for part in parts), 2),
        parts=parts,
        warnings=warnings,
    )


def _build_saved_card_plan(db: Session, item: LibraryItem) -> CardPlanResponse:
    target_duration_seconds = _target_duration_seconds(db)
    target_size_mb = _target_size_mb(db)
    parts: list[CardPlanPartResponse] = []
    saved_parts = list(
        db.scalars(
            select(CardPlanPart)
            .where(CardPlanPart.library_item_id == item.id)
            .order_by(CardPlanPart.part_number.asc(), CardPlanPart.id.asc())
        )
    )
    for saved_part in saved_parts:
        assignments = db.execute(
            select(CardPlanTrackAssignment, PlaylistTrack)
            .join(PlaylistTrack, PlaylistTrack.id == CardPlanTrackAssignment.playlist_track_id)
            .where(CardPlanTrackAssignment.card_plan_part_id == saved_part.id)
            .order_by(CardPlanTrackAssignment.track_order.asc(), PlaylistTrack.track_number.asc())
        ).all()
        tracks = [
            CardPlanTrackResponse(
                track_id=track.id,
                title=track.title,
                track_number=track.track_number,
                duration_seconds=track.duration_seconds,
                estimated_size_mb=_estimate_track_size_mb(track.duration_seconds, target_duration_seconds, target_size_mb),
            )
            for _, track in assignments
        ]
        duration_seconds = sum(track.duration_seconds or 0 for track in tracks)
        estimated_size_mb = round(sum(track.estimated_size_mb or 0 for track in tracks), 2)
        warnings = []
        if duration_seconds > target_duration_seconds:
            warnings.append("Part exceeds target duration.")
        if estimated_size_mb > target_size_mb:
            warnings.append("Part exceeds estimated target size.")
        parts.append(
            CardPlanPartResponse(
                part_number=saved_part.part_number,
                title=saved_part.title,
                duration_seconds=duration_seconds,
                estimated_size_mb=estimated_size_mb,
                track_count=len(tracks),
                tracks=tracks,
                warnings=warnings,
            )
        )
    return CardPlanResponse(
        library_item_id=item.id,
        target_duration_seconds=target_duration_seconds,
        target_size_mb=target_size_mb,
        total_duration_seconds=sum(part.duration_seconds for part in parts),
        estimated_total_size_mb=round(sum(part.estimated_size_mb for part in parts), 2),
        parts=parts,
        warnings=[],
    )


def _duration_text(seconds: int | None) -> str | None:
    if seconds is None:
        return None
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    return f"{hours}h {minutes}m" if hours else f"{minutes}m"


def _parse_duration(value: str | None) -> int | None:
    if not value:
        return None
    parts = value.strip().split(":")
    if not all(part.isdigit() for part in parts):
        return None
    numbers = [int(part) for part in parts]
    if len(numbers) == 3:
        return numbers[0] * 3600 + numbers[1] * 60 + numbers[2]
    if len(numbers) == 2:
        return numbers[0] * 60 + numbers[1]
    if len(numbers) == 1:
        return numbers[0]
    return None


def _xml_text(element: ET.Element, *names: str) -> str | None:
    for name in names:
        child = element.find(name)
        if child is not None and child.text:
            return child.text.strip()
    return None


def _xml_attr(element: ET.Element, name: str, attr: str) -> str | None:
    child = element.find(name)
    if child is None:
        return None
    value = child.attrib.get(attr)
    return value.strip() if value else None


def _parse_podcast_xml(rss_xml: str) -> tuple[dict[str, str | None], list[dict[str, str | int | None]]]:
    root = ET.fromstring(rss_xml)
    channel = root.find("channel")
    if channel is None:
        raise HTTPException(status_code=422, detail="RSS XML does not contain a channel.")

    metadata = {
        "title": _xml_text(channel, "title"),
        "description": _xml_text(channel, "description"),
        "artwork_url": _xml_attr(channel, "image", "href") or _xml_text(channel, "image/url"),
    }
    episodes: list[dict[str, str | int | None]] = []
    for item in channel.findall("item"):
        enclosure = item.find("enclosure")
        episode_url = enclosure.attrib.get("url") if enclosure is not None else None
        title = _xml_text(item, "title") or "Untitled episode"
        episodes.append(
            {
                "guid": _xml_text(item, "guid"),
                "title": title[:240],
                "description": _xml_text(item, "description"),
                "episode_url": episode_url,
                "published_at": _xml_text(item, "pubDate"),
                "duration_seconds": _parse_duration(
                    _xml_text(item, "{http://www.itunes.com/dtds/podcast-1.0.dtd}duration", "duration")
                ),
            }
        )
    return metadata, episodes


def _ensure_http_stream_url(stream_url: str) -> None:
    parsed_url = urlparse(stream_url)
    if parsed_url.scheme not in {"http", "https"}:
        raise HTTPException(status_code=422, detail="Radio stream URL must use http or https.")


def _playlist_stream_url_from_text(playlist_text: str) -> str | None:
    for line in playlist_text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith("["):
            continue
        if stripped.lower().startswith("file") and "=" in stripped:
            candidate = stripped.split("=", 1)[1].strip()
        else:
            candidate = stripped
        if candidate.startswith(("http://", "https://")):
            return candidate
    return None


async def _resolve_stream_url(stream_url: str) -> str:
    _ensure_http_stream_url(stream_url)
    parsed_url = urlparse(stream_url)
    if not parsed_url.path.lower().endswith((".pls", ".m3u", ".m3u8")):
        return stream_url

    async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
        response = await client.get(stream_url)
    response.raise_for_status()

    resolved_url = _playlist_stream_url_from_text(response.text)
    if resolved_url is None:
        raise HTTPException(status_code=422, detail="Radio playlist did not contain a playable stream URL.")
    _ensure_http_stream_url(resolved_url)
    return resolved_url


def _calculate_readiness(db: Session, item: LibraryItem) -> ReadinessResponse:
    tracks = list(
        db.scalars(
            select(PlaylistTrack)
            .where(PlaylistTrack.library_item_id == item.id)
            .order_by(PlaylistTrack.track_number.asc(), PlaylistTrack.id.asc())
        )
    )
    split_points = list(db.scalars(select(SplitPoint).where(SplitPoint.library_item_id == item.id)))
    source_size = _source_size_mb(db, item)
    target_size = _target_size_mb(db)
    cards = list(db.scalars(select(PhysicalCard).where(PhysicalCard.current_library_item_id == item.id)))

    checks = [
        ReadinessCheck(
            key="title",
            label="Title",
            ok=bool(item.title.strip()),
            detail="A playlist/card title is saved.",
        ),
        ReadinessCheck(
            key="cover",
            label="Cover artwork",
            ok=bool(item.cover_art_path),
            detail="Cover artwork is set." if item.cover_art_path else "Cover artwork still needs choosing.",
        ),
        ReadinessCheck(
            key="tracks",
            label="Track order",
            ok=bool(tracks) or _media_url_for_item(db, item) is not None,
            detail=f"{len(tracks)} track rows are saved." if tracks else "No track rows yet; source media can still be inspected.",
        ),
        ReadinessCheck(
            key="track_icons",
            label="Track icons",
            ok=not tracks or all(track.icon_path for track in tracks),
            detail="All track icons are set." if tracks and all(track.icon_path for track in tracks) else "Some tracks do not have icons yet.",
        ),
        ReadinessCheck(
            key="card_limits",
            label="Card limits",
            ok=source_size is None or source_size <= target_size,
            detail=(
                "Source size has not been measured yet."
                if source_size is None
                else f"Source is {source_size} MB against the {target_size} MB target."
            ),
        ),
        ReadinessCheck(
            key="split_plan",
            label="Split plan",
            ok=source_size is None or source_size <= target_size or bool(split_points),
            detail=(
                f"{len(split_points)} manual split point(s) saved."
                if split_points
                else "Oversized media will need a split plan before upload."
            ),
        ),
        ReadinessCheck(
            key="card_link",
            label="Card link",
            ok=bool(cards),
            detail="A physical card slot is associated." if cards else "No physical card slot selected yet.",
        ),
    ]

    status_text = "ready" if all(check.ok for check in checks) else "needs_review"
    item.readiness_status = status_text
    item.readiness_detail = "; ".join(check.detail for check in checks if not check.ok) or "Ready to prepare for Yoto."
    db.add(item)
    db.commit()
    return ReadinessResponse(library_item_id=item.id, status=status_text, checks=checks)


@router.get("", response_model=list[LibraryItemResponse])
async def list_library_items(
    db: Annotated[Session, Depends(get_db_session)],
    content_type: str | None = None,
    tag_id: int | None = None,
    search: str | None = None,
) -> list[LibraryItemResponse]:
    query = select(LibraryItem).order_by(LibraryItem.created_at.desc(), LibraryItem.id.desc())
    if content_type:
        query = query.where(LibraryItem.content_type == content_type)
    if tag_id is not None:
        query = query.join(
            TagAssignment,
            (TagAssignment.entity_type == "library_item") & (TagAssignment.entity_id == LibraryItem.id),
        ).where(TagAssignment.tag_id == tag_id)
    if search:
        query = query.where(LibraryItem.title.ilike(f"%{search.strip()}%"))
    return [_build_library_item_response(db, item) for item in db.scalars(query)]


@router.get("/{item_id}", response_model=LibraryItemDetailResponse)
async def get_library_item_detail(
    item_id: int,
    db: Annotated[Session, Depends(get_db_session)],
) -> LibraryItemDetailResponse:
    item = db.get(LibraryItem, item_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Library item not found")
    return _detail_for_item(db, item)


@router.get("/{item_id}/versions", response_model=list[VersionEventResponse])
async def list_library_item_versions(
    item_id: int,
    db: Annotated[Session, Depends(get_db_session)],
) -> list[VersionEventResponse]:
    item = db.get(LibraryItem, item_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Library item not found")
    events = db.scalars(
        select(VersionEvent)
        .where(VersionEvent.entity_type == "library_item")
        .where(VersionEvent.entity_id == item.id)
        .order_by(VersionEvent.version_number.desc(), VersionEvent.id.desc())
    )
    return [VersionEventResponse.model_validate(event, from_attributes=True) for event in events]


@router.post("/{item_id}/versions/{version_id}/restore", response_model=VersionRestoreResponse)
async def restore_library_item_version(
    item_id: int,
    version_id: int,
    db: Annotated[Session, Depends(get_db_session)],
) -> VersionRestoreResponse:
    item = db.get(LibraryItem, item_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Library item not found")
    version = db.get(VersionEvent, version_id)
    if version is None or version.entity_type != "library_item" or version.entity_id != item.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Version event not found")

    _restore_library_item_from_snapshot(db, item, version.snapshot_json)
    db.flush()
    restored_event = _record_library_version(
        db,
        item,
        "version_restored",
        f"Restored from version {version.version_number}.",
        version.created_by_user_id,
    )
    db.commit()
    db.refresh(item)
    db.refresh(restored_event)

    return VersionRestoreResponse(
        restored_from_version_id=version.id,
        restored_version_number=version.version_number,
        library_item=_detail_for_item(db, item),
        version_event=VersionEventResponse.model_validate(restored_event, from_attributes=True),
    )


@router.get("/{item_id}/media")
async def get_library_item_media(
    item_id: int,
    db: Annotated[Session, Depends(get_db_session)],
) -> FileResponse:
    item = db.get(LibraryItem, item_id)
    if item is None or item.source_import_id is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Media not found")
    import_request = db.get(ImportRequest, item.source_import_id)
    if import_request is None or not import_request.source_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Media not found")

    source_path = Path(import_request.source_path)
    if not _is_allowed_media_path(source_path) or not source_path.exists() or not source_path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Media not found")

    return FileResponse(source_path)


@router.get("/{item_id}/stream")
async def get_library_item_stream(
    item_id: int,
    db: Annotated[Session, Depends(get_db_session)],
) -> RedirectResponse:
    item = db.get(LibraryItem, item_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Library item not found")

    stream_track = _stream_track_for_item(db, item)
    if stream_track is None or not stream_track.stream_url:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Radio stream not found")

    try:
        resolved_stream_url = await _resolve_stream_url(stream_track.stream_url)
    except httpx.HTTPError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Radio stream playlist could not be resolved.",
        ) from error
    return RedirectResponse(resolved_stream_url)


@router.post("", response_model=LibraryItemResponse, status_code=201)
async def create_library_item(
    payload: LibraryItemCreate,
    db: Annotated[Session, Depends(get_db_session)],
) -> LibraryItemResponse:
    owner = None
    if payload.owner_user_slug:
        owner = db.scalar(select(User).where(User.slug == payload.owner_user_slug))

    item = LibraryItem(
        title=payload.title,
        content_type=payload.content_type,
        status="draft",
        cover_art_path=payload.cover_art_path,
        playlist_always_play_from_start=payload.playlist_always_play_from_start,
        playlist_shuffle_tracks=payload.playlist_shuffle_tracks,
        playlist_hide_track_numbers=payload.playlist_hide_track_numbers,
        notes=payload.notes,
        owner_user_id=owner.id if owner else None,
    )
    db.add(item)
    db.flush()
    _record_library_version(db, item, "library_item_created", "Library item created.")
    db.commit()
    db.refresh(item)
    return _build_library_item_response(db, item)


@router.put("/{item_id}/settings", response_model=LibraryItemResponse)
async def update_library_item_settings(
    item_id: int,
    payload: LibraryItemSettingsUpdate,
    db: Annotated[Session, Depends(get_db_session)],
) -> LibraryItemResponse:
    item = db.get(LibraryItem, item_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Library item not found")

    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, key, value)
    db.add(item)
    db.flush()
    _record_library_version(db, item, "settings_updated", "Playlist/card settings updated.")
    db.commit()
    db.refresh(item)
    return _build_library_item_response(db, item)


@router.post("/{item_id}/cover-art", response_model=LibraryItemResponse)
async def upload_library_item_cover_art(
    item_id: int,
    db: Annotated[Session, Depends(get_db_session)],
    artwork_file: UploadFile = File(...),
) -> LibraryItemResponse:
    item = db.get(LibraryItem, item_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Library item not found")
    if not artwork_file.filename:
        raise HTTPException(status_code=422, detail="Artwork upload requires a filename.")

    settings = get_settings()
    artwork_root = Path(settings.artwork_path).resolve(strict=False)
    artwork_root.mkdir(parents=True, exist_ok=True)
    destination = artwork_root / f"library-{item.id}-{_safe_artwork_filename(artwork_file.filename)}"

    with destination.open("wb") as output_file:
        while chunk := await artwork_file.read(1024 * 1024):
            output_file.write(chunk)

    item.cover_art_path = str(destination)
    item.status = "artwork_uploaded"
    db.add(item)
    db.add(
        ArtworkAsset(
            library_item_id=item.id,
            kind="source",
            status="available",
            source_path=str(destination),
            output_path=str(destination),
            settings_json=json.dumps({"upload_filename": artwork_file.filename}, sort_keys=True),
        )
    )
    db.flush()
    _record_library_version(db, item, "cover_art_uploaded", "Cover artwork uploaded.")
    db.commit()
    db.refresh(item)
    return _build_library_item_response(db, item)


@router.get("/{item_id}/artwork", response_model=list[ArtworkAssetResponse])
async def list_library_item_artwork(
    item_id: int,
    db: Annotated[Session, Depends(get_db_session)],
) -> list[ArtworkAssetResponse]:
    item = db.get(LibraryItem, item_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Library item not found")
    assets = db.scalars(
        select(ArtworkAsset)
        .where(ArtworkAsset.library_item_id == item.id)
        .order_by(ArtworkAsset.created_at.desc(), ArtworkAsset.id.desc())
    )
    return [_build_artwork_asset_response(asset) for asset in assets]


@router.post("/{item_id}/artwork/pixelise", response_model=JobResponse, status_code=202)
async def queue_library_item_artwork_pixelise(
    item_id: int,
    db: Annotated[Session, Depends(get_db_session)],
) -> JobResponse:
    item = db.get(LibraryItem, item_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Library item not found")
    if not item.cover_art_path:
        raise HTTPException(status_code=422, detail="Upload or choose cover artwork before pixelising.")

    job = Job(
        type="pixelise_artwork",
        status="queued",
        progress_percent=0,
        progress_message="Queued Yoto pixel artwork generation",
        related_library_item_id=item.id,
    )
    item.status = "artwork_pixelise_queued"
    item.readiness_status = "artwork_pixelise_queued"
    item.readiness_detail = "Pixel artwork generation queued."
    db.add(job)
    db.flush()
    _record_library_version(db, item, "artwork_pixelise_queued", "Queued pixel artwork generation.")
    db.commit()
    db.refresh(job)
    return JobResponse.model_validate(job, from_attributes=True)


@router.post("/{item_id}/tracks", response_model=PlaylistTrackResponse, status_code=201)
async def create_playlist_track(
    item_id: int,
    payload: PlaylistTrackCreate,
    db: Annotated[Session, Depends(get_db_session)],
) -> PlaylistTrackResponse:
    item = db.get(LibraryItem, item_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Library item not found")
    track = PlaylistTrack(library_item_id=item.id, **payload.model_dump())
    db.add(track)
    db.flush()
    _record_library_version(db, item, "track_created", f"Track added: {track.title}.")
    db.commit()
    db.refresh(track)
    return _build_track_response(track)


@router.put("/{item_id}/tracks/{track_id}", response_model=PlaylistTrackResponse)
async def update_playlist_track(
    item_id: int,
    track_id: int,
    payload: PlaylistTrackUpdate,
    db: Annotated[Session, Depends(get_db_session)],
) -> PlaylistTrackResponse:
    item = db.get(LibraryItem, item_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Library item not found")
    track = db.get(PlaylistTrack, track_id)
    if track is None or track.library_item_id != item.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Track not found")
    updates = payload.model_dump(exclude_unset=True)
    if "stream_url" in updates and updates["stream_url"]:
        _ensure_http_stream_url(updates["stream_url"])
    for key, value in updates.items():
        setattr(track, key, value)
    db.add(track)
    db.flush()
    _record_library_version(db, item, "track_updated", f"Track updated: {track.title}.")
    db.commit()
    db.refresh(track)
    return _build_track_response(track)


@router.post("/{item_id}/tracks/apply-icon", response_model=list[PlaylistTrackResponse])
async def apply_icon_to_tracks(
    item_id: int,
    payload: TrackIconApplyRequest,
    db: Annotated[Session, Depends(get_db_session)],
) -> list[PlaylistTrackResponse]:
    item = db.get(LibraryItem, item_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Library item not found")
    tracks = list(db.scalars(select(PlaylistTrack).where(PlaylistTrack.library_item_id == item.id)))
    for track in tracks:
        track.icon_path = payload.icon_path
        db.add(track)
    db.flush()
    _record_library_version(db, item, "track_icons_applied", "Track icon applied to all tracks.")
    db.commit()
    return [_build_track_response(track) for track in tracks]


@router.post("/{item_id}/radio-streams", response_model=PlaylistTrackResponse, status_code=201)
async def create_radio_stream_track(
    item_id: int,
    payload: RadioStreamCreate,
    db: Annotated[Session, Depends(get_db_session)],
) -> PlaylistTrackResponse:
    item = db.get(LibraryItem, item_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Library item not found")
    _ensure_http_stream_url(payload.stream_url)
    current_last_track = db.scalar(
        select(PlaylistTrack.track_number)
        .where(PlaylistTrack.library_item_id == item.id)
        .order_by(PlaylistTrack.track_number.desc())
    )
    track = PlaylistTrack(
        library_item_id=item.id,
        title=payload.title,
        source_url=payload.stream_url,
        track_number=payload.track_number or (current_last_track or 0) + 1,
        icon_path=payload.icon_path,
        track_behavior="continue",
        is_stream=True,
        stream_url=payload.stream_url,
    )
    job = Job(
        type="validate_radio_stream",
        status="queued",
        progress_percent=0,
        progress_message="Queued radio stream validation; radio cards require Wi-Fi and are not offline-ready.",
        related_library_item_id=item.id,
    )
    item.status = "radio_stream_validation_queued"
    db.add(track)
    db.add(job)
    db.add(item)
    db.flush()
    _record_library_version(db, item, "radio_stream_created", f"Radio stream added: {track.title}.")
    db.commit()
    db.refresh(track)
    return _build_track_response(track)


@router.post("/{item_id}/podcast-feeds", response_model=PodcastFeedResponse, status_code=201)
async def create_podcast_feed(
    item_id: int,
    payload: PodcastFeedCreate,
    db: Annotated[Session, Depends(get_db_session)],
) -> PodcastFeedResponse:
    item = db.get(LibraryItem, item_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Library item not found")

    metadata: dict[str, str | None] = {}
    episodes: list[dict[str, str | int | None]] = []
    if payload.rss_xml:
        try:
            metadata, episodes = _parse_podcast_xml(payload.rss_xml)
        except ET.ParseError as error:
            raise HTTPException(status_code=422, detail="RSS XML could not be parsed.") from error

    feed = PodcastFeed(
        library_item_id=item.id,
        rss_url=payload.rss_url,
        title=payload.title or metadata.get("title"),
        description=metadata.get("description"),
        artwork_url=metadata.get("artwork_url"),
    )
    db.add(feed)
    db.flush()
    for episode in episodes:
        db.add(PodcastEpisode(feed_id=feed.id, **episode))

    job = Job(
        type="inspect_podcast_feed",
        status="queued",
        progress_percent=0,
        progress_message=(
            "Podcast feed saved. Yoto may only keep recent episodes; fixed playlists should be built from selected episodes."
        ),
        related_library_item_id=item.id,
    )
    item.status = "podcast_feed_queued"
    db.add(job)
    db.add(item)
    db.flush()
    _record_library_version(db, item, "podcast_feed_created", f"Podcast feed added: {feed.title or feed.rss_url}.")
    db.commit()
    db.refresh(feed)
    return _build_podcast_feed_response(db, feed)


@router.post("/{item_id}/split-points", response_model=SplitPointResponse, status_code=201)
async def create_split_point(
    item_id: int,
    payload: SplitPointCreate,
    db: Annotated[Session, Depends(get_db_session)],
) -> SplitPointResponse:
    item = db.get(LibraryItem, item_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Library item not found")
    split_point = SplitPoint(library_item_id=item.id, **payload.model_dump())
    item.status = "split_plan_draft"
    db.add(split_point)
    db.add(item)
    db.flush()
    _record_library_version(db, item, "split_point_added", f"Split point added: {split_point.title}.")
    db.commit()
    db.refresh(split_point)
    return _build_split_point_response(split_point)


@router.get("/{item_id}/readiness", response_model=ReadinessResponse)
async def get_library_item_readiness(
    item_id: int,
    db: Annotated[Session, Depends(get_db_session)],
) -> ReadinessResponse:
    item = db.get(LibraryItem, item_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Library item not found")
    return _calculate_readiness(db, item)


@router.get("/{item_id}/card-plan", response_model=CardPlanResponse)
async def get_library_item_card_plan(
    item_id: int,
    db: Annotated[Session, Depends(get_db_session)],
) -> CardPlanResponse:
    item = db.get(LibraryItem, item_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Library item not found")
    return _build_card_plan(db, item)


@router.get("/{item_id}/card-plan/saved", response_model=CardPlanResponse)
async def get_saved_library_item_card_plan(
    item_id: int,
    db: Annotated[Session, Depends(get_db_session)],
) -> CardPlanResponse:
    item = db.get(LibraryItem, item_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Library item not found")
    return _build_saved_card_plan(db, item)


@router.put("/{item_id}/card-plan", response_model=CardPlanResponse)
async def save_library_item_card_plan(
    item_id: int,
    payload: CardPlanSaveRequest,
    db: Annotated[Session, Depends(get_db_session)],
) -> CardPlanResponse:
    item = db.get(LibraryItem, item_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Library item not found")

    track_ids = {
        track_id
        for part in payload.parts
        for track_id in (part.track_ids or [assignment.track_id for assignment in part.tracks or []])
    }
    existing_track_ids = set(
        db.scalars(
            select(PlaylistTrack.id)
            .where(PlaylistTrack.library_item_id == item.id)
            .where(PlaylistTrack.id.in_(track_ids) if track_ids else False)
        )
    )
    missing_track_ids = track_ids - existing_track_ids
    if missing_track_ids:
        raise HTTPException(status_code=422, detail=f"Track IDs do not belong to this item: {sorted(missing_track_ids)}")

    existing_part_ids = list(db.scalars(select(CardPlanPart.id).where(CardPlanPart.library_item_id == item.id)))
    if existing_part_ids:
        db.execute(delete(CardPlanTrackAssignment).where(CardPlanTrackAssignment.card_plan_part_id.in_(existing_part_ids)))
    db.execute(delete(CardPlanPart).where(CardPlanPart.library_item_id == item.id))
    db.flush()

    for part in sorted(payload.parts, key=lambda saved_part: saved_part.part_number):
        saved_part = CardPlanPart(
            library_item_id=item.id,
            part_number=part.part_number,
            title=part.title,
            estimated_duration_seconds=0,
            estimated_size_mb=0,
        )
        db.add(saved_part)
        db.flush()
        assignments = (
            [(assignment.track_id, assignment.track_order) for assignment in part.tracks]
            if part.tracks
            else [(track_id, index) for index, track_id in enumerate(part.track_ids or [], start=1)]
        )
        for track_id, track_order in assignments:
            db.add(
                CardPlanTrackAssignment(
                    card_plan_part_id=saved_part.id,
                    playlist_track_id=track_id,
                    track_order=track_order,
                )
            )

    item.status = "card_plan_saved"
    db.add(item)
    db.flush()
    _record_library_version(db, item, "card_plan_saved", "Saved card plan track assignments.")
    db.commit()
    db.refresh(item)
    return _build_saved_card_plan(db, item)


@router.post("/{item_id}/process", response_model=JobResponse, status_code=202)
async def queue_library_item_processing(
    item_id: int,
    db: Annotated[Session, Depends(get_db_session)],
) -> JobResponse:
    item = db.get(LibraryItem, item_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Library item not found")

    track_count = db.scalar(
        select(func.count(PlaylistTrack.id))
        .where(PlaylistTrack.library_item_id == item.id)
        .where(PlaylistTrack.is_stream.is_(False))
    )
    if not track_count:
        raise HTTPException(status_code=409, detail="Add or inspect non-stream tracks before processing.")

    item.status = "processing_queued"
    job = Job(
        type="transcode_audio",
        status="queued",
        progress_percent=0,
        progress_message="Queued Yoto-ready audio processing",
        related_library_item_id=item.id,
        related_import_id=item.source_import_id,
    )
    db.add(item)
    db.add(job)
    db.flush()
    _record_library_version(db, item, "processing_queued", "Queued Yoto-ready audio processing.")
    db.commit()
    db.refresh(job)
    return JobResponse.model_validate(job, from_attributes=True)


@router.post("/{item_id}/link-card", response_model=LinkCardResponse, status_code=202)
async def link_library_item_to_card(
    item_id: int,
    payload: LinkCardRequest,
    db: Annotated[Session, Depends(get_db_session)],
) -> LinkCardResponse:
    item = db.get(LibraryItem, item_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Library item not found")

    card = db.get(PhysicalCard, payload.card_id)
    if card is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Card not found")

    previous_library_item_id = card.current_library_item_id
    previous_status = card.status
    previous_yoto_playlist_uri = card.yoto_playlist_uri
    source_size_mb = _source_size_mb(db, item)
    requires_split_plan = source_size_mb is not None and source_size_mb > _target_size_mb(db)
    existing_remote_draft = db.scalar(
        select(YotoPlaylistDraft)
        .where(YotoPlaylistDraft.library_item_id == item.id)
        .where(
            (YotoPlaylistDraft.remote_playlist_id.is_not(None)) | (YotoPlaylistDraft.remote_playlist_uri.is_not(None))
        )
        .order_by(YotoPlaylistDraft.created_at.desc(), YotoPlaylistDraft.id.desc())
    )
    can_link_immediately = not requires_split_plan and existing_remote_draft is not None
    job_type = (
        "build_card_plan"
        if requires_split_plan
        else "link_yoto_card_ready"
        if can_link_immediately
        else "upload_yoto_asset"
    )
    progress_message = (
        "Queued to split media into card-sized parts"
        if requires_split_plan
        else "Remote Yoto content already exists; card is ready to program or link now"
        if can_link_immediately
        else "Queued to prepare Yoto upload and playlist link"
    )

    item.status = (
        "card_plan_queued"
        if requires_split_plan
        else "ready_to_link"
        if can_link_immediately
        else "yoto_upload_queued"
    )
    item.readiness_status = (
        item.readiness_status
        if requires_split_plan
        else "ready_to_link"
        if can_link_immediately
        else item.readiness_status
    )
    if can_link_immediately:
        remote_reference = existing_remote_draft.remote_playlist_uri or existing_remote_draft.remote_playlist_id
        item.readiness_detail = (
            f"Remote Yoto content already exists ({remote_reference}). Program or link the card now."
            if remote_reference
            else "Remote Yoto content already exists. Program or link the card now."
        )
    card.status = "planning" if requires_split_plan else "ready_to_link" if can_link_immediately else "upload_queued"
    card.current_library_item_id = item.id
    card.ready_to_link_in_app = not requires_split_plan
    card.needs_player_download = False
    if can_link_immediately and existing_remote_draft.remote_playlist_uri:
        card.yoto_playlist_uri = existing_remote_draft.remote_playlist_uri

    job = Job(
        type=job_type,
        status="queued" if not can_link_immediately else "succeeded",
        progress_percent=0 if not can_link_immediately else 100,
        progress_message=progress_message,
        related_library_item_id=item.id,
        related_import_id=item.source_import_id,
        related_card_id=card.id,
    )
    db.add(job)
    db.flush()
    card.pending_job_id = None if can_link_immediately else job.id

    db.add(item)
    db.add(card)
    db.flush()
    db.add(
        CardAssignmentEvent(
            card_id=card.id,
            event_type="link_prepared" if can_link_immediately else "link_queued",
            previous_library_item_id=previous_library_item_id,
            library_item_id=item.id,
            job_id=job.id,
            previous_status=previous_status,
            new_status=card.status,
            previous_yoto_playlist_uri=previous_yoto_playlist_uri,
            yoto_playlist_uri=card.yoto_playlist_uri,
            summary=(
                f"Prepared {card.display_name} for immediate Yoto linking."
                if can_link_immediately
                else f"Queued {card.display_name} for {item.title}."
            ),
        )
    )
    _record_library_version(
        db,
        item,
        "card_link_prepared" if can_link_immediately else "card_link_queued",
        (
            f"Prepared immediate link to {card.display_name} using existing remote Yoto content."
            if can_link_immediately
            else f"Queued link to {card.display_name}."
        ),
    )
    db.commit()
    db.refresh(item)
    db.refresh(card)
    db.refresh(job)

    return LinkCardResponse(
        library_item=_build_library_item_response(db, item),
        card=_build_card_response(card),
        job=JobResponse.model_validate(job, from_attributes=True),
        requires_split_plan=requires_split_plan,
        estimated_source_size_mb=source_size_mb,
    )
