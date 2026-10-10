# BORTUS K8s — Workflow Guide

End-to-end workflows for managing a Kubernetes cluster with the BORTUS dashboard.

## Current migration bootstrap

The approved migration uses `ansible-playbook/playbooks/site.yml` on james@192.168.0.4/.5/.6, SSH port 2002. Nonsecret initial settings live in `group_vars/all.yml`; sudo reaches Ansible through the migration runner's stdin. Initial provisioning is independent of BORTUS, and must not regenerate that bootstrap configuration from the application database. The sections below describe the existing dashboard workflow; its native Secrets development is owned by a separate chat and remains an acceptance dependency. Follow [MIGRATION-OPERATIONS.md](MIGRATION-OPERATIONS.md) and [MIGRATION_STATUS.md](../MIGRATION_STATUS.md) for live migration progress and cutover gates.

The revised foundation preserves Docker's runtime, resolver, Gluster and NAS data, installs `containerd-k8s`, enables Secrets encryption at rest and retained LUKS Longhorn volumes, and uses temporary ingress NodePorts 30080/30443. Flux retains source, Kustomize, Helm and notification controllers. Chart source activation waits for individual chart/value validation; runtime configuration generation in the legacy UI is not a prerequisite for this migration.

## Initial Setup

### 1. Start the Dashboard

```bash
cd k8s-rewrite/front-end
npm install
npm run dev
# Dashboard at http://localhost:4000
```

### 2. Initialize metadata/authentication

Run npm run db:deploy; supply DATABASE_URL, stable BOTRUS_JWT_SECRET and BOTRUS_SECRETS_KEY independently. First registered user receives write role. Seed only nonsecret configuration through authenticated APIs; never SQLite passwords.

### 3. Connect native Secrets

Supply operator kubeconfig or service account, namespace allowlist and explicit aliases. Import values externally before consumers. Use /secrets for native CRUD and /configuration for nonsecret config. See [deployment](BORTUS-DEPLOYMENT.md).

### 4. Verify Connectivity

Open the dashboard at `http://localhost:4000` and check the **Nodes** page. If nodes show as `pending`, they haven't been provisioned yet.

## Provisioning a Cluster

### Option A: Full Provision (from scratch)

1. In local operator mode, use **Configuration** for nonsecret variables. Container provisioning is disabled; bootstrap credentials are independent.
2. Go to **Deploy** → select playbook `site.yml`
3. Choose roles to run (or run all):
   - `bootstrap` — SSH key distribution, base packages
   - `network` — iptables, sysctl, kernel modules
   - `kubernetes` — kubeadm init/join, kubelet, kubectl
   - `storage` — Longhorn, NFS, SMB provisioners
   - `ingress` — Traefik ingress controller
   - `gitops` — FluxCD bootstrap
   - `dns` — systemd-resolved configuration
4. Click **Run** — watch live output

### Option B: Incremental (add a role)

Same as above, but select only the role(s) you need. Example: add `storage` to an existing cluster (includes Longhorn).

### Option C: CLI

```bash
cd k8s-rewrite/ansible-playbook

# Full provision
ansible-playbook playbooks/site.yml \
  -i inventory/production.ini \
  -u brajam \
  --private-key ~/.ssh/id_ed25519 \
  --become

# Single role
ansible-playbook playbooks/site.yml --tags kubernetes
```

## Deploying Applications (GitOps)

Applications are managed via FluxCD from the separate private `jtmb/branconet-charts` repository. Each retained application has `charts/<name>/Chart.yaml`, its own values and templates, and `flux/releases/<name>.yaml` for effective release overrides.

The existing `migration-releases` Kustomization uses GitRepository `branconet-charts`, path `./flux/releases`, and prune:false. It owns 33 application HelmReleases plus cert-manager and the preserved foundation. GitHub CI validates main and promotes only successful current-main commits to validated. See [Flux contract](FLUX-GITOPS.md).

### Adding a New App

1. Add `charts/my-app/` with Chart.yaml, values.yaml and Helm templates in the charts repository.
2. Preserve native Secret references and review image, namespaces, release identity, storage and routes.
3. Add the HelmRelease to `flux/releases/` and its resource entry to that composition's kustomization.yaml.
4. Update the reviewed inventory/count validation for an authorized scope change. Excluded games stay excluded.
5. Run local validation and push main; require successful CI and observed Flux/Helm revisions.
6. Flux polls its source each minute; trigger an immediate sync if needed:
   ```bash
   flux reconcile kustomization migration-releases -n flux-system --with-source
   ```

### Checking App Status

- **Dashboard:** `/flux` page shows all repositories and their sync status
- **CLI:** `kubectl get kustomization -n flux-system`
- **Manual sync trigger:**
  ```bash
  kubectl annotate gitrepository my-app -n flux-system \
    reconcile.fluxcd.io/requestedAt="$(date -Iseconds)" --overwrite
  ```

## Managing Variables

Nonsecret configuration lives in SQLite; native Secrets are authoritative for values.

### View Variables

Dashboard → **Configuration** tab, or:
```bash
curl http://localhost:4000/api/vars | jq .
```

