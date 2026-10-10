# BORTUS user permissions

BORTUS has two roles stored in SQLite: `write` for operator access and `readonly` for viewing. The JWT carries user ID and username; authorization queries the current DB role, so demotion takes effect without re-login.

## Authentication

Login verifies the bcrypt password hash and signs an HS256 JWT with stable externally supplied `BOTRUS_JWT_SECRET`. Signing material is never generated or stored in SQLite. The `botrus_auth_token` cookie is HttpOnly, SameSite=Lax, valid for seven days and Secure in production. Rotation invalidates cookies while preserving accounts.

First registration creates a write user. Later users default to readonly. Registration closes unless `ALLOW_REGISTRATION=true` or AppSetting `allow_registration` is true. A write user manages accounts; self-demotion/deletion and removal of the last write user are refused.

## Gates

Middleware at `src/middleware.ts` verifies cookie identity. Public paths are `/welcome`, `/auth/*`, `/api/auth/*`, exact `/api/cluster/info`, framework/static paths and exact health endpoints. Exact `/api/vars/lookup` instead requires Bearer authentication inside its handler. Other unauthenticated APIs return 401 and protected pages redirect to welcome.

Server-side `requireWrite()` enforces the fresh DB role for mutations. Native Secret handlers separately enforce fresh role for value reads and mutations. Client UI hides operator controls from readonly users; server checks remain authoritative. User creation remains disabled while username/password are empty or a request is saving; the named canCreateUser boolean preserves that validation.

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

See [API usage](API-USAGE.md), [Secrets engine](SECRETS-ENGINE.md) and [deployment contract](BORTUS-DEPLOYMENT.md).