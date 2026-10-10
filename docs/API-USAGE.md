# BORTUS API usage

Development base URL: `http://localhost:4000`. Use the configured TLS ingress in production.

## Authentication

Dashboard APIs require the HttpOnly `botrus_auth_token` cookie, set by login. Infrastructure, peer identity, configuration and flat Secret value operations require fresh write role plus engineAdmin. Scoped KV actions require fresh write role and deny-aware path policy. JWTs carry identity, not role.

Public API paths are `/api/auth/*`, exact `/api/cluster/info`, `/api/health/live` and `/api/health/ready`. Exact `/api/vars/lookup` bypasses cookie middleware but requires Bearer `BOTRUS_SECRETS_KEY`. The lookup token is independent of user JWTs. Node middleware checks current account existence/sessionVersion for protected reads/pages; deleted accounts and password-reset cookies are rejected. Native Secret handlers and write gates additionally check the current role. A middleware DB outage returns a fixed 503. See [implementation ledger](BORTUS-IMPLEMENTATION.md).

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
| GET /api/auth/session | authenticated, username, role, effective engineAdmin, hasUsers, registrationOpen, runtime capabilities (provisioning/operatorShell/podExec) |
| GET /api/users | User metadata without passwordHash |
| POST /api/users | Effective engine administration; username/password and optional role |
| PATCH /api/users/[id] | Engine administration for peer role/password/engineAdmin changes; scoped write users may change only their own password |
| DELETE /api/users/[id] | Effective engine administration; delete user |

Registration closes after the first user unless `ALLOW_REGISTRATION=true` or AppSetting `allow_registration` is true. Registration/account changes serialize the final check and mutation in SQLite; actor/session/role are rechecked inside the transaction. Self-role changes/deletion and removal of the last writer are refused. Password-only self-reset is allowed for write users and revokes their prior cookies. Duplicate usernames return 409; retryable account contention may return 503. See [permissions](USER-PERMS.md).

## Native Secrets and aliases

| Endpoint | Auth | Contract |
|---|---|---|
| GET /api/secrets?namespace=... | Cookie, either role | `{secrets:[...]}`, object metadata and key names, no values |
| GET /api/secrets?namespace=...&name=...&key=... | Write + engineAdmin cookie | UTF-8 value and current resourceVersion |
| POST /api/secrets | Write + engineAdmin cookie | JSON namespace/name/key/value, mode create or update; update requires resourceVersion; optional type for creation |
| DELETE /api/secrets | Write + engineAdmin cookie | JSON namespace/name/key/resourceVersion; deletes one key and retains empty object |
| GET /api/secret-references | Cookie, either role | Metadata-only explicit aliases |
| POST /api/secret-references | Write + engineAdmin cookie | JSON alias/namespace/name/key; cannot remap an existing alias |
| DELETE /api/secret-references?alias=... | Write + engineAdmin cookie | Deletes SQLite mapping only, retaining native key and file mapping |

Create refuses existing keys. Updates/deletes preserve unrelated data, type and metadata without retrying conflicts. Namespace must be allowed by `BORTUS_SECRET_NAMESPACES`. Missing version: 428; stale/create collisions or immutable objects: 409; missing key: 404; invalid input: 400; Kubernetes/config/RBAC outage: 503. Non-UTF-8 values cannot be revealed through the text API. Responses are private/no-store.

Send value-bearing requests from the UI or protected files over TLS; never include them in command arguments, Git or logs. See [Secrets engine](SECRETS-ENGINE.md).

### KV metadata foundation (local branch, local checks passed)

`GET/POST /api/kv/mounts`, `PATCH/DELETE /api/kv/mounts/[id]`, `GET/POST /api/kv/paths`, `GET/PATCH /api/kv/paths/[id]`, `GET/POST /api/kv/policies`, `PATCH/DELETE /api/kv/policies/[id]`, `GET/POST /api/kv/identities` and `DELETE /api/kv/identities/[id]` are implemented metadata endpoints. Cursor pages return `{items,nextCursor}` with at most 100 entries. Mount/policy administration requires effective engineAdmin; path registration requires create policy and write role, registers metadata intent only, and performs no native mutation. Registered namespace scopes remain subsets of the allowlist and exclude history. Active key ownership is unique; disjoint groups may share an object. Path PATCH changes retention only; target/mapping moves are not accepted. Metadata changes require revision (428 missing, 409 stale). All responses are private/no-store; JSON bodies are bounded to 512 KiB and validated strictly.

