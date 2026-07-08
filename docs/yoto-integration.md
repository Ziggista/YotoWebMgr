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
