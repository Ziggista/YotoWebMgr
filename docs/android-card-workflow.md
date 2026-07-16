# Android Card Workflow Brief

YotoWebMgr's first Android-facing webapp step is a mobile card console for reading, preparing,
linking, and verifying physical MYO or compatible NFC cards. The app remains a browser-delivered
web UI for now, with the option to wrap it in Capacitor later using the same pattern as Daymark.

## Step 1: Card Console Foundation

- Add a phone-first card workflow to the existing Cards screen.
- Let the household admin capture a card code, programmable NFC ID, chip details, NDEF state,
  source transfer card, Yoto playlist URI, and verification notes.
- Surface a clear checklist: scan, prepare NDEF, link in the Yoto app, download on the player,
  and test playback.
- Use browser NFC reads only when the Android browser exposes Web NFC.
- Treat NFC programming as an explicit manual step through a known app such as NFC Tools until the
  supported Yoto card-linking behaviour is confirmed.

## Step 2: Playlist-to-Card Handoff

- Keep Yoto playlist creation in the worker path.
- Mark a card `ready_to_link` only after the app has queued or prepared the local playlist.
- Preserve a manual confirmation step before the household user records that a physical card has
  been linked.
- Keep assignment history separate from card chip metadata.

## Step 3: Native Android Wrapper

- Add Capacitor only after the mobile web workflow is usable and stable.
- Reuse the Daymark shape: Vite `dist` as the web directory, an Android app ID, clear local
  development server settings, and build scripts.
- Evaluate native NFC capabilities separately from browser Web NFC before enabling any write path.

## Git Checkpoints

1. Commit this brief.
2. Commit the mobile card console and Web NFC read affordance.
3. Commit verification fixes and any follow-up polish.
