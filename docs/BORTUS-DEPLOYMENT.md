# BORTUS application deployment

Administration entry wiring, captured destroy pathRevision and separate consumer rotationIdMarker change UI/public metadata only. They add no migration, native format, runtime input, RBAC verb or automatic consumer reload. Combined Node22 140-unit/four-HTTP/build/type and recorded actual-route browser subset passed. Final coherent Linux image/recovery qualification remains pending; the isolated maintenance image does not qualify these later changes.

The combined metadata/workbench source passed its recorded local Node22 unit/build/HTTP and native-browser subset. See implementation-evidence/kv-workbench-integrated.json; this is not final-image qualification. Its on-demand dialog entry adds no runtime input, migration or native verb and preserves externally verified guarded-mode requirements. The a82a6cb/ea849ee Linux QA image does not contain these later UI/request changes; final coherent image/schema/lock/migration/recovery qualification remains open.

Application deployment contract. Main includes BORTUS source and documentation alongside the existing Swarm homelab. Kubernetes charts, provisioning, Secret import and live Flux source configuration remain separate deployment work. Publishing this application never imports or pushes old SQLite values.

The live chart is maintained in the separate private `jtmb/branconet-charts`
repository at `charts/bortus`; effective overrides are in `flux/releases/bortus.yaml`.
The CI-validated Flux source is `branconet-charts` and its existing Kustomization
is `migration-releases`. Production remains `bortus:migration-1438b27`, preloaded
on all nodes with pull policy Never. See the [reviewed image-release procedure](FLUX-GITOPS.md).

## Image and storage contract

### Current backend checkpoint for independent qualification

