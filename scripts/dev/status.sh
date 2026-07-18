#!/usr/bin/env bash
set -euo pipefail
export PATH="/snap/bin:${PATH}"
MICROK8S_BIN="${MICROK8S_BIN:-$(command -v microk8s || true)}"

NAMESPACE="${NAMESPACE:-yotowebmgr}"
TAIL_LINES="${TAIL_LINES:-80}"

if [[ -z "${MICROK8S_BIN}" && -x /snap/bin/microk8s ]]; then
  MICROK8S_BIN="/snap/bin/microk8s"
fi
if [[ -z "${MICROK8S_BIN}" ]]; then
  echo "microk8s command not found. Ensure MicroK8s is installed in WSL and available on PATH or at /snap/bin/microk8s." >&2
  exit 1
fi

echo "Pods"
"${MICROK8S_BIN}" kubectl -n "${NAMESPACE}" get pods

echo
echo "Services"
"${MICROK8S_BIN}" kubectl -n "${NAMESPACE}" get svc

echo
echo "Recent API logs"
"${MICROK8S_BIN}" kubectl -n "${NAMESPACE}" logs deploy/api --tail="${TAIL_LINES}" || true
