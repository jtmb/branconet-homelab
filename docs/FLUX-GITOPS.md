# Flux GitOps Guide

## Overview

Flux CD watches `charts/` in this repo and applies any changes to the cluster automatically. Every app lives in its own `charts/<name>/` subdirectory, giving Fleet-style per-app visibility.

## How Deployments Work

```mermaid
flowchart LR
    A["Edit YAML"] --> B["git push"]
    B --> C["Flux polls repo"]
    C --> D["Kustomize builds"]
    D --> E["kubectl apply"]
    E --> F["Cluster updated"]
    F --> G["Drift auto-corrected"]
```

1. **You change a manifest** — edit any `.yaml` in `charts/` or add a new app
2. **Commit & push** to the `k8s-rewrite` branch
3. **Flux detects it** — `GitRepository` polls GitHub every 5 minutes
4. **Kustomize builds it** — `charts/kustomization.yaml` flattens all subdirectories into two Kustomization stacks
5. **Applied server-side** — Flux runs the equivalent of `kubectl apply -k charts/ --server-side`
6. **Drift correction** — manual `kubectl edit` changes get reverted
7. **Pruning** — deleted files get removed from the cluster

## Directory Structure

```
k8s-rewrite/
├── charts/
│   ├── kustomization.yaml              ← Root: Flux builds this
│   ├── test-stack/                      ← Test/dev apps
│   │   ├── kustomization.yaml
│   │   ├── http-echo/
│   │   │   ├── kustomization.yaml
│   │   │   ├── namespace.yaml
│   │   │   ├── deployment.yaml
│   │   │   ├── service.yaml
│   │   │   ├── ingress.yaml
│   │   │   └── ingressroute.yaml
│   │   ├── nginx-hello/
│   │   └── whoami/
│   └── media-stack/                     ← Media apps
│       ├── kustomization.yaml
│       └── plex/
├── clusters/
│   ├── prd/flux-system/                 ← Production cluster bootstrap
│   ├── dev/flux-system/                 ← Dev cluster bootstrap
│   └── README.md
└── ansible-playbook/roles/gitops/       ← Automates Flux install + bootstrap
```

### Stack Architecture

The `charts/` directory is split into **two stacks**, each with its own Flux Kustomization CRD:

| Stack | Path | Kustomization CRD | Apps |
|-------|------|-------------------|------|
| **test-stack** | `./k8s-rewrite/charts/test-stack/` | `test-stack` | http-echo, nginx-hello, whoami |
| **media-stack** | `./k8s-rewrite/charts/media-stack/` | `media-stack` | plex |

Both stacks pull from the same `branconet-charts` GitRepository. The root `kustomization.yaml` references both stacks as resources:

```yaml
# charts/kustomization.yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
  - ./test-stack
  - ./media-stack
```

Each stack has its own `kustomization.yaml` referencing its apps:

```yaml
# charts/test-stack/kustomization.yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
  - ./http-echo
  - ./nginx-hello
  - ./whoami
```

## View Status

### Dashboard (Fleet-style Hierarchy)

The `/flux` page in the dashboard shows a Rancher Fleet-style expandable tree view:

- **GitRepositories** are root nodes, grouped by their `sourceRef`
- **Kustomizations** appear as children of the GitRepository they pull from
- **Namespaces** appear as leaf children of Kustomizations — parsed from the Kustomization's `status.inventory.entries` to show which namespaces are managed by that Kustomization
- **HelmReleases** appear as children of the GitRepository or Kustomization they reference
- Sub-kustomizations (e.g., `flux-system` Kustomization spawning per-app Kustomizations) nest recursively
- Each node shows live readiness status (green/amber/red), last sync time, and short revision hash
- Expand/collapse with tree-line indentation
- Sync and Delete buttons are available on root GitRepository rows

**Orphan filter:** The tree filters out GitRepositories that have no linked Kustomizations and aren't connected to any managed namespace. Suspended GitRepositories are also hidden.

