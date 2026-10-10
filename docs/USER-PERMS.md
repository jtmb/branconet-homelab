# BORTUS user permissions

The warm Pod response optimization caches only the redacted metadata projection of a resource snapshot. Middleware still verifies current account existence/sessionVersion for every protected request; no successful authorization result is cached or bypassed. Filtering and current availability/error responses are preserved. Combined Node22 130-test/build/HTTP qualification passed, including account-revocation HTTP checks; controlled performance remains pending.

The integrated workbench receives a fresh selected-path capability result or null and checks its own session/capabilities before private actions. Parent 401/403 removes the selected metadata/dialog; permission/revision failures pause or discard private intent. Readonly may open metadata only, while update-without-read uses an explicit complete-replacement mode. The recorded combined Node22/backend/browser subset passed; integrated transfer/reconcile, full KV lifecycle and final-image/live acceptance remain open.

Fresh create permission does not imply a missing/unadopted target. Client initialization also requires known status or explicit not-found proof, and adoption requires a known source; unavailable/post-mutation unknown status pauses new native actions. Server permissions and CAS remain authoritative.

KV metadata UI passed local qualification. `/secrets/kv` distinguishes fresh effective administrators from scoped writers/readonly users. Mount forms require effective administration; registration uses the fresh write role and server create policy. Retention uses fresh per-path capabilities with matching revision and server update policy. Refresh preserves metadata drafts across revision disagreement with Save disabled; actual role/update-policy withdrawal unmounts and discards the affected form. 401/403 metadata failures hide retained query data. Browser checks prove readonly metadata/no edit controls, complete-segment scope/deny exclusions and fresh withdrawal. Every mutation still checks fresh server authorization. Full policy/identity/value workflow UI and final live acceptance remain open.

KV update and read policies are independent. An explicit complete-replacement form can be available to update-without-read principals, with no private value prefetch and deliberate acknowledgement that omitted mapped fields are removed. Editing that preserves existing selected values requires read. Client gating must not convert update into read access; server drift/CAS verification remains internal.

Flux reader metadata passed local unit/build/HTTP qualification with payload filtering: arbitrary annotations/managed fields, unsafe existing repository URLs and raw controller condition/event messages are withheld. Condition type/status and event type/timestamps are constrained to structured metadata. Engine-administrator requirements on Flux creation/sync/deletion remain enforced, and existing native auth references/credentials are retained. Local provisioning uses fixed callback progress with raw stdout/stderr withheld; local producer and production persistence/stream qualification passed; deployed Linux runner/image acceptance remains open.

The flat Secret editor uses the fresh shared administrator session. Losing access clears value/draft/target/delete-confirmation state, and late reveal callbacks cannot restore it. Selection/reveal cannot submit a replacement; empty values require explicit intent. Key deletion confirms the exact namespace/Secret/key, and alias removal confirms the exact alias. These client controls supplement fresh server authorization and CAS; local TLS/browser qualification passed, including withdrawal and late-response fencing.

The locally qualified rotation workflow uses fresh rotate policy without granting value read/update access. Optional named consumer inspection/reload additionally requires effective administration; scoped users and scoped tokens cannot use it. Consumer acknowledgement is an explicit operator assertion against the current native rotation head. Public workflow/reload qualification passed locally; final-image/live evidence remains pending.

BORTUS has two roles stored in SQLite: `write` for policy-authorized KV access and `readonly` for permitted metadata. Effective engine administration additionally requires write plus `engineAdmin` and grants infrastructure and peer-account access. The JWT carries user ID, username and sessionVersion, never role; authorization queries the current DB role, so demotion takes effect without re-login.

## Authentication

Login verifies the bcrypt password hash and signs an HS256 JWT with stable externally supplied `BOTRUS_JWT_SECRET`. Signing material is never generated or stored in SQLite. The `botrus_auth_token` cookie is HttpOnly, SameSite=Lax, valid for seven days and Secure in production. Rotation invalidates cookies while preserving accounts.

First registration creates a write user. Later users default to readonly. Registration closes unless `ALLOW_REGISTRATION=true` or AppSetting `allow_registration` is true. Account operations acquire SQLite's write lock through the seeded account_lock row before checking registration, actor/session/role, target and writer count. The check and mutation share one transaction across processes. Password hashing happens before acquiring the lock. Self-role changes/deletion and removal of the last writer are refused; a write user may reset their own password. Unique username conflicts return 409 and exhausted retryable contention returns 503. See [implementation acceptance](BORTUS-IMPLEMENTATION.md); audit A01/A03 describe the historical baseline.

