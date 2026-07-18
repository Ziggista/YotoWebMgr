# Fixes and Environment Notes

This file records local environment and dependency fixes that affect how YotoWebMgr is developed
or tested. Keep it short and practical so future us does not rediscover the same sharp edges.

## 2026-07-07 - Backend Python Tooling in WSL

### What happened

The WSL Python install had `python3` but did not include `venv`/`pip`, so the backend virtual
environment could not be created and project dependencies could not be installed.

### Fix

Installed the missing system packages:

```bash
sudo apt-get update
sudo apt-get install -y python3.12-venv python3-pip
```

Then created the backend virtual environment:

```bash
cd backend
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
```

### Watch-outs

- `.venv/` is ignored by Git and should stay local.
- If WSL is rebuilt, this setup may need to be repeated.

## 2026-07-07 - Backend Dependency Caps

### What happened

Open-ended backend dependency ranges pulled newer FastAPI/Starlette/httpx/pytest/ruff versions.
The test stack hung inside Starlette/AnyIO request handling in this environment.

### Fix

Capped the backend dependency ranges in `backend/pyproject.toml` to the currently verified major
and minor ranges:

```text
fastapi>=0.115.0,<0.116.0
uvicorn[standard]>=0.30.0,<0.31.0
pydantic>=2.8.0,<3.0.0
pydantic-settings>=2.4.0,<3.0.0
sqlalchemy>=2.0.32,<3.0.0
alembic>=1.13.2,<2.0.0
httpx>=0.27.0,<0.28.0
pytest>=8.3.2,<9.0.0
pytest-asyncio>=0.24.0,<1.0.0
ruff>=0.6.2,<0.7.0
```

### Watch-outs

- Do not widen these casually. Upgrade deliberately, then run backend tests and lint.
- If adding lockfiles later, keep this note and the lockfile in sync.

## 2026-07-07 - FastAPI Request Tests

### What happened

`fastapi.testclient.TestClient` and sync dependency overrides could hang in the sandbox/WSL test
environment.

### Fix

Backend API tests use `httpx.AsyncClient` with `ASGITransport`, and the auth service dependency is
async so FastAPI does not need to construct it through a worker thread.

Example pattern:

```python
async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
    response = await client.get("/api/v1/health")
```

### Watch-outs

- Prefer async API tests for FastAPI routes.
- If adding dependency overrides in tests, make them async when they are used by async routes.

## 2026-07-07 - Editable Install Metadata

### What happened

`pip install -e '.[dev]'` creates local `*.egg-info/` metadata, which showed up as untracked
working-tree noise.

### Fix

Added `*.egg-info/` to `.gitignore`.

### Watch-outs

- Do not commit generated package metadata.

## 2026-07-07 - Frontend Node Tooling in WSL

### What happened

The WSL shell did not have a usable local `node` binary. `npm` was resolving to a Windows/Docker
Desktop shim and reported that WSL 1 was unsupported, which blocked frontend install/build/test.

### Fix

Installed Node.js and npm inside WSL:

```bash
sudo apt-get update
sudo apt-get install -y nodejs npm
```

Then installed frontend dependencies:

```bash
cd frontend
npm install
npm run build
```

This created `frontend/package-lock.json`, which should be committed for repeatable frontend
installs.

### Watch-outs

- The current apt-provided Node is Node 18, which is enough for the current Vite 5 frontend.
- `npm audit` reports a Vite/esbuild dev-server advisory. The suggested automatic fix jumps to a
  breaking Vite major, so do not run `npm audit fix --force` casually.

## 2026-07-07 - MicroK8s Local Validation

### What happened

MicroK8s snap commands cannot run inside the restricted sandbox because snap needs capabilities and
write access to its user data directories.

### Fix

Run MicroK8s commands outside the sandbox/with approval. The cluster was healthy with DNS and
hostpath storage enabled.

### Watch-outs

