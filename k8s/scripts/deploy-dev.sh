#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
NAMESPACE="${NAMESPACE:-yotowebmgr}"
SECRET_NAME="${SECRET_NAME:-yotowebmgr-secrets}"
LOG_DIR="${LOG_DIR:-${ROOT_DIR}/scripts/dev/logs}"
RUN_TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
GIT_SHA="$(git -C "${ROOT_DIR}" rev-parse --short HEAD 2>/dev/null || echo "nogit")"
LOG_FILE="${LOG_FILE:-${LOG_DIR}/deploy-dev-${RUN_TIMESTAMP}-${GIT_SHA}.log}"
FORCE_DESTROY=false
SECRET_BACKUP_FILE=""

usage() {
  cat <<EOF
Usage: $(basename "$0") [--force]

Options:
  --force   Delete the namespace without preserving ${SECRET_NAME}.
EOF
}

while (($# > 0)); do
  case "$1" in
    --force)
      FORCE_DESTROY=true
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
  shift
done

mkdir -p "${LOG_DIR}"
touch "${LOG_FILE}"

exec > >(tee -a "${LOG_FILE}") 2>&1

cleanup() {
  if [[ -n "${SECRET_BACKUP_FILE}" && -f "${SECRET_BACKUP_FILE}" ]]; then
    rm -f "${SECRET_BACKUP_FILE}"
  fi
}
trap cleanup EXIT

echo "YotoWebMgr destructive dev deploy"
echo "UTC timestamp: ${RUN_TIMESTAMP}"
echo "Git SHA: ${GIT_SHA}"
echo "Log file: ${LOG_FILE}"
echo "Force destroy: ${FORCE_DESTROY}"
echo

if ! microk8s status --wait-ready | grep -q "registry.*enabled"; then
  echo "Enabling MicroK8s registry addon"
  microk8s enable registry
fi

if [[ "${FORCE_DESTROY}" != "true" ]]; then
  if microk8s kubectl -n "${NAMESPACE}" get secret "${SECRET_NAME}" >/dev/null 2>&1; then
    SECRET_BACKUP_FILE="$(mktemp "${TMPDIR:-/tmp}/yotowebmgr-secret-${RUN_TIMESTAMP}-XXXXXX.json")"
    echo "Backing up ${NAMESPACE}/${SECRET_NAME} to ${SECRET_BACKUP_FILE}"
    microk8s kubectl -n "${NAMESPACE}" get secret "${SECRET_NAME}" -o json \
      | python3 -c 'import json,sys; source=json.load(sys.stdin); sanitized={"apiVersion":"v1","kind":"Secret","metadata":{"name":source["metadata"]["name"],"namespace":source["metadata"]["namespace"]},"type":source.get("type","Opaque"),"data":source.get("data",{})}; json.dump(sanitized, sys.stdout)' \
      > "${SECRET_BACKUP_FILE}"
  else
    echo "No existing ${NAMESPACE}/${SECRET_NAME} secret found to preserve."
  fi
else
  echo "Force mode enabled: ${NAMESPACE}/${SECRET_NAME} will not be preserved."
fi

echo "Deleting existing ${NAMESPACE} namespace before building or deploying"
microk8s kubectl delete namespace "${NAMESPACE}" --ignore-not-found=true
while microk8s kubectl get namespace "${NAMESPACE}" >/dev/null 2>&1; do
  echo "Waiting for ${NAMESPACE} namespace deletion"
  sleep 2
done

"${ROOT_DIR}/k8s/scripts/build-images.sh"

microk8s kubectl apply -k "${ROOT_DIR}/k8s/overlays/dev"
if [[ -n "${SECRET_BACKUP_FILE}" && -f "${SECRET_BACKUP_FILE}" ]]; then
  echo "Restoring preserved ${NAMESPACE}/${SECRET_NAME}"
  microk8s kubectl apply -f "${SECRET_BACKUP_FILE}"
fi
microk8s kubectl -n "${NAMESPACE}" rollout status deployment/postgres --timeout=180s
microk8s kubectl -n "${NAMESPACE}" rollout status deployment/api --timeout=180s
microk8s kubectl -n "${NAMESPACE}" rollout status deployment/worker --timeout=180s
microk8s kubectl -n "${NAMESPACE}" rollout status deployment/frontend --timeout=180s

echo
echo "Pods:"
microk8s kubectl -n "${NAMESPACE}" get pods -o wide
echo
echo "Recent backend API logs:"
microk8s kubectl -n "${NAMESPACE}" logs deployment/api --tail=200 || true
echo
echo "Recent frontend logs:"
microk8s kubectl -n "${NAMESPACE}" logs deployment/frontend --tail=200 || true
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
echo "  microk8s kubectl -n ${NAMESPACE} logs deployment/api --tail=200 -f"
echo "  microk8s kubectl -n ${NAMESPACE} logs deployment/frontend --tail=200 -f"
echo "  microk8s kubectl -n ${NAMESPACE} logs deployment/worker --tail=200 -f"
