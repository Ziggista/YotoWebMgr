from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
import json
from pathlib import Path
import subprocess


CommandRunner = Callable[[Sequence[str]], subprocess.CompletedProcess[str]]


@dataclass(frozen=True)
class ProbeChapter:
    title: str
    start_seconds: int
    end_seconds: int | None


@dataclass(frozen=True)
class ProbeResult:
    path: str
    title: str | None
    duration_seconds: int | None
    codec_name: str | None
    channels: int | None
    bit_rate: int | None
    chapters: list[ProbeChapter]


def _run_command(args: Sequence[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        check=False,
        capture_output=True,
        text=True,
    )


def _seconds(value: object) -> int | None:
    if value is None:
        return None
    try:
        return max(0, round(float(str(value))))
    except ValueError:
        return None


def _string_tag(tags: dict[str, object], *names: str) -> str | None:
    lowered = {key.lower(): value for key, value in tags.items()}
    for name in names:
        value = lowered.get(name.lower())
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _fallback_title(path: Path) -> str:
    cleaned = path.stem.replace("_", " ").replace("-", " ").strip()
    return " ".join(cleaned.split()) or path.stem


def inspect_media(path: str, *, command_runner: CommandRunner = _run_command) -> ProbeResult:
    media_path = Path(path)
    result = command_runner(
        [
            "ffprobe",
            "-v",
            "error",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            "-show_chapters",
            str(media_path),
        ]
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or "ffprobe failed"
        raise RuntimeError(detail)

    payload = json.loads(result.stdout or "{}")
    format_info = payload.get("format") if isinstance(payload.get("format"), dict) else {}
    streams = payload.get("streams") if isinstance(payload.get("streams"), list) else []
    chapters_payload = payload.get("chapters") if isinstance(payload.get("chapters"), list) else []

    audio_stream = next(
        (
            stream
            for stream in streams
            if isinstance(stream, dict) and stream.get("codec_type") == "audio"
        ),
        {},
    )
    format_tags = format_info.get("tags") if isinstance(format_info.get("tags"), dict) else {}
    title = _string_tag(format_tags, "title")

    chapters: list[ProbeChapter] = []
    for index, chapter in enumerate(chapters_payload, start=1):
        if not isinstance(chapter, dict):
            continue
        chapter_tags = chapter.get("tags") if isinstance(chapter.get("tags"), dict) else {}
        chapter_title = _string_tag(chapter_tags, "title") or f"Chapter {index}"
        chapters.append(
            ProbeChapter(
                title=chapter_title,
                start_seconds=_seconds(chapter.get("start_time")) or 0,
                end_seconds=_seconds(chapter.get("end_time")),
            )
        )

    return ProbeResult(
        path=str(media_path),
        title=title or _fallback_title(media_path),
        duration_seconds=_seconds(format_info.get("duration")),
        codec_name=audio_stream.get("codec_name") if isinstance(audio_stream.get("codec_name"), str) else None,
        channels=audio_stream.get("channels") if isinstance(audio_stream.get("channels"), int) else None,
        bit_rate=_seconds(format_info.get("bit_rate")),
        chapters=chapters,
    )
