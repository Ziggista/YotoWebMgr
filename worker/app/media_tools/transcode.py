from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path
import subprocess


CommandRunner = Callable[[Sequence[str]], subprocess.CompletedProcess[str]]


def _run_command(args: Sequence[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, check=False, capture_output=True, text=True)


def transcode_audio(
    *,
    source_path: str,
    output_path: str,
    bitrate_kbps: int,
    channels: int,
    start_seconds: int | None = None,
    end_seconds: int | None = None,
    normalise_loudness: bool = True,
    command_runner: CommandRunner | None = None,
) -> None:
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)

    args = ["ffmpeg", "-y"]
    if start_seconds is not None:
        args.extend(["-ss", str(start_seconds)])
    if end_seconds is not None:
        args.extend(["-to", str(end_seconds)])
    args.extend(["-i", source_path, "-vn", "-ac", str(channels), "-codec:a", "libmp3lame", "-b:a", f"{bitrate_kbps}k"])
    if normalise_loudness:
        args.extend(["-af", "loudnorm=I=-16:TP=-1.5:LRA=11"])
    args.append(str(destination))

    result = (command_runner or _run_command)(args)
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or "ffmpeg failed"
        raise RuntimeError(detail)
