# Botrus K8s — API Usage

All API endpoints are served by the Next.js dev server at `http://localhost:4000`.

## Authentication

Botrus uses **two auth mechanisms** depending on the endpoint:

### Cookie-based (dashboard users)

All dashboard-facing endpoints require the `botrus_auth_token` HttpOnly cookie (set on login). The middleware intercepts every request — public paths pass through, everything else gets 401/redirect.

**Public paths** (no auth required):
- `/api/auth/*`, `/api/cluster/info`, `/_next/*`

**Write-gated endpoints** (cookie + `role="write"` in DB):
- All `POST`/`PATCH`/`DELETE` methods on `/api/nodes`, `/api/users`, `/api/vars`, `/api/settings`, `/api/deploy/*`, `/api/flux/repos/*`, `/api/cluster/*/delete`, `/api/cluster/refresh`

**Read-only endpoints** (cookie required, any role):
- All `GET` methods that aren't public

### Bearer token (Ansible lookup plugin)

- `GET /api/vars/lookup` — `Authorization: Bearer <BOTRUS_SECRETS_KEY>`

This is the only Bearer endpoint. The token is the `BOTRUS_SECRETS_KEY` env var — not a JWT, not a user token.

### Using curl with cookie auth

```bash
# 1. Login to get session cookie
curl -c /tmp/botrus-cookies http://localhost:4000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"your-password"}'

# 2. Use the cookie for subsequent requests
curl -b /tmp/botrus-cookies http://localhost:4000/api/cluster/pods | jq .
```

---

## Auth API

### `POST /api/auth/login`

**Auth:** None (public)

```bash
curl -c /tmp/botrus-cookies http://localhost:4000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"your-password"}'
```

**Response:** `{ "id": "cm...", "username": "admin" }`
Sets `botrus_auth_token` cookie (HttpOnly, 7d expiry).

### `POST /api/auth/register`

**Auth:** None (if registration is open)

```bash
curl http://localhost:4000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username":"newuser","password":"my-password-123"}'
```

**Response (201):** `{ "id": "cm...", "username": "newuser" }`

First user gets `write` role. Subsequent users get `readonly`. Registration locks after first user unless `ALLOW_REGISTRATION=true` or the `allow_registration` AppSetting is `"true"`.

### `POST /api/auth/logout`

Clears the auth cookie.

```bash
curl -X POST -b /tmp/botrus-cookies http://localhost:4000/api/auth/logout
```

### `GET /api/auth/session`

**Auth:** Cookie (returns partial data if unauthenticated)

```bash
curl -b /tmp/botrus-cookies http://localhost:4000/api/auth/session | jq .
```

**Response (authenticated):**
```json
{
  "authenticated": true,
  "username": "admin",
  "role": "write",
  "hasUsers": true,
  "registrationOpen": false
}
```

---

## Cluster API

All cluster endpoints return live kubectl data (local or via SSH). **Read endpoints require auth cookie. Write endpoints require `write` role.**

### `GET /api/cluster/info`

**Auth:** None (public)

Cluster overview — node count, pod summary, K8s version, Longhorn volumes.

```bash
curl http://localhost:4000/api/cluster/info | jq .
```

### `POST /api/cluster/refresh`

**Auth:** Cookie, `write` role

Invalidates the cluster cache (30s TTL) and forces a fresh kubectl query on next read.

```bash
curl -X POST -b /tmp/botrus-cookies http://localhost:4000/api/cluster/refresh
```

### `POST /api/cluster/kubectl`

**Auth:** Cookie, `write` role

Execute any kubectl command. The `kubectl` prefix may be included or omitted — it is stripped automatically. No command filtering is applied; the shell has the same capabilities as local `kubectl` (which can only interact with the Kubernetes API server — no filesystem access outside its kubeconfig).

```bash
curl -X POST http://localhost:4000/api/cluster/kubectl \
  -H "Content-Type: application/json" \
  -b /tmp/botrus-cookies \
  -d '{"command": "get nodes"}'
```

