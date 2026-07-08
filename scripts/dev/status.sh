#!/usr/bin/env bash
set -euo pipefail

NAMESPACE="${NAMESPACE:-yotowebmgr}"
TAIL_LINES="${TAIL_LINES:-80}"

echo "Pods"
microk8s kubectl -n "${NAMESPACE}" get pods

echo
echo "Services"
microk8s kubectl -n "${NAMESPACE}" get svc

echo
echo "Recent API logs"
microk8s kubectl -n "${NAMESPACE}" logs deploy/api --tail="${TAIL_LINES}" || true
