# Botrus Secrets Engine

The Botrus Secrets Engine is a **zero-disk, API-backed secret management system** built into the Botrus K8s dashboard. No secret value ever touches the filesystem — all values are resolved at runtime over an authenticated HTTP channel.

## Architecture

```
┌──────────────┐     Bearer token      ┌──────────────────┐
│  Ansible     │ ─── GET /api/vars/ ──▶ │  Next.js API     │
│  lookup      │     lookup?key=foo    │  /api/vars/lookup │
│  plugin      │ ◀── {key, value} ──── │                   │
└──────────────┘                       └────────┬─────────┘
                                                 │
                                          Prisma │ SQLite
                                                 │
                                        ┌────────▼─────────┐
                                        │  Variable table   │
                                        │  (encrypted col)  │
                                        └──────────────────┘
```

## Components

### 1. Database (`Variable` table)

Prisma model with an `encrypted` boolean flag:

| Column     | Type    | Notes                         |
| ---------- | ------- | ----------------------------- |
| `key`      | String  | Unique variable name          |
| `value`    | String  | The actual secret/value       |
| `category` | String  | Grouping (ansible, kubernetes, secret, etc.) |
| `encrypted`| Boolean | Marks sensitivity             |

### 2. API Endpoint

- **`GET /api/vars/lookup?key=<variable_key>`**
- **Auth:** `Authorization: Bearer <BOTRUS_SECRETS_KEY>`
- **Returns:** `{ "key": "...", "value": "..." }`
- **Errors:** 401 (bad token), 404 (key not found), 500 (DB error)

Used by the Ansible lookup plugin at playbook runtime. The API lives in `front-end/src/app/api/vars/lookup/route.ts`.

### 3. Ansible Lookup Plugin

`ansible-playbook/lookup_plugins/botrus_secret.py`

Standard Ansible lookup plugin. Usage:

```yaml
# In a playbook or template:
ansible_become_password: "{{ lookup('botrus_secret', 'ansible_become_password') }}"
```

Configuration via environment variables:

| Env var               | Default                  | Purpose              |
| --------------------- | ------------------------ | -------------------- |
| `BOTRUS_SECRETS_KEY`  | *(required)*             | Bearer auth token    |
| `BOTRUS_API_URL`      | `http://localhost:4000`  | Next.js API base URL |

Features:
- In-memory cache per playbook run — no duplicate HTTP calls for the same key
- 10-second HTTP timeout
- Raises `AnsibleLookupError` on any failure
- Never writes to disk

### 4. Variable Sync

`front-end/src/lib/sync-vars.ts` → `syncVarsToYAML()`

Reads all variables from the DB and writes `group_vars/all.yml` with **lookup refs only** — no values:

```yaml
# all.yml (auto-generated, gitignored)
cluster_cidr: "{{ lookup('botrus_secret', 'cluster_cidr') }}"
k8s_version: "{{ lookup('botrus_secret', 'k8s_version') }}"
ansible_become_password: "{{ lookup('botrus_secret', 'ansible_become_password') }}"
```

This file is regenerated on every deploy/sync and is **gitignored**.

### 5. Runtime Wiring

**`ansible.cfg`:**
```ini
lookup_plugins = ./lookup_plugins
```

**`ansible.ts`** spawns Ansible with env vars:
```typescript
env: {
  BOTRUS_SECRETS_KEY: process.env.BOTRUS_SECRETS_KEY || "",
  BOTRUS_API_URL: "http://localhost:4000",
  ANSIBLE_BECOME_PASSWORD: becomePassword,  // sudo, never in argv
}
```

## Security Properties

| Threat                | Mitigation                                      |
| --------------------- | ----------------------------------------------- |
| Secrets on disk       | **Zero** — `all.yml` contains only lookup refs  |
| Secrets in argv       | **Zero** — password flows through stdin/environ |
| Secrets in logs       | Lookup plugin does not log values               |
| Unauthenticated read  | Bearer token required on `/api/vars/lookup`     |
| Replay attacks        | Token is per-session; rotate `BOTRUS_SECRETS_KEY` |

## Seeding the Database

```bash
cd front-end
BECOME_PASSWORD='...' SMB_PASSWORD='...' ./seed-db.sh
```

Seeds all 47 variables (including passwords) into the Prisma SQLite database. See `API-USAGE.md` for the full variable list.

## Using in Playbooks

Any variable stored in the DB can be referenced in Ansible:

```yaml
- name: Install Kubernetes
  hosts: all
  vars:
    k8s_ver: "{{ lookup('botrus_secret', 'k8s_version') }}"
  tasks:
    - name: Install kubelet
      apt:
        name: "kubelet={{ k8s_ver }}"
        state: present
```

## Troubleshooting

**`BOTRUS_SECRETS_KEY environment variable is not set`**
→ Export the token before running Ansible, or ensure `ansible.ts` is spawning the process.

**`Botrus API returned 401`**
→ Token mismatch. Verify `BOTRUS_SECRETS_KEY` matches what the API expects.

**`Cannot reach Botrus API at http://localhost:4000`**
→ Next.js dev server isn't running. Start with `cd front-end && npm run dev`.

**`Variable not found: X`**
→ Variable `X` isn't in the DB. Run `seed-db.sh` or add it via the `/api/vars` endpoint.
