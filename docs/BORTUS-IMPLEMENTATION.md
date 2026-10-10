# BORTUS audit remediation and native Secrets engine delivery

Active goal, started 2026-10-10: implement A01–A22 from [the immutable audit baseline](BORTUS-AUDIT.md), validate the changes, and deliver the human-selected native Secrets engine scope. Branch: `codex/bortus-performance-ui-audit`; starting audit commit `51e8cd6`, application/main baseline `c2e22ca`. Production rollout and charts-repository work are separate coordination tasks.

## Acceptance ledger

An item becomes complete only after implementation and relevant evidence. Local acceptance and external/image/live acceptance are recorded separately. Historical audit findings/evidence remain unchanged; this ledger records their resolution.

| Finding | Implementation / acceptance | Status |
|---|---|---|
| A01 writer invariant | Serialized SQLite transaction/actor recheck; 12 concurrent demotion/deletion/mixed cases across independent clients | Local acceptance passed; image/live unperformed |
| A02 account revocation | Current-user/session-version Node middleware; deletion/reset HTTP API/page denial; legacy version-zero compatibility | Local acceptance passed; image/live unperformed |
| A03 bootstrap invariant | Serialized registration/settings decision; six concurrent client requests and four production HTTP requests; uniqueness 409 | Local acceptance passed; image/live unperformed |
| A04 argv boundaries | Structured args, DNS validation, injected argv tests and production HTTP fake CLI rejection | Local acceptance passed; real CLI/image/live unperformed |
| A05 truthful commands | Typed/sanitized failures; production HTTP failed scale/action/delete/apply/PV and Flux create/cascade | Local acceptance passed; real CLI/image/live unperformed |
| A06 availability | Explicit unavailable/partial/stale server contracts; browser presentation still pending | Backend local acceptance passed; UI pending |
| A07 cache cost | Per-resource coalescing/backoff/retention, size/item limits, bounded commands and fixed-fixture timing | Local acceptance passed; image/live peak memory/process evidence unperformed |
| A08 resource capabilities | API/menu capability matrix and supported logs/YAML/actions | Pending |
| A09 deployment state | Owner UID mapping, desired/observed generation/zero replicas and integer bounds | Backend local acceptance passed; UI pending |
| A10 pod filters | Namespace/type/label selector contract and server filtering | Local API acceptance passed; browser evidence pending |
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

Account changes committed as 63a0688. The explicit legacy JWT follow-up and typecheck both passed. The kubectl wrapper now accepts structured argv and throws fixed typed errors on nonzero exit/timeout/permission/missing-resource/size failures; caller conversion and route error mapping are in progress. The read JSON compatibility wrapper still maps failures to null until A06 availability work changes that contract.

Command regression coverage now includes preserved JSON/path argument boundaries, DNS/option/path rejection before execution, fixed error mapping and rejection of successful-looking stdout on nonzero exit. Flux cascade stops on discovery/child/namespace errors and no longer attempts the unsupported shell pipeline. Scale is bounded to integer 0–10000. These checks are not yet recorded as passed; production HTTP fake-CLI evidence is being added.

The three focused command tests passed. The HTTP fixture now provides a disposable fake executable on Windows and Linux, logs encoded argv, rejects all mutation commands, and asserts actual route validation/failed scale/action/delete/apply and partial PV results. This fixture cannot contact Kubernetes; real CLI/RBAC/argv behavior still requires separate disposable-cluster evidence.

Final command stage checks passed on Windows/Node 24: 19 unit/transport tests (0 skipped), production build, typecheck, production HTTP integration in 22.22 s. HTTP also verifies Flux apply failure, cascade's active error step, retained recovery metadata and absence of raw command output in responses/server logs. All docs checked; affected API/Flux/workflow/engine/ledger updated. No Docker, real CLI or live test is claimed. Read availability remains A06 work.

Availability/cache conversion is underway. The typed JSON client now throws instead of collapsing failures to null. Each requested resource has separate snapshot/coalescing/backoff/retention state; this replaces the all-resources cache. Route response contracts, projections and focused race/outage evidence are not complete yet.

