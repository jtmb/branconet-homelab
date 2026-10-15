# BORTUS K8s performance, correctness and UI audit

## Current finite A19 sensitivity qualification

Hosted run `38770022640` now qualifies seven finite source-regression sensitivities: the unchanged five flat cases plus A02 deleted-account and A03 bootstrap-writer DB cases. Validation commit `3420513ec034439c38e0cd2adc17aa2c96b9136e` has the complete frontend tree `2dd777cadd669b214631401a98f85bf4a4eeda78` equal to owning commit `e386e5bfdcaf07e01054f98f1e537452334db171`, with workflow blob `a8198320c23d28628750ae86e573e038208ea032`. Normal locked build/lint/types and unchanged342+8 passed. All seven pristine executions exited0 and all seven disposable mutants exited1 at their declared unchanged assertions; original inputs and restoration checks passed, with no skips/cancellations, signals or spawn errors. The A02 account parent has pristine5/5/0 and mutant5/3/2 tests/pass/fail, including only its final post-deletion child assertion plus parent aggregate. The A03 registration parent has11/11/0 and11/4/7, including six declared open-registration child assertions plus parent aggregate; the other four children pass. The exact166-byte SQLite warning is retained in both A02 executions; A03 and all five flat cases have empty stderr. The five flat pairs took3493ms and the four DB executions6362ms in this observation, within separate unchanged240-second/20-second-reserve runners,30-second children,1MiB per stream and five-minute2CPU/1GiB/no-swap/PID256/networknone steps. The original90-second accounts and30-second registration parent timers and all342+8 bodies/flags remain unchanged. The initial metadata parser refused a timestamp BOM; its correction parsed the same retained hosted log without refetch or CI rerun. Default log/result scan `135142` passed0/zero; the committed-source authority is fresh raw394-file scan `1dbbd8`, not the earlier normalized snapshot `5aa92f`. Prior three/five qualifications and source-only preparation receipts remain immutable and source-specific. These unit/VM and synthetic DB checks do not establish A01 cross-process sensitivity, browser CI smoke, universal mutation/redaction coverage or complete A19. Actual AT, the two warm performance regressions, image/security/recovery/live and adoption limits remain open. [Seven-regression hosted qualification](implementation-evidence/a19-seven-regression-sensitivity-qualification.json) records the exact cases and limits.

The initial compiled Pods browser CI run `38775576367` failed with an unlocated AssertionError; its cause and cleanup remain unproved. The diagnostic run `38778394877`, validation `55aed470ab67faec0007cf13c7effb8b80a7b381` (owning source `dadcca0ee891a641de47673deb79982af1184c61`, frontend `e92300f98c7100381e6b9882fdccecfd2b158fba`, unchanged workflow `b945ae89321d544a9a2de4ca7210c90aba6062bb`), observed the real Pods response at stage4 with HTTP503. Its prior build, lint/types/342 units, seven sensitivity pairs, eight integrations and pinned tool acquisition passed. Fixed emitted records show orderly fixture stop/close,165 stdout bytes/0 stderr bytes, cleanupFailed=false,2 confirmed CIDs,3 exact-name queries/all absent and uncertainCreate=false; this proves only that run's recorded stop/cleanup scope. The HTTP503 cause remains unknown: an executable fake CLI under the current `/tmp` mount may encounter noexec, but no mount or spawn observation was retained. A new wrapper-only diagnostic is source-only/unrun. It reads the actual `/tmp` mount noexec flag and regular/executable-file Booleans, then invokes the original public fake CLI once with fixed get-pods arguments, at most5 seconds within the existing ready deadline and1MiB output cap. It emits only fixed numeric/error-class/count/Boolean fields; no output, error body, path, credential or observed resource string is logged. Diagnostic failure is recorded without replacing the original refusal. The browser driver/assertions, original fixture, shell cleanup, mount options, tool pins, production dependencies, resources and300/60/180/150 deadlines are unchanged. Neither failure is converted into a browser pass or historical cause claim. A01 deterministic cross-process sensitivity is paused before implementation; actual AT, performance/image/recovery/live/adoption and complete A19 remain open. [Fixture execution diagnostic source scope](implementation-evidence/a19-browser-ci-fixture-exec-diagnostic-source.json) preserves both failures and the unchanged acceptance assertions.

The five-case sensitivity extension is now hosted-qualified on run `38764208687`, validation commit `aa13eb7326997960a11c9298ac909488a5c9f4c0`, with the complete frontend tree `b78f417d7e4a1e9e41cb98dacf32a7b5ec1dcf7f` equal to owning commit `cfabf77658bff5e8742b350447af12954e9e62cc` and workflow blob `cd8d2979fd498ecfe5c73decd04460ce4d6b77c7`. All five pristine controls exited0 and all five disposable mutants exited1 at their exact unchanged named assertion, operator and ERR_ASSERTION location; there were no skips/cancellations, signals, spawn errors, stderr or restoration failures, and original inputs stayed exact. The ten children completed in3534ms in this observation under the unchanged240-second whole/20-second reserve,30-second child,1MiB per-stream, five-minute step and2CPU/1GiB/no-swap/PID256/networknone/readonly-checkout bounds. Normal locked build/lint/types and342+8 passed with unchanged flags and test bodies. The434050-byte retained hosted log and numeric result passed the default unsuppressed two-file scanner0/zero, with source current and scanner noLive. The added deployment case executes actual route source through its existing TypeScript/VM unit fixture with real Next responses and validators but controlled auth/CLI/cache dependencies; it does not establish a compiled deployment action or real-cluster outcome. The private KV cache case exercises actual admission modules on a synthetic named `/data` path without reading private values. Fourteen pinned LF inputs, the exact literal route allowance and original three mutant definitions/shared run/assert/restore logic remain bound. Earlier three-case hosted evidence and both source-only preparation records stay unchanged and source-specific; no local test replay was performed. Other meaningful source-regression coverage and original A19/manual/actual AT/performance/image/recovery/live/adoption gates remain open. [Five-regression hosted qualification](implementation-evidence/a19-five-regression-sensitivity-qualification.json) retains the exact cases and limits.

The one-prop overview correction at `ea628d2411238a6776acf3cf742adb03cbe5d6af` (frontend `2d47cae1abf1ed2d969ee552e41104fd29791713`) now has a fresh local build/native-load/342-unit/8-HTTP pass and independent current/process closure. Hosted clean CI run `38750289826` passed the unchanged342+8 checks on lean validation commit `2f4d84f2e9c0c6cc86810f8119b707909145f01a`, whose complete frontend bytes/modes equal that payload. Four finite actual-browser cases also passed: terminal success200 and failed-command502/redaction, then real inventory DELETE500 with six-table rollback and retained dialog/input/in-dialog error, followed by one explicit retry200 after removing the synthetic abort trigger. The premature-launch workflow remains failed and preserved; it created no business browser job. Independent exact/Linux/Windows/final closure passed for the fresh four-case owner. These results do not transfer historical6e receipts to new source or close whole A05/A19, actual AT, performance, image, live or adoption acceptance.

