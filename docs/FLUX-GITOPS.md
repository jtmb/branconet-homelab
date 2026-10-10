# BORTUS Flux integration

BORTUS manages and displays Flux GitRepositories and Kustomizations installed in the connected cluster. Flux must be supplied independently. This application merge adds no charts or cluster bootstrap files and does not change a live GitRepository branch.

## Source and reconciliation

Use the repository, branch, path and reconciliation interval actually configured in the cluster. Inspect the source and revision before publishing manifests:

```bash
kubectl get gitrepositories,kustomizations -n flux-system
kubectl describe gitrepository <name> -n flux-system
kubectl describe kustomization <name> -n flux-system
```

Publish manifests to that source, then use the dashboard's **Sync** operation or the configured Flux CLI. Changes to BORTUS application source in main do not themselves rebuild or redeploy the running image.

## Dashboard and API

The `/flux` page displays a hierarchy of repositories, Kustomizations, HelmReleases and namespace inventory. Repository and bundle links show readiness, conditions, events and managed resources.

- `GET /api/flux/hierarchy`: hierarchy, authenticated users.
- `GET /api/flux/repos`: repository list.
- `GET /api/flux/repos/<name>/detail`: repository and bundle detail.
- `GET /api/flux/kustomizations/<name>`: bundle inventory and conditions.
- Repository create, delete and sync operations require the fresh `write` role.

See [API usage](API-USAGE.md) for the full application interface. Dashboard writes operate on the connected cluster using the application's credentials.

## Private repository credentials

New private-repository credentials are created as native Secrets in `flux-system` using verified API request bodies. Configure the namespace allowlist and RBAC accordingly. `GitRepo.authData` stays empty; old SQLite credentials are never replayed. Existing native Secret collisions fail instead of overwriting imported credentials.

Keep value-bearing native Secret resources out of Git. Manifests should reference credentials created independently. Bootstrap and recovery credentials must remain available outside the cluster being created. See [deployment contract](BORTUS-DEPLOYMENT.md).