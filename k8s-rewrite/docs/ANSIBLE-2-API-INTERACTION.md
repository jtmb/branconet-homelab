# Ansible ↔ Botrus API Interaction

How Ansible resolves configuration and secrets from the Botrus dashboard at runtime — without any values on disk.

## The Two Paths

### Path 1: Ansible Playbooks (full cluster provisioning)

When you run a playbook from the dashboard (or CLI), Ansible resolves **all** variables from the Botrus API via the `botrus_secret` lookup plugin.

```
┌─────────────────────────────────────────────────────────────┐
│  ansible-playbook site.yml                                   │
│    │                                                         │
│    ├─ group_vars/all.yml                                     │
│    │   cluster_cidr: "{{ lookup('botrus_secret','cluster_cidr') }}"  │
│    │   k8s_version: "{{ lookup('botrus_secret','k8s_version') }}"    │
│    │   ... (47 lookup refs, zero values)                     │
│    │                                                         │
│    ├─ lookup_plugins/botrus_secret.py                        │
│    │   → GET http://localhost:4000/api/vars/lookup?key=X     │
│    │   → Authorization: Bearer <BOTRUS_SECRETS_KEY>          │
│    │   → In-memory cache per run                             │
│    │                                                         │
│    └─ env:                                                   │
│         ANSIBLE_BECOME_PASSWORD  (sudo, never in argv)       │
│         BOTRUS_SECRETS_KEY       (for lookup plugin)         │
│         BOTRUS_API_URL=http://localhost:4000                 │
└─────────────────────────────────────────────────────────────┘
```

### Path 2: kubectl via SSH (dashboard pages)

When the dashboard UI queries cluster state (pods, nodes, etc.), it uses a **direct SSH + kubectl** path:

```
┌─────────────────────────────────────────────┐
│  Dashboard page (e.g. /nodes)                │
│    │                                         │
│    └─ k8s.ts → kubectlJSON("u1", "get nodes")│
│         │                                    │
│         ├─ Local kubeconfig? → kubectl directly
│         │                                    │
│         └─ No kubeconfig? → sshWithSudo()    │
│              │                               │
│              ├─ Reads ansible_become_password from DB
│              ├─ spawn("ssh", ["brajam@u1", "sudo -S kubectl ..."])
│              └─ Pipes password via stdin (fd, never argv)
└─────────────────────────────────────────────┘
```

## The Lookup Plugin in Detail

**File:** `ansible-playbook/lookup_plugins/botrus_secret.py`

### Execution flow per variable lookup:

1. Ansible encounters `{{ lookup('botrus_secret', 'some_key') }}`
2. Plugin checks in-memory cache → returns cached value if found
3. Cache miss → HTTP GET to `http://localhost:4000/api/vars/lookup?key=some_key`
4. Request includes `Authorization: Bearer <token>` header
5. API validates token, queries Prisma DB, returns `{ key, value }`
6. Plugin caches value for this playbook run
7. Returns value to Ansible

### Caching

Cache is a module-level `dict` — lives for the duration of `ansible-playbook` process. Cleared when the process exits. No stale values across playbook runs.

### Error handling

| Scenario | Behavior |
|----------|----------|
| `BOTRUS_SECRETS_KEY` not set | `AnsibleLookupError` — playbook fails immediately |
| API returns 401 | `AnsibleLookupError` with HTTP body |
| API returns 404 | `AnsibleLookupError` — variable not found |
| API unreachable | `AnsibleLookupError` — connection error |
| API returns invalid JSON | `AnsibleLookupError` |
| Network timeout (10s) | `AnsibleLookupError` |

Failures are **fatal** — the playbook stops. This is intentional: Ansible should not proceed with missing configuration.

## How the Dashboard Spawns Ansible

**File:** `front-end/src/lib/ansible.ts` → `runAnsiblePlaybook()`

```typescript
const proc = spawn("ansible-playbook", args, {
  cwd: ANSIBLE_DIR,
  env: {
    ...process.env,
    ANSIBLE_FORCE_COLOR: "1",
    ANSIBLE_BECOME_PASSWORD: becomePassword,   // from DB, via env
    BOTRUS_SECRETS_KEY: process.env.BOTRUS_SECRETS_KEY || "",
    BOTRUS_API_URL: "http://localhost:4000",
  },
});
```

Key points:
- **`ANSIBLE_BECOME_PASSWORD`** — Ansible's native env var for sudo. Never passes through `-e` flag (no argv leak).
- **`BOTRUS_SECRETS_KEY`** — Forwarded from the dashboard's own environment so the lookup plugin can authenticate.
- **`BOTRUS_API_URL`** — Always `localhost:4000` since both Ansible and the dashboard run on the same machine.

## Ansible Configuration

**File:** `ansible-playbook/ansible.cfg`

```ini
[defaults]
inventory = inventory/production.ini
roles_path = ./roles
lookup_plugins = ./lookup_plugins    # ← enables botrus_secret
host_key_checking = False
```

Ansible finds `botrus_secret.py` because `lookup_plugins` points to `./lookup_plugins/` relative to the playbook directory.

## Variable Sync (DB → YAML)

**File:** `front-end/src/lib/sync-vars.ts` → `syncVarsToYAML()`

Triggered on deploy or manually via the API. Reads all 47 variables from the Prisma DB and writes:

```yaml
# group_vars/all.yml — auto-generated, gitignored
cluster_cidr: "{{ lookup('botrus_secret', 'cluster_cidr') }}"
k8s_version: "{{ lookup('botrus_secret', 'k8s_version') }}"
# ... 45 more lookup refs
```

This file contains **zero values** — only `{{ lookup(...) }}` references. At playbook runtime, each reference triggers the lookup plugin → API → DB chain.

### Manually regenerating

```bash
cd front-end
npx tsx -e "
import { syncVarsToYAML } from './src/lib/sync-vars';
syncVarsToYAML().then(console.log);
"
```

## Data Flow Summary

```
User clicks "Deploy" in dashboard
  │
  ├─ 1. syncVarsToYAML() — writes all.yml (lookup refs only)
  │
  ├─ 2. runAnsiblePlaybook("site.yml")
  │     └─ spawn ansible-playbook with env vars
  │
  └─ 3. Ansible reads all.yml
        └─ For each {{ lookup('botrus_secret', 'X') }}:
             ├─ Check in-memory cache
             ├─ Cache miss → GET /api/vars/lookup?key=X
             ├─ API validates Bearer token
             ├─ API queries Prisma Variable table
             └─ Returns { key, value } → cached → used in playbook

At no point does any secret or config value touch the filesystem.
```
