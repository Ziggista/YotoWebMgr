# YotoWebMgr Roadmap

This backlog captures the remaining product and operator work after the initial Yoto auth,
playlist, Android wrapper, NFC scan, and debug tooling milestones.

## Current Priorities

1. Finish blank-card writing from either:
   - a staged genuine/source MYO scan dump, or
   - a freshly created Yoto playlist URI without first scanning a source card.
2. Make the upload and link lifecycle explicit so the operator can see:
   - local processing state,
   - local Yoto draft state,
   - remote Yoto cloud state,
   - card handoff state,
   - verification state.
3. Add post-write verification by rescanning the card and comparing the observed payload against
   the payload that the app expected to write.

## Card Programming

- Keep improving the Android card console so blank-card programming is a guided flow rather than a
  loose collection of buttons.
- Support both copy modes:
  - exact staged source-card clone writes, and
  - generated Yoto playlist payload writes for clean blank cards.
- Show a dedicated staged write target in the UI so the operator can move from Create to Cards
  without copying payloads manually.
- Add clearer write success, write failure, and "scan again to verify" states.
- Continue validating the Reddit-derived blank-card preparation workflow against real cards.

## Yoto Upload and Cloud State

- Show the exact current stage for each item:
  - audio processing,
  - local Yoto draft,
  - upload in progress,
  - upload complete,
  - transcode in progress,
  - remote content ready,
  - remote link recorded,
  - failed or blocked.
- Persist enough remote identifiers and timestamps so state survives rebuilds and restarts.
- Improve polling or completion detection so the UI can move from upload complete to ready-to-link
  without ambiguous waiting.
- Keep logging around Yoto create/upload/transcode calls detailed enough to diagnose API-side
  problems quickly.

## Verification and Diagnostics

- Persist recent scan dumps and compare:
  - scanned source dump,
  - staged write target,
  - saved card record,
  - post-write verification scan.
- Highlight exact mismatch reasons when verification fails:
  - payload text mismatch,
  - payload hex mismatch,
  - missing playlist URI,
  - unsupported raw record structure.
- Add export-friendly scan dump and verification views for troubleshooting.

## Playlist and Library Management

- Improve the local-to-remote Yoto content view with richer metadata and history.
- Allow re-upload, replace, rename, archive, and remote status refresh actions.
- Keep default artwork generation available when the operator does not provide cover art.

## Android and Deploy

- Deep-link Android notifications back into the relevant workflow screen.
- Keep secrets persistent across normal redeploys and only remove them with explicit force flags.
- Continue hardening WSL, MicroK8s, Tailscale, and Android build tooling.
- Finish signed Android release build docs and scripts once release testing begins.

## Operator Docs

- Keep the Android, Yoto auth, deploy, and troubleshooting docs aligned with the actual live flow.
- Document the real supported blank-card workflow once write/verify behaviour is fully confirmed.
