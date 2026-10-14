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

## 2026-10-13: filesystem scheduling controls and isolated HTTP cost

The [root local-controls receipt](../evidence/bortus-sync-fence-recovery-controls-root-20261013.json) qualifies an outside-production prototype that runs every ancestor/leaf lstat and access check synchronously, then yields with setImmediate before either success or refusal. All16 controls pass: fresh projections, revocation/deletion, all checks after a fault, permission/symlink/schema/config/inode failures, queue saturation, abort/close ownership, BUSY retry and deadline expiry. Root verifies130 originals, current362 source files,5384 compiled and40635 dependency objects;20 recorded identities and both exact container references are absent. No authority result or filesystem identity is cached.

A separate once-only public loopback diagnostic passes480 requests in24 untrimmed alternating batches. Both independent identical agents open20 sockets on their first batch and fully drain. Median batch latency is11.151→8.016ms; median CPU is15.296→9.203ms. Batch p95 is the maximum of12 batches,60.153→16.366ms; individual client p95 over240 requests is50.380→10.957ms. First batches and instrumentation remain included. Shared-process setup and aggregate event-loop occupancy prevent isolated syscall/startup claims; timer samples cannot prove absence of blocking. This measures one fresh session projection per request, without JWT or Next. Root confirms all current inputs unchanged,16 recorded identities absent and both exact container references absent. Production integration and the original functional/Next performance gates are still required. One-active/64-queue/5000ms semantics and native eight-request/size/item limits remain unchanged; kernel I/O has no hard wall bound. A07/A21 and deployment stay open.

## 2026-10-13: fresh read-only utility cache attestation

The [root current-cache receipt](../evidence/bortus-current-utility-cache-root-20261013.json) completes a new once-only inspection with actual caller/outer exit0 in25.012s. The literal c29 utility digest reference already exists, with exact linux/amd64 manifest/config hashes, five source labels and16 ordered layer descriptors/content names. Exactly four read-only CTR jobs exit0 and are reaped; no alias, import, pull, export or image/server operation occurs. Layer bodies are not rehashed. Root verifies17 source/authority files unchanged after execution, independently confirms eight remote and four local process identities absent, and verifies87 archived originals plus85 current-original byte matches. The credential used only the qualified private stdin/controlling TTY route; foreground identity and disabled echo were independently checked before input. No credential file, argv value or input log is created.

The four-source default scan retains literal exit1/one generic-api-key finding. Root binds that finding to the exact public inspector source checksum without suppressing, altering or replaying the scan. This accepts sampled current utility-cache metadata and closure only. It proves neither continuous cache residency, layer-body integrity, original API-server recovery, live network enforcement nor private-material delivery. Actual bidirectional TCP denial remains required before nine private recovery parts. Original Gluster/Vault/Consul data and accepted backups stay retained.

## 2026-10-13: canonical build succeeds; test-only type correction pending checks

The [root failed-run receipt](../evidence/bortus-sync-full-type-failure-root-20261013.json) preserves canonical16adaea actual outer1: build/native loading pass, lint passes, then fresh type checking exits2 with two TS2540 errors in the filesystem mock. Unit/HTTP tests never run. The source/compiled/dependency inventories remain verified, with native8dde and5384 compiled objects. Root independently confirms89 recorded host identities and seven exact container ID/name queries absent, and verifies all705 archived originals against current bytes. No failed run is relabeled successful.

Followup a720 changes only three test type casts to writable mapped facades; production, assertions and runtime inputs remain unchanged. Its nine-file default scan exits0/zero findings with fresh scanner absence. A separate continuation is dispatched to verify actual TypeScript emitted-JavaScript parity, fresh lint/types/295 units and eight HTTP checks against the retained build and dependencies mounted read-only. Those results are still pending here. No build/native replay, original performance pass, final image, live deployment or data retirement follows.

## 2026-10-13: composed sync-reader functional qualification and separate probe refusal

The [root composite receipt](../evidence/bortus-sync-functional-composite-root-20261013.json) verifies the retained16adaea build/native pass plus fresh a720 lint/types/295 units/eight HTTP checks, with no failures/skips/cancellations. Actual TypeScript5.9.3 emits identical JavaScript before/after the three test annotation changes; production bytes and assertions are unchanged. Root verifies734 archived/current originals,362 source files,377 preparation inputs and the current compiled/dependency inventories, then freshly confirms104 host identities and four exact container queries absent. This composes local functional qualification; original full-run exit1 remains preserved and is not an uninterrupted pass. Build/native phases are not replayed.

A separate actual compiled SQL probe exits1 before its final report. Its retained trace eventually contains ten expected HTTP statuses and12 fresh SQL projections (five session/seven account), one connection/two statement owners, zero unscoped known queries and zero publication failures. All12 terminal numeric guards pass against that closed report; the first nine sequential parent body/status assertions preceded request10, but the last parent JSON read and final report assignment were not recorded. The original failed assertion is unknown; a publication timing race is only a source-supported hypothesis. Root freshly confirms17 host identities and both exact container references absent; server PID closure is a container-namespace observation only. The read-only validator's archive verification completed after invocation, an ordering mistake retained without workload replay. This does not upgrade the original probe to success. Deterministic publication observation and a fresh complete probe remain required before the unchanged original paired performance gates. Final image/security, live TCP/crypto recovery, latest backups and guarded rollout remain open; no data retirement occurs.

## 2026-10-13: fresh compiled SQL qualification after publication controls

The [root compiled qualification receipt](../evidence/bortus-sync-publication-compiled-root-20261013.json) preserves the original compiled fixture exit1 as unaccepted; its failure cause remains unproved. A fixture-only publication waiter passes ten controls, refusing stale nine-request traces, unknown files, corrupt JSON, wrong statuses, publication faults and expired deadlines. The new waiter uses the existing child deadline and requires a stable complete trace with no temporary files; it changes no production or frozen performance code. Root verifies92 control originals and106 failed-probe originals against archive CRC/hashes and current bytes.

One fresh compiled observation exits0, completing all ten original HTTP status/body assertions and twelve fresh SQL reads: five session and seven account projections. Role changes, session revocation, deletion and schema outage checks pass. The selected observation has one database and two statement owners, zero unscoped known queries/publication faults and no numeric refusal. Root verifies108 archived/current originals and current362 source files,5384 compiled objects and40,635 dependency objects. Fresh closure verifies18 host identities and both exact container references absent; server closure retains container-namespace scope. Control closure separately verifies14 host identities and both container references absent. Earlier failures are retained separately.

This qualifies the new local compiled observation alongside the composed functional pass. The unchanged original three-pair comparison is dispatched against baseline51e8 and candidatea720 only after fresh cleanup, current input verification and a quiet-window release. Its result remains pending. A07/A21 performance, final image/security, live TCP/crypto recovery, latest backups and guarded rollout remain open. Native concurrency stays eight; no source/runtime/live adoption or data retirement follows.

## 2026-10-13: synchronous-fence original paired comparison remains failed

The [root paired receipt](../evidence/bortus-sync-paired-root-20261013.json) records unchanged original three alternating pairs against baseline51e8 and candidatea720, with all six observations/six profiles complete and driver/supervisor/actual outer exit0. Current66 frozen inputs and431 exported source files match. The original pure summary is recomputed identically; no fixture, oracle, limit, timing window, warmup or tolerance changes. Fresh verification confirms ten birth-bound identities, the separately PID-only dispatcher and eight exact owned container names absent. No container IDs were retained for these eight names, so ID-based absence is not claimed.

Concurrent warm-Pod p95 medians baseline/candidate milliseconds are46.479/46.008 (small),54.455/49.267 (200),63.240/74.664 (1,000),47.157/45.968 (25large),43.743/45.603 (three largest). Two comparable concurrent cases regress. Serial warm p95 also rises in the small,1,000 and three-largest cases. The original no-warm-regression gate remains failed/open; functional and compiled-query success does not override it. Native metadata medians are94.129/71.003,62.476/80.857,66.610/68.644,240.327/163.624,177.490/140.893 and117.045/96.868. Whole-fixture CPU median falls33.104→28.180 seconds, while peak memory rises364.063→418.770 MiB. No OOM is observed; baseline throttling has median0 and one1.642ms observation, candidate0. These include fixture/driver costs, not isolated app measurements.

The result is retained without replay, adoption or deployment. A bounded causal investigation is required before another candidate. A07 remains failed/open and A21/final image/security/live TCP/crypto recovery/latest backups/guarded rollout remain open. Native concurrency stays eight and all original Gluster/Vault/Consul data and backups remain retained.

### Compiled warm-request attribution with unchanged bounds (2026-10-13)

The [root causal receipt](../evidence/bortus-warm-causal-root-20261013.json) qualifies one current compiled trace: one cold seed plus20 warm requests return every1000-Pod field correctly. All65 fresh queries, explicit request/operation/database ownership,20 row-memo hits and actual original Next shutdown/terminal publication checks pass. Independent review verifies362 source files,5384 compiled objects,40635 dependency objects and25 preparation inputs;19 captured host births and exact container ID/name queries are absent. Root verifies103 earlier-control,107 final-control,130 trace and261 TCP failure/cleanup originals. Nine pure typed-envelope tests pass separately; they do not qualify live denial.

Across20 disjoint held-reader intervals,106.177ms includes101.597ms in scheduled-yield windows,1.542ms in identity setup/check windows and1.588ms in SQLite calls. Response construction occupies8.601ms; envelope work occupies0.201ms and overlaps it. These are instrumented wall spans, not isolated CPU costs. Warm row projection/stringification is already memoized. Nearest-rank p50/p95 is used consistently with the frozen driver. All20 client promises start together, but server arrivals spread84.037ms; parent full-field validation shares the2CPU cgroup. The151.936ms parent phase is not original benchmark latency or a simultaneous server burst.

The dispatcher enforces its original180-second deadline before verification and retains60 seconds for closure. The inherited controller incorrectly labels its terminal annotation300; that original remains unchanged. A focused independent source/deadline guard proves180 and records the discrepancy without replaying the observation or current-graph/container checks.

```mermaid
flowchart LR
  A[Fresh authenticated request] --> B[Admission queue]
  B --> C[Identity checks and real yield]
  C --> D[Fresh SQLite read]
  D --> E[Identity checks and real yield]
  E --> F[Existing redacted row JSON memo]
  F --> G[Fresh availability and response body]
  G --> H[HTTP delivery]
```

