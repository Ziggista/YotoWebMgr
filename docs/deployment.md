# Deployment

The initial deployment target is MicroK8s in WSL.

## Base Components

- Namespace: `yotowebmgr`
- Deployments: `frontend`, `api`, `worker`
- Stateful workload: `postgres`
- Persistent volume claims for media and database storage

## Notes

- Secrets should be supplied through Kubernetes `Secret` objects.
- Local overlays should adjust image names, ingress, and storage classes.

