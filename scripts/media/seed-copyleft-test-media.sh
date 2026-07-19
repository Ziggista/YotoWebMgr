#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DROP_DIR="${ROOT_DIR}/local-media/imports/drop"
COPYLEFT_DIR="${DROP_DIR}/copyleft"
AUDIOBOOK_DIR="${COPYLEFT_DIR}/the-velveteen-rabbit"
MUSIC_DIR="${COPYLEFT_DIR}/mr-sloth-is-sleepy"
MANIFEST_PATH="${DROP_DIR}/MANIFEST.md"

mkdir -p "${AUDIOBOOK_DIR}" "${MUSIC_DIR}"

download_if_missing() {
  local url="$1"
  local destination="$2"

  if [[ -f "${destination}" ]]; then
    echo "Keeping existing $(basename "${destination}")"
    return 0
  fi

  echo "Downloading $(basename "${destination}")"
  curl --fail --location --silent --show-error --output "${destination}" "${url}"
}

audiobook_tracks=(
  "01-the-velveteen-rabbit.mp3|The Velveteen Rabbit|https://www.gutenberg.org/files/26286/mp3/26286-01.mp3"
)

music_tracks=(
  "01-big-rock-candy-mountain.mp3|Big Rock Candy Mountain|https://files.freemusicarchive.org/storage-freemusicarchive-org/tracks/jFqps4RsfR3h0dYvTepJRmbHrsK9EWFSK8nU9okf.mp3"
  "02-are-you-sleeping-brother-john.mp3|Are You Sleeping Brother John|https://files.freemusicarchive.org/storage-freemusicarchive-org/tracks/Nr0uHzMFUd8YmFCeXjZGGYocow7Lde2m9V6WK3uJ.mp3"
  "03-you-are-my-sunshine.mp3|You Are My Sunshine|https://files.freemusicarchive.org/storage-freemusicarchive-org/tracks/YLYUsSjQF7lgmUoPYN4mVQ8ojUMqxCwNV1cTeqwU.mp3"
  "04-twinkle-twinkle-little-star.mp3|Twinkle Twinkle Little Star|https://files.freemusicarchive.org/storage-freemusicarchive-org/tracks/iPU3U4LmdpwBv7dKgodvxzsuGkADtgj8AFUQl0Sh.mp3"
  "05-oh-my-darling.mp3|Oh My Darling|https://files.freemusicarchive.org/storage-freemusicarchive-org/tracks/uApdi0ubyzheyWBEwkYocwCKYerzMRuuWgmPdA2d.mp3"
  "06-ill-fly-away.mp3|I'll Fly Away|https://files.freemusicarchive.org/storage-freemusicarchive-org/tracks/e9VWddTYe9sRPcaLBv58ZMAphJoOosK7nm81Pcut.mp3"
)

for entry in "${audiobook_tracks[@]}"; do
  IFS="|" read -r file_name title url <<<"${entry}"
  filename="${AUDIOBOOK_DIR}/${file_name}"
  download_if_missing "${url}" "${filename}"
done

for entry in "${music_tracks[@]}"; do
  IFS="|" read -r file_name title url <<<"${entry}"
  filename="${MUSIC_DIR}/${file_name}"
  download_if_missing "${url}" "${filename}"
done

cat >"${MANIFEST_PATH}" <<'EOF'
# Local Test Audio

These files are local-only test imports and are intentionally ignored by Git.

## Quick Samples

Source: LibriVox recording of `Alice's Adventures in Wonderland` by Lewis Carroll.
License/status: LibriVox recordings are public domain in the United States.
Catalog: https://librivox.org/alices-adventures-in-wonderland-by-lewis-carroll/

Files:

- `alice-01-chapter-1-librivox-public-domain.mp3`
  - Chapter 1
  - Reader: Kristen McQuillin
  - Source URL: https://www.archive.org/download/alice_in_wonderland_librivox/wonderland_ch_01_64kb.mp3
- `alice-02-chapter-2-librivox-public-domain.mp3`
  - Chapter 2
  - Reader: Brad Bush
  - Source URL: https://www.archive.org/download/alice_in_wonderland_librivox/wonderland_ch_02_64kb.mp3

## Full Audiobook

Directory: `copyleft/the-velveteen-rabbit/`

- Source page: https://www.gutenberg.org/ebooks/26286
- Source audio index: https://www.gutenberg.org/files/26286/26286-index.html
- Reader: Project Gutenberg audio edition
- License/status: Project Gutenberg lists this audio edition under its free ebook terms and the
  underlying work is public domain in the USA

## Kids Music Album

Directory: `copyleft/mr-sloth-is-sleepy/`

- Source page: https://freemusicarchive.org/index.php/music/holizna4kidsmusic/mr-sloth-is-sleepy
- Artist page: https://freemusicarchive.org/music/holizna4kidsmusic/bio
- Artist: Holizna4KidsMusic
- Released: 2022-03-06
- License/status: album page lists `CC BY`; check individual tracks for the same attribution terms
EOF

echo
echo "Seeded copyleft test media into:"
echo "  ${AUDIOBOOK_DIR}"
echo "  ${MUSIC_DIR}"
echo
echo "Manifest updated at:"
echo "  ${MANIFEST_PATH}"
