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
security review, A07/A21 performance, three-node delivery, active guards,
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
