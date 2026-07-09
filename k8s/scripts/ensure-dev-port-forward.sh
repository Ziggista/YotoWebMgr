#!/usr/bin/env bash
set -euo pipefail

LOCAL_PORT="${LOCAL_PORT:-5175}"
REMOTE_PORT="${REMOTE_PORT:-80}"
NAMESPACE="${NAMESPACE:-yotowebmgr}"
SERVICE="${SERVICE:-frontend}"
PID_FILE="${PID_FILE:-/tmp/yotowebmgr-${SERVICE}-${LOCAL_PORT}.port-forward.pid}"
LOG_FILE="${LOG_FILE:-/tmp/yotowebmgr-${SERVICE}-${LOCAL_PORT}.port-forward.log}"
TMUX_SESSION="${TMUX_SESSION:-yotowebmgr-${SERVICE}-${LOCAL_PORT}}"
URL="http://127.0.0.1:${LOCAL_PORT}/"

if curl -fsS --max-time 2 "${URL}" >/dev/null 2>&1; then
  echo "Kubernetes ${SERVICE} is already forwarded at ${URL}"
  exit 0
fi

if [[ -f "${PID_FILE}" ]]; then
  existing_pid="$(<"${PID_FILE}")"
  if [[ "${existing_pid}" =~ ^[0-9]+$ ]] && kill -0 "${existing_pid}" >/dev/null 2>&1; then
    echo "Stopping stale ${SERVICE} port-forward process ${existing_pid}"
    kill "${existing_pid}" >/dev/null 2>&1 || true
    sleep 1
  fi
fi

if command -v tmux >/dev/null 2>&1 && tmux has-session -t "${TMUX_SESSION}" >/dev/null 2>&1; then
  echo "Stopping stale tmux port-forward session ${TMUX_SESSION}"
  tmux kill-session -t "${TMUX_SESSION}" >/dev/null 2>&1 || true
fi

echo "Starting Kubernetes ${SERVICE} port-forward at ${URL}"
if command -v tmux >/dev/null 2>&1; then
  tmux new-session -d -s "${TMUX_SESSION}" "microk8s kubectl -n '${NAMESPACE}' port-forward 'svc/${SERVICE}' '${LOCAL_PORT}:${REMOTE_PORT}' >'${LOG_FILE}' 2>&1"
  echo "tmux:${TMUX_SESSION}" >"${PID_FILE}"
else
  setsid microk8s kubectl -n "${NAMESPACE}" port-forward "svc/${SERVICE}" "${LOCAL_PORT}:${REMOTE_PORT}" >"${LOG_FILE}" 2>&1 &
  forward_pid="$!"
  echo "${forward_pid}" >"${PID_FILE}"
fi

for _ in {1..30}; do
  if curl -fsS --max-time 2 "${URL}" >/dev/null 2>&1; then
    sleep 1
    if command -v tmux >/dev/null 2>&1; then
      if ! tmux has-session -t "${TMUX_SESSION}" >/dev/null 2>&1; then
        echo "Port-forward tmux session exited after becoming reachable. Log:"
        tail -n 20 "${LOG_FILE}" || true
        exit 1
      fi
    elif ! kill -0 "${forward_pid}" >/dev/null 2>&1; then
      echo "Port-forward process exited after becoming reachable. Log:"
      tail -n 20 "${LOG_FILE}" || true
      exit 1
    fi
    echo "Kubernetes ${SERVICE} is forwarded at ${URL}"
    echo "Port-forward log: ${LOG_FILE}"
    exit 0
  fi
  if command -v tmux >/dev/null 2>&1; then
    if ! tmux has-session -t "${TMUX_SESSION}" >/dev/null 2>&1; then
      echo "Port-forward tmux session exited early. Log:"
      tail -n 20 "${LOG_FILE}" || true
      exit 1
    fi
  elif ! kill -0 "${forward_pid}" >/dev/null 2>&1; then
    echo "Port-forward process exited early. Log:"
    tail -n 20 "${LOG_FILE}" || true
    exit 1
  fi
  sleep 1
done

echo "Port-forward did not become reachable at ${URL}. Log:"
tail -n 20 "${LOG_FILE}" || true
exit 1
