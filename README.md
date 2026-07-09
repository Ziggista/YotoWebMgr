# YotoWebMgr

YotoWebMgr is a self-hosted household media-library and Yoto MYO card management application.

This repository is scaffolded for:

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

Then browse to:

```text
http://127.0.0.1:5175/
```

Use this URL for the MicroK8s app. Port `5173` is reserved for local Vite development and can show
stale local state if it is running separately.

### Dev Shortcuts

Common commands are wrapped so routine checks use less typing:

```bash
scripts/dev/verify.sh      # backend tests, frontend build, shell syntax checks
scripts/dev/redeploy.sh    # destructive MicroK8s rebuild/redeploy from scratch
k8s/scripts/open-dev.sh    # ensure the Kubernetes frontend is forwarded on http://127.0.0.1:5175/
scripts/dev/status.sh      # pods, services, recent API logs
scripts/dev/seed-radio.sh  # add the ABC Triple J test stream to the current dev API
```

Filesystem imports use a persistent MicroK8s volume mounted into the API and worker pods at:

```text
/var/lib/yotowebmgr/media/imports
```

Use `/var/lib/yotowebmgr/media/imports/drop` for files copied into the pod-backed import area and
`/var/lib/yotowebmgr/media/imports/uploads` for browser-uploaded files staged by the API.

## Initial Scope

The current scaffold provides:

- FastAPI health API under `/api/v1`
- Auth scaffold with quick household user selection, Argon2 password support hooks, and OAuth 2.0 placeholders
- Import screen with browser upload and persistent filesystem drop-area support
- Library rows with embedded playback for staged media files
- Python worker bootstrap
- Mobile-first React shell with base navigation
- Kubernetes base manifests for namespace, frontend, api, worker, and postgres
- Documentation stubs aligned with the project brief

## License

YotoWebMgr is licensed under the MIT License. See [LICENSE](LICENSE).
