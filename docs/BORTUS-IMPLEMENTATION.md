# BORTUS audit remediation and native Secrets engine delivery

Active goal, started 2026-10-10: implement A01–A22 from the [immutable audit baseline](BORTUS-AUDIT.md), validate the changes, and deliver the selected native Secrets engine. Branch: `codex/bortus-performance-ui-audit`; audit baseline `51e8cd6`, application baseline `c2e22ca`. Production rollout and separate chart delivery belong to the infrastructure executors.

## Acceptance ledger

Local implementation/acceptance and external Linux image/real-cluster acceptance are separate. The historical audit and audit-evidence stay unchanged. An item remains partial while relevant callers or required checks remain.

| Finding | Current result | Status |
|---|---|---|
| A01 writer invariant | Serialized account transaction; 12 independent-client concurrent demotion/deletion/mixed cases | Local passed; image/live pending |
| A02 revocation | Fresh account/sessionVersion Node middleware; deleted/reset cookies denied on API/pages; legacy version-zero compatibility | Local passed; image/live pending |
| A03 bootstrap | Serialized registration/settings decision; six concurrent clients/four HTTP requests; one writer; uniqueness 409 | Local passed; image/live pending |
| A04 argv | Structured args/name validation; fake CLI HTTP rejection and argv isolation | Local passed; real CLI/image pending |
| A05 truthful commands | Fixed typed failures; failed scale/action/delete/apply and Flux cascade retain recovery metadata | Local passed; real CLI/image pending |
| A06 availability | Explicit backend states; canonical resource lists/details distinguish failed reads from true empty/404 | Resource browser/HTTP passed; remaining legacy callers partial |
| A07 cache cost | Independent resource coalescing/backoff/retention; pool/queue/deadline/item/output limits; fixed-fixture timing | Local passed; image CPU/RSS/real-cluster pending |
| A08 capabilities | Shared matrix/scoped YAML CAS/logs/node actions/pod exec; writer/reader/PVC/node browser menus | Local passed; real ServiceAccount acceptance pending |
| A09 deployment state | UID ownership; zero/paused/generation state; explicit integer scale form; zero→one actual argv | Local passed; real controller/Flux pending |
| A10 pod filters | API and browser namespace/type/label filtering; correct empty result | Local passed |
| A11 polling/refetch | Shared completion-based lifecycle, cancellation/backoff/generation tests; actual browser timer fix | Resource/session/provisioning/administration local passed; Flux migration pending |
| A12 permissions/runtime | Fresh shared session in resources/topnav/shells/provisioning/admin; browser demotion erases user editor/password input | Local passed for migrated callers; Secrets/Flux pending |
| A13 sorting | Numeric/quantity/date/count/unknown tests; browser restarts 2/7/12; typed admin columns | Resources/admin local passed; Secrets/Flux/child tables pending |
| A14 mobile | 56-pixel narrow rail, local table scrolling, dialog fit; resources/admin at 320/390/768 CSS widths | Migrated screens local passed; Secrets/Flux/actual zoom pending |
| A15 accessibility | Named controls/links, resource/admin keyboard dialog trap/return; exact confirmations | Local passed for migrated controls; other controls/automated scan/manual screen reader pending |
| A16 YAML lifecycle | Reset per open/mode; authoritative readOnly; dirty save/discard; readonly reopening/focus return | Local browser passed |
| A17 Secret intent | Existing CAS/value safety plus other-key annotation/managed-fields exclusion regression | Engine/editor dirty/empty/delete-intent work pending |
| A18 SSE | Backpressure/Unicode SQL slices, cursor resume, fresh account checks, terminal cleanup; bounded text tail and browser completion/unmount counts | Local unit/HTTP/browser passed; real runner/image pending |
| A19 quality gates | Flat-config zero-warning lint; app-only Node22 CI; clean Node22 Windows install/build/type/49 unit/HTTP pass | Local passed; external Linux CI/image pending |
| A20 dependencies | Compatible lockfile/PostCSS updates, unused highlighter removed; production audit 7→3 entries for one retained Prisma-config advisory | Local compatibility/reachability review passed; residual advisories/ESLint retirement documented; image/OS scan pending |
| A21 lists/probes/forms | Resource/admin tables bound DOM to 100 rows; exact-ID inventory/config edits; explicit save failures; no speculative row prefetch | Partial; Secret metadata/probes/detail tables pending |
| A22 lazy code | Actions/YAML/log/terminal deferral; observed scripts and offline gzip/Brotli; build estimates | Resource local measurements passed; provisioning/CPU/LCP/fixed mobile performance pending |

