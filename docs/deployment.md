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
The default dev deployment is now non-destructive for the app namespace: it keeps `yotowebmgr`,
preserves PostgreSQL storage and media PVCs, rebuilds the images, reapplies the manifests, and
rolls the app deployments so they pull the fresh `:dev` images.

The API container also supports an explicit development reset switch:

```text
RESET_DATABASE_ON_START=true
```

When this is enabled with `ENVIRONMENT=development` and a PostgreSQL `DATABASE_URL`, API startup
drops and recreates the PostgreSQL `public` schema before running Alembic.

The dev overlay now keeps `RESET_DATABASE_ON_START=false` so ordinary redeploys preserve library
state. Use `--destructive` if you want the old clean-slate namespace reset behavior, or `--force`
if you also want to skip the existing secret and Yoto-state preservation helpers.

```bash
k8s/scripts/deploy-dev.sh
```

```bash
k8s/scripts/deploy-dev.sh --destructive
```

To build Android artifacts from the same script:

```bash
k8s/scripts/deploy-dev.sh --android-build
```

That produces an APK. If you have `frontend/android/keystore.properties` configured and need the
Google Play upload artifact instead, build the signed release app bundle:

```bash
k8s/scripts/deploy-dev.sh --android-bundle
```

That now builds both the Play bundle and a signed release APK in one run.

The Play Console bundle output path is:

```text
frontend/android/app/build/outputs/bundle/release/app-release.aab
```

The signed release APK output path is:

```text
frontend/android/app/build/outputs/apk/release/app-release.apk
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
scripts/dev/redeploy.sh    # MicroK8s rebuild/redeploy; preserves state unless --destructive is passed through
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
- In the default dev pipeline this PVC is preserved because the namespace is no longer deleted on
  every run.
- If you run `k8s/scripts/deploy-dev.sh --destructive`, the namespace is deleted and recreated, so
  this PVC is wiped along with the rest of the namespace.

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
