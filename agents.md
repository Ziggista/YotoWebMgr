# AGENTS.md — YotoWebMgr

## Project purpose

YotoWebMgr is a self-hosted household media-library and Yoto MYO-card management application.

It is designed primarily for managing audiobooks, music, story collections, podcasts, and other child-friendly audio for a Yoto player. The main user is Krystin, with Dale as a second household user. Most content will be for Elyza.

The application must:

* Import and preserve original media files.
* Process separate Yoto-ready copies.
* Detect and preserve audiobook chapters.
* Split long content across multiple MYO cards at logical chapter boundaries.
* Create and update Yoto playlists through Yoto-supported API workflows.
* Maintain a local media library with metadata, tags, history, physical-card assignments, and rollback capability.
* Provide a polished web UI similar in spirit to the Daymark project.
* Run in MicroK8s inside WSL from the beginning.

The project name is:

```text
YotoWebMgr
```

---

## Core principles

1. **Python owns the backend and all processing.**

   Python is mandatory for:

   * API/backend logic.
   * Media inspection.
   * FFmpeg orchestration.
   * Chapter extraction.
   * Audio conversion.
   * Loudness normalisation.
   * Artwork processing.
   * Yoto authentication and API integration.
   * Background jobs.
   * Versioning and rollback logic.

2. **The frontend may use React/Vite/TypeScript.**

   Use a modern mobile-first frontend similar in philosophy to Daymark:

   * Good on phones/tablets.
   * Large touch targets.
   * Clear job status.
   * Simple household-oriented navigation.
   * Desktop-friendly library and chapter editor views.

3. **Original media is immutable.**

   Never alter an original imported media file.

   Original media must be copied or referenced in a dedicated original-media location. All transcoded, normalised, split, or edited media must exist separately as generated Yoto-ready copies.

4. **History is never destructive.**

   Editing a playlist/card assignment must create a new version.

   Restoring a prior version must not erase newer versions. A restore creates a new version whose content matches the selected historical version.

5. **Processing must be resumable and idempotent.**

   Jobs may fail due to network issues, upload failures, transcoding issues, pod restarts, or bad media. Re-running a job must safely reuse completed work where possible rather than duplicating uploads or corrupting records.

6. **Build around household usability, not enterprise complexity.**

   This is self-hosted and should remain understandable and maintainable by one technically capable household admin.

---

## Technology direction

### Frontend

Preferred stack:

```text
React
TypeScript
Vite
TanStack Query or equivalent API state management
React Router
Tailwind CSS or existing Daymark-style styling conventions
```

The frontend should be mobile-first but include a capable desktop library-management experience.

### Backend/API

Preferred stack:

```text
Python 3.12+
FastAPI
Pydantic v2
SQLAlchemy 2.x
Alembic migrations
httpx for outbound HTTP APIs
```

Use typed request/response schemas. Do not expose raw database models directly through API endpoints.

### Background jobs

Preferred approach:

```text
Python worker deployment
PostgreSQL-backed job table initially
Database polling / lease-based job locking
```

Do not introduce Redis, Celery, RabbitMQ, Kafka, or another queue unless there is a demonstrated need.

The worker must support:

* Job leasing.
* Retry counts.
* Exponential backoff.
* Clear failure details.
* Manual retry.
* Cancellation where safe.
* Progress updates.
* Idempotent job execution.

### Database

Use PostgreSQL from day one because the application runs as multiple MicroK8s workloads.

Use PostgreSQL for:

* Users.
* Tags.
* Media library records.
* Media metadata.
* Chapters/tracks.
* Playlist/card records.
* Version history.
* Job queue/history.
* Yoto account/token metadata.
* Audit events.
* Processing asset metadata.

Do not use SQLite for the main deployment.

### Media processing

Use Python to orchestrate:

```text
ffprobe
ffmpeg
```

Do not reimplement media decoding or transcoding in Python libraries unless there is a clear reason.

The system must inspect common locally available media formats, including where technically supported:

```text
M4B
M4A
MP3
AAC
FLAC
OGG
WAV
OPUS
MP4 audio tracks where appropriate
```

The app must not fetch media from piracy/download sites or embed download functionality. It should process media that the user has already obtained and is authorised to use.

### Deployment

