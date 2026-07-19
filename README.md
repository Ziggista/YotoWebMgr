# YotoWebMgr

YotoWebMgr is a self-hosted household media-library and Yoto MYO card management application.

This repository currently includes:

- `frontend`: React + TypeScript + Vite
- `backend`: FastAPI + Pydantic v2 + SQLAlchemy-ready structure
- `worker`: Python worker process for background jobs
- `k8s`: MicroK8s-oriented Kubernetes manifests

## Repository Layout

```text
YotoWebMgr/
├── backend/
├── docs/
├── frontend/
├── k8s/
├── scripts/
├── shared/
└── worker/
```

## Quick Start

### Backend

```bash
cd backend
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/uvicorn app.main:app --reload
```

### Worker

```bash
cd worker
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/python -m app.worker
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

### MicroK8s Dev Deployment

Docker Desktop is not used. Build and deploy from scratch with WSL-native `buildah` and the
MicroK8s registry:

```bash
k8s/scripts/deploy-dev.sh
```

From Windows PowerShell, use the wrapper that runs the same destructive script through WSL:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/dev/redeploy.ps1
```

The dev deployment script is intentionally destructive. It deletes the `yotowebmgr` namespace
before building images or applying manifests, so PostgreSQL starts with a clean volume and Alembic
applies all migrations from scratch.
The dev overlay also sets `RESET_DATABASE_ON_START=true`, which makes the API drop and recreate
PostgreSQL's `public` schema before migrations run. That is intentionally destructive and should
stay disabled outside disposable dev deployments.

The deployment script starts or refreshes the local frontend port-forward automatically. To check or
restart it later, run the dedicated helper:

```bash
k8s/scripts/open-dev.sh
```

Or from Windows PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/dev/open-dev.ps1
```

Then browse to:

```text
http://127.0.0.1:5175/
```

The deploy script now defaults the frontend port-forward bind address to `0.0.0.0`, so the same
dev deployment is reachable from remote devices over the current Windows/Tailscale forwarding path
without needing to pass `--bind-address 0.0.0.0` each time.

Use this URL for the MicroK8s app. Port `5173` is reserved for local Vite development and can show
stale local state if it is running separately.
When testing the deployed app, quick-select a local household user first. The Yoto settings screen
and OAuth actions sit behind that local auth gate.

### Dev Shortcuts

Common commands are wrapped so routine checks use less typing:

```bash
scripts/dev/verify.sh      # backend tests, frontend build, shell syntax checks
scripts/dev/redeploy.sh    # destructive MicroK8s rebuild/redeploy from scratch
k8s/scripts/deploy-dev.sh  # destructive Linux/WSL deploy entrypoint used by the wrappers
k8s/scripts/open-dev.sh    # ensure the Kubernetes frontend is forwarded on http://127.0.0.1:5175/
scripts/dev/status.sh      # pods, services, recent API logs
scripts/dev/seed-radio.sh  # add the ABC Triple J test stream to the current dev API
scripts/media/seed-copyleft-test-media.sh # seed local audiobook + kids album fixtures outside Git
```

PowerShell wrappers are also available:

```text
scripts/dev/redeploy.ps1
scripts/dev/open-dev.ps1
```

If you want to force a specific distro instead of the first installed one, set
`YOTOWEBMGR_WSL_DISTRO` before running the wrapper.

Filesystem imports use a persistent MicroK8s volume mounted into the API and worker pods at:

```text
/var/lib/yotowebmgr/media/imports
```

Use `/var/lib/yotowebmgr/media/imports/drop` for files copied into the pod-backed import area and
`/var/lib/yotowebmgr/media/imports/uploads` for browser-uploaded files staged by the API.

For repeatable end-to-end tests after a destructive redeploy, prefer browser upload through
`POST /api/v1/imports/uploads` or the Import screen. The `drop` directory is only reliable if the
current PVC has been seeded again after namespace deletion.

## Initial Scope

The current scaffold provides:

- FastAPI health API under `/api/v1`
- Auth scaffold with quick household user selection, Argon2 password support hooks, and OAuth 2.0 placeholders
- Import screen with browser upload and persistent filesystem drop-area support
- Library rows with embedded playback for staged media files
- Android-ready Capacitor wrapper with native NFC read/write support
- Yoto OAuth with PKCE, token persistence in Kubernetes Secrets, and live debug probes
- Local Yoto playlist drafts, generated live `POST /content` payload previews, and live playlist creation
- Card scan-dump capture plus staged or direct blank-card write workflows
- Python worker bootstrap
- Mobile-first React shell with base navigation
- Kubernetes base manifests for namespace, frontend, api, worker, and postgres
- Destructive dev deployment helpers and frontend/backend build stamping

## License

YotoWebMgr is licensed under the MIT License. See [LICENSE](LICENSE).