The prior qualified three-case `npm run test:regression-sensitivity` command runs in a separate read-only CI step for three disposable mutations only: A04 permissive name admission, A05 failed subprocess stdout treated as success, and A06 outage treated as an empty list. Each runs its unchanged named test on a pristine copy and then its single mutant; success requires exactly the pinned assertion location, operator, ERR_ASSERTION and expected witness, not an arbitrary exit1. Nine LF input files and unique replacements/mutant hashes are pinned; the copies resolve installed dependencies through a node_modules link to the read-only checkout. Only this filtered step uses Node22.23.3 `--experimental-test-isolation=none` so the selected test runs inside each directly awaited child OS process; normal342+8 flags stay unchanged. TSX may use threads in the same process. Timeout, spawn error, signal, output overflow or unexpected stderr refuse, and a child return is not a universal descendant-absence proof. The six sequential children each have a30-second limit and1MiB per-stream cap, within a240-second runner deadline with20 seconds reserved and a five-minute CI step; the isolated container retains2CPU/1GiB/no swap/PID256/networknone. Every copy is restored/verified even on failure and removed; original selected bytes are checked. Complete bounded synthetic TAP/status records are printed to hosted logs; temp records last only for the container lifetime. Hosted run `38760696046` now passed this exact committed step on validation commit `8f0c0e30cf5cd204d87622eb8b32a60c14988af0`, with the complete frontend tree `8cc04e769bed874ddf513590aaaa69c9a1723cb2` equal to owning commit `e9274f89630157daa4a922a45fada713b48b2ed5` and unchanged workflow blob `1f6ea96c11f125b0457c140cf6c66d23a90570fb`. All three pristine children exited0 and all three mutants exited1 at their exact named assertion; there were no skipped/cancelled tests, stderr, spawn errors or signals. All restore/original-input checks passed. The six controls took1775ms in this observation, within the fixed bounds. Locked build/lint/types and the original342+8 tests also passed. The retained416155-byte hosted log and numeric result passed a default unsuppressed two-file scanner0/zero with current bytes and scanner noLive verified. This is a hosted finite sensitivity pass; no local replay was performed. The historical source-only preparation record stays unchanged. [Hosted three-regression qualification](implementation-evidence/a19-three-regression-sensitivity-qualification.json) records the exact cases and limits. The original342-unit/8-HTTP bodies and steps are unchanged; deliberate sensitivity for remaining source regressions is still open, and manual acceptance clauses are not replaced by these tests.

Fresh public-lock audits retain literal full exit1 with nine development-dependency rows (seven high/two moderate from two advisories) and omit-dev exit0/zero. The coordinator accepted only trusted-source controlled build use through `2026-10-22T23:59:59Z`, with re-review on dependency/input/boundary changes and expiry. Final pruned image package/bundle inspection remains required. No dependency update, clean full-audit claim or image-system waiver follows. Root checkpoint `40e351859c0e295315a2143b346f4b79f4706321` binds these receipts. The original two warm regressions, ten MEDIUM image findings and recovery/other original acceptance gaps remain open.

Audited 2026-10-10 on branch `codex/bortus-performance-ui-audit`, starting from `origin/main` commit `c2e22caeea096836a8b3992f86c63b11c9eb8dbe`. Application root: `k8s-rewrite/front-end/`. Source references below are relative to that root and refer to this immutable baseline.

The highest priorities are account invariants, revoked-account access, kubectl argument boundaries and truthful mutation results. The healthy cache already coalesces concurrent requests; the larger performance opportunity is failure handling, cold-fetch fanout and browser polling. Broken resource actions, retained YAML edit state, sorting, mobile navigation and accessibility need targeted fixes before a visual redesign.

This branch contains the audit, evidence and documentation corrections. Application behavior has not been changed. No image, cluster resource, Secret, user, Flux source, provisioning job or production service was changed by this audit.

## Scope and evidence limits

- **Reproduced (R):** observed against the actual production standalone build using an isolated, freshly migrated SQLite database and synthetic accounts/credentials. Kubernetes CLI responses came from a disposable executable that returns metadata-only fixtures, delays each command by 50 ms, and fails every mutation. Native Secret access pointed at an unavailable loopback HTTPS endpoint.
- **Source-confirmed (S):** a concrete path or lifecycle is visible in the audited code. Where no runtime reproduction was performed, that limitation is stated.
- **Hypothesis (H):** needs additional instrumentation, a real kubectl binary, a representative cluster or a deployment inspection. These are separated from reproduced findings.
- Host: Windows, Node `v24.18.0`, npm `11.16.0`, Next `15.5.27`; image contract is Node 22/Linux. Docker was unavailable. These results do not measure deployed-image behavior, real Kubernetes latency, ingress performance, LCP, peak capacity or live CPU usage.
- The separate migration image was previously reported as `migration-1438b27`. This audit examined the main source above and did not independently inspect or retest that running image. A merge to main does not redeploy it.
- Temporary fixture gateways supplied synthetic cookies internally. Screenshots and saved JSON contain synthetic metadata only. No operator credentials or native Secret values were retrieved or saved.

All ten existing documents in `docs/` were checked: technology stack, Flux, Secrets, permissions, API usage, workflow, cluster connection, kubectl, Ansible interaction and deployment. Current behavioral overstatements in permissions/API documentation are corrected alongside this report.

## Baseline checks and measurements

| Check | Result | Interpretation |
|---|---|---|
| `npm test` | 11 passed, 0 skipped; runner 3.02 s | Includes the real verified HTTPS client against a mock Kubernetes API; proves covered native Secret contracts |
| `npm run build` | Passed; command 47.03 s | Production build and framework type checking; cached local build, not a clean image build |
| `npm run test:integration` | 1 passed; runner 28.62 s | Fresh SQLite migration, zero drift and production HTTP auth/native-outage checks |
| `npm run typecheck` | Passed | No TypeScript errors after the build/integration run |
| Packaged `reproduce.mjs` execution | Completed; reproduced the same account/CLI/filter/attribution/outage findings | New isolated fixture run; [reproduction.json](audit-evidence/reproduction.json), independent timing samples |
| `npm run lint` | Interactive configuration prompt | No checked-in ESLint configuration; this is not a reproducible completed lint gate |
| `npm audit --json` | 16 affected package entries: 12 high, 4 moderate | Scanner classification, not 16 independently exploitable application vulnerabilities |
| `npm audit --omit=dev --json` | 7 entries: 6 high, 1 moderate | Dependency-tree filter; does not prove which packages execute in the standalone runtime |
| Build First Load JS | Shared 103 kB; overview 108 kB; resource details about 133–135 kB | Framework build estimates; not measured browser transfer/render timing |

