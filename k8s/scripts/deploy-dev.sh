#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
export PATH="/snap/bin:${PATH}"
MICROK8S_BIN="${MICROK8S_BIN:-$(command -v microk8s || true)}"
NAMESPACE="${NAMESPACE:-yotowebmgr}"
SECRET_NAME="${SECRET_NAME:-yotowebmgr-secrets}"
BIND_ADDRESS="${BIND_ADDRESS:-127.0.0.1}"
FRONTEND_DIR="${ROOT_DIR}/frontend"
ANDROID_DIR="${FRONTEND_DIR}/android"
ANDROID_ASSETS_DIR="${ANDROID_DIR}/app/src/main/assets/public"
ANDROID_LOCAL_PROPERTIES_FILE="${ANDROID_DIR}/local.properties"
ANDROID_KEYSTORE_PROPERTIES_FILE="${ANDROID_DIR}/keystore.properties"
LOG_DIR="${LOG_DIR:-${ROOT_DIR}/scripts/dev/logs}"
RUN_TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
GIT_SHA="$(git -C "${ROOT_DIR}" rev-parse --short HEAD 2>/dev/null || echo "nogit")"
LOG_FILE="${LOG_FILE:-${LOG_DIR}/deploy-dev-${RUN_TIMESTAMP}-${GIT_SHA}.log}"
FORCE_DESTROY=false
ANDROID_BUILD=false
SECRET_BACKUP_FILE=""
YOTO_STATE_BACKUP_FILE=""

if [[ -z "${MICROK8S_BIN}" && -x /snap/bin/microk8s ]]; then
  MICROK8S_BIN="/snap/bin/microk8s"
fi
if [[ -z "${MICROK8S_BIN}" ]]; then
  echo "microk8s command not found. Ensure MicroK8s is installed in WSL and available on PATH or at /snap/bin/microk8s." >&2
  exit 1
fi

usage() {
  cat <<EOF
Usage: $(basename "$0") [--force] [--bind-address ADDRESS]

Options:
  --force   Delete the namespace without preserving ${SECRET_NAME}.
  --android-build
            Rebuild the Android debug APK after the deploy completes.
  --bind-address ADDRESS
            Bind the frontend port-forward to a specific address, such as 0.0.0.0.
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
    --bind-address)
      shift
      if (($# == 0)); then
        echo "Missing value for --bind-address" >&2
        usage >&2
        exit 1
      fi
      BIND_ADDRESS="$1"
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
  if [[ -n "${YOTO_STATE_BACKUP_FILE}" && -f "${YOTO_STATE_BACKUP_FILE}" ]]; then
    rm -f "${YOTO_STATE_BACKUP_FILE}"
  fi
}
trap cleanup EXIT

postgres_psql() {
  local sql="$1"
  "${MICROK8S_BIN}" kubectl -n "${NAMESPACE}" exec deploy/postgres -- bash -lc \
    "PGPASSWORD='change-me' psql -U yotowebmgr -d yotowebmgr -v ON_ERROR_STOP=1 -At -c \"$sql\""
}

backup_yoto_state() {
  if [[ "${FORCE_DESTROY}" == "true" ]]; then
    echo "Force mode enabled: Yoto database-backed state will not be preserved."
    return 0
  fi

  if ! "${MICROK8S_BIN}" kubectl -n "${NAMESPACE}" get deploy postgres >/dev/null 2>&1; then
    echo "No existing postgres deployment found to preserve Yoto database-backed state."
    return 0
  fi

  local settings_json
  local credentials_json
  settings_json="$(postgres_psql "SELECT COALESCE(json_agg(row_to_json(t)), '[]'::json)::text FROM (SELECT key, value, description FROM settings WHERE key LIKE 'yoto_%' ORDER BY key) t;")"
  credentials_json="$(postgres_psql "SELECT COALESCE(json_agg(row_to_json(t)), '[]'::json)::text FROM (SELECT id, account_label, status, token_storage_ref, masked_account_id, masked_email, scopes, authorization_url, oauth_state, last_refreshed_at, expires_at, error_summary, created_at, updated_at FROM yoto_credential_states ORDER BY id) t;")"

  YOTO_STATE_BACKUP_FILE="$(mktemp "${TMPDIR:-/tmp}/yotowebmgr-yoto-state-${RUN_TIMESTAMP}-XXXXXX.json")"
  python3 - <<PY
import json

settings = json.loads("""${settings_json}""")
credentials = json.loads("""${credentials_json}""")
with open("${YOTO_STATE_BACKUP_FILE}", "w", encoding="utf-8") as handle:
    json.dump({"settings": settings, "credentials": credentials}, handle, indent=2)
PY
  echo "Backed up $(python3 - <<PY
import json
payload = json.load(open("${YOTO_STATE_BACKUP_FILE}", "r", encoding="utf-8"))
print(f"{len(payload.get('settings', []))} Yoto setting(s) and {len(payload.get('credentials', []))} credential row(s)")
PY
) to ${YOTO_STATE_BACKUP_FILE}"
}