Run in MicroK8s in WSL from the start.

Expected Kubernetes components:

```text
Namespace: yotowebmgr

Deployments:
- frontend
- api
- worker
- postgres

Persistent storage:
- originals PVC
- processed PVC
- artwork PVC
- exports PVC
- temp/scratch PVC or emptyDir where appropriate
- postgres PVC

Secrets:
- database credentials
- Yoto OAuth credentials
- Yoto refresh token or encrypted token material
- optional OpenAI API key for artwork generation
```

Use Kubernetes manifests or Kustomize first. Helm is optional later but is not required for the initial build.

---

## Repository structure

Use this layout unless there is a strong reason to change it:

```text
YotoWebMgr/
├── AGENTS.md
├── README.md
├── docs/
│   ├── architecture.md
│   ├── api.md
│   ├── deployment.md
│   ├── media-processing.md
│   ├── yoto-integration.md
│   └── decisions/
├── frontend/
│   ├── src/
│   ├── public/
│   ├── package.json
│   └── vite.config.ts
├── backend/
│   ├── app/
│   │   ├── api/
│   │   ├── core/
│   │   ├── db/
│   │   ├── models/
│   │   ├── schemas/
│   │   ├── services/
│   │   ├── integrations/
│   │   └── main.py
│   ├── alembic/
│   ├── tests/
│   ├── pyproject.toml
│   └── Dockerfile
├── worker/
│   ├── app/
│   │   ├── jobs/
│   │   ├── media/
│   │   ├── yoto/
│   │   ├── artwork/
│   │   └── worker.py
│   ├── tests/
│   ├── pyproject.toml
│   └── Dockerfile
├── shared/
│   ├── openapi/
│   └── generated/
├── k8s/
│   ├── base/
│   ├── overlays/
│   │   ├── dev/
│   │   └── prod/
│   └── scripts/
├── scripts/
│   ├── dev/
│   ├── media/
│   └── deployment/
└── .github/
    └── workflows/
```

Avoid placing production logic in one giant `main.py`, one giant API router, or one giant worker script.

---

## Required storage layout

Use distinct media locations.

```text
/media/originals
/media/processed
/media/artwork
/media/exports
/media/temp
```

### `/media/originals`

Contains preserved source media.

Rules:

* Treat as append-only.
* Never transcode over originals.
* Never delete automatically.
* Store checksum and original filename.
* Record source type: browser upload, filesystem import, Plex import, or other configured source.
* Store source path where applicable.

### `/media/processed`

Contains generated audio suitable for Yoto upload.

Rules:

* Generated files must be tied to a media/version/track record.
* Do not overwrite processed files in place when editing a card.
* Use content checksums to reuse already-generated assets.
* Keep source-to-output traceability.

### `/media/artwork`

Contains:

* Extracted embedded artwork.
* User-uploaded artwork.
* Generated artwork.
* Pixelised Yoto-ready artwork.
* Original artwork source where applicable.

### `/media/exports`

Contains exportable and backup-friendly material:

* Playlist/card manifests.
* Version history snapshots.
* Metadata exports.
* Artwork references.
* Card assignment history.
* Optional JSON backup format.

### `/media/temp`

Used for transient processing.

Rules:

* Safe to clear after completed jobs.
* Must not be the sole location of required media.
* Never rely on temp files for restore functionality.

---

## Main user roles

Initial users:

```text
Krystin
Dale
```

Potential future user:

```text
Elyza
```

Initial access model:

* Separate local accounts for Krystin and Dale.
* Both are household administrators.
* Audit records should capture who created, edited, uploaded, linked, restored, retried, or deleted an item.
* Tags are organisational, not access-control permissions in v1.

Do not build complex RBAC in the first release.

---

## Tagging requirements

Tags are a core library feature.

Examples:

```text
Krystin
Dale
Elyza
Family
Audiobook
Music
Story Collection
Bedtime
Car Trip
Educational
Favourite
Calm
Christmas
School Holidays
```

Requirements:

* Tags are reusable.
* Tags can apply to library items, playlists, card assignments, and optionally versions.
* Tag filtering must be available in the library UI.
* Tags should support quick-add and existing-tag selection.
* People tags such as `Dale`, `Krystin`, and `Elyza` should work as library filters and default views.
* Do not hard-code individual names into the application logic.