### Local HTTP and subprocess baseline

Small fixture: one node, three pods, two deployments and 200 nonsecret configuration rows. Each fake CLI call adds 50 ms. Timings include local HTTP/Node/CLI overhead. Warm p50/p95 use 12 sequential samples and nearest-rank percentiles; they are a baseline, not a statistical production SLO.

| Scenario | HTTP result | Latency | CLI calls |
|---|---|---|---|
| First Pods list, cold cache | 200 | 184.86 ms | 10 |
| Services immediately afterward | 200 | 10.10 ms | 0 |
| Deployments immediately afterward | 200 | 15.75 ms | 0 |
| Warm Pods list, 12 samples | 200 | p50 15.24 ms; p95 16.23 ms | 0 |
| 20 concurrent warm Pods reads | All 200 | 17.54–47.51 ms | 0 total |
| 20 concurrent reads after 11 s without cache reads | All 200 | 154.69–186.40 ms | 10 total |
| Two sequential reads with failed node lookup | Both 200 with empty pods | No production latency claim | 20 total |

A single post-test Windows process snapshot was 174.27 MiB working set / 175.26 MiB private memory after the fixture and UI exercises. This is an idle sample, not peak RSS or a Kubernetes memory recommendation. Multiple pods/processes have independent caches; cross-process sharing was not measured.

The shared cache and in-flight coalescing are confirmed across resource routes. A suspected cache copy per route was disproved. Retain that benefit when changing resource fetching. Saved machine-readable results: [baseline.json](audit-evidence/baseline.json).

## Prioritized findings

P1 means fix first because account access, operator decisions or resource boundaries are affected. P2 means a confirmed correctness, usability, resource-cost or validation gap worth fixing in the next stages. P3 means an incremental improvement requiring measurement or product choice. No production exploit or P0 incident is claimed.

### A01 — P1: concurrent changes can remove every write user (R)

**Source:** `src/app/api/users/[id]/route.ts:60–76`, `:122–132`.

**Evidence:** Two synthetic write users concurrently PATCHed the other user's role to readonly, with a password field to exercise the asynchronous hash path. Both requests returned 200; the temporary database contained zero write users. The last-writer count and update are separate operations. DELETE has the same count/delete structure, but its race was not separately reproduced.

**Impact:** The advertised lockout prevention can fail, leaving no account permitted to administer the app.

**Fix:** Enforce the count/check/change invariant atomically with SQLite-compatible transactions/serialization and handle conflicts explicitly. Perform expensive password hashing before the transaction, then revalidate actor and target inside it. Cover demotion and deletion together.

**Validation:** A concurrency regression must attempt cross-demotion, cross-deletion and mixed changes repeatedly, assert at least one writer remains, verify rejected changes return a defined conflict/error, and retain self-change restrictions. Use disposable SQLite only.

### A02 — P1: deleted accounts retain ordinary read access (R)

**Source:** `src/lib/auth.ts:24–32`, `:36–48`, `:54–66`; `src/middleware.ts:21–28`; `src/app/api/auth/session/route.ts:26`.

**Evidence:** After removing a synthetic account from the temporary DB, its still-valid JWT received 200 from `GET /api/nodes`. `/api/auth/session` reported `authenticated: true` and defaulted to readonly. `/api/secrets` correctly returned 401 because its handler checks the current DB role.

**Impact:** Account deletion does not revoke ordinary dashboard/metadata reads for the remaining JWT lifetime, up to seven days for normal tokens. Fresh write/native Secret gates remain effective.

**Fix:** Add an authenticated-user existence/session-version gate in the Node server paths that protect pages and ordinary APIs. Middleware identity verification alone is insufficient. Define password-reset revocation policy and add a session version if required; do not cache write authorization in the JWT.

**Validation:** With an already-issued cookie, delete its account and assert session is unauthenticated and all protected pages/ordinary APIs reject it. Retest demotion, native metadata/value permissions, expiry and logout. Password-reset revocation is currently a source-level follow-up, not a reproduced finding.

### A03 — P1: concurrent first registration creates multiple administrators (R)

**Source:** `src/app/api/auth/register/route.ts:23–24`, `:63–68`.

**Evidence:** Two simultaneous registrations on an empty temporary DB both returned 201 and both received write roles. Role selection uses the pre-hash user count; neither create rechecks the bootstrap invariant.

**Impact:** When registration should close after bootstrap, a concurrent request can also obtain the first-user privilege.

**Fix:** Make bootstrap claiming and account creation atomic, rechecking registration settings/current count inside the protected operation. Keep later registrations readonly. Return predictable conflict/closed-registration responses for races.

**Validation:** Concurrent distinct and duplicate usernames on an empty DB must leave exactly one bootstrap writer. Repeat with registration explicitly open/closed and with the AppSetting override; test uniqueness failures without leaking internal DB errors.

### A04 — P1: readonly resource names can become kubectl options (R mechanism; H impact)

**Source:** `src/lib/k8s.ts:35–38`, `:82–85`; `src/app/api/cluster/namespaces/[name]/yaml/route.ts:14`; analogous pod/deployment YAML GET handlers.

**Evidence:** A readonly request to `/api/cluster/namespaces/<URL-encoded "apps --raw=/version">/yaml` reached the fake CLI with a separate `--raw=/version` option and returned its synthetic raw marker with 200. Route parameters are interpolated into a command string and split on spaces. This confirms argument injection, not shell metacharacter execution: these paths use `execFile`.

**Impact:** A read-only, resource-specific endpoint can accept caller-controlled global CLI options using the app's Kubernetes credentials. Actual kubectl option precedence, target substitution and any native Secret disclosure were **not** tested; no real kubectl binary was available. The potential authorization bypass warrants fixing before further features.

**Fix:** Replace command strings with structured argv; validate namespace/resource names against Kubernetes naming rules at each boundary and reject whitespace/options. Preserve endpoint-specific resource restrictions. Do not expose raw CLI output from generic read handlers.

**Validation:** Instrument argv on all read/write handlers; reject spaces, leading hyphens, encoded separators and global flags before spawning. In a disposable cluster with a real matching kubectl, prove readonly resource endpoints cannot select another resource, server, credential or raw API path. Never run a Secret-exfiltration probe against production.