A distinct secondary hypothesis proposes a lazy immutable row Blob and a fresh per-request availability/body composition; Blob is an immutable representation in the pinned [Node22 documentation](https://nodejs.org/download/release/v22.23.3/docs/api/buffer.html#class-blob). Complete-read costs, clone/cancel/mutation isolation and small-response behavior remain unproved. No source edit or adoption follows. Both real yields, one active reader through settlement,64 queued reads,5000ms deadline and native8/16MiB/32MiB/10000-item bounds stay fixed. Original performance gates remain failed/open; final image/security, live TCP/crypto recovery, latest backups, guarded rollout and original data retirement remain open.


### Complete-read response experiment — 2026-10-13

The [root component review](../evidence/bortus-blob-component-root-20261013.json) verifies16 controls,144 untrimmed observations/3168 complete reads, all18 independently recomputed conditions,114/126 immutable originals, current362/5384/40635 objects and27 inputs each. Recorded15/17 process births and exact container IDs/names are freshly absent.

For20 complete ASCII reads, twelve-sample nearest-rank medians (reference→Blob, milliseconds) are0.628→2.193 at3 rows,1.452→1.564 at200 and9.583→2.709 at1000. Unicode/long-label medians are0.533→1.387,11.947→2.465 and67.187→20.575. Cold/one-warm/concurrent, CPU and sampled memory distributions are all retained. The shared196.875MiB HWM is not an independent backend peak; these are component measurements, not HTTP/auth acceptance.

Blanket Blob adoption is rejected for small-case regressions. No fitted threshold, production edit or original benchmark replay follows. The earlier rejected bytes path already used private redacted-row Buffer reuse plus fresh Buffer.concat; the substantially repeated BufferSource option is withdrawn unimplemented/unrun. Original immutable qualification stays preserved. A07 concurrent-warm failure2/5 remains open. Both real yields, one active reader held through settlement,64 queued/5000ms deadline, every fresh path/schema/account check and native8/16MiB/32MiB/10000-item bounds stay fixed. Changing a bound requires a concrete reviewed proposal and explicit evaluation approval.


### 2026-10-13: local supervisor qualification and failed build checkpoint

The [root controls receipt](../evidence/bortus-proc20-controls-root-20261013.json) verifies all20 local supervisor controls (12 modeled predicates/eight actual local process and pipe checks), actual suite/outer0, unchanged ten sources, nine wrapper/suite/fixture births absent and the independent reader birth separately absent. The original30-second budget includes its two-second closure reserve. All78 immutable files/79 ZIP members and76 current originals verify; the selected four-file default scan exits0 with zero findings. This qualifies the isolated supervisor source only. The actual historical kernel exception, live TCP, private holder authority and recovery acceptance remain unproved.

The separate two-reader full build exits1 at direct-account-reader.ts152:53 because TypeScript narrows the post-import connection to never. Native-load, units and HTTP do not run. Root preserves the failure and confirms362 sources/379 inputs and retained dependencies unchanged,34 captured births absent and all five exact container queries absent. Partial compiled artifacts remain unqualified. Four erased type assertions are prepared; a fresh full build and actual Next case18 remain required before cost or original performance comparison. Production remains unchanged.

The image command closure is prepared from pinned definitions:72 slices/21 packages, retaining the prior62 definitions and restoring sed/Perl dependencies. All1085 tool/release objects and26 content-addressed seed cache files are copied separately. The new cut, signed-package verification, runtime ABI and full image scan remain pending. No original data or backups are retired.


### 2026-10-13: explicit two-reader evaluation and completed controls

The user explicitly approved 19 controls followed by one bounded comparison, for evaluation only. The [root qualification receipt](../evidence/bortus-two-reader-qualified-root-20261013.json) records a fresh four-phase build/native/lint-types-units/HTTP run with every phase exiting zero, 295 unit tests and eight integration tests passing without skips. Erased type assertions fix compilation while emitted runtime code remains identical to the original two-reader proposal. The two earlier failed builds remain preserved separately. Root verifies 987 immutable originals against current bytes, plus the 528 and 537 originals from those failures; 172 recorded process identities and eight exact container queries are absent.

Actual compiled Next case18 passes ten HTTP requests and twelve fresh SQL calls, with one connection and two statement owners. Together with initial cases01-17/19, all19 mandatory controls pass; preliminary module-owner18a is excluded from that union. Current source, compiled files, dependencies and preparation inputs match. Eighteen captured host births and both exact container ID/name are freshly absent. An early fresh reader refused a missing exact-review file before issuing queries; the later ordered exact and fresh checks both exit zero.

The next step is the single authorized bounded comparison. Production remains at one active reader; the evaluation admits two with64 queued reads, both real yields and the5-second result deadline unchanged. All native Secret limits and the original performance benchmark/oracles remain fixed. These functional controls establish no performance acceptance, adoption or deployment. Original data and backups remain preserved.


### 2026-10-13: expanded rootfs signed provenance

The [root signed-package receipt](../evidence/bortus-command-image-signed-root-20261013.json) verifies the expanded72-slice/21-package filesystem, including sed and Perl. The original cut command exits zero but its outer verifier exits one; that failure remains literal and its exact cause is unproved. A distinct signed verifier initially exits one after five successful signature checks. A read-only diagnostic identifies four newly downloaded cache files with mode0666; root verifies their bytes/content addresses and tightens only those four to0600. Existing seed cache files and source inputs remain unchanged.

The fresh signed verifier and independent reader both exit zero: five release signatures, ten signed indexes and21 selected package controls bind the exact package archives. Root verifies904 filesystem objects,1085 source objects,26 seed files and all36 current cache entries;38 recorded process identities and the reader's own birth are freshly absent. All186 immutable files/187 archive members and184 current originals match. No cut, GPG or package-control command was replayed by the independent reader.

The selected source scan retains exit1 with one finding on a verified public archive-key checksum; no suppression or overall source-scan pass is claimed. This proves provenance and current filesystem bytes only. Coherent canonicala720 application compilation/pruned dependencies, runtime ABI/startup/migration qualification and a durable full default image scan remain required before deployment. The isolated two-reader evaluation is excluded from image source selection until separately adopted. Original data and backups remain preserved.


### 2026-10-13: single two-reader cost sample complete; no adoption

The [root cost receipt](../evidence/bortus-two-reader-cost-root-20261013.json) preserves all24 alternating batches/480 successful requests and480 real returned session SQL reads. Exact postchecks and fresh cleanup both exit zero; current source, compiled artifacts, dependencies and20 inputs match,16 captured host births and both exact container ID/name are absent. The116 compiled-case18 originals are independently hash/CRC/current verified. Selected source6-file and preparation3-file default scans exit zero without findings or suppressions.

Timing is mixed: independent batch medians are10.097064ms for one reader and9.960943ms for two, but the two-reader version is slower in7/12 matched pairs and the median paired ratio is1.013742 (1.37% slower). All twelve pairs remain included. First pair60.244226ms versus22.922091ms contains first connections and preceding setup effects; it cannot establish startup causality. Shared process/CPU/memory, forwarding SQL counters and timers are disclosed; this sample does not measure Next/JWT or establish A07 acceptance.

The canonical application source remains at one active reader; the live deployment is unchanged. All101 cost originals and the complete paired analysis are independently hash/CRC/current verified. The user was immediately asked whether to extend evaluation to the unchanged original three-pair benchmark on an isolated candidate; the original evaluation authorization is exhausted and no dependent benchmark or adoption proceeds without that answer. Image preparation continues against canonicala720 independently. Original data/backups and all earlier failures remain preserved; the overall goal remains active.


### 2026-10-13: original benchmark authorized; canonical build/prune checkpoint

The user approved the unchanged original three-pair benchmark on a distinct isolated candidate, with no adoption/deployment. Candidate3be78557da928a3da01b73b771bf342d6baa71bd on codex/bortus-two-reader-evaluation contains the qualified two-reader source/test bytes and five checked docs; the original canonical checkout remains clean and unchanged. Its selected seven-file default scan exits zero without findings, with fresh scanner absence and current-byte verification. The subsequently completed benchmark is recorded below; baseline51e8, original driver/exporter/oracles, limits and alternation remain unchanged. There is no pending user question.

The [canonical artifact receipt](../evidence/bortus-canonical-build-prune-root-20261013.json) binds274 raw Git source bodies/modes and286 scanned source/metadata files. Initial preparation exits one because the root wrapper's umask made a newly requested0755 directory0700. A separate correction changes only three owned new directory modes; independent full source and original/copied40635-dependency checks exit zero. The original failure remains literal; no preparation replay occurs.

Fresh canonical build exits zero and binds the native8dde artifact. The separate prune child times out at150 seconds with null status/SIGTERM/ETIMEDOUT, and the actor exits one; the cause is unproved and no complete pruned manifest is produced. A separate failed-owner reader exits zero, verifies source/full dependency authority and completed compiled/native manifests, and freshly confirms174 captured identities plus two exact container-ID queries absent; its own birth is independently absent. Success-only context copying stays unrun. Partial21 signed metadata is rendered outside the original rootfs, with explicit72-slice markers. A distinct new-copy pruning proposal was held during the benchmark timing window; that window is now released for review. No new image is qualified or deployed, and original data/backups remain preserved.


### 2026-10-13: isolated two-reader original benchmark complete; not adopted

The [root original benchmark receipt](../evidence/bortus-two-reader-paired-root-20261013.json) records baseline51e8 and isolated candidate3be7855, with both builds and all six observations/six profiles complete and actual outer/runner/supervisor exit zero. Independent verification checks66 unchanged frozen inputs,431 exported source files and recomputes the original pure summary identically. Ten captured process births, the separately PID-only dispatcher and eight exact container names are freshly absent. No container IDs were retained for these eight names, so ID-based absence is not claimed.

Concurrent warm-Pod p95 medians baseline/candidate milliseconds are48.539/49.441 (small),57.668/52.342 (200),71.366/70.398 (1,000),49.033651/49.052621 (25large) and55.111/47.385 (three largest). The small and25large cases regress; serial warm small also rises14.869/16.368. All three pairs and distributions remain retained without trimming or tolerance changes. Whole-fixture CPU median falls34.854/29.224 seconds, while peak memory rises363.004/427.383 MiB; no OOM or throttling is observed. These are fixture/driver measurements, not isolated app costs, and comparison with the earlier a720 run cannot establish a matched two-reader gain.

The original no-warm-regression acceptance gate remains failed/open. The two-reader candidate is not adopted or deployed; canonical source remains one-reader and live deployment remains unchanged. The benchmark quiet window is released for independent canonical image work. No evaluation permission is pending. A07/A21, coherent image/security, current recovery and guarded live acceptance remain open; original Gluster/Vault/Consul data and backups remain preserved and the overall goal is active.


### 2026-10-13: canonical offline prune fails explicitly; closure verified

The [root offline-prune receipt](../evidence/bortus-offline-prune-root-20261013.json) records a distinct fresh-copy preparation with actual exit zero, followed by independent verification of274 current source files/modes, original and copied40635 dependency objects and identical retained/copied compiled/native artifacts. The selected283-file default source scan exits zero without findings; scanner birth and current bytes are freshly verified. The successful build is copied from its retained original build0, without replaying it or reusing the earlier partially pruned dependency directory.

The new network-disabled prune exits one with child status1, null signal and null child errorCode. Original stderr identifies npm ENOTCACHED for @eslint/eslintrc registry metadata in only-if-cached mode. This establishes this new failure, not the cause of the earlier150-second timeout. A separate failure reader exits zero, verifies current source/full dependency authority and unchanged completed compiled/native artifacts, confirms14 recorded process identities and the exact container ID absent, and keeps all11 CLI jobs and the literal actor failure. The reader and its new query child are independently freshly absent. No complete pruned manifest, success context, accepted image or live deployment follows.

Root verifies all560 earlier failed-build/prune archive files/561 members and557 current originals. All178 isolated original-benchmark originals also pass current hash and archive CRC verification; the failed loose-copy assumption in the first root archive reader remains recorded separately before its corrected ZIP-only metadata pass. Lock-respecting pruning is being investigated on a fresh copy with the original source/lock and resource limits preserved. A07/A21, coherent image/security and recovery/live acceptance remain open. Production and all original migration data/backups remain unchanged; the goal remains active with no pending user decision.


### 2026-10-13: canonical pruned context passes; small-fixture trace qualified

The [root canonical context receipt](../evidence/bortus-canonical-pruned-context-root-20261013.json) records a fresh lock-respecting offline prune with actual actor/container/child exits zero. It reads the existing lock with package-lock=true/no-save/ignore-scripts, preserves both package and lock hashes, and records actual npm10.9.9/Arborist8.0.5 plus five public tool-source hashes. The unchanged original150/180/900-second bounds, network isolation and resource limits remain. Initial preparation and independent full source/dependency/compiled/native checks exit zero; the original successful build is reused without replay. The selected284-file source scan and6-file context-post scan exit zero without findings, with fresh current-byte and scanner-birth checks.

Independent context checks verify the actual29814-object pruned dependency tree, unchanged completed compiled/native artifacts and retained full40635-object dependency authority. Eighteen captured actor process identities and the exact prune container ID are absent; the context reader and its query child are independently freshly absent. A new durable context retains715 standalone objects, excludes exactly3332 objects in standalone/node_modules, and uses only the verified pruned tree for dependencies. Original source/compiled files remain unchanged. This qualifies future image inputs only: no runtime/native/HTTP/full-image security or deployment acceptance follows. Earlier timeout and ENOTCACHED failures remain preserved; all70 offline-failure archive files/71 members and67 current originals are verified.

A separate quiet three-Pod diagnostic preserves the qualified observer and original21-request/65-SQL protocol, all20 warm results and one cold seed. Actual actor and exact/fresh posts exit zero;362 sources,5384 compiled objects,40635 dependency objects and32 preparation bindings remain current,19 host births and exact container ID/name are absent. Observed warm held intervals total94.690ms, including89.768ms in real scheduled-yield windows,1.680ms in identity/setup checks and1.715ms in SQL; response construction totals1.397ms. The spans include instrumentation and shared fixture/framework/client scheduling; nested spans cannot be added as independent CPU costs. This is causal evidence only. Both real yields, one active reader, all fresh checks and existing bounds remain unchanged. The isolated two-reader original benchmark still fails its warm criterion and remains unadopted.

Current image assembly and a distinct performance remedy remain open. No user decision is pending. A07/A21, full coherent image/security, latest recovery and guarded live acceptance remain open; production and all original Gluster/Vault/Consul data and backups remain unchanged, and the overall goal remains active.

### 2026-10-13: current live baseline and public image components verified

The [root live/component receipt](../evidence/bortus-live-components-root-20261013.json) records read-only inspection at17:17 UTC: three Ready nodes,97 Pods with no non-completed unready Pod,54 Bound PVCs and33 active Helm releases Ready at their observed current generations. BORTUS remains suspended, generation10/observed10, on existing image3b076. The40 encrypted two-replica Longhorn volumes include30 attached/healthy and10 detached/unknown; this metadata does not prove restoration. No Secret objects or environment values are reported. The charts repository is private with one active Charts validation and Flux promotion workflow. Its latest successful main run38150613416 and live Flux validated revision both bind7828f5b; chart pushes remain CI-promoted to validated before reconciliation. No new deployment is claimed.

The public component copy completes once with actual exit0 and ten recorded CLI jobs; its Node ELF and licence match the fixed public hashes. The container never starts and is removed without force. Independent checks verify all12 Node objects and five empty runtime directories,11 captured component identities absent, exact container ID/name absence, and later the post-reader plus two query identities absent. The six-file default source scan passes with zero findings and fresh current-byte/birth checks. A Windows command-length staging refusal and a final-print metadata error after successful staging remain recorded; neither replays the workload. All93 canonical-context archive files/94 ZIP members and90 current readable source leaves are verified, preserving the root-owned receipt access boundary. This qualifies image inputs only. COPY-only assembly, runtime/ABI/Prisma/HTTP, full default image/security scans, A07/A21, latest recovery and guarded live acceptance remain open. No candidate adoption or original data retirement.

### 2026-10-13: actual canonical COPY-only image build completes

The [root image-build receipt](../evidence/bortus-copy-image-build-root-20261013.json) records a distinct corrected build with actor/build/four CLI exits0, all five source labels, UID/GID1000, expected entrypoint/workdir and Docker image ID1f842e41. Its size is275889397bytes; later retained-archive inspection identifies this Docker .Id as an OCI index digest, not a config digest. Raw historical receipt field names are preserved; no registry publication is qualified. The actual image Config.Env includes the original public PATH and six intended public app settings, so no PATH inheritance/default assumption or second build is needed. Five recorded CLI/actor birth identities are freshly absent. The raw release producer passes under a gated180-second inherited Windows job; all274 tar/Git blob/mode bindings and exclusive staged archive/manifest bytes are independently verified. The ten-file dispatcher default scan passes without findings and has fresh current-byte/scanner checks. No container/application starts.

The prior actual V2 attempt remains exit1 before owner creation/build dispatch; its generic finalization label does not prove deadline expiry or reconstruct the original exception. A separate current read-only discriminator identifies the rootfs check rejecting signed empty tmp and var/tmp directories01777. V3 preserves those exact modes only on protected source/new-copy rootfs contexts, with no original mutation or relaxed app/component checks, and retains primary numeric refusal metadata. All173 three-Pod originals and the application’s21-original docs-only publication are verified. A separate held worker source candidate now has a source correction for its unacknowledged-close gap; complete source and runtime/performance qualification remain pending. The actual independent image-input post exits0 and verifies all30902 application objects,904 original/copied rootfs objects,12 Node objects, five runtime directories, ten source files, current pins and exact image metadata/five labels/13 layers/public PATH. It freshly confirms five actor births absent; a further root check confirms the post reader and its metadata-query birth absent. Its three-file default source scan passes without findings. Export/layer-content digest, actual native/Prisma/HTTP, full default security scans, A07/A21, latest recovery and guarded live rollout remain open. Production and original data/backups remain preserved.

## 2026-10-13: worker focused controls pass; saved image identity corrected

The [worker receipt](../evidence/bortus-worker-focused-root-20261013.json) records all four actual phases at exit0: emitted-worker preparation, semantic types,83 focused tests and lint. All25 worker controls pass with the original seven test files unchanged. The candidate preserves one active read,64 queued reads, the original five-second envelope and both actual yields. Root verifies410 prepared files,370 current source files,409 inputs and the full40635 dependency/5384 retained compiled graphs. It freshly verifies82 runtime birth identities, eight exact container ID/name absence queries and then nine post/query identities absent. The retained compiled graph is compiler context only. Candidate full production build, standalone/compiled ownership, full functional/HTTP and unchanged performance qualification remain open; focused controls grant no adoption.

The [export receipt](../evidence/bortus-image-export-refusal-root-20261013.json) retains literal actor exit1, save exit0 and the275913728-byte archive, SHA25665126d42e222fc86b70d072fc54125afa0b4d6d8b528fec080b5d4374d5dd86c. Default source scan and14 pure descriptor controls pass. An initial test wrapper left the filename in unittest argv and refused before those controls; its receipt is retained, and the corrected wrapper passes. Export refuses at stage6 because the unchanged legacy helper expects the config blob SHA to equal Docker .Id. Read-only archive metadata instead demonstrates Docker .Id1f842 is the856-byte OCI index, selecting the2767-byte linux/amd64 image manifest bb225 and6651-byte config24c8. The canonical image build remains valid, but historical config_image_id fields are not config proof. Root verifies all three export and four test birth identities absent and seven source files unchanged. A separate retained-archive post must qualify the complete chain and layers without another save or modifying the legacy ABI. Full filesystem/runtime/default-security and live acceptance remain open. No production change or original-data retirement.

The [independent retained-chain receipt](../evidence/bortus-image-retained-chain-root-20261013.json) records this result. The retained archive now passes a distinct read-only chain verifier with actual exit0. Its independently verified DockerId/OCI index is1f842, selected linux/amd64 manifest bb225, and actual config24c8; every raw referenced size/hash/media type, attestation reference, public config setting and13 ordered layer blob/diff hashes match. The unchanged legacy archive helper receives the actual config digest, preserving its ABI. Root freshly verifies the reader and three export birth identities absent, unchanged full application/rootfs/components/pins and archive SHA65126. Original export actor1/save0 remain retained. The saved-image chain is qualified; registry publication, full filesystem reconstruction, native/Prisma/HTTP execution, default security and live acceptance remain open. No second save, deployment or data retirement.

## 2026-10-13: worker full qualification passes; canonical filesystem and scan complete

The [worker full-functional receipt](../evidence/bortus-worker-full-functional-root-20261013.json) records four distinct phases at actual exit0: production build, native addon load, unchanged lint/types plus322 units, and all eight unchanged integrations. Preparation uses370 raw/V3 source files and a fresh40635-object dependency copy, with no install, pruning or retained compiled artifact reuse. Independent checks verify412 inputs, the unchanged dependency authority, all5382 current compiled objects and exact standalone worker/core/receipt/schema bytes. All179 runtime birth identities and four exact container ID/name pairs are absent; the later reader and eight query births are also absent. The original command arrays and900-second budget/60-second cleanup reserve remain fixed. Tests may rewrite only the two generated worker assets on the new source copy; their final hashes/modes and every selected source file remain guarded. This is full local functional qualification; compiled middleware/handler-to-worker SQL ownership and the original performance benchmark remain open. No adoption.

The [canonical filesystem/security receipt](../evidence/bortus-canonical-fs-security-root-20261013.json) records exact equality of31792 filesystem objects across13 layers, including bytes, ownership, modes and links. All12 pure parser controls pass. V1’s parser did not independently pin three expected manifests; the separate root gate pins all three approved SHA values plus the chain result/terminal before and after current source-tree and stored-inventory comparison. This completes the missing manifest-binding scope without replaying extraction or rewriting the original receipt. No host filesystem extraction occurs.

The default Trivy0.75 image/secret/config scan refreshes a new exclusive database cache and returns literal exit1: five MEDIUM findings across libc6,libpcre2-8-0 and zlib1g, zero HIGH/CRITICAL/secrets and no reported fixes. Ubuntu24.04/21 explicitly partial package records,202 npm packages and90 kubectl Go packages are analyzed. The Node.js target has no node package entry; no Node ELF vulnerability pass is inferred. Root independently verifies current tool, archive, complete report and all cache hashes, including the refreshed1614467072-byte database, plus both scanner/owner births absent. No filters or suppressions are used. All five findings remain retained; package triage, Node core security coverage, residual exception decisions, actual image native/Prisma/HTTP execution and live acceptance remain open. Original data and production remain unchanged.

## 2026-10-13: actual canonical image runtime passes; isolated worker source committed

The [image runtime receipt](../evidence/bortus-canonical-image-runtime-root-20261013.json) records actual actor0 and independent post0. The exact image runs asUID1000 with2CPU/1GiB/no swap/PID256/networknone/read-only root and an empty memory database. There is no application or dependency overlay, operator credential or existing production data. The actual Node/native addon loads; the original entrypoint performs Prisma migrations and starts the standalone app. Live health, registration/login/session, readonly403, operator200 and fresh database permission withdrawal403 pass. All21 recorded runtime birth identities and the exact container ID/name are independently absent; later the post reader and its two query births are absent. Eight source objects,81 original runtime files, current application/rootfs/components and full archive descriptor/diff-ID chain remain exact. Native Kubernetes TLS client, private recovery, performance, residual security review and live adoption remain open.

V3’s default source scan retains one generic-key finding for its explicitly public synthetic fixture key; it never stages or runs. V4 uses an obvious public all-zero32-byte fixture key and passes the unchanged default eight-file scan. Cryptographic algorithms, permission/status oracles and private/production key material are unchanged. No scan suppression or filter is introduced. The independent three-file post scan also passes.

The [committed worker receipt](../evidence/bortus-worker-committed-source-root-20261013.json) independently verifies clean isolated commit8299384 and371 raw frontend Git blobs/modes. Its370 qualified payloads match369 raw blobs literally; only runtime/.gitignore has a documented working-CRLF/raw-LF relation. Every behavior/compiler/worker/test source matches the qualified V3 bytes. The excluded.env.example is metadata-only. All1107 immutable full-functional originals, ZIP CRC/hashes and current original bytes verify. The selected15 source/docs default scan passes with zero findings and fresh scanner absence. This source commit remains unadopted; compiled middleware/handler-to-worker SQL and original performance qualification remain open. No source rebuild or workload replay is inferred from metadata normalization.


## 2026-10-13: worker observer controls qualified

The [observer control receipt](../evidence/bortus-worker-compiled-observer-controls-root-20261013.json) records all twelve public controls at actual exit0. Real HTTP requests join to actual worker operations, SQLite connections and prepared statements; both real yields preserve ownership. Fresh mutations, listener/prototype restoration, original errors, unscoped/missing/duplicate/late joins and final-write/rename refusal checks pass. Root review corrected registration ownership to record a listener only after the original registration succeeds; the new original-error/no-ghost-registration assertion is included in the unchanged twelve-control suite. Earlier V1/V2 source packets remain preserved and unrun.

Independent root checks verify370 current source files,14 current inputs,40635 retained dependency objects and5382 compiled objects, with15 recorded runtime births and exact container ID/name absent; the later reader and two query births are also absent. The original300-second whole budget/60-second closure reserve,2CPU/1GiB/no swap/PID256/UID1000/read-only/network-none settings remain. This qualifies the observer's public controls only. Actual compiled middleware/handler-to-worker ownership and the original performance benchmark remain open. No adoption, deployment, original-data retirement or acceptance relaxation.


## 2026-10-13: Node core advisory coverage remains open

The [root primary review](../evidence/bortus-node-core-primary-review-root-20261013.json) verifies21 packet files/22 CRC-valid members, current original bindings, the inspection process birth absent and six current ELF-header/needed-name comparisons totaling15520 bytes. Node22.23.3 bundles OpenSSL3.5.8; its ELF has no direct libssl/libcrypto dependency, while Prisma's query engine needs both shared libraries. These bounded linkage observations do not prove every dynamic-load/caller path or replace the existing full-byte image authority.

The [September OpenSSL advisory](https://openssl-library.org/news/secadv/20260929.txt) includes HIGH CVE-2026-84782 in the3.5.8 range. The exact Node built-in TLS selector cannot select its required DTLS operation; that source rationale does not waive the whole ELF/addon boundary. LOW CVE-2026-35189 concerns ordinary peer-certificate processing and remains unresolved for the native HTTPS client. The original default Trivy exit1/five MEDIUM/zero reported HIGH remains unchanged; its npm target did not assess Node core. No exception or security pass is accepted. Source-only remedies compare a custom Node22/full OpenSSL3.5.9 update with official Node26.11.1 and a fresh coherent qualification profile. Neither changes runtime, benchmark acceptance, source image or deployment.


The [actual compiled-fixture V1 refusal](../evidence/bortus-worker-compiled-fixture-refusal-root-20261013.json) preserves actor/container exit1 and the150-second child timeout. All ten parent HTTP statuses and thirteen dispatch/settlement frames were observed, but no worker-side SQL report exists. Exact Node startup source explains that default Workers inherit initial native launch flags; mutating process.execArgv after launch did not preload the worker observer. Independent checks verify117 runtime births and exact container ID/name absent, followed by three post/query births absent and current source/dependency/compiled authority. The first metadata reader's missing success-only removedVerified field remains recorded; its corrected reader checks closureVerified and fresh exact absence. The new fixture uses initial --require with a main/worker-aware ownership gate, preserving application code, original assertions and limits. Compiled worker SQL and performance remain unqualified until that distinct actor passes.


## 2026-10-13: compiled worker SQL ownership qualified

The [compiled SQL receipt](../evidence/bortus-worker-compiled-sql-root-20261013.json) records corrected fixture actor/container exit0 using the supported initial --require preload and separate main/worker ownership-gate branches. All ten unchanged HTTP status/body assertions pass, including fresh role withdrawal, session revocation, user deletion and schema outage. Thirteen actual dispatch/settlement frames join to one real worker, one SQLite connection, two prepared statements and twelve selected SQL reads (five session/seven account); the schema-refusal attempt selects no row. Complete numeric reports remain stable through actual server exit. The earlier V1 timeout is preserved.

Root independently recomputes all cross-thread joins and request projections, verifies370 source files/24 inputs and the current40635 dependency/5382 compiled authority, and freshly confirms19 runtime births plus exact container ID/name absent. The later reader and two query births are also absent. All25 selected source files pass the default scan with zero findings and fresh byte/birth checks. Application Worker construction, SQL, permissions, original ten assertions and300/60/150/180-second bounds remain unchanged. The candidate retains one active read/64 queued/five-second deadline/both real yields. Full local322+8 tests and actual compiled ownership now pass; the unchanged original three-pair performance comparison is next. A07/A21, security, latest recovery and guarded live adoption remain open. Production and original migration data/backups remain preserved.


## 2026-10-13: worker original benchmark complete; serial warm gate remains open

The [worker benchmark receipt](../evidence/bortus-worker-paired-root-20261013.json) records fresh baseline51e8/candidate829 builds and all six alternating observations/six profiles at actual outer/runner/supervisor exit0, with every expected inventory returned. All five original benchmark files, exporter, runtime/image/limits, fixtures, warm-up and criteria remain unchanged. The unchanged summary and independent root arithmetic reproduce1386 distributions/4158 numeric values;437 actual tar/Git blob/mode bindings (280 candidate/157 baseline),66 frozen inputs and current exported sources verify. Ten runtime birth identities, the separately PID-only dispatcher and eight exact container names are absent; eight later query births are also absent. No container IDs are invented.

Concurrent warm-Pod p95 medians baseline/candidate milliseconds improve in all five cases:80.698/70.514 small,114.966/90.395 at200,146.039/119.617 at1000,87.347/85.877 at25large and79.169/78.957 atthree-largest. Serial warm200 regresses11.096/11.455,25large10.328/11.793 andthree-largest11.054/12.785. All three pairs/min/median/max and95 comparable latency/workflow/CPU median increases remain retained. Whole-fixture CPU median falls52.421/46.208seconds while peak memory rises365.637/426.590MiB, with no OOM; these include the driver/fixtures and do not isolate worker cost. Earlier candidate runs are distinct observations, not matched worker mechanism controls.

The original no-warm-regression gate therefore fails. The candidate remains isolated, with one active read/64 queued/five-second deadline/both real yields and all fresh checks preserved; no adoption, deployment or acceptance relaxation follows. Source-only serial-path review continues. Two raw-source metadata reader API/type refusals remain preserved; the corrected reader verifies the437 bindings without rerunning export/build/timing. A07/A21, security, latest recovery and guarded live acceptance remain open; goal active, no pending user decision, original Gluster/Vault/Consul data and backups preserved.

## 2026-10-13: upstream source signatures authenticated

The [root signature receipt](../evidence/bortus-node-source-signatures-root-20261013.json) records the bounded source-authentication result. Root authenticated the signed Node22.23.3 checksum list and Node/OpenSSL3.5.9 tag signatures using the published primary keys. All three actual GPG checks exit0. The original wrapper exits1 on non-ASCII public signer display text; a distinct read-only post exits0 after parsing only machine status fields. Independent root checks verify all22 current input rows and all five original/post process births absent. The wrapper failure is retained, and no cryptographic check is replayed. This authenticates the existing small public signatures only; source archive bytes, OpenSSL archive signature, exact Node22 regeneration/build, ABI/Prisma/TLS and final image security/performance remain unqualified. No runtime or deployment changes.

## 2026-10-13: source archives authenticated and cached builder inspected

The [archive receipt](../evidence/bortus-node-source-archives-root-20261013.json) records two successful fixed acquisitions: Node22.23.3 source50,447,060 bytes and OpenSSL3.5.9 source53,279,637 bytes. The Node archive matches the authenticated signed checksum list; the OpenSSL detached archive signature passes once against the expected primary key. Independent read-only checks verify archive/source/keyring/tool bytes and four original process births absent, followed by the reader itself. No download or crypto check is replayed. The original source scan retains two public-receipt-digest findings; clearer checksum naming passes the unchanged default scan without suppressions. Archives remain unextracted/unpatched/uncompiled.

The [builder receipt](../evidence/bortus-node-builder-inspection-root-20261013.json) records corrected inspection0 and independent post0 against the fixed cached image. It retains the prior pre-create missing-Labels refusal and started inspection refusal. The actual corrected reader observes Perl with two legitimate hard links, GCC/G++12.2, binutils2.40, make4.3 and Python3.11.2. NASM is absent; the exact OpenSSL regeneration helper invokes it even on Linux. The18657-byte default config is retained separately from process.config. Root verifies8 source files/228 records,43 original host births absent, four exact container ID/name queries and five later reader/query births absent. Container tool coordinates are never treated as host PIDs. Isolated authenticated tooling, safe source projection, generation/build, ABI/Prisma/TLS, final image/security and recovery/live qualification remain open.

## 2026-10-13: finite serial diagnostic passes; original warm gate remains open

The [serial diagnostic receipt](../evidence/bortus-worker-serial-diagnostic-root-20261013.json) records twelve new instrumentation controls0, actual compiled diagnostic0 and independent exact/fresh posts0. Thirteen complete three-Pod body checks join to13 fresh session reads,26 schema-version queries and two initial schema queries on one connection/selected-row statement. There is one cold CLI seed and no warm CLI calls. Root independently reconstructs all13 joins and verifies270 immutable originals/current bytes/ZIP CRC,370 source files,25 inputs and the40635 dependency/5382 compiled authority. Nineteen runtime births and exact container ID/name are absent, followed by three reader/query births. The earlier dependent post started before its prerequisite completed refuses before querying; it passes only after the prerequisite finishes, with no control replay.

Across all12 untrimmed warm requests, ordinary medians are75.5 microseconds for core read-entry to execute-entry,2.2105 milliseconds before dispatch,3.6705 milliseconds after parent receive-return to HTTP finish and9.454 milliseconds to complete body bytes. These nested wall-time windows are not summed as CPU and do not attribute JWT/Next/serialization costs. The cold outlier and final-publication overlap remain retained. The worker report proves the settled13-operation prefix, not all later worker state through termination. This evidence does not support tiny duplicate-core bookkeeping removal as the main remedy. Source review continues on larger framework/request/response windows; fresh authorization remains mandatory. Original benchmark files, fixtures, limits and criteria remain unchanged; its three serial warm regressions still fail A07/A21. No adoption or deployment.

## 2026-10-13: source-copy controls pass; real-archive preparation refuses

The [source-preparation receipt](../evidence/bortus-node-source-projection-root-20261013.json) records 14 passing synthetic controls, including real regular/executable/symlink/materialized-hardlink copying and the exact 106 modified, six added and 33 removed path operation. Existing-copy refusal preserves the copied bytes. Independent checks verify all three input files, actual suite exit and two distinct process births absent. The selected source and runner pass their default scans without findings or suppressions.

The subsequent authenticated-archive attempt exits 1 during stage-one validation, with no source trees created. Independent read-only checks confirm the actor birth absent, all three source files and four authority records unchanged, and both authenticated archives retaining their original full hashes and fingerprints. The numeric refusal does not establish its cause; a bounded read-only diagnosis is next. The failed attempt remains preserved. No extraction, generation, compilation, production adoption or deployment has occurred.

Root also revalidates the 178 immutable originals and archive CRC for the completed two-reader original three-pair benchmark. Its six observations finish successfully, but A07/A21 remain failed/open; no benchmark is replayed or candidate adopted. The goal stays active with no pending user decision. Original Gluster/Vault/Consul data and backups remain protected.

## 2026-10-13: read-only archive diagnosis identifies a representation mismatch

The [updated source-preparation receipt](../evidence/bortus-node-source-projection-root-20261013.json) records diagnostic exit 0 and independent read-only post 0. The unchanged Node parser returns all 32,585 logical objects and 553,575,480 expanded regular bytes. For OpenSSL, the first root header carries a bounded `comment` PAX field and mode 0775; the current parser rejects the PAX allowlist at source line 258, before admitting any OpenSSL object. This is a new current-parser witness, not a retroactive assertion about the original caught exception.

The diagnostic process is absent and all three bound inputs plus both archives retain their original bytes and fingerprints. No extraction, crypto replay, network, generation or compilation occurs. A scoped correction is being prepared for the fixed signed OpenSSL distribution: retain bounded inert metadata, preserve bytes and Git execute modes, and remove group/other write bits only from newly created copies. Node guards, path/link/sparse/special-file checks and original archives remain protected. That correction was unexecuted at this checkpoint; the later V5 result below supersedes source-preparation status. Build, security, performance and live acceptance remain open.

## 2026-10-13: authenticated signed-release source projection completes

The [updated source receipt](../evidence/bortus-node-source-projection-root-20261013.json) records three passing scoped SSL distribution controls and six exact release-mapping controls. The retained V4 attempt refuses before tree creation. A complete current comparison checks all 145 paths: all 138 present Node preimages match old blobs/modes, all 112 SSL postimages match new blobs/modes, and all 33 removals are absent from SSL. Only `deps/openssl/openssl/doc/build.info` is absent from the signed Node release. V5 maps that exact path, old/new blobs and modes from Git-modified to release-added, preserving every other byte/mode/removal guard. Git counts remain 106 modified/six added/33 removed; measured release counts are 105 modified/seven added/33 removed. No export-policy intention is claimed.

The once-only V5 actor exits zero. Independent read-only verification binds all six manifests and all three current physical source trees, all three source files/four authority records, the original actor birth absence and both unchanged archive hashes/fingerprints. Finalizers are empty. Newly copied SSL files clear group/other write bits while preserving content/execute modes; original files remain unchanged. The six-control supervisor has disclosed LF/CRLF byte differences with equal normalized text/AST; archive/source content is never normalized. No generated main-branch files, Git context, generator, compiler, custom runtime or production deployment follows this source-preparation result. NASM/tool compatibility, Node build/security, original performance and private recovery/live gates remain open.

## 2026-10-13: actual compiled Next span diagnostic completes

The [framework diagnostic receipt](../evidence/bortus-worker-next-span-diagnostic-root-20261013.json) records seven passing public API controls and a separate once-only compiled trace. Thirteen complete three-Pod responses join to 13 ended/nonfailed middleware spans, 13 route-module spans and 41 SQL queries on one connection: 13 fresh session projections, 26 schema-version queries and two initial queries. The public Next API realm and HTTP asynchronous context associate in the actual compiled app. Both observers seal and restore before publication; no context-manager replacement or prior provider-object identity restoration is claimed. Two unscoped watched spans and 70 other spans remain transparently counted.

Root independently recomputes all 91 signed framework interval fields and verifies all current 370 source files, 24 inputs, 5,382 compiled objects and 40,635 dependencies. Exact/fresh posts verify 19 original process births and exact container ID/name absence; three later reader/query births are independently absent. The initial missing-cache attempt ran no tests/container and stays retained; restoration pulls the same fixed immutable c4 image. Original 300-second/60-second closure and 2CPU/1GiB limits remain unchanged. All 189 archived originals retain their current bytes and ZIP CRC/hashes.

Across all 12 untrimmed warm requests, ordinary medians are 1.0655ms HTTP-to-middleware entry, 0.818ms middleware-entry-to-worker dispatch, 2.316ms middleware occupancy, 0.1495ms worker receive-return-to-middleware end, 2.1365ms middleware end-to-route entry, 0.3635ms route-module occupancy, 0.842ms route end-to-HTTP finish and 10.387ms complete client body. These nested instrumented wall intervals are not additive CPU or a new performance gate. The finite worker settled-prefix limitation and cold outlier remain retained. Actual route body occupancy is small relative to the middleware/route transition in this sample; source review continues without assigning that transition to one mechanism. Original warm benchmark regressions still fail A07/A21; no source adoption, deployment or original data retirement follows.

## 2026-10-13: NASM parser controls pass; signed-index acquisition refuses

The [NASM prerequisite receipt](../evidence/bortus-nasm-prerequisite-root-20261013.json) records eight passing public parser controls and an independent current-source/process check. Public packet/protocol/index/tar fixtures do not establish actual GPG or Debian provenance; the sparse case models the parsed TarInfo boundary. Original source scanning retains two public primary-fingerprint findings. The corrected runtime files pass their three-file default scan, while the complete eight-file packet still exits one for the historical removed line in its diff. Both findings remain reported, with no suppression/filter or overall eight-file pass. The standalone five-file acquisition packet passes its default scan.

The actual once-only acquisition exits one at stage four. All seven completed commands exit zero, including the original Release signature command; six public downloads remain retained, with no NASM download/tool tree. A separate read-only witness confirms all eight original births absent, current source/artifact hashes and both complete compressed/plain index hashes. The exact current parser rejects an index line over its 16KiB field bound. The longest signed-index line is 75,649 bytes and stanza 76,338 bytes; the NASM stanza still matches the fixed 2.16.01-1/amd64/405,156-byte package digest. This is a current parser witness, not a retrospective original exception assertion. A secondary generic diagnostic also refused before publication and remains retained. No network, crypto or download is replayed for the successful witness. A narrowly scoped package-index correction is being prepared; real package projection, compatibility, generation/build and security remain open. Production and original data/backups remain protected.

## 2026-10-13: scoped index correction qualifies; continuation refuses before download

The [updated NASM receipt](../evidence/bortus-nasm-prerequisite-root-20261013.json) records two passing focused controls. Only package-index lines/stanzas use 128KiB; Release/deb-control fields keep 16KiB, with full size/hash/uniqueness/package checks unchanged. Seven source files pass the default scan; independent verification confirms all three runtime files and two original births absent. The earlier eight controls are not replayed.

The separate continuation exits one at stage one before downloading NASM. Its two source files and all 24 original public records remain current, with the actor birth absent and empty finalizers. A new typed read-only witness finds all seven original terminal identities equal to their started identity fields but with the sole added `same_identity_absent: true` cleanup annotation. The new exact whole-dictionary comparison is therefore false; every original job is zero/reaped/no-refusal and currently absent. This is a current predicate witness, not retrospective exception reconstruction. The correction will admit only that affirmative annotation while preserving every recorded identity field and fresh absence check. No crypto, prior download, package execution or build is replayed. Actual tool compatibility and build/security/performance/live gates remain open.


## 2026-10-14: authenticated NASM projection and builder compatibility verified

[The updated NASM receipt](../evidence/bortus-nasm-prerequisite-root-20261013.json) records two passing identity-annotation controls. The corrected guard preserves all six recorded identity fields and admits only the affirmative cleanup annotation. The new continuation exits zero, downloads only the fixed 405,156-byte NASM 2.16.01-1/amd64 package, verifies its digest against the retained signed complete index, and projects only the executable and copyright. Root independently verifies 24 original records, six artifacts, full index selection, tool hashes/modes/fingerprints, and all ten original/new host births absent. Prior crypto and downloads are not replayed; prior refused actors remain recorded. The signed Release has date 2026-07-11 and no Valid-Until field. The three disclosed NASM advisories remain recorded with no security exception; this is build-only tooling, with no host installation or final runtime inclusion.

The separate fixed-c4 builder compatibility actor exits zero. Readelf dynamic/symbol inspections and the actual version command all exit zero; NASM reports 2.16.01 and requires libc.so.6 through GLIBC_2.34. Independent verification binds four runtime source files, six acquisition records and both unchanged tools, confirms 18 recorded host births and fresh exact container ID/name absence, then separately confirms five later reader/query births absent. The initial independent post refused because absent formatted Docker inspect emits one LF; a new exact-LF post passes without replaying the compatibility workload. Three tool coordinates belong to the container namespace and are not host PIDs.

This qualifies loader/startup/version only. Node regeneration, compilation, default upstream tests, runtime ABI/Prisma/TLS, final-image security, original performance, private recovery and guarded live acceptance remain open. The first long-build proposal is source-only and unrun; review requested explicit private PID namespace identity, compiler temporary files on the new private output filesystem, and durable closure records under the original deadline. No production adoption, deployment or retirement follows.


## 2026-10-13 23:47 UTC: read-only cluster metadata refresh

[The current metadata receipt](../evidence/bortus-live-metadata-refresh-root-20261013.json) records three Ready nodes, 54 Bound PVCs, 97 Pods and all 33 active Helm releases Ready. The BORTUS HelmRelease in flux-system remains suspended; BORTUS runs the existing digest 3b076fb9 with one Ready container and zero restarts. Both Flux sources and migration-releases are Ready at the recorded revisions. All 40 Longhorn volumes are encrypted with two replicas: 30 attached/healthy and ten detached/unknown. No Secret values or environment values were requested or reported. These observations do not establish recovery, chart-push delivery, new-image rollout, or full application acceptance. No production mutation or data retirement occurred.


## 2026-10-14: isolated Node generator refuses; independent cleanup verified

[The literal build receipt](../evidence/bortus-node22-build-root-20261014.json) records actual exit one with empty finalizers and the exact container removed. New-copy Git initialization, add and commit exit zero. The unchanged all-target OpenSSL generator exits two on its first aix64-gcc-as Configure: embedded test/build.info is absent and no Makefile is produced. Configure, compilation, upstream tests and the new-Node probe never start. The fixed three-hour lease, 60-second closure reserve, 2CPU/8GiB/no-swap/PID512, no network and new private compiler temporary directory remain unchanged. Actual resource checks pass; distinct PID and IPC namespace identities are recorded before worker release. The eleven-file source default scan and scanner absence pass. Earlier source-only V1/V2/V3 drafts remain unrun.

The separate outcome-honest post exits zero while preserving the original actor failure. It verifies 83 current records, five runtime sources/authority records, the original working tree, tool fingerprints and both unchanged archive hashes/fingerprints; all 14 recorded host births, fresh exact container ID/name absence and three later post/query births are absent. Four phase coordinates are container identities, never host PIDs; unsampled descendants close through the verified private namespace and removed exact container. No source-generation, build, runtime or security pass follows. Source review now checks the full authenticated OpenSSL distribution for required auxiliary inputs while preserving embedded projected bytes and the exact generator/test recipe. No production mutation or data retirement occurred.


## 2026-10-14: synchronous HS256 primitive controls qualify; integration held

[The isolated authentication receipt](../evidence/bortus-sync-hs256-controls-root-20261014.json) records ten passing control sections and 175 untrimmed comparisons against unchanged public JOSE6.2.12 verification, including accepted/refused outcomes and exact payload/header equality. Actual nonextractable-key HMAC, an independent RFC4231 vector and real key-slot cold/warm/rotation/no-overlap/zeroing controls pass. The candidate authenticates original HS256 compact bytes before using public JOSE claims validation; external unsigned tokens remain rejected. This is finite corpus evidence, not universal verifier equivalence or whole-operation constant-time proof.

Root exact and fresh posts verify all 370 source files, 18 inputs, 5,382 compiled objects and 40,635 dependency objects unchanged, all 16 original process births and fresh exact container ID/name absence, then three later reader/query births absent. Nineteen control-source files and six post-source files pass default scans and fresh scanner absence. The original 300-second/60-second closure, 150-second child/180-second attach, 2CPU/1GiB/no-swap limits remain unchanged; actual private PID namespace, UID1000, read-only/network-none/cap-drop/no-new-privileges checks pass. Original thirteen authorization outcomes, compiled application, typed integration, performance and adoption remain explicitly unproven. Application source and production remain unchanged. A typed isolated integration proposal is being reviewed; the frozen original warm-performance gate remains failed/open.


## 2026-10-14: typed signing-path checks pass; full preparations interrupted

[The typed candidate receipt](../evidence/bortus-sync-hs256-typed-root-20261014.json) records actual exit zero for types, the original ten-section/175-case differential corpus using the real typed export, original thirteen authorization/four key-slot cases (eighteen TAP entries including the parent), and lint. Independent checks bind371 raw source files,394 inputs,40,635 dependency objects and5,382 unchanged old compiler-context objects; the latter are not candidate compiled proof. All64 recorded original births, eight exact container ID/name queries and nine later reader/query births are absent. Source/post default scans pass without suppression, and scanner birth absence is verified. The earlier four public-digest metadata findings remain retained; conventional relative/sha256 rows clear the new source packet without changing code or fixtures. The earlier V4 OCI mountpoint failure remains exit one with no child checks run; its cleanup passed. V5 adds only two empty mountpoint directories in a new source copy. Full production build, original322-unit/eight-integration checks, compiled authorization, performance and deployment acceptance remain open.

[The complement receipt](../evidence/bortus-node22-complement-root-20261014.json) retains the initial11/12 public copy-control result: an existing destination-parent symlink caused44 new objects in a disposable protected fixture sibling before late rejection. No original data was involved. Verifying the entire original destination and source before any new effect makes the unchanged12 cases pass. Further Configure source review shows that22 missing build.info files alone cannot establish generator readiness. The complete complement is exactly6,077 authenticated full-distribution objects minus2,712 existing embedded objects:3,365 additions, comprising128 directories and3,237 files/96,299,821 bytes. Existing embedded bytes and modes remain authoritative even where the full distribution differs.

All15 distinct complete-protocol controls pass, including exact actual-manifest derivation, source/destination symlink refusal, no overwrite, full union checks, mode/type/hash/path refusals, hard-SHA tampering and expiry. Independent current checks bind seven inputs and both original births absent, then the later reader absent. These public fixtures do not authenticate source archives or prove generator readiness. The new actor uses the already authenticated read-only full source, one consumed source FD at a time, with original-tree/full-tree checks before and after. Link and special input types are refused; no atomic privileged-race claim follows. Its ten-file default scan and current scanner absence pass.

The isolated complete-complement build and fresh application dependency preparation were interrupted by a WSL kernel restart. Both WSL invocations return exit one with empty diagnostics; no Python exception or OOM cause is inferred. Current kernel uptime68.43 seconds contrasts with the old actor start tick923435 (about9,234 seconds), and the new boot ID is recorded. The retained complete-complement receipt reports3,365 objects/3,237 files/128 directories/96,299,821 bytes and git-init exits zero, but no generator, compiler or upstream tests start and neither actor nor worker terminal exists. The exact owned build container is observed exited255 with matching image/owner/source, then removed; fresh exact ID/name queries report not found. The application has all371 source files but an incomplete dependency copy, no completion receipt and no dispatched full suite. Independent current-input/authority checks are pending; partial outputs will not be reused. The unchanged Node10800/60 and application900/60 recipes remain separate new-owner work, to be run sequentially. No source-generation, build, runtime, performance, security or deployment acceptance follows the interruption. The earlier failures remain retained. No original data or retirement changed.


## 2026-10-14: fresh full and compiled authorization qualification pass

[The qualification receipt](../evidence/bortus-sync-hs256-functional-compiled-root-20261014.json) records a fresh dependency copy from the unchanged40,635-object authority, production build/native load/lint/types, all322 original units and eight original integrations with no failures or skips. Independent checks bind371 raw source files,400 inputs,5,382 actual compiled objects and40,635 installed objects; all185 recorded births, eight exact container ID/name queries and nine later post/query births are absent. Four standalone worker/core/receipt/schema bindings and the actual8dde native ELF load pass. The original900/60-second full recipe and commands remain unchanged.

The separate compiled fixture and independent numeric join checks pass ten exact HTTP statuses/full-body assertions, twelve fresh SQL calls (five session three-column and seven write five-column projections), thirteen attempt/settlement/worker joins and stable reports through actual server exit. One database and two prepared statement owners are observed. Current371 raw files plus four separately declared generated runtime extras make375 checked objects; this is not375 raw Git files. All34 inputs and the current compiled/installed graphs remain unchanged. All18 recorded births, exact container ID/name absence and three later post/query births pass. Original300/60/180/150 bounds and observer/fixture/oracles remain unchanged. Source and post default scans and scanner birth absence pass.

The interrupted V2 preparation remains exit one and never dispatched. A separate post-restart witness verifies371 source files and the full40,635 authority before/after. Its partial36,721-object copy has3,914 missing and33,442 mismatched complete metadata rows; individual corruption fields and restart cause are not inferred. That partial copy is retained and never reused. The fresh V3 run above uses a new dependency copy.

[The updated runtime-source receipt](../evidence/bortus-node22-complement-root-20261014.json) preserves V6 outer exit one, missing terminals and the observed exited255 container. Its independent incomplete post passes47 current records, all six projection manifests/three original trees/archives/tool authorities, the physical original-plus3,365 complement union excluding only new Git metadata, and exact removed container ID/name absence. Nine recorded host coordinates predate that post's boot; no namespace continuity across restart is claimed. Three post/query births and the later reader are absent, with differing boot IDs recorded without cause attribution. No generator, compiler, upstream tests or runtime/security acceptance follows. Fresh V7 changes only owner/path/labels; its five other runtime files, phases and10800/60 resource contract remain identical and its source scan passes.

The unchanged original three-alternating-pair/six-profile comparison is now running against baseline51e8 and candidate4df4, with all five benchmark files, exporter, fixtures, warmup, oracles and limits fixed. Node V7 is held for this exclusive measurement window. Performance, final image/security, private recovery and live acceptance remain open. No production deployment, original-data change or retirement occurred.


## 2026-10-14: original HS256 comparison complete; warm gate fails

The [original comparison receipt](../evidence/bortus-sync-hs256-paired-root-20261014.json) supersedes the running/held status in the preceding checkpoint. The original three alternating pairs and six profiles complete with actor exit zero and every native inventory present. Root independently recomputes 1,386 distributions / 4,158 numeric values and verifies all 438 exported tar members against raw Git blob IDs, bytes and modes (281 candidate, 157 baseline). All 66 frozen inputs remain unchanged. Exact and fresh posts pass: ten recorded births and eight exact container names are absent. There are no retained container IDs; dispatcher absence is PID-only. Eight later query births are absent. These scopes are not expanded into stronger ownership claims.

The no-warm-regression gate fails five of ten comparable cases. Serial warm p95 medians in milliseconds rise from 6.82 to 8.26 for 200 Pods, 9.99 to 24.14 for 1,000, 7.31 to 8.49 for the 25-large fixture and 7.27 to 7.32 for the three-largest fixture. Audit-small concurrent warm p95 rises from 51.09 to 55.69. Other warm cases improve, but do not cancel failures. The baseline 10,000-Pod false-empty result remains ineligible for equivalently successful latency. No fixtures, driver, warmup, timing windows, limits or tolerance are changed; the benchmark is retained without replay. Functional/compiled qualification remains valid and separate from failed performance acceptance. Candidate 4df4d32 remains isolated and unadopted.

Source review finds the current route already caches redacted Pod rows and their JSON string for the exact cached items array. A further serialization cache is not justified. A held 1,000-Pod diagnostic will reuse the qualified Next collector, worker observer and gate, preserving 13 requests, 41 SQL checks and 26 spans; only the public fixture count and matching exact full-body oracle change. It will run after the isolated Node build's exclusive resource window and will report middleware, route and emission wall windows with instrumentation/overlap limits. It does not authorize adoption or relax acceptance.

Fresh Node V7 is now dispatched once and its exact generator phase has started. No terminal build/test result or new ELF/image/security pass exists yet. Final image, TLS, private recovery and live acceptance remain open. Production, original data and retirement state are unchanged.


## 2026-10-14: V7 header dependency refusal and 1,000-Pod causal trace

[The updated Node receipt](../evidence/bortus-node22-complement-root-20261014.json) supersedes the running status: actor exit one, generator exit two, complete retained failure and exact container removal. The final error is missing Text/Template.pm at generate_headers.pl line 6; compilation and default tests never start. The independent post exits zero, verifies 84 current records, all six original manifests/three physical source trees/archives, four phase terminals, 14 recorded host births and exact container ID/name absence. Three post/query births and the later fresh reader are absent. No generated-manifest, ELF, license/config, runtime or security acceptance follows. The original generator command/platforms/options/tests/deadlines remain fixed; a generator-only search-path correction using authenticated existing module bytes is being prepared in a fresh owner.

[The 1,000-Pod trace receipt](../evidence/bortus-sync-hs256-warm1000-trace-root-20261014.json) records actual actor/exact/fresh/later checks at exit zero. One cold seed and twelve serial warm requests return every exact expected row, with 41 fresh SQL checks and 26 qualified Next middleware/route spans. Memoization has twelve hits/one miss and zero warm CLI calls. The 371 raw source files plus four generated extras, 29 inputs, 5,382 compiled objects and 40,635 installed objects remain current. Nineteen original births, exact container ID/name and three later post/query births are absent. Thirty source files and four post files pass default scans with scanner birth absence; only new source directories/files receive private modes. The qualified observers/gate/lifecycle bounds are retained; only the public fixture count and matching complete-body oracle change.

The numeric windows are instrumented wall observations with nested spans, framework/client scheduling and full-field fixture validation sharing the fixed cgroup. They cannot be summed as independent CPU costs or substituted for the unchanged original benchmark. Causal source analysis continues. The five-of-ten warm performance failure remains; no candidate adoption, production mutation or data retirement occurs.


## 2026-10-14: fresh generator dependency-path attempt dispatched

Fresh V8 starts once after V7 independent cleanup and the completed quiet trace. Root verifies the actor has only fresh owner/path/label and worker-hash changes; all old non-main worker functions and the nested phase implementation remain unchanged. The only worker change binds the authenticated Text::Template subtree (four rows, two files, 72,212 bytes), verifies its signed full-distribution and new-work copies before/after, and supplies PERL5LIB only to generator descendants. It removes the variable before configure/build/tests. No install, download, overwrite, platform/options/test change or partial-work reuse occurs. The same 10,800-second whole/60-second closure and phase/resource bounds remain fixed. Twelve source files pass the default scan and fresh scanner birth absence. V8 is running; no terminal, new ELF or security/runtime acceptance is claimed. V7's failed source/log/terminal/post evidence remains preserved.

The completed 1,000-Pod trace has ordinary warm medians of 7.1405 ms client, 1.4645 ms middleware, 1.578 ms middleware-to-route transition and 0.7175 ms route module. Its twelve timed complete-body reads total 105.967 ms; the whole loop takes 147.012 ms, leaving 41.045 ms for fixture parsing/full-field assertions, inter-request work and overhead outside those timers. Nested medians are not additive CPU costs. The largest warm request includes both an IPC delivery window and a route window; this does not identify SQL, GC, compression or allocation as a cause. Existing row/JSON memoization and bare successful middleware continuation are already present. No source remedy follows from this correlation. A separate source-only proposal will add supported thread/process CPU and GC/scheduling observations with bounded numeric output; the original benchmark, fixtures, permission/freshness limits and failed acceptance remain unchanged. No production mutation or retirement occurs.

## 2026-10-14: CPU helper qualification and pre-operation receipt refusal

[Current root receipt](../evidence/bortus-current-checkpoint-root-20261014.json) records seven new CPU/GC helper controls passing, plus exact, fresh and later cleanup checks. These tests qualify bounded numeric sampling and forwarding behavior only. They do not rerun prior controls or the original performance benchmark. The prepared 13-HTTP/41-SQL/26-Next-span trace remains held until Node V8 and its post checks close; GC delivery coverage remains explicitly incomplete.

Node V8 header generation and configuration exit zero; compilation is running. There is no actual terminal or qualified new ELF. Original build commands, platform, tests, resource and deadline bounds remain unchanged.

The public TCP attempt exits 1 before creating its operation directory. Its generic caller failure does not retain an exception. A separate bounded read-only diagnostic reproduces the first current refusal at the cache prerequisite's `completed_monotonic <= time.monotonic()` predicate. The retained receipt predates the WSL boot; its monotonic timestamp is ahead of the current clock. The diagnostic constructs no transport and issues no API command, creates no resources and accesses no credentials. Four recorded process births are absent on a fresh observation; the operation directory remains absent. This identifies a current prerequisite failure, not the historical exception. Preserve the failed attempt and predicate; obtain a fresh actual cache attestation before binding a new attempt. Public isolation proof would still not authorize delivery into a different private holder.

The read-only 03:30 UTC snapshot shows 3 Ready nodes, 97 Pods, 54 Bound PVCs and 33 current Ready active Helm releases. BORTUS is Ready with zero restarts on its existing immutable image; its Helm release remains suspended. All 40 Longhorn volumes are encrypted with two replicas: 30 attached/healthy and 10 detached/unknown. Both Git sources and the release Kustomization are Ready. This is metadata evidence, not a push/rollout, restore or acceptance claim. Performance, final image/security, TLS, private recovery and guarded live acceptance remain open. No user decision is pending; original data/backups stay preserved.

## 2026-10-14: fresh current-boot cache attestation completed

The [current root receipt](../evidence/bortus-current-checkpoint-root-20261014.json) now includes fresh run c5a4381e960b. The original qualified caller and read-only actor remain unchanged. Only observer/closure nonce bindings change. The 75-second local lease starts before verification and the private controlling-TTY prompt; remote work retains its inherited maximum 60-second bound. Root verifies ECHO disabled and the caller PID/start/UID/foreground group before input. Actual outer/caller exits are zero in 19.709 seconds; all four read-only containerd jobs exit zero and are reaped. Manifest/config hashes, source labels, platform and 16 ordered layer-content names match; layer bodies are not rehashed. No pull, import, alias mutation, container or private material delivery occurs.

Root independently checks eight recorded remote and four local identities absent, final SSH birth absent, the same WSL boot before/after and all 17 source-authority files unchanged. The closed archive verifies 38 raw originals against ZIP CRC/SHA and all 38 current originals. Original four-source default scanning retains literal exit 1 and one finding, independently bound to the public inspect-api-cache.py SHA256 at caller line 17; there is no suppression or scanner-pass claim. The two nonce-only observer/closure sources scan with exit zero and no findings separately.

The old 8326 receipt, failed TCP attempt and cross-boot refusal remain intact. A distinct TCP proposal is being bound to the new actual receipts and archive counts. No TCP attempt has run after this refresh, and neither sampled cache metadata nor a public TCP test proves same-holder private recovery isolation. Node V8 remains compiling; performance and final live/recovery acceptance remain open. No user decision is pending.

## 2026-10-14: refreshed TCP startup hash mismatch

The fresh-cache-bound TCP attempt 11fc01a9d088 exits 1 before its supervisor or operation directory exists. Root first verifies the current 200 staged hashes/modes/UID/nlink and a fresh owned six-dependency inspection; both pass. Its generic late-durability/closure/deadline output does not retain the underlying exception. The source review identifies an explicit incompatibility: configuration pins refreshed prerequisite 640f3927, but the supervisor's unchanged PREREQUISITE_SHA is 8630bf47 and both configuration equality and file pinning require it. Root missed this dependent constant in the initial review. A separate constant-only correction and dependent source bindings are being prepared; the same functions, guards, original 300-second lease/one-second closure and controls remain intact. Neither failed nonce is reused, and no success reader runs against a failure.

The four-source review verifies the closed 51-file ZIP and exact nonce/count/comment prerequisite delta. Its default scanner retains literal exit 1 and two generic matches at caller lines 18/19; root binds both to current public source SHA256 values for the recovery specifications and TCP isolation program. There is no suppression, replay or scanner-pass claim. Fresh cache evidence remains separate and valid as a same-boot sampled prerequisite; it does not prove TCP or private-holder isolation. The old receipt and failed attempts remain preserved. No production or data mutation, adoption or retirement occurs.

## 2026-10-14: public TCP sample and independent cleanup completed

Fresh V9.1 changes only the supervisor prerequisite constant and dependent source hashes; every function/class, including main, is raw-identical to the qualified supervisor. Root verifies all fixed runtime pins match actual source, 53 closed ZIP files, 12 unchanged receipt payloads, original staging functions and all 200 current staged hashes/modes/UID/nlink. A fresh owned six-dependency check passes. The default four-source scan retains exit 1 and the same two findings independently bound to public source checksums; no suppression, replay or pass claim occurs. Failed attempts and old receipts remain preserved.

Actual public TCP run 586c5101fc0d exits zero in 47.066 seconds under the original 300-second lease plus one-second OS closure. Both directions first deliver the expected marker; after policy enforcement both new connections are blocked while loopback listeners remain alive. Source/callback checks remain unchanged. The caller records 451 jobs; the supervisor records 452 observed identities. No private material or API server starts.

The unchanged independent V5 post exits zero in 1.104 seconds under its original 30-second lease. Five read-only API requests verify three resource absences by exact name and UID. It validates 453 identities including the actor supervisor. Root subsequently checks seven reader/supervisor/job identities absent, corroborates each job's expected UID against observed births, verifies current 200 actor sources and five post sources, and later observes the fresh-checker birth absent on the same boot. Root binds the actual supervisor5336 hash and actual pending/terminal/input bytes; the post reader does not independently rerun the cache callback validation. The [current root receipt](../evidence/bortus-current-checkpoint-root-20261014.json) contains the hashes and scopes.

This completes the public TCP sample and cleanup evidence. It does not authorize private material delivery into a different holder or prove future CNI enforcement. The next recovery work must prove isolation on the same live holder used for accepted private backups, then restore and validate all required rows/keys. Private recovery, final image/security, performance and guarded live acceptance remain open. Node V8 is still compiling; the CPU trace remains held, and the two missing A16 browser permutations have a source-only current-runtime adapter in preparation. No production adoption or original-data retirement occurs.

## 2026-10-14: V8 build interrupted; partial evidence retained

The original build handle is missing. Authoritative Docker metadata reports the exact owned container exited 255 at 05:08:07 UTC, Running=false, PID=0 and OOMKilled=false. WSL's boot ID changed. Neither the actor terminal nor the build-phase terminal exists; no compiler exit, interruption cause or successful build is inferred. Header generation/configuration had exited zero. No new ELF, default-suite, runtime or security qualification follows from this partial output.

Root verifies original CID/name/source labels and immutable image, then removes only the already-stopped experimental container without force or volume deletion. The first cleanup wrapper exits 1 after removal because its absence parser expected empty output/capitalized text; actual Docker returns a JSON empty array and lowercase missing-object error. A separate read-only audit prefix also refuses on that case-sensitive check before new queries. The corrected separate audit performs metadata-only exact CID/name absence checks, retains hashes for 73 partial records and verifies six original actor-source files unchanged. Root later verifies those records remain current and six current-boot query/observer births are absent. No historical PID coordinates are compared or signalled across boots, no build/remove is replayed, and output bind directories remain intact. This narrow interruption audit does not revalidate the full input projection trees or substitute for the prepared 900-second success/failure post that requires a real actor terminal; that post remains unrun.

The completed public TCP/cleanup evidence belongs to the prior boot and remains historical evidence. Private execution needs current source/cache custody and proof on its own live holder. The quiet interval can now be used for the prepared CPU/GC trace before a fresh build owner is considered. Original benchmark failures and all acceptance gates remain unchanged; no deployment, original-data retirement or whole-goal completion is claimed.

## 2026-10-14: bounded CPU/GC observation completed

The [root CPU/GC receipt](../evidence/bortus-sync-hs256-cpu-gc-trace-root-20261014.json) records actual actor/exact/fresh/later exits zero. All 13 complete 1,000-Pod bodies, 41 SQL queries and 26 Next spans pass unchanged; warm reads use no CLI and retain 12 memo hits. Root verifies the 130 main/91 worker/39 client numeric samples, current source371+4/input35/compiled5382/dependency40635 guards, 19 recorded identities absent and exact container/name absence. A later check confirms three reader/query births absent and all three numeric hashes current. An initial later-reader metadata attempt selected the wrong exact-receipt filename and failed before writing a result; the corrected filename-only read succeeds without repeating the actor or post tests.

Root independently recomputes ordinary warm HTTP wall brackets of 4.903–4.940 ms and main-thread CPU median 2.3245 ms. Whole warm windows show substantial server/client CPU, but narrow counter deltas sometimes exceed their wall upper bracket: 2/12 middleware-to-route, 3/12 route, 6/12 IPC wait and 7/12 client oracle windows. These public counters do not attribute per-stage CPU or prove idle scheduling. Server observed GC lies between sampled HTTP windows in this observation; GC delivery coverage remains incomplete, so absence of observed overlap cannot exclude GC. Process and thread counters overlap and nested windows must not be summed.

No source correction or performance acceptance follows yet. The next direct diagnostic samples compiled-server function stacks with the same workload/oracles and explicit profiler overhead/output bounds; it does not alter the original benchmark, fixtures, permissions, freshness or runtime limits. A07/A21 remain failed/open, the candidate remains isolated, and no production or original-data retirement occurs.

## 2026-10-14: function profile closes; performance gate stays open

The [function-profile receipt](../evidence/bortus-sync-hs256-function-profile-root-20261014.json) records one actual profile exit zero and unchanged 13 complete 1,000-Pod responses, 41 SQL queries and 26 Next spans. All three new profile-parser controls pass. Two private profiles total 709,585 bytes; the main thread has 91 warm samples (51 within HTTP), the database worker 92 (53 within HTTP). Idle self samples are 42 and 85 respectively. These are sampled counts with profiling overhead, not CPU milliseconds or latency shares. There is no dominant application, SQL or JWT hotspot supporting a distinct source correction; earlier equivalent response-body variants remain rejected. No further timing/profile variant is selected, no original benchmark is replayed, and A07/A21 remain failed/open.

The first independent profile reader fails because its new window calculation uses framework HTTP endpoints instead of the original parent request endpoints. A separate reader corrects only that collection and independently reconstructs both raw profile trees, sample arithmetic and file mappings. Exact/fresh/later checks exit zero: source371+4, input46, compiled5382 and dependency40635 authorities remain current; 19 runtime identities and exact container/name are absent, followed by three reader/query births absent and both raw hashes current. Neither actor nor workload is repeated. Raw names/URLs stay private; output byte limits remain post-exit acceptance bounds, not a native profiler disk-write cap.

The 13:18:18 UTC read-only cluster snapshot still shows three Ready nodes, 54 Bound PVCs, 33/33 active Ready Helm releases and the existing BORTUS image Ready with zero restarts. BORTUS's HelmRelease in flux-system remains suspended. All 40 Longhorn volumes retain encryption/two replicas: 30 attached/healthy and ten detached/unknown. Metadata acquisition exits zero; an initial saved-result formatter assumes the wrong HelmRelease namespace, then a corrected local reader summarizes the same retained response without another remote acquisition. This is health metadata, not rollout or recovery acceptance.

The exact application commit is recovered into a new clean managed checkout after the old checkout directory is found absent; retained verified build authorities continue to back the diagnostic. A fresh Node V9 owner starts after profiling closes, retaining the original 10,800-second/60-second closure and 2CPU/8GiB limits, default tests and authenticated inputs. It reuses no interrupted V8 output; build, new ELF and security qualification remain pending. The two-case Windows Job control attempt refuses its exact-two-process assumption after observing four owned members; the helper reports every member closed. Browser/app runtime has not started. The correction must retain full bounded job census/closure and require the expected parent and descendant, with actual image metadata. Original migration data/backups and production remain preserved; the goal remains active.

## 2026-10-14: current cache custody and source guards; browser closure remains open

The [current-cache receipt](../evidence/bortus-current-cache-d917-root-20261014.json) records a fresh current-boot read-only attestation: actual original caller/TTY exit zero in 22.558 seconds under the unchanged 75-second local/60-second remote limits. All 17 original/new observer source bytes remain current, eight recorded remote and four local identities are absent, and the last SSH identity is freshly absent. Thirty-six current raw records are frozen in a 38-member CRC/SHA-verified archive. Sixteen ordered layer names and manifest/config bytes are verified; layer bodies, continuous cache validity and same-holder isolation are not claimed. The foreground closure command exits zero; no unrecorded closure PID tuple is invented. Credential values are not written by this workflow. Historical previous-boot receipts remain separate.

The [same-holder source-control receipt](../evidence/bortus-same-holder-source-controls-root-20261014.json) records twelve passing finite public source guards, including refusal when only the CNI receipt changes. This is source/control qualification, not a live holder or private recovery run. The default source scanner returns one finding: an exact public source-code checksum at source-bindings.json:18, independently reproduced from the original Git blob. The literal finding stays recorded without suppression or a green relabel. Concrete source composition now binds the real source graph and accepted encrypted32/snapshot paths; an executable original private600 caller, real same-holder gate and independent restore/oracle closure remain pending. Fresh Node V9 generation and configuration exit zero; compilation/default-suite/runtime/security acceptance remain pending.

Two normal/timeout Windows Job controls and a scoped optional-image metadata control pass. Browser assertions repeatedly reach both requested A16 checks with the exact five GET200/one PUT502 sequence, but the completed workflow remains unaccepted. Preserved failures distinguish the first optional-image query denial, the one-shot gate pipe deadline, and later process-object absence checks despite a normally exited driver and empty owned job. Their independent failure readers preserve actual exits one; no partial report is promoted to acceptance. The latest attempt records a still-queryable Chrome birth after the existing five-second check, without recording its historical live/signaled state. That state cannot be guessed from a later absent PID. A Windows kernel liveness control and correctly named liveness metadata are required before any further acceptance. Original assertions, data fields, benchmark, resource budgets and production remain unchanged. A07/A21 and full migration/recovery/live acceptance stay open; original data and backups remain preserved.

The separate real Windows process-state control exits zero: an exited process remains queryable with the same creation time while its held handle is open, yet the kernel wait is signaled and exit code is zero; a running process returns WAIT_TIMEOUT/STILL_ACTIVE. This matches [Microsoft process termination semantics](https://learn.microsoft.com/en-us/windows/win32/procthread/terminating-a-process). It does not infer the historical state of the failed Chrome birth. The correction will report retained signaled objects separately from absent objects and require no live recorded births, exact identity, empty owned job, reaping and closed owned handles. Live, failed or uncertain kernel state must refuse; prior failed workflows remain failed.

## 2026-10-14: two missing A16 browser cases verified

The [A16 root receipt](../evidence/bortus-a16-two-cases-root-20261014.json) records actual server/browser exits zero and independent exact, Linux, Windows and later checks zero. The unchanged two cases verify that a failed save retains the draft/error, discard and reopen clear them, and View/Edit fetch the actual changed resource version. The exact five GET200/one PUT502 sequence passes against the retained compiled application. All 371 source files plus four generated files, 5,382 compiled objects, 40,635 dependencies and 481 browser dependency files retain their qualified bytes. No product source changes or original performance benchmark replay occur.

The corrected Windows observer distinguishes kernel liveness from process-object queryability. One original Chrome object is still queryable but signaled with exit zero; it is explicitly reported as retained, never absent. The owned job is empty, its child reaped and owned handles closed; twelve recorded Windows births have no live process, 39 Linux births and exact container/name are absent. Three later Linux reader/query births and the Windows reader also close. Existing 480/60/420-second server/closure/attach and 300/330-second browser limits remain unchanged. All four earlier failed workflows remain failed. This qualifies the two finite A16 cases, not mobile, actual screen-reader, delivered-image or performance acceptance. A07/A21, private recovery, final image/security and guarded live acceptance remain open; production and original data/backups remain preserved.

## 2026-10-14: numeric/count browser checks and recovery startup controls pass

The [A13 browser receipt](../evidence/bortus-a13-count-browser-root-20261014.json) records complete server/browser exits zero and sixteen exact direction observations across eight columns: Pods Restarts/Ready, deployment Ready/Up to date/Available, node CPU/memory and storage capacity. It checks zero, positive values, count ties and reachable missing values through the actual routes, preserving each complete name/link/cell tuple. Omitted Pod restart counts normalize to zero; node nulls and storage unknown values sort last in both directions. No API response interception or product source change occurs. Independent exact/Linux/Windows/later checks pass: current371+4 source,5382 compiled,40635 dependencies,30 inputs and481 browser dependencies;62 Linux births and exact container/name absent,10 Windows births with no live process, then three Linux readers/queries and the Windows reader closed. The proposed readiness change is not executed because the frozen first run succeeds. Original budgets remain unchanged. This covers the numeric/count subset, not every table/date column, physical DOM identity, actual screen-reader, performance or delivered-image acceptance.

The separate [private600 startup-control receipt](../evidence/bortus-private600-state-controls-root-20261014.json) records four passing public state/journal controls under the original30/2+1-second bounds,249 unchanged source files and both original supervisor/suite births absent. It permits only an actual admitted, journal-bound API startup-status progression with fixed Pod UID/spec/security and fixed policy/ConfigMap UID/RV. The original admitted journal remains immutable; readiness gets a separate receipt. No Transport, live API or private backup data is used by these controls. The default six-source scan exits one for two embedded public source checksums, independently reproduced from their original qualified files; the literal findings, initial zero-findings wrapper refusal and failed Git-HEAD assumption remain preserved without suppression or pass relabeling. Actual same-holder private recovery remains unproven.

The A16 archive is independently verified:1,756 original members/current paths match the26,762,180-byte CRC/SHA-checked archive, retaining four failed workflows and the final successful two-case workflow. No tests are replayed for archiving. Node V9 compilation remains in progress; performance, final image/security, private recovery and guarded live acceptance remain open. Production and original data/backups remain preserved.

## 2026-10-14: literal recovery and A08 failures retained

Same-holder recovery has two literal failed attempts: the first refused a public source-mode check before Transport; the second created three owned test resources and refused the ephemeral-container dry-run before backup material release. Separate UID/RV cleanup removed all three owned test resources in Pod/ConfigMap/policy order; an independent six-GET observer verifies all three names and recorded UIDs absent, and a later check verifies its seven process identities absent. The public admission diagnostic refused before sending its PUT, so the original API refusal remains unexplained. A08 metadata-error browser attempts also remain failed, with a source-led fixture-order correction prepared. These are open acceptance items, not live recovery passes. The [failure receipt](../evidence/bortus-recovery-attempt-failures-root-20261014.json) binds the actual outcomes and independent observations. No original actor, journal or result was rewritten. Original Gluster/Vault/Consul and accepted backups remain preserved.

## 2026-10-14: focused metadata-error and raw-date browser checks

The two A08 metadata-error browser cases now pass actual404/503 responses, visible errors, no container selector and no log request; four failed actor attempts and the first failed Windows reader remain retained. A separate strict Windows reader and independent Linux/current-source/cleanup checks pass. A13 Pod and Deployment raw-date Age sorting also passes both directions, missing-last, duplicate-date name ties and preserved row identity. These focused results do not qualify every table, actual assistive technology, performance or the delivered image. See the [A08 receipt](../evidence/bortus-a08-metadata-browser-root-20261014.json) and [A13 date receipt](../evidence/bortus-a13-date-browser-root-20261014.json). The corrected Node post verifies101 records and exact build-container absence while retaining build0/default-suite2 and original actor1; it provides no new ELF/runtime/security acceptance.

## 2026-10-14: fresh legacy sorting functional qualification

The legacy /cluster/* sorting correction at fb960307 now passes a fresh build, native load, lint, fresh types,330 unit tests and eight HTTP integrations. Independent checks verify373 current source files,396 inputs,5382 compiled objects,40635 installed objects and closure of168 recorded process identities plus four exact container IDs/names; a later check verifies the nine reader/query identities closed. Its first ten-column browser run fails after six columns/twelve directions because the legacy Nodes page can match an earlier shared IP before the exact hostname. The failed run and independent cleanup remain retained; the minimal hostname-first correction at6718193 awaits a new331-unit/eight-integration build and the unchanged browser checks. See the [root functional receipt](../evidence/bortus-legacy-sort-full-root-20261014.json). This is local functional evidence, not performance, final image, compiled worker SQL or production adoption. The original benchmark remains failed; original Gluster/Vault/Consul and accepted backups remain preserved.

## 2026-10-14: latest isolated qualification outcome

The [6718193 qualification receipt](../evidence/bortus-legacy-node-identity-qualified-root-20261014.json) records fresh build, native load, lint/types,331 unit tests and eight HTTP integrations, followed by all ten legacy sorting columns/twenty directions. Independent checks bind373 source files,401 functional inputs,5382 compiled and40635 installed objects;177 functional births and later nine reader/query births are absent. Browser checks bind35 inputs,77 Linux births absent and11 Windows births with no live recorded process, followed by separate later closure. The initial shared-IP lookup failure and subsequent four incorrectly encoded expected em dashes remain failed; the final attempt changes only those four expected codepoints with nine runtime files unchanged. Its frozen prose says330 tests, while actual executable gates/TAP require331+8. Root independently verifies all4849 originals against their69737176-byte CRC/SHA archive. This qualifies finite local functional/browser behavior only; actual assistive technology, performance, delivered image and adoption remain open.

The [public admission receipt](../evidence/bortus-public-admission-qualified-root-20261014.json) records one direct-TLS ephemeral-container PUT with dryRun=All returningHTTP200 against a fresh owned holder and immutable UID/resourceVersion intent. The whole proof volume is mounted read-only; all six API file flags point beneath its proof directory. Before/after persistent payloads and UID/RVs match. Independent reads verify244 current source files and415 original births absent. UID/fresh-RV cleanup naturally deletes Pod,ConfigMap,policy in order; a separate six-GET observer confirms every name/recorded UID absent, other6 Pods/1 ConfigMap/0 policies preserved, and88 cleanup/reader/query births absent. The source scanner literally exits1 with seven independently reviewed public findings: six checksums and one invalid public test PEM fixture; no suppression or green relabel occurs. No private password/backup material is released. This is current public admission proof, not private restore/API recovery acceptance; prior failed attempts remain failed.

The [Node continuation outcome](../evidence/bortus-node22-continuation-outcome-root-20261014.json) records offline documentation installation exit0 with279 exact-lock packages, then unchanged make -j2 test-only JOBS=2 exit2: two original cluster scripts time out after120seconds and the pending-DNS setServers test misses its expected exception. The version phase is not run. A live read-only sample binds114 zombies to the exact owned Python PID1; this establishes deficient orphan reaping, without retrospectively identifying the failed worker PIDs or proving the DNS cause. Independent outcome/custody checks exit0 with78 records, original51008-object workspace/physical fingerprint and810-object cache current,14 original births and exact CID/name absent; three later reader/query births are absent. The generic terminal SHA equals an older failure because its JSON bytes match; distinct started/phase/post records establish this execution. Runtime/security/image acceptance remains unproven. A separate bounded unchanged-script baseline/init and DNS observation is prepared; no suite skip, weakened oracle, performance replay or adoption is authorized by these results.

## 2026-10-14: recovery API mount integration

The migration source now integrates the exact API spec used by the [successful public admission dry-run](../evidence/bortus-public-admission-qualified-root-20261014.json). Only the ephemeral API mounts the complete proof volume read-only at `/memory-proof`; its six certificate/key/encryption file flags use `/memory-proof/proof/`. The ordinary init, utility and etcd mounts retain their existing writable subdirectory paths. Kubernetes forbids ephemeral-container `subPath`/`subPathExpr`; neither field is proposed. The matcher also permits only the literal empty `resources: {}` default on ephemeral containers; nonempty, null or mistyped resource objects remain rejected. This two-line matcher normalization was already present in the frozen diagnostic source, but absent from the migration repo. The integrated spec is byte-identical to that qualified diagnostic. Fifteen pure regression tests pass, including unsupported mounts, old file paths, writable access and resource-default drift. The added tests first fail against the old repo spec. See the [integration receipt](../evidence/bortus-api-volume-integration-root-20261014.json). No frozen old actor is repinned or rerun; a fresh private-recovery actor still needs current authorities and separate complete execution.

## 2026-10-14: Node init and DNS diagnosis

The [finite init/DNS diagnostic](../evidence/bortus-node22-init-dns-diagnostic-root-20261014.json) exits zero, followed by an independent zero-exit source/workspace/closure check. Both unchanged cluster scripts time out after 120 seconds with Python as PID 1, then both pass with the exact verified Docker init executable. In both cells the existing one-server DNS configuration yields ECONNREFUSED without the expected pending-query exception; a real reachable loopback sink receives one DNS datagram and preserves ERR_DNS_SET_SERVERS_FAILED until cancellation. Actual Node 22.23.3, OpenSSL 3.5.9 and module ABI 127 assertions pass. This supports a runner reaping and resolver-environment correction; it does not turn the failed original full suite into a pass. The selected direct-test environment differs from full-suite PATH/unused Git variables and uses new owned HOME/TMPDIR/NODE_TEST_DIR/TEST_SERIAL_ID scratch. Source, test bodies, original frozen 51008-object workspace/physical fingerprint, network-none and fixed 2CPU/8GiB/no-swap/512-PID limits stay intact. Independent checks verify 29 original host births absent and both exact created CIDs/names absent; five reader/query births and the saved later checker birth are also absent on the same boot. V1 stays unrun; the executed V1.1 adds directory fsync, held/revalidated actual-init executable/namespace FDs and independent deadline-protected socket cleanup. No original performance benchmark, private recovery, production rollout or data retirement occurs.

## 2026-10-14: current6e raw source independently qualified

The [raw-source qualification](../evidence/bortus-current6e-raw-source-qualified-root-20261014.json) records the distinct V3 exporter and child at exit zero. Independent verification reconstructs the full 375-entry Git tree and checks every selected blob, mode, size and SHA-256, complete gzip/tar boundaries and no extra members: 282 included files, 93 excluded entries and eleven migrations. All 472 recorded process births are freshly confirmed no longer live; the independent reader is also closed. Seven optional image queries returned error 5 and one returned 31 under the qualified stable-birth/membership predicate. The default production-source scan passes with zero findings across all 282 selected files, unchanged bytes and scanner birth no longer live. The earlier V1/V2 partial archives remain failed and unaccepted. Current6e COPY context and newNode component are qualified separately; COPY-only image assembly, full-filesystem/default image scan, runtime/native/TLS, performance and guarded live acceptance remain pending. No production image or recovery guard changes.
