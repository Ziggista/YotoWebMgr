#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
REGISTRY="${REGISTRY:-localhost:32000}"
TAG="${TAG:-dev}"
BUILDAH_ISOLATION="${BUILDAH_ISOLATION:-chroot}"
XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/tmp/yotowebmgr-buildah-run-${UID}}"
export BUILDAH_ISOLATION
export XDG_RUNTIME_DIR
mkdir -p "${XDG_RUNTIME_DIR}"
chmod 700 "${XDG_RUNTIME_DIR}"

build_image() {
  local name="$1"
  local context="$2"
  local dockerfile="$3"
  local image="${REGISTRY}/${name}:${TAG}"

  echo "Building ${image}"
  buildah bud --pull --tag "${image}" --file "${dockerfile}" "${context}"

  echo "Pushing ${image}"
  buildah push --tls-verify=false "${image}" "docker://${image}"
}

build_image "yotowebmgr-api" "${ROOT_DIR}/backend" "${ROOT_DIR}/backend/Dockerfile"
build_image "yotowebmgr-worker" "${ROOT_DIR}/worker" "${ROOT_DIR}/worker/Dockerfile"
build_image "yotowebmgr-frontend" "${ROOT_DIR}/frontend" "${ROOT_DIR}/frontend/Dockerfile"
