#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
LOG_DIR="${LOG_DIR:-${ROOT_DIR}/scripts/dev/logs}"
RUN_TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
GIT_SHA="$(git -C "${ROOT_DIR}" rev-parse --short HEAD 2>/dev/null || echo "nogit")"
LOG_FILE="${LOG_FILE:-${LOG_DIR}/deploy-dev-${RUN_TIMESTAMP}-${GIT_SHA}.log}"

mkdir -p "${LOG_DIR}"
touch "${LOG_FILE}"

exec > >(tee -a "${LOG_FILE}") 2>&1

echo "YotoWebMgr destructive dev deploy"
echo "UTC timestamp: ${RUN_TIMESTAMP}"
echo "Git SHA: ${GIT_SHA}"
echo "Log file: ${LOG_FILE}"
echo

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
echo "Pods:"
microk8s kubectl -n yotowebmgr get pods -o wide
echo
echo "Recent backend API logs:"
microk8s kubectl -n yotowebmgr logs deployment/api --tail=200 || true
echo
echo "Recent frontend logs:"
microk8s kubectl -n yotowebmgr logs deployment/frontend --tail=200 || true
echo
echo "Dev deployment is ready."
echo "Ensuring the Kubernetes frontend is forwarded locally."
bash "${ROOT_DIR}/k8s/scripts/ensure-dev-port-forward.sh"
echo "Browse to:"
echo "  http://127.0.0.1:5175/"
echo
echo "Deploy log saved to:"
echo "  ${LOG_FILE}"
echo
echo "Useful follow-up log commands:"
echo "  microk8s kubectl -n yotowebmgr logs deployment/api --tail=200 -f"
echo "  microk8s kubectl -n yotowebmgr logs deployment/frontend --tail=200 -f"
echo "  microk8s kubectl -n yotowebmgr logs deployment/worker --tail=200 -f"