---

## Supported content concepts

The application must distinguish these content types:

```text
Audiobook
Music Album
Story Collection
Podcast
Radio Play
Sleep Sounds
Custom Playlist
Other Audio
```

### Audiobooks

Expected behaviour:

* Detect embedded chapters where available, especially M4B/M4A.
* Use embedded chapter names where useful.
* Allow manual chapter name edits.
* Use one source chapter as one Yoto chapter by default.
* Split long books into logical parts at chapter boundaries.
* Prefer clean part boundaries over maximising every final minute of card capacity.

### Music albums

Expected behaviour:

* Each track normally becomes a selectable Yoto chapter.
* Preserve track order.
* Use stereo processing by default.
* Allow creating cards from an entire album or selected tracks.

### Story collections and podcasts

Expected behaviour:

* Treat each file as a chapter/track when embedded chapters do not exist.
* Allow manual ordering.
* Support custom title cleanup.

### Custom playlists

The architecture must support this even if the UI is deferred.

A custom playlist may contain tracks from different library items, for example:

```text
Elyza Bedtime Mix
- Story chapter
- Calm song
- Another story
- Sleep audio
```

---

## Yoto card limits and splitting rules

Default target limits:

```text
Target duration per card: 4.9 hours
Target size per card: 480 MB
```

These are safety targets, not assumed hard Yoto limits.

Requirements:

* Validate against configured Yoto limits before upload.
* Warn clearly if a card would exceed duration, track count, or size limits.
* Prefer splitting at embedded chapter boundaries.
* For multi-card books, create clean logical parts:

```text
Book Title — Part 1 of 3
Book Title — Part 2 of 3
Book Title — Part 3 of 3
```

* Allow the user to manually move chapters between parts before processing/upload.
* Provide an estimated duration and estimated output size per part.
* Make target duration and target size configurable per import.

Do not split an audiobook in the middle of a chapter unless the user explicitly chooses to do so.

---

## Audio processing rules

### Default audio profiles

Use content-aware defaults.

```text
Audiobook / spoken word:
- Mono by default
- 96 kbps preferred default
- Loudness normalisation enabled by default

Music / radio plays:
- Stereo by default
- 128 kbps preferred default
- Loudness normalisation enabled by default
```

The user has requested 128 kbps stereo for quality-sensitive content. Spoken-word content may use mono where appropriate to save card space.

All defaults must be adjustable per import.

### Normalisation

Provide a UI checkbox:

```text
Normalise loudness: enabled by default
```

Requirements:

* Use sensible loudness normalisation rather than aggressive peak-only normalisation.
* Preserve musical dynamics reasonably.
* Allow disabling normalisation for any import.
* Record the processing settings used in the asset/version history.

### Re-encoding

Requirements:

* Re-encode all Yoto output into a predictable standard format.
* Keep original media untouched.
* Record codec, bitrate, channels, duration, size, and checksum.
* Use FFmpeg profiles defined centrally in code.
* Do not hide FFmpeg command failures; capture stderr in job logs.

### Silence trimming

Do not enable automatic silence trimming in the first release.

The source should remain intact except for requested encoding, normalisation, splitting, and metadata changes.

---

## Media import sources

The app should eventually support:

1. Browser upload.
2. Import from configured filesystem paths.
3. Import from Plex libraries.
4. Optional metadata/artwork lookup through Plex.

Initial import UX should support both:

```text
Upload a file through the browser
Import from a configured media path
```

Plex should not be required for the initial release. Design the integration as optional.

Do not rely on Plex as the system of record. YotoWebMgr’s own database and media library are the system of record for Yoto processing history.

---

## Plex integration expectations

Plex integration should be isolated behind an integration/service layer.

Potential future functions:

* Browse selected Plex libraries.
* Search Plex media.
* Import selected media into YotoWebMgr.
* Pull title, author/artist, album/series, track numbers, artwork, and descriptions.
* Record Plex identifiers and source paths.
* Detect likely existing library matches.

Do not tightly couple the application to Plex database internals.

---

## Yoto integration requirements

Yoto integration must be implemented through a dedicated Python integration layer.

Suggested structure:

```text
backend/app/integrations/yoto/
worker/app/yoto/
```

