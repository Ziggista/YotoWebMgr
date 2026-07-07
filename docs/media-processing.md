# Media Processing

Media processing will be orchestrated in Python and delegated to `ffprobe` and `ffmpeg`.

## Storage Layout

- `/media/originals`
- `/media/imports`
- `/media/processed`
- `/media/artwork`
- `/media/exports`
- `/media/temp`

## Import Staging

`/media/imports` is a persistent staging area mounted into both the API and worker pods.

- `/media/imports/drop` is for filesystem imports copied into the cluster storage.
- `/media/imports/uploads` is for browser uploads accepted by the API.
- Files staged under `/media/imports` are not treated as preserved originals yet. The worker must
  copy accepted media into `/media/originals` and record checksum/source metadata before processing.
- Filesystem imports are limited to `/media/imports/drop` in the API.

## Core Rules

- Never overwrite original media.
- Reuse processed assets by checksum and settings where possible.
- Capture ffmpeg stderr in job logs on failure.