```bash
# Also works with kubectl prefix
curl -X POST http://localhost:4000/api/cluster/kubectl \
  -H "Content-Type: application/json" \
  -b /tmp/botrus-cookies \
  -d '{"command": "kubectl get pods -A"}'
```

### `GET /api/cluster/nodes`

List all Kubernetes nodes (from kubectl).

```bash
curl -b /tmp/botrus-cookies http://localhost:4000/api/cluster/nodes | jq .
```

### `GET /api/cluster/pods`

List pods. Optional `?namespace=` filter.

```bash
curl -b /tmp/botrus-cookies "http://localhost:4000/api/cluster/pods?namespace=kube-system" | jq .
```

### `GET /api/cluster/pods/[namespace]/[name]`

Pod detail.

```bash
curl -b /tmp/botrus-cookies http://localhost:4000/api/cluster/pods/http-echo/http-echo-7d8f9c6b5-x2k4m | jq .
```

### `DELETE /api/cluster/pods/[namespace]/[name]/delete`

**Auth:** Cookie, `write` role

Delete a pod.

```bash
curl -X DELETE -b /tmp/botrus-cookies \
  http://localhost:4000/api/cluster/pods/http-echo/http-echo-7d8f9c6b5-x2k4m/delete
```

### `POST /api/cluster/pods/[namespace]/[name]/shell`

**Auth:** Cookie, `write` role

Opens an interactive shell session (xterm.js). Not used via curl directly — consumed by the dashboard UI.

### `GET /api/cluster/deployments`

List deployments. Optional `?namespace=` filter.

### `GET /api/cluster/deployments/[namespace]/[name]`

Deployment detail.

### `GET /api/cluster/services`

List services. Optional `?namespace=` filter.

### `GET /api/cluster/ingresses`

List ingresses. Optional `?namespace=` filter.

### `GET /api/cluster/namespaces`

List all namespaces.

```bash
curl -b /tmp/botrus-cookies http://localhost:4000/api/cluster/namespaces | jq .
```

### `GET /api/cluster/namespaces/[name]`

Namespace detail.

```bash
curl -b /tmp/botrus-cookies http://localhost:4000/api/cluster/namespaces/http-echo | jq .
```

### `DELETE /api/cluster/namespaces/[name]/delete`

**Auth:** Cookie, `write` role

Delete a namespace (cascading — removes all resources inside).

```bash
curl -X DELETE -b /tmp/botrus-cookies \
  http://localhost:4000/api/cluster/namespaces/http-echo/delete
```

### `GET /api/cluster/volumes`

Storage overview — PVCs, PVs, storage classes.

### `DELETE /api/cluster/remove`

**Auth:** Cookie, `write` role

Remove a resource from the cluster.

---

## Node API (DB-level)

These endpoints manage the `Node` table in the Botrus database — NOT the live Kubernetes nodes. Used for Ansible inventory tracking.

### `GET /api/nodes`

List all registered nodes from DB.

```bash
curl -b /tmp/botrus-cookies http://localhost:4000/api/nodes | jq .
```

### `POST /api/nodes`

**Auth:** Cookie, `write` role

Register a node in the DB.

```bash
curl -X POST -b /tmp/botrus-cookies http://localhost:4000/api/nodes \
  -H "Content-Type: application/json" \
  -d '{"name":"U1 Tower","hostname":"u1","ipAddress":"192.168.0.25","role":"master"}'
```

### `GET /api/nodes/[id]`

Get a specific node by DB id.

### `PATCH /api/nodes/[id]`

**Auth:** Cookie, `write` role

Update node fields.

### `DELETE /api/nodes/[id]`