Identity issue requires the owner or an effective administrator, explicit mount/prefix/actions and a maximum 30-day expiry. POST returns a credential once; list responses exclude credentials/hashes. Revocation, owner deletion/reset/demotion, expiry and owner-policy intersection are checked before every authorized operation. The automation handler, value/history operations, adoption and KV UI remain pending; issuance does not make those future endpoints available. See [KV contract](BORTUS-KV-DESIGN.md).

The historical write-role endpoint tables are narrowed by the KV trust boundary: infrastructure/Flux/YAML/logs/provisioning output, app/alias/inventory mutations and flat Secret values require a fresh write role **and engineAdmin**. Peer identity mutations likewise require effective administration; a scoped writer may PATCH only their own password. Cluster JSON omits arbitrary annotations/managedFields, workload env/commands/args, Secret data fields and condition messages; raw YAML/log output requires administration. Responses label `privateFieldsOmitted:true`. Readonly/scoped writers retain ordinary operational metadata views. The shared UI reflects this boundary. Full native KV qualification and external guards remain pending.

### Bearer lookup

`GET /api/vars/lookup?key=<alias>` with `Authorization: Bearer <BOTRUS_SECRETS_KEY>` returns `{key,value}`. Exact explicit aliases resolve native namespace/name/key; nonsecret configuration resolves SQLite. Sensitive legacy DB rows never return values. Invalid token: 401; missing key parameter: 400; absent mapping/key: 404; collision: 409; missing configured token or native outage: 503.

## Configuration, inventory and settings

| Endpoint | Contract |
|---|---|
| GET /api/vars | Nonsecret configuration only |
| POST /api/vars | Write + engineAdmin; create/update configuration by key; mapped legacy sensitive writes target native Secrets with mode/version |
| DELETE /api/vars/[id] | Write + engineAdmin; deletes nonsecret config; legacy sensitive row deletion refused |
| GET /api/vars/sync | Sync status |
| POST /api/vars/sync | Write + engineAdmin; generates nonsecret/alias lookup expressions and inventory for optional external Ansible tree |
| GET /api/nodes | SQLite inventory records |
| POST /api/nodes | Write + engineAdmin; upsert by hostname with name/ipAddress/role |
| DELETE /api/nodes/[id] | Write + engineAdmin; delete inventory record |
| GET /api/settings | Key/value map |
| PATCH /api/settings | Write + engineAdmin; upsert JSON key/value; returns success/key/value |

Administration screens check response status before presenting success or refetching metadata. User/settings/configuration reads share bounded lifecycle queries; failed reads show unavailable/Retry and may label a retained prior snapshot. User/configuration saves validate changed input, allow one request at a time, time out after 20 seconds and abort on unmount. No mutation retries automatically after an ambiguous result. Configuration editing sends the existing ID and key; blank nonsecret values are valid. Settings' registration switch shows the persisted app setting separately from effective registration status. PV policy changes use the existing reclaim endpoint one volume at a time with exact-name confirmation, and treat a 207 partial failure as failure. The unused default-PV fake Save is removed.

Nonsecret keys must be valid Ansible identifiers. Legacy sensitive aliases may contain hyphens or path separators; their spelling does not derive a native destination. No DB-to-cluster push remains.

```bash
curl -X PATCH -b /tmp/botrus-cookies http://localhost:4000/api/settings \
  -H 'Content-Type: application/json' \
  -d '{"key":"allow_registration","value":"true"}'
```

## Cluster resources

Live node CPU uses Kubernetes quantities (including millicores); memory is reported in GiB from its actual suffix. Missing capacity remains null. Live IP, role and capacity come from native node data, while the optional display name may come from inventory. Live status never falls back to inventory status or silently rounds a small nonzero capacity to zero.

