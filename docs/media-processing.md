# Media Processing

Media processing will be orchestrated in Python and delegated to `ffprobe` and `ffmpeg`.

## Storage Layout

- `/var/lib/yotowebmgr/media/originals`
- `/var/lib/yotowebmgr/media/imports`
- `/var/lib/yotowebmgr/media/processed`
- `/var/lib/yotowebmgr/media/artwork`
- `/var/lib/yotowebmgr/media/exports`
- `/var/lib/yotowebmgr/media/temp`

## Import Staging

`/var/lib/yotowebmgr/media/imports` is a persistent staging area mounted into both the API and worker pods.

- `/var/lib/yotowebmgr/media/imports/drop` is for filesystem imports copied into the cluster storage.
- `/var/lib/yotowebmgr/media/imports/uploads` is for browser uploads accepted by the API.
- Files staged under `/var/lib/yotowebmgr/media/imports` are not treated as preserved originals yet. The worker must
  copy accepted media into `/var/lib/yotowebmgr/media/originals` and record checksum/source metadata before processing.
- Filesystem imports are limited to `/var/lib/yotowebmgr/media/imports/drop` in the API.

## Core Rules

- Never overwrite original media.
- Reuse processed assets by checksum and settings where possible.
- Capture ffmpeg stderr in job logs on failure.