New cache/pool tests cover requested-resource coalescing without unrelated fanout, stale expiry/backoff, optional API absence versus true empty/partial response fields, mutation-generation races, invalid/oversized lists, concurrency/queue capacity/deadline and invalid JSON. Execution/HTTP/performance/UI evidence remains pending.

All ten focused cache/command tests passed. Deployment/pod regressions now cover ambiguous names/labels, controller UID and namespace isolation, regular/init restarts, desired/observed generation, zero/paused/failure states and actual type/namespace/label selection. The compatibility cluster-node inventory POST also gained the missing fresh write gate; this is an additional authorization correction discovered during conversion.

The three deployment/filter tests passed. The production HTTP fixture now uses fixed 50-ms metadata queries and verifies one-resource cold pod fetch, 20 shared warm requests with no CLI calls, filters, owner/zero/generation state, fresh role denial on node registration/diagnostics, labelled stale reads with backoff, initial unavailable 503 versus successful empty 200, and diagnostic limits. These new HTTP assertions have not run yet. Browser availability/state acceptance and controlled timing evidence remain outstanding.

That expanded HTTP suite passed in 24.98 s; all 29 unit/transport tests and production build passed. Metadata-only timing capture and actual subprocess output/timeout tests have since been added and await their final run. See [post-change evidence](implementation-evidence/README.md) for reproduction and comparison limits.

Final cache/state HTTP acceptance passed in 9.48 s and saved [cache-http.json](implementation-evidence/cache-http.json). Cold pods: 107.37 ms/1 CLI call (baseline 184.86 ms/10); 12 warm samples p50/p95 14.45/16.37 ms/0 CLI; 20 concurrent cold requests shared 1 call at p50/p95 112.95/113.47 ms; 20 warm requests made 0 calls. Twelve requests during an initial service outage returned 503 with no additional CLI calls. Compare latency observationally, not as controlled image performance. Real child-process output overflow and timeout tests passed; typecheck passed. Fresh build already passed for all runtime changes. UI availability/ownership displays, pagination and real image/RBAC checks remain pending.

Final full unit/transport run: 30 passed, zero skipped. All runtime changes had a successful production build; expanded HTTP and typecheck passed. Main's separate-chart contract was merged as 3588864 with application notes retained. No source/image publication or live mutation occurred.

## Native Secrets engine scope decision

The coordinator has stated the working assumption to the human: deliver complete Vault-style KV management (mounts/paths, versions/rollback, policies, audit, import/export, scoped automation and rotation workflows) backed by native Kubernetes Secrets. No direct human answer to the optional broader dynamic credentials/PKI/transit choice has arrived. KV implementation proceeds under that stated assumption; speculative issuers and full HashiCorp API/feature parity are excluded. A later explicit answer may expand the goal.

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

The charts coordinator reports cutover complete: private jtmb/branconet-charts main passes CI to validated; Flux source flux-system/branconet-charts, Kustomization flux-system/migration-releases at ./flux/releases, chart charts/bortus and release overrides flux/releases/bortus.yaml. Live BORTUS remains migration-1438b27. These are reported infrastructure-executor results, not app-executor live checks. Preserve the merged main documentation for that contract when integrating this branch. No app deployment is performed here.

Account fixes add a forward migration for session versions and a SQLite account serialization row. Apply migrations before admitting traffic and take a consistent DB backup; do not reset existing DB. Existing tokens default to version zero for migration compatibility; password resets increment the user's version. Native engine retention/RBAC/env additions will be specified after the scope answer, not guessed into the chart. No Secrets value belongs in Git/Helm values. Current native verbs remain get/list/create/update in every allowed namespace until a reviewed selected design establishes a specific additional need.

The app executor does not change the live image/Flux source. Image build, real-cluster performance, native imported-value acceptance and rollout/rollback evidence require the deployment executor and separate authorized cutover.
