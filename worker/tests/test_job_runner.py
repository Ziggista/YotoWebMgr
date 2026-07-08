from datetime import UTC, datetime

import httpx
from sqlalchemy import create_engine, select

from app.jobs.runner import JobRunner, jobs, metadata, playlist_tracks


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
                type="inspect_media",
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
    assert "inspect_media" in job.progress_message