Responsibilities:

* OAuth/client authentication.
* Token refresh.
* Secure token storage.
* Upload preparation.
* Upload URL handling.
* Upload progress.
* Transcode status polling.
* Playlist creation/update.
* Chapter/track construction.
* Artwork association.
* Error handling and retry classification.
* Local-to-remote ID mapping.

Do not scatter Yoto API requests across route handlers or job functions.

### Physical MYO cards

At first, physical cards are a locally managed inventory concept.

Represent cards as named slots such as:

```text
Card 01
Card 02
Card 03
...
Card 10
```

Allow optional metadata later:

```text
Colour
Sticker/label
Written identifier
Notes
Yoto identifier if available
Current assignment
Assignment history
```

The system should support a workflow where the app creates a playlist and marks it:

```text
Ready to link
```

The household user then links it to a physical MYO card through the supported Yoto workflow and records the assignment in YotoWebMgr.

Do not assume that physical-card linking can be fully automated until the actual Yoto card/API behaviour is confirmed.

---

## Versioning and restore requirements

Versioning is mandatory.

Version these entities:

```text
Library item metadata
Processed media set
Playlist definition
Chapter order
Part/card split
Artwork selection
Yoto remote playlist mapping
Physical card assignment
```

Every meaningful change creates a new version or version event.

### Restore behaviour

When a user restores version `n-1`:

1. Do not delete the current version.
2. Create a new version based on the selected historical version.
3. Reuse existing processed media where checksums/settings match.
4. Restore the selected chapter order, artwork, settings, and card/playlist mapping.
5. Push restored Yoto playlist state to Yoto where safe and supported.
6. Ask for confirmation before altering remote Yoto content.
7. Record:

```text
Version 13 restored from Version 11 by Krystin
```

Use immutable version snapshots or event-sourced version records. Do not rely only on a mutable “current state” record.

---

## Job types

The initial worker should support job types such as:

```text
inspect_media
extract_metadata
extract_chapters
extract_artwork
generate_artwork
pixelise_artwork
build_card_plan
transcode_audio
normalise_audio
upload_yoto_asset
wait_for_yoto_transcode
create_yoto_playlist
update_yoto_playlist
restore_playlist_version
import_from_filesystem
import_from_plex
export_library_manifest
cleanup_temp_files
```

Each job must include:

```text
id
type
status
created_at
started_at
finished_at
created_by_user_id
retry_count
max_retries
progress_percent
progress_message
error_summary
error_detail
related_library_item_id
related_playlist_id
related_version_id
```

Job status should include:

```text
queued
running
waiting
succeeded
failed
cancelled
retrying
```

The frontend must show usable status such as:

```text
Inspecting source media
Extracting chapters
Building Part 2 of 3
Encoding chapter 8 of 24
Uploading track 14 of 31
Waiting for Yoto processing
Ready to link to a card
Failed — Retry available
```

---

## Artwork requirements

YotoWebMgr needs simple child-friendly pixel artwork suitable for a Yoto-style small display.

Artwork priority:

1. Use embedded cover art where suitable.
2. Allow a user to upload artwork.
3. Pixelise/crop/dither suitable artwork for the Yoto display.
4. Offer generated artwork when no suitable image exists.

Generated artwork may use an external image-generation API in future, including OpenAI-compatible image generation.

Do not require image generation for the core import flow.

Artwork requirements:

* Keep a source image and generated output separately.
* Avoid relying on tiny text rendered into pixel artwork.
* Prefer simple recognisable visual themes:

```text
Dragon
Dinosaur
Moon
Forest
Space ship
Princess castle
Robot
Pirate ship
Animals
Books
Music notes
```

* Store the prompt/parameters for generated images.
* Allow users to approve, regenerate, replace, or upload artwork manually.
* Ensure the pixel conversion process is deterministic when given the same source/settings.

---

## API design rules

Use REST APIs initially.

Suggested API areas:

```text
/auth
/users
/tags
/library
/media
/imports
/playlists
/cards
/versions
/jobs
/artwork
/yoto
/settings
/health
```

Requirements:

