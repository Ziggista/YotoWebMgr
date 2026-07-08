#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://127.0.0.1:5175}"
TITLE="${TITLE:-Triple J test stream}"
STREAM_TITLE="${STREAM_TITLE:-ABC Triple J}"
STREAM_URL="${STREAM_URL:-http://www.abc.net.au/res/streaming/audio/mp3/triplej.pls}"
ICON_PATH="${ICON_PATH:-/icons/radio.png}"

echo "Creating radio library item at ${BASE_URL}"
library_response="$(
  curl -fsS \
    -X POST "${BASE_URL}/api/v1/library" \
    -H "Content-Type: application/json" \
    -d "{\"title\":\"${TITLE}\",\"content_type\":\"Radio Play\",\"cover_art_path\":\"${ICON_PATH}\",\"playlist_always_play_from_start\":true}"
)"
item_id="$(printf "%s" "${library_response}" | sed -n 's/.*"id":\([0-9][0-9]*\).*/\1/p' | head -n 1)"
if [[ -z "${item_id}" ]]; then
  echo "Could not read created library item id from API response." >&2
  echo "${library_response}" >&2
  exit 1
fi

echo "Adding stream track ${STREAM_TITLE}"
curl -fsS \
  -X POST "${BASE_URL}/api/v1/library/${item_id}/radio-streams" \
  -H "Content-Type: application/json" \
  -d "{\"title\":\"${STREAM_TITLE}\",\"stream_url\":\"${STREAM_URL}\",\"icon_path\":\"${ICON_PATH}\"}"

echo
echo "Seeded item ${item_id}. Library row should show a play button."
echo "Open ${BASE_URL}/ and view Library."
