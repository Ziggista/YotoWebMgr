#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
NAMESPACE="${NAMESPACE:-yotowebmgr}"
SECRET_NAME="${SECRET_NAME:-yotowebmgr-secrets}"
FRONTEND_DIR="${ROOT_DIR}/frontend"
ANDROID_DIR="${FRONTEND_DIR}/android"
ANDROID_ASSETS_DIR="${ANDROID_DIR}/app/src/main/assets/public"
ANDROID_LOCAL_PROPERTIES_FILE="${ANDROID_DIR}/local.properties"
LOG_DIR="${LOG_DIR:-${ROOT_DIR}/scripts/dev/logs}"
RUN_TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
GIT_SHA="$(git -C "${ROOT_DIR}" rev-parse --short HEAD 2>/dev/null || echo "nogit")"
LOG_FILE="${LOG_FILE:-${LOG_DIR}/deploy-dev-${RUN_TIMESTAMP}-${GIT_SHA}.log}"
FORCE_DESTROY=false
ANDROID_BUILD=false
SECRET_BACKUP_FILE=""

usage() {
  cat <<EOF
Usage: $(basename "$0") [--force]

Options:
  --force   Delete the namespace without preserving ${SECRET_NAME}.
  --android-build
            Rebuild the Android debug APK after the deploy completes.
EOF
}

while (($# > 0)); do
  case "$1" in
    --force)
      FORCE_DESTROY=true
      ;;
    --android-build)
      ANDROID_BUILD=true
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

node_major_version() {
  local version
  version="$(node -v 2>/dev/null || true)"
  version="${version#v}"
  printf '%s\n' "${version%%.*}"
}

copy_web_dist_into_android_assets() {
  if [[ ! -d "${ANDROID_ASSETS_DIR}" ]]; then
    echo "Android assets directory not found at ${ANDROID_ASSETS_DIR}" >&2
    exit 1
  fi
  if [[ ! -d "${FRONTEND_DIR}/dist" ]]; then
    echo "Frontend dist directory not found at ${FRONTEND_DIR}/dist" >&2
    exit 1
  fi

  echo "Copying built web assets into the existing Capacitor Android project"
  find "${ANDROID_ASSETS_DIR}" -mindepth 1 -maxdepth 1 \
    ! -name ".gitkeep" \
    ! -name "cordova.js" \
    ! -name "cordova_plugins.js" \
    -exec rm -rf {} +
  cp -R "${FRONTEND_DIR}/dist/." "${ANDROID_ASSETS_DIR}/"
}

detect_android_sdk_dir() {
  local candidate
  for candidate in \
    "${ANDROID_SDK_ROOT:-}" \
    "${ANDROID_HOME:-}" \
    "${HOME}/Android/Sdk" \
    "${HOME}/Android" \
    /mnt/c/Users/*/AppData/Local/Android/Sdk
  do
    if [[ -n "${candidate}" && -d "${candidate}" ]]; then
      printf '%s\n' "${candidate}"
      return 0
    fi
  done
  return 1
}

ensure_android_local_properties() {
  local sdk_dir
  sdk_dir="$(detect_android_sdk_dir || true)"
  if [[ -z "${sdk_dir}" ]]; then
    echo "Android SDK not found. Set ANDROID_SDK_ROOT or install the SDK before Android builds." >&2
    echo "Expected one of: \$ANDROID_SDK_ROOT, \$ANDROID_HOME, \$HOME/Android/Sdk, or a Windows SDK under /mnt/c/Users/.../AppData/Local/Android/Sdk" >&2
    exit 1
  fi

  export ANDROID_SDK_ROOT="${sdk_dir}"
  export ANDROID_HOME="${sdk_dir}"
  printf 'sdk.dir=%s\n' "${sdk_dir//\\/\\\\}" > "${ANDROID_LOCAL_PROPERTIES_FILE}"
  echo "Using Android SDK: ${sdk_dir}"
  echo "Wrote ${ANDROID_LOCAL_PROPERTIES_FILE}"
}

echo "YotoWebMgr destructive dev deploy"
echo "UTC timestamp: ${RUN_TIMESTAMP}"
echo "Git SHA: ${GIT_SHA}"
echo "Log file: ${LOG_FILE}"
echo "Force destroy: ${FORCE_DESTROY}"
echo "Android build: ${ANDROID_BUILD}"
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

if [[ "${ANDROID_BUILD}" == "true" ]]; then
  echo "Building Android debug APK"
  if [[ ! -d "${FRONTEND_DIR}" ]]; then
    echo "Frontend directory not found at ${FRONTEND_DIR}" >&2
    exit 1
  fi

  pushd "${FRONTEND_DIR}" >/dev/null
  ensure_android_local_properties
  if [[ ! -d "node_modules/@rollup/rollup-linux-x64-gnu" ]]; then
    echo "Linux Rollup optional dependency is missing; refreshing frontend dependencies for this WSL build"
    npm install
  fi
  npm run build
  if [[ "$(node_major_version)" =~ ^[0-9]+$ ]] && (( $(node_major_version) >= 22 )); then
    npx cap sync android
  else
    echo "Node $(node -v) is below Capacitor CLI's required Node 22 runtime; skipping 'cap sync' and using asset-copy fallback"
    echo "Fallback assumption: the existing Android wrapper is already checked in and no native Capacitor plugin set changed."
    copy_web_dist_into_android_assets
  fi
  popd >/dev/null

  if [[ ! -x "${ANDROID_DIR}/gradlew" ]]; then
    echo "Android Gradle wrapper not found at ${ANDROID_DIR}/gradlew" >&2
    exit 1
  fi

  pushd "${ANDROID_DIR}" >/dev/null
  ./gradlew assembleDebug
  popd >/dev/null

  echo "Android APK built:"
  echo "  ${ANDROID_DIR}/app/build/outputs/apk/debug/app-debug.apk"
  echo
fi

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