* Version API endpoints if needed, for example `/api/v1/...`.
* Use Pydantic schemas.
* Return stable IDs.
* Use pagination for library/history views.
* Support filtering by tags, type, owner, status, and text search.
* Use clear error responses.
* Do not expose secrets, source filesystem paths unnecessarily, or raw stack traces to frontend users.
* Provide OpenAPI documentation through FastAPI.

---

## Frontend requirements

Primary navigation should likely include:

```text
Library
Import
Cards
Jobs
Tags
Settings
```

### Library

Must support:

* Search.
* Filter by type.
* Filter by tags.
* Filter by user/person tags.
* Sort by recently added, title, author, last used, or status.
* Show processing/Yoto/card status.
* Open a detailed media page.

### Import

Must support:

* Browser upload.
* Configured filesystem import.
* Future Plex import.
* Metadata review.
* Content-type selection.
* Chapter inspection.
* Card split review.
* Artwork selection.
* Audio processing options.

### Card planning/editor

Must support:

* Display chapters/tracks in order.
* Show duration and estimated size.
* Show proposed part/card boundaries.
* Allow moving chapters between parts.
* Allow editing part titles.
* Warn about limits.
* Provide dry-run/preview before upload.

### Cards

Must support:

* Named card slots.
* Current assignment.
* Assignment history.
* “Ready to link” state.
* Optional colour/label/notes.
* Open linked playlist details.
* Restore prior assignment/version.

### Jobs

Must support:

* Live or regularly refreshed progress.
* Failed-job details.
* Retry action.
* Job history.
* Link back to related media/playlist/card.

### Mobile design

Prioritise:

* Large touch targets.
* Clear calls to action.
* Avoid dense unreadable tables on a phone.
* Use responsive detail pages.
* Keep advanced controls available but not overwhelming.

---

## Security requirements

This is a private household application, but basic security still matters.

Requirements:

* Require login for normal application access.
* Use secure password hashing.
* Keep secrets in Kubernetes Secrets, not source control.
* Never commit tokens, API keys, database passwords, or personal media files.
* Validate all uploads.
* Limit allowed import directories.
* Protect against path traversal.
* Sanitize filenames.
* Avoid shell injection when invoking FFmpeg.
* Invoke FFmpeg using argument arrays, not shell-concatenated strings.
* Restrict media file access to application volumes.
* Log errors without logging sensitive OAuth tokens or credentials.
* Use HTTPS/Tailscale/reverse-proxy protections when exposed beyond localhost.

---

## Testing expectations

Write tests alongside features.

### Backend tests

Cover:

* API input validation.
* Authentication.
* Tagging.
* Version creation.
* Restore flow.
* Card split logic.
* Size/duration limit calculations.
* Job leasing/retry logic.
* Yoto integration request mapping using mocks.
* Filesystem import validation.

### Media tests

Use small fixture media files where legally appropriate.

Test:

* M4B chapter discovery.
* MP3 folder ordering.
* Missing/invalid metadata.
* Audio profile selection.
* Card splitting at chapter boundaries.
* Long chapter edge cases.
* FFmpeg failure handling.
* Output metadata recording.

### Frontend tests

Cover:

* Library filtering.
* Import review flow.
* Chapter movement between parts.
* Version restore confirmation.
* Job status rendering.
* Mobile-critical interactions.

### End-to-end tests

Eventually cover:

```text
Import media
→ inspect chapters
→ plan cards
→ process audio
→ create local playlist version
→ mock Yoto upload
→ mark ready to link
→ edit playlist
→ restore previous version
```

Do not require live Yoto credentials for automated CI.

---

## Development workflow

When implementing a feature:

1. Read relevant existing code and docs first.
2. Identify affected database models and migrations.
3. Define or update API schemas.
4. Implement backend/service logic.
5. Implement worker/job logic where processing is involved.
6. Add tests.
7. Implement/update frontend workflow.
8. Update docs when architecture, deployment, or user workflow changes.
9. Verify local development and Kubernetes manifests remain aligned.

Avoid large unrelated refactors while implementing a specific feature.

Prefer small coherent commits.

---

## Important implementation constraints