restore_yoto_state() {
  if [[ -z "${YOTO_STATE_BACKUP_FILE}" || ! -f "${YOTO_STATE_BACKUP_FILE}" ]]; then
    return 0
  fi

  echo "Restoring preserved Yoto database-backed state from ${YOTO_STATE_BACKUP_FILE}"
  python3 - <<PY | "${MICROK8S_BIN}" kubectl -n "${NAMESPACE}" exec -i deploy/postgres -- bash -lc "PGPASSWORD='change-me' psql -U yotowebmgr -d yotowebmgr -v ON_ERROR_STOP=1"
import json

payload = json.load(open("${YOTO_STATE_BACKUP_FILE}", "r", encoding="utf-8"))

def sql_literal(value):
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    text = str(value).replace("'", "''")
    return f"'{text}'"

print("BEGIN;")
for row in payload.get("settings", []):
    print(
        "INSERT INTO settings (key, value, description) VALUES "
        f"({sql_literal(row.get('key'))}, {sql_literal(row.get('value'))}, {sql_literal(row.get('description'))}) "
        "ON CONFLICT (key) DO UPDATE SET "
        "value = EXCLUDED.value, "
        "description = EXCLUDED.description, "
        "updated_at = NOW();"
    )

for row in payload.get("credentials", []):
    print(
        "INSERT INTO yoto_credential_states "
        "(id, account_label, status, token_storage_ref, masked_account_id, masked_email, scopes, authorization_url, oauth_state, last_refreshed_at, expires_at, error_summary, created_at, updated_at) VALUES "
        f"({sql_literal(row.get('id'))}, {sql_literal(row.get('account_label'))}, {sql_literal(row.get('status'))}, {sql_literal(row.get('token_storage_ref'))}, {sql_literal(row.get('masked_account_id'))}, {sql_literal(row.get('masked_email'))}, {sql_literal(row.get('scopes'))}, {sql_literal(row.get('authorization_url'))}, {sql_literal(row.get('oauth_state'))}, {sql_literal(row.get('last_refreshed_at'))}, {sql_literal(row.get('expires_at'))}, {sql_literal(row.get('error_summary'))}, {sql_literal(row.get('created_at'))}, {sql_literal(row.get('updated_at'))}) "
        "ON CONFLICT (id) DO UPDATE SET "
        "account_label = EXCLUDED.account_label, "
        "status = EXCLUDED.status, "
        "token_storage_ref = EXCLUDED.token_storage_ref, "
        "masked_account_id = EXCLUDED.masked_account_id, "
        "masked_email = EXCLUDED.masked_email, "
        "scopes = EXCLUDED.scopes, "
        "authorization_url = EXCLUDED.authorization_url, "
        "oauth_state = EXCLUDED.oauth_state, "
        "last_refreshed_at = EXCLUDED.last_refreshed_at, "
        "expires_at = EXCLUDED.expires_at, "
        "error_summary = EXCLUDED.error_summary, "
        "created_at = EXCLUDED.created_at, "
        "updated_at = EXCLUDED.updated_at;"
    )

print("SELECT setval(pg_get_serial_sequence('yoto_credential_states', 'id'), COALESCE((SELECT MAX(id) FROM yoto_credential_states), 1), true);")
print("COMMIT;")
PY
  echo "Yoto database-backed state restored."
}

