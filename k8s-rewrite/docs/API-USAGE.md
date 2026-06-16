# Botrus K8s — API Usage

All API endpoints are served by the Next.js dev server at `http://localhost:4000`.

## Authentication

The secrets lookup endpoint requires Bearer auth. All other endpoints are unprotected (dashboard use).

**Bearer endpoints:**
- `/api/vars/lookup` — `Authorization: Bearer <BOTRUS_SECRETS_KEY>`

## Variables API

### `GET /api/vars`

List all variables in the database.

```bash
curl http://localhost:4000/api/vars | jq .
```

**Response:**
```json
[
  {
    "id": "cm...",
    "key": "k8s_version",
    "value": "v1.30.0",
    "category": "kubernetes",
    "encrypted": false,
    "createdAt": "2026-06-15T...",
    "updatedAt": "2026-06-15T..."
  }
]
```

### `POST /api/vars`

Create or update a variable.

```bash
curl -X POST http://localhost:4000/api/vars \
  -H "Content-Type: application/json" \
  -d '{
    "key": "my_var",
    "value": "some value",
    "category": "general",
    "encrypted": false
  }'
```

**Response:** `{ "success": true, "variable": { ... } }`

To update an existing variable, include the `id` field:
```json
{ "id": "cm...", "value": "new value" }
```

### `DELETE /api/vars?key=<key>`

Delete a variable by key.

```bash
curl -X DELETE "http://localhost:4000/api/vars?key=my_var"
```

## Secrets Lookup API

### `GET /api/vars/lookup?key=<variable_key>`

**Auth required:** `Authorization: Bearer <BOTRUS_SECRETS_KEY>`

Resolves a single variable at runtime. Used by the Ansible `botrus_secret` lookup plugin.

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

## Cluster API

### `GET /api/cluster/info`

Cluster-level information (node count, K8s version, pod summary).

```bash
curl http://localhost:4000/api/cluster/info | jq .
```

### `GET /api/cluster/nodes`

List all nodes.

```bash
curl http://localhost:4000/api/cluster/nodes | jq .
```

### `POST /api/cluster/nodes`

Register a node.

```bash
curl -X POST http://localhost:4000/api/cluster/nodes \
  -H "Content-Type: application/json" \
  -d '{"name":"U1 Tower","hostname":"u1","ipAddress":"192.168.1.10","role":"master"}'
```

### `GET /api/cluster/nodes/[hostname]`

Get a specific node.

```bash
curl http://localhost:4000/api/cluster/nodes/u1 | jq .
```

### `GET /api/cluster/namespaces`

List all namespaces.

```bash
curl http://localhost:4000/api/cluster/namespaces | jq .
```

### `GET /api/cluster/namespaces/[name]`

Get namespace details.

```bash
curl http://localhost:4000/api/cluster/namespaces/plex | jq .
```

### `GET /api/cluster/pods`

List pods (optionally filtered by `?namespace=`).

```bash
curl "http://localhost:4000/api/cluster/pods?namespace=plex" | jq .
```

### `GET /api/cluster/services`

List services with `?namespace=` filter.

### `GET /api/cluster/ingresses`

List ingresses with `?namespace=` filter.

### `GET /api/cluster/storage`

Storage overview (PVCs, PVs, storage classes).

## YAML Export Endpoints

These endpoints return raw Kubernetes resource YAML as text.

### `GET /api/cluster/namespaces/[name]/yaml`
### `GET /api/cluster/deployments/[namespace]/[name]/yaml`
### `GET /api/cluster/pods/[namespace]/[name]/yaml`

```bash
curl "http://localhost:4000/api/cluster/pods/plex/plex-7d8f9c6b5-x2k4m/yaml"
```

## FluxCD API

### `GET /api/flux/repos`

List Flux GitRepository and Kustomization resources.

### `POST /api/flux/repos`

Add a repository to Flux. Accepts JSON body with `repoUrl`, `branch`, `path`.

```bash
curl -X POST http://localhost:4000/api/flux/repos \
  -H "Content-Type: application/json" \
  -d '{"repoUrl":"https://github.com/user/charts","branch":"main","path":"./"}'
```

## Ansible / Job API

### `POST /api/jobs`

Run an Ansible playbook.

```bash
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