**Auth:** Cookie, `write` role`

Delete a node from DB.

---

## Variables API (Secrets Engine)

### `GET /api/vars`

List all variables in the database. Values are included in the response.

```bash
curl -b /tmp/botrus-cookies http://localhost:4000/api/vars | jq .
```

**Response:**
```json
[
  {
    "id": "cm...",
    "key": "k8s_version",
    "value": "v1.30.0",
    "category": "kubernetes",
    "encrypted": true,
    "createdAt": "2026-06-15T...",
    "updatedAt": "2026-06-15T..."
  }
]
```

### `POST /api/vars`

**Auth:** Cookie, `write` role

Create or update a variable.

```bash
curl -X POST -b /tmp/botrus-cookies http://localhost:4000/api/vars \
  -H "Content-Type: application/json" \
  -d '{"key":"my_var","value":"some value","category":"general","encrypted":true}'
```

To update an existing variable, include the `id` field:
```json
{ "id": "cm...", "value": "new value" }
```

### `GET /api/vars/[id]`

Get a single variable.

### `PATCH /api/vars/[id]`

**Auth:** Cookie, `write` role

Update a variable's value or category.

### `DELETE /api/vars/[id]`

**Auth:** Cookie, `write` role

Delete a variable.

---

## Secrets Lookup API

### `GET /api/vars/lookup?key=<variable_key>`

**Auth:** `Authorization: Bearer <BOTRUS_SECRETS_KEY>` (NOT cookie)

Resolves a single variable at runtime. Used by the Ansible `botrus_secret` lookup plugin. Values never touch the filesystem.

```bash
curl -H "Authorization: Bearer $BOTRUS_SECRETS_KEY" \
  "http://localhost:4000/api/vars/lookup?key=k8s_version"
```

**Response:**
```json
{ "key": "k8s_version", "value": "v1.30.0" }
```

**Error responses:**
| Status | Body | Meaning |
|--------|------|---------|
| 400 | `{"error":"Missing ?key= parameter"}` | No key param |
| 401 | `{"error":"Missing or invalid Authorization header"}` | Bad/missing token |
| 401 | `{"error":"Invalid token"}` | Token mismatch |
| 404 | `{"error":"Variable not found: X"}` | Key doesn't exist |
| 500 | `{"error":"Server not configured — BOTRUS_SECRETS_KEY not set"}` | Env var missing |

### `POST /api/vars/sync`

**Auth:** Cookie, `write` role

Regenerates `group_vars/all.yml` (lookup refs only) and rebuilds the Ansible inventory file from node data.

```bash
curl -X POST -b /tmp/botrus-cookies http://localhost:4000/api/vars/sync
```

**Response:**
```json
{
  "success": true,
  "vars": { "synced": 47, "file": "../ansible-playbook/group_vars/all.yml" },
  "nodes": { "synced": 3 },
  "inventory": { "synced": 3, "file": "../ansible-playbook/inventory/production.ini" }
}
```

---

## Deploy API (Ansible)

### `POST /api/deploy/start`

**Auth:** Cookie, `write` role

Run an Ansible playbook.

```bash
curl -X POST -b /tmp/botrus-cookies http://localhost:4000/api/deploy/start \
  -H "Content-Type: application/json" \
  -d '{"playbook":"site.yml","roles":["kubernetes","storage"]}'