### Update a Variable

Dashboard → **Configuration** → edit a nonsecret field, or:
```bash
curl -X POST http://localhost:4000/api/vars \
  -H "Content-Type: application/json" \
  -d '{"id":"<variable-id>","value":"new-value"}'
```

### Sync to Ansible

After changing variables, regenerate the Ansible vars file:
```bash
cd front-end
npx tsx -e "import { syncVarsToYAML } from './src/lib/sync-vars'; syncVarsToYAML()"
```

This writes `ansible-playbook/group_vars/all.yml` with lookup refs — ready for the next playbook run.

## Managing native Secrets

Open /secrets, select namespace/name/key, reveal explicitly as a write user, and edit with current resourceVersion. Create refuses collisions; delete removes one key while preserving unrelated data/type/metadata. Readonly users see keys/metadata without values or mutations. Changes are immediate; no Ansible secrets role/sync is needed.

Register legacy lookup aliases via /api/secret-references or ConfigMap JSON. Never split underscores to derive destinations. Native outage errors without DB fallback. Keep values out of Git, command arguments and reports.

## Cluster Operations

### Node Management

Add a node:
```bash
curl -X POST -b /tmp/botrus-cookies http://localhost:4000/api/nodes \
  -H "Content-Type: application/json" \
  -d '{"name":"New Node","hostname":"u4","ipAddress":"192.168.0.28","role":"worker"}'
```

Then add node variables (`node_u4_hostname`, `node_u4_ip`, etc.) and run the `kubernetes` role with `--tags kubernetes` to join it to the cluster.

### Troubleshooting

See `kubectl-cheatsheet.md` for common diagnostic commands.

Dashboard pages mirror kubectl output:
- **Nodes** → `kubectl get nodes`
- **Namespaces** → `kubectl get ns`
- **Pods** → `kubectl get pods -A`
- **Services** → `kubectl get svc -A`
- **Ingresses** → `kubectl get ingress -A`
- **Storage** → `kubectl get pvc -A`
- **Flux** → `kubectl get gitrepositories,kustomizations -n flux-system`

The **kubectl shell** (terminal icon in the top bar, write-only) provides a live
kubectl prompt right in the dashboard. Type any kubectl command (with or without
the `kubectl` prefix) and see output inline — no SSH needed.

## Environment Variables Reference

| Variable | Required | Purpose |
|----------|----------|---------|
| `BOTRUS_SECRETS_KEY` | Yes | Bearer token for `/api/vars/lookup` |
| `BOTRUS_API_URL` | No | API base URL (default: `http://localhost:4000`) |
| `DATABASE_URL` | Yes | Prisma SQLite path (auto-set by `.env`) |
| `ANSIBLE_BECOME_PASSWORD` | Local provisioning | Independent operator environment |
| `BORTUS_SECRET_NAMESPACES` | Production | Native Secret namespace allowlist |
| `BOTRUS_JWT_SECRET` | Yes | Stable external signing material |
| `BORTUS_SECRET_ALIASES_FILE` | Optional | Metadata-only JSON mapping file |

## Directory Map

```
k8s-rewrite/
├── PLAN.md                          # Architecture plan
├── .gitignore                       # group_vars/all.yml gitignored
├── docs/                            # ← Documentation
│   ├── API-USAGE.md
│   ├── SECRETS-ENGINE.md
│   ├── ANSIBLE-2-API-INTERACTION.md
│   ├── BORTRUS-WORKFLOW.md
│   ├── CONNECTING-TO-A-CLUSTER.md
│   └── kubectl-cheatsheet.md
├── ansible-playbook/
│   ├── ansible.cfg                  # lookup_plugins enabled
│   ├── inventory/production.ini
│   ├── group_vars/all.yml           # Auto-generated, gitignored
│   ├── lookup_plugins/
│   │   └── botrus_secret.py         # Ansible → API bridge
│   ├── playbooks/site.yml
│   └── roles/                       # bootstrap, kubernetes, storage, ingress, etc.
├── front-end/
│   ├── src/app/api/
│   │   ├── vars/lookup/route.ts     # Secrets API endpoint
│   │   ├── vars/route.ts            # CRUD for variables
│   │   ├── cluster/                 # Cluster state endpoints
│   │   └── flux/                    # FluxCD management
│   ├── src/lib/
│   │   ├── sync-vars.ts            # DB → all.yml generator
│   │   ├── ansible.ts              # Ansible playbook spawner
│   │   ├── k8s.ts                  # kubectl/SSH bridge
│   │   ├── encryption.ts           # AES-256-GCM (lib/)
│   │   └── db.ts                   # Prisma client
│   ├── prisma/schema.prisma        # Variable, Node, Job models
│   └── seed-db.sh                  # Retired helper; use authenticated configuration/Secrets UI
└── charts/                          # Retained migration checkpoint; active charts moved
```

The active deployment tree is `jtmb/branconet-charts`: `charts/<name>/`,
`flux/releases/` and `flux/source.yaml`. BORTUS source pushes alone cannot change
the deployed image; use the reviewed image-release procedure in FLUX-GITOPS.md.
