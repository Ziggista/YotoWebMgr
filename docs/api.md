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

Library mutations now write version events for the current item snapshot, including playlist settings, cover art, tracks, split points, podcast feeds, radio streams, and queued card links. These snapshots are the first restore-ready history layer; restore endpoints will build on them later.