## Reversible stages and evidence

- `63a0688`: account invariants/revocation, forward account_lock/sessionVersion migration. 16 unit/transport tests, build/typecheck, production HTTP in 18.59 s; explicit legacy-token follow-up passed.
- `ac5b35f`: structured commands/fixed failures/Flux recovery. 19 unit/transport tests, build/typecheck, production HTTP in 22.22 s.
- `3588864`: merged main's separate-chart contract with application notes retained.
- `0f1e9df`: resource cache/availability/state. 30 unit/transport tests, build/typecheck, production HTTP in 9.48 s; [cache-http.json](implementation-evidence/cache-http.json).
- `cf381a9`: scoped resource APIs/capabilities/runtime gates. 33 unit/transport tests, build/typecheck, production HTTP in 26.80 s. Includes narrow source-ignore exception for API logs/route.ts.
- Current UI/query stage: full 38-test run passed, plus the newly added different-key metadata regression and its 11-test native suite passed. Production build passed after browser-native timers were bound to globalThis. Expanded HTTP passed in 28.47 s, including exact-ID node rename/create/delete, readonly denial and invalid storage/node input. Browser acceptance and byte observations are [recorded separately](implementation-evidence/README.md).
- `0a962f8`: committed resource/query UI and its evidence. SSE/provisioning follow-up: 44-test full suite, production build/typecheck and expanded HTTP in 26.10 s passed; an additional two-MiB SQLite Unicode slice test passed. Browser counts verify one running stream, completed stream closure, no reopen during metadata polling, one stream after readonly navigation and zero after unmount. Guarded KV mode/legacy-lookup/recovery remain proposed next-stage contracts, not implemented features.
- `e2c3abd`: committed bounded provisioning streams/output, six focused lifecycle tests and proposed guarded KV/recovery contracts.
- Administration follow-up: full 49-test suite, build/typecheck and production HTTP in 25.86 s passed. Shared queries/fresh role controls, one abortable mutation per screen, 100-row tables, labelled dialogs, exact deletions and truthful setting/policy state replace one-shot role fetches, overlapping intervals and fake saves. [Browser evidence](implementation-evidence/administration-ui.json) includes open-editor demotion, empty nonsecret save, failed policy apply/recovery, readonly controls and mobile bounds. No browser credential reset or deletion was performed.
- `39b0335`: committed administration forms, mutation lifecycle tests and browser evidence.
- Quality/dependency follow-up: clean source copy with official SHA256-verified Node 22.23.3 Windows runtime passes npm ci, zero-warning lint, build/typecheck, all 49 tests and HTTP (25.22 s; runtime-label evidence follow-up 10.77 s). SHA256 comparison finds zero application-file differences from the tested copy. Browser smoke verifies stable stream count during five metadata refreshes, bounded completed output, zero streams after navigation and settled mobile CSS. [Evidence](implementation-evidence/quality-node22.json), [HTTP diagnostic](implementation-evidence/quality-node22-http.json) and [dependency review](TECH-STACK.md#dependency-review-2026-10-10) retain limitations and unresolved advisories. The Linux workflow is defined but has not run or been pushed by this executor.

The browser found and corrected two defects before acceptance: unbound native timers stopped polling, and an absolutely positioned screen-reader-only Actions header escaped its local scroll region. Regression/browser checks verify the corrections. Initial menu imports briefly raised lists to 149 kB; deferring action code restored their build estimate to 115 kB. Details estimate 113–115 kB versus the historical 133–135 kB. Neither estimate is actual transfer/CPU/LCP.

Observed desktop Pods scripts changed from 18 files to 11 after disabling speculative sidebar/settings/table prefetch. Offline gzip totals changed from 183,805 to 152,244 bytes; default Brotli from 158,313 to 130,651 bytes. Opening actions plus YAML added two files, 7,063 gzip bytes. Single warm-cache wall-clock UI samples include browser-control overhead and do not establish interaction latency acceptance. No network/CPU throttling, Lighthouse, actual browser zoom or screen-reader result is claimed.

Cold fixed-fixture pods took 107.37 ms/one CLI call versus the audit's 184.86 ms/ten calls. Twelve warm samples p50/p95 14.45/16.37 ms made zero CLI calls; twenty concurrent cold requests shared one call. Initial-outage repeated requests returned 503 with no additional calls during backoff. Latencies are observational across different synthetic metadata, not controlled image results.

After each behavior change, every docs domain is checked and affected contracts updated. Focused regressions and relevant unit/type/build/HTTP/browser checks accompany each stage. Tests use disposable SQLite, fake credentials/CLI and loopback mock/unavailable native APIs. No operator database, live kubeconfig, production value or production mutation is used. Broad checks are not repeated on an unchanged stage.

A command combining shutdown and recursive cleanup of an owned UI fixture was rejected by automatic approval review. Narrow shutdown of the two verified disposable processes succeeded; its temporary files were retained. Subsequent stdin-controlled fixtures stop and clean up normally. The earlier blocked historical prototype is never retried or bypassed.

## Native Secrets engine scope

The coordinator stated the working assumption to the human: complete Vault-style KV management, including mounts/paths, grouped fields, immutable versions/rollback, policies, audit, protected import/export, scoped automation and rotation workflows, backed by native Kubernetes Secrets. The optional broader dynamic credentials/PKI/transit question has no direct human answer. KV work proceeds; speculative issuers and full HashiCorp API/feature parity remain outside scope.

The concrete [architecture/API implementation contract](BORTUS-KV-DESIGN.md) specifies scalar/group mapping, native current/history ownership, metadata whitelists, candidate/commit CAS, ambiguous recovery, drift, retention/destruction/GC, policies and token audiences, proposed migrations/env/RBAC, 603 legacy aliases, binary-safe import/export and consumer rotation intent. It is an implementation plan; its future routes/env are not claimed as shipped. Review is not an additional approval gate. The different-key last-applied annotation regression must extend across history/audit/export/UI as those components are added.

Values/history stay native; SQLite holds metadata and authentication hashes, never secret values or value digests. Readonly stays metadata-only. Current objects preserve unrelated keys/type/metadata; owned history/auth metadata is minimal. TLS, resourceVersion and fresh account/policy gates remain mandatory. Bootstrap runs externally and cannot depend on Secrets in the cluster being created.

## Runtime/chart interface

Current image contract: port 4000, Node 22/Linux standalone, UID/GID 1000, one replica/Recreate, writable SQLite PVC `/data/bortus.db`, framework cache, stable externally supplied BOTRUS_JWT_SECRET/BOTRUS_SECRETS_KEY, ServiceAccount token/CA or operator kubeconfig, BORTUS_SECRET_NAMESPACES and metadata-only alias mount. Container provisioning remains disabled. Public probe paths remain exact. Session flags reflect provisioning/operator-shell/pod-exec support; server handlers enforce them independently.

Apply forward migrations before traffic, with a consistent SQLite backup; never reset an existing database. Existing tokens default to session version zero, and reset increments that version. Current native Secret verbs remain get/list/create/update in all configured namespaces. Proposed dedicated history namespace/get-list-create-delete permissions in BORTUS-KV-DESIGN are not yet chart requirements. Preserve all reported 603 unique aliases in 12 namespaces and the existing 18-namespace allowlist/Roles.

The charts coordinator reports private jtmb/branconet-charts main → CI → validated → Flux, source flux-system/branconet-charts, Kustomization flux-system/migration-releases at ./flux/releases, chart charts/bortus and release overrides flux/releases/bortus.yaml. Live BORTUS remains migration-1438b27. These are reported infrastructure results, not app-executor live checks. The app executor does not deploy or change live Flux/image state. Final source/runtime contract and image/native/RBAC/performance/rollback acceptance go to the delivery executor when implementation is verified.
