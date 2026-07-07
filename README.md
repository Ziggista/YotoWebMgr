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

The dev deployment script deletes the `yotowebmgr` namespace before applying the manifests so
PostgreSQL starts with a clean volume and Alembic applies all migrations from scratch.

Filesystem imports use a persistent MicroK8s volume mounted into the API and worker pods at:

```text
/media/imports
```

Use `/media/imports/drop` for files copied into the pod-backed import area and
`/media/imports/uploads` for browser-uploaded files staged by the API.

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