```

### `POST /api/deploy/stop`

**Auth:** Cookie, `write` role

Cancel a running playbook.

### `GET /api/deploy/history`

List past job runs.

### `GET /api/deploy/stream`

SSE stream for live Ansible output. Consumed by the dashboard UI, not curl.

---

## Flux API

### `GET /api/flux/repos`

List Flux GitRepositories and Kustomizations.

```bash
curl -b /tmp/botrus-cookies http://localhost:4000/api/flux/repos | jq .
```

### `GET /api/flux/hierarchy`

Get Fleet-style hierarchical tree of all Flux resources. Each GitRepository is a root node with associated Kustomizations and HelmReleases as children. Namespace nodes appear as leaf children of Kustomizations — parsed from the Kustomization's `status.inventory.entries` to show which namespaces are managed by that Kustomization.

**Auth:** Cookie (any role)

```bash
curl -b /tmp/botrus-cookies http://localhost:4000/api/flux/hierarchy | jq .
```

**Response:**

```json
{
  "trees": [
    {
      "id": "cm...",
      "name": "branconet-charts",
      "kind": "GitRepository",
      "url": "https://github.com/jtmb/branconet-homelab.git",
      "branch": "k8s-rewrite",
      "path": "./k8s-rewrite/charts",
      "namespace": "flux-system",
      "ready": true,
      "status": "Ready",
      "lastSync": "2026-06-16T17:34:07Z",
      "revision": "fb02389c",
      "authMethod": "none",
      "children": [
        {
          "id": "ks-...",
          "name": "media-stack",
          "kind": "Kustomization",
          "path": "./k8s-rewrite/charts/media-stack/",
          "namespace": "flux-system",
          "ready": true,
          "status": "Ready",
          "lastSync": null,
          "revision": "fb02389c",
          "children": [
            {
              "id": "ns-...",
              "name": "plex",
              "kind": "Namespace",
              "namespace": "plex",
              "ready": true,
              "status": "Ready",
              "children": []
            }
          ]
        },
        {
          "id": "ks-...",
          "name": "test-stack",
          "kind": "Kustomization",
          "path": "./k8s-rewrite/charts/test-stack/",
          "namespace": "flux-system",
          "ready": true,
          "status": "Ready",
          "lastSync": null,
          "revision": "fb02389c",
          "children": [
            {
              "id": "ns-...",
              "name": "http-echo",
              "kind": "Namespace",
              "namespace": "http-echo",
              "ready": true,
              "status": "Ready",
              "children": []
            },
            {
              "id": "ns-...",
              "name": "nginx-hello",
              "kind": "Namespace",
              "namespace": "nginx-hello",
              "ready": true,
              "status": "Ready",
              "children": []
            },
            {
              "id": "ns-...",
              "name": "whoami",
              "kind": "Namespace",
              "namespace": "whoami",
              "ready": true,
              "status": "Ready",
              "children": []
            }
          ]
        }
      ]
    }
  ]
}
```

**Node kinds:** `GitRepository`, `Kustomization`, `HelmRelease`, `Namespace`

**Orphan filter:** GitRepositories with no linked Kustomizations are excluded from the tree. Suspended GitRepositories are also filtered out.
**Tree depth:** Arbitrary (Kustomizations whose sourceRef matches another Kustomization or GitRepository are nested as children)

### `POST /api/flux/repos`

**Auth:** Cookie, `write` role

Add a Flux GitRepository.

```bash
curl -X POST -b /tmp/botrus-cookies http://localhost:4000/api/flux/repos \
  -H "Content-Type: application/json" \
  -d '{"name":"my-app","url":"https://github.com/user/charts","branch":"main","path":"./apps/my-app"}'
```

### `GET /api/flux/repos/[id]`

Get a specific Flux repo.

### `PATCH /api/flux/repos/[id]`

**Auth:** Cookie, `write` role

Update a Flux repo.

### `DELETE /api/flux/repos/[id]`

**Auth:** Cookie, `write` role

Delete a Flux repo (with progress tracking).

### `POST /api/flux/repos/[id]/sync`

**Auth:** Cookie, `write` role

Trigger manual reconciliation.

```bash
curl -X POST -b /tmp/botrus-cookies \
  http://localhost:4000/api/flux/repos/cm.../sync
```

---

## Users API

### `GET /api/users`

List all users (no passwordHash).

```bash
curl -b /tmp/botrus-cookies http://localhost:4000/api/users | jq .
```

### `POST /api/users`

**Auth:** Cookie, `write` role

Create a user. Role defaults to `readonly`.

```bash
curl -X POST -b /tmp/botrus-cookies http://localhost:4000/api/users \
  -H "Content-Type: application/json" \
  -d '{"username":"devops","password":"secure-password","role":"write"}'
```

### `PATCH /api/users/[id]`

**Auth:** Cookie, `write` role

Update user role or reset password. Cannot change own role. Cannot demote last write user.

```bash
curl -X PATCH -b /tmp/botrus-cookies http://localhost:4000/api/users/cm... \
  -H "Content-Type: application/json" \
  -d '{"role":"write"}'
