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
python -m venv .venv
.venv\Scripts\activate
pip install -e .[dev]
uvicorn app.main:app --reload
```

### Worker

```bash
cd worker
python -m venv .venv
.venv\Scripts\activate
pip install -e .[dev]
python -m app.worker
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

## Initial Scope

The current scaffold provides:

- FastAPI health API under `/api/v1`
- Auth scaffold with quick household user selection, Argon2 password support hooks, and OAuth 2.0 placeholders
- Python worker bootstrap
- Mobile-first React shell with base navigation
- Kubernetes base manifests for namespace, frontend, api, worker, and postgres
- Documentation stubs aligned with the project brief
