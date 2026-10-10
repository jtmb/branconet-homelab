# BORTUS audit remediation and native Secrets engine delivery

Active goal, started 2026-10-10: implement A01–A22 from [the immutable audit baseline](BORTUS-AUDIT.md), validate the changes, and deliver the human-selected native Secrets engine scope. Branch: `codex/bortus-performance-ui-audit`; starting audit commit `51e8cd6`, application/main baseline `c2e22ca`. Production rollout and charts-repository work are separate coordination tasks.

## Acceptance ledger

An item becomes complete only after implementation and relevant evidence. Local acceptance and external/image/live acceptance are recorded separately. Historical audit findings/evidence remain unchanged; this ledger records their resolution.

| Finding | Implementation / acceptance | Status |
|---|---|---|
| A01 writer invariant | Serialized SQLite transaction/actor recheck; 12 concurrent demotion/deletion/mixed cases across independent clients | Local acceptance passed; image/live unperformed |
| A02 account revocation | Current-user/session-version Node middleware; deletion/reset HTTP API/page denial; legacy version-zero compatibility | Local acceptance passed; image/live unperformed |
| A03 bootstrap invariant | Serialized registration/settings decision; six concurrent client requests and four production HTTP requests; uniqueness 409 | Local acceptance passed; image/live unperformed |
| A04 argv boundaries | Structured args, resource validation, fake CLI assertions; real kubectl impact remains external | Pending |
| A05 truthful commands | Typed/sanitized subprocess failure; mutation/Flux callers and failure matrix | Pending |
| A06 availability | Explicit unavailable/partial/stale contracts and browser states | Pending |
| A07 cache cost | Preserve coalescing; per-resource timing/deadlines/backoff/size handling; fixed before/after fixture | Pending |
| A08 resource capabilities | API/menu capability matrix and supported logs/YAML/actions | Pending |
| A09 deployment state | Owner UID mapping, desired/observed/zero replicas and integer bounds | Pending |
| A10 pod filters | Defined namespace/type/label contract and regressions | Pending |
| A11 polling/refetch | Shared query/session state, visibility/cancel/overlap/backoff and mutation refetch | Pending |
| A12 permissions/runtime UI | Fresh UI session/capabilities; server authority retained | Pending |
| A13 sorting | Typed numeric/quantity/date sorting with browser evidence | Pending |
| A14 mobile | Responsive nav/content/dialogs at fixed widths/zoom | Pending |
| A15 accessibility | Names, links, focus, dialog semantics; keyboard evidence; screen-reader limitation explicit | Pending |
| A16 YAML lifecycle | Authoritative readOnly and reset/dirty-close behavior | Pending |
| A17 Secret intent | Explicit dirty/empty replacement/delete confirmation; mock CAS/value-redaction tests | Pending |
| A18 SSE | Completion/abort/cancel cleanup, no overlapping poll; timer and large-output tests | Pending |
| A19 quality gates | Noninteractive lint, scoped clean Node 22 CI, focused HTTP/browser coverage | Pending |
| A20 dependencies | Compatible upgrades, advisory reachability ledger, image/major-upgrade boundaries | Pending |
| A21 lists/probes/forms | Bounded metadata/probe work, independent aliases, loading/saving/error/pagination | Pending |
| A22 lazy loading | Route bundle and modal interaction comparison, optional feature loading | Pending |

## Commit sequence and checks

1. Account invariants and revocation, including forward SQLite migration and disposable concurrency/HTTP checks.
2. Structured kubectl boundaries and truthful failures, followed by capability/availability/resource correctness.
3. Role/runtime UI, query lifecycle, responsive/accessibility/editor/Secret intent fixes.
4. Measured cache/poll/SSE/list/probe/client-code work without losing healthy coalescing.
5. Lint/CI and compatible dependency triage; distinct review for any breaking framework/style change.
6. Selected native Secrets engine capabilities and integrated acceptance.

