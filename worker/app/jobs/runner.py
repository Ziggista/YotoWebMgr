from collections.abc import Callable
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
from urllib.parse import urlparse

import httpx
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    and_,
    create_engine,
    delete,
    insert,
    select,
    update,
)
from sqlalchemy.engine import Engine

from app.artwork.pixelise import pixelise_artwork
from app.media_tools.probe import CommandRunner, ProbeResult, inspect_media
from app.media_tools.transcode import transcode_audio


metadata = MetaData()

jobs = Table(
    "jobs",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("type", String(80), nullable=False),
    Column("status", String(32), nullable=False),
    Column("pending_delete", Boolean, nullable=False, default=False),
    Column("retry_count", Integer, nullable=False, default=0),
    Column("max_retries", Integer, nullable=False, default=3),
    Column("progress_percent", Integer, nullable=False, default=0),
    Column("progress_message", String(240), nullable=False, default="Queued"),
    Column("error_summary", String(240), nullable=True),
    Column("error_detail", Text, nullable=True),
    Column("related_library_item_id", Integer, nullable=True),
    Column("related_import_id", Integer, nullable=True),
    Column("related_card_id", Integer, nullable=True),
    Column("started_at", DateTime(timezone=True), nullable=True),
    Column("finished_at", DateTime(timezone=True), nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=True),
    Column("updated_at", DateTime(timezone=True), nullable=True),
)

import_requests = Table(
    "import_requests",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("source_path", Text, nullable=True),
    Column("status", String(64), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=True),
)

library_items = Table(
    "library_items",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("title", String(240), nullable=False),
    Column("content_type", String(64), nullable=False),
    Column("status", String(64), nullable=False),
    Column("cover_art_path", Text, nullable=True),
    Column("readiness_status", String(80), nullable=False),
    Column("readiness_detail", Text, nullable=True),
    Column("updated_at", DateTime(timezone=True), nullable=True),
)

playlist_tracks = Table(
    "playlist_tracks",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("library_item_id", Integer, nullable=False),
    Column("title", String(240), nullable=False),
    Column("source_path", Text, nullable=True),
    Column("source_start_seconds", Integer, nullable=True),
    Column("source_end_seconds", Integer, nullable=True),
    Column("track_number", Integer, nullable=False),
    Column("duration_seconds", Integer, nullable=True),
    Column("is_stream", Boolean, nullable=False, default=False),
    Column("stream_url", Text, nullable=True),
    Column("track_behavior", String(80), nullable=False, default="continue"),
    Column("updated_at", DateTime(timezone=True), nullable=True),
)

settings = Table(
    "settings",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("key", String(120), nullable=False),
    Column("value", String(500), nullable=False),
)

processed_assets = Table(
    "processed_assets",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("library_item_id", Integer, nullable=False),
    Column("playlist_track_id", Integer, nullable=True),
    Column("source_path", Text, nullable=False),
    Column("output_path", Text, nullable=False),
    Column("codec", String(80), nullable=False),
    Column("bitrate_kbps", Integer, nullable=False),
    Column("channels", Integer, nullable=False),
    Column("duration_seconds", Integer, nullable=True),
    Column("size_bytes", Integer, nullable=False),
    Column("checksum_sha256", String(64), nullable=False),
    Column("profile", String(80), nullable=False),
    Column("settings_json", Text, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=True),
)

artwork_assets = Table(
    "artwork_assets",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("library_item_id", Integer, nullable=False),
    Column("source_artwork_id", Integer, nullable=True),
    Column("kind", String(80), nullable=False),
    Column("status", String(80), nullable=False),
    Column("source_path", Text, nullable=False),
    Column("output_path", Text, nullable=True),
    Column("width", Integer, nullable=True),
    Column("height", Integer, nullable=True),
    Column("palette", String(80), nullable=True),
    Column("settings_json", Text, nullable=False),
    Column("checksum_sha256", String(64), nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=True),
    Column("updated_at", DateTime(timezone=True), nullable=True),
)

yoto_playlist_drafts = Table(
    "yoto_playlist_drafts",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("library_item_id", Integer, nullable=False),
    Column("related_job_id", Integer, nullable=True),
    Column("title", String(240), nullable=False),
    Column("status", String(80), nullable=False),
    Column("payload_json", Text, nullable=False),
    Column("remote_playlist_id", String(240), nullable=True),
    Column("remote_playlist_uri", String(500), nullable=True),
    Column("last_error", Text, nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=True),
    Column("updated_at", DateTime(timezone=True), nullable=True),
)


def create_worker_engine(database_url: str) -> Engine:
    return create_engine(database_url, pool_pre_ping=True)


