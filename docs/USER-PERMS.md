# BORTUS user permissions

BORTUS has two roles stored in SQLite: `write` for operator access and `readonly` for viewing. The JWT carries user ID and username; authorization queries the current DB role, so demotion takes effect without re-login.

## Authentication

Login verifies the bcrypt password hash and signs an HS256 JWT with stable externally supplied `BOTRUS_JWT_SECRET`. Signing material is never generated or stored in SQLite. The `botrus_auth_token` cookie is HttpOnly, SameSite=Lax, valid for seven days and Secure in production. Rotation invalidates cookies while preserving accounts.

First registration creates a write user. Later users default to readonly. Registration closes unless `ALLOW_REGISTRATION=true` or AppSetting `allow_registration` is true. A write user manages accounts; self-demotion/deletion and removal of the last write user are checked. These count/check/change operations are currently non-atomic: the [audit](BORTUS-AUDIT.md#a01--p1-concurrent-changes-can-remove-every-write-user-r) reproduced concurrent demotions leaving zero writers and concurrent first registrations creating two writers. The protections do not currently guarantee these invariants under concurrency.

## Gates

Middleware at `src/middleware.ts` verifies cookie identity. Public paths are `/welcome`, `/auth/login`, `/auth/register`, `/api/auth/*`, framework paths and exact health endpoints. The current implementation treats `/api/cluster/info` as a prefix, although only the info handler exists; it should become an exact exception. Exact `/api/vars/lookup` instead requires Bearer authentication inside its handler. Other unauthenticated APIs return 401 and protected pages redirect to welcome.

Server-side `requireWrite()` enforces the fresh DB role for mutations. Native Secret handlers separately enforce fresh role for metadata/value reads and mutations. Ordinary read routes generally rely on JWT middleware alone: deleting a user does not currently revoke those reads before token expiry, and the session API defaults a missing user to readonly. Native Secret reads and write gates reject a deleted account. See audit finding A02.

Some client views hide operator controls, but the shared resource action menu still shows Edit YAML, Execute Shell and Delete to readonly users; the server gates remain authoritative. Provisioning controls also do not reflect the container runtime's disabled capability. See audit A12. User creation remains disabled while username/password are empty or a request is saving; the named canCreateUser boolean preserves that validation.

| Operation | readonly | write |
|---|---|---|
| Dashboard resource lists/details | Yes | Yes |
| Native Secret names/key metadata | Yes | Yes |
| Native Secret value reveal | No | Yes |
| Configuration, Secret, alias and user mutations | No | Yes |
| Cluster mutations, Flux operations, optional provisioning | No | Yes |
| Application-host terminal | No | Yes |

Write-role terminal commands execute with the application's operating-system permissions and Kubernetes credentials. Treat write accounts as operator accounts with application-host access.

## Bearer lookup and recovery

`GET /api/vars/lookup` uses independently supplied `BOTRUS_SECRETS_KEY`, not user cookies or roles. It returns mapped native Secret values and nonsecret configuration. Keep this credential available only to authorized lookup consumers and require TLS.

Native Secret values never persist in SQLite, command arguments, generated Git files, errors or logs. Legacy sensitive SQLite rows are quarantined. Recover SQLite identities/configuration/reference metadata and Kubernetes values using independently protected backups and operator credentials.

See [API usage](API-USAGE.md), [Secrets engine](SECRETS-ENGINE.md), [deployment contract](BORTUS-DEPLOYMENT.md) and the [prioritized audit](BORTUS-AUDIT.md).
