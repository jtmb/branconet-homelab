# BORTUS application deployment

Integration contract for the migration coordinator. Cluster provisioning, Secret import, charts and live acceptance belong to the migration chat. This change never imports or pushes old SQLite values.

## Image and storage contract

Build from repo root: `docker build -t bortus:local k8s-rewrite/front-end`. Override `--build-arg KUBECTL_VERSION=<cluster-compatible-version>` for dashboard CLI operations (default v1.34.1); native Secret API has no kubectl dependency. Docker build excludes env/SQLite/kubeconfig files. Runtime entrypoint runs Prisma migrate deploy and requires signing/lookup env before starting the standalone server. Missing DB schema on existing installations requires a consistent backup and baseline/migration assessment before deploy; never reset production DB.

Kubernetes liveness/startup probes: HTTP /api/health/live port 4000. Readiness: /api/health/ready, timeoutSeconds at least 10. Configure readiness period 30s and protect these endpoints from external probe floods. Network policy must permit app to Kubernetes API TCP 443/6443 and DNS; browser/Bearer ingress needs TLS. Mount aliases from a ConfigMap read-only. No host SSH private keys are needed. For a PVC use fsGroup 1000; allow writable /app/.next/cache and /home/shell for existing dashboard operations. Use one replica/Recreate to avoid concurrent SQLite writers/schema deploys.

The app uses Node 22, Next.js 15.5.27, Prisma/SQLite and the official Kubernetes JavaScript client 1.4.0. The installed Next package lacks `node_modules/next/dist/docs/`; implementation follows the official [Next 15 route guide](https://nextjs.org/docs/15/app/api-reference/file-conventions/route) and [standalone guide](https://nextjs.org/docs/15/app/api-reference/config/next-config-js/output).

Build context: `k8s-rewrite/front-end`. Port: 4000. SQLite: `/data/bortus.db`, persistent RWO PVC at `/data`, one replica, Recreate strategy, UID/GID 1000. SQLite stores users/password hashes, roles, nonsecret configuration and lookup metadata. Run migrations before traffic; back up consistently. Legacy sensitive rows are quarantined from APIs, never used as fallback. After separate import/readback acceptance, scrub obsolete working DB values and protect historical backups outside Git.

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
migration/restart. Liveness returned200; native-unavailable readiness returned503.
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