node_major_version() {
  local version
  version="$(node -v 2>/dev/null || true)"
  version="${version#v}"
  printf '%s\n' "${version%%.*}"
}

ensure_frontend_node_modules() {
  if [[ ! -d "${FRONTEND_DIR}/node_modules/@rollup/rollup-linux-x64-gnu" ]]; then
    echo "Linux Rollup optional dependency is missing; refreshing frontend dependencies for this WSL build"
    pushd "${FRONTEND_DIR}" >/dev/null
    npm install
    popd >/dev/null
  fi
}

prepare_frontend_ota_bundle() {
  if [[ ! -d "${FRONTEND_DIR}" ]]; then
    echo "Frontend directory not found at ${FRONTEND_DIR}" >&2
    exit 1
  fi

  echo "Preparing frontend OTA bundle for Android web updates"
  ensure_frontend_node_modules
  pushd "${FRONTEND_DIR}" >/dev/null
  VITE_APP_BUILD_SHA="${GIT_SHA}" npm run build
  VITE_APP_BUILD_SHA="${GIT_SHA}" npm run build:ota-bundle
  popd >/dev/null
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
    "${HOME}/Android"
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
    echo "Android SDK not found in WSL. Set ANDROID_SDK_ROOT or install the Linux Android SDK before Android builds." >&2
    echo "Expected one of: \$ANDROID_SDK_ROOT, \$ANDROID_HOME, \$HOME/Android/Sdk, or \$HOME/Android" >&2
    echo "Do not point WSL Gradle builds at a Windows SDK under /mnt/c/... because Linux tools need Linux binaries such as 'aapt', not 'aapt.exe'." >&2
    exit 1
  fi
  if [[ "${sdk_dir}" == /mnt/* ]]; then
    echo "Refusing to use Android SDK from ${sdk_dir} for this WSL build." >&2
    echo "WSL Gradle builds require a Linux Android SDK install inside WSL, not the Windows SDK mounted under /mnt/c/..." >&2
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
echo "Port-forward bind address: ${BIND_ADDRESS}"
echo

if ! "${MICROK8S_BIN}" status --wait-ready | grep -q "registry.*enabled"; then
  echo "Enabling MicroK8s registry addon"
  "${MICROK8S_BIN}" enable registry
fi

if [[ "${FORCE_DESTROY}" != "true" ]]; then
  if "${MICROK8S_BIN}" kubectl -n "${NAMESPACE}" get secret "${SECRET_NAME}" >/dev/null 2>&1; then
    SECRET_BACKUP_FILE="$(mktemp "${TMPDIR:-/tmp}/yotowebmgr-secret-${RUN_TIMESTAMP}-XXXXXX.json")"
    echo "Backing up ${NAMESPACE}/${SECRET_NAME} to ${SECRET_BACKUP_FILE}"
    "${MICROK8S_BIN}" kubectl -n "${NAMESPACE}" get secret "${SECRET_NAME}" -o json \
      | python3 -c 'import json,sys; source=json.load(sys.stdin); sanitized={"apiVersion":"v1","kind":"Secret","metadata":{"name":source["metadata"]["name"],"namespace":source["metadata"]["namespace"]},"type":source.get("type","Opaque"),"data":source.get("data",{})}; json.dump(sanitized, sys.stdout)' \
      > "${SECRET_BACKUP_FILE}"
  else
    echo "No existing ${NAMESPACE}/${SECRET_NAME} secret found to preserve."
  fi
else
  echo "Force mode enabled: ${NAMESPACE}/${SECRET_NAME} will not be preserved."
fi

backup_yoto_state

echo "Deleting existing ${NAMESPACE} namespace before building or deploying"
"${MICROK8S_BIN}" kubectl delete namespace "${NAMESPACE}" --ignore-not-found=true
while "${MICROK8S_BIN}" kubectl get namespace "${NAMESPACE}" >/dev/null 2>&1; do
  echo "Waiting for ${NAMESPACE} namespace deletion"
  sleep 2
done

prepare_frontend_ota_bundle
"${ROOT_DIR}/k8s/scripts/build-images.sh"

"${MICROK8S_BIN}" kubectl apply -k "${ROOT_DIR}/k8s/overlays/dev"
if [[ -n "${SECRET_BACKUP_FILE}" && -f "${SECRET_BACKUP_FILE}" ]]; then
  echo "Restoring preserved ${NAMESPACE}/${SECRET_NAME}"
  "${MICROK8S_BIN}" kubectl apply -f "${SECRET_BACKUP_FILE}"
fi
"${MICROK8S_BIN}" kubectl -n "${NAMESPACE}" rollout status deployment/postgres --timeout=180s
"${MICROK8S_BIN}" kubectl -n "${NAMESPACE}" rollout status deployment/api --timeout=180s
"${MICROK8S_BIN}" kubectl -n "${NAMESPACE}" rollout status deployment/worker --timeout=180s
"${MICROK8S_BIN}" kubectl -n "${NAMESPACE}" rollout status deployment/frontend --timeout=180s
restore_yoto_state

echo
echo "Pods:"
"${MICROK8S_BIN}" kubectl -n "${NAMESPACE}" get pods -o wide
echo
echo "Recent backend API logs:"
"${MICROK8S_BIN}" kubectl -n "${NAMESPACE}" logs deployment/api --tail=200 || true
echo
echo "Recent frontend logs:"
"${MICROK8S_BIN}" kubectl -n "${NAMESPACE}" logs deployment/frontend --tail=200 || true
echo

if [[ "${ANDROID_BUILD}" == "true" ]]; then
  android_gradle_task="assembleDebug"
  android_output_path="${ANDROID_DIR}/app/build/outputs/apk/debug/app-debug.apk"
  android_build_label="debug APK"
  if [[ -f "${ANDROID_KEYSTORE_PROPERTIES_FILE}" ]]; then
    android_gradle_task="assembleRelease"
    android_output_path="${ANDROID_DIR}/app/build/outputs/apk/release/app-release.apk"
    android_build_label="signed release APK"
  fi

  echo "Building Android ${android_build_label}"
  if [[ ! -d "${FRONTEND_DIR}" ]]; then
    echo "Frontend directory not found at ${FRONTEND_DIR}" >&2
    exit 1
  fi

  pushd "${FRONTEND_DIR}" >/dev/null
  ensure_android_local_properties
  ensure_frontend_node_modules
  VITE_APP_BUILD_SHA="${GIT_SHA}" npm run build
  VITE_APP_BUILD_SHA="${GIT_SHA}" npm run build:ota-bundle
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
  ./gradlew "${android_gradle_task}"
  popd >/dev/null

  echo "Android ${android_build_label} built:"
  echo "  ${android_output_path}"
  echo
fi

echo "Dev deployment is ready."
echo "Ensuring the Kubernetes frontend is forwarded."
BIND_ADDRESS="${BIND_ADDRESS}" bash "${ROOT_DIR}/k8s/scripts/ensure-dev-port-forward.sh"
echo "Browse to:"
if [[ "${BIND_ADDRESS}" == "0.0.0.0" ]]; then
  echo "  http://127.0.0.1:5175/"
  echo "  http://ziggi-pc-1.tailaf3d4b.ts.net:5175/"
else
  echo "  http://127.0.0.1:5175/"
fi
echo
echo "Deploy log saved to:"
echo "  ${LOG_FILE}"
echo
echo "Useful follow-up log commands:"
echo "  microk8s kubectl -n ${NAMESPACE} logs deployment/api --tail=200 -f"
echo "  microk8s kubectl -n ${NAMESPACE} logs deployment/frontend --tail=200 -f"
echo "  microk8s kubectl -n ${NAMESPACE} logs deployment/worker --tail=200 -f"