```

### `DELETE /api/users/[id]`

**Auth:** Cookie, `write` role

Delete a user. Cannot delete self. Cannot delete last write user.

---

## Settings API

### `GET /api/settings`

List all AppSettings.

### `POST /api/settings`

**Auth:** Cookie, `write` role

Create a setting.

```bash
curl -X POST -b /tmp/botrus-cookies http://localhost:4000/api/settings \
  -H "Content-Type: application/json" \
  -d '{"key":"allow_registration","value":"true"}'
```

### `PATCH /api/settings`

**Auth:** Cookie, `write` role

Update an existing setting. Include `key` and `value`.
curl -X POST http://localhost:4000/api/jobs \
  -H "Content-Type: application/json" \
  -d '{"playbook":"site.yml","roles":["kubernetes","longhorn"]}'
```

### `GET /api/jobs`

List job history.

### `GET /api/jobs/[id]`

Get job status and output.

## Variable Reference (all 47 keys)

| Key | Category | Purpose |
|-----|----------|---------|
| `ansible_become_password` | ansible | Sudo password for Ansible |
| `ansible_ssh_private_key_file` | ansible | Path to SSH key |
| `dns_servers` | dns | System DNS resolvers |
| `github_token` | general | GitHub PAT for Flux/GitOps |
| `helm_version` | helm | Helm binary version |
| `calico_version` | kubernetes | Calico CNI version |
| `cluster_name` | kubernetes | K8s cluster name |
| `coredns_replicas` | kubernetes | CoreDNS replica count |
| `crictl_version` | kubernetes | crictl version |
| `k8s_version` | kubernetes | Kubernetes version |
| `kubeconfig_path` | kubernetes | Kubeconfig path on nodes |
| `node_u1_hostname` | kubernetes | U1 actual hostname |
| `node_u1_ip` | kubernetes | U1 IP address |
| `node_u1_name` | kubernetes | U1 display name |
| `node_u1_role` | kubernetes | U1 role (master/worker) |
| `node_u2_hostname` | kubernetes | U2 actual hostname |
| `node_u2_ip` | kubernetes | U2 IP address |
| `node_u2_name` | kubernetes | U2 display name |
| `node_u2_role` | kubernetes | U2 role |
| `node_u3_hostname` | kubernetes | U3 actual hostname |
| `node_u3_ip` | kubernetes | U3 IP address |
| `node_u3_name` | kubernetes | U3 display name |
| `node_u3_role` | kubernetes | U3 role |
| `longhorn_default_storage_class` | longhorn | Default SC for Longhorn |
| `longhorn_replicas` | longhorn | Volume replica count |
| `longhorn_version` | longhorn | Longhorn version |
| `cluster_cidr` | networking | Cluster CIDR range |
| `cluster_domain` | networking | Cluster DNS domain |
| `pod_network_cidr` | networking | Pod network CIDR |
| `service_cidr` | networking | Service CIDR range |
| `nfs_enabled` | nfs | Enable NFS provisioner |
| `nfs_provisioner_version` | nfs | NFS provisioner version |
| `nfs_server_path` | nfs | NFS export path |
| `nfs_storage_class` | nfs | NFS storage class name |
| `containerd_cgroup_driver` | runtime | systemd cgroup driver |
| `containerd_log_level` | runtime | containerd log level |
| `samba_enabled` | samba | Enable SMB provisioner |
| `samba_share_name` | samba | SMB share name |
| `samba_share_path` | samba | SMB server path |
| `smb_storage_class` | samba | SMB storage class name |
| `secret_plex_smb-creds_password` | secret | Plex SMB password |
| `secret_plex_smb-creds_username` | secret | Plex SMB username |
| `default_storage_size` | storage | Default PVC size |
| `storage_class` | storage | Default storage class |
| `traefik_accesslog` | traefik | Enable access logs |
| `traefik_log_level` | traefik | Traefik log level |
| `traefik_version` | traefik | Traefik version |
