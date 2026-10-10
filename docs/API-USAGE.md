# BORTUS API usage

Flux metadata projections passed local unit/build/HTTP qualification: existing unsafe URLs return an empty URL field, arbitrary annotations/managed fields/value bodies are excluded, readiness uses fixed Ready/Not Ready/Unknown states, and raw condition/event messages are withheld. Stored/native source specs and their authentication references remain intact. Conditions expose bounded allowlisted type/status and fixed classifications.

Flux repository creation now validates URLs as public metadata before persistence/native/CLI side effects. Use credential-free HTTPS/SSH (including supported SSH SCP spelling); embedded HTTPS userinfo, SSH passwords, query/fragment authentication, HTTP/other schemes and control characters return a fixed 400 without echoing the URL. Submit private auth separately; native auth Secret collisions remain refusals. All 89 unit tests, lint, fresh production build/typecheck and both production HTTP fixtures passed; see implementation-evidence/flux-confidentiality.json.

Development base URL: `http://localhost:4000`. Use the configured TLS ingress in production.

## Authentication



Middleware API authentication failures are private/no-store, including 401 and fixed authentication-service 503 responses.

Dashboard APIs require the HttpOnly `botrus_auth_token` cookie, set by login. Infrastructure, peer identity, configuration and flat Secret value operations require fresh write role plus engineAdmin. Scoped KV actions require fresh write role and deny-aware path policy. JWTs carry identity, not role.

Public API paths are `/api/auth/*`, exact `/api/cluster/info`, `/api/health/live` and `/api/health/ready`. Exact `/api/vars/lookup` bypasses cookie middleware but requires Bearer `BOTRUS_SECRETS_KEY`. Exact /api/kv/automation instead requires a scoped KV token inside its handler. Lookup and KV token audiences are independent of user JWTs. Node middleware checks current account existence/sessionVersion for protected reads/pages; deleted accounts and password-reset cookies are rejected. Native Secret handlers and write gates additionally check the current role. A middleware DB outage returns a fixed 503. See [implementation ledger](BORTUS-IMPLEMENTATION.md).

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

Locally qualified administrator consumer controls: GET `/api/kv/rotations/[id]/consumer` returns only named workload UID/RV/owned marker metadata. POST requires matching rotationId, revision/confirmPath, exact confirmConsumer, consumerUid/consumerResourceVersion and current native expectedHead/resourceVersion. It reserves and audits reload-pending with persisted UID/RV, then JSON-patches only the pod-template rotation marker with UID/RV tests. Positive same-UID marker read-back can resolve timeout; unknown outcomes retain intent and never repeat the patch. PATCH rotation resolve can inspect a pending reload only for effective administrators. Tokens have no consumer API/action. Workload readiness and consumption remain explicit operator assertions. These controls passed local unit and production HTTP/TLS qualification.

Rotation routes passed local unit and production HTTP/TLS qualification: `GET /api/kv/rotations?pathId=...&cursor=...` returns up to 100 metadata intents with nextCursor; POST prepares an exact mapped field/same-namespace Deployment, StatefulSet or DaemonSet consumer using pathRevision. PATCH accepts generate, acknowledge, resolve or cancel with rotationId and strict four-KiB metadata bodies. Generate requires revision/pathRevision/confirmPath and native head/RV, and returns only operation/rotation metadata. Acknowledgement requires revision/confirmPath/head/RV, exact `namespace/Kind/name` confirmConsumer and confirmConsumption:true; it records an operator assertion. Cancellation is limited to prepare or proven conflict; resolution never regenerates. Scoped automation accepts rotationPrepare/rotationGenerate/rotationAcknowledge/rotationCancel/rotationResolve under fresh owner/token rotate policy. Tokens never receive workload-reload authority. Final image, real controller and consumer-consumption acceptance remain pending.

