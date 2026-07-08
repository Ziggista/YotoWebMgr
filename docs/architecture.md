# Architecture

## Overview

YotoWebMgr is split into four main runtime areas:

- A React frontend for household-facing workflows.
- A FastAPI backend for authenticated REST APIs.
- A Python worker for long-running and retry-safe processing jobs.
- PostgreSQL for application state, audit history, and job leasing.

## Design Principles

- Original media is immutable.
- Background work is asynchronous and idempotent.
- Version history is append-only and restore-safe.
- Integrations such as Yoto and Plex are isolated behind service layers.
- Tags are reusable records with generic assignments so the same tag model can apply to library
  items first and later extend to cards, playlists, or versions without duplicating tag names.

## Initial Runtime Topology

- `frontend` serves the web UI.
- `api` exposes `/api/v1` and health endpoints.
- `worker` polls a PostgreSQL-backed jobs table.
- `postgres` stores operational and domain data.

## Persistence

The backend uses SQLAlchemy 2.x models with Alembic migrations against PostgreSQL. The first
migration creates household user records for Krystin and Dale so local auth can move from the
temporary in-memory scaffold to persistent accounts without changing the API contract.
