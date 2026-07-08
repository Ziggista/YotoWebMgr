from collections.abc import Callable
from datetime import UTC, datetime
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
    select,
    update,
)
from sqlalchemy.engine import Engine


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

playlist_tracks = Table(
    "playlist_tracks",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("library_item_id", Integer, nullable=False),
    Column("title", String(240), nullable=False),
    Column("track_number", Integer, nullable=False),
    Column("is_stream", Boolean, nullable=False, default=False),
    Column("stream_url", Text, nullable=True),
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
    ) -> None:
        self.engine = engine
        self.http_client_factory = http_client_factory or (
            lambda: httpx.Client(timeout=10, follow_redirects=True)
        )

    def process_once(self) -> bool:
        leased_job = self._lease_next_job()
        if leased_job is None:
            return False

        try:
            if leased_job.type == "validate_radio_stream":
                self._validate_radio_stream(leased_job.id, leased_job.related_library_item_id)
            else:
                self._mark_waiting(leased_job.id, f"Waiting for worker support for {leased_job.type}")
        except Exception as error:  # noqa: BLE001 - job failures need to be captured, not raised.
            self._mark_failed(leased_job.id, "Job failed", str(error))
        return True

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
