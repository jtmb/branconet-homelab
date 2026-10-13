# BORTUS application deployment

Integration contract for the migration coordinator. Cluster provisioning, Secret import, charts and live acceptance belong to the migration chat. This change never imports or pushes old SQLite values.

## Image and storage contract

Build from repo root: `docker build -t bortus:local k8s-rewrite/front-end`. Override `--build-arg KUBECTL_VERSION=<cluster-compatible-version>` for dashboard CLI operations (default v1.34.1); native Secret API has no kubectl dependency. Docker build excludes env/SQLite/kubeconfig files. Runtime entrypoint runs Prisma migrate deploy and requires signing/lookup env before starting the standalone server. Missing DB schema on existing installations requires a consistent backup and baseline/migration assessment before deploy; never reset production DB.

Kubernetes liveness/startup probes: HTTP /api/health/live port 4000. Readiness: /api/health/ready, timeoutSeconds at least 10. Configure readiness period 30s and protect these endpoints from external probe floods. Network policy must permit app to Kubernetes API TCP 443/6443 and DNS; browser/Bearer ingress needs TLS. Mount aliases from a ConfigMap read-only. No host SSH private keys are needed. For a PVC use fsGroup 1000; allow writable /app/.next/cache and /home/shell for existing dashboard operations. Use one replica/Recreate to avoid concurrent SQLite writers/schema deploys.