Each stage has independently revertible commits, checks all `docs/` for changed contracts, and runs focused regressions plus applicable `npm test`, `npm run typecheck`, `npm run build`, `npm run test:integration`. No operator DB, kubeconfig, password or production resource is used for testing. No ignored prototype cleanup bypass is permitted.

Account implementation now includes a seeded account_lock forward migration, transaction-based account store, Node middleware current-user/session-version checks and reset revocation. `tests/accounts.test.ts` covers two independent Prisma clients, six concurrent bootstrap/open-registration requests, repeated cross-demotion/deletion/mixed attempts, uniqueness, self protection and stale/deleted/demoted actors. Execution evidence remains pending until checks finish.

Account stage evidence on Windows/Node 24: all 16 unit/transport tests passed (including five new account tests and 12 cross-change races across independent clients). Production build passed with Node middleware. HTTP integration passed in 18.59 s with four concurrent bootstrap requests leaving one writer, exact info exceptions, reset/deleted-cookie denial on ordinary APIs/pages, fresh migration/zero drift and existing native value-safety checks. Typecheck passed after correcting the test-env type to NodeJS.ProcessEnv. A focused follow-up adds explicit pre-version JWT migration/reset coverage. Docker/image/live acceptance remains external.

## Native Secrets engine scope decision

The human's answer is pending between Vault-style KV paths/versions/rollback/policies/audit/import-export/rotation workflows and additionally dynamic credentials/PKI/transit. Scope-dependent implementation waits for that answer. Full Vault parity is not claimed.

Design constraints for either choice:

- Canonical name BORTUS; Kubernetes Secrets remain the only authoritative value/history store. SQLite may hold policies, path/reference and audit metadata, never values or value digests.
- Paths are explicit metadata mapped to exact namespace/name/key. Imported references keep their spelling; no underscore parsing or inferred targets.
- Policies can restrict existing write privileges; readonly remains metadata-only. Reveal/CRUD always require a current DB write role and policy evaluation.
- TLS, resourceVersion/CAS, unrelated keys/type/metadata, immutable objects, valid empty values and last-key retention are preserved.
- Version history, if selected, needs native backing, bounded retention and explicit handling of Kubernetes' per-object size limit. Cross-object history/current writes are not atomic: the design must expose/resolve ambiguous outcomes rather than claim a transaction spanning Secrets.
- Audit records identify actor, operation, target, result and versions without values, payloads, diffs or content hashes. Export is explicit, ephemeral and over authenticated TLS; no server/browser draft persistence.
- Rotation workflows describe supported credential consumers and acknowledgement/recovery; dynamic issuance needs a selected real issuer/backend and revocation/lease acceptance. A random-string generator alone does not establish dynamic credentials or Vault parity.

## Runtime/chart interface for the infrastructure executor

Current inputs remain stable: port 4000, Node 22/Linux standalone image, UID/GID 1000, one replica/Recreate, writable SQLite PVC `/data/bortus.db`, writable framework cache, externally supplied stable `BOTRUS_JWT_SECRET`/`BOTRUS_SECRETS_KEY`, ServiceAccount token/CA or operator kubeconfig, `BORTUS_SECRET_NAMESPACES` and optional metadata-only aliases file. Container provisioning stays disabled. Health paths stay exact public exceptions.

Account fixes add a forward migration for session versions and a SQLite account serialization row. Apply migrations before admitting traffic and take a consistent DB backup; do not reset existing DB. Existing tokens default to version zero for migration compatibility; password resets increment the user's version. Native engine retention/RBAC/env additions will be specified after the scope answer, not guessed into the chart. No Secrets value belongs in Git/Helm values. Current native verbs remain get/list/create/update in every allowed namespace until a reviewed selected design establishes a specific additional need.

The app executor does not change the live image/Flux source. Image build, real-cluster performance, native imported-value acceptance and rollout/rollback evidence require the deployment executor and separate authorized cutover.