Node inventory POST validates DNS hostnames, IPv4/IPv6 addresses and worker/master/control-plane roles, then upserts by hostname. PUT /api/nodes/[id] updates the exact existing inventory record (including hostname changes), with 404 for absent records and 409 for duplicate hostname. DELETE uses the same fixed failure handling. These fresh-write mutations affect inventory only, not Kubernetes membership or provisioning.

A detail absent from a stale snapshot returns 503 rather than claiming current absence; a successful current empty list can establish 404. Refresh reports cache invalidation only and lets the requesting screen refetch its own resources, avoiding an unrelated whole-cluster prefetch. Diagnostic counters are process-local and reset with the app.

These routes use kubectl with external operator or in-cluster credentials. The resource cache keeps a separate 10-second snapshot per resource, coalesces concurrent reads and retains a labelled stale snapshot for up to 120 seconds on failure. Failed resources back off from 1 to 30 seconds; a confirmed missing optional Longhorn API backs off for 5 minutes. Invalid or over-10000-item lists fail explicitly. Canonical list/detail UI labels unavailable and stale snapshots; legacy callers remain in the acceptance ledger. Reads require cookies except the exact public info endpoint; mutations require write plus engineAdmin.

Cluster list/detail/overview responses add `availability:{state,resources}`. Each requested resource includes healthy/empty/stale/unavailable/unsupported state, sample time, stale age, retry delay, duration and fixed error. Unavailable primary resources return 503 with availability; unavailable secondary fields are null and overall state is partial. True successful empty lists remain arrays. Retained snapshots return labelled stale data and a Warning header. Responses use no-store. Nodes return live nodes and a separate `inventory` array; inventory rows no longer masquerade as live status.

| Endpoint | Methods and purpose |
|---|---|
| /api/cluster/info | GET overview |
| /api/cluster/refresh | POST invalidate cache |
| /api/cluster/diagnostics | GET write-role cache timing/attempt/failure/item-count and process-pool metadata; no resource values |
| /api/cluster/nodes | GET nodes; POST register a node record |
| /api/cluster/nodes/[hostname] | GET node detail |
| /api/cluster/pods | GET list; type=all/app/system, namespace and labelSelector filters |
| /api/cluster/pods/[namespace]/[name] | GET detail |
| /api/cluster/pods/[namespace]/[name]/delete | DELETE pod |
| /api/cluster/pods/[namespace]/[name]/yaml | GET YAML; PUT versioned replacement |
| /api/cluster/pods/[namespace]/[name]/logs | GET bounded logs; tail, sinceSeconds, container, previous |
| /api/cluster/pods/[namespace]/[name]/exec | POST write-role command in selected pod/container via structured argv |
| /api/cluster/deployments | GET list |
| /api/cluster/deployments/[namespace]/[name] | GET detail |
| /api/cluster/deployments/[namespace]/[name]/delete | DELETE deployment |
| /api/cluster/deployments/[namespace]/[name]/scale | POST replica count |
| /api/cluster/deployments/[namespace]/[name]/action | POST supported deployment action |
| /api/cluster/deployments/[namespace]/[name]/yaml | GET YAML; PUT versioned replacement |
| /api/cluster/services | GET list |
| /api/cluster/services/[namespace]/[name] | GET detail |
| /api/cluster/services/[namespace]/[name]/yaml | GET actual YAML, read-only |
| /api/cluster/ingresses | GET list |
| /api/cluster/ingresses/[namespace]/[name] | GET detail |
| /api/cluster/ingresses/[namespace]/[name]/yaml | GET YAML; PUT scoped versioned replacement |
| /api/cluster/ingresses/[namespace]/[name]/delete | DELETE write-role ingress |
| /api/cluster/namespaces | GET list |
| /api/cluster/namespaces/[name] | GET detail |
| /api/cluster/namespaces/[name]/delete | DELETE namespace |
| /api/cluster/namespaces/[name]/yaml | GET YAML; PUT versioned replacement |
| /api/cluster/volumes | GET PV + optional Longhorn list; kind=pvc selects actual claims; type=all/local/nfs/samba/longhorn |
| /api/cluster/volumes/[namespace]/[name] | GET PVC detail |
| /api/cluster/volumes/[namespace]/[name]/yaml | GET actual PVC YAML, read-only |
| /api/cluster/volumes/reclaim | GET reclaim policies; PATCH policy |
| /api/cluster/remove | DELETE recorded cluster state |
| /api/cluster/kubectl | POST JSON command; returns output |