### A05 — P1: kubectl failures are reported as successful mutations (R)

**Source:** `src/lib/k8s.ts:88–92`; `src/app/api/cluster/deployments/[namespace]/[name]/scale/route.ts:19–27`; similar callers in delete/action/YAML paths.

**Evidence:** The fake CLI exited 1 and emitted `simulated kubectl failure` on stderr for POST scale. The actual API returned `200 {"success":true}`. `kubectlExec` converts error output into a non-null success-like string; callers treat non-null as success.

**Impact:** The UI can acknowledge a failed scale/delete/apply operation and invalidate/refetch as if it succeeded, obscuring permission, validation and connection failures.

**Fix:** Preserve exit status and distinguish `{ok, stdout, safeError}` or throw a typed error. Translate failures into accurate HTTP status and sanitized user feedback. Do not relay potentially credential-bearing raw stderr. Audit every caller, including Flux deletion progress.

**Validation:** Exercise exit 1 with stderr, stdout, both and neither, timeout, missing executable, RBAC denial and a true success. All mutation routes must reject failed commands; UI must retain state and display an actionable error. Keep native Secret values out of errors/logs.

### A06 — P2: unavailable resource data looks like a healthy empty cluster (R/S)

**Source:** `src/app/api/cluster/pods/route.ts:8–10`; `src/lib/k8s.ts:42–43`; `src/lib/cluster-cache.ts:77–90`, `:315–319`, `:346–348`; `src/app/(dashboard)/pods/page.tsx:40–47`.

**Evidence:** Failed node discovery produced `200 {"pods":[]}` twice. Optional resource query failures are also normalized to empty arrays and may be cached while other data succeeds. The Pods client does not check `res.ok` and clears data on fetch exceptions. Several resource lists follow this pattern.

**Impact:** Operators cannot distinguish zero resources, partial permissions, an expired session and an API outage. A bad resource fetch can hide running workloads.

**Fix:** Return explicit availability/error metadata or 503 for failed required reads; represent per-resource partial failures. Preserve last-good metadata with a timestamp/stale indicator if useful. Keep native Secret outage semantics separate: never introduce a DB value fallback or value cache.

**Validation:** Test missing credentials, failed nodes, one failed resource, timeout, 401 and a genuinely empty cluster. The UI must distinguish each state and must never present stale data as current.

### A07 — P2: cold reads fetch ten resources; failed reads retry the whole fanout (R/S)

**Source:** `src/lib/cluster-cache.ts:49–52`, `:75–87`, `:331–348`; `src/app/api/cluster/info/route.ts:17–23`; `src/lib/k8s.ts:30–38`.

**Evidence:** A cold Pods read spawned ten parallel processes; 20 simultaneous cold requests correctly shared those ten. Sequential failed reads spawned ten each, with no failure cooldown. The public overview also performs three DB queries on every read. All resource reads wait for the slowest member of the fanout; configured CLI timeouts reach 15 s, including optional Longhorn at 8 s. CLI JSON output is capped at 2 MiB.

**Impact:** A slow or unavailable optional resource delays unrelated screens; outage traffic repeatedly starts processes. Large cluster lists may exceed the buffer and become an apparent empty cluster through A06. The size limit and production cost were not load-tested.

**Fix:** First add timing/error/process metrics. Preserve in-flight coalescing, introduce bounded failure backoff and resource-specific freshness/failure state. Consider per-resource caches or a native/watch client for nonsecret metadata after profiling. Define a whole-request deadline, optional-resource behavior and bounded large-list handling. Cache inexpensive overview counters only with explicit invalidation.

**Validation:** Repeat cold/warm/concurrent/outage baselines with fixed fixture delays; inject a slow optional resource, >2 MiB lists and 1k/10k pods. Measure p50/p95, process counts, response size, CPU and peak memory in the Node 22/Linux image. Require no warm-cache regression and bounded repeated-failure cost.

### A08 — P2: advertised resource actions target missing or mismatched APIs (R/S)

**Source:** `src/app/(dashboard)/resource-actions-menu.tsx:294`, `:297–314`, `:495–538`, `:545–567`; current route tree under `src/app/api/cluster/`.

**Evidence:** Authenticated fixture GETs for pod logs, node YAML and ingress YAML all returned 404. The menu exposes these actions. Node cordon/drain points at a missing node `/action` handler; ingress Edit YAML has no matching PUT route. Service/PVC “View YAML” fetches the existing JSON detail route and shows serialized JSON. Mutation methods on missing paths were identified from source, not exercised.

**Impact:** Common debugging and management flows fail after the user chooses a supported-looking action.

**Fix:** Define a resource capability matrix and connect only implemented APIs. Add carefully scoped log/YAML routes and write-gated actions where desired, or remove/disable unsupported options with useful explanations. Render actual YAML or accurately label JSON. Apply A04/A05 before adding CLI handlers.

**Validation:** For every advertised action, verify route/method, role, namespace/name encoding, success/error handling and content type. Test logs with multiple containers and unavailable pods. Cover missing resources and API permission errors in browser flows; no live destructive test is needed.

### A09 — P2: deployment attribution and scale state are incorrect (R/S)

**Source:** `src/lib/cluster-cache.ts:202–220`, `:228`; `src/app/(dashboard)/resource-actions-menu.tsx:355–388`.

**Evidence:** With deployments `api` and `api-worker`, a pod owned by `api-worker-rs` with seven restarts was attributed to `api` (7), leaving `api-worker` at 0. Prefix matching stops on the first match. Desired replicas use `status.replicas` instead of `spec.replicas`. Scale-up calculates `(replicas || 1) + 1`, so a zero-replica resource targets two; this last issue is source-confirmed, not a successful CLI mutation test.

**Impact:** Restart totals can point to the wrong deployment; scale state/controls can misrepresent the desired workload and overshoot from zero.

**Fix:** Map pod → ReplicaSet → Deployment by owner references/UIDs rather than name prefixes, using an indexed lookup. Separate desired/observed replicas, handle intentionally scaled-to-zero workloads, use nullish defaults and validate finite nonnegative integer replica counts in the API.

**Validation:** Cover overlapping names, namespaces, arbitrary ReplicaSet names, orphan pods, rolling updates, missing status, zero replicas and fractional/oversized inputs. Assert correct attribution and that scale-up from zero requests one.

### A10 — P2: pod filter query parameters are ignored (R/S)

**Source:** `src/app/api/cluster/pods/route.ts:5–6`, `:15–31`, `:33–57`.

**Evidence:** `?type=app` and `?type=system` returned identical three-pod responses despite two application pods and one kube-system pod. `typeFilter` and the system namespace set are unused. The previously documented namespace query is not implemented either.