| Endpoint | Auth | Contract |
|---|---|---|
| GET /api/secrets?namespace=... | Cookie, either role | `{secrets:[...]}`, object metadata and key names, no values |
| GET /api/secrets?namespace=...&name=...&key=... | Write + engineAdmin cookie | UTF-8 value and current resourceVersion |
| POST /api/secrets | Write + engineAdmin cookie | JSON namespace/name/key/value, mode create or update; update requires resourceVersion; optional type for creation |
| DELETE /api/secrets | Write + engineAdmin cookie | JSON namespace/name/key/resourceVersion; deletes one key and retains empty object |
| GET /api/secret-references?cursor=...&namespace=... | Cookie, either role | At most 100 explicit metadata references plus nextCursor; current scopes only, history excluded |
| POST /api/secret-references | Write + engineAdmin cookie | JSON alias/namespace/name/key; cannot remap an existing alias |
| DELETE /api/secret-references?alias=... | Write + engineAdmin cookie | Deletes SQLite mapping only, retaining native key and file mapping |

Create refuses existing keys. Updates/deletes preserve unrelated data, type and metadata without retrying conflicts. Namespace must be allowed by `BORTUS_SECRET_NAMESPACES`. Missing version: 428; stale/create collisions or immutable objects: 409; missing key: 404; invalid input: 400; Kubernetes/config/RBAC outage: 503. Non-UTF-8 values cannot be revealed through the text API. Responses are private/no-store.

Send value-bearing requests from the UI or protected files over TLS; never include them in command arguments, Git or logs. See [Secrets engine](SECRETS-ENGINE.md).

Alias metadata bounds/cache passed local unit and production HTTP/TLS qualification. GET references accepts only optional cursor/namespace and returns at most 100 references plus nextCursor in stable alias order, filtered to current namespaces excluding history. Internal alias resolution/adoption retains all valid mappings, bounded to 10,000 unique aliases and a one-MiB UTF-8 file. File/DB reads coalesce for 10 seconds; alias API mutations invalidate immediately and fixed failures back off for two seconds. A five-second refresh deadline retains an unsettled worker slot rather than launching more reads or serving stale metadata. No credential values enter this cache.

Alias registration uses a strict four-field JSON body, a four-KiB maximum and the shared 20-second body-read deadline; this bound passed local qualification.

Registration/deletion recheck effective administration in a serialized transaction. Registration merges current bounded DB rows with the validated snapshot and refuses a combined quota over 10,000 with 413, including concurrent registrations; conflicts remain 409. These checks passed local unit and production HTTP/TLS qualification.

