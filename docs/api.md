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

## Library History

- `GET /api/v1/library/{item_id}/versions`
- `POST /api/v1/library/{item_id}/versions/{version_id}/restore`

Library mutations write version events for the current item snapshot, including playlist settings, cover art, tracks, split points, podcast feeds, radio streams, and queued card links. Restoring a version applies that historical snapshot to the current editable library item, then creates a new `version_restored` event. Existing version events are retained.