**Impact:** API consumers expecting scoped lists receive unfiltered data and extra work; filtering intentions are not enforced.

**Fix:** Decide the supported query contract, validate it, implement namespace/type classification (including the documented label override) or explicitly remove unused options. Client-only search does not substitute for an API filter.

**Validation:** Mixed system/app namespaces, `branconet.io/type` labels, absent labels, combined filters, empty results and invalid query values. Document exact response/filter behavior.

### A11 — P2: polling and refresh lack coherent loading/error/freshness behavior (S)

**Source:** `src/app/(dashboard)/pods/page.tsx:40–76`; `src/app/(dashboard)/deployments/page.tsx:28–67`; `src/app/(dashboard)/nodes/page.tsx:39–69`; `src/app/(dashboard)/settings/page.tsx:62–88`, `:109–128`; `src/app/(dashboard)/topnav.tsx:28–46`; pod detail `page.tsx:28–41`; YAML PUT handlers.

**Evidence:** Resource lists use fixed 10 s intervals without cancellation, visibility pause, overlap protection or backoff. Settings has duplicate session reads in addition to topnav. Refresh ignores HTTP errors and sends no event to refetch the currently displayed page; detail pages generally fetch once. YAML apply handlers do not invalidate the cluster cache. This audit did not simulate slow-network response reordering or measure background-tab request rates.

**Impact:** Slow requests can overlap and older responses may replace newer ones; hidden tabs continue work; a refresh or successful edit can leave displayed state unchanged. Errors are often silent or appear as empty/not-found states.

**Fix:** Share session and resource query state, cancel obsolete requests, avoid overlap, pause hidden-tab polling and back off failures. Connect mutations/manual refresh to targeted invalidation/refetch and visible last-updated/error states. Reuse a compatible existing approach or justify a new query dependency with measured benefits.

**Validation:** Delay/reorder responses, navigate during a fetch, switch tab visibility, expire a cookie and fail refresh/apply. Assert newest-response wins, requests stop when appropriate, errors are visible and post-mutation data updates promptly.

### A12 — P2: UI shows mutations and provisioning without role/runtime capabilities (R/S)

**Source:** `src/app/(dashboard)/resource-actions-menu.tsx:39–45`, `:186`, `:305–342`; `src/app/(dashboard)/deploy/deploy-client.tsx:121–178`, `:369–385`; `src/app/api/deploy/start/route.ts:13`.

**Evidence:** A readonly user's actual pod detail menu offered Execute Shell, Edit YAML and Delete. No role prop gates this shared menu. Provisioning buttons are disabled only by `running`; the backend deliberately returns 501 in container/in-cluster mode, but the UI does not obtain that runtime capability. Server write checks remain authoritative; UI exposure alone is not a mutation bypass.

**Fix:** Supply fresh-session role plus explicit server capabilities to the UI; show only actionable controls and explain unavailable external provisioning. Preserve server-side fresh DB role checks even when controls are hidden.

**Validation:** Browser flows for readonly/write/deleted/demoted users and provisioning enabled/disabled. Direct unauthorized calls must still fail. Role changes should update visible controls without granting cached authority. [Screenshot](audit-evidence/readonly-actions.jpg).

### A13 — P2: numeric table columns sort as strings (R)

**Source:** `src/app/(dashboard)/pods/page.tsx:59–67`; inspect comparable deployment/storage comparators.

**Evidence:** Clicking ascending Restarts in the actual Pods table displayed `12, 2, 7`. The comparator stringifies values and uses `localeCompare`.

**Fix:** Use typed numeric comparators, stable tie-breaking and defined missing-value behavior. Parse resource quantities/dates explicitly where applicable instead of assuming textual order is numeric order.

**Validation:** Compare 0, 2, 7, 12, missing values and both directions in the browser; verify no row identity changes. [Screenshot](audit-evidence/pods-numeric-sort.jpg).

**Finite Settings/PVC follow-up (2026-10-15):** Three further A13 cases passed against unchanged `6e2efbda` compiled source: Settings PV Capacity/Created and Storage PVC Capacity, with six exact ascending/descending observations and three actual-wire/display preconditions. Public values0/2/7/12, equivalent2Gi/2048Mi ties, distinct/equal/missing ISO dates and reachable missing values retained name-ascending ties and missing-last ordering. PVC status capacity, request fallback and defensive missing capacity were checked through actual normalization. Complete name/link/action-label and displayed-cell mappings stayed unchanged; this does not prove physical DOM object identity. Both actors and independent exact/Linux/Windows/later checks exited0, with five GET200 events,374 raw source files plus four generated artifacts,40 inputs,5383 compiled objects and40635 dependencies.58 recorded Linux births and the exact container ID/name were absent;11 Windows births were noLive, with three later Linux reader/query births absent and the Windows reader noLive. Two preceding server/browser workflows remain literal exit1 with Settings-only partial2cases/4directions and no whole-matrix acceptance. The second also retained launcher image-query WinError31 and a separate Windows fresh-reader AccessDenied5; that reader remains exit1. Supplemental closure separately bound eleven direct noLive observations and one recorded PID whose CIM creation time differed, without fabricating a direct API result or waiving access errors. The fresh browser used an initial PV-wire/render precondition and a unique Resource combobox role selector with exact options; historical selector/hydration causation remains an inference because the prior DOM was not captured. The fixture, six business oracles, resource limits and product bytes were unchanged. [Scoped Settings/PVC evidence](implementation-evidence/a13-settings-pvc-browser-qualification.json) supplements earlier A13 subsets without replaying them. Universal table/date, physical DOM, actual assistive technology, mobile, performance, image/live delivery and adoption acceptance remain separate; A07/A21 remain failed/open.

**Finite local follow-up (2026-10-14):** Five further A13 columns passed against the unchanged current `6e2efbda` compiled UI/API: Deployment Restarts, Node Pods and Node/Namespace/Ingress Age, with ten exact directions and five durable actual-wire/display preconditions. Public counts0/2/7/12 and ties retained production zero-normalization; formatted ages2h/2d/7d/12d and reachable missing values used stable name ties and missing-last ordering. Complete name/link/all displayed-cell mappings were preserved, with eight GET200 events. Both actors and independent exact/Linux/Windows/later checks exited0, binding374 raw source files plus four generated artifacts,39 inputs,5383 compiled objects and40635 dependencies.33 recorded Linux births and the exact container ID/name were absent;10 Windows births were independently noLive, with three later Linux reader/query births and the Windows reader closed. The first attempt remains failed after four checkpoints/eight directions: the fixture wrote plural `ingresses.json` while actual source/compiled argv selected singular `ingress.json`. SourceV4 corrected only that dataset key and its comment; browser and all ten expected observations stayed byte-identical. The failed HTTP body count was not separately captured. A retained root staging-mode/order refusal was corrected before independent fresh closure without changing content or replaying the actor. [Five-column evidence](implementation-evidence/a13-five-column-browser-qualification.json) qualifies only this finite subset; prior eight-count/two-raw-date cases were not replayed or reassigned. Other unrecorded table/date cases, physical DOM identity, actual assistive technology, performance, final image, live deployment and adoption remain separate. A07/A21 remain failed/open.

