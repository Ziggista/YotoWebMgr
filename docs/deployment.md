# Deployment

The initial deployment target is MicroK8s in WSL.

## Base Components

- Namespace: `yotowebmgr`
- Deployments: `frontend`, `api`, `worker`
- Stateful workload: `postgres`
- Persistent volume claims for media and database storage

## Notes

- Secrets should be supplied through Kubernetes `Secret` objects.
- Docker Desktop is not used for this project.
- Dev images are built with `buildah` and pushed to the MicroK8s local registry.
- Local overlays should adjust image names, ingress, and storage classes.

## Dev Deployment

The dev overlay expects the MicroK8s registry addon and images tagged under `localhost:32000`.
The dev deployment is intentionally destructive for the app namespace: each run deletes
`yotowebmgr` before image build/deploy, recreates PostgreSQL storage, and runs migrations from
scratch.

The API container also supports an explicit development reset switch:

```text
RESET_DATABASE_ON_START=true
```

When this is enabled with `ENVIRONMENT=development` and a PostgreSQL `DATABASE_URL`, API startup
drops and recreates the PostgreSQL `public` schema before running Alembic. This keeps dev deploys
honest against PostgreSQL instead of relying on throwaway SQLite schemas while the data model is
still moving quickly.

Keep `RESET_DATABASE_ON_START=false` outside disposable dev deployments.

```bash
k8s/scripts/deploy-dev.sh
```

`k8s/scripts/deploy-dev.sh` now defaults the frontend port-forward bind address to `0.0.0.0`.
That makes the forwarded `5175` service reachable from remote Android/browser clients when the
Windows host or Tailscale layer forwards the port onward.

The deployment script starts or refreshes the local frontend port-forward automatically. To check or
restart the frontend service forward after deployment:

```bash
k8s/scripts/open-dev.sh
```

Then browse to:

```text
http://127.0.0.1:5175/
```

Use `5175` for the MicroK8s app. Port `5173` is left to local Vite development so a stale local
frontend cannot be confused with the deployed cluster.
After opening the app, quick-select a local household user before testing Settings or Yoto OAuth.

For remote Android/browser testing over Tailscale, the current external dev host is:

```text
http://ziggi-pc-1.tailaf3d4b.ts.net:5175/
```

That host is useful for remote UI testing, but it is still the same dev deployment behind the local
port-forward/proxy setup.

The deploy script also now waits for:

- Alembic to finish materialising the schema before any Yoto database-state restore runs.
- `api`, `worker`, and `frontend` pods to remain `Ready`, not merely to report a Kubernetes rollout.

This matters because a container can crash after image start but before the app is genuinely usable.

## Dev Shortcuts

```bash
scripts/dev/verify.sh      # backend tests, frontend build, shell syntax checks
scripts/dev/redeploy.sh    # destructive MicroK8s rebuild/redeploy from scratch
k8s/scripts/open-dev.sh    # ensure the Kubernetes frontend is forwarded on http://127.0.0.1:5175/
scripts/dev/status.sh      # pods, services, recent API logs
scripts/dev/seed-radio.sh  # add the ABC Triple J test stream to the current dev API
```

## Import Storage

The API and worker both mount the `imports-pvc` claim at:

```text
/var/lib/yotowebmgr/media/imports
```

The import area is split by purpose:

```text
/var/lib/yotowebmgr/media/imports/drop
/var/lib/yotowebmgr/media/imports/uploads
```

- `/var/lib/yotowebmgr/media/imports/drop` is the reusable filesystem import area. Files placed here can be queued
  from the Import screen by absolute path or path relative to the drop directory.
- `/var/lib/yotowebmgr/media/imports/uploads` is where browser uploads are staged by the API before worker processing.
- The backend constrains filesystem imports to `/var/lib/yotowebmgr/media/imports/drop` to avoid arbitrary host or pod
  path access.
- Library playback currently serves staged import media only when the source file is still inside
  the configured import storage roots.
- In the dev pipeline this PVC is recreated whenever `k8s/scripts/deploy-dev.sh` deletes the
  namespace. For non-destructive environments, keep this PVC and the media PVCs persistent.

Practical testing rule: after a destructive dev redeploy, prefer browser upload or
`POST /api/v1/imports/uploads` for end-to-end media tests unless you have explicitly reseeded the
current `drop` PVC. A source path copied from a previous run can be valid locally but absent inside
the new API/worker pods.

## Card Inventory Fields

Cards are tracked locally before any assumption is made about remote Yoto card identity. The
initial card scaffold stores:

- `card_code`: household alphanumeric identifier such as `CARD01`.
- `programmable_id`: optional NFC/card programmable identifier or UID-like value.
- `card_kind`: official MYO, generic NFC, or transfer/source card.
- `chip_type` and `memory_size_bytes`: useful for generic cards; the DIY MYO workflow discussed
  MIFARE Ultralight EV1-style cards with 48-byte memory.
- `ndef_prepared`: whether the card has been formatted/prepared for NDEF data.
- `source_card_code`: optional transfer/source MYO card used when manually copying a link.
- `yoto_playlist_uri`: playlist/link URI if known.
- `tested`, `status`, `label_color`, and `notes` for household inventory workflow.

Physical linking still remains a user-confirmed workflow until actual card/API behaviour is
validated.

The newer Yoto draft flow can now create live Yoto content and store the returned remote card/content
ID on the draft. The older `upload_yoto_asset` job path is still a placeholder and should not be
treated as a completed live upload workflow.
