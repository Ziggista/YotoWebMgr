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
HTTP route handlers should enqueue Yoto work and return quickly; uploads, playlist updates, token
refresh, and transcode polling belong in worker jobs.

## Local Preview Endpoints

The API exposes local-only Yoto scaffolding endpoints:

- `GET /api/v1/yoto/config` reports non-secret Yoto configuration state.
- `GET /api/v1/yoto/credentials/status` reports the locally stored Yoto connection state without
  exposing tokens or secrets.
- `POST /api/v1/yoto/credentials/start` validates the configured client ID and redirect URI,
  stores an `authorization_started` credential record, and returns a prepared OAuth authorization
  URL. It does not exchange a code or call Yoto.
- `POST /api/v1/yoto/credentials/disconnect` clears local token references and marks the stored
  credential state as `revoked`. It does not make a live revoke call.
- `GET /api/v1/yoto/library/{item_id}/playlist-preview` maps a local library item and its tracks
  into a Yoto-shaped playlist payload without making a live Yoto API call.
- `GET /api/v1/yoto/library/{item_id}/playlists` lists stored local playlist drafts.
- `POST /api/v1/yoto/library/{item_id}/playlists` stores a draft payload and queues
  `create_yoto_playlist`.

The preview endpoint is deliberately not an upload action. The queue endpoint is a local scaffold:
it persists the payload, creates a trackable worker job, and currently advances the item to
`ready_to_link` for the manual Yoto-app linking workflow. Live OAuth/upload calls will be added
behind the same worker job once the exact supported flow is confirmed.

The credential scaffold stores only connection metadata such as account label, scope, masked
account fields, authorization URL, OAuth state, expiry timestamps, status, and an optional
`token_storage_ref`. Actual refresh tokens, access tokens, client secrets, or encrypted token
material must live in Kubernetes Secrets or a future encrypted token store.

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