## Gates

Alias registration/deletion now recheck effective administration in the serialized metadata transaction; registration also enforces the combined mapping quota. This metadata bound passed local unit and production HTTP/TLS qualification.

History destruction requires fresh write role, destroy policy, guarded mode and exact path confirmation. GC additionally requires fresh effective engine administration at preview, source fence and deletion authorization; scoped automation supports destruction but cannot run administrator GC. Cleanup endpoints passed local unit and production HTTP/TLS qualification and add no infrastructure authority.

Middleware at `src/middleware.ts` uses the Next 15.5 Node runtime and verifies cookie identity against the current DB account/sessionVersion. Public paths are `/welcome`, `/auth/login`, `/auth/register`, `/api/auth/*`, framework paths and exact info/health/favicon paths. Exact `/api/vars/lookup` and `/api/kv/automation` instead require their distinct Bearer audiences inside their handlers. Other unauthenticated APIs return 401 and protected pages redirect to welcome. Middleware DB failures return a fixed 503 rather than admitting the request.

Server-side `requireOperator()` enforces fresh write plus engineAdmin for infrastructure/configuration operations. `requireWrite()` remains on the account route, whose serialized store checks peer administration and scoped self-password access. KV routes enforce fresh role and deny-aware policy. Flat Secret values require effective administration. Deleted accounts and stale session versions are rejected on ordinary reads/pages as well. Password resets atomically increment sessionVersion, revoking existing cookies, including the resetting user's own cookie for a self-reset. Migrated accounts and legacy JWTs default to version zero, avoiding blanket sign-out on migration. Login signs the current version; the session API no longer treats absent accounts as readonly.

Resource actions, provisioning and user administration use the shared polled session. Unknown/readonly/failed sessions do not receive mutations or exec controls; user editors close and erase their password input when write access ends. Server gates remain authoritative. User creation requires a valid 3–30-character username and at least eight password characters; unchanged/invalid edits and duplicate saving are disabled. Passwords are submitted exactly, including intentional whitespace. User dialogs trap focus, close on Escape and return focus; deletion requires the exact username. User metadata uses the shared completion-based query lifecycle and a sortable 100-row page, with explicit unavailable/retry state. Remaining client views are being converted under A12.

| Operation | readonly | scoped write | write + engineAdmin |
|---|---|---|---|
| Dashboard operational metadata | Yes | Yes | Yes |
| Native Secret names/key metadata | Yes | Yes | Yes |
| KV metadata | Permitted list policy | Permitted list policy | Metadata administration |
| KV values/changes (local API checks passed) | No | Action policy | Action policy; administration can repair policies |
| Flat Secret values/changes, configuration and aliases | No | No | Yes |
| Peer user creation/reset/role/flag/deletion | No | No | Yes |
| Own password change | No | Yes | Yes |
| Cluster/Flux/provisioning mutations, YAML, logs/output | No | No | Yes |
| Application-host terminal/pod exec | No | No | Yes, when runtime enabled |

Engine administrator terminal commands execute with the application's operating-system permissions and Kubernetes credentials. Treat effective engine administrators as trusted operator accounts with application-host access.

Both /api/nodes mutations and the compatibility POST /api/cluster/nodes inventory endpoint require fresh effective administration. Inventory registration does not provision/join a node.

## Bearer lookup and recovery

Authenticated KV read/export and adopted flat/legacy reveal now require metadata-only audit authorization before value release. Audit outages fail closed; entries contain no values/digests and do not claim client delivery. The read-audit and bounded transfer additions passed local unit and production HTTP/TLS qualification.

Middleware authentication failures return private/no-store 401 or 503 responses, including attempts to present KV credentials as human cookies. The automation entrypoint authenticates its own token before reading a body or calling native APIs.

Adopted native keys now additionally pass KV read policy on flat reveal. Flat edits/deletions require the versioned endpoint (409), and history cannot be reached through flat/alias routes. Every lookup, including nonsecret configuration, checks the fresh enabled legacy service principal; adopted aliases additionally require exact compatibility grants and deny-aware policy. Unadopted alias behavior remains unchanged. These bridge checks passed local unit and production HTTP/TLS qualification.

Desired-replica editing is a labelled explicit form with integer bounds 0–10000, a disabled unchanged/invalid/save state and fixed API errors. Readonly sessions see the desired count. It does not submit on blur or parse fractional input as an integer.

