from datetime import UTC, datetime
import json
from pathlib import Path
import subprocess

import httpx
from sqlalchemy import create_engine, select

from app.jobs.runner import (
    artwork_assets,
    import_requests,
    jobs,
    library_items,
    metadata,
    playlist_tracks,
    processed_assets,
    settings,
)
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
                type="generate_artwork",
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
    assert "generate_artwork" in job.progress_message


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
                content_type="Audiobook",
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
    assert [track.source_start_seconds for track in tracks] == [0, 60]
    assert [track.source_end_seconds for track in tracks] == [60, 150]


def test_runner_transcodes_tracks_and_records_assets(tmp_path: Path) -> None:
    engine = _make_engine()
    with engine.begin() as connection:
        connection.execute(settings.insert().values(key="audiobook_bitrate_kbps", value="96"))
        connection.execute(settings.insert().values(key="music_bitrate_kbps", value="128"))
        connection.execute(settings.insert().values(key="normalise_loudness_default", value="true"))
        connection.execute(
            library_items.insert().values(
                id=30,
                title="A Processed Book",
                content_type="Audiobook",
                status="inspected",
                readiness_status="needs_card_plan",
            )
        )
        connection.execute(
            playlist_tracks.insert().values(
                id=11,
                library_item_id=30,
                title="Opening",
                source_path="/imports/book.m4b",
                source_start_seconds=0,
                source_end_seconds=60,
                track_number=1,
                duration_seconds=60,
                is_stream=False,
                track_behavior="continue",
            )
        )
        connection.execute(
            jobs.insert().values(
                id=4,
                type="transcode_audio",
                status="queued",
                pending_delete=False,
                retry_count=0,
                max_retries=3,
                progress_percent=0,
                progress_message="Queued",
                related_library_item_id=30,
                created_at=datetime.now(UTC),
            )
        )

    runner = JobRunner(engine, command_runner=_ffmpeg_runner, processed_root=str(tmp_path / "processed"))

    assert runner.process_once() is True
    with engine.begin() as connection:
        job = connection.execute(select(jobs).where(jobs.c.id == 4)).one()
        library_item = connection.execute(select(library_items).where(library_items.c.id == 30)).one()
        asset = connection.execute(select(processed_assets).where(processed_assets.c.library_item_id == 30)).one()

    assert job.status == "succeeded"
    assert library_item.status == "processed"
    assert library_item.readiness_status == "needs_yoto_upload"
    assert asset.playlist_track_id == 11
    assert asset.bitrate_kbps == 96
    assert asset.channels == 1
    assert asset.duration_seconds == 60
    assert asset.size_bytes == len(b"processed-audio")
    assert Path(asset.output_path).read_bytes() == b"processed-audio"


def test_runner_pixelises_artwork_and_records_asset(tmp_path: Path) -> None:
    from PIL import Image

    engine = _make_engine()
    source_path = tmp_path / "source.png"
    Image.new("RGB", (32, 24), color=(20, 100, 220)).save(source_path)

    with engine.begin() as connection:
        connection.execute(
            library_items.insert().values(
                id=40,
                title="Pixel Book",
                content_type="Story Collection",
                status="artwork_uploaded",
                cover_art_path=str(source_path),
                readiness_status="needs_review",
            )
        )
        connection.execute(
            artwork_assets.insert().values(
                id=7,
                library_item_id=40,
                kind="source",
                status="available",
                source_path=str(source_path),
                output_path=str(source_path),
                settings_json="{}",
            )
        )
        connection.execute(
            jobs.insert().values(
                id=8,
                type="pixelise_artwork",
                status="queued",
                pending_delete=False,
                retry_count=0,
                max_retries=3,
                progress_percent=0,
                progress_message="Queued",
                related_library_item_id=40,
                created_at=datetime.now(UTC),
            )
        )

    runner = JobRunner(engine, artwork_root=str(tmp_path / "artwork"))

    assert runner.process_once() is True
    with engine.begin() as connection:
        job = connection.execute(select(jobs).where(jobs.c.id == 8)).one()
        library_item = connection.execute(select(library_items).where(library_items.c.id == 40)).one()
        asset = connection.execute(
            select(artwork_assets)
            .where(artwork_assets.c.library_item_id == 40)
            .where(artwork_assets.c.kind == "pixelized")
        ).one()

    assert job.status == "succeeded"
    assert library_item.status == "artwork_pixelized"
    assert library_item.cover_art_path == asset.output_path
    assert asset.source_artwork_id == 7
    assert asset.width == 16
    assert asset.height == 16
    assert Path(asset.output_path).exists()


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


def _ffmpeg_runner(args: list[str]) -> subprocess.CompletedProcess[str]:
    assert args[0] == "ffmpeg"
    assert "-ss" in args
    assert "-to" in args
    assert "-af" in args
    output_path = Path(args[-1])
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(b"processed-audio")
    return subprocess.CompletedProcess(args, 0, stdout="", stderr="")
