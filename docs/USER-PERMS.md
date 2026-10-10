# BORTUS user permissions

BORTUS has two roles stored in SQLite: `write` for operator access and `readonly` for viewing. The JWT carries user ID, username and sessionVersion, never role; authorization queries the current DB role, so demotion takes effect without re-login.

## Authentication

Login verifies the bcrypt password hash and signs an HS256 JWT with stable externally supplied `BOTRUS_JWT_SECRET`. Signing material is never generated or stored in SQLite. The `botrus_auth_token` cookie is HttpOnly, SameSite=Lax, valid for seven days and Secure in production. Rotation invalidates cookies while preserving accounts.

First registration creates a write user. Later users default to readonly. Registration closes unless `ALLOW_REGISTRATION=true` or AppSetting `allow_registration` is true. Account operations acquire SQLite's write lock through the seeded account_lock row before checking registration, actor/session/role, target and writer count. The check and mutation share one transaction across processes. Password hashing happens before acquiring the lock. Self-role changes/deletion and removal of the last writer are refused; a write user may reset their own password. Unique username conflicts return 409 and exhausted retryable contention returns 503. See [implementation acceptance](BORTUS-IMPLEMENTATION.md); audit A01/A03 describe the historical baseline.

## Gates

Middleware at `src/middleware.ts` uses the Next 15.5 Node runtime and verifies cookie identity against the current DB account/sessionVersion. Public paths are `/welcome`, `/auth/login`, `/auth/register`, `/api/auth/*`, framework paths and exact info/health/favicon paths. Exact `/api/vars/lookup` instead requires Bearer authentication inside its handler. Other unauthenticated APIs return 401 and protected pages redirect to welcome. Middleware DB failures return a fixed 503 rather than admitting the request.

Server-side `requireWrite()` enforces the fresh DB role for mutations. Native Secret handlers separately enforce fresh role for metadata/value reads and mutations. Deleted accounts and stale session versions are rejected on ordinary reads/pages as well. Password resets atomically increment sessionVersion, revoking existing cookies, including the resetting user's own cookie for a self-reset. Migrated accounts and legacy JWTs default to version zero, avoiding blanket sign-out on migration. Login signs the current version; the session API no longer treats absent accounts as readonly.

Resource actions, provisioning and user administration use the shared polled session. Unknown/readonly/failed sessions do not receive mutations or exec controls; user editors close and erase their password input when write access ends. Server gates remain authoritative. User creation requires a valid 3–30-character username and at least eight password characters; unchanged/invalid edits and duplicate saving are disabled. Passwords are submitted exactly, including intentional whitespace. User dialogs trap focus, close on Escape and return focus; deletion requires the exact username. User metadata uses the shared completion-based query lifecycle and a sortable 100-row page, with explicit unavailable/retry state. Remaining client views are being converted under A12.

| Operation | readonly | write |
|---|---|---|
| Dashboard resource lists/details | Yes | Yes |
| Native Secret names/key metadata | Yes | Yes |
| Native Secret value reveal | No | Yes |
| Configuration, Secret, alias and user mutations | No | Yes |
| Cluster mutations, Flux operations, optional provisioning | No | Yes |
| Application-host terminal | No | Yes |

Write-role terminal commands execute with the application's operating-system permissions and Kubernetes credentials. Treat write accounts as operator accounts with application-host access.

Both /api/nodes mutations and the compatibility POST /api/cluster/nodes inventory endpoint require a fresh write role. Inventory registration does not provision/join a node.

## Bearer lookup and recovery

Desired-replica editing is a labelled explicit form with integer bounds 0–10000, a disabled unchanged/invalid/save state and fixed API errors. Readonly sessions see the desired count. It does not submit on blur or parse fractional input as an integer.

Top navigation, shell containers, provisioning, users, settings and configuration share the session subscription. Write controls pause after session failure/staleness; host terminal and provisioning visibility also require runtime capability. Logout, revoked role and ended-session events clear terminal instances/metadata and shared queries. The top refresh control checks the server result before refetching active resource queries. Administration mutations have a 20-second deadline, prevent duplicate submissions and abort/drop callbacks on unmount; failures require explicit retry after checking the actual state. Job output streams recheck account existence/sessionVersion during reads and close on revocation; metadata and explicit output remain readable to authenticated readonly users.

`GET /api/vars/lookup` uses independently supplied `BOTRUS_SECRETS_KEY`, not user cookies or roles. It returns mapped native Secret values and nonsecret configuration. Keep this credential available only to authorized lookup consumers and require TLS.

Native Secret values never persist in SQLite, command arguments, generated Git files, errors or logs. Legacy sensitive SQLite rows are quarantined. Recover SQLite identities/configuration/reference metadata and Kubernetes values using independently protected backups and operator credentials.

See [API usage](API-USAGE.md), [Secrets engine](SECRETS-ENGINE.md), [deployment contract](BORTUS-DEPLOYMENT.md) and the [prioritized audit](BORTUS-AUDIT.md).
