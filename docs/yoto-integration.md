# Yoto Integration

Yoto integration will live in dedicated Python modules under:

- `backend/app/integrations/yoto/`
- `worker/app/yoto/`

## Responsibilities

- OAuth and token refresh
- Asset upload preparation
- Playlist creation and update
- Remote/local ID mapping
- Retry-aware error classification

## API Configuration Settings

The settings table stores non-secret Yoto integration configuration only:

- `yoto_api_enabled`
- `yoto_api_base_url`
- `yoto_auth_base_url`
- `yoto_client_id`
- `yoto_redirect_uri`
- `yoto_oauth_scope`
- `yoto_upload_timeout_seconds`
- `yoto_transcode_poll_seconds`
- `yoto_transcode_timeout_minutes`

Refresh tokens, access tokens, client secrets, and encrypted token material must be stored through
Kubernetes Secrets or a dedicated encrypted token store, not in generic application settings.

These values are intentionally editable placeholders until the exact Yoto-supported OAuth, upload,
playlist, and transcode-polling workflows are confirmed against live credentials and current docs.
The current codebase now uses a hybrid approach:

- The queued `create_yoto_playlist` worker still prepares durable local drafts only.
- `POST /api/v1/yoto/playlists/{playlist_id}/create-live` can now upload processed/local audio to
  Yoto on demand, poll for Yoto's transcode result, and then create live `/content` from the
  generated `yoto:#sha256` track references.

## Local Preview Endpoints

The API exposes local-only Yoto scaffolding endpoints:

- `GET /api/v1/yoto/config` reports non-secret Yoto configuration state.
- `GET /api/v1/yoto/credentials/status` reports the locally stored Yoto connection state without
  exposing tokens or secrets.
- `POST /api/v1/yoto/credentials/start` validates the configured client ID and redirect URI,
  stores an `authorization_started` credential record, and returns a Yoto browser-auth
  `/authorize` URL using the browser-generated PKCE code challenge. It does not call Yoto.
- `POST /api/v1/yoto/credentials/callback` validates the returned OAuth state and exchanges the
  authorization code with Yoto's `/oauth/token` endpoint using the browser-held PKCE verifier. This
  is a live auth call and persists the returned token payload in a Kubernetes Secret.
- `POST /api/v1/yoto/credentials/disconnect` clears local token references and marks the stored
  credential state as `revoked`. It does not make a live revoke call.
- `POST /api/v1/yoto/credentials/probe` and `POST /api/v1/yoto/debug/request` use the stored token
  material to test live Yoto API calls, including token refresh if needed.
- `GET /api/v1/yoto/playlists/{playlist_id}/versions` lists immutable local payload snapshots for a
  queued Yoto playlist draft.
- `POST /api/v1/yoto/playlists/{playlist_id}/versions/{version_id}/restore` restores a draft to a
  prior local snapshot and records a newer `restored` version.
- `GET /api/v1/yoto/playlists/{playlist_id}/remote-payload` converts a local draft into the current
  live `POST /content` request shape.
- `POST /api/v1/yoto/playlists/{playlist_id}/create-live` submits that payload to Yoto and stores
  the returned remote card/content identifier on the local draft. For local audio chapters it now
  requests a Yoto upload URL, uploads the processed or source file, polls Yoto transcode status,
  and builds the final `/content` payload from the returned `transcodedSha256`.
- `GET /api/v1/yoto/library/{item_id}/playlist-preview` maps a local library item and its tracks
  into a Yoto-shaped playlist payload without making a live Yoto API call.
- `GET /api/v1/yoto/library/{item_id}/playlists` lists stored local playlist drafts.
- `POST /api/v1/yoto/library/{item_id}/playlists` stores a draft payload and queues
  `create_yoto_playlist`.

The preview endpoint is deliberately not an upload action. The queue endpoint persists the payload,
creates a trackable worker job, and currently advances the draft to `awaiting_remote_mapping` after
local preparation. Audio upload still does not happen in that worker step; it happens during the
explicit live-create call so the user can test and inspect it directly from the app.

## Current Tested End-to-End Flow

As of July 19, 2026, the working repeatable live test path is:

1. Upload media through `POST /api/v1/imports/uploads` or the Import screen.
2. Wait for `inspect_media` to succeed so the library item has concrete playlist tracks.
3. Run `POST /api/v1/library/{item_id}/process` and wait for `transcode_audio` to succeed.
4. Run `POST /api/v1/yoto/library/{item_id}/playlists` and wait for `create_yoto_playlist` to
   settle the draft into `awaiting_remote_mapping`.
5. Optionally inspect `GET /api/v1/yoto/playlists/{playlist_id}/remote-payload`.
6. Run `POST /api/v1/yoto/playlists/{playlist_id}/create-live` to upload the processed/source
   audio to Yoto, wait through Yoto transcode, and create live `/content`.

This flow was verified against the Alice LibriVox sample and returned a live Yoto card/content ID.

Do not treat a hardcoded `/var/lib/yotowebmgr/media/imports/drop/...` source path from a previous
destructive dev deploy as stable. After namespace deletion, that PVC may be empty even when a local
workspace copy still exists on the Windows filesystem.

For local browser testing, set the redirect URI to the frontend callback route, for example
`http://127.0.0.1:5175/settings/yoto/callback`, and register the same URI with the Yoto developer
application.

For remote Tailscale-host testing, the current deployed redirect URI is:

`http://ziggi-pc-1.tailaf3d4b.ts.net:5175/settings/yoto/callback`

That origin is HTTP rather than HTTPS, so browser support for `SubtleCrypto` is inconsistent.
YotoWebMgr now falls back to a local SHA-256 implementation for PKCE generation when needed.

The credential scaffold stores only connection metadata such as account label, scope, masked
account fields, authorization URL, OAuth state, expiry timestamps, status, and a
`token_storage_ref`. Actual refresh tokens, access tokens, client secrets, or encrypted token
material live in Kubernetes Secrets rather than the generic settings table.

Playlist versions are local payload snapshots only. A restore changes the local draft that future
jobs or live-create actions will use, but it does not alter any already-created remote Yoto content
until a newer explicit live-create/update call is made.

## Physical Card Inventory

Physical MYO cards remain a local inventory concept until the supported Yoto linking workflow is
confirmed. The cards page stores both a household-friendly alphanumeric card ID and an optional
programmable ID or playlist URI.

Generic NFC card experiments should record:

- NFC technology and chip type, for example `NFC Type 2` and `MIFARE Ultralight EV1`.
- Memory size, such as `48` bytes for the tested EV1 flow.
- Whether the card has been NDEF-prepared.
- The NDEF preparation command or settings used.
- The programming app used, such as NFC Tools.
- The source or transfer MYO card used to prepare/link the playlist.
- Whether a card is a reusable transfer card.
- Tested/programmed status and notes.

This metadata is deliberately separate from Yoto playlist creation. Writing or cloning NFC card
data must not become a hidden side effect of playlist generation.

## Current Known Gaps

- `POST /api/v1/library/{item_id}/link-card` still queues `upload_yoto_asset` for non-split items.
  That worker job is a placeholder and currently settles in `waiting`.
- The newer Yoto draft endpoints and live `POST /content` creation flow are the active path for
  playlist testing, including processed/local audio upload.
- Direct blank-card write from Yoto-created content is under active validation; staged source-card
  cloning remains available as a fallback workflow.
