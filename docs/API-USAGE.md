# BORTUS API usage

Development base URL: `http://localhost:4000`. Use the configured TLS ingress in production.

## Authentication

Dashboard APIs require the HttpOnly `botrus_auth_token` cookie, set by login. Writes require the current `write` role from SQLite. JWTs carry identity, not role.

Public API paths are `/api/auth/*`, exact `/api/cluster/info`, `/api/health/live` and `/api/health/ready`. Exact `/api/vars/lookup` bypasses cookie middleware but requires Bearer `BOTRUS_SECRETS_KEY`. The lookup token is independent of user JWTs.

To login without putting credentials in terminal arguments, use a protected, untracked JSON file:

```bash
curl -c /tmp/botrus-cookies http://localhost:4000/api/auth/login \
  -H 'Content-Type: application/json' --data-binary @/protected/login.json
curl -b /tmp/botrus-cookies http://localhost:4000/api/cluster/pods
```

Keep the cookie file protected. Examples below use placeholder names and nonsecret data.

## Auth and users

| Endpoint | Contract |
|---|---|
| POST /api/auth/login | JSON username/password; sets 7-day cookie; returns id/username |
| POST /api/auth/register | JSON username/password; first user gets write, subsequent users readonly |
| POST /api/auth/logout | Clears cookie |
| GET /api/auth/session | authenticated, username, role, hasUsers, registrationOpen |
| GET /api/users | User metadata without passwordHash |
| POST /api/users | Write role; username/password and optional role |
| PATCH /api/users/[id] | Write role; role change or password reset |
| DELETE /api/users/[id] | Write role; delete user |

Registration closes after the first user unless `ALLOW_REGISTRATION=true` or AppSetting `allow_registration` is true. Self-demotion/deletion and removing the last write user are refused. See [permissions](USER-PERMS.md).

## Native Secrets and aliases

| Endpoint | Auth | Contract |
|---|---|---|
| GET /api/secrets?namespace=... | Cookie, either role | `{secrets:[...]}`, object metadata and key names, no values |
| GET /api/secrets?namespace=...&name=...&key=... | Write cookie | UTF-8 value and current resourceVersion |
| POST /api/secrets | Write cookie | JSON namespace/name/key/value, mode create or update; update requires resourceVersion; optional type for creation |
| DELETE /api/secrets | Write cookie | JSON namespace/name/key/resourceVersion; deletes one key and retains empty object |
| GET /api/secret-references | Cookie, either role | Metadata-only explicit aliases |
| POST /api/secret-references | Write cookie | JSON alias/namespace/name/key; cannot remap an existing alias |
| DELETE /api/secret-references?alias=... | Write cookie | Deletes SQLite mapping only, retaining native key and file mapping |

Create refuses existing keys. Updates/deletes preserve unrelated data, type and metadata without retrying conflicts. Namespace must be allowed by `BORTUS_SECRET_NAMESPACES`. Missing version: 428; stale/create collisions or immutable objects: 409; missing key: 404; invalid input: 400; Kubernetes/config/RBAC outage: 503. Non-UTF-8 values cannot be revealed through the text API. Responses are private/no-store.

Send value-bearing requests from the UI or protected files over TLS; never include them in command arguments, Git or logs. See [Secrets engine](SECRETS-ENGINE.md).

### Bearer lookup

`GET /api/vars/lookup?key=<alias>` with `Authorization: Bearer <BOTRUS_SECRETS_KEY>` returns `{key,value}`. Exact explicit aliases resolve native namespace/name/key; nonsecret configuration resolves SQLite. Sensitive legacy DB rows never return values. Invalid token: 401; missing key parameter: 400; absent mapping/key: 404; collision: 409; missing configured token or native outage: 503.

## Configuration, inventory and settings

| Endpoint | Contract |
|---|---|
| GET /api/vars | Nonsecret configuration only |
| POST /api/vars | Write role; create/update configuration by key; mapped legacy sensitive writes target native Secrets with mode/version |
| DELETE /api/vars/[id] | Write role; deletes nonsecret config; legacy sensitive row deletion refused |
| GET /api/vars/sync | Sync status |
| POST /api/vars/sync | Write role; generates nonsecret/alias lookup expressions and inventory for optional external Ansible tree |
| GET /api/nodes | SQLite inventory records |
| POST /api/nodes | Write role; upsert by hostname with name/ipAddress/role |
| DELETE /api/nodes/[id] | Write role; delete inventory record |
| GET /api/settings | Key/value map |
| PATCH /api/settings | Write role; upsert JSON key/value; returns success/key/value |