The shared capability matrix defines YAML read for all seven kinds, edit/delete only for supported kinds, logs for pods and explicit node/deployment actions. All declared API handlers exist. YAML edit accepts one exact kind/API-version/namespace/name object within 256 KiB, requires resourceVersion (428 if missing), uses replace with CAS, and invalidates cache after success. Conflict is fixed 409; invalid Kubernetes request is fixed 400. Native Secret YAML is never accepted here. Canonical resource UI wiring passed local browser checks; real CLI/RBAC acceptance remains pending; check the implementation ledger.

Node YAML is GET /api/cluster/nodes/[hostname]/yaml. POST /api/cluster/nodes/[hostname]/action supports cordon/uncordon/drain with fresh write plus engineAdmin; drain requires confirmName exactly matching hostname, respects PDB/unmanaged/local-data refusals and has a 20-second Kubernetes timeout. No force or emptyDir deletion flag is used. Failed drain may have partial effects; cache is invalidated even on failure and the operator must inspect current state. Logs default to 100 lines, permit 1–1000, cap output at 256 KiB and never follow indefinitely. Pod exec sends a script as one sh -lc argument inside the selected pod; it never concatenates that script into a host shell command.

The write-role operator terminal endpoint executes arbitrary shell commands through bash with application-host permissions when its runtime capability is enabled. Pod execution uses its separate namespaced endpoint, so selected pod commands do not run in a host shell.

Auth session responses now include capabilities:{provisioning,operatorShell,podExec}. These describe implemented runtime gates, not a successful live RBAC probe. Operator shell is disabled on Windows and when BORTUS_DISABLE_OPERATOR_SHELL=true; pod exec is disabled when BORTUS_DISABLE_POD_EXEC=true. The corresponding handlers enforce these gates with 501. Provisioning retains its container/in-cluster disable behavior. YAML reads also cap output at 256 KiB (413 if exceeded); logs enforce their limit after CLI output. Fresh canonical UI uses these runtime flags; remaining legacy callers are tracked under A12.

The wrapper accepts structured argv and throws fixed errors instead of returning failed-command stdout/stderr as success. Resource names and namespaces reject whitespace, flags, separators and invalid DNS forms before CLI invocation. Scale accepts integer replicas from 0 through 10000. Mutation/YAML route errors are mapped to fixed 400/403/404/502/503/504 responses; acceptance is tracked under A04/A05. JSON reads now throw on failed commands/invalid JSON; cluster route availability conversion is in progress under A06. Historical command splitting/false-success evidence remains in the audit.

All structured kubectl operations share a four-process pool with at most 64 waiting commands, a two-MiB output bound, and a deadline including queue time. Full queues return fixed 503; timeout returns fixed 504. Secret operations use their separate verified native API transport.

Flux handler exceptions also use this fixed error mapper. Cascade progress identifies the failed step and stops cleanup instead of overwriting a failure with a done status.

PV reclaim PATCH validates 1–100 named volumes and policies before any command. Per-volume command failures produce `success:false` and fixed errors; a mixed/failed batch returns 207. Repository creation is a multi-request operation: a failed apply may leave metadata/earlier resources for explicit recovery. Failed cascade deletion retains its DB record.

