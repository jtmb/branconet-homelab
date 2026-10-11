# Admission qualification metadata and callable probes

`scripts/migration/bortus-admission-qualification.py` validates bounded caller
inputs without making requests or installing policies. The chart guard source is
frozen at `710e5ecd`: three policies and three bindings, Fail/Deny/Equivalent,
the exact BORTUS namespace, complete CREATE/UPDATE workload coverage including
ephemeral containers, and new-or-old protected references. The module's literal
CEL/spec reconstruction must equal the independently supplied canonical renders;
matching weakened caller renders cannot relax it. Original and exact restore
claims, runtime/operator Secret references and one to eight exact tagless image
digests are mandatory. Additional explicitly reviewed Secret references remain
protected. There are no selectors, parameters or label exemptions.

Call `evaluate(expected_renders, actual_gets, contract, probe_outcomes,
pinned_guard_identities=...)`. The six independently recorded kind/name/UID pins
must match fresh GETs. ResourceVersions remain opaque, may advance and are
returned with canonical public policy-spec SHA-256s. Each policy needs current
observedGeneration and present typeChecking; absent/empty expressionWarnings is
the documented warning-free form. Stale results, warnings, deletion, identity or
spec drift refuse without returning raw objects or warning text. Canonical specs
normalize only literal empty namespaceSelector/objectSelector maps inserted by
the [Kubernetes v1.37 defaulting source](https://github.com/kubernetes/kubernetes/blob/v1.37.0/pkg/apis/admissionregistration/v1/defaults.go).
Those defaults match all objects; every nonempty selector still refuses.

`probe_catalog(contract)` provides closed metadata descriptors for positive
original/restore inert Pods and negative legacy/new/default principal, mutable
tag/label, registry alias, pull policy, init/ephemeral, deprecated principal alias,
all protected Secret delivery forms and oldObject-removal UPDATE cases across
the workload families. The jointly covering corpus has exactly 40 cases, rather
than Cartesian repetition at every mutation. `coverage_map(contract)` and the
returned coverage tuples identify which cases cover each family, reference and
scenario. Both required Secrets get every listed delivery form; the four
oldObject-removal cases cover both claims and both Secrets. Extra explicitly
reviewed Secret names are marked structural-only, never claimed to have actual
probe coverage. Exact full CEL/spec matching proves structural coverage across
families independently of this finite actual corpus, including the new/old
ephemeral claim branches. The actual ephemeral fixture triggers
through its `bortus-kv` service-account principal. Its descriptor names that
principal; `structural_only_ephemeral_claim_names` marks both claims as unprobed
for that specific trigger. It references no nonexistent restore PVC. All four
oldObject-removal UPDATE cases use Deployment; Job init CREATE remains covered.
Root constructs the real requests from reviewed
fixtures and independently bind their descriptors to actual outcomes. Every
case must appear once. Results contain only http_status, outcome, attribution
and other_failure. A negative needs Forbidden/403 with an exact selected
policy/binding UID and validation index; generic 403, RBAC, schema or immutability
errors do not count. Raw API messages, parent metadata, credentials and values
must never enter these outcomes or public refusal frames.

`bortus-admission-operator.py` supplies `AdmissionOperator(source_fence, options,
contract, renders, expected_chart_commit, verify_publication).qualify(directory,
deadline=...)`. Use its exact exported `source.SourceFence`; the caller owns and
closes that borrowed fence. Permanent
guards remain owned by the existing Flux publication path; a trusted current
publication callback must bind exact chart/validated/Ready revision and six
independently observed UID/RV/spec pins. Publication and its potentially long CI
wait happen before the bounded collector invocation. The fresh completed cold
checkpoint must precede guard activation, with the original writer resumed and
Ready: a guard denying legacy Deployment updates cannot be activated before
the cold helper's scale/resume sequence. Guard-protected independent restore
requires that unchanged Ready original writer throughout.

The callback returns closed chart_commit/validated_revision/flux_revision fields,
literal ci_success/flux_ready, the owned Flux Kustomization kind/name/namespace/
UID/RV, six kind/name/UID/RV/spec_sha256 pins, and publication_receipt_sha256.
It verifies prior publication, rather than publishing inside the evaluation
deadline. Independent verified-TLS GETs must match these pins and current exact
specs/type checking before fixtures and around probes. One absolute deadline of
at most 300 seconds includes all requests, source rechecks and cleanup; the
30-second socket limit is not a fresh operation budget. Options are fresh on
every connection; bodies/replies are bounded to 1 MiB/8 MiB, without redirects,
compression, retries or Secret endpoints.

Only root-authorized disposable approved inert Pod and replicas-zero Deployment
fixtures supply actual server oldObject for ephemeral and reference-removal
dry-runs. All four removal cases use Deployment, avoiding Job's immutable
template as a confounding failure; Job remains covered by init CREATE. Durable
pending/UID/RV intents precede fixture mutations, and successful deletion needs
a complete fresh namespace inventory proving name and UID absence. No dummy
fixture mounts original/restored PVC contents or starts the application. Failed
or ambiguous operations remain for root review rather than replay/adoption.

The collector exclusively creates a protected fsynced run with durable proposal
intents before each fixture mutation. Its four oldObject switches use a
replicas-zero Deployment, fresh owned UID/RV and exact spec GETs; ephemeral
dry-run uses the actual owned inert Pod. DELETE acknowledgment needs the exact
owned identity, followed by complete namespace LIST absence of both name and UID.
Failures retain fixtures and uncertain receipts; no automatic cleanup mutation
or new attempt is made. The receipt includes closed selected outcomes, not raw
API messages. Only the exact reviewed Kubernetes Status policy/binding validation
cause counts as denial; RBAC, schema, immutable-field and ambiguous causes refuse.
Canonical-spec matching and fresh pinned UIDs bind the single validation index;
Status itself does not carry policy UIDs or prove them. Thirteen owned local
HTTPS/POSIX regressions pass alongside seventeen pure validator cases: thirty
cases passed on the final source without skips. The first collector source/logs
and prior immutable descriptor set remain retained. No cluster requests were made.

The pure validator remains an input validator, not an admission engine. Root must
perform fresh verified-TLS GETs, parse unambiguous policy/binding attribution
from protected actual API replies, prove binding propagation and request
identity, and repeat identity/spec checks before use. A forged closed record can
never establish observation provenance. Returned `actual_enforcement_accepted`
and `overall_live_restore_acceptance` are always false. The restore callback's
admission receipt must bind separate real evidence; neither a bare Boolean nor
this local library can grant image, RBAC, runtime, data or release acceptance.

The official [policy API](https://kubernetes.io/docs/reference/kubernetes-api/admissionregistration/validating-admission-policy-v1/)
defines current observedGeneration and typeChecking. The [admission guide](https://kubernetes.io/docs/reference/access-authn-authz/validating-admission-policy/)
documents empty typeChecking as warning-free. Chart CEL evaluation and actual
server request qualification remain separate from this metadata validation.
See the [callable restore coordinator](BORTUS-INDEPENDENT-RESTORE.md).

Seventeen pure local regressions pass, including independent frozen chart-render
equivalence, weakened expected/live specs, UID replacement, stale type checking,
missing/duplicated cases, false Boolean shortcuts, unattributed/RBAC/schema
errors, opaque RV changes and public refusal-frame privacy. The first
empty-default-selector refusal and earlier Cartesian fixture versions are
retained. No actual API, policy installation, CEL runtime or live probe was run.

Root integrated the selected admission collector, exact runtime imageID checks
and cold holder-release ordering fix through immutable handoffs, preserving the
actual earlier checkpoint evidence. The [combined local receipt](../evidence/bortus-admission-cold-helper-integration-20261011.json)
records 474 passing current test_bortus*.py cases, zero failures/errors/skips,
144 frozen Python source files and reaped exact process owners. This discovery
scope excludes differently named test modules. Loopback/fake API and disposable
local data checks do not prove live guard enforcement or independent recovery.
The corrected helper has not recaptured live data; the completed checkpoint
remains bound to its original executed source and explicit recovery journal.

The [root maintenance/preflight review](../evidence/bortus-maintenance-preflight-review-20261011.json)
verifies 37 offline proposal payloads, 20 raw committed source blobs/modes, six
exact canonical guard renders, the grant-free externally Flux-owned bortus-kv
ServiceAccount and the BORTUS-only declarative suspension. The actual 11:15 UTC
metadata-only preflight using the corrected helpers passed against the unchanged
completed checkpoint: original writer/storage are healthy, the target remains
absent and masternode is the alternate. It reads no database or native Secret
values and makes no mutation. Neither offline renders nor this preflight prove
admission, independent restoration or application acceptance.

Keep Deny activation held until a qualified compatible app image permits the
planned recovery route. An inert-only allowlist would deny legacy writer
replacement even with its HelmRelease suspended. With prune:false, removing
guard files/references does not remove live Deny bindings. The reviewed
pre-adoption withdrawal alternative explicitly changes all three existing
bindings to Audit through validated Flux, requires fresh observation and owned
holder absence, then resumes the unchanged legacy release through another
validated revision. Audit is not enforcement acceptance. That withdrawal path
is forbidden after forward schema/principal migration or KV adoption; retain
guards and recover with an approved compatible image and current accepted data.
Actual invocation still needs the root's current image/runtime and admission
proof callback; complete probes before creating the isolated restore target.

## BORTUS maintenance prerequisite PR

The [chart prerequisite PR](https://github.com/jtmb/branconet-charts/pull/1)
publishes candidate 47bfca2a5c98bf2834cb5e3f2cd18cfffbe7b015 for review.
It suspends only the BORTUS HelmRelease and adds a grant-free, token-automount-
disabled bortus-kv ServiceAccount through the existing Flux composition. It
includes earlier offline delivery preparation but references no admission
policies/bindings, changes no image, and grants no new permissions. The existing
writer can still self-heal. Global pruning and force remain disabled.

The [root publication receipt](../evidence/bortus-chart-prerequisite-publication-20261011.json)
independently binds 302 frozen inputs, 10 selected raw Git blobs/modes and 35
original artifacts. Existing 22 units and full validation pass; all 33
application renders match the retained prior report. A fresh 11:41 UTC read
finds the same Ready writer, three Ready nodes, active Flux owner and absent
target ServiceAccount, with no data/Secret value reads or mutations. The PR's
exact-head CI is pending at this checkpoint. No merge, promotion or live
reconciliation is claimed; those observations and preserved workload/storage
checks are still required. Final performance/image/admission/independent restore
and native KV acceptance remain open. The completed cold journal is unchanged.

## Observed BORTUS maintenance publication

[Chart PR 1](https://github.com/jtmb/branconet-charts/pull/1) merged as
ba7c8e5bbbabe174cbbaec5b0ba7367336f62752 at 11:46 UTC. Exact-main CI run
38136779991 passed validation and promotion; main and validated match that SHA.
The [root live receipt](../evidence/bortus-chart-prerequisite-publication-20261011.json)
observes source and migration-releases Ready at the same applied revision at
11:49 UTC. Its inventory adds only bortus-kv, Flux-owned with token automount
disabled and no Secret references or RBAC grants. The same BORTUS HelmRelease
is suspended and has exactly the previously reviewed failure settings; removing
those eleven fields and suspension reproduces the original whole spec hash.
The first overly narrow suspension-only assertion is retained as an actual
failed read, followed by this exact corrected comparison; no checks were weakened.

Original writer UID, Ready state, all workload specs/images, claims/PVs,
Longhorn identities/settings, RBAC and nodes match the before checkpoint.
BORTUS storage is healthy. This prerequisite pauses Helm upgrades while leaving
workload self-healing available; it installs no guard, new app image, schema or
KV adoption. The completed cold checkpoint and originals remain intact. Final
app performance, guarded release and independent full-row restore stay open.


## 2026-10-11: actual legacy schema metadata qualification

The [root live schema receipt](../evidence/bortus-current-legacy-schema-20261011.json)
passes against the sole Ready legacy digest writer. Seven migration names,
finished/non-rolled-back history and all thirteen application table column layouts
match; writer UID/RV, owner/template and claim/PV identities match before and after.
The fixed Node program opens SQLite read-only and selects only migration ledger
and schema metadata. It runs through stdin; no app entrypoint, application rows
or credential values are read. Separate reads and name-based exec are non-atomic.

The first actual check failed because raw Git SQL checksums differ from deployed
SQL file bytes. Actual ledger hashes match all seven files in the immutable legacy
image: six are exact Git LF-to-CRLF conversions; the seventh is exact Git LF. The
new manifest pins this exact mixed history. It does not accept arbitrary alternate
checksums. Original failure and diagnostic receipts remain retained. An earlier
local launcher used Windows CRLF reader bytes instead of the already qualified
embedded LF program; that failure and its non-causal negative checks are retained.

The [callable producer](../scripts/migration/schema-current-writer-v1/current-schema-producer.py)
is source-bound with its fixed reader, exact image migration manifest and controls.
Six actual disposable Node fixtures and sixteen local producer controls pass,
including identity/RV/storage drift, forward schema refusal, FIFO nonblocking open,
selector-constructor failure child reaping and bounded output/deadline cleanup.
The actual producer uses fresh verified mTLS metadata and an exclusive fsynced
0600 receipt in a 0700 directory. Receipt names match the phase-one callback ABI.
Invoke it fresh under the callback's shared deadline each time; this observed
receipt is historical evidence. Guard publication, actual admission probes,
independent whole-row restoration and final app/image/performance remain open.

## 2026-10-11: guards delivered through CI and Flux

[Charts PR #3](https://github.com/jtmb/branconet-charts/pull/3) merged the
reviewed guard chart. Main CI run 38150613416 passed validation and promotion;
Flux source and `migration-releases` both applied the exact validated merge
commit. All six Fail/Deny guard specs match their reviewed renders, and all
three policies report current-generation type checking with no warnings.

Fresh actual checks preserve the original controller/storage/principal identities,
sole Ready legacy writer, credential references, encrypted healthy two-replica
Longhorn volume, three Ready nodes and the other 33 Ready releases. The BORTUS
HelmRelease is suspended with the same legacy image; its running Deployment
remains at one replica. The external `bortus-kv` principal still has no grants.

The earlier combined-command approval rejection remains historical evidence.
Separate exact branch push, PR creation and reviewed-head merge commands succeeded.
No manual Flux reconciliation was used. The
[publication evidence](../evidence/bortus-phase1-guard-publication-20261011.json)
records actual publication and metadata checks. It does not prove the 43 admission
probes or independent whole-row restore; neither had run at that publication
checkpoint. The subsequent actual attempts are recorded below. Review identified
an additional typed collection item-header assumption in probe cleanup; its
qualified correction is required before fixture creation. No forward schema or
new application entrypoint has started. Two subagents and the migration coordinator
continue the active goal; the seven old BORTUS chats remain archived.


## 2026-10-11: actual admission attempts and explicit fixture recovery

The [actual probe progress](../evidence/bortus-admission-progress-20261011.json)
retains the first 12-case refusal. Its inert Pod and replicas-zero Deployment
were explicitly deleted with their confirmed creation UIDs, fresh RVs, full
semantic specs and complete LIST/name absence checks. The original uncertain
PUT journal remains unchanged. Kubernetes added the standard Secret-volume
mode 420; the exact strict matcher correction and cleanup composition pass 58
root controls against the current frozen dependencies.

A distinct new probe reached 25 completed cases before a generic probe refusal.
All six recorded fixture mutations were confirmed; its inert Pod and zero-replica
Deployment were subsequently explicitly recovered (see the current evidence below). A separate actual dry-run
for the next scaleIO-reference case returns a correctly attributed guard denial.
That diagnostic does not prove the earlier failure's cause or a full 43-case pass.
No whole-row restore, forward schema or new app entrypoint has run.

The [independent process-group review](../evidence/bortus-operator-group-root-review-20261011.json)
checks 341 raw frontend files, 364 retained artifacts, a successful fresh build,
six HTTP/process controls and thirteen enabled-shell controls. Root also verifies
340 actual retained source files and 4262 compiled files. The selected eight-file
default scan returns one finding: an exact unchanged public prose span,
independently reviewed with zero untriaged findings; it is not a clean scan or
resolution of the two historical provenance findings. This proof covers the
prior process-group source only. All six recorded fixture mutations were confirmed; its inert Pod and zero-replica
Deployment were subsequently explicitly recovered (see the current evidence below).


## 2026-10-11: current admission and private-resource evidence

The [current admission receipt](../evidence/bortus-admission-current-20261011.json)
records successful explicit cleanup of both the 25-case and subsequent one-case
fixtures, preserving each original refusal. An earlier distinct run completed
all 40 protection cases, then refused a legacy ReplicaSet dry-run response. Its
two persistent inert fixtures were subsequently explicitly recovered. A separate
actual HTTP201 dry-run response has a valid UID and no resourceVersion; its name
remains absent. This diagnostic does not reconstruct the earlier reply or grant
the missing three-case, whole-row restore, schema or application acceptance.

Flux metadata independently showed Ready=Unknown while Reconciling=True, both
Progressing at the unchanged chart revision. The root read-only provider now
waits at most ten seconds for that exact current-generation state within the
original absolute deadline. A fresh Ready=True proof is still required; other
failures refuse, and mutations are not retried. The current dependency and
readiness composition passes 79 local controls.

The [private-resource review](../evidence/bortus-private-resource-root-review-20261011.json)
binds candidate f27cfa10 to 342 raw Git files, 416 retained artifacts, 341 actual
source files and 4262 compiled files; three focused controls, a fresh build, six
HTTP/process controls and six browser checks pass. Two mixed-line-ending
bindings explicitly run from working bytes to raw Git bytes; both directions
were independently verified. The selected default scan still reports one
individually reviewed unchanged public prose finding. Historical findings,
performance and final live-image acceptance remain open. This candidate is not
deployed.

## 2026-10-11: completed admission stage and current verification preparation

The [current admission receipt](../evidence/bortus-admission-current-20261011.json)
records a distinct completed operator run: 40 policy outcomes plus three legacy
positive dry-run checks, all eleven operations confirmed, and 135.613 seconds
within the original 300-second budget. The original writer stays Ready with the
same template. Both inert fixtures have named404 and complete LIST/name/UID
absence proof. Six guard UID/RV/spec pins and chart/CI/Flux stable fields remain
exact. The Flux owner's status RV may advance during normal reconciliation,
with fresh Ready/current-generation proof at the same UID/revision.

The root reporting wrapper incorrectly expected 43 entries in the policy-only
array and exited 1 after operator completion. Independent read-only verification
checks the original unchanged completed transcript, strict attribution, separate
three positives, all confirmed deletes and fresh current closure; it exits 0.
Its first overly strict full Flux owner RV equality assertion is also retained.
No admission probes were replayed or lost responses reconstructed.

The [pinned current-verification proposal](../evidence/bortus-pinned-current-root-20261011.json)
passes 117 local controls with isolated exact-source suite copies. The original
shared fixture-directory setup failure remains retained. This separately qualified
private callback reuses the completed 43 transcript as labelled static evidence,
with fresh six exact guard UID/RV/spec GETs, source/image/publication fences and
two distinct schema receipts inside each callback floor. All six callbacks share
one absolute 300-second deadline. Actual producer wiring, independent whole-row
restore, final checkpoint, schema upgrade, rollback and release acceptance remain
open. No live callback or application entrypoint was dispatched.

The [log-choice candidate review](../evidence/bortus-log-container-root-review-20261011.json)
verifies 342 raw Git files, 192 original artifacts and 341 retained source and 4262
compiled files. Six focused controls, fresh types/lint/build and six HTTP/process
checks pass. Eight browser checks belong to an overall failed attempt; three
complementary checks pass on the same immutable build with exact compiled shared
focus-refresh attribution. This is not one uninterrupted 11-pass run. The selected
ten-file default scan retains one independently reviewed unchanged public prose
finding, zero untriaged findings and two historical provenance findings still
open. This candidate is not deployed; performance and whole-audit gates stay open.
