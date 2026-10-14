# BORTUS K8s — Workflow Guide

End-to-end workflows for managing a Kubernetes cluster with the BORTUS dashboard.

## Current migration bootstrap

The approved migration uses `ansible-playbook/playbooks/site.yml` on james@192.168.0.4/.5/.6, SSH port 2002. Nonsecret initial settings live in `group_vars/all.yml`; sudo reaches Ansible through the migration runner's stdin. Initial provisioning is independent of BORTUS, and must not regenerate that bootstrap configuration from the application database. The sections below describe the existing dashboard workflow; native Secrets development is owned by the scoped application and native-transport sub-agents and remains an acceptance dependency. The former execution chats are archived. Follow [MIGRATION-OPERATIONS.md](MIGRATION-OPERATIONS.md) and [MIGRATION_STATUS.md](../MIGRATION_STATUS.md) for live migration progress and cutover gates.

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

Use the separate private `jtmb/branconet-charts` repository. Every application has its own `charts/<name>/` package and effective values in `flux/releases/<name>.yaml`. Change those files, validate the effective renders and push to `main`. Successful current-main chart CI promotes the exact tested SHA to `validated`; Flux's existing `branconet-charts` source and `migration-releases` Kustomization apply `./flux/releases`.

Do not deploy the legacy raw `test-stack`/`media-stack` root or restore the retired migration publisher. Native Secret values stay outside Git. Preserve existing PVC identities and wait for the service's data/consumer gates before activation. New BORTUS source also requires a separately qualified immutable image and guarded release; an application source push alone does not change the running image.

For status, inspect the `/flux` dashboard, `kubectl get helmreleases -n flux-system`, and source/applied revisions. Manual reconciliation of the existing owner is an operator mutation, not a CI bypass. See [FLUX-GITOPS.md](FLUX-GITOPS.md) for the current pipeline, commands and historical boundaries.

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
└── charts/                          # FluxCD-managed apps (dual stack)
    ├── kustomization.yaml           # Root: references ./test-stack, ./media-stack
    ├── test-stack/
    │   ├── kustomization.yaml
    │   ├── http-echo/
    │   ├── nginx-hello/
    │   └── whoami/
    └── media-stack/
        ├── kustomization.yaml
        └── plex/
```

## 2026-10-14: remaining five-column sort attempt fails at fixture resource lookup

The [literal A13 failure receipt](../evidence/bortus-a13-five-column-failure-root-20261014.json) retains server1/browser1. Deployments Restarts, Nodes Pods/Age and Namespaces Age complete eight directions with wire/display preconditions and unchanged complete row identity checks. Ingress stops at the six-row API length assertion; the failed body was not separately retained. Source and compiled command inspection identifies a fixture mismatch: it wrote `ingresses.json` while the app requests singular `ingress` and the fake CLI reads `ingress.json`. The whole five-column matrix remains unqualified; a separate source-only fixture correction keeps the browser and all ten expected observations byte-identical. Exact/Linux/Windows posts pass with374 source/39 inputs/5383 compiled/40635 dependency objects current,151 Linux births absent,10 Windows births with no live process and exact CID/name absent. Later reader/query checks pass. A root review-directory mode check failed after UNC creation; the exact reader inadvertently ran before root corrected0755/0644 to0700/0600 ahead of the fresh readers. This metadata error and the failed actor are retained. No application, benchmark, production image or cluster change follows.