Nonsecret keys must be valid Ansible identifiers. Legacy sensitive aliases may contain hyphens or path separators; their spelling does not derive a native destination. No DB-to-cluster push remains.

```bash
curl -X PATCH -b /tmp/botrus-cookies http://localhost:4000/api/settings \
  -H 'Content-Type: application/json' \
  -d '{"key":"allow_registration","value":"true"}'
```

## Cluster resources

These routes use kubectl with external operator or in-cluster credentials. Cluster list data uses a 10-second cache. Reads require cookies except the exact public info endpoint; mutations require write role.

| Endpoint | Methods and purpose |
|---|---|
| /api/cluster/info | GET overview |
| /api/cluster/refresh | POST invalidate cache |
| /api/cluster/nodes | GET nodes; POST register a node record |
| /api/cluster/nodes/[hostname] | GET node detail |
| /api/cluster/pods | GET list, optional namespace query |
| /api/cluster/pods/[namespace]/[name] | GET detail |
| /api/cluster/pods/[namespace]/[name]/delete | DELETE pod |
| /api/cluster/pods/[namespace]/[name]/yaml | GET YAML; PUT apply YAML |
| /api/cluster/deployments | GET list |
| /api/cluster/deployments/[namespace]/[name] | GET detail |
| /api/cluster/deployments/[namespace]/[name]/delete | DELETE deployment |
| /api/cluster/deployments/[namespace]/[name]/scale | POST replica count |
| /api/cluster/deployments/[namespace]/[name]/action | POST supported deployment action |
| /api/cluster/deployments/[namespace]/[name]/yaml | GET YAML; PUT apply YAML |
| /api/cluster/services | GET list |
| /api/cluster/services/[namespace]/[name] | GET detail |
| /api/cluster/ingresses | GET list |
| /api/cluster/ingresses/[namespace]/[name] | GET detail |
| /api/cluster/namespaces | GET list |
| /api/cluster/namespaces/[name] | GET detail |
| /api/cluster/namespaces/[name]/delete | DELETE namespace |
| /api/cluster/namespaces/[name]/yaml | GET YAML; PUT apply YAML |
| /api/cluster/volumes | GET PVC list |
| /api/cluster/volumes/[namespace]/[name] | GET PVC detail |
| /api/cluster/volumes/reclaim | GET reclaim policies; PATCH policy |
| /api/cluster/remove | DELETE recorded cluster state |
| /api/cluster/kubectl | POST JSON command; returns output |

The write-role terminal endpoint executes arbitrary shell commands through bash with application-host permissions. It is not restricted to Kubernetes API access. Service/PVC compatibility menus display read-only YAML using their existing detail APIs; no unsupported mutations are offered.

## Optional Ansible runner

| Endpoint | Contract |
|---|---|
| POST /api/deploy/start | Write role; JSON playbook and roles; returns success/jobId |
| GET /api/deploy/start | Active job IDs |
| POST /api/deploy/stop | Write role; cancel job |
| GET /api/deploy/history | Job history |
| DELETE /api/deploy/history | Write role; remove history |
| GET /api/deploy/stream | SSE job output |

Container provisioning returns 501. Local provisioning requires separately supplied Ansible/playbooks and independent bootstrap credentials; this app merge includes no Kubernetes provisioning roles. See [workflow](BOTRUS-WORKFLOW.md).

## Flux

| Endpoint | Contract |
|---|---|
| GET /api/flux/repos | Repository list |
| POST /api/flux/repos | Write role; create GitRepository with name/url/branch/path and optional auth inputs |
| DELETE /api/flux/repos/[id] | Write role; delete with progress tracking |
| POST /api/flux/repos/[id]/sync | Write role; reconcile |
| GET /api/flux/repos/[id]/delete-progress | Deletion progress |
| GET /api/flux/repos/[id]/detail | Repository detail (name used by dashboard) |
| GET /api/flux/kustomizations/[name] | Bundle inventory/conditions |
| GET /api/flux/hierarchy | Repository/Kustomization/HelmRelease/namespace hierarchy |

New private credentials use native Secrets and are never retained in `GitRepo.authData` or argv. Existing credential collisions fail. The application merge does not change any live Flux branch; see [Flux guide](FLUX-GITOPS.md).

## Health

Exact public GET `/api/health/live` reports process liveness. `/api/health/ready` checks signing/lookup configuration, migrated SQLite/aliases and native Secret list access across the allowlist, returning 503 on failure. Neither returns credentials.