Pod classification uses explicit branconet.io/type=app/system, otherwise the infrastructure namespace set in pod-query.ts; selectors support =/==/!=, in/notin and existence/!existence. Invalid type/namespace/selectors return 400 before loading resources. Deployment list/detail uses Pod → ReplicaSet → Deployment controller UID ownership, desired spec replicas and observed generation, including scaled-down state and null restarts/pods when ownership sources are unavailable. Regular/init-container restarts are counted. Node pod counts become null when pod data is unavailable. See [Kubernetes ownership](https://kubernetes.io/docs/concepts/overview/working-with-objects/owners-dependents/).

POST /api/cluster/nodes now requires fresh write plus engineAdmin, matching other inventory mutations. It creates an inventory record, not a live Kubernetes node.

## Optional Ansible runner

Operator shell scripts are limited to 16 KiB and reject NUL bytes. Pod exec uses its exact namespaced endpoint and a single script argument; the browser never routes a selected pod command through the application-host shell. Both are one-shot command runners with bounded output/time, not interactive PTYs. Client abort does not establish that a command's server-side effects were cancelled.

Storage's default list contains persistent volumes and optional Longhorn volumes. It does not use PV names as PVC identities. The explicit kind=pvc view links exact namespace/claim names to PVC details/YAML. Invalid kind/type filters return 400 before CLI execution. List UI renders at most 100 rows per page with typed numeric/quantity/date sorting; API's bounded snapshot limit remains unchanged.

| Endpoint | Contract |
|---|---|
| POST /api/deploy/start | Write + engineAdmin; JSON playbook and roles; returns success/jobId |
| GET /api/deploy/start | Active job IDs |
| POST /api/deploy/stop | Write + engineAdmin; 202 cancellation requested for a running job owned by this process; 409 for already-complete/unowned jobs; status is determined by the runner |
| GET /api/deploy/history | Latest 50 job metadata rows, without output; administrator-only explicit ?jobId=...&tail=1..65536 returns bounded output/cursor/truncated |
| DELETE /api/deploy/history | Write + engineAdmin; remove completed history only; running job 409, missing job 404 |
| GET /api/deploy/stream | Write + engineAdmin; jobId plus cursor/Last-Event-ID; Unicode-code-point offsets, 4096-character chunks, 32-KiB frame ceiling, explicit completion/error/reset |

Job output streams read bounded SQLite substrings under consumer backpressure, recheck current effective administration/account/session on every poll, and poll at most once per completed 500-ms cycle. The full captured field is not returned to the Node process for polling. Completion, request abort, reader cancellation, missing jobs, authorization failure, DB failure and a 30-minute lifetime close the stream and clear timers. Completed startup never starts a polling interval. Output history is fetched explicitly, never as part of the shared metadata list. Local timer/HTTP/browser and two-MiB Unicode slice evidence is recorded under A18; real runner/image performance remains external.

Container provisioning returns 501. Local provisioning requires separately supplied Ansible/playbooks and independent bootstrap credentials; this app merge includes no Kubernetes provisioning roles. The UI uses the current session/runtime capability and shows independent-operator guidance when provisioning is disabled. See [workflow](BOTRUS-WORKFLOW.md) and [audit](BORTUS-AUDIT.md).

## Flux

| Endpoint | Contract |
|---|---|
| GET /api/flux/repos | Repository list |
| POST /api/flux/repos | Write + engineAdmin; create GitRepository with name/url/branch/path and optional auth inputs |
| DELETE /api/flux/repos/[id] | Write + engineAdmin; delete with progress tracking |
| POST /api/flux/repos/[id]/sync | Write + engineAdmin; reconcile |
| GET /api/flux/repos/[id]/delete-progress | Deletion progress |
| GET /api/flux/repos/[id]/detail | Repository detail (name used by dashboard) |
| GET /api/flux/kustomizations/[name] | Bundle inventory/conditions |
| GET /api/flux/hierarchy | Repository/Kustomization/HelmRelease/namespace hierarchy |

New private credentials use native Secrets and are never retained in `GitRepo.authData` or argv. Existing credential collisions fail. The application merge does not change any live Flux branch; see [Flux guide](FLUX-GITOPS.md).

## Health

Exact public GET `/api/health/live` reports process liveness. `/api/health/ready` checks signing/lookup configuration, migrated SQLite/aliases and native Secret list access across the allowlist, returning 503 on failure. Neither returns credentials.
