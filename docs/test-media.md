# Test Media

Use clearly licensed media files for local and automated tests. Do not commit large media files to
the repository.

## Seed Script

The repo now includes a repeatable media seed helper:

```bash
scripts/media/seed-copyleft-test-media.sh
```

Run it from WSL to populate `local-media/imports/drop` with:

- a full Project Gutenberg audiobook suitable for a young child
- a full kid-friendly music album from Free Music Archive
- an updated local `MANIFEST.md` with provenance and licensing notes

The script is idempotent. Existing files are kept in place.

## Audiobook Candidate

LibriVox is the safest initial audiobook source. LibriVox records public-domain texts and states
that all LibriVox recordings are public domain in the United States.

Suggested use:

- For quick smoke tests, use one or two short MP3 chapters.
- For full pipeline and playlist tests, use the seeded full-book fixture under
  `copyleft/the-velveteen-rabbit/`.
- Keep it outside Git, then import it through `/var/lib/yotowebmgr/media/imports/drop` or browser
  upload.
- Record the title, reader, source URL, and public-domain notice in any fixture manifest.

Source:

- https://librivox.org/pages/public-domain/

## Local Audiobook Samples

Two local LibriVox MP3 files are staged outside Git for import testing:

```text
local-media/imports/drop/alice-01-chapter-1-librivox-public-domain.mp3
local-media/imports/drop/alice-02-chapter-2-librivox-public-domain.mp3
```

They are chapters from `Alice's Adventures in Wonderland` by Lewis Carroll, from the LibriVox
public-domain recording:

- https://librivox.org/alices-adventures-in-wonderland-by-lewis-carroll/
- https://www.archive.org/download/alice_in_wonderland_librivox/wonderland_ch_01_64kb.mp3
- https://www.archive.org/download/alice_in_wonderland_librivox/wonderland_ch_02_64kb.mp3

The default app import path is `/var/lib/yotowebmgr/media/imports/drop`. For local testing, point
`IMPORT_DROP_PATH` at `local-media/imports/drop` or copy these files into the MicroK8s import PVC.

For destructive MicroK8s dev redeploys, the most reliable repeatable test path is browser upload or
`POST /api/v1/imports/uploads` using these same local files. The upload flow stages the file into
the current pod-backed `/var/lib/yotowebmgr/media/imports/uploads` PVC automatically, so the worker
and API both see the same source path for inspect/process/Yoto tests.

The direct `/var/lib/yotowebmgr/media/imports/drop/...` path is only safe when you have reseeded
the current `imports-pvc` after the latest namespace delete.

## Full Audiobook Fixture

The seed script downloads the full `The Velveteen Rabbit` Project Gutenberg audio edition into:

```text
local-media/imports/drop/copyleft/the-velveteen-rabbit/
```

This gives you a complete child-friendly audiobook from a source that is reachable without relying
on the current Internet Archive mirrors.

Source:

- https://www.gutenberg.org/ebooks/26286
- https://www.gutenberg.org/files/26286/26286-index.html

## Copyleft Music Fixture

The seed script downloads the full `Mr. Sloth Is Sleepy` album by `Holizna4KidsMusic` into:

```text
local-media/imports/drop/copyleft/mr-sloth-is-sleepy/
```

Why this one:

- the album page is explicitly marked `CC BY`
- it is tagged `Kid-Friendly`
- it gives you six tracks, which is enough to exercise import, playlist ordering, and Yoto upload
  flows with real media

Source:

- https://freemusicarchive.org/index.php/music/holizna4kidsmusic/mr-sloth-is-sleepy
- https://freemusicarchive.org/music/holizna4kidsmusic/bio

## Frontend Player Dependency

The Library UI uses `react-h5-audio-player` for embedded playback. It wraps the browser audio
element with responsive controls and is MIT-licensed.

Verified with:

```bash
npm view react-h5-audio-player license version repository.url
```

Result at selection time:

```text
license = 'MIT'
version = '3.10.2'
repository.url = 'git+ssh://git@github.com/lhz516/react-h5-audio-player.git'
```