def playlist_stream_url_from_text(playlist_text: str) -> str | None:
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


class JobRunner:
    def __init__(
        self,
        engine: Engine,
        *,
        http_client_factory: Callable[[], httpx.Client] | None = None,
        command_runner: CommandRunner | None = None,
        processed_root: str = "/var/lib/yotowebmgr/media/processed",
        artwork_root: str = "/var/lib/yotowebmgr/media/artwork",
    ) -> None:
        self.engine = engine
        self.http_client_factory = http_client_factory or (
            lambda: httpx.Client(timeout=10, follow_redirects=True)
        )
        self.command_runner = command_runner
        self.processed_root = Path(processed_root)
        self.artwork_root = Path(artwork_root)

    def process_once(self) -> bool:
        leased_job = self._lease_next_job()
        if leased_job is None:
            return False

        try:
            if leased_job.type == "validate_radio_stream":
                self._validate_radio_stream(leased_job.id, leased_job.related_library_item_id)
            elif leased_job.type in {"inspect_media", "extract_zip_import"}:
                self._inspect_media(
                    leased_job.id,
                    leased_job.related_library_item_id,
                    leased_job.related_import_id,
                )
            elif leased_job.type == "transcode_audio":
                self._transcode_audio(leased_job.id, leased_job.related_library_item_id)
            elif leased_job.type == "create_yoto_playlist":
                self._prepare_yoto_playlist(leased_job.id, leased_job.related_library_item_id)
            elif leased_job.type == "pixelise_artwork":
                self._pixelise_artwork(leased_job.id, leased_job.related_library_item_id)
            else:
                self._mark_waiting(leased_job.id, f"Waiting for worker support for {leased_job.type}")
        except Exception as error:  # noqa: BLE001 - job failures need to be captured, not raised.
            self._mark_failed(leased_job.id, "Job failed", str(error))
        return True

    def _probe(self, path: str) -> ProbeResult:
        if self.command_runner is None:
            return inspect_media(path)
        return inspect_media(path, command_runner=self.command_runner)

    def _lease_next_job(self):
        with self.engine.begin() as connection:
            row = connection.execute(
                select(jobs)
                .where(and_(jobs.c.status.in_(["queued", "retrying"]), jobs.c.pending_delete.is_(False)))
                .order_by(jobs.c.created_at.asc(), jobs.c.id.asc())
                .limit(1)
            ).first()
            if row is None:
                return None

            now = datetime.now(UTC)
            result = connection.execute(
                update(jobs)
                .where(and_(jobs.c.id == row.id, jobs.c.status.in_(["queued", "retrying"])))
                .values(
                    status="running",
                    started_at=now,
                    updated_at=now,
                    progress_percent=5,
                    progress_message="Worker leased job",
                    error_summary=None,
                    error_detail=None,
                )
            )
            if result.rowcount != 1:
                return None

            return row

    def _validate_radio_stream(self, job_id: int, library_item_id: int | None) -> None:
        if library_item_id is None:
            raise RuntimeError("Radio validation job is missing a library item.")

        with self.engine.begin() as connection:
            track = connection.execute(
                select(playlist_tracks)
                .where(
                    and_(
                        playlist_tracks.c.library_item_id == library_item_id,
                        playlist_tracks.c.is_stream.is_(True),
                        playlist_tracks.c.stream_url.is_not(None),
                    )
                )
                .order_by(playlist_tracks.c.track_number.asc(), playlist_tracks.c.id.asc())
                .limit(1)
            ).first()
        if track is None or not track.stream_url:
            raise RuntimeError("No stream track found for radio validation.")

        resolved_url = self._resolve_stream_url(track.stream_url)
        self._mark_succeeded(job_id, f"Radio stream validated: {resolved_url}")

    def _inspect_media(
        self,
        job_id: int,
        library_item_id: int | None,
        import_id: int | None,
    ) -> None:
        if library_item_id is None:
            raise RuntimeError("Media inspection job is missing a library item.")

        self._mark_running(job_id, 15, "Inspecting source media with ffprobe")
        with self.engine.begin() as connection:
            library_item = connection.execute(
                select(library_items).where(library_items.c.id == library_item_id)
            ).first()
            if library_item is None:
                raise RuntimeError("Media inspection job references a missing library item.")

            import_request = (
                connection.execute(select(import_requests).where(import_requests.c.id == import_id)).first()
                if import_id is not None
                else None
            )
            existing_tracks = connection.execute(
                select(playlist_tracks)
                .where(
                    and_(
                        playlist_tracks.c.library_item_id == library_item_id,
                        playlist_tracks.c.is_stream.is_(False),
                    )
                )
                .order_by(playlist_tracks.c.track_number.asc(), playlist_tracks.c.id.asc())
            ).all()

        source_paths = [track.source_path for track in existing_tracks if track.source_path]
        if not source_paths and import_request is not None and import_request.source_path:
            source_paths = [import_request.source_path]
        if not source_paths:
            raise RuntimeError("No source media path found for inspection.")

        probes = [self._probe(path) for path in source_paths]
        self._mark_running(job_id, 70, "Saving inspected track metadata")
        self._save_inspection(
            library_item_id=library_item_id,
            import_id=import_id,
            item_title=library_item.title,
            probes=probes,
        )
        total_duration = sum(probe.duration_seconds or 0 for probe in probes)
        message = f"Inspected {len(probes)} source file(s)"
        if total_duration:
            message = f"{message}, {total_duration // 60} min total"
        self._mark_succeeded(job_id, message)

    def _resolve_stream_url(self, stream_url: str) -> str:
        parsed_url = urlparse(stream_url)
        if parsed_url.scheme not in {"http", "https"}:
            raise RuntimeError("Radio stream URL must use http or https.")

        with self.http_client_factory() as client:
            response = client.get(stream_url)
            response.raise_for_status()
            if parsed_url.path.lower().endswith((".pls", ".m3u", ".m3u8")):
                resolved_url = playlist_stream_url_from_text(response.text)
                if resolved_url is None:
                    raise RuntimeError("Radio playlist did not contain a playable stream URL.")
                return resolved_url
        return stream_url

    def _save_inspection(
        self,
        *,
        library_item_id: int,
        import_id: int | None,
        item_title: str,
        probes: list[ProbeResult],
    ) -> None:
        now = datetime.now(UTC)
        detail = _inspection_detail(probes)
        with self.engine.begin() as connection:
            connection.execute(
                delete(playlist_tracks).where(
                    and_(
                        playlist_tracks.c.library_item_id == library_item_id,
                        playlist_tracks.c.is_stream.is_(False),
                    )
                )
            )
            track_number = 1
            for probe in probes:
                if probe.chapters:
                    for chapter in probe.chapters:
                        duration = (
                            chapter.end_seconds - chapter.start_seconds
                            if chapter.end_seconds is not None
                            else None
                        )
                        connection.execute(
                            insert(playlist_tracks).values(
                                library_item_id=library_item_id,
                                title=chapter.title,
                                source_path=probe.path,
                                source_start_seconds=chapter.start_seconds,
                                source_end_seconds=chapter.end_seconds,
                                track_number=track_number,
                                duration_seconds=duration,
                                is_stream=False,
                                track_behavior="continue",
                                updated_at=now,
                            )
                        )
                        track_number += 1
                else:
                    connection.execute(
                        insert(playlist_tracks).values(
                            library_item_id=library_item_id,
                            title=probe.title or item_title or Path(probe.path).stem,
                            source_path=probe.path,
                            source_start_seconds=None,
                            source_end_seconds=None,
                            track_number=track_number,
                            duration_seconds=probe.duration_seconds,
                            is_stream=False,
                            track_behavior="continue",
                            updated_at=now,
                        )
                    )
                    track_number += 1

            connection.execute(
                update(library_items)
                .where(library_items.c.id == library_item_id)
                .values(
                    status="inspected",
                    readiness_status="needs_card_plan",
                    readiness_detail=detail,
                    updated_at=now,
                )
            )
            if import_id is not None:
                connection.execute(
                    update(import_requests)
                    .where(import_requests.c.id == import_id)
                    .values(status="inspected", updated_at=now)
                )

    def _transcode_audio(self, job_id: int, library_item_id: int | None) -> None:
        if library_item_id is None:
            raise RuntimeError("Transcode job is missing a library item.")

        self._mark_running(job_id, 10, "Loading tracks for Yoto-ready processing")
        with self.engine.begin() as connection:
            library_item = connection.execute(
                select(library_items).where(library_items.c.id == library_item_id)
            ).first()
            if library_item is None:
                raise RuntimeError("Transcode job references a missing library item.")
            tracks = connection.execute(
                select(playlist_tracks)
                .where(
                    and_(
                        playlist_tracks.c.library_item_id == library_item_id,
                        playlist_tracks.c.is_stream.is_(False),
                        playlist_tracks.c.source_path.is_not(None),
                    )
                )
                .order_by(playlist_tracks.c.track_number.asc(), playlist_tracks.c.id.asc())
            ).all()
            setting_rows = connection.execute(select(settings.c.key, settings.c.value)).all()

        if not tracks:
            raise RuntimeError("No source-backed tracks are available for transcoding.")

        setting_values = {row.key: row.value for row in setting_rows}
        spoken_word = library_item.content_type in {"Audiobook", "Story Collection", "Podcast", "Sleep Sounds"}
        profile = "spoken_word" if spoken_word else "music"
        bitrate_kbps = _int_setting(
            setting_values,
            "audiobook_bitrate_kbps" if spoken_word else "music_bitrate_kbps",
            96 if spoken_word else 128,
        )
        channels = 1 if spoken_word else 2
        normalise_loudness = setting_values.get("normalise_loudness_default", "true").lower() == "true"
        settings_json = json.dumps(
            {
                "bitrate_kbps": bitrate_kbps,
                "channels": channels,
                "normalise_loudness": normalise_loudness,
                "profile": profile,
            },
            sort_keys=True,
        )

        now = datetime.now(UTC)
        with self.engine.begin() as connection:
            connection.execute(delete(processed_assets).where(processed_assets.c.library_item_id == library_item_id))

        for index, track in enumerate(tracks, start=1):
            progress = 10 + round((index - 1) / len(tracks) * 75)
            self._mark_running(job_id, progress, f"Encoding track {index} of {len(tracks)}")
            output_path = self.processed_root / f"library-{library_item_id}" / f"{track.track_number:03d}-{track.id}.mp3"
            transcode_audio(
                source_path=track.source_path,
                output_path=str(output_path),
                bitrate_kbps=bitrate_kbps,
                channels=channels,
                start_seconds=track.source_start_seconds,
                end_seconds=track.source_end_seconds,
                normalise_loudness=normalise_loudness,
                command_runner=self.command_runner if self.command_runner is not None else None,
            )
            checksum = _sha256(output_path)
            size_bytes = output_path.stat().st_size
            duration_seconds = track.duration_seconds
            with self.engine.begin() as connection:
                connection.execute(
                    insert(processed_assets).values(
                        library_item_id=library_item_id,
                        playlist_track_id=track.id,
                        source_path=track.source_path,
                        output_path=str(output_path),
                        codec="mp3",
                        bitrate_kbps=bitrate_kbps,
                        channels=channels,
                        duration_seconds=duration_seconds,
                        size_bytes=size_bytes,
                        checksum_sha256=checksum,
                        profile=profile,
                        settings_json=settings_json,
                        created_at=now,
                    )
                )

        with self.engine.begin() as connection:
            connection.execute(
                update(library_items)
                .where(library_items.c.id == library_item_id)
                .values(
                    status="processed",
                    readiness_status="needs_yoto_upload",
                    readiness_detail=f"Generated {len(tracks)} Yoto-ready MP3 asset(s).",
                    updated_at=datetime.now(UTC),
                )
            )
        self._mark_succeeded(job_id, f"Generated {len(tracks)} Yoto-ready MP3 asset(s)")

    def _prepare_yoto_playlist(self, job_id: int, library_item_id: int | None) -> None:
        if library_item_id is None:
            raise RuntimeError("Yoto playlist job is missing a library item.")

        self._mark_running(job_id, 20, "Loading local Yoto playlist draft")
        now = datetime.now(UTC)
        with self.engine.begin() as connection:
            draft = connection.execute(
                select(yoto_playlist_drafts)
                .where(yoto_playlist_drafts.c.related_job_id == job_id)
                .order_by(yoto_playlist_drafts.c.id.desc())
                .limit(1)
            ).first()
            if draft is None:
                raise RuntimeError("Yoto playlist job references a missing playlist draft.")

            json.loads(draft.payload_json)
            connection.execute(
                update(yoto_playlist_drafts)
                .where(yoto_playlist_drafts.c.id == draft.id)
                .values(
                    status="awaiting_remote_mapping",
                    last_error=None,
                    updated_at=now,
                )
            )
            connection.execute(
                update(library_items)
                .where(library_items.c.id == library_item_id)
                .values(
                    status="awaiting_remote_mapping",
                    readiness_status="awaiting_remote_mapping",
                    readiness_detail=(
                        "Local Yoto playlist payload is ready. Find or create the remote Yoto playlist, "
                        "then record its playlist URI or ID before NFC linking."
                    ),
                    updated_at=now,
                )
            )

        self._mark_succeeded(job_id, "Yoto playlist draft ready for remote mapping")

    def _pixelise_artwork(self, job_id: int, library_item_id: int | None) -> None:
        if library_item_id is None:
            raise RuntimeError("Artwork pixelisation job is missing a library item.")

        self._mark_running(job_id, 15, "Loading cover artwork")
        with self.engine.begin() as connection:
            library_item = connection.execute(
                select(library_items).where(library_items.c.id == library_item_id)
            ).first()
            if library_item is None:
                raise RuntimeError("Artwork pixelisation job references a missing library item.")
            if not library_item.cover_art_path:
                raise RuntimeError("Library item has no cover artwork to pixelise.")
            source_asset = connection.execute(
                select(artwork_assets)
                .where(
                    and_(
                        artwork_assets.c.library_item_id == library_item_id,
                        artwork_assets.c.source_path == library_item.cover_art_path,
                    )
                )
                .order_by(artwork_assets.c.id.desc())
                .limit(1)
            ).first()

        source_path = Path(library_item.cover_art_path)
        if not source_path.exists():
            raise RuntimeError("Cover artwork file is missing from storage.")

        settings_json = json.dumps({"size": 16, "colors": 16, "method": "center_crop_nearest"}, sort_keys=True)
        source_hash = _sha256(source_path)
        output_path = self.artwork_root / f"library-{library_item_id}" / f"pixel-{source_hash[:16]}-16.png"

        self._mark_running(job_id, 55, "Generating pixel artwork")
        width, height = pixelise_artwork(source_path=str(source_path), output_path=str(output_path), size=16, colors=16)
        checksum = _sha256(output_path)
        now = datetime.now(UTC)
        with self.engine.begin() as connection:
            connection.execute(
                insert(artwork_assets).values(
                    library_item_id=library_item_id,
                    source_artwork_id=source_asset.id if source_asset is not None else None,
                    kind="pixelized",
                    status="available",
                    source_path=str(source_path),
                    output_path=str(output_path),
                    width=width,
                    height=height,
                    palette="adaptive_16",
                    settings_json=settings_json,
                    checksum_sha256=checksum,
                    created_at=now,
                    updated_at=now,
                )
            )
            connection.execute(
                update(library_items)
                .where(library_items.c.id == library_item_id)
                .values(
                    status="artwork_pixelized",
                    cover_art_path=str(output_path),
                    readiness_status="artwork_ready",
                    readiness_detail="Pixel artwork generated for Yoto playlist use.",
                    updated_at=now,
                )
            )

        self._mark_succeeded(job_id, "Pixel artwork generated")

    def _mark_running(self, job_id: int, progress_percent: int, message: str) -> None:
        now = datetime.now(UTC)
        with self.engine.begin() as connection:
            connection.execute(
                update(jobs)
                .where(jobs.c.id == job_id)
                .values(
                    status="running",
                    progress_percent=progress_percent,
                    progress_message=message[:240],
                    updated_at=now,
                )
            )

    def _mark_succeeded(self, job_id: int, message: str) -> None:
        now = datetime.now(UTC)
        with self.engine.begin() as connection:
            connection.execute(
                update(jobs)
                .where(jobs.c.id == job_id)
                .values(
                    status="succeeded",
                    progress_percent=100,
                    progress_message=message[:240],
                    finished_at=now,
                    updated_at=now,
                    error_summary=None,
                    error_detail=None,
                )
            )

    def _mark_waiting(self, job_id: int, message: str) -> None:
        now = datetime.now(UTC)
        with self.engine.begin() as connection:
            connection.execute(
                update(jobs)
                .where(jobs.c.id == job_id)
                .values(
                    status="waiting",
                    progress_message=message[:240],
                    updated_at=now,
                )
            )

    def _mark_failed(self, job_id: int, summary: str, detail: str) -> None:
        now = datetime.now(UTC)
        with self.engine.begin() as connection:
            connection.execute(
                update(jobs)
                .where(jobs.c.id == job_id)
                .values(
                    status="failed",
                    progress_message="Failed",
                    error_summary=summary[:240],
                    error_detail=detail,
                    finished_at=now,
                    updated_at=now,
                )
            )


def _inspection_detail(probes: list[ProbeResult]) -> str:
    parts: list[str] = []
    for probe in probes:
        codec = probe.codec_name or "unknown codec"
        channels = f"{probe.channels}ch" if probe.channels else "unknown channels"
        duration = f"{probe.duration_seconds}s" if probe.duration_seconds is not None else "unknown duration"
        chapter_text = f"{len(probe.chapters)} chapter(s)" if probe.chapters else "no embedded chapters"
        parts.append(f"{Path(probe.path).name}: {duration}, {codec}, {channels}, {chapter_text}")
    return "; ".join(parts)[:1000]


def _int_setting(setting_values: dict[str, str], key: str, default: int) -> int:
    try:
        return int(setting_values.get(key, str(default)))
    except ValueError:
        return default


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as asset_file:
        for chunk in iter(lambda: asset_file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