* Do not overwrite original media.
* Do not assume every file has valid metadata.
* Do not assume every audiobook has embedded chapters.
* Do not split mid-chapter by default.
* Do not assume a Yoto upload completes immediately.
* Do not assume a physical MYO card has an API-readable identity.
* Do not silently discard failed processing output without recording the failure.
* Do not create duplicate Yoto uploads where an existing processed asset can be safely reused.
* Do not make Yoto API calls directly from HTTP request handlers if the operation may take more than a few seconds.
* Do not make browser requests wait for long transcoding/upload jobs.
* Do not tightly couple Plex to core library logic.
* Do not treat tag names as permissions.
* Do not delete version history during restore.

---

## Initial milestone order

### Milestone 1: Project foundation

* Repository scaffold.
* MicroK8s namespace/manifests.
* PostgreSQL deployment and migrations.
* FastAPI health endpoint.
* React/Vite frontend shell.
* Local authentication for Krystin and Dale.
* Base navigation.
* Persistent media volumes.
* Basic job framework.

### Milestone 2: Library and tagging

* Library item model.
* Tags.
* User attribution.
* Browser upload.
* Filesystem import.
* Metadata inspection.
* Library search/filter UI.
* Basic detail page.

### Milestone 3: Media inspection and planning

* FFprobe integration.
* M4B embedded chapter extraction.
* File/folder track discovery.
* Artwork extraction.
* Content type selection.
* Chapter editor.
* Card split planner.
* Duration/size estimates.
* Part naming.

### Milestone 4: Processing pipeline

* FFmpeg audio profiles.
* Loudness normalisation toggle.
* Mono/stereo selection.
* Processed asset storage.
* Job progress.
* Retry handling.
* Processed-output inspection.

### Milestone 5: Yoto integration

* Yoto OAuth configuration.
* Secure token handling.
* Asset upload flow.
* Playlist construction.
* Playlist update flow.
* Ready-to-link workflow.
* Local card-slot inventory.

### Milestone 6: Versioning and restore

* Playlist versions.
* Card assignment history.
* Restore confirmation flow.
* Restore-to-new-version behaviour.
* Push restored playlist state to Yoto.
* Export manifests.

### Milestone 7: Artwork and Plex

* Pixel artwork conversion.
* Artwork upload/manual selection.
* Optional image-generation API integration.
* Plex filesystem import.
* Optional Plex API metadata/artwork integration.

---

## Decisions already made

```text
Application name: YotoWebMgr
Primary purpose: Household Yoto MYO media manager
Primary audience: Elyza, with Krystin and Dale managing content
Deployment: MicroK8s in WSL from day one
Backend: Python/FastAPI
Worker: Python
Frontend: React/Vite/TypeScript is acceptable
Database: PostgreSQL
Original media: Preserved separately and never modified
Processed media: Stored separately as Yoto-ready files
Tags: Required, including Dale, Krystin, Elyza
Main UI: Web-app driven
CLI: Useful as supporting/admin tooling, not primary workflow
Chapters: Preserve embedded chapters where available
Splitting: Prefer logical chapter-boundary splits
Default card planning target: 4.9 hours / 480 MB
Audio: Re-encode to standard output
Music quality: 128 kbps stereo
Audiobook mode: Mono acceptable and preferred where appropriate
Normalisation: Enabled by default with user option to disable
History: Required
Undo/restore: Required, including restore to prior `n-1` state
Artwork: Basic pixel/8-bit style, embedded/manual/generated options
Plex: Optional integration; not required as core dependency
Physical MYO card identity: Unknown until cards arrive; use named card slots initially
```

---

## Open decisions to revisit

These should not block repository initialisation.

```text
Exact Yoto API capabilities for card linking.
Exact physical MYO card identification workflow.
Whether custom mixed playlists are included in the first user-facing release.
Exact Plex server path/API details.
Whether access is LAN-only, Tailscale-only, or both.
Exact frontend visual system copied/adapted from Daymark.
Exact audio output container/codec after validating Yoto API/media requirements.
Exact artwork pixel dimensions and Yoto display constraints.
```

---

## Definition of done for a feature

A feature is not complete until:

* It has a clear user-visible purpose.
* Database changes have a migration.
* API changes have schemas and tests.
* Worker behaviour is retry-safe where relevant.
* Errors are visible and actionable.
* The UI works on both phone and desktop.
* Relevant history/audit information is retained.
* No original media is modified.
* Docs are updated where the workflow or deployment changed.
