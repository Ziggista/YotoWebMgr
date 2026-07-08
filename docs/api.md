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

## Artwork

- `POST /api/v1/library/{item_id}/cover-art`
- `GET /api/v1/library/{item_id}/artwork`
- `POST /api/v1/library/{item_id}/artwork/pixelise`

Cover uploads are stored as source artwork assets. Pixelisation queues a `pixelise_artwork` worker
job that creates a deterministic 16x16 PNG derivative, records it separately, and updates the
library cover path to the generated Yoto-style artwork.

## Yoto Playlist Drafts

- `GET /api/v1/yoto/config`
- `GET /api/v1/yoto/library/{item_id}/playlist-preview`
- `GET /api/v1/yoto/library/{item_id}/playlists`
- `POST /api/v1/yoto/library/{item_id}/playlists`

The playlist preview maps local library tracks into the Yoto-shaped payload without a live API call.
Posting to `playlists` stores that payload as a durable local draft and queues a `create_yoto_playlist`
job. Until the confirmed live Yoto upload flow is implemented, the worker marks the draft ready for
manual linking rather than calling the remote API.

## Card Planning

- `GET /api/v1/library/{item_id}/card-plan`
- `GET /api/v1/library/{item_id}/card-plan/saved`
- `PUT /api/v1/library/{item_id}/card-plan`

The generated card plan remains a preview. Saving a card plan stores durable part rows and track assignments, records a version event, and lets later processing/upload workflows use explicit user-approved part boundaries.

## Library History

- `GET /api/v1/library/{item_id}/versions`
- `POST /api/v1/library/{item_id}/versions/{version_id}/restore`

Library mutations write version events for the current item snapshot, including playlist settings, cover art, tracks, split points, podcast feeds, radio streams, and queued card links. Restoring a version applies that historical snapshot to the current editable library item, then creates a new `version_restored` event. Existing version events are retained.
