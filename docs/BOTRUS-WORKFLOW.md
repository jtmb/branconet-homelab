# Botrus K8s — Workflow Guide

End-to-end workflows for managing a Kubernetes cluster with the Botrus dashboard.

## Initial Setup

### 1. Start the Dashboard

```bash
cd k8s-rewrite/front-end
npm install
npm run dev
# Dashboard at http://localhost:4000
```

### 2. Seed the Database

```bash
cd k8s-rewrite/front-end
BECOME_PASSWORD='your-sudo-password' \
SMB_PASSWORD='your-smb-password' \
./seed-db.sh
```

This populates all 47 variables and node entries into the Prisma SQLite database. Variables include:
- Kubernetes versions (`k8s_version`, `calico_version`, etc.)
- Cluster networking (`cluster_cidr`, `pod_network_cidr`, etc.)
- Node inventory (`node_u1_ip`, `node_u1_hostname`, etc.)
- Storage config (`storage_class`, `nfs_server_path`, etc.)
- Secrets (`ansible_become_password`, `secret_plex_smb-creds_password`, etc.)

### 3. Configure the Secrets Token

```bash
export BOTRUS_SECRETS_KEY="your-secure-random-token"
```

This token protects the `/api/vars/lookup` endpoint. Both the dashboard server and any Ansible processes need it set.

### 4. Verify Connectivity

Open the dashboard at `http://localhost:4000` and check the **Nodes** page. If nodes show as `pending`, they haven't been provisioned yet.

## Provisioning a Cluster

### Option A: Full Provision (from scratch)

1. Go to **Settings** → verify variables are correct
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

Applications are managed via FluxCD. Each app lives in a Git repository under `charts/<name>/`.

### Adding a New App

1. Create a directory: `charts/my-app/`
2. Add Kubernetes manifests (`deployment.yaml`, `service.yaml`, `ingress.yaml`, etc.)
3. Commit and push to the Git repository
4. Add the repo to Flux:
   ```bash
   curl -X POST http://localhost:4000/api/flux/repos \
     -H "Content-Type: application/json" \
     -d '{"name":"my-app","url":"https://github.com/user/charts","branch":"main","path":"./charts/my-app"}'
   ```
5. Flux polls every 5 minutes; trigger an immediate sync if needed:
   ```bash
   curl -X POST http://localhost:4000/api/flux/repos/<id>/sync
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

All configuration is stored in the Botrus database, not on disk.

### View Variables

Dashboard → **Settings** tab, or:
```bash
curl http://localhost:4000/api/vars | jq .
```

### Update a Variable

Dashboard → **Settings** → edit any field, or:
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

## Managing Secrets (e.g., SMB credentials)

Secrets follow the convention `secret_<namespace>_<name>_<key>`.

Example: Plex SMB credentials:
- `secret_plex_smb-creds_username` = `james`
- `secret_plex_smb-creds_password` = (stored in DB)

These are deployed as Kubernetes Secret objects by the `secrets` Ansible role. FluxCD is configured to **not prune** secrets (annotation `prune: disabled`).

### Creating a New Secret

```bash
curl -X POST http://localhost:4000/api/vars \
  -H "Content-Type: application/json" \
  -d '{"key":"secret_myapp_my-creds_password","value":"...","category":"secret","encrypted":true}'
```

Then re-run the `secrets` Ansible role to deploy it to the cluster.

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

## Environment Variables Reference

| Variable | Required | Purpose |
|----------|----------|---------|
| `BOTRUS_SECRETS_KEY` | Yes | Bearer token for `/api/vars/lookup` |
| `BOTRUS_API_URL` | No | API base URL (default: `http://localhost:4000`) |
| `DATABASE_URL` | Yes | Prisma SQLite path (auto-set by `.env`) |
| `BECOME_PASSWORD` | Seed only | Sudo password for `seed-db.sh` |
| `SMB_PASSWORD` | Seed only | SMB share password for `seed-db.sh` |

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
│   └── seed-db.sh                  # Initial DB population
└── charts/                          # FluxCD-managed apps
    ├── plex/
    ├── home-assistant/
    ├── discord-bots/
    └── ...
```