The app uses Node 22, Next.js 15.5.27, Prisma/SQLite and the official Kubernetes JavaScript client 1.4.0. The installed Next package lacks `node_modules/next/dist/docs/`; implementation follows the official [Next 15 route guide](https://nextjs.org/docs/15/app/api-reference/file-conventions/route) and [standalone guide](https://nextjs.org/docs/15/app/api-reference/config/next-config-js/output).

Build context: `k8s-rewrite/front-end`. Port: 4000. SQLite: `/data/bortus.db`, persistent RWO PVC at `/data`, one replica, Recreate strategy, UID/GID 1000. SQLite stores users/password hashes, roles, nonsecret configuration and lookup metadata. Run migrations before traffic; back up consistently. Legacy sensitive rows are quarantined from APIs, never used as fallback. After separate import/readback acceptance, scrub obsolete working DB values and protect historical backups outside Git.

## Current source qualification

The reviewed candidate `a00baa8` includes the approved eight-request native
Secret-list cap, flat parser, strict loader failures and pinned Linux compiler.
The dedicated quality workflow runs its original build/check/integration commands
as host UID with explicit writable `HOME=/tmp/bortus-quality-home`. Root verifies
350 raw source files and their Git modes, retained originals and CI delta; see
[source evidence](../evidence/bortus-app-source-root-review-20261012.json).
The separate [fullfunctional review](../evidence/bortus-app-fullfunctional-root-20261012.json)
passes fresh build/lint/types,267 unit tests and six integration controls at UID1001.
All370 originals and4263 compiled bytes are verified. Git archive applied EOL
conversion: four executed files are raw-exact,346 are CRLF-to-LF equivalent and
all350 actual source modes are0664. The original records remain intact; no raw-Git
byte-execution claim follows from this working-EOL qualification.
The child candidate `18c86a7` changes only the compiler’s public header-pin
representation; its full checksums, verifier and resulting ELF remain identical.
[Root pin/export review](../evidence/bortus-header-pins-root-20261012.json) passes
nine focused controls and the unchanged272-file raw source exporter/default scan.
The [original performance comparison](../evidence/bortus-paired-loader-refusal-root-20261012.json)
passes both raw builds, then fails the first candidate native metadata assertion.
Root verifies the compiled default loader was rewritten into an undefined call.
Unbundled loader tests and an identical ELF do not establish compiled-route
correctness. The later [actual compiled correction](../evidence/bortus-compiled-native-root-20261012.json) verifies raw352-source build, unchanged4263 compiled outputs and a334-record/18-namespace status200 route that actually loads the native ELF. Its fixture-only child passes two cleanup controls; full current-suite, final image and live acceptance remain separate. The original six-observation comparison completed but regressed some large-value and warm paths, so A07/A21 remain open. This fixes the loader gate before further performance
or image acceptance; the frozen driver and expected responses remain unchanged.
This source review does not establish the final image, hosted CI, performance or
live release. Production remains on its original writer until those checks and
latest-data recovery pass.

## Secrets and RBAC

Supply `BOTRUS_JWT_SECRET` and `BOTRUS_SECRETS_KEY` from existing native Secret keys (recommended object `bortus-runtime` in app namespace). Legacy env names remain compatible. Signing material must be stable across restart; it is never auto-generated or persisted in SQLite.

Recommended chart inputs (create credentials independently, never Helm values):

| Container input | Native reference / value |
|---|---|
| BOTRUS_JWT_SECRET | secretKeyRef name bortus-runtime, key jwt-secret |
| BOTRUS_SECRETS_KEY | secretKeyRef name bortus-runtime, key lookup-token |
| DATABASE_URL | file:/data/bortus.db |
| BORTUS_SECRET_NAMESPACES | explicit comma-separated import namespaces |
| BORTUS_SECRET_ALIASES_FILE | /etc/bortus/aliases.json |
| Aliases volume | ConfigMap bortus-secret-aliases, key aliases.json, read-only mount |
| serviceAccountName | bortus in app namespace (recommended namespace bortus) |

Bind the app namespace's ServiceAccount from Roles in each imported namespace. Do not place runtime credential values in Helm values/ConfigMaps. Retain the actual import namespace/name/key map as the lookup reference contract.

Set `BORTUS_SECRET_NAMESPACES` to the imported application namespaces, comma-separated, plus `flux-system` for private Git credentials. Default: `default`. ServiceAccount: `bortus`. In **each allowed namespace**, Role with core resource `secrets`, verbs `get,list,create,update`; RoleBinding to the app namespace's `bortus` ServiceAccount. Key deletion is update and retains the object even when empty. No namespace creation or object deletion permission is needed. Other dashboard/Flux/exec RBAC is separate; no cluster-admin requirement is introduced.

Local: operator `KUBECONFIG` or `~/.kube/config`. In-cluster: mounted service-account token/CA and Kubernetes service host. Require HTTPS with verified certificates. No kubectl/host SSH key/DB bootstrap for Secret operations. Eight-second timeout; failed writes can have an unknown outcome, so read back before retrying.

Mount a metadata-only ConfigMap JSON file via `BORTUS_SECRET_ALIASES_FILE`, or register aliases using `/api/secret-references`. File format:

```json
[
  {"alias":"secret_gluetun_vpn_openvpn_user","namespace":"gluetun","name":"vpn","key":"openvpn_user"},
  {"alias":"legacy_vault_path/user","namespace":"gluetun","name":"vpn","key":"openvpn_user"}
]
```

Multiple aliases can reference a key; one alias cannot reference multiple targets. File/DB conflicts fail. No underscore parser. Import mapping must preserve every Vault/Docker alias explicitly; ConfigMap metadata can be committed, values cannot. Native Secrets need RBAC, encrypted etcd storage and tested recovery.

## Bootstrap/recovery

The fresh guarded release requires current encrypted configuration alongside
SQLite/native-volume/etcd checkpoints. The targeted32-file callable
`capture-kubernetes-recovery-config.py` uses the separately qualified Transport,
without historical-helper fallback. The integrated transport/writer passes75
root controls. A new actual32-file capture and authenticated ciphertext NAS
readback are accepted, with launcher0 and all owned processes closed. Both
prior refused outputs remain retained without replay/adoption. No plaintext
keys, mount settings or NAS permissions changed. See [migration operations](MIGRATION-OPERATIONS.md)
for exact scope, per-read consistency and independent restore limitations.

The [restored-consumer metadata fence](BORTUS-RESTORED-CONSUMER-FENCE.md)
checks distinct owned PVC/PV/Longhorn identities, two owned running RW replicas
and the sole qualified inert holder before and after a recovery read. It does
not prove historical completion or data equality. The
[recovery helper qualification](../evidence/bortus-restored-consumer-integration-20261011.json)
binds the integrated fence and shared-deadline, pinned-ciphertext and complete-row
comparison libraries to 303 local passing tests. Real watch continuity,
independent restored data equality, qualified image and final live acceptance
remain required; see [migration operations](MIGRATION-OPERATIONS.md).

The [restored-data composition](BORTUS-RESTORE-DATA.md) now joins those libraries
under one deadline and a separate durable data intent, preserving the borrowed
watch and leaving holder deletion to the executor. The scoped
[metadata reader](BORTUS-OPERATOR-MTLS.md) uses fresh verified TLS for each fixed
GET/complete LIST. Their integrated local suite passes 350 tests without skips;
local fixtures grant no live restore, image/admission or cutover acceptance.
See [integration evidence](../evidence/bortus-restore-data-metadata-integration-20261011.json).

The `/secrets` editor uses the existing dark dashboard layout, explicit value reveal and versioned writes. `/configuration` edits nonsecret variables separately. `/api/health/live` and `/api/health/ready` are exact public probe paths; readiness checks signing/lookup env, migrated SQLite and Kubernetes access across the namespace allowlist.

Keep operator kubeconfig, SSH keys and provisioning credentials independently available in a protected operator environment/offline store. Creating a cluster cannot depend on its unavailable Secrets. Container provisioning is disabled; migration runs Ansible externally. Local Ansible integration retains Bearer lookup for mapped native Secrets/nonsecret config. Supply bootstrap credentials independently, and use `no_log` for sensitive tasks. See `SECRETS-ENGINE.md`.

## Validation ownership

The `dafb41c3` explicit metadata-summary candidate has independently verified
[Windows functional evidence](../evidence/bortus-windows-functional-dafb-20261011.json):
48 focused cases, 205 units, lint/types and four production HTTP suites pass with
no skips. Root retains 25 original artifacts, 314 tested working files with raw
Git blob/mode bindings and 687 unchanged compiled outputs. The successful fresh
build from the earlier qualification attempt was reused after only a test
observer changed; its original failure and successful build terminal are retained.
One historical mixed-EOL test fixture has normalized-text equality only, with
separate tested/raw hashes. Root's default scan passes on exactly 264 raw production
inputs. The completed [paired and Linux qualification](../evidence/bortus-paired-performance-dafb-20261011.json)
also passes 205 Linux units and four HTTP suites without skips. Root verifies
50 original artifacts, 421 exported source blobs/modes and all 4,122 statistics.
Performance acceptance fails: the large native medians are slower, so release
image and final live acceptance remain pending; no production switch is implied.

An additional TLS transport test generates temporary self-signed test credentials with OpenSSL and talks to an HTTPS mock Kubernetes API using the real client/CA/token. It verifies create/read/update/list/delete and body-only value transport. This is still a mock API, not cluster acceptance. OpenSSL absence skips that test explicitly.

`npm run test:integration` requires a completed build. It migrates a fresh temporary SQLite DB, checks zero schema drift, starts the production standalone server on loopback, and validates real registration/roles, variable redaction, Bearer lookup, stale DB rejection, unavailable readiness, alias collisions and demotion enforcement. It uses fake credentials and an unavailable loopback Kubernetes endpoint, then removes its temporary DB. It never touches the operator DB or live cluster.

`npm test` covers imported reads/restart against a mock API, explicit aliases/underscored keys, metadata/type preservation, key/last-key deletion, collisions/races/immutability, outage/error redaction, sensitive DB classification, role/Bearer boundaries, exact middleware exceptions and insecure kubeconfig rejection. `npm run typecheck` and `npm run build` verify application integration. Actual results are recorded after execution below; Docker/live acceptance require the migration environment.

Mock tests establish API/alias/preservation behavior only. Live migration must prove imported values without logging them, authorization, lookup/edit/delete, readonly denial, conflict/outage behavior, restart persistence, no DB overwrite and recovery. Record image/live evidence separately; unit tests do not establish AC7 acceptance.

## Build blockers repaired

Alias registration rechecks any concurrently inserted DB mapping before returning success. The unique alias constraint rejects create races; mapping targets are never silently remapped.

The baseline included stale /cluster component imports, icon title props and shell-state comparisons that prevented type checking. Minimal compatibility corrections are included to make the container build usable; route/UI behavior remains documented in the existing API/resource guides. Private Flux credentials now use native API bodies, not SQLite or kubectl literals. seed-db.sh is retired because its old unauthenticated password flow is incompatible.

## Development validation recorded 2026-10-09

- npm test: 11 tests passed, 0 skipped; includes the real TLS client against mock API.
- npm run test:integration: production HTTP test passed against fresh migrated temporary SQLite; migrate diff reported an empty migration (no schema drift).
- npm run typecheck: passed after baseline compatibility fixes and test typing correction.
- npm run build: production Next 15.5.27 build passed; final check is repeated after the alias race recheck.
- npm run build: production Next 15.5.27 build passed after the alias race and hyphenated legacy alias changes. The final HTTP test also checks native-only writes using hyphenated legacy aliases.
- git diff --check: passed. No live Kubernetes/Vault/server operations were executed.
- Host runtime is Node v24.18.0/Windows; Docker specifies Node 22/Linux. Docker executable is unavailable here, so image build/run and cluster acceptance remain coordinator work.
- npm audit currently reports 16 advisories (12 high, 4 moderate, 0 critical) across the inherited/build dependency tree. The Next v15 patch removed the install-time critical advisory; a full dependency/major-version upgrade is outside this early migration dependency.

Container build runs without env files (excluded by .dockerignore). Local Next standalone output traces an .env file from the workspace; do not distribute that local directory. Build the image from the clean Docker context instead, and inject runtime keys from native Secret references.

The migration coordinator's new `scripts/migration/prepare-bortus-release-context.py` prepares a deterministic raw-Git context from an exact application commit, excluding local/generated/credential paths without reading excluded payloads. See [MIGRATION-OPERATIONS.md](MIGRATION-OPERATIONS.md) for output protection, bounds and refusal behavior. This is preparation only: source/context credential qualification, final source freeze, actual image build and deployment acceptance remain separate gates.

Previously tracked `.env`/`.env.local` files were removed from Git tracking during the original deployment. `.env.example` contains empty signing/lookup placeholders and nonsecret defaults; Git history is unchanged. The original bootstrap established separate native runtime credentials. The current guarded update must preserve the deployed signing and lookup material and existing accounts/roles; do not rotate those keys or invalidate sessions as a side effect of this release.

A temporary build without .env/signing/lookup credentials compiled and generated all pages successfully. Windows junction-based node_modules caused standalone tracing symlink warnings in that temporary copy; it is not an image/run proof. The normal worktree standalone build/HTTP test passed. The clean build also reports inherited jose JWE compression Edge-runtime warnings; JWT registration/authentication is covered by the passing production HTTP test.

The coordinator has verified the exact `32eb227e` [source context](../evidence/bortus-final-release-context-20261011.json): 263 included files, 11 forward migrations and a passing default source-only credential scan. Exclusive copies with identical hashes reside in the protected WSL operator runtime (0600 files/0700 input directory). Its completed [unchanged paired comparison](../evidence/bortus-paired-performance-32eb-20261011.json) fails performance acceptance, so this remains a retained candidate. A replacement must complete qualification before actual builder dispatch. This source transfer does not build, preload or deploy an image.

The selected [immutable release builder](BORTUS-RELEASE-IMAGE.md) validates the complete archive and manifest before SSH, records a durable intent and refuses existing runs/tags or automatic replay. A successful build config ID is not a qualified OCI runtime digest; image distribution, scanning and guarded live acceptance remain separate.

The separate [export and sequential preload helper](BORTUS-RELEASE-STAGING.md) verifies that completed builder receipt, exact Docker tag/config/source labels, bounded archive and each node's actual containerd root/selected manifest/config/layers. It records three-node staging separately from runtime qualification. Existing runs/tags and uncertain outcomes cannot be replayed or adopted. The actual immutable `7e30b9b4` inert-holder build/export and image scan are now recorded in the [holder receipt](../evidence/bortus-holder-source-image-7e30-20261011.json); zero Secret findings coexist with vulnerability findings. The [later three-node import and inert public-fixture runtime](../evidence/bortus-holder-preload-runtime-7e30-20261011.json) completed; read-only production-holder, guarded startup and data/recovery acceptance remain pending. Earlier local tooling fixtures keep their original preparatory scope.

The later `3f9b21cd` candidate has independently verified [Linux functional evidence](../evidence/bortus-linux-functional-3f9-20261011.json): 197 units and four HTTP suites pass with no skips, using read-only source/tests/build/dependencies and no network. Root verifies its paired source archives against all 420 baseline/candidate Git blobs and modes, plus the original logs and terminal records. Its [unchanged paired comparison](../evidence/bortus-paired-performance-3f9-20261011.json) still fails performance acceptance. It remains a retained candidate, with no release build or production switch.

The [callable independent restore coordinator](BORTUS-INDEPENDENT-RESTORE.md) now
composes the source, durable watch, admitted mutations, reader and encrypted full-row
comparison under one deadline. Its local qualification does not grant live
image/admission/data acceptance; actual operator execution remains required.

The [actual fresh BORTUS cold checkpoint](../evidence/bortus-cold-checkpoint-b473091bebef-20261011.json)
completed at 10:45:09 UTC on 2026-10-11. The immutable inert reader mounted the
original claim read-only; SQLite bytes went directly into authenticated age
ciphertext and the NAS copy matched. A cold snapshot and full encrypted 1 GiB
Longhorn NAS backup completed. Complete raw PodList name/UID checks prove reader
absence; the original writer is Ready on workernode2, its volume is healthy, and
Deployment/HelmRelease/Kustomization fields are restored. Capture exposed a
cross-node RWO resume-order defect; exact owned-reader removal and explicit
same-journal recovery completed without recapturing data or repeating creates.
All failed setup, transient-detach and controller-default-label attempts remain
recorded. A fresh read-only source preflight validates this closed checkpoint and
an absent masternode restore target. Complete SQLite row equality, independent
restoration, active admission and the final application release remain pending.

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

## Combined source and maintenance follow-through

The [root follow-through receipt](../evidence/bortus-app-maintenance-follow-through-20261011.json)
independently verifies application source c29fc8c: 333 raw Git blobs/modes, 20
exact original artifacts, 332 unchanged retained Linux source/test files and
4,262 compiled outputs. Fresh build, 214 units, lint/types and all four strict
HTTP suites exited zero with no skips; the owned supervisor and containers are
absent. This includes the Longhorn robustness-only health classification fix
and scalar known-field duplicate flags. It establishes functional correctness,
not the still-open A07/A21 performance gate or final image/live acceptance.

Chart docs-only follow-through 564fbc56894cca4d6b7934bff9c46311306cdc08 passed
main validation/promotion run 38137251240. At 11:55:44 UTC Flux source/owner are
Ready at that revision, BORTUS maintenance remains unchanged and every other
release is reconciled. Original writer/data/workload/RBAC/node preservation
checks pass. A prior 11:55:11 read caught four releases still reconciling their
unchanged packages; that actual nonpassing observation remains recorded. No
manual reconciliation, application restart, image upgrade, guard or adoption
was dispatched. The original completed cold checkpoint and data remain retained.

## Exact c29fc application image qualification

The [c29fc image receipt](../evidence/bortus-app-source-image-c29fc-20261011.json)
records the single source-bound build (12:06:21 UTC) and export (12:10:33 UTC)
on 2026-10-11. Its 265 production entries match independently verified raw Git
sources and the tested build context. The Docker config ID is
`sha256:b147db1da11fc66634954e12f15a4ef19fb3eb5e06b8b4e7d9676212caf39b4c`;
this is not a qualified OCI manifest or runtime digest. The archive's ordered
layers/config/labels match the completed receipt. Exact child owners are closed.

A fresh pinned Trivy 0.75.0 default image and image-config scan completed at
12:11:00 UTC with exit 1: zero Secret findings, 346 vulnerability entries
(125 Low, 142 Medium, 67 High, 11 Unknown, one Critical). Nineteen fixable entries
are in bundled kubectl, including four High. The Critical zlib finding has
scanner status `will_not_fix`; no suppression or application reachability
acceptance follows from that status. The earlier inert-holder assessment cannot
qualify the application image. At that scan checkpoint, runtime/schema fixtures were pending; the later
disposable fixture below records their scoped result. Kubectl remediation and
security review, A07/A21 performance, three-node runtime qualification, active guards,
independent complete-row recovery and final live acceptance stay open.
This qualification dispatched no application rollout, cluster mutation or
production data read; the original writer and data remain preserved.

## Disposable c29fc image runtime and synthetic forward migration

The [runtime receipt](../evidence/bortus-app-disposable-runtime-c29fc-20261011.json)
records one reviewed run completed at 12:18:51 UTC on 2026-10-11. Exact config
and five source labels matched before execution. Three disposable stages ran
with no network, read-only root, UID/GID1000, 2CPU/1GiB/128PID limits and bounded
tmpfs mounts: package inventory, fresh schema/restart and legacy1438 forward
migration/restart. Liveness returned 200; native-unavailable readiness returned503.
All11 migrations completed with zero schema drift and the expected account lock,
legacy principal and write/admin versus readonly/nonadmin policy bridge.

The legacy fixture uses the exact historical schema and seven raw migrations,
with every original application table populated. The unchanged comparator
checked all14 original tables, all original columns and complete row multisets:
21 source rows survived unchanged, including both users and the alias with an
underscored key. Added migration rows are separately recorded. SQLite integrity,
foreign keys, terminal migration state and new sessionVersion default0 passed.
These are synthetic rows; the fixture's arbitrary hashes do not establish login
behavior, and this is not production preservation or independent storage recovery.

Root freshly checked absence of all20 owned Linux process identities, the exact
Windows launcher and the complete owner-labelled Docker container list. Fixture
database frames remained in memory/tmpfs and cleanup completed. No production
PVC/database/native credentials, Kubernetes operation, image preload or rollout
was used. Application security, A07/A21, full-row production recovery, admission,
actual auth/UI/consumer acceptance and final live release remain separate gates.

## Current image staging checkpoint

The [exact c29fc preload](../evidence/bortus-app-preload-c29fc-20261011.json)
completed on all three nodes with matching archive/config/source labels and
OCI manifest068254f3. No application rollout followed. The separate later
digest-name alias and inert Kubernetes qualification are recorded below.
The [selected MiniZip metadata probe](../evidence/bortus-app-minizip-metadata-c29fc-20261011.json)
closed normally with owned cleanup; its narrow negative result does not accept
image security. The original legacy writer, suspended HelmRelease, grant-free
external bortus-kv principal and completed cold checkpoint remain the rollout
starting point. Production full-row recovery, principal/admission/schema
migration and actual auth/UI/consumer acceptance remain required.


## c29fc digest aliases and inert Kubernetes runtime completed

The [actual three-node runtime receipt](../evidence/bortus-app-three-node-runtime-c29fc-20261011.json)
records the separate alias-only operation at12:55:18 UTC and inert public
runtime at12:56:45 UTC on2026-10-11, both actual exit0. Each node verifies the
same config, five source labels, ordered layers and OCI manifest068254f3;
absent digest cache names were created without force or image replacement.
The image is referenced by its manifest digest, never its Docker config ID.

All three nodes ran Node22.23.3/Prisma6.19.3 against two public SQLite rows in
an8-MiB memory volume, with integrity and an8192-byte reader frame checked.
Pods used UID1000, read-only root, dropped capabilities and no service-account
token, production PVC or application entrypoint. Six owned execs completed.
UID/resourceVersion-preconditioned deletion and a fresh complete PodList prove
all three probe names/UIDs and the owner label absent. Root independently
verified all seven runtime process identities and the exact Windows launcher
absent, plus all24 frozen helper hashes unchanged. The original Deployment and
Ready writer retain their exact UIDs, resourceVersions and1438 image.

This qualifies c29fc as an inert public-fixture runtime only. The newer ab8d
application source needs its own final image qualification. No production-row
restore, active admission, original PVC schema migration, app rollout, security,
performance or live auth/UI/consumer acceptance follows from these probes.


## Separate ab8 handler qualification

The [independent handler/build review](../evidence/bortus-app-handler-production-ab8-20261011.json)
binds immutable application sourceab8d450 and evidence-only publicationbe8e891.
Three GET handlers use one fresh five-field account snapshot per handler:
variables and Secret aliases avoid a redundant role query; auth/session avoids
reading a full passwordHash-bearing account row. Middleware and handler
freshness checks remain independent. Mutations, native Secret behavior and the
production parser are unchanged by this patch. This is qualified application
source in the separate worktree; the coordinator frontend and live1438 writer
have not been replaced.

One actual pinned LinuxNode22 run passed a fresh production build, the four
original strict HTTP tests and13 supplemental affected-route checks. Root
independently verifies333 raw source/test bindings,67 unchanged original tests,
4262 unchanged compiled files,15 exact published originals and all11 original
Linux artifacts (the ZIP also contains its added complete proof). The exact
supervisor and all owned containers are absent. No image build, full unit rerun,
paired performance or live auth/consumer acceptance is implied.

The complete265-file raw production default scan has exit0/zero findings.
The separate complete23-file publication default scan retains exit1 and one
individually verified historical three-word public prose match, with no
suppression or untriaged selected finding. Two older whole-history provenance
gaps remain unresolved. Earlier partial scan/exporter failures remain preserved
and unqualified. Final image and A07/A21 performance acceptance remain open.


## Accepted legacy image digest-cache maintenance prerequisite

The [actual legacy cache receipt](../evidence/bortus-legacy-digest-cache-20261011.json)
binds the retained1438 archive/config and15 ordered layers to manifest3b076
on all three nodes. Source1438 is recorded historical provenance only; this
older build is not retroactively granted the new five-label qualification.
The first operation retained actual exit1 after its first node's tag succeeded:
a second verification reused an exclusive journal filename. Root inspected its
remote intent/source-after verification and local/remote wrapper closure;
the partial receipt was never adopted as three-node success or replayed.

A reviewed corrected wrapper used distinct source/alias stage names and a fresh
owner. Actual exit0 at13:28:52 UTC verified the first exact existing alias and
created the two absent aliases without force. Each source and alias retained
config/platform/layer identity. All four Linux identities and exact Windows
launcher are absent; all45 frozen preparation files were independently rehashed.
There was no import, application startup, production schema or Secret operation.

At the pre-rollout checkpoint, the original Ready writer reported literal
config imageIDa8f40 with a mutable tag. That is not normalized into the required repo@3b076 runtime proof. A
separate disposable public-fixture qualification is required before CI/Flux
pins the same accepted legacy bytes. This is a pre-schema maintenance step;
1438 cannot be a final KV rollback image and must leave every active allowlist
before a forward-schema entrypoint can touch the original claim. Full-row
production restoration, final image/performance/security and live acceptance
remain separate requirements.


## Accepted legacy digest inert runtime completed

The [actual legacy runtime receipt](../evidence/bortus-legacy-digest-runtime-20261011.json)
records one public-only Kubernetes qualification completed at13:33:19 UTC,
actual exit0. All three Pods used literal repo@3b076 spec and actual imageID;
Node22.23.3/Prisma6.19.3, two public SQLite rows, integrity and8192-byte reader
framing pass. It uses the same frozen fixture/reader contract with no token,
production PVC, native Secret value or application entrypoint. Exact cleanup
uses UID/resourceVersion deletion plus independently fresh complete PodList
absence. Root verifies all seven Linux processes/exact Windows launcher absent
and all27 helper inputs unchanged. The original Deployment/Ready writer's UIDs,
resourceVersions and mutable spec image remain identical before and after.

This is current accepted-artifact runtime proof for the proposed pre-schema
legacy digest pin. Historical source qualification and modern five-label
provenance remain distinct. At this13:33 checkpoint, CI/Flux publication and
observation of the replacement writer, storage/controller identities and
credential references were pending; the subsequent completed rollout is below. It is not production-row preservation, schema-forward, active
admission or final KV/performance/security acceptance.


## 2026-10-11 13:48 UTC: legacy digest CI→Flux rollout verified

The [actual rollout receipt](../evidence/bortus-legacy-digest-flux-rollout-20261011.json)
records PR #2 merged as `182eafd4da4cda56b2a846d0c5f067e527eb79c4`.
Its tree exactly equals reviewed head `f15f1e03`; main run `38144292988`
completed validation and promotion successfully. Flux source and migration
owner are Ready at that exact validated revision with prune/force false.
BORTUS HelmRelease is resumed, UpgradeSucceeded at generation9. Its sole Ready
writer is `bortus-5c55f6d5b5-67mnk` on workernode2, with literal spec and
actual imageID `docker.io/library/bortus@sha256:3b076fb9b7fb64fd760691c0120f29d4e363d4ccb9910a596ff211bfc3ea0879`.
The complete PodList shows the previous writer name and UID absent. This
supersedes the earlier mutable-tag/config-only writer observation.

Deployment, Flux owner/source, HelmRelease, PVC/PV and external principal UIDs
are preserved. The claim remains Bound, its PV Retain, and Longhorn is encrypted
and healthy with two running replicas. Existing credential references and the
legacy service account remain unchanged. The external `bortus-kv` principal
still has zero grants and automount false; all six guard objects remain absent.
All three nodes and the other33 releases are Ready with current observed
generations. No manual reconcile, native Secret value or production DB read was
used. This is accepted-artifact maintenance, not production-row restoration,
schema-forward, new KV adoption, final app security/performance or live auth/UI
acceptance. Next guard publication must separately resuspend BORTUS and retain
both accepted legacy and qualified inert images only for pre-schema restoration;
legacy must leave all allowlists before any forward-schema entrypoint.

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

## 2026-10-11: deployment-action coercion fix reviewed

The [root review](../evidence/bortus-deployment-action-root-review-20261011.json)
verifies source 42f2f864/final evidence dbc3c2a9: 343 exact raw Git files, 29
original artifacts, eight executed source/dependency bindings and 22 checked
document originals. The actual transpiled route previously accepted an array
action and returned 200 after dispatching rollout restart; that negative result
is retained. The corrected handler requires one literal supported string and
returns fixed 400 for coerced/inherited/unknown shapes before command dispatch.

Six focused route controls, fresh noEmit types and selected zero-warning lint
pass. The first test-only getter oracle failure remains retained. All four valid
actions retain their exact structured arguments/15-second timeout, authorization
and typed failures. The selected six-file default scan reports one independently
reviewed unchanged public prose span, zero untriaged findings and two historical
provenance findings still open. This candidate has no fresh production build/HTTP,
real kubectl/cluster, image or performance qualification; broad A04/A05 acceptance
remains open. It is not deployed.

The [root current metadata assembler qualification](../evidence/bortus-current-assembler-root-20261011.json) passes 130 local controls on the frozen dependency composition; all seven owned children exited and every selected source remained unchanged. It borrows the operator transport and source fence, requires fresh publication/guard observations, two distinct schema receipts per callback, and image/source verification before and after assembly under the original shared 300-second deadline. Completed43 probe evidence stays explicitly static. Actual three-node image/source transport wiring and independent whole-row restore remain pending; this local result grants no application startup or forward migration.

The [root current source/image verification receipt](../evidence/bortus-current-image-root-20261011.json) records 154 local controls and one actual isolated read-only callback passing in 17.731 seconds. Twelve sequential SSH inspections freshly verify manifest/config hashes, source labels, ordered descriptors and cache blob presence on the three Ready nodes; all owned SSH children are absent. Two new schema receipts and exact current writer/storage/guard pins accompany the explicitly reused completed43 transcript. Layer bytes and the prior inert runtime fixture are not reexecuted. The timing-only callback trace correctly remains incomplete/refused because only one of six calls ran; its graph and deadline are never reused. This establishes timing and current prerequisites, not independent whole-row recovery or application startup. The initial v19 missing fixture-directory failure is retained; frozen v20 suites passed on unchanged exact sources.

The [actual independent b473 recovery proof](../evidence/bortus-independent-live-b473-20261011.json) completed at 17:41:44 UTC in 189.566 seconds under the original 300-second deadline. The separately restored encrypted Longhorn volume passed the complete SQLite recovery-row comparison against the authenticated cold archive. Both tmpfs copies were cleaned; all four operations, six callbacks, 72 fresh SSH inspections and twelve schema receipts completed. Same-UID watch evidence records restore flags true/true at RV1220694 then true/false at RV1220836, with no later regression. The inert reader is absent by fresh named404 and complete PodList UID/name checks; its StorageClass remains retained and its PVC remains Bound. Fresh post-run metadata confirms the original Ready writer/template/storage and six guard UID/RV/spec pins, plus current Ready Flux revision. The first post-review used the wrong lowercase standby key and refused; the corrected exact Longhorn `Standby` review passed without replaying restoration. Static completed43 outcomes and prior image runtime proof remain explicitly reused. Exact schema invocation floors are enforced by executed source, not separately reconstructed from retained scalar fields. Original coordinator overall flags remain false; this separate receipt accepts the cold-baseline recovery gate only. Latest-data capture, updated app build/performance/image, forward schema migration and final rollback/live acceptance remain pending. Gluster/Vault/Consul originals are retained.

## 2026-10-11: mutation lifetime source review

The [root lifecycle review](../evidence/bortus-lifecycle-root-review-20261011.json)
binds the successive resource, YAML and Settings fixes through candidate
`4ae9f5c`. Independent byte review verifies 379 unique Git blobs, 1,032
frontend bindings, 143 retained originals and 66 documentation relations.
The final affected controls pass 11, 14 and 7 respectively, alongside fresh
types and corrected selected lint. Resource callbacks reject stale targets,
navigation and permissions; YAML replacement and close/reopen cannot inherit
an old save; Settings permission withdrawal and restoration cannot revive
an earlier mutation or retry it automatically.

Original negative and fixture/lint failures remain retained. The exact source
snapshot for one intermediate three-test Settings run is missing; the final
four Settings/seven affected controls have verified source bindings. Each
selected default scan retains one independently reviewed unchanged prose
finding, and two historical provenance findings remain unresolved. This accepts
source-local behavior only. A fresh production build, affected browser checks,
unchanged paired performance, final image and live upgrade remain pending.
The original running application and data have not been changed by this review.

The separately prepared [4ae9 release context](../evidence/bortus-release-context-4ae9-20261011.json) contains 267 production files and eleven migrations. Every archived byte, Git blob and mode independently matches the final raw-source receipt. The full production-source default credential scan returns zero findings; this excludes docs/tests and does not resolve historical provenance findings. No image was built or deployed, and functional/performance acceptance remains separate.

The fresh [4ae9 Linux functional qualification](../evidence/bortus-functional-4ae9-root-20261011.json) passed its production build, 262 unit tests without skips, whole-source lint, fresh type checking and six existing HTTP/process controls. Root independently rehashed 344 executed sources, 77 test/helpers, 4,262 compiled files and all five original stage logs against the final 345 raw Git frontend bindings. All observed owned processes and containers are absent. The first read-only root count assertion accidentally included 22 doc rows; the corrected frontend-only check passed without rerunning qualification. Browser lifecycle, universal action, paired performance, immutable final image and live release gates remain separate and pending. Production remains unchanged.


The [actual immutable 4ae9 image receipt](../evidence/bortus-app-source-image-4ae9-20261011.json) records build0 at18:28:26 UTC, export0, exact five source labels, complete independently verified linux/amd64 archive/config/ordered-layer hashes and observed owned-process closure. Default Trivy0.75 scanning completed with exit1:346 findings (1critical,67high), including four fixable high findings in kubectl, and zero secrets. The critical zlib1g finding is individually classified using Debian's Bookworm binary-package assessment and actual archive package/library contents; its original count remains retained. This does not accept the entire image. No application/image runtime or deployment occurred. Patched CLI selection, remaining security/performance, latest-data capture and final schema/admission/principal/live/rollback gates remain open.


## Root review of final4ae9 browser and universal action evidence

The [independent root receipt](../evidence/bortus-browser-actions-4ae9-root-20261011.json) binds all264 functional/browser and99 universal originals by raw SHA. The five bounded compiled production route groups passed27 actions,513 recorded control labels and270 failure outcomes, including exact single-invocation argv, four nonzero-output combinations, missing executable, real timeouts, both output bounds, RBAC/NotFound and fresh authorization before input. PV reclaim retains its documented207 partial-result semantics. Two failed harness setup attempts are retained. Fresh root verification finds all344 executed sources and4262 compiled outputs unchanged, every observed universal child absent and no owned containers.

Browser scope comprises seven completed assertions in a run that later failed a Secrets locator, one completed Secrets assertion in a run that later failed a Flux locator, and two completed Flux/Settings assertions in the final terminal0 run. This is ten completed checks across7+1+2, not one uninterrupted ten-check pass. The six held success/error action classes fence stale callbacks and private state after fresh withdrawal and permission ABA; current Configuration/Users/KV/Secrets/Flux/Settings paths retain task completion and failure drafts. Only the exact Next framework route-announcer is excluded from application-alert assertions. All original failures remain retained. Browser request-event arrays are empty, so this does not establish physical request/replay counts. Controlled CLI/localhost fixtures do not establish real cluster action acceptance. Performance, patched-image security, latest-data migration and live/rollback acceptance remain separate open gates.


## 2026-10-12: final4ae9 performance execution closed, regression gate failed

The [independent root comparison review](../evidence/bortus-performance-4ae9-root-20261012.json) verifies40 originals,424 raw Git blobs/modes and actual immutable baseline157/candidate267-file tar bytes. The unchanged original runner completed six unique alternating observations, three per source, with all assertions. Root recomputed330 workflow/HTTP summary distributions, confirms all six native metadata profiles returned the complete expected inventory, and observed supervisor/runner absence. Execution success does not establish A07/A21 acceptance: native HTTP latency regresses at200/1000objects and large-value cases; some warm1000-object tails improve. The10,000-Pod baseline false-empty cases remain ineligible for equivalent latency claims; native metadata comparisons independently remain valid. The first root read placed the native phase oracle on its request entry; correction used the actual phase field without rerunning measurement. Original limits/oracles/source remain unchanged. Safe performance remediation, final runtime/security, latest-data migration and live/rollback acceptance stay open.


## 2026-10-12: primary package triage and pinned custom-build inputs

The [primary remediation receipt](../evidence/bortus-image-remediation-research-20261012.json) retains all20 unique Debian High/Critical IDs from the default4ae9 scan and current Debian release tables. All20 primary requests succeeded. Debian13 contains fixes for some Bookworm findings (for example [util-linux target-path redirection](https://security-tracker.debian.org/tracker/CVE-2026-53613) and [OpenSSL DTLS retransmission](https://security-tracker.debian.org/tracker/CVE-2026-84782)); several other findings remain vulnerable there. A base upgrade alone cannot establish security acceptance. No suppression or change to original346 findings is applied.

Root downloaded the exact upstream Kubernetes1.37.1 source42196261bytes and Go1.26.9 Linuxamd64 toolchain66935201bytes onto the separate build host, then independently rehashed both and observed the downloader absent. The source checksum remainsd58492a0… and Go42d158b4…; full bindings are in the receipt. Actual source layout is flat with two file and three directory symlinks, unlike the draft fixture; those cases are corrected before compilation. Inputs are public archives, no cluster or credential mount is involved. Custom compilation, vendor diff review, binary scan, final source/image injection and runtime acceptance remain pending.


The separate [custom kubectl security build contract](BORTUS-KUBECTL-SECURITY-BUILD.md)
consumes pinned upstream1.37.1 source and Go1.26.9 archives, with reviewed
x/net0.60.0 and transitive pins. It is a local-only candidate for a custom
binary, not an upstream1.37.2 release or image security pass. Existing Dockerfile
and release-builder defaults remain unchanged pending separately qualified
source-linked injection and actual image/runtime acceptance.


Custom kubectl build receipts keep detailed source/cache diffs in a bounded,
protected fsynced metadata sidecar and full before/after ZIP; only count/SHA/path
stay in the1MiB ownership record. Public archive modes are preserved inside the
private run. The first actual attempt failed before compiler dispatch at the
record bound; earlier fixtures did not qualify its cache scale. Existing image
contracts and defaults remain unchanged; see [custom build](BORTUS-KUBECTL-SECURITY-BUILD.md).

## 2026-10-12 05:31 UTC: actual custom kubectl build and component scan

The [actual root receipt](../evidence/bortus-kubectl-actual-build-root-20261012.json) records all12 build stages with exit0, completed at05:18:10UTC. The 61,960,354-byte binary is a custom `v1.37.1-bortus.security.1-dirty`, built with Go1.26.9 and x/net0.60.0; SHA-256 `a3c4741294f061550b30bd2e3f357197ffbac37eefc5a45d686fe9cd29032b75`. All observed build command, helper and supervisor PIDs are absent.

Root independently verifies34 transferred originals, complete CRC-valid original/diff ZIPs and32,084 changed-file byte identities. All31,916 paths remain retained, including31,723 generated cache paths; faithful archive modes eliminate artificial mode-only changes. The detailed sidecar is12,741,184bytes while the main completion record is8,902bytes. Source changes outside generated cache are module records and x/* vendor files, including upstream-selected sync/tools/mod transitives.

Default Trivy0.75 component scan returns0 with zero vulnerability or secret findings and explicitly analyzes the kubectl Go binary and90 packages. The first protected copy had mode600 and yielded no Go analysis; that report is retained and rejected. A new owned scan uses the unchanged binary with its original0755 mode inside a private directory, confirms Go1.26.9/x/net0.60.0, retains all severities and uses no suppressions. The original image scan remains346 findings (1Critical/67High). This component result does not accept a final image, deployment, performance, schema migration or live engine. Source-linked image injection, full image/runtime gates and the latest-data cutover remain open.


A separate [patched ELF image adapter](BORTUS-PATCHED-KUBECTL-IMAGE.md) can bind a
completed custom kubectl receipt and exact ELF to a named BuildKit context while
keeping the raw Git source tar and five source labels. Its protected injection
sidecar is required for root qualification; existing export/preload alone does
not qualify the patch. Default builder and frontend Dockerfile stay unchanged;
actual binary/image/security/runtime acceptance remains separately required.

## 2026-10-12: integrated patched-binary image adapter

The [root qualification](../evidence/bortus-patched-kubectl-image-root-20261012.json) independently verifies all10 raw native files,50 retained originals and1,879 CRC-valid ZIP members. Three source/test files and the dedicated image-adapter doc are integrated; later root build/scan sections are preserved. All21 POSIX orchestration controls pass without skips in2.510s (2.620s wall), with seven original sources unchanged and the owned test child reaped. The first root freeze check incorrectly counted newly generated test-fixture copies as original sources; that failed harness result remains retained, and no source/test behavior was altered.

Root separately validates all six actual compiled artifacts in3.138s: complete247,076,441-byte source diff ZIP,12,741,184-byte metadata sidecar/all31,916 paths, ELF, completed build receipt, actual version and Go build metadata. Their identities and bytes remain unchanged. These checks call no build, transfer, SSH or Docker operation. The default builder/export/five-label contracts and frontend Dockerfile remain unchanged.

A future source-linked build must carry both completed image and injection receipts, exact owner/config/context identities and actual launcher terminal0. The adapter supplies the separately verified kubectl through a named BuildKit context and checks its SHA in the image consumer; interrupted or mismatched outcomes cannot qualify. Actual consumer/source image construction, full image/runtime/performance, latest-data and live schema/RBAC/admission/rollback gates remain open.


[Current root qualification](../evidence/bortus-canonical-cifs-root-20261012.json)
verifies canonical deny-all policy generation, fixed typed LIST endpoints and
the closed configuration/etcd ciphertext-writer factory:58 local controls pass
without skips or ResourceWarnings on164 unchanged private POSIX source files.
Fourteen configuration cases include exact CIFS mode handling and closed-prefix
refusals. Retained server dry-run metadata proves exact admitted policy spec
and typed complete collections, with no persistent resource ownership inferred.
The streaming consumer and narrow CIFS creator-close correction are now integrated and pass75 root controls. The [fresh actual configuration receipt](../evidence/bortus-kubernetes-config-actual-20261012.json) accepts only the32-file age archive and exact NAS ciphertext readback. The raw etcd checkpoint and complete encrypted-registry restore now have [actual acceptance](../evidence/bortus-etcd-actual-recovery-root-20261012.json); API decryption, Longhorn recovery and the guarded app rollout remain pending. Both refused archives remain retained without replay/adoption.


The [second retained actual configuration run](../evidence/bortus-config-close-refusal-20261012.json)
authenticated its32-file operator archive, then refused the CIFS creator-close/
reopen timestamp fence. The NAS ciphertext hash matches; the refused run remains
unaccepted without replay/adoption. A distinct encrypted public fixture proves
both timestamps advance3.7178ms on close while device/inode/owner/mode/link-count/
size and full mount identity stay exact. The narrow CIFS-boundary correction is integrated: it pins a full reopened
fingerprint and preserves strict full readback/POSIX/owner/inode/hash/mount/
deadline checks. The new successful configuration archive is distinct from
this retained failed run; no production etcd snapshot is claimed.

The [approved eight-request diagnostic](../evidence/bortus-eight-request-evaluation-root-20261012.json) passes all seven admission/cancellation/size/item/namespace/generic-metadata controls and all six unchanged benchmark driver assertions. Root verifies all56 retained originals and both CRC-valid handoff ZIPs. One measured observation uses the corrected indexed native flat-summary parser with an eight-request cap, original six profiles/driver and2CPU/1GiB limits; production source remains unchanged. The1000-item path measures76.311ms versus96.871ms for the prior four-request flat prototype and80.814ms for the matched old baseline. The25-large-value path remains237.754ms versus187.792ms baseline, and3-large-values161.629ms versus156.379ms baseline. Sequential size-refusal/fallback and fixture serialization dominate those remaining gaps. This is an evaluation result, not a fresh paired no-regression acceptance, source adoption or final release. The initial fixture loader failure is retained; only missing declared chunk registration was corrected before the passing controls.

## 2026-10-12: eight-request paired comparison verified; performance remains open

[Independent comparison review](../evidence/bortus-performance-eight-root-20261012.json) verifies36 originals,429 raw Git blobs/modes and both actual production tar archives. All six unique alternating observations pass the original inventory assertions; root independently recomputes1320 reported distributions and observes supervisor/runner absence. Both sources used the same pinned full Node22 image and2CPU/1GiB measurement limits. No driver, dataset, limit or oracle changed.

Native Secret-list median HTTP milliseconds, baseline → candidate:

| Case | Baseline | Eight requests | Native API calls |
|---|---:|---:|---|
|334 small records|99.443|78.369|18 →18|
|200 records|61.745|65.986|18 →18|
|1,000 records|71.387|71.292|18 →18|
|10,000 records|245.394|169.477|54 →54|
|25 large records|172.868|229.442|18 →21|
|3 maximum-size records|118.893|165.136|18 →20|

All native inventories are complete. Large-value cases make extra page requests; some warm/concurrent Pod results regress. A07/A21 remain failed/open, with every original tail/range retained. The baseline10,000-Pod false-empty result is ineligible for equivalent-success latency comparisons. Whole-fixture CPU and peak memory include the fixture producer/driver, so they are not isolated app costs. This comparison authorizes no performance pass, final image or live rollout; remediation continues on the unchanged privacy/namespace/size/deadline contract.

## 2026-10-12: eighteen-request evaluation approved; rejected prototypes retained

The user approved evaluating eighteen concurrent native Secret-list requests with the existing 4 MiB page, 32 MiB aggregate, 10,000-item, deadline, namespace, fresh-authorization and redaction contracts. Production remains at eight requests. Controls and one bounded original-profile observation precede any full paired comparison; approval grants no rollout or performance pass.

[Root diagnostic review](../evidence/bortus-rejected-performance-prototypes-root-20261012.json) verifies 42 originals and ten raw publication files, then four clarification blobs/modes with unchanged frontend. Scalar C prefix counting costs 4.589 ms versus 1.665 ms JavaScript for the retained large fixture and is rejected. Exact original ASCII Pod-response pre-encoding regresses the 3- and 200-row fixtures; its 1,000-row saving does not establish an HTTP acceptance pass, so global adoption is rejected. All nine alternating batches remain recorded. These are medians of batch means, not HTTP latency tails. The 2,533 prefix cases, 32 multibyte controls and 35 exact ASCII response controls establish scoped equivalence only. Initial noexec setup and preparation failures remain retained.

The generator proof combines two disjoint original driver byte slices (1223:1263 and 9451:10128). The reported generator field hashes the second slice only. Root's initial contiguous-source assumption refused and was corrected without rerunning measurements. No original driver bytes or production behavior changed. A07/A21 remain open.

## 2026-10-12: eighteen-request evaluation completed without adoption

The [independent root review](../evidence/bortus-eighteen-request-evaluation-root-20261012.json) verifies all 61 retained originals, 1,640 current source/compiled hashes, the sole compiled 8-to-18 anchor, eight passing control sections and six actual native ELF loads. All six original inventory oracles pass, and the original driver is unchanged. Root confirms observed process absence and a fresh successful query proving the owned container absent.

The single native-list observation measures 123.791 ms (334 small records), 77.500 ms (200), 105.643 ms (1,000), 142.666 ms (10,000), 337.225 ms (25 large) and 253.744 ms (three largest). API calls remain 18/18/18/54/21/20. This is one unpaired observation; prior eight-request paired medians are reference values, not matched causal comparisons. It does not demonstrate broad improvement or satisfy A07/A21. The candidate source cap stays eight and no live deployment changes. Missing dependency chunks and then wrong native-loader cwd caused two retained control setup failures; corrected controls retain the mandatory actual native-load assertion. Root metadata path/oracle-field read errors were corrected without replaying measurement.

The user approved evaluating a16 MiB ceiling for Secret metadata lists on2026-10-12. The experiment retains the32 MiB aggregate,10,000-item, deadline, namespace, authorization, redaction and runtime limits; generic/non-flat responses stay at4 MiB and candidate concurrency stays eight. Both matching transport/native-selector input guards may change only in an isolated prototype. This authorizes evaluation only; production source remains4 MiB and no adoption or deployment is approved by this evaluation.

## 2026-10-12: default e50 image scan completed; security review remains open

The [independent root scan review](../evidence/bortus-patched-app-security-e50-root-20261012.json) verifies all 13 original artifacts, raw report counts/config ID, exact default vulnerability/secret/image-config flags, closed environment, unchanged receipt/archive/tool pins and actual scanner/supervisor absence. Trivy exits 1 with 162 Debian 13.7 findings: 43 High, 58 Medium, 60 Low and one Unknown. It reports zero Critical, fixable or secret findings. Node.js and the patched kubectl target report zero vulnerability findings.

Every original finding remains retained without suppression. Zero available fixes does not establish absence of risk. Debian advisory and actual component/exploit-path review remains separate, and no full-image security, runtime or deployment acceptance is granted.
## 2026-10-12: fresh canonical e50 functional qualification

The [root canonical qualification](../evidence/bortus-canonical-e50-functional-root-20261012.json) independently verifies383 originals,353 exact Git source byte/mode bindings and4263 current compiled hashes. Production build, actual native load, zero-warning lint, fresh types,267 units and eight integrations pass with no skips. Root freshly proves seven local process identities and five owned containers absent. This closes the fresh local functional check for e50; it grants no hosted CI, new browser, performance, final image/security, schema migration or live rollout acceptance. The eighteen-request experiment remains unadopted and the sixteen-MiB single observation is independently reviewed; source fallback parity/full functional/paired acceptance remain pending with no adoption or deployment.


The [root16 MiB observation review](../evidence/bortus-metadata16-evaluation-root-20261012.json) independently verifies74 retained originals,4616 unchanged current source/compiled hashes, six actual native-load records among15 module records, all six exact inventories,28 absent process identities and three absent owned containers. Large-profile phase wall observations were149.4 ms and123.5 ms (literal HTTP146.5 ms and120.6 ms); peak memory477.3 MiB with zero recorded memory events. The retained control composition is seven sections before the v1 fixture failure plus the corrected remainder/corpus/generic v2, rather than one uninterrupted pass. This completes the single evaluation observation only. The root authorized a source candidate with distinct portable-flat16 parity and unchanged generic4 MiB rules for qualification; full functional proof and unchanged three alternating pairs remain required before performance acceptance. Candidate/source concurrency eight is not a measured live setting. No production adoption or deployment.


The [root partial-package metadata review](../evidence/bortus-chisel-scanner-metadata-root-20261012.json) compares all17 scanner blocks to the exact signed package control bytes with explicit partial-package/slice markers. An isolated scanner report detects Ubuntu24.04 and all17 exact versions after independently recombining epoch/upstream/revision, and reports five MEDIUM findings with zero HIGH/CRITICAL/secret findings in this rootfs-only input. All original regular file bytes and the input rootfs remain unchanged; six absolute links were mapped only in a confined scanner snapshot. The retained postscan checker failed on its version-field assumption before durably recording the scanner returncode, so this is report visibility evidence, not a passed scanner gate. No Node/app/kubectl runtime or complete application image is tested. The final image requires its own full default scan and compatibility proof; no scanner replay, exception acceptance or deployment follows from this report.


The [root current utility cache read](../evidence/bortus-utility-cache-current-root-20261012.json) completes authenticated fixed CTR discovery with actual exit0 and proves the frozen `docker.io/library/bortus@sha256:068254f38c47f99fd35604185a806a92147d934010329638b32adb5c19802c90` reference absent on the master. This BORTUS image is used solely as the inert Node utility; it is not an official Node image. The earlier unprivileged permission refusal does not establish absence. Root independently verifies two local identities and the remote CTR identity absent. No pull/export/tag/import, Pod, policy, ephemeral container or version probe is dispatched. Original-image compatibility therefore remains open until an exact verified resident reference is established; tracing existing artifact/alias provenance is preparation only. The private no-echo credential bridge is unchanged, and the retained staging/validator failures grant no cache claim.


The [root flat16 source review](../evidence/bortus-flat16-source-focused-root-20261012.json) independently verifies the evaluation commit2216fa62acf642862517dbda884c345197e540ed:363 raw Git byte/mode/blob bindings (355 frontend files),78 retained originals and all355 exact/explicit CRLF-to-LF working-source relations. Four production files add only flat16 client/native bounds and a distinct portable-flat16 entry sharing the unchanged generic4 grammar. Seventeen focused controls, fresh types and zero-warning lint pass; the exact native ELF matches the approved prototype. Retained V2 type failure and V3 repeated focused stage remain visible. Root independently scans all14 changed raw files with defaults and records0 findings. Fresh full raw-source functional and unchanged alternating pairs remain pending; this commits evaluation evidence without production adoption or deployment.


The [root canonical flat16 functional review](../evidence/bortus-flat16-functional-root-20261012.json) independently verifies381 originals,355 exact source/mode/current-hash bindings,4263 current compiled hashes,11 absent owned process identities and five absent owned containers for2216fa62acf642862517dbda884c345197e540ed. All five stages exit0: fresh install/standalone build, actual native load, lint/fresh nonincremental types,271 units and eight original strict HTTP/process/compiled-native integrations with no skips. The native ELF matches the approved16 MiB prototype. A transient status-read timeout is retained as observation failure, without restart or replacement. This closes local functional qualification only. Root refused the first paired preparation before dispatch because it still names unavailable `/mnt/c` paths; a protected exact-object Linux repository/exporter composition and lifecycle must be reviewed before the original three alternating pairs. A07/A21, final image/security/hosted CI, schema/RBAC/live and rollback remain open. No production adoption or deployment.


The [root cache refusal review](../evidence/bortus-utility-cache-refusal-root-20261012.json) retains the single actual cache-name attempt with exit1 and its independent read-only journal observation with exit0. The durable journal records a refusal after one successful read-only CTR job, with no alias intent or alias job; that remote identity and all four local actor/observer identities are freshly absent. The actor is not replayed. This establishes no new cache-name state or original-image execution acceptance. A separate bounded read-only discriminator must distinguish image-list parsing from the exact resident source-name prerequisite before further cache work; no Pod, policy, ephemeral container or image version execution follows from this refusal.


The [root paired preflight review](../evidence/bortus-flat16-paired-preflight-root-20261012.json) verifies511 lifecycle-control originals and61 exact frozen preparation inputs, followed by13 actual failed-owner originals. The corrected wrapper passed all14 POSIX controls, including stale-leader signal refusal; the retained first control run passed11/13 with two failures. The actual original comparison stops after image inspection because the unchanged source exporter requires a checksum-verified Linux Gitleaks executable at its fixed charts path, which was not staged. Actual runner/supervisor exit1, zero source builds/observations and fresh absence of three process identities are preserved. A distinct preparation must add the exact scanner and its provenance; the failed owner is never replayed. No performance, image or rollout acceptance follows.


The [root fixed cache discriminator](../evidence/bortus-utility-cache-discriminator-root-20261012.json) completes one read-only images-list command with actual controller/SSH/CTR exit0 and owned-child reaping. The45,570-byte table is parsed by the unchanged actor parser as104 images; both exact c29 source tags and the frozen068 utility digest reference are absent in this current sample. Only bounded fixed-name flags and public hashes are retained, and both local process identities are independently absent. This distinct read cannot retrospectively prove the earlier unretained table or original refusal cause. No import, alias, pull or image/resource execution occurs. Exact retained artifact provenance and a separately reviewed once-only preload are required before original-image compatibility testing; no profile or utility substitution is approved.


The [root flat16 paired comparison](../evidence/bortus-flat16-paired-root-20261012.json) independently verifies 101 retained originals, 429 raw Git blob/mode/actual-tar bindings and all 1,386 reported distributions. Both builds and all six original alternating observations exit 0; all native inventories are complete, and 11 process identities are freshly absent. The same frozen driver, exporter, datasets, runtime limits and oracles are retained. Native cold HTTP medians (baseline to candidate, milliseconds) are 100.94 to 82.82 for 334 records, 71.08 to 73.53 for 200, 77.63 to 77.71 for 1,000, 289.58 to 181.56 for 10,000, 194.19 to 162.76 for 25 large records and 136.89 to 122.33 forthree maximum-size records. Large cases now require 18 calls for both sources, eliminating extra page retries. Whole-fixture median CPU falls 39.13 to 33.62 seconds while peak memory rises 358.54 to 421.11 MiB; these include fixture production and do not isolate application costs. Warm/concurrent Pod, configuration, alias and readiness outcomes remain mixed; no trimming, tolerance or significance claim is introduced. Baseline incomplete 10,000-Pod results and differing Services-after-Pods cache/envelope semantics are noncomparative. A07/A21 remain failed/open, with no source adoption, final image or deployment acceptance. The prior export-prerequisite failure and corrected preparation are preserved.


On 2026-10-12 the user approved the [reviewed combined eighteen-request/flat16 prototype](../evidence/bortus-combined18-flat16-proposal-root-20261012.json). Root verifies 16 exact raw source bindings and three current compiled/native bindings. The isolated wrapper changes exactly one compiled `let e=8;class f` anchor to18, covering global native request admission, namespace workers and operation-owned Agent limits together; original source and compiled files stay unchanged. Flat metadata16 MiB, generic4 MiB, aggregate32 MiB,10,000 items, queue64, request/list deadlines, namespace/fresh-credential/permission checks, redaction and original runtime/oracles remain fixed. Complete boundary/ownership/refusal/native-load controls precede one original six-profile observation under a reserved quiet window. This authorizes no source adoption, full paired comparison, image or deployment. Native concurrency cannot fix repeated warm Pod phases, which make zero native calls; those regressions remain separate work.


The [root runtime tool selection](../evidence/bortus-runtime-tool-license-selection-root-20261012.json) binds the exact 61,960,354-byte patched kubectl ELF to its completed build/injection receipts and provides a separate executable named context. The cached Node image is identified by its actual OCI manifest descriptor and resident repository digest. A read-only filesystem copy from a unique container that was never started verifies `/usr/local/LICENSE`, 145,485 bytes, SHA256 `c738ae413cf561f174e34f6961f8ca458aae2369a73640dda6234c629b98bcc4`. All seven owned CLI identities are freshly absent, and removal plus a fresh successful query proves the inspector container absent. No image execution, pull, prototype build or source adoption occurs. These inputs resolve preparation prerequisites only; the complete assembled image still requires dependency/runtime/data-preservation qualification and its own durable full default security scan.

Root independently verifies the [combined eighteen-request/flat16 controls](../evidence/bortus-combined18-flat16-controls-root-20261012.json): all ten admission, cancellation, fresh-credential, namespace, redaction, size, aggregate, item and deadline sections pass on actual loopback HTTPS, alongside 3,674 native grammar cases and eight generic tests. The exact native ELF is loaded; all owner queues drain to zero. Actual runner/container/supervisor/dispatcher exits are zero within the original 60-second bound (24.59 seconds); 1,723 current source/compiled hashes are unchanged, and independent fresh checks prove four process identities and the exact container absent. This qualifies the isolated evaluation controls, not performance, source adoption or deployment. The separately approved single six-profile timing observation uses no control getter.

The [root combined single observation](../evidence/bortus-combined18-flat16-observation-root-20261012.json) retains all 28 observed originals; root also verifies the closed 41-file immutable package and matches those 28 captured files exactly. The original driver, runner and container exit 0 with six complete native inventories; supervisor and dispatcher exit 1 because their postcheck wrongly expects paired-run-only `runtime_harness_sha256` in direct driver output. That failure is preserved and no benchmark is replayed. Independent metadata-only review binds the pre-dispatch driver hash, verifies all 15 core-only module records and six actual native loads, recomputes 25 latency fields, checks 1,723 current source/compiled hashes and freshly proves four process identities plus the exact container absent. Secret HTTP times are 140.56/90.77/94.97/171.01/206.90/189.03 ms for 334/200/1,000/10,000/25 large/three maximum-size records; all expected inventories are complete. Whole-fixture CPU is 35.55 seconds and peak memory 566.69 MiB, without throttle or OOM. This single observation has no contemporary paired baseline or significance claim; five cases are descriptively slower and memory higher than the prior eight-request/flat16 candidate medians. Eighteen requests is not adopted, canonical source remains at eight, and A07/A21 remain open. Warm Pod and alias hot paths require separate source work; native concurrency does not change their calls.

## 2026-10-12: source 9fd comparison and master alias verified

The [unchanged three-pair comparison](../evidence/bortus-jwt-alias-paired-root-20261012.json) completes both builds and six observations with runner and supervisor exits of zero. Root verifies 107 originals, 430 exported Git/blob/mode/tar bindings, 520 current Git proof bindings and all 1,386 distributions. Current compiled snapshots contain 3,894 baseline and 4,263 candidate regular files. Ten PID/start identities, a separate dispatcher PID-only absence check and eight exact container absences are independently verified. Native Secret HTTP medians (baseline/candidate milliseconds) are 77.24/75.01, 65.82/71.74, 73.59/72.33, 267.55/174.35, 201.31/144.47 and 123.31/108.71. Whole-fixture CPU median falls from 35.94 to 30.61 seconds while peak memory rises from 356.98 to 413.11 MiB. All 69 comparable latency/workflow/CPU median increases remain recorded; A07/A21 stay failed/open. Alias listing takes one baseline request versus seven bounded 100-row candidate pages; this is source-backed context, not an exemption. No trimming, tolerance change, benchmark replay or source adoption.

The [alias-only public controls](../evidence/bortus-current-master-alias-controls-root-20261012.json) pass eight tests with 21 unchanged inputs under the original 30-second supervisor. The default scan exits with code 1 for one exact public dependency-hash declaration, transparently triaged without suppression. The [actual master alias](../evidence/bortus-current-master-alias-root-20261012.json) then completes once in 20.04 seconds within the original 75-second local/60-second remote bounds. All 13 image commands exit successfully and are reaped, fixed digest/config metadata matches before and after, and root independently observes 17 remote and four local identities absent. Current source and authority bytes stay unchanged. This adds the already imported c29 image's digest reference without an import, transfer, pull, application writer or data change.

Original-image version/isolation/API recovery, final image/security, latest-data backups and guarded live cutover remain open. Gluster/Vault/Consul originals and accepted backups remain preserved; the goal stays active.

## 2026-10-12: authoritative account-read mechanism diagnostic

The [isolated public diagnostic](../evidence/bortus-public-account-read-root-20261012.json) completes with outer/supervisor exits of zero, ten controls and all 24 untrimmed observations. Root verifies 78 originals and independently observes 20 PID/start identities and both exact container references absent. On selected Node 22.23.3/SQLite 3.51.3, median two fresh reads cost 0.637 ms through Prisma and 0.059 ms through prepared readonly SQLite, including native file identity checks. Both refuse locking, schema and permission faults; independent writes, revocation, demotion and deletion remain visible. The native reader refuses file replacement while the existing Prisma fixture connection returns its old snapshot. This is diagnostic behavior, not an existing production fence. Experimental warnings and all tails are retained.

No HTTP or asynchronous-worker performance acceptance follows these timings. A reviewable candidate may replace only the two current session/account reads with an asynchronous worker, preserving independent boundaries, projections, all extra permission and mutation checks, status mapping and the 100-row alias bound. Proposed auxiliary reader bounds are one active read, 64 queued and a 5,000 ms end-to-end deadline; native Secret limits stay unchanged. No rows, roles or sessions may be cached. Actual worker ownership, path/URL/schema parity, blocking/failure behavior, compiled packaging and original functional/performance gates remain required. A07/A21 remain failed/open; no live deployment or data change.

## 2026-10-12: held original-image version launcher controls

The [root receipt](../evidence/bortus-version-launcher-controls-root-20261012.json) retain the first fixture-copy setup failure and a distinct corrected input-only run: all 13 public controls pass in 0.567 seconds, with actual outer exit zero. Production launcher and assertions are unchanged. Root verifies all 310 files and 311 unique ZIP members by bytes, hashes and CRC, reads the complete launcher/original runner, and independently observes all 14 preflight/control/scanner PID-start identities absent. The selected ten-file default scan exits zero with no findings. These controls import the original default source graph and validate receipt drift, expiry and refusal; they do not construct a Transport or make a cluster request.

The actual version probe is still held at this checkpoint. Its scope is an inert temporary utility Pod plus the original API image's version command under the original 120-second deadline, without snapshot material or server startup. Historical TCP-denial evidence and current exact Calico correspondence do not establish new or continuous enforcement. Actual outer success, source stability, child closure and complete typed Pod/policy absence are still required; plaintext API recovery and overall acceptance remain open.

## 2026-10-12: async account-reader candidate rejected

The [root verdict](../evidence/bortus-async-account-reader-verdict-root-20261012.json) preserves both actual terminal failures. V3 passes 20/22 tests: the resolver incorrectly decodes a percent-containing filename that Prisma treats literally, and the cost guard correctly refuses timing after that failed prerequisite. V4 fixes only that resolver and passes all 22 focused checks, including the 13 original authorization outcomes and 24 untrimmed cost observations; types then fail on two test-only TS7022 annotations and lint does not run. Root verifies all 810 and 896 archived originals against their retained locations and independently confirms 23 and 44 local PID/start identities absent plus every exact owned container ID/name absent. Source, existing compiled artifacts, dependencies and inputs remain unchanged during each run.

The asynchronous worker removes the useful direct-SQLite timing gain: median two fresh reads cost 0.712 ms through Prisma versus 0.709 ms through the worker. Fresh-connection startup after controls costs 3.906 ms versus 86.919 ms. Those fixture results provide no HTTP or compiled-isolate acceptance. Root rejects this mechanism as the current performance remedy and preserves its experimental branch and failed packages. No full build, original pair, integration or deployment follows. The next source-only diagnosis concerns the unchanged seven-request, 100-row-page alias workflow; catalog loading occurs per refresh, not necessarily per page, and actual compiled owner/query counts remain unproved. A07/A21 stay failed/open.

## 2026-10-12: original version probe refused; separate cleanup verified

The [root receipt](../evidence/bortus-version-refusal-cleanup-root-20261012.json) records the once-only 4c version probe as an actual failure. Its 111 kubectl jobs exit zero and are reaped, but the semantic probe refuses after only the policy and inert Pod creates are confirmed; API-add never occurs. A later read-only observation finds the same Pod RunningReady with the correct original utility image and full spec. That does not reveal which original predicate failed. No API container, server or snapshot material was used, and no version success is accepted.

A separately reviewed d829 cleanup then completes with actual outer/caller/supervisor exits zero and 48 reaped successful CLI jobs. Fresh UID/resourceVersion delete intents remove only that owned Pod, prove complete typed name/UID absence, then remove its policy. Root independently verifies named404 and complete typed lists (six other Pods, zero policies), 50 cleanup process identities absent, and a further 171 distinct local PID/start identities absent across failure, cleanup and readers. The original refused journal stays byte-for-byte unchanged. Root verifies the 40-file/41-member immutable package by bytes/hashes/CRC, including 38 reread retained originals and two derived documents. Cleanup grants no version or API recovery acceptance. A source-only predicate trace is the next investigation; the original matcher, 120-second deadline and once-only dispatch remain fixed. Gluster/Vault/Consul originals and backups remain preserved.

## 2026-10-13: public numeric observer qualified; compiled attribution held

The [root observer receipt](../evidence/bortus-alias-observer-controls-root-20261013.json) verifies71 successful-control originals,63 initial failed-run originals and19 refused-clone originals against their retained bytes and ZIP hashes/CRC. The initial UID1001 fixture could not read the private UID1000 source; a proposed traversal-preserving clone also refused. A distinct fixture uses original runtime UID1000 without changing or copying retained files. All15 public HTTP/actual Prisma/HMAC/privacy/restoration/forwarding controls pass; root independently verifies15 recorded PID-start identities and the exact container ID/name absent. The selected16-file default scan exits0 without findings. These controls do not prove actual Next attachment.

Review refuses the unused asynchronous output launcher because a final failed write could leave an older complete report. Seven separate synchronous-output fault controls pass without replaying the15 interface controls; their exact owned resources are independently absent. The new publisher writes/fsyncs/closes an exclusive no-follow temporary file before rename and refuses failures without retry. Root independently verifies all72 archived originals against their retained bytes and hashes/CRC. One separately held original-driver compiled observation remains pending. Synchronous instrumentation adds I/O overhead, with no hard kernel-I/O bound or performance acceptance. A07/A21 stay failed/open; source, live deployment, original data and accepted backups are unchanged.

## 2026-10-13: compiled alias attribution verified

The [root compiled observation](../evidence/bortus-alias-compiled-observation-root-20261013.json) completes once with actual driver/container/supervisor/outer exits zero and all six original profiles complete. Independent root recomputation verifies 42 alias GETs, 84 fresh projected User reads and 84 HMAC operations. Each profile has two Prisma owners, one visible catalog owner and one CryptoKey owner. Only the first page performs a SecretReference query and alias-file stream creation; the remaining six reuse the catalog. Repeated catalog loading and JWT key import are therefore not demonstrated bottlenecks in this workflow. Both independent account boundaries remain fresh.

Instrumented median HTTP finish, Prisma-facade and HMAC spans are 5,336.5, 838 and 269 microseconds. These overlapping spans include observer overhead; Prisma timing includes queue/IPC/SQL and is not isolated SQL. Synchronous publication adds client-visible cost after the recorded finish. This observation establishes actual Next/Prisma request correlation, without private catalog-method or universal-isolate claims, and grants no latency acceptance. Root freshly verifies 37 PID/start identities and both exact container references absent; source, compiled files, dependencies and inputs are unchanged. A07/A21, final image/security, recovery and guarded live acceptance remain open.

## 2026-10-13: modeled version trace qualification

The [root trace receipt](../evidence/bortus-version-trace-controls-root-20261013.json) records 24 passing modeled controls, followed by a default scanner exit 1 for a verified public source-hash declaration. Original outer exit 1 is retained; separate source adjudication and fresh four-process absence do not upgrade it. The corrected binding follows the original loader's AST recipe with strict typed code fields. The detailed [API proof](BORTUS-ETCD-API-PROOF.md) preserves failed prerequisites, the 46-function diagnostic and exact scope. The traced original caller is reviewed source only; no new version/resource dispatch, material or server start is accepted. Actual version/API recovery, final image/security and guarded live gates remain open.

## 2026-10-13: traced refusal, current dry-run default and owned cleanup

The [root receipt](../evidence/bortus-version-dryrun-cleanup-root-20261013.json) preserves the original a726 failure: 87 successful CLI jobs and 47 trace events identify refusal at dryrun_match, before API-add. The full original reply was not retained, so its exact rejecting predicate remains unproved. Root verifies 102 archived files, 103 ZIP members and 99 current originals; the original failure is not upgraded.

A distinct current dryRun-only request succeeds with 23 reaped CLI jobs. The original matcher rejects the response, which contains exactly an extra empty resources object; removing only that field from a disposable in-memory comparison makes the unchanged matcher pass. Same Pod/policy UID and resourceVersion, source and CNI checks pass before and after. No persistent API-add, server or materials are dispatched. This identifies current default normalization only. The metadata reader exits zero, and root freshly verifies all 26 recorded identities absent.

A separate c931 cleanup succeeds with 48 reaped CLI jobs, deleting only the owned Pod with fresh UID/resourceVersion preconditions, proving complete absence, then deleting its policy. Independent typed reads confirm both names and UIDs absent (six other Pods, zero policies); root freshly verifies all 56 cleanup/reader identities absent. The original refused record is unchanged. Version/API recovery remain unaccepted; Gluster, Vault/Consul originals and accepted backups stay preserved. A minimal exact-empty-default correction remains a distinct source proposal.

## 2026-10-13: direct account reader focused controls pass

The [root focused receipt](../evidence/bortus-direct-account-focused-root-20261013.json) qualifies frozen candidate 94a0704 for focused evaluation only. Root verifies 377 source ZIP members, 384 preparation members, 383 current Linux inputs and exact raw Git tree/blob identities. The default scan of all 13 changed files exits zero with no findings. All 27 focused tests pass once: 25 distinct subtests plus two parents, including all original authorization outcomes, database lock/event-loop behavior, revocation/deletion, path/schema/type failures, queue expiry and ownership through actual filesystem settlement. Root independently verifies every expected test name exactly once, 23 process identities absent and the exact container name/ID absent. Source, dependencies and inputs remain unchanged.

Two independent session/account boundaries stay fresh; no role, row, session or result is cached. Native admission remains eight, flat metadata pages 16 MiB, generic pages 4 MiB, aggregate 32 MiB and 10,000 items. The proposed account-reader envelope is one active read, 64 queued and 5,000 ms admission-to-result; synchronous SQLite/kernel I/O has no hard wall bound, and directory ownership/modes remain deployment assumptions. Separate cost, types, build, original HTTP performance and live gates are pending. The worker experiment remains rejected; this candidate is not adopted.

## 2026-10-13: direct account reader cost observation verified

The [root cost receipt](../evidence/bortus-direct-account-cost-root-20261013.json) completes once with dispatcher, supervisor, container and diagnostic exits zero. Six prerequisites pass before 24 untrimmed observations alternate backend order across 12 pairs, each measuring 100 two-boundary read pairs. Root independently recomputes every row and statistic. Median cost per two fresh reads is 0.609412 ms through Prisma and 0.563993 ms through the direct reader: 0.045419 ms saved, about 7.45%. The reported batch p95 is the maximum of 12 batches (69.387 versus64.782 ms), not an individual HTTP percentile. Fresh connections after controls, including close, cost2.781 versus0.988 ms; this is not process startup.

Median CPU per100pairs rises from68.494 to76.250 ms, about11.3%. Whole-process observed high-water memory reaches119156 KiB; it is not independent backend memory attribution. All owners drain. Root freshly verifies17 process identities and exact container ID/name absent; source, dependencies and inputs stay unchanged. The first post-reader draft names the wrong preparation and remains unrun; a distinct reader corrects only that constant before dispatch. This is a modest diagnostic latency gain with higher CPU, not A07, HTTP, image, live or adoption acceptance. Frozen source94a requires functional/types/build and the unchanged HTTP gates next.

## 2026-10-13: exact-empty ephemeral resource default controls

The [root pure-control receipt](../evidence/bortus-empty-ephemeral-resources-controls-root-20261013.json) records a distinct two-line proposal that uses existing strict default normalization only for ephemeralContainers. Absent expected resources may match exactly an observed empty object; nonempty resources, wrong types, command/security/unknown-field drift, ordinary containers and explicit expected resources retain their original checks. All16 pure controls pass, including original request-body/input immutability and UID/resourceVersion fences. The first launcher executes zero tests and exits5 because it uses a detached module namespace; that failure is preserved. A distinct launcher changes execution to the real main module and completes the controls with actual exit0 in0.156s. Both test identities are freshly absent. The default scan of changed source/tests/review exits0 with no findings.

These controls make no Transport construction or API request. Original f080 source and accepted graphs remain immutable; new source5e47 is only a separately pinned proposal for a fresh held version procedure. The current empty-default observation does not reconstruct the original failed reply. Actual version, API recovery, final image/security and live adoption remain unaccepted.

## 2026-10-13: corrected typing passes; full HTTP interrupted

The [root type receipt](../evidence/bortus-direct-account-types-root-20261013.json) preserves the original94a type failure (three errors; child2, supervisor/outer1). Candidate8cf changes only two environment type annotations and one invalid-input fixture cast; production code and test assertions remain unchanged. Actual TypeScript5.9.3 emits identical JavaScript for both helpers. Fresh types/lint exit0; root verifies39 identities and four exact container references absent,914 current originals and the nine-file default scan0/0. Focused/cost observations were not replayed. A separate full run builds and loads the native module and passes293 units, then exits1 on a supervisor ProcessLookupError during HTTP testing after three passed cases. Full HTTP, performance, image and live acceptance remain open; the failure is retained.

## 2026-10-13: original-image version branch and independent cleanup verified

The [root version receipt](../evidence/bortus-original-image-version-root-20261013.json) binds the separately qualified exact-empty ephemeral resources normalization to a fresh version-only run. Caller/supervisor/actual outer exit0, all five operations are confirmed and155 CLI jobs are reaped. The independent reader adds ten successful read-only jobs, proves named and complete typed Pod/policy absence, and verifies source/CNI correspondence. Root freshly verifies169 PID/start/UID identities absent and118 archived files. Original e190 image spec/status match and its version branch exits0; version stdout was not observed and no server or recovery material started. The eight-source default scan retains exit1/one finding, independently identified as the public spec SHA, without suppression or upgrading its scanner result. The original a726 failure/cause remain unchanged. API plaintext recovery, final image/security and live acceptance remain open.

## 2026-10-13: supervisor race controls pass; retained build bound

The [updated root type receipt](../evidence/bortus-direct-account-types-root-20261013.json) independently verifies137 failed-run PID/start identities and eight exact container references absent, plus362 source files and5384 compiled objects at their recorded bytes/modes/links. The original full-run outer1 and incomplete HTTP result remain unchanged; its exact raising callsite was not captured. A separate narrow controller correction retries a proc lookup once after ESRCH and accepts a signal ESRCH only when a fresh owned-session group is empty. Eight controls pass once, including actual stale-proc and vanished-group cases and refusal of live, uncertain or mismatched identities. Root verifies six process identities absent and all13 inputs/six core copies unchanged. Three earlier outer drafts remain unrun. No build,293-unit suite or benchmark was replayed. A fresh HTTP-only qualification against the retained build is next; performance and live acceptance remain open.

## 2026-10-13: fresh eight-case HTTP qualification completes local composition

The [updated root functional receipt](../evidence/bortus-direct-account-types-root-20261013.json) records one fresh HTTP-only run against the retained8cf build. Dispatcher/supervisor/container/child all exit0; every unchanged integration case passes (8/8, zero failures/skips/cancellations). Root verifies62 PID/start identities and both exact container references absent, current362 source files/5384 compiled objects/40635 postbuild dependency objects, lock32b and both native8dde copies. All223 new originals are independently verified. The original1215 failed full-run originals and outer1 remain separate: successful build/native/293-unit phases plus this fresh HTTP result compose local functional qualification, not an uninterrupted full-run0. No install, build or293-unit replay occurred. Actual compiled fresh SQL ownership, the original performance gates, final image/security, recovery and live rollout remain pending; no limit adoption follows.

## 2026-10-13: actual compiled fresh SQL boundaries verified

The [root compiled SQL receipt](../evidence/bortus-direct-account-compiled-sql-root-20261013.json) passes ten isolated observer controls, including exact result/error forwarding, restoration and numeric-only reporting. A separate actual compiled8cf fixture completes ten HTTP requests with twelve fresh SELECTs: five session projections and seven account projections. Successful vars requests exercise both independent reads; role changes, session-version withdrawal, user deletion and schema outage produce the expected responses. There are zero unscoped known queries and no publication failures. This run observes one connection and two statement owners, without asserting universal process/isolate ownership or caching roles/rows. Root verifies15 control and18 fixture host identities plus exact container absence, and independently verifies81 control/97 fixture originals. The server PID is checked only in its container namespace. No source, build, dependency or authority result is replaced, and no benchmark/rebuild is replayed. Synchronous observer overhead precludes latency acceptance. The unchanged original three-pair comparison against baseline51e8 is next; A07/A21, recovery, final image/security and live adoption remain open.

## 2026-10-13: original comparison completes; warm-cache acceptance remains failed

The [root checkpoint receipt](../evidence/bortus-qualification-checkpoint-root-20261013.json) records unchanged original three-pair measurement with driver, supervisor and actual outer exit0. All six observations contain six complete profiles with equivalent expected inventories. Root freshly verifies10 PID/start identities and the separate dispatcher PID absent, eight exact container names absent,66 frozen inputs and431 exported-source hashes unchanged. CPU/memory/network/PID limits match every observation. The original summary is generated without altered fixtures, thresholds, timing windows or trimming.

Concurrent warm Pod p95 median baseline/candidate milliseconds are49.47/60.29 (small),58.57/70.99 (200),77.18/76.25 (1k),48.24/56.32 (25large),51.38/54.86 (three largest). Four comparable fixtures regress, so the required no-warm-cache-regression gate remains failed. Native Secret HTTP medians are88.82/76.30,67.90/68.84,70.83/76.09,259.42/175.48,187.85/152.31 and116.26/113.91. Whole-fixture CPU median falls35.21→30.91 seconds; peak memory rises364.39→419.56 MiB, with no observed OOM or throttling. These include fixture/driver work and do not isolate app CPU or memory. A07 remains failed/open; A21 and final image/recovery/live acceptance remain open. No source adoption, live rollout, benchmark replay or limit change follows.

## 2026-10-13: current cluster and charts pipeline read-only verification

The [current root cluster receipt](../evidence/bortus-cluster-current-root-20261013.json) verifies all three nodes Ready on Kubernetes1.37.1. The private charts repository has main7828f5b, one active validation/promotion workflow, and successful main-push run38150613416. Flux’s branconet-charts artifact and migration-releases applied revision both match validated7828f5b; their current Ready generations match. All33 active HelmReleases are Ready. BORTUS remains suspended at generation10, whose Ready condition is historical generation9; its one Ready pod still runs old image3b076fb9. No new candidate is deployed.

All54 PVCs are Bound. Observed attached Longhorn volumes report healthy, encryption enabled and two configured replicas; detached retained volumes report unknown robustness. These metadata reads do not establish data integrity, latest backups or plaintext restore acceptance. Retained game/recovery PVCs are preserved; no game release was installed. The observations span separate read-only queries, not an atomic snapshot. Final image/security, performance, recovery and guarded live acceptance remain open.
