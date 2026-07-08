#!/usr/bin/env bash
set -euo pipefail

LOCAL_PORT="${LOCAL_PORT:-5175}"

echo "Opening Kubernetes frontend on http://127.0.0.1:${LOCAL_PORT}/"
echo "This forwards the MicroK8s frontend service, not any local Vite dev server."
microk8s kubectl -n yotowebmgr port-forward svc/frontend "${LOCAL_PORT}:80"
