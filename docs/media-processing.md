# Media Processing

Media processing will be orchestrated in Python and delegated to `ffprobe` and `ffmpeg`.

## Storage Layout

- `/media/originals`
- `/media/processed`
- `/media/artwork`
- `/media/exports`
- `/media/temp`

## Core Rules

- Never overwrite original media.
- Reuse processed assets by checksum and settings where possible.
- Capture ffmpeg stderr in job logs on failure.

