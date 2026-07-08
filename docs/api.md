# API

## Base Path

`/api/v1`

## Initial Endpoints

- `GET /health`
- `GET /api/v1/health`
- `GET /api/v1/auth/providers`
- `POST /api/v1/auth/session/select`
- `POST /api/v1/auth/session/password`

Future areas will include library, tags, imports, playlists, cards, jobs, artwork, and settings.

## Library Processing

- `POST /api/v1/library/{item_id}/process`

Queues a `transcode_audio` worker job for non-stream source-backed tracks. Generated output is returned on the library detail response as `processed_assets`.

## Library History

- `GET /api/v1/library/{item_id}/versions`
- `POST /api/v1/library/{item_id}/versions/{version_id}/restore`

Library mutations write version events for the current item snapshot, including playlist settings, cover art, tracks, split points, podcast feeds, radio streams, and queued card links. Restoring a version applies that historical snapshot to the current editable library item, then creates a new `version_restored` event. Existing version events are retained.
