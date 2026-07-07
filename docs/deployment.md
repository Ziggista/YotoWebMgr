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
`yotowebmgr`, recreates PostgreSQL storage, and runs migrations from scratch.

```bash
k8s/scripts/deploy-dev.sh
```

To open the frontend service after deployment:

```bash
microk8s kubectl -n yotowebmgr port-forward svc/frontend 5173:80
```

Then browse to:

```text
http://localhost:5173/
```

## Import Storage

The API and worker both mount the `imports-pvc` claim at:

```text
/media/imports
```

The import area is split by purpose:

```text
/media/imports/drop
/media/imports/uploads
```

- `/media/imports/drop` is the reusable filesystem import area. Files placed here can be queued
  from the Import screen by absolute path or path relative to the drop directory.
- `/media/imports/uploads` is where browser uploads are staged by the API before worker processing.
- The backend constrains filesystem imports to `/media/imports/drop` to avoid arbitrary host or pod
  path access.
- Library playback currently serves staged import media only when the source file is still inside
  the configured import storage roots.
- In the dev pipeline this PVC is recreated whenever `k8s/scripts/deploy-dev.sh` deletes the
  namespace. For non-destructive environments, keep this PVC and the media PVCs persistent.