Independent delivery commit `a82a6cb9e244b0ec05489bc7251f3e29411c64dc` records functional Linux/runtime/callback and eleven-migration/restart qualification for ea849ee, with exact committed blob/mode/schema/lock agreement. The app inspected selected evidence fields; the local QA RepoDigest is not a final-image or recovery approval. Package advisories remain open. The later completed Trivy/security report is local and uncommitted, with vulnerability gate false; vendor/architecture observations and the proposed scoped deepmerge-ts fix do not replace app qualification and a fixed-image rescan. See [stack maintenance status](TECH-STACK.md) and [implementation provenance](BORTUS-IMPLEMENTATION.md#runtimechart-interface). Later UI/query/pathRevision changes are a separate source state and must enter the final coherent image/recovery qualification.

The isolated [dependency/runtime maintenance handoff](implementation-evidence/runtime-maintenance/README.md) qualifies corrected source `483ba4f0c82cbaca76646f221c4c497f8c298d70` from the app owner's committed `74500af`. Its pinned Node/bookworm build, fixed Perl floor, default kubectl v1.37.1 and removal of runtime package managers pass Linux quality and image fresh/legacy eleven-migration/restart checks. Exact source/base/image/archive/scanner/database identities and residual findings are retained there. This is a local QA artifact; the owner's subsequently integrated UI source and final release/recovery image still require their own exact qualification. No deployment, admission allowlist, native resources or databases changed.

Immutable source `ea849ee1f5b13031c4a6af79c4756ceddb68fc8a` is eligible for independent Linux/image qualification of the current backend/schema baseline. Its 113 unit tests, zero-warning lint, fresh Windows Node 22.23.3 standalone build/typecheck and all three production HTTP/TLS fixtures passed. It includes consumer reload identity, legacy-impact audit/controls, Flux/provisioning confidentiality and adaptive aggregate Secret reads. This is not approval of a final recovery image or the complete UI/performance goal. Build from that Git commit and the clean Docker context; the follow-on Secret table stage is a different source state, qualified locally in [its own evidence](implementation-evidence/secret-tables.json).

The exact committed schema SHA-256 is `06abf29e554e101a7b048c7334c9a3eae12c6e78c7f399f709ee2e7b14ecc409`; package-lock SHA-256 is `e056b09e00442c0896ae9a863995414b3b18504c1626bc9b2c645634b5e83fb2` (Git blob bytes, rather than Windows working-tree line endings). Apply all eleven forward migrations in order: `20260614204135_init`, `20260615042521_add_gitrepos`, `20260615170328_add_namespace_to_gitrepos`, `20260616050858_add_user_model`, `20260616130024_add_app_settings`, `20260616132006_add_user_role`, `20261009150000_native_secret_references`, `20261010160000_account_invariants`, `20261010210000_kv_metadata`, `20261010220000_rotation_consumer_identity`, `20261010230000_legacy_access_audit`. Preserve accounts, hashes, session versions, aliases, grants, current/history ownership, operations and rotation intents; no reset or value ingestion. Native canonical/history format-1 is unchanged. Old flat or earlier schema/API images remain unapproved recovery choices.

Keep Node 22/Linux, UID/GID 1000, port 4000, one replica/Recreate and the SQLite PVC. Signing/legacy lookup keys and kubeconfig/in-cluster credentials remain externally supplied, stable, TLS-verified and independent of bootstrap. Preserve the explicit existing 18-namespace current allowlist; history defaults to separately created `bortus-history`. Retention defaults 20, maximum 100. Keep `BORTUS_DISABLE_PROVISIONING=true` for the container and `BORTUS_KV_GUARDED_ADOPTION=false` until external qualification. The distinct guarded principal is `bortus-kv`; current scopes require Secret get/list/create/update and history get/list/create/delete, without history update/patch or canonical delete. Existing readiness/probe metadata negotiation, protected PVC/runtime credential references and immutable-compatible-digest admission/RBAC requirements below still apply. A true adoption flag is an operator assertion, never app proof of those guards.

No extra database/protocol migration is planned for the active Secret metadata-table stage. Broader UI/workflow/recovery and final-image acceptance remain open; any later backend/schema/protocol change requires a new exact-commit qualification contract. This checkpoint can be qualified now without adoption, rollout, live RBAC changes or a claim that the finished release is complete.

The locally qualified legacy-control stage adds forward metadata-only migration 20261010230000_legacy_access_audit: nullable principal/alias/key columns on KvAudit. Forward migration tests preserve existing accounts, audit rows and alias grants without native value ingestion. Apply normal forward migrations before traffic; never reset SQLite. Legacy principal/policy/grant controls do not add native verbs or rotate the external lookup key. Principal disable affects nonsecret lookup as well as aliases. Readiness checks the new columns. See [local evidence](implementation-evidence/kv-legacy-access.json); final recovery-image compatibility remains pending and must include this additive schema.

The optional named consumer reload adds forward metadata-only migration `20261010220000_rotation_consumer_identity` (nullable consumer UID/RV on KvRotation). It never stores values. Apply migrations before traffic without resetting SQLite. Reload is effective-administrator-only and additionally requires rotate policy, an explicit same-namespace Deployment/StatefulSet/DaemonSet and displayed UID/RV; reviewed get/patch permissions for that consumer are required. No grants are created automatically. Migration/reload qualification passed locally; final recovery-image compatibility remains pending.

Readiness stops scheduling additional scopes after a failed probe and retains the shared worker until already-started probes settle within their native deadlines. Overlapping requests cannot detach those probes and start another refresh immediately. This failure lifecycle passed the focused regression and the final full unit/HTTP run.

Build from repo root: `docker build -t bortus:local k8s-rewrite/front-end`. The Node 22.23.3/bookworm-slim base is pinned by digest; installed Debian security packages are upgraded and `perl-base >= 5.36.0-7+deb12u4` is required. Default kubectl is the currently released v1.37.1 patch, checksum verified, for the 1.37 cluster. Override `--build-arg KUBECTL_VERSION=<cluster-compatible-version>` only with a separately qualified supported patch within one minor of every API server ([official policy](https://kubernetes.io/releases/version-skew-policy/#kubectl)); native Secret API has no kubectl dependency. Record the actual base/runtime/image/package identities because APT updates can change subsequent artifacts. Docker build excludes env/SQLite/kubeconfig files. Runtime package managers are removed; the entrypoint invokes the installed local Prisma CLI with Node, runs all forward migrations and requires signing/lookup env before starting the standalone server. Missing DB schema on existing installations requires a consistent backup and baseline/migration assessment before deploy; never reset production DB.

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

Flat metadata lists retain exact key/type/immutable/RV summaries and project pages immediately. Native production schedules up to four namespace workers in the existing four-request/64-queued pool, with one shared aggregate budget and failure cancellation of owned reads. Compatibility stores retain serial defaults; see [native scheduling qualification](BORTUS-NATIVE-LIST-PERFORMANCE.md). Full-list GET pages start at 20 objects and only locally oversized successful responses reduce through 10/5/2/1, keeping their cursor and smaller limit. Rejected body prefixes count toward one shared 32-MiB received-body/10,000-accepted-object/15-second scope budget. Metadata-only negotiation and mutations never retry/fall back. Local 100-test/build/HTTP and resource-limited Linux fixture qualification passed; large-record retries cost transfer/CPU/memory, and final server/image/live acceptance remains separate. See [adaptive read evidence](implementation-evidence/secret-adaptive-read.json). No native verbs, runtime env or operator limits change.

Mount a metadata-only ConfigMap JSON file via `BORTUS_SECRET_ALIASES_FILE`, or register aliases using `/api/secret-references`. File format:

```json
[
  {"alias":"secret_gluetun_vpn_openvpn_user","namespace":"gluetun","name":"vpn","key":"openvpn_user"},
  {"alias":"legacy_vault_path/user","namespace":"gluetun","name":"vpn","key":"openvpn_user"}
]
```

Multiple aliases can reference a key; one alias cannot reference multiple targets. File/DB conflicts fail. No underscore parser. Import mapping must preserve every Vault/Docker alias explicitly; ConfigMap metadata can be committed, values cannot. Native Secrets need RBAC, encrypted etcd storage and tested recovery.

## Bootstrap/recovery

Repository cascade removal retains native authentication Secrets and reports retained credentials. No inferred name establishes ownership and no canonical Secret delete verb is added. Explicit key/version cleanup requires exact target/consumer review; dedicated owned-history deletion is a separate guarded KV contract.

Dashboard deployment attribution additionally lists apps/replicasets to follow controller UIDs. If that permission/resource is unavailable, deployment responses expose partial availability and null ownership/restart data. Ensure this separate dashboard RBAC when accepting the new image. Structured kubectl work shares four active/64 queued slots with deadlines and output limits; write-role /api/cluster/diagnostics exposes process-local counters without values. No native Secret verbs changed in this cache/state stage.

The resource-capability stage adds pod log get, pod exec create, node patch and pod eviction create to the relevant separate dashboard RBAC when those operator features are enabled. Node drain also reads pods/daemonsets and respects PDBs. Service/PVC YAML remains read-only; ingress YAML/delete follows its existing resource permissions. Validate each capability with the deployed ServiceAccount; UI support is not proof of Kubernetes authorization.

Optional nonsecret runtime flags BORTUS_DISABLE_OPERATOR_SHELL=true and BORTUS_DISABLE_POD_EXEC=true disable the corresponding handlers. Windows operator shell is always disabled. Session capabilities mirror these server gates; the container continues to disable provisioning. Scoped YAML replacement requires resourceVersion and never accepts Secret manifests.

The `/secrets` editor uses the existing dark dashboard layout, explicit value reveal and versioned writes. `/configuration` edits nonsecret variables separately. `/api/health/live` and `/api/health/ready` are exact public probe paths; readiness checks signing/lookup env, migrated SQLite and Kubernetes access across the namespace allowlist.

Keep operator kubeconfig, SSH keys and provisioning credentials independently available in a protected operator environment/offline store. Creating a cluster cannot depend on its unavailable Secrets. Container provisioning is disabled; migration runs Ansible externally. Local Ansible integration retains Bearer lookup for mapped native Secrets/nonsecret config. The optional runner generates a temporary fixed stdout callback from its bundled source, accepts only site.yml/supported roles, and withholds raw diagnostics before job persistence. Isolated Ansible-core 2.20.0 producer and Windows production consumer qualification passed; full Linux runner/image acceptance remains pending and no Python/Ansible runtime is added to the container. Supply bootstrap credentials independently, and use `no_log` for sensitive tasks in the external environment. See `SECRETS-ENGINE.md`.

## Validation ownership

The standalone [KV administration UI](BORTUS-KV-ADMINISTRATION-UI.md) is qualified against disposable production Next routes, temporary SQLite and CA-verified synthetic native APIs. It changes no deployment/RBAC/migration contract and uses no operator credentials. It still requires owner screen integration and the documented shared API corrections; these Windows fixture/browser passes do not qualify a final Linux image, installed guards, real consumer receipt or live rollout.

Readiness/alias bounds passed local unit and production HTTP/TLS qualification. Public readiness now coalesces bounded metadata-only probes (limit one), checks forward account/KV metadata and aliases, and includes history only when guarded mode is enabled. Use timeoutSeconds at least 10 for the nine-second dependency budget. A ready response remains a dependency read check; it does not certify write verbs, admission, old-principal revocation or recovery backups. No extra native verbs are required.

History destroy/GC APIs passed local unit and production HTTP/TLS qualification. The dedicated history namespace needs get/list/create/delete, including UID/resourceVersion delete preconditions; current namespaces retain get/list/create/update without delete. Metadata-only list negotiation must be supported by the API. No app code creates namespaces or RoleBindings. Final external guard/image/RBAC validation remains required before adoption.

Bounded v1 import/export and audited value-release decisions passed local unit and production HTTP/TLS qualification. They require no additional native RBAC verbs. Values remain in transient request/response memory; path revision/head/RV and explicit overwrite protect existing documents, and audit availability gates value release. Final transfer UI/image/live validation remains pending.

Scoped automation and filtered audit/capability routes passed local production HTTP against the verified mock API. Token cookies/legacy/session audiences are denied, expiry/revocation is fresh, and middleware authentication failures are private/no-store. These checks add no native verbs and do not establish external admission/RBAC or final Linux-image acceptance.

The local native KV HTTP suite starts a disposable production server against a CA-verified HTTPS mock API and synthetic SQLite/accounts. It restarts guarded mode off/on, verifies current/historic binary values without recording them, scope/readonly/legacy/flat denials, version prerequisites, drift/reconcile/rollback/tombstone and administrator revocation. Local native route qualification passed, including empty first creation and refusal to recreate a missing source with prior history. This does not establish live Kubernetes/RBAC or Linux-image acceptance. OpenSSL is required rather than silently skipping this suite.

An additional TLS transport test generates temporary self-signed test credentials with OpenSSL and talks to an HTTPS mock Kubernetes API using the real client/CA/token. It verifies create/read/update/list/delete and body-only value transport. This is still a mock API, not cluster acceptance. OpenSSL absence skips that test explicitly.

`npm run test:integration` requires a completed build. It migrates a fresh temporary SQLite DB, checks zero schema drift, starts the production standalone server on loopback, and validates real registration/roles, variable redaction, Bearer lookup, stale DB rejection, unavailable readiness, alias collisions and demotion enforcement. It uses fake credentials and an unavailable loopback Kubernetes endpoint, then removes its temporary DB. It never touches the operator DB or live cluster.

`npm test` covers imported reads/restart against a mock API, explicit aliases/underscored keys, metadata/type preservation, key/last-key deletion, collisions/races/immutability, outage/error redaction, sensitive DB classification, role/Bearer boundaries, exact middleware exceptions and insecure kubeconfig rejection. `npm run typecheck` and `npm run build` verify application integration. Actual results are recorded after execution below; Docker/live acceptance require the migration environment.

Mock tests establish API/alias/preservation behavior only. Live migration must prove imported values without logging them, authorization, lookup/edit/delete, readonly denial, conflict/outage behavior, restart persistence, no DB overwrite and recovery. Record image/live evidence separately; unit tests do not establish AC7 acceptance.

## Build blockers repaired

Alias registration rechecks any concurrently inserted DB mapping before returning success. The unique alias constraint rejects create races; mapping targets are never silently remapped.

The baseline included stale /cluster component imports, icon title props and shell-state comparisons that prevented type checking. Minimal compatibility corrections are included to make the container build usable; route/UI behavior remains documented in the existing API/resource guides. Private Flux credentials now use native API bodies, not SQLite or kubectl literals. seed-db.sh is retired because its old unauthenticated password flow is incompatible.

## Scoped main integration validation recorded 2026-10-10

The integration branch starts from main fa9c226 and imports only the BORTUS app snapshot 1438b27, scoped instructions/ignore rules and matching application documentation. Original main files are preserved, with an additive README link. App source differs from the accepted snapshot by whitespace cleanup and an equivalent named boolean for the user-create button validation; generated tsconfig.tsbuildinfo is excluded. GitGuardian had misidentified the adjacent Tailwind class string as a generic password, so validation was moved out of that JSX attribute without changing behavior.

- Clean npm ci: passed.
- npm test: 11 passed, 0 skipped, including verified HTTPS transport against a mock Kubernetes API.
- npm run typecheck: passed.
- npm run build: standalone production Next 15.5.27 build passed from the fresh checkout without env files.
- npm run test:integration: 1 passed, using fresh temporary SQLite, zero migration drift, real production HTTP auth/roles, metadata, quarantine and unavailable native lookup.
- git diff --cached --check: passed; no legacy file deletions or Kubernetes charts/provisioning changes are included.
- Main contains no .github/workflows files, so this publication has no repository-defined main push/merge workflow that deploys Swarm or provisions the cluster.
- Host validation uses Node v24.18.0 on Windows; the image specifies Node 22/Linux. Docker is unavailable on this host, so no image was rebuilt during this scoped integration.
- The separate migration coordinator reports the migration-1438b27 image loaded on all three hosts, readiness and native Secret/auth/restart/outage/recovery checks, and human login/UI acceptance. This integration did not independently repeat live-cluster checks or change the deployed image/Flux source.
- Known inherited dependency advisories remain: 12 high and 4 moderate, 0 critical. The clean build reports jose JWE compression Edge-runtime warnings; production JWT auth passes the HTTP suite.

Build images from the clean Docker context, which excludes env/SQLite/kubeconfig files. Local standalone output can trace workspace env files; do not distribute output built from a credential-bearing development checkout. The fresh integration build used no env files.

Main tracks only .env.example with empty signing/lookup placeholders and nonsecret defaults. Previously tracked env files were removed from the original development snapshot while the original local files were preserved. Historical development-branch credentials require rotation outside Git; existing history is unchanged. Rotation requires re-login while preserving users and roles.

## Subsequent audit baseline

The remediation branch adds migration `20261010160000_account_invariants`: user sessionVersion defaults to zero and account_lock receives its serialization row. Run the normal forward migration before traffic, with a consistent DB backup; never reset existing DB. Legacy cookies retain version-zero compatibility until a password reset increments their user's version. Deleted accounts are rejected immediately. No live migration/rollout has been performed. See [implementation acceptance](BORTUS-IMPLEMENTATION.md).

The in-progress KV foundation adds forward migration `20261010210000_kv_metadata`: metadata-only mount/path/field/policy/identity/service-grant/operation/audit/rotation tables, and a user engineAdmin column. Existing users, hashes, roles and session versions are retained; existing writers receive engine administration and an initial action grant. No native values or legacy variable values are imported. Local forward migration preservation/zero-drift and metadata/policy unit, production HTTP and browser qualification passed; human native KV routes also passed disposable production HTTP/TLS checks; remaining workflows and final KV image/live acceptance are pending. The guarded adoption, history namespace and principal/admission prerequisites in [KV design](BORTUS-KV-DESIGN.md) must be validated before a finished KV image is eligible for adoption; the pre-KV image is not a compatible post-adoption rollback image.

Before adoption, the old app principal must lose credential-reaching exec/workload permissions as well as Secret verbs. Compatible-image admission must additionally protect the migrated SQLite PVC regardless of principal: an old user API with that database could reset/promote a broader-policy identity. Check all regular/init/ephemeral images and relevant controller templates, reject old-image access to the claim, and verify no pre-existing old image still mounts it. These external guards remain uninstalled/unverified by the app executor; the local flag alone is never proof. KV-compatible image/schema and independent metadata/native backups are the supported recovery contract.

The [2026-10-10 audit](BORTUS-AUDIT.md) starts from merged main c2e22ca and reran unit, typecheck, production build and isolated HTTP integration checks successfully. It also reproduced account races/revocation gaps, kubectl argv/error bugs and UI issues using disposable fixtures. Passing the existing suite does not cover those findings. Healthy-cache coalescing and failed-read fanout were measured locally; Node 22/Linux image, real-cluster latency and full screen-reader checks remain unperformed in that audit. The audit changes documentation/evidence only and performs no rollout or live resource mutation.

## Standalone KV workbench

The standalone [KV workbench](BORTUS-KV-WORKBENCH.md) introduces no runtime environment variables, native verbs or metadata migrations. Its local Windows/Node 24 synthetic/browser and production HTTP checks do not substitute for the integration owner's final Node 22/Linux image, guard/RBAC or live qualification.
