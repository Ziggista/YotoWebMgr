#!/usr/bin/env bash
set -euo pipefail

LOCAL_PORT="${LOCAL_PORT:-5175}"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

echo "Ensuring Kubernetes frontend is available on http://127.0.0.1:${LOCAL_PORT}/"
echo "This forwards the MicroK8s frontend service, not any local Vite dev server."
bash "${ROOT_DIR}/k8s/scripts/ensure-dev-port-forward.sh"
