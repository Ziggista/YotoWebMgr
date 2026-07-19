# Test Media

Use small, clearly licensed media files for local and automated tests. Do not commit large media
files to the repository.

## Audiobook Candidate

LibriVox is the safest initial audiobook source. LibriVox records public-domain texts and states
that all LibriVox recordings are public domain in the United States.

Suggested use:

- Download one or two short MP3 chapters from a LibriVox children's book, such as chapters from
  `Alice's Adventures in Wonderland`.
- Keep it outside Git, then import it through `/var/lib/yotowebmgr/media/imports/drop` or browser upload.
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

## Copyleft Music Candidate

Prefer Creative Commons Attribution-ShareAlike music for copyleft-style tests. CC BY-SA permits
sharing and adaptation, including commercial use, if attribution is preserved and adaptations use
the same license.

Concrete candidate:

- `Pulse of the Earth` by Hungry Lucy is listed as `CC BY-SA` in the major Creative
  Commons-licensed works index.

Other places to search:

- Wikimedia Commons audio files with `CC BY-SA` licensing.
- ccMixter tracks that explicitly show `CC BY-SA`; avoid `NonCommercial` tracks for reusable test
  fixtures.

Source:

- https://creativecommons.org/licenses/by-sa/4.0/
- https://en.wikipedia.org/wiki/List_of_major_Creative_Commons%E2%80%93licensed_works

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