- Local port-forwards also need commands that connect to them to run outside the sandbox.
- For local API testing, Postgres was started in MicroK8s and forwarded to localhost:

```bash
microk8s kubectl -n yotowebmgr port-forward svc/postgres 15432:5432
```

Then the backend used:

```bash
DATABASE_URL=postgresql+psycopg://yotowebmgr:change-me@127.0.0.1:15432/yotowebmgr
```

## 2026-07-07 - MicroK8s Image Builds Without Docker Desktop

### What happened

Docker Desktop must not be part of the YotoWebMgr workflow. MicroK8s containerd is available, but it
does not provide a Dockerfile builder by itself.

### Fix

Use WSL-native `buildah` to build images and MicroK8s' local registry addon to store them:

```bash
microk8s enable registry
k8s/scripts/build-images.sh
microk8s kubectl apply -k k8s/overlays/dev
```

The dev overlay rewrites app images to:

```text
localhost:32000/yotowebmgr-api:dev
localhost:32000/yotowebmgr-worker:dev
localhost:32000/yotowebmgr-frontend:dev
```

### Watch-outs

- Do not use Docker Desktop for this project.
- App deployments use `imagePullPolicy: Always` because the dev pipeline reuses the `:dev` tag.
- Keep Alembic revision IDs under 32 characters. Alembic's default `version_num` column is
  `VARCHAR(32)`, so long descriptive revision strings can make fresh PostgreSQL migrations fail
  after the DDL has already run.
- `buildah` may need `BUILDAH_ISOLATION=chroot` under WSL; `k8s/scripts/build-images.sh` sets this
  by default.
- `buildah` may also need a writable runtime directory instead of `/run/user/<uid>`;
  `k8s/scripts/build-images.sh` sets `XDG_RUNTIME_DIR` under `/tmp` by default.
- `k8s/scripts/deploy-dev.sh` enables the registry if needed, builds/pushes images, deletes the
  `yotowebmgr` namespace for a fresh database, applies the dev overlay, and waits for rollouts.

## 2026-07-07 - Browser Upload Dependency

### What happened

FastAPI multipart form uploads require `python-multipart`. Without it, routes using `UploadFile`
fail at application import time.

### Fix

Added this backend dependency:

```text
python-multipart>=0.0.9,<0.1.0
```

### Watch-outs

- Keep browser uploads staged under `/media/imports/uploads`.
- Keep filesystem import paths constrained to `/media/imports/drop`; do not accept arbitrary pod
  paths from the UI.

## 2026-07-07 - Frontend Audio Player

### What happened

The Library UI needed embedded media playback without hand-rolling custom audio controls.

### Fix

Added `react-h5-audio-player@3.10.2`. It is MIT-licensed and wraps the browser audio element with
responsive controls.

### Watch-outs

- Keep the package license/version in `docs/test-media.md` current if upgrading.
- Do not expose arbitrary filesystem paths as audio URLs. Playback should go through API routes
  that validate media roots.

## 2026-07-18 - PKCE on Tailscale HTTP Dev Host

### What happened

The Yoto `Test browser auth` button failed on the remote Tailscale dev URL with:

```text
Cannot read properties of undefined (reading 'digest')
```

The frontend was assuming `window.crypto.subtle.digest(...)` existed for PKCE hashing. On the
non-HTTPS Tailscale dev origin, some browser/runtime combinations expose `crypto` but not
`SubtleCrypto`.

### Fix

The frontend PKCE helper now:

- uses Web Crypto when `crypto.subtle` is available
- falls back to a local SHA-256 implementation when it is not
- still uses `crypto.getRandomValues(...)` for verifier generation

### Watch-outs

- Quick-select a local household user before testing the Settings page; otherwise the auth gate
  hides the Yoto controls.
- Do not assume browser security APIs behave the same on `http://127.0.0.1` and on an HTTP
  Tailscale hostname.
