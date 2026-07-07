# Test Media

Use small, clearly licensed media files for local and automated tests. Do not commit large media
files to the repository.

## Audiobook Candidate

LibriVox is the safest initial audiobook source. LibriVox records public-domain texts and states
that all LibriVox recordings are public domain in the United States.

Suggested use:

- Download one short MP3 chapter from a LibriVox children's book, such as a chapter from a public
  domain children's story collection.
- Keep it outside Git, then import it through `/media/imports/drop` or browser upload.
- Record the title, reader, source URL, and public-domain notice in any fixture manifest.

Source:

- https://librivox.org/pages/public-domain/

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
