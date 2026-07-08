#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

echo "Running backend tests"
"${ROOT_DIR}/backend/.venv/bin/pytest" "${ROOT_DIR}/backend/tests"

echo
echo "Running worker tests"
"${ROOT_DIR}/worker/.venv/bin/pytest" "${ROOT_DIR}/worker/tests"

echo
echo "Building frontend"
npm --prefix "${ROOT_DIR}/frontend" run build

echo
echo "Checking shell script syntax"
bash -n "${ROOT_DIR}/k8s/scripts/build-images.sh"
bash -n "${ROOT_DIR}/k8s/scripts/deploy-dev.sh"
bash -n "${ROOT_DIR}/k8s/scripts/open-dev.sh"
bash -n "${ROOT_DIR}/scripts/dev/redeploy.sh"
bash -n "${ROOT_DIR}/scripts/dev/verify.sh"
bash -n "${ROOT_DIR}/scripts/dev/status.sh"
bash -n "${ROOT_DIR}/scripts/dev/seed-radio.sh"

echo
echo "Verification complete."
