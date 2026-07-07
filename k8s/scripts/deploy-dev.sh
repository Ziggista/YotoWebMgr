#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

if ! microk8s status --wait-ready | grep -q "registry.*enabled"; then
  echo "Enabling MicroK8s registry addon"
  microk8s enable registry
fi

"${ROOT_DIR}/k8s/scripts/build-images.sh"

echo "Deleting existing yotowebmgr namespace for a fresh database and clean deploy"
microk8s kubectl delete namespace yotowebmgr --ignore-not-found=true
while microk8s kubectl get namespace yotowebmgr >/dev/null 2>&1; do
  echo "Waiting for yotowebmgr namespace deletion"
  sleep 2
done

microk8s kubectl apply -k "${ROOT_DIR}/k8s/overlays/dev"
microk8s kubectl -n yotowebmgr rollout status deployment/postgres --timeout=180s
microk8s kubectl -n yotowebmgr rollout status deployment/api --timeout=180s
microk8s kubectl -n yotowebmgr rollout status deployment/worker --timeout=180s
microk8s kubectl -n yotowebmgr rollout status deployment/frontend --timeout=180s

echo
echo "Dev deployment is ready."
echo "Run this in another terminal to open the app:"
echo "  microk8s kubectl -n yotowebmgr port-forward svc/frontend 5173:80"
echo "Then browse to:"
echo "  http://localhost:5173/"