The tree is powered by `GET /api/flux/hierarchy` which queries GitRepositories, Kustomizations, and HelmReleases from the cluster, links them by `sourceRef.name`, and merges DB metadata (auth method, ID) for tracked repos.

### kubectl / CLI

```bash
# What Flux resources are running?
kubectl get gitrepositories,kustomizations -n flux-system

# Fleet-style listing (with flux CLI)
flux get sources git -n flux-system
flux get kustomizations -n flux-system

# Detailed per-app status
flux get kustomizations --watch

# See what Flux would change
flux diff kustomization test-stack -n flux-system
```

## Add a New App

1. Create `charts/<stack>/<name>/` directory (in the appropriate stack: `test-stack` or `media-stack`)
2. Add `kustomization.yaml`:

```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
  - namespace.yaml
  - deployment.yaml
  - service.yaml
```

3. Add your Kubernetes manifests
4. Register in the stack's `kustomization.yaml`:

```yaml
# charts/test-stack/kustomization.yaml (or media-stack/kustomization.yaml)
resources:
  - ./http-echo
  - ./<name>          # ← add this
```

5. Commit + push — Flux auto-syncs within 5 minutes

## Manual Sync

```bash
# Sync a specific stack immediately
flux reconcile kustomization test-stack -n flux-system

# Or without flux CLI:
kubectl annotate kustomization test-stack -n flux-system \
  reconcile.fluxcd.io/requestedAt="$(date +%s)"
```

## Pause / Resume

```bash
# Stop Flux from touching a specific stack
flux suspend kustomization test-stack -n flux-system

# Resume
flux resume kustomization test-stack -n flux-system

# Without flux CLI:
kubectl patch kustomization test-stack -n flux-system \
  --type merge -p '{"spec":{"suspend":true}}'
kubectl patch kustomization test-stack -n flux-system \
  --type merge -p '{"spec":{"suspend":false}}'
```

## Drift Detection

Flux detects manual changes (`kubectl edit`, `kubectl scale`, etc.) and reverts them within 5 minutes.

- `READY: True` — cluster state matches Git
- `READY: False` — drift detected, check with:
  ```bash
  kubectl describe kustomization test-stack -n flux-system
  ```

## Troubleshooting

### "kustomize build failed"
```bash
# Test locally what Flux sees:
kubectl apply -k charts/ --dry-run=server
```

### Stale revision (not picking up new commits)
```bash
# Check Flux can reach GitHub:
kubectl get gitrepository branconet-charts -n flux-system -o yaml | grep -A10 status
```

### "Reconciliation in progress" stuck
```bash
kubectl get events -n flux-system --sort-by='.lastTimestamp' | tail -20
```

### New app not appearing
Did you:
1. Create `charts/<stack>/<app>/kustomization.yaml`?
2. Add it to the stack's `kustomization.yaml` resources (e.g., `charts/test-stack/kustomization.yaml`)?
3. Commit **and push** both changes?

Flux watches the **remote** repo, not local files. Changes only apply after `git push`.

## Bootstrapping a New Cluster

See `clusters/README.md` for the full bootstrap procedure and multi-cluster setup.

Quick bootstrap:
```bash
flux bootstrap github \
  --owner=jtmb \
  --repository=branconet-homelab \
  --branch=k8s-rewrite \
  --path=./k8s-rewrite/clusters/prd \
  --personal
```

## How It Compares to Fleet (Rancher)

| Feature | Fleet | Flux |
|---------|-------|------|
| Repo scan | Auto-discovery (`fleet.yaml`) | Explicit (`kustomization.yaml` per dir) |
| Per-app status | `fleet bundle list` | `flux get kustomizations` |
| Self-healing | Yes | Yes (`prune: true`) |
| Multi-cluster | Cluster groups | Separate bootstrap per cluster |
| Sync interval | Per bundle | Per Kustomization |
| Drift detection | Built-in | Built-in + alerts |
| Dependencies | None (built into Rancher) | Standalone controllers |
