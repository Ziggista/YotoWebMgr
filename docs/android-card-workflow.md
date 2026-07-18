# Android Card Workflow Brief

YotoWebMgr's first Android-facing webapp step is a mobile card console for reading, preparing,
linking, and verifying physical MYO or compatible NFC cards. The web UI now also ships in a
Capacitor Android wrapper using the same overall shape as Daymark.

## Step 1: Card Console Foundation

- Add a phone-first card workflow to the existing Cards screen.
- Let the household admin capture a card code, programmable NFC ID, chip details, NDEF state,
  source transfer card, Yoto playlist URI, and verification notes.
- Surface a clear checklist: scan, prepare NDEF, link in the Yoto app, download on the player,
  and test playback.
- Prefer native Capacitor NFC inside the Android app for read/write flows.
- Keep browser Web NFC and NFC Tools as fallback capture paths when native/plugin behaviour differs
  by device.
- Persist recent scan dumps so captured source-card payloads can be inspected and applied directly
  to a blank target card.
- Allow direct blank-card programming tests from app-generated Yoto playlist/card data where the
  Yoto API response is sufficient, without forcing a source-card staging step first.

## Step 2: Playlist-to-Card Handoff

- Queue and version local Yoto playlist drafts in the backend, then expose a generated live
  `POST /content` payload for review from the library detail screen.
- Mark a card `ready_to_link` only after the app has queued or prepared the local playlist.
- Preserve a manual confirmation step before the household user records that a physical card has
  been linked, even when the app can generate the blank-card write payload directly.
- Keep assignment history separate from card chip metadata.

## Step 3: Native Android Wrapper

- Capacitor is now in use for the Android wrapper.
- Reuse the Daymark shape: Vite `dist` as the web directory, an Android app ID, clear local
  development server settings, and build scripts.
- Use a native MIT-licensed Capacitor NFC plugin for scan/write before relying on WebView Web NFC.
- Expose persisted scan dumps, staged source-card cloning, and direct write actions so NFC testing
  remains auditable.

## Current Caveats

- Native NFC read/write works through the Capacitor plugin, but Android device permission and
  launch-via-NFC behaviour can still vary by handset.
- Yoto OAuth from the remote Tailscale HTTP host uses a PKCE hashing fallback because some
  browsers do not expose `SubtleCrypto` on that non-HTTPS origin.
- The older backend `upload_yoto_asset` worker job is still a placeholder; the newer Yoto draft
  and live-create endpoints are the path under active development.

## Git Checkpoints

1. Commit this brief.
2. Commit the mobile card console and Web NFC read affordance.
3. Commit verification fixes and any follow-up polish.