Top navigation, shell containers, provisioning, users, settings and configuration share the session subscription. Write controls pause after session failure/staleness; host terminal and provisioning visibility also require runtime capability. Logout, revoked role and ended-session events clear terminal instances/metadata and shared queries. The top refresh control checks the server result before refetching active resource queries. Administration mutations have a 20-second deadline, prevent duplicate submissions and abort/drop callbacks on unmount; failures require explicit retry after checking the actual state. Job output streams recheck effective administration/account/sessionVersion during reads and close on revocation. Job metadata remains readable to authenticated readers; explicit output and streams require administration.

`GET /api/vars/lookup` uses independently supplied `BOTRUS_SECRETS_KEY`, not user cookies or roles. It returns mapped native Secret values and nonsecret configuration. Keep this credential available only to authorized lookup consumers and require TLS.

Native Secret values never persist in SQLite, command arguments, generated Git files, errors or logs. Legacy sensitive SQLite rows are quarantined. Recover SQLite identities/configuration/reference metadata and Kubernetes values using independently protected backups and operator credentials.

See [API usage](API-USAGE.md), [Secrets engine](SECRETS-ENGINE.md), [deployment contract](BORTUS-DEPLOYMENT.md) and the [prioritized audit](BORTUS-AUDIT.md).

Exact `/api/kv/automation` has a distinct Bearer audience and ignores human cookies. Its current operations cover scoped status/capabilities/history/value/update/tombstone/rollback/reconcile/destroy/outcome resolution; it cannot perform administrator initial adoption/creation or infrastructure/identity administration. Fresh audit views use list policy, with engine administrators permitted global metadata. These routes passed local unit and production HTTP/TLS qualification; remaining workflows/UI are pending.

## KV foundation in progress

Forward migration `20261010210000_kv_metadata` adds `engineAdmin` without rebuilding or resetting the user table, grants it to existing write users, and seeds their initial KV action policy (existing readonly accounts receive list only). First bootstrap registration receives the flag and full initial policy; subsequently created accounts receive no admin flag and list-only policy, including new write accounts. Engine administration requires a fresh write role plus the flag. User metadata/session responses expose the flag; PATCH users accepts engineAdmin. Peer account creation/password/role/flag/deletion requires effective administration regardless of the peer's flag or policy. A scoped write user may change only their own password. The serialized transaction preserves a final writer and effective engine administrator. Human native KV operations passed local production HTTP/TLS checks; administration UI and remaining workflows are being implemented. Local foundation unit/HTTP/browser qualification passed.

The KV trust boundary enforces the matrix above: infrastructure operations, shell/pod exec, YAML read/download/replacement, pod logs, provisioning output/stream, Flux/workload mutations, flat Secret value access and app/alias/inventory configuration changes now require effective engine administration through the shared server gate. Raw YAML/log/output may contain credentials even when a resource is not a Secret. Shared UI canWrite now means effective administration; canKvWrite retains fresh write-role status for scoped KV controls. Scoped writers must use authorized KV endpoints and cannot reset a broader-policy peer or execute a workload to obtain the app ServiceAccount token. Kubernetes/host administrators and externally controlled workloads remain trusted out-of-band principals. Their direct access is outside application policy isolation. The pre-KV flat writer image cannot enforce this boundary and is not a supported post-adoption recovery image.

Legacy principal and exact-grant administration requires a fresh effective human engine administrator; scoped writers, readonly accounts and automation identities cannot preview or change it. Legacy-involving policy edits require a fresh metadata-only impact preview and exact affected-alias acknowledgement. Principal/path/mount revisions and scope changes invalidate older previews. Principal enable/disable also controls nonsecret legacy lookup and requires that consequence to be acknowledged. There is no new token audience, credential issuance or native privilege. [Local unit and production HTTP/TLS qualification passed](implementation-evidence/kv-legacy-access.json); UI/final-image acceptance remains pending.

## Standalone KV workbench

The standalone [KV workbench](BORTUS-KV-WORKBENCH.md) combines the existing fresh session with selected-path capabilities, rechecks capabilities every ten seconds and pauses after failures/staleness. Readonly receives metadata only; initial adoption/creation needs initializationAllowed and create policy. Ordinary grouped edit requires read and update; update without read uses a distinct confirmed complete replacement using only metadata/operator-entered fields, with no current/history value request. Role, session or capability withdrawal clears all value/draft/transfer state and fences late callbacks. Selection wiring and recorded combined Node22/native-browser checks now pass; broader KV interaction/lifecycle and final-image/live acceptance remain open.