### A14 — P2: expanded sidebar leaves unusably little mobile content space (R)

**Source:** `src/app/(dashboard)/sidebar.tsx:29–36`; dashboard layout and resource table layouts.

**Evidence:** At a 390×844 viewport the default sidebar occupied 224 pixels, leaving 166 pixels before content padding. The Pods table became a narrow horizontal slice. Users can manually collapse it, but there is no responsive initial state/drawer.

**Fix:** Use a mobile drawer or collapsed navigation breakpoint, preserve a reachable menu toggle and give content the available width. Retain useful table scrolling or offer compact summaries for narrow screens. Define whether collapse preference persists.

**Validation:** 320/390/768/1280 widths, zoom at 200%, long resource names, touch targets, scrolling and menu focus. No clipped dialogs or unreachable actions. [Screenshot](audit-evidence/mobile-expanded.jpg).

### A15 — P2: core navigation, rows and dialogs have accessibility gaps (R/S)

**Source:** `src/app/(dashboard)/sidebar.tsx:59–77`; `src/app/(dashboard)/pods/page.tsx:95`, `:150`; `src/app/(dashboard)/confirm-dialog.tsx:29–38`; `yaml-modal.tsx:51–96`; `log-modal.tsx:20–37`.

**Evidence:** After collapsing the sidebar, DOM inspection found all 13 navigation links with no text, aria-label or title. Links remove the outline without replacement focus styling. Pod navigation uses clickable `<tr>` elements without keyboard link semantics. Custom modal wrappers lack dialog semantics/focus management, and close icon buttons lack names. Search fields rely on placeholders. Modal/focus behavior was source-inspected rather than subjected to a full screen-reader audit.

**Fix:** Keep accessible names/aria-current and visible focus; use real links inside rows, named inputs/icon buttons and dialog primitives with focus trapping, Escape and focus restoration. Radix Dialog is already a dependency.

**Validation:** Keyboard-only navigation through collapsed sidebar, tables and every modal; inspect accessible names/dialog roles, focus return and screen-reader announcements. Run an automated accessibility scan, then manually review findings rather than treating a score as acceptance.

### A16 — P2: closing YAML edit preserves editing state in later View YAML (R)

**Source:** `src/app/(dashboard)/yaml-modal.tsx:27–31`, `:57–83`, `:92–99`; `resource-actions-menu.tsx:240–247`.

**Evidence:** Open Edit YAML → Edit → close without saving → View YAML. The reopened viewer still contained an editable textarea and Save button. The modal stays mounted and does not reset editing/content/error state for a new open/mode. In this readonly view, Save has no callback and does nothing. No save request was sent during reproduction.

**Impact:** Viewer/editor modes become misleading and can retain old unsaved content across openings; with later edits, stale content may be mistaken for newly fetched state.

**Fix:** Reset state on an explicitly defined open/resource/mode transition or key/remount the editor. Keep readOnly authoritative and handle dirty-close/discard intentionally.

**Validation:** Edit/cancel/view, edit/error/reopen, different fetched versions and mode transitions. Viewer must never be editable or show Save; newly opened edit must use the fetched version or clearly offer draft recovery. [Screenshot](audit-evidence/yaml-view-retains-edit.jpg).

### A17 — P2: Secret selection permits an accidental empty-value update (S; no native mutation)

**Source:** `src/app/(dashboard)/secrets/secrets-editor.tsx:58–82`, `:211–218`, `:245–265`.

**Evidence:** Selecting an existing key sets update mode/resourceVersion and clears `value` to `""`. Save is enabled whenever the version exists and the form is not busy, without a dirty/explicit-empty-intent check. Submission sends that empty value. Successful saves clear the display and again leave update mode/version active. Key delete is immediate without a confirmation step. These paths were reviewed in source; this audit did not edit/delete any native key.

**Impact:** A user can replace a valid credential with an empty string by saving the untouched, hidden-value editor. Intentional empty values are valid and must remain supported.

**Fix:** Track whether a new value was deliberately entered; distinguish hidden/current/cleared editor state from an intentional empty replacement. Offer explicit empty-value intent and confirm key deletion with the exact target. Do not auto-reveal values, persist drafts, or disable valid empty values unconditionally. Preserve CAS/resourceVersion checks and unrelated metadata/data.

**Validation:** Metadata-only selection cannot silently overwrite; explicit empty create/update works; clear-display never changes Kubernetes by itself; cancelled deletion sends no request; stale versions fail. Use the mock TLS native API and inspect redacted assertions only.

### A18 — P2: SSE startup can register a timer after stream completion (S)

**Source:** `src/app/api/deploy/stream/route.ts:37–46`, `:51–82`, `:91–95`.

**Evidence:** Initial `sendState()` can set `closed=true` for a completed job and close the controller while `interval` is still null. Its `.then()` unconditionally registers a 500 ms interval afterward. The callback exits early while closed; cleanup depends on a later abort. This ordering is source-confirmed; retained timer counts in the production process were not instrumented.

**Impact:** Reopening completed jobs can leave unnecessary interval handles. Running streams also read the entire growing output field twice per second per client and compute a slice; expensive large-output behavior remains unmeasured.

**Fix:** Start polling only when still open; unify abort/cancel/completion cleanup, prevent async poll overlap and handle disappeared jobs. Consider incremental output storage/events if large logs justify it.

**Validation:** Fake-timer tests for completed-at-open, completion during first read, early abort, cancel, missing job and DB failure. Assert zero active timers after termination. Measure large-output DB reads and bounded per-client work before changing storage.

### A19 — P2: lint/CI and regression coverage leave these bugs unguarded (R/S)

**Source:** `package.json:10`, `:14–16`; `tests/native-secrets.test.ts`, `tests/transport.test.ts`, `tests/http.integration.ts`; no checked-in `.github/` workflow or ESLint configuration at the audited baseline.

**Evidence:** Unit/native transport and HTTP integration pass, but those suites do not cover the reproduced account races, ordinary-read revocation, command failures/argv boundaries, resource menu routes or browser interactions. `next lint` prompted for configuration. No repository-owned application CI workflow was present; this does not claim external checks are absent.

