#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

if ! microk8s status --wait-ready | grep -q "registry.*enabled"; then
  echo "Enabling MicroK8s registry addon"
  microk8s enable registry
fi

echo "Deleting existing yotowebmgr namespace before building or deploying"
microk8s kubectl delete namespace yotowebmgr --ignore-not-found=true
while microk8s kubectl get namespace yotowebmgr >/dev/null 2>&1; do
  echo "Waiting for yotowebmgr namespace deletion"
  sleep 2
done

"${ROOT_DIR}/k8s/scripts/build-images.sh"

microk8s kubectl apply -k "${ROOT_DIR}/k8s/overlays/dev"
microk8s kubectl -n yotowebmgr rollout status deployment/postgres --timeout=180s
microk8s kubectl -n yotowebmgr rollout status deployment/api --timeout=180s
microk8s kubectl -n yotowebmgr rollout status deployment/worker --timeout=180s
microk8s kubectl -n yotowebmgr rollout status deployment/frontend --timeout=180s

echo
echo "Dev deployment is ready."
echo "Ensuring the Kubernetes frontend is forwarded locally."
bash "${ROOT_DIR}/k8s/scripts/ensure-dev-port-forward.sh"
echo "Browse to:"
echo "  http://127.0.0.1:5175/"
