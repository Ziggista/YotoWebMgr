from datetime import UTC, datetime
import json
import subprocess

import httpx
from sqlalchemy import create_engine, select

from app.jobs.runner import import_requests, jobs, library_items, metadata, playlist_tracks
from app.jobs.runner import JobRunner


def _make_engine():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    metadata.create_all(engine)
    return engine


def _http_client_for_playlist() -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url) == "https://example.test/radio.pls":
            return httpx.Response(
                200,
                text="[playlist]\nFile1=https://stream.example.test/live.mp3\n",
            )
        return httpx.Response(200, text="ok")

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_runner_validates_radio_stream_job() -> None:
    engine = _make_engine()
    with engine.begin() as connection:
        connection.execute(
            jobs.insert().values(
                id=1,
                type="validate_radio_stream",
                status="queued",
                pending_delete=False,
                retry_count=0,
                max_retries=3,
                progress_percent=0,
                progress_message="Queued",
                related_library_item_id=10,
                created_at=datetime.now(UTC),
            )
        )
        connection.execute(
            playlist_tracks.insert().values(
                id=1,
                library_item_id=10,
                title="Radio",
                track_number=1,
                is_stream=True,
                stream_url="https://example.test/radio.pls",
            )
        )

    runner = JobRunner(engine, http_client_factory=_http_client_for_playlist)

    assert runner.process_once() is True
    with engine.begin() as connection:
        job = connection.execute(select(jobs).where(jobs.c.id == 1)).one()

    assert job.status == "succeeded"
    assert job.progress_percent == 100
    assert "https://stream.example.test/live.mp3" in job.progress_message


def test_runner_marks_unknown_job_waiting() -> None:
    engine = _make_engine()
    with engine.begin() as connection:
        connection.execute(
            jobs.insert().values(
                id=1,
                type="transcode_audio",
                status="queued",
                pending_delete=False,
                retry_count=0,
                max_retries=3,
                progress_percent=0,
                progress_message="Queued",
                created_at=datetime.now(UTC),
            )
        )

    runner = JobRunner(engine)

    assert runner.process_once() is True
    with engine.begin() as connection:
        job = connection.execute(select(jobs).where(jobs.c.id == 1)).one()

    assert job.status == "waiting"
    assert "transcode_audio" in job.progress_message


def test_runner_inspects_media_and_creates_chapter_tracks() -> None:
    engine = _make_engine()
    with engine.begin() as connection:
        connection.execute(
            import_requests.insert().values(
                id=2,
                source_path="/imports/book.m4b",
                status="queued",
            )
        )
        connection.execute(
            library_items.insert().values(
                id=20,
                title="A Test Book",
                status="import_queued",
                readiness_status="needs_review",
            )
        )
        connection.execute(
            jobs.insert().values(
                id=3,
                type="inspect_media",
                status="queued",
                pending_delete=False,
                retry_count=0,
                max_retries=3,
                progress_percent=0,
                progress_message="Queued",
                related_library_item_id=20,
                related_import_id=2,
                created_at=datetime.now(UTC),
            )
        )

    runner = JobRunner(engine, command_runner=_ffprobe_runner)

    assert runner.process_once() is True
    with engine.begin() as connection:
        job = connection.execute(select(jobs).where(jobs.c.id == 3)).one()
        library_item = connection.execute(select(library_items).where(library_items.c.id == 20)).one()
        import_request = connection.execute(select(import_requests).where(import_requests.c.id == 2)).one()
        tracks = connection.execute(
            select(playlist_tracks)
            .where(playlist_tracks.c.library_item_id == 20)
            .order_by(playlist_tracks.c.track_number)
        ).all()

    assert job.status == "succeeded"
    assert job.progress_percent == 100
    assert library_item.status == "inspected"
    assert library_item.readiness_status == "needs_card_plan"
    assert "aac" in library_item.readiness_detail
    assert import_request.status == "inspected"
    assert [track.title for track in tracks] == ["Opening", "Middle"]
    assert [track.duration_seconds for track in tracks] == [60, 90]


def _ffprobe_runner(args: list[str]) -> subprocess.CompletedProcess[str]:
    assert args[:2] == ["ffprobe", "-v"]
    payload = {
        "format": {
            "duration": "150.2",
            "bit_rate": "96000",
            "tags": {"title": "Embedded Book Title"},
        },
        "streams": [
            {
                "codec_type": "audio",
                "codec_name": "aac",
                "channels": 2,
            }
        ],
        "chapters": [
            {
                "start_time": "0.0",
                "end_time": "60.0",
                "tags": {"title": "Opening"},
            },
            {
                "start_time": "60.0",
                "end_time": "150.0",
                "tags": {"title": "Middle"},
            },
        ],
    }
    return subprocess.CompletedProcess(args, 0, stdout=json.dumps(payload), stderr="")