**Fix:** Configure a noninteractive lint gate and app-scoped CI for install, migrations, typecheck, tests and build. Add focused regression coverage for the findings rather than implementation-mirroring tests. Use a small browser smoke/capability suite with fake metadata/API fixtures. Match the image's Node major and document OpenSSL-dependent skips.

**Validation:** Run CI from a clean checkout with no operator env/DB/kubeconfig. It must finish without prompts, fail on each deliberately reintroduced regression and publish redacted results. Next 15 describes the deprecated lint workflow and direct ESLint migration in its [versioned ESLint guide](https://nextjs.org/docs/15/app/api-reference/config/eslint).

### A20 — P2: resolved dependencies have outstanding advisories (scanner-confirmed; reachability unproven)

**Source:** `package-lock.json`, `package.json:24–60`.

**Evidence:** Full audit reports 12 high/4 moderate affected entries; omit-dev reports six high/one moderate. Locked examples: Next 15.5.27, nested PostCSS 8.4.31, root PostCSS 8.5.15, source-map-js 1.2.1, nanoid 3.3.12, deepmerge-ts 7.1.5 via Prisma 6.19.3. Counts include direct/transitive affected packages, not unique advisories.

**Impact assessment:** The reviewed [PostCSS maintainer advisory](https://github.com/postcss/postcss/security/advisories/GHSA-6g55-p6wh-862q) requires attacker-controlled CSS processed by PostCSS. No public BORTUS CSS upload/processing route was found. The [DeepmergeTS maintainer advisory](https://github.com/RebeccaStevens/deepmerge-ts/security/advisories/GHSA-ggr8-5vv4-36mx) requires recursive object graphs, which plain JSON alone cannot create. Presence warrants maintenance; application exploitability was not established. The omit-dev tree still includes tools used at build/migration time.

**Fix:** Triage every advisory by version/path and actual execution boundary; update compatible patched packages in small groups with lockfile review. Evaluate Next/Tailwind major changes separately. Do not run blanket `npm audit fix --force`: suggested fixes include major framework/style upgrades. Inspect the built standalone image as well as the install tree.

**Validation:** Clean install, full audit/omit-dev audit, Node 22/Linux build, native transport/HTTP/browser checks and image package inspection. Record remaining exceptions with precise reachability rationale and expiry; no credentials in build context.

### A21 — P3: large metadata/configuration lists and save feedback need refinement (S)

**Source:** `src/app/(dashboard)/configuration/page.tsx:9–29`, `:56–87`; `src/app/(dashboard)/secrets/secrets-editor.tsx:36–43`, `:126–145`, `:310`; `src/lib/secret-client.ts:67–78`; health readiness `route.ts:14–16`.

**Evidence:** Configuration/Secret metadata render complete lists with no pagination/filtering. Configuration lacks a save-in-progress guard and mutation network-error handling. Secret refresh waits for both native list and aliases, so a failed native read prevents independently available alias metadata from displaying. Each readiness check loads all Secret pages (200/page) across all scopes through the same full-list path. Native values necessarily enter the server from the current full Secret API response but are not returned to readonly clients or persisted.

**Fix:** Add useful filtering/pagination after measuring representative list sizes; add explicit loading/saving/error states. Load alias metadata independently. Make readiness checks bounded while still checking every allowed namespace's actual permissions/connectivity; consider metadata-only responses for probes. Never persist/cache value-bearing list payloads as a performance shortcut.

**Validation:** 200/1k/10k metadata/config entries, slow/failing independent sources, repeated save clicks, dropped network and malformed responses. Measure render time, response bytes, probe request count/deadline and peak memory. Validate readiness still rejects an inaccessible namespace and respects TLS.

### A22 — P3: defer optional client code after measuring its contribution (S/H)

**Source:** `src/app/(dashboard)/yaml-modal.tsx:5–7`; shared resource action menu imports; `src/components/cluster/kubectl-shell.tsx` and provisioning terminal imports.

**Evidence:** YAML syntax-highlighting code is imported by menus even when the modal is closed. Resource detail build estimates are about 133–135 kB versus roughly 106–112 kB for many lists. This audit did not attribute individual bytes, run Lighthouse or measure interaction delay. The 103 kB shared base is not evidence of a bundle crisis.

**Fix:** Analyze route bundles; defer YAML/log/terminal features until opened where this reduces initial cost without slowing common actions excessively. Keep the visual design coherent and avoid a framework rewrite for unmeasured savings.

**Validation:** Compare gzip/Brotli transfer, initial JS, parse/execute time, LCP and first modal/terminal interaction under a fixed mobile profile. Check loading/error/focus behavior and keep browser cold/warm measurements separate.

## Additional hypotheses and decisions to resolve

These do not count as reproduced bugs or established production vulnerabilities.

| Item | Source/evidence | Next check |
|---|---|---|
| In-flight refresh can repopulate an invalidated cache | `cluster-cache.ts:342–357`: invalidation clears the value but does not fence an older fetch | Delayed deterministic fetch/mutation test; add generation/version handling if reproduced |
| Public route prefix differs from the documented exact exception | `src/middleware.ts:7–11` uses startsWith for `/api/cluster/info`; no additional matching handler currently exists | Change to exact path when implementing auth fixes; test lookalike future paths |
| Public login/registration/probes can consume CPU/DB/API capacity | Login schema has no max lengths/application throttle; registration bcrypt cost 12; public overview/probes perform downstream work | Inspect actual ingress limits, then benchmark bounded synthetic request rates locally and define body/rate/concurrency limits |
| Deployment/Flux deletion may obscure partial failure or affect broad resources | `flux.ts` deletion calls share A05 and includes optional force/purge behavior | Review each capability/confirmation and dry-run plan; no live deletion was attempted |
| Shell is a one-shot command runner rather than a PTY | `kubectl-shell.tsx` posts commands to the application-host shell endpoint | Choose accurate product labeling or design a separately secured interactive terminal; do not broaden readonly access |
| Native Secret client/probe overhead may dominate larger scopes | `secret-client.ts:28–90` constructs a client per call and traverses list pages | Profile TLS/auth setup and bounded probes in the image; reuse only safe transport state without retaining Secret values or stale roles |
| Bootstrap/deploy screens include legacy assumptions and artwork | External provisioning tree is absent from this application merge; welcome artwork/text still describes historical Secret behavior | Audit copy/capability states against current architecture; replace misleading claims in the UI implementation stage |

## What should remain intact

- Native Kubernetes Secrets are authoritative. Keep explicit alias/namespace/name/key mapping, TLS verification, fresh write-role checks, no-store responses and resourceVersion compare-and-swap.
- Values remain outside SQLite, argv, generated Git files, errors/logs and persisted browser drafts. Outages must not replay old DB credentials, push queued values or introduce another backend.
- Existing preservation/collision/immutability/redaction tests and verified HTTPS transport tests are useful gates. Extend them when touching the Secret UI or client.
- Bootstrap stays external and independent of the cluster being created; container provisioning remains disabled. Do not couple UI improvements to infrastructure migration or Swarm retirement.
- Healthy single-process cache sharing/coalescing is a measured benefit. Retain it while improving failure behavior and freshness.

## Staged implementation plan

| Stage | Scope and order | Required acceptance | Rollback/review boundary |
|---|---|---|---|
| 1. Account safety and command boundaries | A01/A03 atomic account invariants; A02 current-user/session policy; A04 structured argv/validation; A05 typed command outcomes | Concurrent SQLite/auth regressions and command failure/argv tests; all existing native/HTTP checks pass | Separate small commits; any session-version schema change needs forward migration and consistent DB backup/recovery plan; never reset operator DB |
| 2. Correct resource behavior | A06 truthful availability; A08 capability/route matrix; A09 state/owner mapping; A10 query contract; A16 modal lifecycle | Fixture API + browser flows for supported actions, roles, empty/error/stale states, owner chains and editor transitions | Review API response changes with consumers; retain prior UI contract where possible; no cluster writes needed for validation |
| 3. Safe usable UI | A12 role/runtime capabilities; A13 typed sorting; A14 responsive nav; A15 accessibility; A17 Secret intent; A21 loading/feedback | Keyboard/mobile/browser evidence, unauthorized direct-call denial, mock-native CAS/redaction and explicit-empty tests | No visual redesign or Secret architecture change; screenshots at fixed viewports; keep UI commits independently revertible |
| 4. Measured resource cost | Instrument then A07 cache/deadline/backoff; A11 polling/refetch; A18 SSE cleanup; A21 bounded probes/list handling; A22 measured lazy loading | Repeat cold/warm/concurrent/outage baselines, delayed responses, large fixtures and timer cleanup; validate image CPU/RSS/latency | Tune one factor at a time; compare fixed fixtures and environment; retain healthy cache coalescing; revert regressions before widening scope |
| 5. Quality and dependencies | A19 noninteractive lint/app CI and browser smoke; A20 compatible dependency updates, then assess majors | Clean Node 22/Linux install/build/image inspection, scans and all focused checks; explicit remaining advisory rationale | Review lockfile and breaking docs; major Next/Tailwind upgrades are distinct changes, not silent audit fixes |
| 6. Separate deployment acceptance | Build reviewed image, then operator-authorized rollout and observation | Real cluster read latency, correct runtime capabilities/RBAC, imported Secret/auth/CAS/outage/restart/recovery acceptance without value logging | Preserve prior image, PVC/DB backups and explicit rollout/rollback instructions; no rollout was performed here |

Stage 1 should precede adding missing CLI-backed actions. Stage 2 should precede extensive polling/cache work so measurements do not hide correctness failures. UI and performance changes should follow measured targets rather than arbitrary speed claims. Every implementation stage must check all `docs/` files and update affected contracts.

### Repeatable validation commands

From `k8s-rewrite/front-end/`, with a credential-free checkout and disposable test environment:

```powershell
npm ci
npm test
npm run typecheck
npm run build
npm run test:integration
npm audit --json
npm audit --omit=dev --json
```

The audit commands return nonzero while findings remain; do not treat that as a test-runner failure or automatically force upgrades. Run the new configured lint command after A19. Audit UI/account/CLI regressions must use synthetic credentials, isolated SQLite and a fake executable/loopback native API. The existing HTTP integration suite already follows this isolation pattern; do not reuse operator credentials or database.

For performance, retain fixture size, per-command delay, concurrency, cache age, sample count and percentile calculation in the results. Compare image/runtime versions and clean versus cached builds explicitly. Production acceptance needs a separate read-only baseline before any approved rollout; local 50 ms fixture timings cannot serve as production throughput evidence.

## Reference guidance

The installed Next 15 package has no bundled `dist/docs`. Relevant official versioned guides were checked: [route handlers](https://nextjs.org/docs/15/app/api-reference/file-conventions/route), [caching](https://nextjs.org/docs/15/app/guides/caching), and [ESLint](https://nextjs.org/docs/15/app/api-reference/config/eslint). The app's `cluster-cache.ts` is its own process-local cache; framework caching guidance does not establish sharing between replicas or solve its failure semantics.

Evidence images: [numeric sort](audit-evidence/pods-numeric-sort.jpg), [mobile sidebar](audit-evidence/mobile-expanded.jpg), [readonly action menu](audit-evidence/readonly-actions.jpg), [YAML viewer retaining edit mode](audit-evidence/yaml-view-retains-edit.jpg). Gateway-only chunk/public-asset serving issues encountered while setting up the disposable UI fixture were corrected or excluded and are not reported as application bugs.

Final cleanup: all owned fixture processes and temporary browser tabs were stopped; loopback ports 4206–4209 were verified closed. The packaged fixture removed its own temporary state. Automatic approval review blocked both recursive and explicitly named-file cleanup of the original prototype's ignored `front-end/tmp/audit-4U4WqG/` directory, stating only “blocked by policy.” Its synthetic SQLite/config/fake executable remain local and are excluded from this branch's commit. No operator/native credentials are in that fixture.

**2026-10-15 isolated bookkeeping follow-up (A07/A21 stay FAILED/OPEN):** d69f1160 (product6e2 plus raw core c046 only) completed original3pairs/sixprofiles and every independent closure check, but two of ten warm cases regressed: small serial p95 median10.937845 to14.668675ms and1k concurrent67.699072 to71.921427ms. Eight improved; no sample/tolerance changed. Whole-fixture CPU improved while peak memory increased, without causal isolation. Focused83/build-only/compiled10HTTP12SQL13joins stay finite, not full342+8 or delivered acceptance. Product6e2/tree2c4023 stays unchanged; overlay unadopted. Exact bindings/historical failures: implementation-evidence/account-bookkeeping-paired-evaluation.json.

A19 source follow-up, 2026-10-15: the current quality workflow no longer invokes `npm test` in its read-only check container. Its unconditional `pretest` worker writes belong to the preceding writable build; direct `node --import tsx --test tests/*.test.ts` preserves the unit bodies against frozen output. The exact revised read-only command passed lint, nonincremental types and all342 unchanged units in the bounded current-source fixture, with exact/current, all55 recorded host births, CID/name absence and later-reader closure independently verified. This checks-only result does not qualify a new clean install/build/eight HTTP, hosted CI or each-regression negative control. Original audit evidence and validation clauses remain unchanged.