The A21 capacity correction preserves exact key-name/immutable/CAS metadata. One-object pages increase request cost: a synthetic 334-object/18-namespace fixture with verified loopback TLS and a fixed 12-ms producer delay made 334 requests and completed in 9.13 seconds (103,828 response bytes). The previous 20-object contract would require 18 pages for that fixture by arithmetic, without a measured old-run latency. This is a capacity correction, not an unqualified performance improvement; slower APIs can hit the unchanged shared 15-second deadline. Controlled Linux RSS/live latency and Secret table/DOM work remain open. Kubernetes [Table negotiation](https://kubernetes.io/docs/reference/using-api/api-concepts/#table-fetches) was evaluated as a future option; [the v1.37.1 Secret printer](https://github.com/kubernetes/kubernetes/blob/v1.37.1/pkg/printers/internalversion/printers.go#L1815) exposes key count, not exact names, so replacing this response requires explicit selected-object metadata retrieval and caller migration. No Table fallback/object inclusion is implemented here.

Native transport writes are limited to 900 KiB of serialized JSON, including existing data/metadata; oversize changes return 413. Requests have eight-second deadlines and four concurrent slots/64 queued. Full lists now use one-object pages with a shared 15-second/10,000-object/32-MiB wire budget across the complete selected namespace scope and the existing four-MiB individual-response cap. Flat summaries read namespaces sequentially and project each page immediately instead of retaining value bodies across namespaces. The response reader also checks remaining aggregate bytes before parsing. Oversize/malformed/repeated-cursor lists still fail explicitly; byte ceilings describe wire input, not total process RSS. A21 local capacity qualification passed all 99 unit tests, lint, fresh production build/typecheck and three HTTP fixtures; see implementation-evidence/secret-capacity.json. History GC preview already uses metadata-only enumeration; focused synthetic qualification passed for 25 owned versions containing 256 KiB each, metadata-only enumeration, stale-RV refusal and exact UID/RV deletion preconditions. The full 99-test/build/HTTP qualification passed; controlled Linux RSS/live performance remains separate. Exact special key spellings including `__proto__` are retained through TLS JSON.

### KV metadata foundation (local branch, local checks passed)

`GET/POST /api/kv/mounts`, `PATCH/DELETE /api/kv/mounts/[id]`, `GET/POST /api/kv/paths`, `GET/PATCH /api/kv/paths/[id]`, `GET/POST /api/kv/policies`, `PATCH/DELETE /api/kv/policies/[id]`, `GET/POST /api/kv/identities` and `DELETE /api/kv/identities/[id]` are implemented metadata endpoints. Cursor pages return `{items,nextCursor}` with at most 100 entries. Mount/policy administration requires effective engineAdmin; path registration requires create policy and write role, registers metadata intent only, and performs no native mutation. Registered namespace scopes remain subsets of the allowlist and exclude history. Active key ownership is unique; disjoint groups may share an object. Path PATCH changes retention only; target/mapping moves are not accepted. Metadata changes require revision (428 missing, 409 stale). All responses are private/no-store; JSON bodies are bounded to 512 KiB and validated strictly.

Identity issue requires the owner or an effective administrator, explicit mount/prefix/actions and a maximum 30-day expiry. POST returns a credential once; list responses exclude credentials/hashes. Revocation, owner deletion/reset/demotion, expiry and owner-policy intersection are checked before every authorized operation. Human value/history/adoption routes passed local production HTTP with verified mock TLS. The automation handler passed local production HTTP/TLS checks; KV UI remains pending. See [KV contract](BORTUS-KV-DESIGN.md).

The historical write-role endpoint tables are narrowed by the KV trust boundary: infrastructure/Flux/YAML/logs/provisioning output, app/alias/inventory mutations and flat Secret values require a fresh write role **and engineAdmin**. Peer identity mutations likewise require effective administration; a scoped writer may PATCH only their own password. Cluster JSON omits arbitrary annotations/managedFields, workload env/commands/args, Secret data fields and condition messages; raw YAML/log output requires administration. Responses label `privateFieldsOmitted:true`. Readonly/scoped writers retain ordinary operational metadata views. The shared UI reflects this boundary. Full native KV qualification and external guards remain pending.

### Scoped automation, audit and capabilities (local checks passed)

Exact `POST /api/kv/automation` now bypasses cookie middleware and requires the distinct opaque KV Bearer token; valid human cookies or the legacy lookup key cannot authenticate it. Strict JSON operations are status, capabilities, versions, read (optional historical version), update, delete (exact path confirmation), rollback, reconcile and resolve (operation ID). Initial creation/adoption, administration, arbitrary shell and unknown fields are rejected. Owner role/session/expiry/revocation and both owner/token path policy are checked before native access; native mutations use the same guarded head/resourceVersion CAS protocol as human routes. Responses are private/no-store; values remain in bounded bodies only. The handler passed unit and disposable production HTTP/TLS qualification.

`GET /api/kv/paths/[id]/capabilities` returns fresh action permissions, supported actions, path revision and operator-asserted guarded-mode flags; permissions do not certify external RBAC/admission or support for unfinished workflows. `GET /api/kv/audit` accepts only pathId, operationId and cursor filters, returns at most 100 whitelisted metadata records, filters scoped views by list policy and excludes unscoped administrative events from those views. Effective engine administrators can inspect all audit metadata. Both passed unit and disposable production HTTP/TLS qualification.

### Human native KV values

History cleanup routes passed local unit and production HTTP/TLS qualification: `DELETE /api/kv/paths/[id]/versions/[version]` accepts head/resourceVersion plus confirmPath; `POST .../destroy` additionally selects 1–100 distinct versions. Fresh destroy policy and guarded mode are required. Active head destruction requires a prior tombstone. References are CAS-removed before checked history deletion, sequence and canonical object are retained, and `cleanupComplete`/per-history outcomes distinguish committed references from partial cleanup. Automation accepts the same structured destroy operation.

`POST /api/kv/history/gc/preview` accepts `{pathId}` and requires effective administration plus destroy policy. It returns up to 100 metadata-only candidates for that path with source head/RV/pathRevision and candidate name/UID/RV, a 24-hour minimum age and complete/eligible/retained counts. `POST /api/kv/history/gc` requires the selected histories, displayed source prerequisites/revision and exact confirmPath; it revalidates ownership, age and all source references, CAS-fences older in-flight commits, then deletes only owned history in the dedicated namespace with UID/RV preconditions. Missing/replaced sources retain history. No startup sweep occurs. These routes passed local unit and production HTTP/TLS qualification.

Bounded transfer APIs passed local qualification: `POST /api/kv/export` accepts selections `{pathId,version?}` and `confirmCredentials:true`, requires export policy, and returns the strict `bortus-kv` v1 bundle described in [KV design](BORTUS-KV-DESIGN.md). `POST /api/kv/import/preview` accepts `{bundle}` and returns metadata-only plans/refusals. `POST /api/kv/import` repeats bundle, ordered documentIndex/pathId/revision/resourceVersion/expectedHead/overwrite plans and `confirmCredentials:true`, returning per-path outcomes and overall success. Existing targets require explicit overwrite; imported unadopted native objects require separate adoption. At most 100 distinct paths/native objects and one-MiB bundle JSON; per-document decoded values remain 256 KiB. No cross-object atomicity or automatic retry. Values stay in private/no-store bodies.

KV JSON bodies have a 20-second read deadline (408 on expiry) and require an exact application/json media type. History namespace aliases cannot be registered through the flat alias endpoint, even if that namespace is included in the ordinary allowlist.

Current human native KV routes passed local production HTTP/TLS qualification: `GET /api/kv/paths/[id]/status`; `GET/POST .../adopt` (metadata-only alias impact preview / explicit administrator adoption); `GET/POST/PUT/DELETE .../data` (current selected fields / administrator first creation / versioned group replacement / exact-path-confirmed tombstone); `GET .../versions`; `GET .../versions/[version]/data`; `POST .../rollback`; `POST .../reconcile`; and `GET /api/kv/operations/[id]` (metadata-only outcome resolution). All responses are private/no-store. Values use explicit `{field,encoding,value}` arrays with utf8 or canonical base64; omitted managed fields in a PUT are removed, unrelated native keys are preserved. Mutations require resourceVersion and expectedHead (428 missing, 409 stale/drift). New creation uses resourceVersion `absent` and head zero. Adoption acknowledges the complete alias list from preview. Native value/history mutations remain disabled unless guarded adoption is explicitly enabled. Ambiguous or post-commit metadata failures return a fixed error plus operationId/outcome for inspection; no automatic overwrite/retry is implied. Automation passed local API checks; Rotation APIs passed local qualification; KV UI and final-image/live acceptance remain pending.

Flat adopted value reads require effective administration and current path read policy; edits/deletions return 409 requiring the versioned endpoint. Legacy lookup checks the fresh enabled legacy service principal; adopted aliases require exact grants and path denies. History is excluded from flat routes even if allowlisted. Bridge/route checks passed locally; image and live-native acceptance remain pending.

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

New runner output is fixed lifecycle/allowlisted role progress only. Ordinary stdout/stderr, task labels, module results and exception text are withheld before job persistence/streaming. A successful child exit without the supported callback start/completion fails with a fixed message. Progress appends are serialized and terminal persistence waits for in-flight appends, preventing a late flush from replacing the final snapshot. All 94 unit tests, zero-warning lint, fresh build/typecheck and three production HTTP fixtures passed, including private-marker absence in storage/streams/logs/argv/generated references. Isolated Ansible-core 2.20.0 producer success/failure checks passed; full deployed Linux runner/image qualification remains separate. Historical raw job output is not rewritten.

Operator shell scripts are limited to 16 KiB and reject NUL bytes. Pod exec uses its exact namespaced endpoint and a single script argument; the browser never routes a selected pod command through the application-host shell. Both are one-shot command runners with bounded output/time, not interactive PTYs. Client abort does not establish that a command's server-side effects were cancelled.

Storage's default list contains persistent volumes and optional Longhorn volumes. It does not use PV names as PVC identities. The explicit kind=pvc view links exact namespace/claim names to PVC details/YAML. Invalid kind/type filters return 400 before CLI execution. List UI renders at most 100 rows per page with typed numeric/quantity/date sorting; API's bounded snapshot limit remains unchanged.

| Endpoint | Contract |
|---|---|
| POST /api/deploy/start | Write + engineAdmin; only site.yml and the eleven supported role identifiers; invalid selection 400 before preparation/job/child side effects; returns success/jobId |
| GET /api/deploy/start | Active job IDs |
| POST /api/deploy/stop | Write + engineAdmin; 202 cancellation requested for a running job owned by this process; 409 for already-complete/unowned jobs; status is determined by the runner |
| GET /api/deploy/history | Latest 50 job metadata rows, without output; administrator-only explicit ?jobId=...&tail=1..65536 returns bounded output/cursor/truncated |
| DELETE /api/deploy/history | Write + engineAdmin; remove completed history only; running job 409, missing job 404 |
| GET /api/deploy/stream | Write + engineAdmin; jobId plus cursor/Last-Event-ID; Unicode-code-point offsets, 4096-character chunks, 32-KiB frame ceiling, explicit completion/error/reset |

Job output streams read bounded SQLite substrings under consumer backpressure, recheck current effective administration/account/session on every poll, and poll at most once per completed 500-ms cycle. The full captured field is not returned to the Node process for polling. Completion, request abort, reader cancellation, missing jobs, authorization failure, DB failure and a 30-minute lifetime close the stream and clear timers. Completed startup never starts a polling interval. Output history is fetched explicitly, never as part of the shared metadata list. Local timer/HTTP/browser and two-MiB Unicode slice evidence is recorded under A18; real runner/image performance remains external.

Container provisioning returns 501. Local provisioning requires separately supplied Ansible/playbooks and independent bootstrap credentials; this app merge includes no Kubernetes provisioning roles. The UI uses the current session/runtime capability and shows independent-operator guidance when provisioning is disabled. See [workflow](BOTRUS-WORKFLOW.md) and [audit](BORTUS-AUDIT.md).

## Flux

Repository DELETE retains native credentials and reports "repository credentials retained for explicit native cleanup" in progress. It performs no inferred `<name>-auth` whole-Secret deletion. Explicit credential lifecycle requires exact native targets/consumers and, for adopted targets, KV policy/version handling. No canonical Secret delete RBAC is added.

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

Readiness passed local unit and production HTTP/TLS qualification with coalesced 10-second results/two-second failure backoff and a nine-second dependency deadline. It verifies forward account/KV metadata and bounded aliases, then requests only a limit-one PartialObjectMetadataList in each current namespace, plus the history namespace when guarded mode is enabled. Four workers share an eight-second native budget; full Secret data lists and write probes are not used. Unsupported metadata negotiation or unavailable dependencies return 503 with fixed metadata only. Readiness does not prove native write RBAC or external admission enforcement.
