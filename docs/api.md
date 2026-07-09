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

## Imports

- `GET /api/v1/imports/sources`
- `GET /api/v1/imports`
- `POST /api/v1/imports`
- `POST /api/v1/imports/uploads`
- `PUT /api/v1/imports/{import_id}/review`
- `POST /api/v1/imports/{import_id}/approve`
- `POST /api/v1/imports/{import_id}/hide`

Filesystem imports are constrained to the configured import drop path. Browser uploads are staged
under the configured upload path and never written to the read-only CD/media source directory. ZIP
uploads are safely extracted under the upload path, reject path traversal entries, and create
ordered playlist tracks for supported audio files.

Import review endpoints let the UI correct title/content type, save review notes, and mark an
import approved while preserving the queued processing job and linked library item.

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

## Tags

- `GET /api/v1/tags`
- `POST /api/v1/tags`
- `GET /api/v1/tags/library-items/{item_id}`
- `PUT /api/v1/tags/library-items/{item_id}`

Tags are reusable household labels with normalized names and optional colors. Library items include
their assigned tags in list/detail responses and can be filtered with `tag_id`, `content_type`, and
`search` query parameters on `GET /api/v1/library`.

## Cards

- `GET /api/v1/cards`
- `POST /api/v1/cards`
- `GET /api/v1/cards/{card_id}`
- `GET /api/v1/cards/{card_id}/history`

Card link operations append immutable assignment history events. The history captures previous and
new library item/status values, related worker job IDs, playlist URIs when known, and a user-facing
summary so card restore workflows can be built without overwriting past state.
The frontend card detail page uses these endpoints to show identifiers, NFC metadata, workflow
flags, notes, and assignment events for a single physical card.

## Yoto Playlist Drafts

- `GET /api/v1/yoto/config`
- `GET /api/v1/yoto/credentials/status`
- `POST /api/v1/yoto/credentials/start`
- `POST /api/v1/yoto/credentials/callback`
- `POST /api/v1/yoto/credentials/disconnect`
- `GET /api/v1/yoto/playlists/{playlist_id}/versions`
- `POST /api/v1/yoto/playlists/{playlist_id}/versions/{version_id}/restore`
- `GET /api/v1/yoto/library/{item_id}/playlist-preview`
- `GET /api/v1/yoto/library/{item_id}/playlists`
- `POST /api/v1/yoto/library/{item_id}/playlists`

The credential endpoints support Yoto browser-based OAuth with PKCE. `start` stores local OAuth
state and returns a Yoto `/authorize` URL using the configured client ID, redirect URI, audience,
scope, and browser-generated code challenge. `callback` exchanges the returned code with Yoto's
token endpoint to prove authentication, then records connection metadata without persisting raw
access or refresh tokens. Token values and client secrets are intentionally excluded from API
responses and from the settings table.

The playlist preview maps local library tracks into the Yoto-shaped payload without a live API call.
Posting to `playlists` stores that payload as a durable local draft and queues a `create_yoto_playlist`
job. Until the confirmed live Yoto upload flow is implemented, the worker marks the draft ready for
manual linking rather than calling the remote API.

Each queued playlist draft records immutable playlist version snapshots. Restoring a playlist
version updates the local draft payload and creates a newer `restored` version; older versions remain
available.

## Card Planning

- `GET /api/v1/library/{item_id}/card-plan`
- `GET /api/v1/library/{item_id}/card-plan/saved`
- `PUT /api/v1/library/{item_id}/card-plan`

The generated card plan remains a preview. Saving a card plan stores durable part rows and track assignments, records a version event, and lets later processing/upload workflows use explicit user-approved part boundaries.

## Library History

- `GET /api/v1/library/{item_id}/versions`
- `POST /api/v1/library/{item_id}/versions/{version_id}/restore`

Library mutations write version events for the current item snapshot, including playlist settings, cover art, tracks, split points, podcast feeds, radio streams, and queued card links. Restoring a version applies that historical snapshot to the current editable library item, then creates a new `version_restored` event. Existing version events are retained.
