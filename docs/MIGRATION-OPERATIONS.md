# Approved cluster migration operations

The [callable admission probe collector](BORTUS-ADMISSION-QUALIFICATION.md) keeps
permanent guards Flux-owned: complete the fresh cold checkpoint and resume its
Ready writer before publication, then verify exact successful CI/Flux revisions
and six live guard UID/RV/spec pins. Forty dry-runs and durable disposable
Pod/replicas-zero Deployment fixtures share one <=300-second deadline. Complete
LIST name/UID absence is required after owned fixture deletion; failed or ambiguous
mutations remain retained without retries. Local fixtures do not establish actual
cluster admission or restore acceptance.

The callable [independent restore coordinator](BORTUS-INDEPENDENT-RESTORE.md) is
qualified by twelve controlled local cases over current source/watch/mutation/reader/data contracts.
It requires root's separately qualified current image/preload/admission binding,
carries one absolute deadline and retains uncertain targets and journals. It has
no CLI and cannot grant overall live acceptance from callback fixtures.

The callable [inert reader launcher](BORTUS-RESTORE-READER.md) supplies fixed
kubectl exec after fresh owned Pod UID/RV/spec checks, passing only an inherited
protected kubeconfig FD. It sends no program itself; the data step supplies the
exact reader through stdin. Post-read fences and live acceptance remain separate.

The callable [restore mutation adapter](BORTUS-RESTORE-MUTATIONS.md) provides
review-bound, dispatch-once TLS create/delete callbacks under the actual borrowed
watch and durable pending intent. It proves neither admitted specs nor deletion
absence; full executor/source/image/admission/data acceptance remain separate.

Root verified the immutable native mutation handoff and its 106 retained
artifacts, excluded the import-only parent, and qualified the integrated adapter
against the current fixed metadata/source dependencies. All 398 combined local
cases pass without skips on frozen inputs. The
[integration receipt](../evidence/bortus-restore-mutations-integration-20261011.json)
records this preparatory result; it does not establish live restore acceptance.

The pure admitted-resource comparison now validates the reviewed StorageClass,
claim and holder against full fresh GETs and created identities before journal
confirmation. It permits only explicit inert API defaults and separately fenced
claim binding names. Holder deletion needs a complete fresh Pod LIST with both
owned UID and name absent; a terminating holder or replacement refuses. API
freshness, reviewed proposal authorization and the actual executor remain required.

Holder readiness requires exactly one current container state, `running`; conflicting
waiting/terminated states refuse. The pure admitted-spec, absence and shared holder
refusal boundaries clear public raw arguments before raising fixed errors. Callers
must still avoid logging their own input-bearing traceback frames. Fresh source
inspection validates the current writer node as a bounded DNS subdomain before
returning `source_node_name` or comparing alternate placement; malformed non-string
or path-like fields never enter the report. These local guards are not live proof.

The initial proposal report now binds `source_node_name` from its freshly checked
writer for the coordinator's alternate-node expectation. Repeated source checks
remain required; the recorded name does not establish ongoing writer placement.

The acceptance contract and architecture are in [PLAN.md](../PLAN.md); current evidence is in [MIGRATION_STATUS.md](../MIGRATION_STATUS.md). BORTUS application and native-transport development are handled by two scoped sub-agents in separate worktrees. Together with the migration coordinator, these are the three execution agents; former execution chats are archived. Cluster operations remain with the migration owner.

## Current operation and recovery

The checked-in Ansible defaults describe native ingress on 80/443, Pi-hole on 53 TCP/UDP and 8079, conditional LAN DNS, Flux activation and the existing NAS CIFS backup target. DNS/ingress/gitops tags were applied successfully against all three hosts. Application delivery now uses the separate private `jtmb/branconet-charts` repository: main Ã¢â€ â€™ successful current-main CI Ã¢â€ â€™ `validated` Ã¢â€ â€™ `branconet-charts` GitRepository Ã¢â€ â€™ existing `migration-releases` Kustomization. Each chart retains its own values. The old migration source/publisher is retained as a suspended historical checkpoint, not an active delivery path. Raw legacy manifests in chart folders are reference material; only Helm templates are reconciled.

For infrastructure recovery, invoke run-ansible.py with --recovery-bootstrap and appropriate stage tags, supplying its sudo JSON through a protected stdin pipe. This explicitly overrides public-port cutover, native-Pi-hole dependency and Flux activation to false. Before recovery of existing data, recover the original Kubernetes PKI/API encryption configuration, kubeconfig and Longhorn encryption key from the authenticated configuration archives. Do not create replacement keys for existing encrypted volumes. Restore the consistent etcd snapshot using the matching API encryption keys, then recover native Secrets and Longhorn claims from the NAS; establish healthy storage/DNS before enabling Flux and public routes. The isolated etcd and BORTUS NAS restore tests prove those recorded restore cases; they do not establish a complete three-host disaster rebuild.

Native backups use cifs://192.168.0.8/container_backups/k8s-migration-20261009/longhorn and the native longhorn-system/longhorn-backup-cifs Secret. Media exports and their paths remain unchanged. Thirty-one migrated application volumes have completed cold NAS backups; an independent BORTUS database restore passed decryption, SHA equality, table counts and integrity checks. The later repository-only monitor state also has a completed cold NAS checkpoint, bringing backed-up volume coverage to 32, including the two now-retained excluded game volumes. Backup holders are removed only after backup completion; incomplete runs retain their evidence and require inspection before repetition.

The original HTTPS Traefik dashboard is restored at proxy.branconet.lan/dashboard/ with unchanged BasicAuth hashes in traefik/traefik-dashboard-config. migrate-traefik-dashboard.py reads the authenticated retained source configuration directly into that native Secret, fails on conflicts, and writes only deployment references and metadata to Git. Both Ansible and Flux use the immutable original Traefik digest; the dynamic file provider routes to api@internal without enabling an insecure API listener. Source hashes and denial checks are verified; authenticated UI/API proof still requires the existing working dashboard password. traefik-dashboard-proof.py accepts optional existing passwords through --credentials-stdin and never reports them or bodies. BORTUS's existing native Secret role can read the configuration; no app changes were needed.

Keep migration_dashboard_enabled false during --recovery-bootstrap until native Secrets are restored. Then enable the persisted source dashboard configuration before final ingress reconciliation. The bootstrap watcher-limits tasks persist fs.inotify.max_user_instances=1024 at /etc/sysctl.d/98-branconet-inotify.conf; the scoped --tags watcher-limits stage was applied and read back on all three hosts after an exhausted master quota prevented file-provider startup. Dynamic watching remains enabled. Following watcher recovery, an actual two-replica restart loaded the protected route successfully. The subsequent encrypted etcd/NAS restore explicitly verified the new dashboard Secret; retain the original API encryption keys.

Application legacy published ports are recorded in evidence/application-port-cutover.json. Their original Docker specifications are encrypted in authenticated operator/NAS rollback files. Source application Services remain defined at zero replicas, with their published ports transferred to native Services. Vault/Consul and Portainer/agents remain running. A TCP connection proves routing only; application APIs/content require their separate evidence. Legacy xTeve TCP 1901 has no observed backend listener; its 34400 web/tuner route works and LAN SSDP discovery passed on all three interfaces.

qBittorrent retains its original password hash and 203-entry queue. The correct native consumer credentials were recovered from retained download-client settings. Gluetun admits inbound Web UI traffic on 8112 while torrent egress uses the preserved ProtonVPN WireGuard tunnel. The monitor reads the negotiated forwarded-port claim and persists its notification bookkeeping on its own Longhorn PVC. The user authorized restoration of the original automatic Discord alerts: client status, VPN-port updates, new downloads and stuck metadata on; download-complete off. One earlier explicitly authorized migration test delivered from the production monitor pod through the native webhook. Live rollout/environment/storage verification is recorded in evidence/monitor-alerts-restoration.json; every event type is not artificially triggered. The webhook value remains only in native Secrets.

For rollback after a destination receives writes, first stop that destination writer and take a recoverable checkpoint. Compare/synchronize the destination changes into a reviewed recovery copy before restarting a retained source. Restoring old Docker port specifications alone does not restore new application writes. Keep source Gluster bricks, cold archives and partial migration claims until the acceptance ledger is complete and final retirement is confirmed by the user.

## Gated source retirement

The read-only evidence/retirement-readiness.json audit inventories the actual Gluster mount targets and remaining source containers. Six Docker containers remain across four services: cicd_vault, cicd_server-bootstrap, portainer_portainer and the three portainer_agent tasks. Portainer and Consul still mount original Gluster data. No active native Pod directly mounts the discovered Gluster paths and no native PV uses those Gluster paths/drivers. All three /gluster/volumes directories remain present. This is a consumer inventory, not approval or proof that every application scenario has passed.

```mermaid
flowchart TD
    Evidence["Finish data/application acceptance<br/>Redis cache exception accepted by user; complete remaining application checks"]
    Approval["User confirms final source retirement"]
    Checkpoint["Verify current native recovery checkpoints<br/>Keep original encrypted archives and keys"]
    Sources["Stop retained Vault, Consul, Portainer and agents<br/>Preserve their specifications and data"]
    Consumers["Recheck actual clients, Pods, PVs and open files<br/>Require no remaining source data consumers"]
    Unmount["Unmount Gluster clients normally<br/>Stop if busy; keep SMB/NFS media mounts"]
    Stop["Stop Gluster volume/services<br/>Retain all brick directories and archives"]
    Evidence --> Approval --> Checkpoint --> Sources --> Consumers --> Unmount --> Stop
```

Re-run the privileged consumer/open-file audit after stopping the approved source services; a prior inventory cannot authorize shutdown of a newly discovered consumer. Do not force or lazily unmount busy clients, delete bricks/claims/backups, or disable NAS media exports. The separate read-only /mnt/migration-gluster-read client on worker2 and /mnt/container-program-files clients on all three nodes must be considered alongside source containers. Root/container filesystem visibility alone does not establish active data consumption; inspect actual holders before shutdown. Restore the original Vault data with its original user-held unseal material if rollback requires that encrypted source store. The authoritative replacement secrets recover from the tested native etcd snapshot using the retained Kubernetes encryption keys.

## Operator tools and metadata

Run migration tooling from WSL with the existing SSH identity. `scripts/migration/install-tools.py` installs checksum-verified age, Flux, Helm and kubectl into `~/.local/share/branconet-migration/bin`, leaving other installations intact. It records upstream URLs/checksums in an operator-local download manifest.

`scripts/migration/inventory.py --output evidence/live-inventory.json` captures current service/container/image/mount/port metadata from all three hosts. It deliberately excludes environment values, raw labels, command arguments and credential files. The source-to-target register must include both Swarm services and standalone containers, including anonymous volumes.

Run register.py with the isolated Python environment to produce SERVICE_REGISTER.md and evidence/service-register.json from the saved baseline. It maps every live source instance to an application chart or an explicit replacement contract, and adds repository-only applications. Replacement entries for Vault/Consul and Portainer/agents remain pending until retained data and replacement behavior are verified; no source service is silently omitted.

That baseline register already exists. Do not rerun register.py or refresh-migration-state.py after production promotion: their preparation defaults replace accumulated acceptance/release state. Run update-acceptance-register.py to enrich the retained baseline with current HelmRelease/PVC metadata, native Secret references (names/keys only), per-service cold backups and scoped evidence. False or absent historical checks remain explicit; this tool never converts HTTP/TCP readiness into full functional acceptance.

pipeline-rollback-proof.py demonstrated a real HTTP echo annotation rollout and rollback through Git, successful validation, the validated branch and Flux. Evidence preserves each commit/CI run, new Pod UID, unchanged PVC/volume and unchanged response hash. It uses Windows Git for the shared Windows checkout to avoid WSL line-ending false positives. It refuses to repeat over an existing report; review and preserve previous evidence before any repeat. This small canary tests the deployment pipeline, not data rollback after application writes.

source-status.py records replicated/global source counts and standalone health without environment values. For Pi-hole startup diagnosis it retains only error/warning lines and excludes credential-bearing lines. Restart command success is not readiness evidence; investigate any source below its recorded desired count before accepting restoration.

Pi-hole currently has a temporary Swarm constraint node.hostname==workernode2 because its worker1 FUSE client cannot stat gravity.db even though all bricks retain the file. Preserve this existing database rather than initialize a replacement. Original service configuration remains in the encrypted baseline backup; remove the temporary constraint only after the relevant mount/readiness or Kubernetes cutover is verified.

check-source-dns.py sends ordinary UDP and TCP DNS queries through port 53 of each node, validates response ID/success/answers and records evidence. A healthy Pi-hole container alone does not prove all routing paths work. This checks source restoration; destination Kubernetes DNS requires separate pod-level checks after provisioning.

Raw runtime configuration and credentials belong only in encrypted recovery backups outside Git. Initial copies of active data are staging copies, not accepted consistent backups. Final database copies require application-consistent backup or stopped writers and verified restoration.

`scripts/migration/backup-config.py` receives its sudo credential through stdin, captures runtime/host configuration, encrypts it with the existing WSL SSH public key, and verifies recovery using the matching private key without displaying either key or configuration values. It stores encrypted copies in the operator's isolated recovery directory and `/mnt/container-backups/k8s-migration-20261009`, checks their ciphertext checksums, and writes a metadata-only evidence report. This proves configuration recoverability; application-data backups are a separate gate.

Repeat configuration capture after Kubernetes/storage provisioning. It includes /etc/kubernetes files (PKI, kubeconfigs, API encryption and LUKS recovery key), independent containerd configuration and its/kubelet systemd units. Do not use this configuration snapshot as an etcd database backup; control-plane database recovery needs a consistent etcd snapshot as a separate check.

Each migration application now has its own `Chart.yaml`, `values.yaml` and Helm template beneath the existing charts tree. `enabled: false` and zero replicas are preparation defaults. Activation requires `migration.verified`; packaging validation alone does not establish that storage, native Secrets, live configuration, or application tests are complete. Legacy raw manifests remain reference sources and must not be reconciled alongside Helm releases. Charts with an empty resources list explicitly require implementation; the CI validator rejects incomplete packages.

`chartify.py` prepares packages from sanitized live image metadata and existing manifests without enabling them. `validate-charts.py` checks Helm lint, staged rendering, integer replica types and the blocked activation path. Its `--allow-incomplete` switch is for local preparation evidence only; repository CI requires all manifests to be implemented. Kubernetes schema and functional verification remain separate acceptance checks.

`measure-storage.py` reads data path sizes and ownership through SSH/sudo supplied on stdin. Size errors remain explicit. PVC allocation must use completed measurements, replica count, free space and reserve; existing source PVC estimates are not accepted as measured capacities.

`complete-live-charts.py --refresh-live` constructs prepared live workload resources from the original sanitized source inventory, using measured data sizes for Longhorn claims and the same SMB directories. It retains legacy reference files, keeps workloads disabled, records source argument and Docker-host dependencies for review, and carries Homepage annotations forward. Run it only during preparation: it replaces prepared resource lists. It wires Gluetun as a restartable init sidecar in the qBittorrent pod; the separate Gluetun package owns its PVCs and live WireGuard runtime Secret reference. Startup/readiness use the upstream Gluetun healthcheck command. VPN egress, startup behavior, kill-switch isolation and forwarded ports still need live tests. BORTUS manifests remain a separately delivered dependency.

`import-secrets.py --kubeconfig <protected-operator-path>` prepares a metadata-only import inventory; adding `--execute` creates native Kubernetes Secrets and compares every value in memory with API readback. It reads Vault and age-encrypted original Docker configuration directly; no plaintext export is created. Existing unequal Secrets fail with a conflict. Vault records use the `bortus-secrets` namespace with original-path/type annotations; application runtime environments use their own namespaces. BORTUS provider mapping, dependency host rewrites, secret rotation and at-rest ciphertext verification require separate live checks before acceptance.

The Ansible runner writes progress into its protected operator log while it runs, so a provisioning failure can be diagnosed without waiting for the whole stage. Credentials arrive through the runner's stdin, then are passed to the Ansible child through an in-memory process environment lookup; no password is in argv or a plaintext file. This avoids Ansible 2.21 resolving /dev/stdin to a nonexistent pipe filename. Each site play explicitly loads ../group_vars/all.yml because the playbook lives below the inventory/group-vars parent directory.

`redis-audit.py` queries only Redis persistence/key-count metadata and WordPress cache-plugin/configuration presence. It does not export keys or values and does not establish historical recovery. Redis source task state had no data mount; its unrecovered historical cache was explicitly accepted as disposable by the user on 2026-10-09, retain new snapshots before further task shutdowns, and provision durable target storage if persistence is required.

`fix-worker-dns.py` records worker2's prior per-link DNS and sets its runtime systemd-resolved DNS to the already verified homelab resolver 192.168.0.6. It changes neither persistent network files nor Pi-hole listening policy. The original runtime resolver must be reconsidered during final DNS cutover and rollback; its exact prior value is in evidence/worker-dns-override.json.

`build-bortus-image.py` builds the separately delivered app commit 1438b278cdf21e98429b4836c018636b01b982a3 using source Docker on the master. Its streamed context excludes local environment files, databases, node_modules, tests and build output; it pins kubectl to the cluster version. Building an image does not run or deploy BORTUS and is not live native Secret acceptance. Protected build logs and metadata record actual build results.

For the new release, `prepare-bortus-release-context.py --source-repo <checkout> --source-commit <full-40-character-commit> --output <new-outside-checkout.tar.gz> --evidence <new-outside-checkout.json>` prepares source only. Both output parents must already exist. It reads raw committed application blobs, never the working tree, and checks each Git object identity. The deterministic archive preserves regular-file executable modes and records the exact commit, application tree, per-file hashes, migration files and archive hash. It excludes environment files, databases/sidecars, dependency/build/test directories, logs and named credential/key files without reading their payloads. Included symlinks/submodules, invalid paths, missing required build inputs and existing output paths are refused. Bounds are 2,000 tree entries, 16 MiB per included file and 128 MiB of included source, with 30-second Git command deadlines; subprocess output-size checks occur after capture and are not process-memory limits.

The helper exclusively creates and flushes its files, retains partial output after failure, and never builds an image, installs dependencies or accesses the cluster. POSIX mode 0600 does not establish a Windows ACL, so use the protected operator artifact location appropriate to the host. Exclusions are not a complete credential scan: qualify the actual selected source/context separately before build. Qualification of a current preparation commit is not final source freeze, image qualification, schema/adoption acceptance or deployment. The historical fixed-source image builder/distributor must not be reused for the new release.

[Local qualification](../evidence/bortus-release-context-qualification-20261011.json) records 13 actual POSIX fixture passes, 12 Windows passes with one explicit POSIX-only skip, successful current-checkpoint preparation and independent verification of all 263 archive files. The default pinned Gitleaks scan passes with zero findings on those selected raw files. It does not resolve the prior whole-repository scan's two historical provenance fields or qualify final source/image/live acceptance.

The separately delivered [terminal UI checkpoint](../evidence/bortus-terminal-handoff-qualification-20261011.json) at `4bea97aa` passes fresh build/lint/types and 11 local browser checks, with exact source/artifact/measurement verification by the coordinator. Viewport docking, keyboard escape, Clear, deferred-load failure feedback and private lifecycle disposal are tested against the fixture; no command is submitted. First-frame observations are 850.3/585.5 ms cold/warm, not a no-regression gate. Actual assistive-technology testing, wider zoom/readability, full coherent QA, the unchanged final frozen performance comparison and image/live acceptance remain separate requirements.

The callable `bortus-restore-watch.py` [collector contract](BORTUS-RESTORE-WATCH.md) supplies verified TLS, complete bounded LIST to exact opaque-RV watch, a concurrent bounded metadata drainer and pinned/fsynced sidecar readiness before journaled create callbacks. Its `WatchJournal` subclass serializes sidecar/journal ownership checks while callbacks remain drainable. Confirmed target PVC/PV/Longhorn identity binds early events; exact observed GET RV and true/true to true/false flags permit metadata eligibility only. Lost replies, history gaps, EOF, malformed/oversized inputs, identity drift and durability failure refuse without reconnect, relist, adoption or mutation replay. The 2,100-second lease has a separate 30-second socket timeout. Importing the library makes no requests. Its actual local TLS/POSIX fixture qualification is separate from a reviewed operator credential adapter, complete live executor, image/admission/source/consumer fences, healthy replicas and independently authenticated data equality. See the linked contract for bounds and non-atomic callback/watch limits.

[Integration qualification](../evidence/bortus-restore-watch-integration-qualification-20261011.json) binds native `b0e37521`, exact selected raw/checkout byte relations, retained initial failures and all 162 passing current root BORTUS helper cases. The native scoped 11-file default scan has zero findings. No live watch, approved credential adapter, restored-data equality, final image or production mutation is claimed by this local qualification.

`network-proof.py` runs two bounded test pods on separate workers, checks Kubernetes service DNS in each pod, and pings each peer pod across nodes. It records actual image IDs and node/runtime versions; test pods remain for diagnostic work and are not production workloads.

After post-provision configuration recovery passes, `operator-kubeconfig.py` recovers admin.conf directly from the authenticated encrypted backup to the operator runtime directory with mode 0600 and verifies the API. It never writes the credential to Git or reports it. Configuration backup metadata keeps prior snapshots instead of replacing their historical references.

Native import also creates fresh stable BORTUS signing and lookup keys in bortus/bortus-runtime; repeated execution reads that existing object rather than generating a replacement. The importer creates an explicit metadata-only bortus-secret-aliases ConfigMap: Vault path aliases for single-key records, path/key aliases for each field, and fully explicit native runtime references. Values are absent from its saved alias map. Live BORTUS read/CRUD/lookup and etcd ciphertext checks remain acceptance gates.

`distribute-bortus-image.py` streams the clean, separately delivered image into each independent Kubernetes runtime and verifies actual cached manifest digests. Successful import stdout is not tag evidence; existing verified images skip retransmission. The current staging chart uses that exact cached tag with imagePullPolicy Never until an authenticated image publication pipeline is selected.

The deployed image export is also preserved independently of the development worktree: evidence/bortus-image-recovery.json records its protected operator/NAS age archives, ciphertext checksum, full authenticated decryption and image-configuration digest. To recover, authenticate/decrypt that archive into the protected operator path recorded by evidence/bortus-image-distribution.json, with mode 0600, and verify its recorded archive SHA before importing. Then supply sudo through protected stdin to distribute-bortus-image.py, which requires the recorded export SHA and identical runtime manifest digest on all three nodes. No app rebuild or separate worktree is required for this restore path. The original build helper is historical delivery tooling with a fixed development-worktree path; do not use it as the disaster-recovery entry point. BORTUS remains on the same image and its Secrets/database recover through their separately tested backups. This proves exact image-artifact recovery, not a full three-host rebuild.


### Current immutable app release preparation

The [final app handoff](../evidence/bortus-terminal-final-handoff-20261011.json) at `32eb227e` supersedes the earlier terminal readability/zoom checkpoint. Current Windows QA passes 196 units, build/lint/types, all four HTTP suites, 11 terminal browser checks and four genuine 2x zoom checks; exact raw-source, original artifacts and separate tested working bytes are bound. Earlier HTTP/capture failures remain retained. Root independently reviewed the public screenshots and recomputed the local measurements. This is functional/browser evidence, not the unchanged controlled performance gate or actual screen-reader testing.

The [raw-Git build context](../evidence/bortus-final-release-context-20261011.json) is prepared for that exact commit: 263 included files and 11 forward migrations, with all tar paths/modes/blob/hash bindings verified. The default source-only credential scan passes zero findings. The unchanged controlled comparison completed but fails performance acceptance; `32eb227e` remains a retained candidate. The app subagent reports passing clean Linux functional tests, with independent coordinator evidence qualification pending. The actual immutable image/runtime digest and every guarded live release/data/recovery gate remain open. Do not invoke the historical fixed-image builder for this new release.

The selected [generic release builder](BORTUS-RELEASE-IMAGE.md) consumes exact commit/archive/manifest hashes and checks every included raw blob and mode before SSH. It uses the existing fixed builder, the approved cluster-compatible kubectl build argument, exclusive protected intent/logs and no automatic replay. Root retains actual build ownership; no build is dispatched while final source/performance qualification remains open. Config image IDs, OCI manifest digests and qualified runtime identities are recorded separately.

Root's [selected integration](../evidence/bortus-release-builder-integration-20261011.json) verifies the native handoff and passes all 218 current WSL helper tests. Its validation of the real retained 263-file candidate archive performs no network or image operation. The [unchanged paired performance receipt](../evidence/bortus-paired-performance-32eb-20261011.json) independently checks six alternating records and 4,122 numeric summaries and keeps performance acceptance false. Preserve those originals and the noncomparative services-cache limitation when comparing the replacement candidate.

The [fresh source preflight](../evidence/bortus-source-preflight-20261011T064554Z.json) is metadata-only: all 53 PVs are inventoried and the original Longhorn handle has one PV mapping. It preserves original identities and verifies current prerequisites without Secret/SQLite reads or mutations. These separate resource reads are not atomic and do not replace the cold capture and independent restore gates.

### Approved embedded operator transport

The replacement [unchanged `3f9b21cd` comparison](../evidence/bortus-paired-performance-3f9-20261011.json) also completed its six records and assertions but fails performance acceptance. Root independently verifies the originals and all summary arithmetic. The app subagent's next request-correlated characterization uses only synthetic data and separately owned instrumentation; it does not alter the frozen driver, source image or acceptance thresholds. Image build/cutover waits for the full source and performance requirements.

The [restore schema/status correction](../evidence/bortus-restore-schema-status-correction-20261011.json) supersedes the original synthetic collector fixtures: installed Longhorn 1.12.1 uses exact `spec.Standby` and `status.isStandby`. The corrected pure evaluator and ABI 2 collector require the canonical false spec flag and preserve observed status validity through durable projection, so faulted/deleting/standby or unsupported states cannot disappear before target/holder authorization. All 223 current root helper tests pass, including owned HTTPS post-completion failure cases. The scoped live metadata/schema inspection does not create a restore or prove independent data equality; image/admission/consumer/executor gates remain open.

The [operator adapter](BORTUS-OPERATOR-MTLS.md) reads the explicitly approved protected operator kubeconfig afresh; only embedded mTLS for the fixed API origin is supported. Native keys remain transient in sealed Linux memfds, never plaintext exports or argv. Root's integrated kubeadm context correction passes all 193 current helper cases and the scoped live complete Longhorn LIST/watch HTTP handshake, with no frames consumed or mutation. Use the [integration evidence](../evidence/bortus-operator-mtls-integration-20261011.json) for exact source, terminal and retained failure bindings. This transport proof cannot authorize restore mutations or replace durable live watch history, fresh source/consumer/image/admission fences and independent whole-row equality.

`deploy-bortus-staging.py` requires three matching cached images, native import readback and Longhorn device/relocation/restore proof, then performs an API server dry run and installs a private one-replica Helm release. The BORTUS-only staging gate allows functional testing before full acceptance and rejects Ingress/IngressRoute or external Service resources. It does not mark migration.verified or applicationChecksPassed true. Public routing requires separate completed acceptance.

`bortus-live-proof.py` reaches staging through a loopback port forward, bootstraps the james operator account with fresh credentials retained only at bortus/bortus-operator-access, and locks registration after creating a readonly acceptance account. It compares every imported Vault lookup alias in memory; checks native CRUD, version conflicts and preservation of unrelated keys/metadata; then restarts the app and proves Secret, session and runtime-key persistence. Tests use dedicated acceptance objects and never rewrite imported production values. Account credentials and HTTP bodies are not reported. Dashboard and live-outage acceptance remain separate.

`backup-etcd.py` takes a consistent snapshot with etcdctl, encrypts it directly into protected operator/NAS recovery files, authenticates decryption, and restores it with etcdutl into an isolated test pod. The pod has no service-account token and denies network ingress/egress; its restored etcd listens on loopback only. Actual restored Secret ciphertext is compared in memory, including every imported encrypted Secret. This follows the official [etcd recovery procedure](https://etcd.io/docs/v3.7/op-guide/recovery/). It never restores over production etcd. Native API encryption keys must also remain recoverable from encrypted configuration backups. Repeat snapshot recovery after later native Secret changes before final retirement.

`verify-secret-encryption.py` reads each imported registry record through etcdctl inside the control-plane etcd pod and verifies the configured AES-CBC prefix in memory. It exports neither ciphertext nor plaintext. API readback comparison and encryption verification address different acceptance requirements.

The Longhorn role installs external-snapshotter v8.6.0 CRDs/controller for CSI snapshot recovery. `storage-proof.py` creates only dedicated migration-system test claims: it checks two replicas on different nodes and the actual LUKS block-device header, writes a marker, snapshots it, writes a newer marker, relocates the source claim to the other worker and restores the older snapshot into a separate claim. Existing source/application volumes are untouched. Test claims/pods/snapshot are retained; inspect them before rerunning. This proves storage primitives, not migrated application or off-cluster backup recovery.

`review-live-integration.py` recovers effective source commands/arguments only from authenticated encrypted configuration and stores them in native launch Secrets. Chart commands expand references through environment variables; argument values never enter YAML. It pins live source digests and rewrites recognized same-namespace service hostnames in native runtime Secrets. Unresolved host/IP dependencies remain metadata-only audit entries for explicit application integration. Rerunning preserves stable native launch values and removes duplicate generated references; do not use it to overwrite later independently edited runtime values.

`copy-application-data.py --chart <relative-chart>` first creates owned private zero-replica resources, then stops that source writer and confirms it is absent. Each temporary root copy pod mounts its host source read-only and a new Longhorn claim writable. It refuses a nonempty destination, copies with numeric owners/ACLs/xattrs, and compares complete file-content and metadata manifests before/after. A source or target mismatch is a failed copy; original and partial destination remain retained and the source writer is restarted. Success leaves the source stopped for destination validation/cutover and records its prior count. No application acceptance is implied by copying. Restore source traffic only through the service's rollback procedure, avoiding conflicting writers after target changes.

`prepare-flux-releases.py` creates the original validated-branch source and all in-scope individual release declarations (currently 33). It retains data resources and namespaces, starts only private BORTUS, and leaves every other application disabled. This is historical preparation tooling: rerunning resets per-release overrides and must not be used after application promotion without inspecting existing values. Validation checks blocked unaccepted activation, private renders without external routes, all chart implementations and manifest types. The original GitHub publisher was used during migration and is now removed. This branch retains read-only archive validation; current delivery uses only the separate chart repository's main Ã¢â€ â€™ successful current-main CI Ã¢â€ â€™ validated pipeline. Actual remote CI/Flux readiness is recorded separately in the acceptance evidence.

`scripts/migration/backup-data.py` records source replica counts and standalone containers, stops application writers for a cold-backup window, and streams encrypted archives to the NAS. It preserves Gluster logical data, NFS application data, all three local Plex directories, ETS2 configuration and anonymous Docker volumes. Its `finally` path restores the recorded Swarm replicas and starts Gluetun before qBittorrent. Sources and Gluster bricks are retained. After restarting sources it validates full authenticated decryption and tar traversal, with metadata-only evidence. An archive/decryption failure is not accepted as a completed backup; investigate and preserve the original data.

`scripts/migration/gluster-audit.py` captures privileged heal summary, split-brain/path diagnostics and logical-versus-brick path metadata without modifying the volume. A source read error is a failed data gate, even if some archives were written successfully. Preserve partial archives and original bricks; identify affected paths and obtain verified recoverable copies before provisioning or cutover.

For the observed read failures, backup-data.py accepts recover_gluster_read_errors through its protected stdin request. It retains valid original worker archives, archives all three raw bricks with ACLs/xattrs, rearchives master local/NFS state, and archives logical Gluster from the worker2 client that can read the Jackett paths. Only the obsolete Gluster Plex Logs directory is excluded from that logical archive; all its brick copies remain in the three recovery archives. Raw bricks are recovery evidence and retained originals, never the source for ordinary application imports. Baseline anonymous volume paths are included even after Swarm has replaced task containers. Every accepted archive still requires authenticated full decryption/tar validation, and provisioning additionally requires complete recovery coverage.

Missing baseline paths fail the backup gate. Swarm task replacement can remove task-owned anonymous volumes, so inspect and capture these before any subsequent task removal; the privileged audit records baseline path existence. Do not report complete data preservation when a source path is missing or unexplained. Per-archive failures are recorded while other jobs finish, preserving valid recovery artifacts and restoring source counts in finally.

The user explicitly classified FlareSolverr /config and Vault /vault/file and /vault/logs as disposable runtime state. With disposable_runtime_state_confirmed in its stdin request, backup-data.py records those exact service/mount exclusions and continues the required dataset backups. Any other baseline anonymous application path blocks writer shutdown until it has separate preservation; no broad anonymous-volume exclusion is allowed. The original sequencing error and user clarification stay in the evidence history.

verify-archives.py authenticates the valid retained worker cold archives and worker2 brick/logical archives independently of failed jobs. Its report explicitly marks complete_backup_set=false: authenticating individual files cannot satisfy missing dataset or all-brick coverage. This read-only recovery check does not stop any source services.

vault-status.py accepts the authorized unseal key/root token through stdin, unseals only when needed after a source restart, checks active HTTP health and records KV path/key/type/version metadata. It never writes secret values, tokens or unseal material. Compare its restored record/value counts and keys with the original inventory; metadata equality is not a substitute for the later in-memory value/import verification.

The health check allows a bounded 15-second leader-election interval after unsealing. If Vault stays sealed/standby/unhealthy, its source restoration is not accepted.

## Runtime coexistence

Provision a separate Kubernetes containerd service, socket and data root. Do not overwrite Docker's existing configuration or restart its runtime during Kubernetes preparation. Preserve resolver settings and verify Docker/Swarm networking after CNI changes. Keep Gluster bricks/mounts and NAS shares intact until final acceptance and user confirmation.

The revised `site.yml` uses `containerd-k8s.service` with /etc/containerd-k8s/config.toml, /run/containerd-k8s/containerd.sock and /var/lib/containerd-k8s. Bootstrap settings are versioned nonsecret configuration and do not call BORTUS. The kubeadm API uses /etc/kubernetes/encryption-config.json for native Secrets; Longhorn uses the native longhorn-crypto Secret and retained LUKS volumes. Include encryption keys and Kubernetes recovery configuration in a new encrypted recovery backup before application PVC imports.

`scripts/migration/run-ansible.py` requires completed authenticated data archives covering all three hosts, complete brick/logical/primary coverage for the recovery strategy, and successful source restart commands before provisioning. It receives sudo through stdin and supplies the Ansible child through a private in-memory environment lookup, uses explicit ANSIBLE_CONFIG under WSL and records stage exit status plus a protected operator-log path. Run foundation tags first; verify actual nodes/network/DNS and existing Docker services before subsequent storage/ingress/Flux stages. All expected node and controller readiness checks fail closed.

## Pipeline ownership

Ansible provisions hosts and the Kubernetes foundation; Flux reconciles application charts and their values. BORTUS manages native Secret values through Kubernetes. No raw secret values go into Git, process arguments or reports. Live acceptance must prove node readiness, pipeline reconciliation, storage persistence/recovery and application behavior; rendered manifests alone do not establish completion.

### Application waves and private reconciliation

Run application-wave.py only for the reviewed independent source services listed in that script. Each cold copy requires authenticated backups, stops its source writer, compares full manifests, retains originals and leaves the destination stopped. private-app-proof.py starts one private replica and checks HTTP and restart; --relocate also proves the same claim on another worker. An HTTP check alone does not establish all application functionality or public cutover.

refresh-migration-state.py retains baseline source inventory, records copy/private evidence, makes tested releases private replicas and suspends every untested release. Commit and wait for successful CI publication before Flux adopts this desired state. Temporary DNS changes and BORTUS dashboard/outage results are recorded separately.

### Native certificate and database recovery

import-ingress-certificates.py reads the retained source ACME store through the independent read-only Gluster client and imports certificates/keys directly into native TLS Secrets. Only public domains, expiry and certificate fingerprints are reported. The pinned cert-manager OCI chart is reconciled by the same Flux pipeline; HTTP01 issuance requires final port-80 routing. Native imported keys and new issuer keys require a fresh encrypted etcd backup.

database-proof.py uses the retained application account, because both original MySQL databases generated their root passwords. It verifies schema/table counts across restart after the exact cold copy. import-redis-snapshot.py restores the protected current snapshot into a retained claim; it does not recover the original task state removed before archival.

Homepage now uses its service account and native configuration Secret for cluster discovery. Original source configuration remains retained. Relevant upstream configuration: https://gethomepage.dev/configs/kubernetes/ and https://gethomepage.dev/installation/k8s/.

Ingress validation: website-ingress-proof.py checks certificate name/chain and the previously verified content hash on all three temporary HTTPS NodePorts. Traefik 2.11 needs router.tls=true and websecure entrypoint annotations; loading a TLS Secret alone does not enable its HTTPS router. Standard ports remain a separate cutover gate. Plex library proof checks retained machine identity, authenticated library totals and a real one-MiB media range through the migrated server. It leaves full client playback and relocation acceptance separate.

Unpackerr fixture acceptance uses an isolated Pod with the exact deployed digest and only an owned subdirectory of the existing SMB CSI claim. The archive is created after the watcher starts, so polling sees a new directory event; output SHA equality and archive retention are required. Production configuration is unchanged and the fixture is retained. Its real Arr API access is a separate check; this does not claim a completed real download/import. Configuration reference: https://unpackerr.zip/docs/install/configuration/.

media-import-prerequisites.py reads the configured Arr APIs in memory and records only root-folder accessibility, enabled client implementations, queue counts and health-warning types. Sonarr's /media/tv and Radarr's /media/movies are accessible and report free space; both use enabled qBittorrent clients. UpdateCheck and Radarr IndexerLongTermStatusCheck warnings remain recorded for review. The tool never changes library/configuration data or establishes a completed download/import.

xTeve's immutable 2.2 image selects the last available IPv4 address and offers no interface override. Host networking alone returned a Docker bridge address in SSDP replies. Its chart therefore keeps the xTeve process on pod networking and adds a separate host-networked discovery responder using a pinned Python utility image, ClusterFirstWithHostNet DNS and UDP 1900. The responder reads the live UDN from the existing LAN descriptor at http://192.168.0.4:34400/device.xml and advertises that exact endpoint; it mounts only its nonsecret code ConfigMap, requires no Kubernetes RBAC and changes no application settings/data. Replies are restricted to the configured LAN. The immutable xTeve image, device identity, Longhorn claims and SMB IPTV claim stay the same. Interface-selection source: https://github.com/xteve-project/xTeVe/blob/master/src/toolchain.go.

Active host networking requires both migration.routingReviewed and migration.hostNetworkingReviewed. Before setting the latter in the Flux release, check 1900/UDP on every eligible host and retain the existing 34400/TCP service ownership. The chart rejects an active deployment missing either review. The responder checks its own UDP reply against the native descriptor for readiness, withdraws advertisements when the backend becomes unavailable, and sends goodbye on termination.

Run scripts/migration/xteve-ssdp-proof.py --phase after to verify real multicast replies from all three LAN interfaces and compare device identity, tuner count and claim identities against the retained baseline. HTTP discovery/lineup checks alone do not prove multicast discovery. For a network-only rollback, remove the responder Deployment/ConfigMap from the chart through the same CI/Flux pipeline, retaining the xTeve pod networking, current claims and destination data; do not restart an outdated source instance.

```mermaid
flowchart LR
    Client["LAN tuner client"] -->|"M-SEARCH / UDP 1900"| Gateway["Stateless SSDP responder<br/>one eligible Kubernetes node"]
    Gateway -->|"Read native UDN"| Service["Existing LAN endpoint<br/>192.168.0.4:34400"]
    Gateway -->|"Reply with existing descriptor URL"| Client
    Client -->|"HTTP tuner requests"| Service
    Service --> Xteve["Original xTeve image<br/>pod networking"]
    Xteve --> Config["Same Longhorn configuration claims"]
    Xteve --> IPTV["Same SMB IPTV claim"]
```

The first probe incorrectly used local unicast; the corrected probe queries the native UDN through multicast and passed against the live responder. CI validated revision 519a418 before the exact nonsecret code was applied to the existing ConfigMap to release an in-flight Helm health wait. Its API readback matched byte-for-byte, and Flux then converged the full release. The helper's new pod disables its API token; no data volume is mounted. Recovery details are in evidence/xteve-gateway-readiness-recovery.json, and actual before/after protocol, image, claim and recreation evidence is in evidence/xteve-ssdp-proof.json.

Actual public-DNS HTTPS probes passed with normal browser headers. Default Python headers returned Cloudflare 1010; no Cloudflare settings were changed. This status is documented at https://developers.cloudflare.com/support/troubleshooting/http-status-codes/cloudflare-1xxx-errors/error-1010/. Run add-native-dns-records.py after recovering Pi-hole to append the recorded native repository/management names without replacing existing records.

## Retained standalone startup audit

[evidence/standalone-autostart-proof.json](../evidence/standalone-autostart-proof.json) records the six stopped source containers and scoped startup-file inspection on all three hosts. No policies were changed. Docker no/default-no and unless-stopped policies keep these stopped containers from daemon-restart autostart; see [Docker restart policies](https://docs.docker.com/engine/containers/start-containers-automatically/). The inspected cron files have no active Docker jobs; no standalone-name or Docker/Compose start matches were found in the checked startup files. This does not replace an actual reboot test or exclude arbitrary external start commands.

Repeat scripts/migration/standalone-autostart-proof.py from the repository root using the WSL migration Python runtime; supply the sudo password through stdin in memory, never in argv, Git or a credential file. The script writes only container/policy identifiers, startup-file paths/hashes/classifications and unit names. It performs no source changes and prints no environment values or startup commands.

## Owned download/import acceptance

The actual publisher-webseed qBittorrent Ã¢â€ â€™ Radarr completed-download handler test passed. [The proof](../evidence/media-download-import-proof.json) records exact torrent/movie identity, import history, three-way file SHA/size equality and cleanup restoring original queue/library fingerprints. The film is [licensed CC BY 3.0 by its publisher](https://peach.blender.org/about/); [WebTorrent publishes the test torrent](https://github.com/webtorrent/webtorrent/blob/master/docs/free-torrents.md). The webseed required eight scoped re-add retries with partial data retained; [selected byte-range checks](../evidence/media-fixture-webseed-proof.json) do not establish the cause of the bans or full external peer connectivity. This Radarr test did not exercise indexer search, Sonarr or Unpackerr; the subsequent Sonarr chain is recorded below.

```mermaid
flowchart LR
    Publisher["Licensed publisher webseed"] --> VPN["Existing ProtonVPN / qBittorrent pod"]
    VPN --> Download["Owned download directory on existing SMB"]
    Download --> Handler["Existing Radarr completed-download handler"]
    Handler --> Library["Owned library directory on the same SMB share"]
    Library --> Proof["Three-way SHA + size; exact import/torrent ID"]
    Proof --> Cleanup["Remove only fixture; verify original queue/library fingerprints"]
```

The live fixture was cleaned up. scripts/migration/media-download-import-proof.py reads protected runtime metadata and native credentials in memory; after cleanup it retains the recorded evidence and explicitly performs no new import check. scripts/migration/media-fixture-cleanup.py requires successful import/hash evidence and checks exact movie/torrent identity, the original CIFS mount, contained unique directory paths, creation times and absence of symlinks. It does not request application-level media deletion or create an import exclusion. The actual run removed only the owned files. Unused test category/tag metadata was retained because pre-test ownership was not recorded; no global settings were reset. A new fixture needs fresh identity/preexistence checks and explicit per-torrent save and incomplete paths at creation.


At 23:47:08 UTC, production Sonarr automatically imported the licensed Blender Shorts S01E02 fixture after the existing qBittorrent client downloaded its archive and production Unpackerr extracted it. History matches the exact torrent ID. The 64,657,027-byte episode matches the publisher SHA in the download, imported Sonarr file and original host SMB mount. Cleanup at 23:48:29 removed only the owned series, torrent and two test directories; all 153 original series, 5,298 original episode-file metadata records and 203 original torrent IDs retain their baseline fingerprints. The temporary loopback seed was stopped and removed. This proves the actual archive/extraction/automatic-episode-import path, using a private loopback seed; external peers and indexer searches are outside this test. The folder fixture required eight scoped seed retries. The initial single-ZIP layout blocked import and is retained in evidence/sonarr-single-archive-stage.json; only fixture layout/display name changed. Unpackerr refused to overwrite the fixtureÃ¢â‚¬â„¢s duplicate attribution text while successfully extracting the unchanged episode. Evidence: evidence/sonarr-archive-import-proof.json.

```mermaid
flowchart LR
    Seed["Private loopback seed<br/>Licensed public episode archive"] --> Qbit["Existing qBittorrent client<br/>Owned folder torrent"]
    Qbit --> Unpackerr["Production Unpackerr<br/>Configured delay and extraction"]
    Unpackerr --> Sonarr["Production Sonarr<br/>Automatic import / matching torrent ID"]
    Sonarr --> Verify["Publisher / download / library / SMB<br/>SHA and size equality"]
    Verify --> Cleanup["Guarded owned-fixture cleanup<br/>153 series / 5298 files / 203 IDs unchanged"]
```

Run sonarr-archive-import-proof.py through WSL to inspect an active owned fixture. After successful chain proof, sonarr-fixture-cleanup.py removes only its guarded records/directories and verifies the original metadata fingerprints. sonarr-seed-cleanup.py verifies the temporary process command, owner marker and loopback socket before stopping it. The retained cleanup marker prevents an old proof rerun from overwriting the recorded result or pretending to perform a fresh import. A new acceptance run requires a new isolated fixture and baseline; do not reuse production releases or source datasets.

## BORTUS operator access

Open https://bortus.branconet.lan/auth/login and use username `james`. The bootstrapped password is held only in native Secret `bortus/bortus-operator-access`, key `password`. Retrieve it in the operator WSL terminal using the protected kubeconfig; no secret value belongs in Git or this report. Authenticated login, dashboard, Secrets page and live nodes/pods/volumes passed via LAN HTTPS in evidence/bortus-operator-bootstrap.json. The current LAN certificate is locally untrusted. Registration remains locked.

ETS2 and the Minecraft exporter are excluded by user direction. Their charts and Flux releases are removed; retained games-namespace claims, native Secrets, original sources and backups remain recoverable. The Minecraft website is retained.

Operator WSL password retrieval (run locally; output is a credential):

```bash
~/.local/share/branconet-migration/bin/kubectl --kubeconfig ~/.local/share/branconet-migration/admin.conf -n bortus get secret bortus-operator-access -o jsonpath='{.data.password}' | base64 -d
```

The read-only `scripts/migration/retirement-readiness.py` refreshes source containers, Gluster mounts/volume metadata, host fuser holders and native Pod/PV dependencies. Supply the existing sudo password in a JSON object on protected stdin. It never stops services, unmounts paths, deletes data or grants retirement approval. The current audit shows the three-brick replicated source volume still Started and Consul holding source files. After retirement approval, repeat the consumer audit after stopping the retained source services and inspect any mount-namespace holders before normal unmounts.

A fresh encrypted etcd recovery checkpoint after game removal restored all 339 current Secret records and verified the 73 original imports and dashboard Secret. Operator/NAS ciphertext checks matched; production etcd was untouched. Exact paths and hashes are in evidence/etcd-recovery.json. Older snapshots remain retained.

## Final BORTUS KV release gates

The normalization and complete-row comparison libraries accept a caller's absolute
`time.monotonic()` deadline through the keyword `deadline`. It must be finite,
unexpired and at most 300 seconds away. Pass the same deadline to both normalizations
and the recovery comparison; a later step cannot renew the remaining whole-operation
budget. Normalization also retains its `seconds` cap (default 60, maximum 300),
using the earlier limit. Comparison defaults to 300 seconds for standalone callers.
Fingerprint blocks, row iteration, multiset counts and SQLite VM progress check
the budget; failures never publish successful comparison metadata. These are
cooperative checks, not a guarantee against an operating-system I/O stall.
The public comparison library, as well as its CLI, returns only fixed failure
codes for SQLite and filesystem errors; backend exception text is never reported.
Archive encryption pins the owned mode700 output directory (or duplicates a
caller-supplied `directory_fd`) and exclusively creates a mode600 regular file.
Authentication reads ciphertext through stdin from that same retained file
descriptor; hashing rewinds that descriptor. Before and after those reads it
rechecks pathname-to-inode binding, owner, mode, link count, size and timestamps.
Substitution or modification refuses acceptance and preserves encrypted partials.
The file and directory entry are flushed before an accepted archive report.
The original cold-capture wrapper passes its already pinned checkpoint journal
directory descriptor; independent recovery must pass its own owned run descriptor.
Local regressions exercise valid ciphertext replacement both before decryption
and after authentication, same-inode modification after authentication, rejected
directory ownership and cleanup of the exact source/age child handles. These
disposable fixture cases do not prove live checkpoint or restore acceptance.
Normalization pins its newly created mode700 tmpfs directory identity before
fallible initialization, so an initialization failure can clean only that owned
partial directory. Full recovery still requires actual execution of the locally qualified coordinator and
independent live data proof; local helper qualification cannot replace either.

The [integrated local qualification](../evidence/bortus-restored-consumer-integration-20261011.json)
records 271 BORTUS helper, 13 complete-row comparison, 11 normalization and eight
encrypted archive cases passing with unchanged inputs and no skips. It includes
actual age/SQLite/tmpfs public fixtures and local TLS tests. Node, Docker, SSH,
operator credential reads and production mutations were not executed.

The selected pure [restored-consumer fence](BORTUS-RESTORED-CONSUMER-FENCE.md) supplies the current distinct PVC/PV/Longhorn mapping, complete physical-PV alias inventory, exact owned Engine/two running RW Replicas and sole inert read-only holder checks. The executor must supply fresh complete authenticated metadata, independently trusted source/target/image identities and the durable completion observation. Recheck before and after streaming; compare each selected name/UID/namespace across observations, allowing opaque RVs to advance. Its return grants metadata eligibility only. It does not perform the restore, prove the image/admission/runtime or authenticate and compare data.

Immutable image delivery uses the [qualified builder](BORTUS-RELEASE-IMAGE.md) followed by the separate [export/preload coordinator](BORTUS-RELEASE-STAGING.md). Supply exact independently verified completed receipt hashes, full source commit and config ID; hold exclusive builder/tag/import ownership. Export checks the source before/after Docker save, and sequential imports verify actual manifest/config/layer identity on each fixed node. Config ID and OCI/runtime digest remain distinct. Durable local/remote pending intents precede dispatch; an existing stage/tag, lost reply or failed validation stops further work without replay or automatic cleanup. After inspecting a retained failed preload and confirming its outcome, the migration owner may explicitly start a new unique preload attempt; both journals/stages remain separate, same-attempt replay and existing release tags still refuse. Remote sudo authorization and commands share a session, with cancellation restricted to the owned PID. The source tools and disposable fixtures are preparation only. Actual image scanning, three preloads, compatible inert holder/runtime acceptance and guarded release remain required.

The 2026-10-11 01:11:50 UTC [read-only refresh](../evidence/bortus-release-preflight-20261011T011150Z.json) confirms that production still uses `bortus:migration-1438b27`, the legacy `bortus` ServiceAccount and the original `bortus-data` claim. All three nodes and 34 HelmReleases are Ready; native admission policies and bindings are absent. This is the accepted migration runtime, not the new KV engine. Application development continues under two scoped sub-agents, with final release operations owned by the migration coordinator.

The separate chart repository's prepared [guard contract](https://github.com/jtmb/branconet-charts/blob/a82a6cb9e244b0ec05489bc7251f3e29411c64dc/docs/BORTUS-ADMISSION-GUARD.md) is outside Flux composition and has an empty approved-image list. It cannot be installed as a finished release. Review its final diff against the qualified application source before publication. Use the existing main Ã¢â€ â€™ successful current-main CI Ã¢â€ â€™ validated Ã¢â€ â€™ `branconet-charts` Ã¢â€ â€™ `migration-releases` owner for every chart change.

The current application entrypoint runs `prisma migrate deploy` before starting the server, independently of guarded adoption. Therefore the initial qualified-image rollout with adoption disabled already applies forward SQLite migrations; take the fresh consistent recovery checkpoint first and compare the resulting database before enabling adoption. Native KV ownership adoption is the later operation. The clean chart-release worktree's documentation commits `7a8f4b0` and `c6d87fe` correct the prepared sequence and forbid restoring the pre-KV source composition, which could regrant revoked legacy RBAC independently of image admission. Those commits are local preparation, not publication or live rollout. A false adoption flag does not defer schema migration or make a pre-KV recovery image compatible with the new schema.

Local [chart qualification](../evidence/bortus-chart-release-qualification-20261011.json) at exact commit `c6d87fe2bf311c5a00d57774c7b9a395d59e99da` passed the existing 17 guard regressions and the full checksum-verified validator: credential scan, 33 chart packages, 34 HelmReleases and 64-resource composition. The tracked checkout stayed clean. The copied raw report is hash-bound in the evidence. This does not validate a final guarded image/RBAC/admission diff, original extraction equivalence, CI publication, live enforcement or failure recovery; those remain required.

The [live Helm contract metadata](../evidence/bortus-helm-recovery-contract-20261011.json) confirms BORTUS zero-retry install/upgrade settings, helm-controller v1.6.5 with no explicit feature-gate override, and v2 support for explicit strategy/remediation fields. The current zero-retry defaults do not request last-failure remediation. For the final guarded release, explicitly set install and upgrade strategy to `RemediateOnFailure`, both remediation retries to zero, both `remediateLastFailure` fields to false, and `upgrade.cleanupOnFail` to false. Preserve normal readiness waits. A failed guarded transition must retain the forward state for reviewed compatible recovery, without automatic old-image/RBAC restoration or new-resource cleanup. This read-only metadata check is not an actual controller failure test; verify the effective final HelmRelease during release acceptance.

Those settings are now locally prepared and validator-enforced in chart commit `710e5ecd9434fc869eac12b497e326a21752c55e`, with both readiness/job waits explicitly enabled. [Qualification evidence](../evidence/bortus-helm-failure-qualification-20261011.json) records 22 passing guard tests and complete credential/render validation, plus read-only support for all eleven fields in the installed v2 CRD. The first validation failure remains recorded: a generated Python cache contained an inert exporter fixture header. Its exact bytes/redacted finding were preserved outside the checkout; CI now prevents bytecode output, without scanner suppression. Local QA used Python 3.14.4; actual GitHub CI on its configured Python 3.12 remains pending. No image, RBAC/admission contract or production state changed.

| Gate | Required evidence before proceeding |
|---|---|
| Final coherent source | One immutable combined commit; full A01Ã¢â‚¬â€œA22 and KV acceptance ledger; exact tracked source/mode, schema, lock and all eleven forward-migration identities. Local tests and actual browser checks must cover the combined source. |
| Compatible images | Clean Linux Node 22 build, package findings reviewed, fresh/legacy forward migration, format-1 native state and restart/recovery qualification. Record OCI digests and verify identical preloads on all three nodes. Both release and recovery references must qualify for the current schema/engine. |
| Fresh recovery | Consistent encrypted SQLite/PVC and native/etcd checkpoints immediately before cutover, independent restore proof and protected artifact hashes. Preserve accounts, password hashes, session versions, exact aliases, grants, operations and rotation metadata. Historical backups remain retained. |
| Reviewed chart contract | Preserve the one-replica Recreate workload, claim/PV/Longhorn identities, stable externally supplied signing/lookup material and exact current namespace scopes. Use the distinct `bortus-kv` principal; keep adoption disabled during initial rollout. Review protected PVC and every credential reference against rendered manifests. |
| Admission and revocation | Install the reviewed native policies/bindings through validated delivery; require no API type-check warnings and actual enforcement after propagation. Reconcile all live direct/group grants and revoke the legacy principal's credential-reaching access. Preserve unrelated subjects and RBAC. Confirm the new principal's exact positive permissions and foreign/canonical-delete denials. |
| Real rejection cases | Use bounded server dry-runs or owned fixtures to distinguish guard rejection from schema/RBAC rejection: old image, alternate principal with protected PVC/credential, mutable tag, init/ephemeral helper, reference-removal update and old-image rollback. Confirm no existing legacy worker/helper retains protected access. Never print credential responses. |
| Adoption and live acceptance | Enable adoption only in a subsequent validated revision after the preceding gates pass. Verify current/history reads, CAS/conflict, policies and identity revocation, audited import/export, rotation/recovery, retention/destroy/GC, restart persistence, legacy aliases and user/UI access against the real deployed engine. Preserve unrelated native keys/type/metadata and all accepted application data. |
| Compatible recovery | Demonstrate recovery with a separately qualified KV-compatible image and the accepted forward schema/native history. Keep current accepted writes; never restore a pre-KV database over them or mount protected references with the old image. |

```mermaid
flowchart LR
    Source["Combined immutable source<br/>full local acceptance"] --> Image["Qualified release + recovery digests<br/>three verified preloads"]
    Image --> Backup["Fresh encrypted checkpoints<br/>independent restore"]
    Backup --> Guard["Validated chart delivery<br/>guards + principal revocation<br/>adoption disabled"]
    Guard --> Enforcement["Actual admission/RBAC proof"]
    Enforcement --> Adoption["Next validated revision<br/>enable adoption"]
    Adoption --> Live["Real KV/UI/preservation acceptance<br/>compatible recovery proof"]
```

These are release prerequisites, not completed results. Do not infer write authorization or guard enforcement from readiness, image labels, offline CEL tests or a true adoption flag. BORTUS maintenance may require stopping its legacy writer; keep the original claim and review controlled Flux/Helm suspend states before acting. Gluster, Vault/Consul originals and backups remain retained until the user's separate retirement approval.

`scripts/migration/compare-bortus-databases.py --source <protected-checkpoint.db> --target <protected-migrated-or-restored.db> --mode forward|recovery --output <new-evidence.json>` compares independently supplied, consistent, checkpointed BORTUS SQLite copies. It opens them immutable/read-only, rejects nonempty WAL/journal companions, checks integrity and foreign keys, and detects snapshot changes. Forward mode requires every original column and row occurrence to survive, including accounts, password hashes, aliases, configuration, migration identities and any existing KV tables. Added columns/rows are allowed; legacy accounts gaining sessionVersion must receive zero. Recovery mode requires identical schema and complete row multisets, including new accepted KV metadata; loss, extra rows or changed credentials fail. Unfinished Prisma migrations fail both modes. Its report contains counts and booleans, never stored values, row identities or credential/database digests. It refuses evidence overwrite and does not mutate either input. Limits are 256 MiB per database and 250,000 rows per table. This checks supplied snapshots only: externally prove cold/consistent capture, exact qualified migration identities, image compatibility, native current/history preservation and PVC/Longhorn recovery separately. Synthetic comparator regression results are not live migration or restore acceptance.

Before the fresh BORTUS-only checkpoint, run `scripts/migration/inspect-bortus-checkpoint.py --expected-claim-uid <retained-original-uid> --output <new-metadata-report.json>` from WSL. It reads only scoped PVC/PV/Longhorn/Deployment/Pod/ReplicaSet/Flux/backup-target metadata, verifies the original claim mapping, Retain/keep, healthy encrypted two-replica storage, exactly one Ready claim consumer, its actual Pod Ã¢â€ â€™ ReplicaSet Ã¢â€ â€™ Deployment owner UID chain, Recreate, and the existing chart/Flux owner. It refuses a recreated claim or inconsistent storage mapping, unexpected consumers, drift and report overwrite; output contains no database or Secret values. PV and Longhorn UIDs are recorded, but historical identity equality is not checked without an independent original baseline. Separate reads are not an atomic checkpoint, and consumer/controller ownership must be rechecked immediately before stopping the writer. The [scoped qualification](../evidence/bortus-checkpoint-preflight-qualification-20261011.json) binds nine regression tests and the actual read-only live report to the helper's exact committed bytes; it does not prove cold capture or recovery.

An optional `--holder-image <qualified-tagless-OCI-digest>` proposes one inert Node holder on the writer's node, with the original claim read-only, pullNever, no service-account token, no environment credentials and no application entrypoint. Digest syntax alone proves neither qualification, preload nor admission. The proposal is never created by this inspector. Supply the actual separately qualified KV-compatible image after final handoff, verify all three preloads and guard acceptance, and review the UID/resourceVersion-fenced suspension/cold-capture/resume sequence before execution. Do not reuse `backup-native-volumes.py` for this release: it stops unrelated writers and uses a Python holder that does not satisfy the new protected-reference guard. The historical fixed-input `restore-native-bortus-backup.py` is also not acceptance of a fresh KV checkpoint; restore that fresh backup independently with the compatible holder and the complete-row comparator. Capture/restore remain pending until executed and verified.

For the independent restore, use the newly completed checkpoint's exact Backup UID, snapshot identity and credential-free NAS URL, rather than the historical fixed backup above. `scripts/migration/inspect-bortus-independent-restore.py --checkpoint-journal <protected-completed-journal.json> --holder-image <qualified-tagless-digest> --alternate-node <other-ready-node> --output <new-report.json>` reads the current source identity chain, exact completed full cold backup/snapshot, source capacity, StorageClass and alternate node, and refuses prior target-name collisions. It requires the completed authenticated SQLite/NAS checkpoint and returns three inert proposals, exact guard reference requirements and verification metadata only. It never creates resources, reads database/Secret values, proves image qualification or substitutes for actual admission/preload/restore acceptance. Separate reads are not atomic; recheck before any execution. The installed `longhorn` StorageClass currently specifies encrypted storage, two replicas, Retain, Immediate binding, ext4, the default backup target and CSI Secret references to `longhorn-system/longhorn-crypto`; this metadata inspection reads no encryption key and is not decryption or restore proof. The preflight deliberately refuses an unreviewed parameter or a source size other than the currently verified 1 GiB. Recheck those settings at execution. Prepare a uniquely named, retained StorageClass with only the reviewed parameters and that exact `fromBackup` URL, plus a separate retained claim sized for the source. Never bind the restore claim to the original PV or scale/change the production writer for this step.

Before creating the restore consumer, add its exact claim name to the reviewed admission contract's protected references, keeping the original references and qualified image allowlist. Validate and conditionally update the actual policies, then prove denied incompatible image/ephemeral-container substitutions and an allowed inert holder. Use the independently restored claim read-only with the qualified tagless image, `imagePullPolicy: Never`, no service-account token or credential environment, no application startup and a preloaded alternate node. Recheck its actual claim/PV/Longhorn UIDs, distinct volume handle, encrypted two-replica policy, completed restore and sole owned consumer before reading. Name/digest syntax, a Ready Pod or a new claim alone establishes none of these gates.

The [hash-bound preflight qualification](../evidence/bortus-independent-restore-preflight-qualification-20261011.json) at `8caa445fb04fd86368fbefeb95053dc74ad898ef` records eight passing local restore-preflight regressions and all 58 passing helper tests. The new preflight cases use synthetic completed checkpoints, including original/backup recreation, incomplete or ambiguous capture, cold/full/source/capacity mismatches, credential-bearing or foreign NAS URLs, encryption/CSI-reference drift, unready/source-node placement, target collisions, malformed/bounded collections, private-field omission, fixed API failure and evidence-overwrite refusal. Subsequent review reproduced an additional defect: URL parsing silently discarded empty duplicate or unknown query fields. Both cold-checkpoint and restore-preflight validators now preserve blank values and allow at most two fields before requiring exactly the expected backup and volume values. Empty extra fields are refused. The [later correction qualification](../evidence/bortus-backup-url-fence-qualification-20261011.json) at `0299079dc9371f523e0c76abe59d908559dcd9b3` binds the corrected focused 30-test and complete 58-test runs, independent review and retained prior failures; the earlier qualification covers only its original source. No live checkpoint journal has been evaluated by this new helper, and it has performed no resource creation or restore.

The future restore coordinator must use its own exclusive protected journal, separate from the cold checkpoint. Persist pending/confirmed/uncertain outcomes before and after every guard update and StorageClass, claim or holder create/delete; record returned UID/resourceVersion identities. A lost reply or restart requires inspecting and explicitly resolving ownership, never replaying a mutation or adopting an object solely by name. Keep the exact fresh checkpoint/Backup UID and the created restore claim Ã¢â€ â€™ PV Ã¢â€ â€™ Longhorn UID/volume-handle chain in that journal. Bind the encrypted restored artifact and complete-row comparison report to those identities, the actual holder UID/image/node and controller confirmation that restoration used this exact backup. Recheck that chain, sole owned restore consumer and unchanged production source-writer/storage invariants before and after the bounded read. Proposal generation and a Ready holder alone cannot establish this ownership or restore provenance.

`scripts/migration/bortus-restore-journal.py` provides the initial ownership-ledger library for this future coordinator. It requires an owned mode-0700 parent, creates an exclusive mode-0700 run directory and mode-0600 records/locks, and pins parent/directory/file identities. Creating the run flushes the parent directory entry before initialization can succeed. Nonblocking no-follow bounded reads and both record-file and run-directory fsync precede API callbacks. Its narrow metadata schema is validated on reopen and every save; extra fields and unsupported operations refuse. It records each create/delete intent once; pending, confirmed and uncertain entries cannot be replayed on reopen. Returned create identities are retained only after caller validation and exact kind/name/namespace/run-label checks. Holder deletion requires a prior confirmed holder identity and a separately supplied fresh resourceVersion for that same UID; live spec verification still belongs to the future executor. Foreign/replaced locks and failed owned run directories are retained. The [library qualification](../evidence/bortus-restore-journal-qualification-20261011.json) at `82908019bcd522b24ca8615c0995b15d0f0b2c0a` binds ten POSIX filesystem/fault regressions and the complete 40-test focused BORTUS helper group; independent review found and verified correction of the parent-flush gap. The initial probe remains honestly identified as tool-output evidence with its exact script saved afterward, rather than a raw source/stdout archive. No actual power-loss test was performed. This library alone performs no API call, guard update, source/storage verification, capture, deletion or restore. Guard changes must continue through validated chart delivery and actual enforcement proof. Executable integration and live execution remain pending.

The [Longhorn 1.12.1 restore contract](../evidence/bortus-longhorn-restore-contract-20261011.json) binds installed metadata schemas and 38 retained primary-source/review artifacts. Its correction addendum supersedes the initial requirement that restore history must remain populated after reattachment: the sync agent initializes restore status in memory and loses it on restart. Normal manager detach also clears monitoring fields. See the [engine implementation](https://github.com/longhorn/longhorn-engine/blob/1fa902f0061b84b92af445c38392bfeb99faffb2/pkg/sync/rpc/server.go#L145-L170). A Pod created early through a dynamic PVC cannot guarantee keeping that first restore process alive, because attachment is rejected while restoration is active or pending. The executor must begin bounded metadata observations before creation and durably bind completion to the new Volume UID and exact accepted `fromBackup`. Prefer observed first-running Engine/per-replica backup consensus; alternatively, qualify the same-UID, source-bound `restoreInitiated=true` and `restoreRequired=true` Ã¢â€ â€™ `false` controller transition together with complete independent authenticated archive/normalized recovery-row equality. That transition is set by the [completion controller](https://github.com/longhorn/longhorn-manager/blob/8320238242e8c804325d9588ec1db10feb9f36b8/controller/volume_controller.go#L4935-L5008); record which proof was actually observed. Reattachment then requires the retained distinct UID/mapping chain, encrypted healthy v1 storage with two running RW replicas, current owned Engine/Replica identities and the sole qualified read-only holder, rechecked before and after the bounded read. Empty reset history may be explained by the recorded completion; detached flags, Ready alone or observation gaps cannot substitute for it. Installed release/engine/image compatibility must be rechecked before execution. This research performed nine scoped metadata GETs and no database/Secret reads or mutations; no fresh completion observation or independent restore is yet qualified.

The pure [restore-transition library](BORTUS-RESTORE-COMPLETION.md), imported from `e1e0f8d7b9a16837ff2c9edb582613c69706d87f`, evaluates bounded, ordered metadata projections for the reviewed Longhorn 1.12.1 v1beta2 contract. It requires a same-UID, exact-source `true/true` to `true/false` restore flag transition; absent or false/false initial flags are non-evidence, while later disappearance/regression, deletion, source/spec drift and watch errors refuse. Its immutable result contains selected identities and resourceVersions only, with data acceptance false. The caller must separately prove durable pre-creation watch startup and continuity, current image/admission/healthy two-replica/consumer fences and complete independent authenticated archive/row equality. A supplied prerequisite boolean is not that proof. Thirty-three synthetic regressions and a pinned default raw-byte scan passed in the isolated handoff; the [coordinator integration qualification](../evidence/bortus-restore-transition-integration-qualification-20261011.json) also binds 33 passing tests against the imported exact source. The library does not establish a live watch, perform a restore or replace the separately locally qualified callable coordinator and its pending live qualification.

Stream the restored files through the same bounded Node reader directly into a separate new encrypted recovery artifact in the protected operator run directory. Do not call the original capture wrapper with a fabricated checkpoint: it requires the original cold-storage fences and chooses the original NAS archive name. Authenticate and normalize the original checkpoint archive and independent restored archive into separate private tmpfs directories, run the complete-row comparator in `recovery` mode, retain only metadata evidence, and clean the two exact owned memory copies. Delete only the restore holder with current UID/resourceVersion preconditions after verification; retain the independently restored claim/PV, NAS backup and encrypted artifacts. Capture/restore errors or ambiguous creates stop for identity inspection without replay or deletion of retained data. Before compatible recovery after new KV writes, take and qualify a new checkpoint of those accepted writes; restoring an older pre-KV checkpoint does not satisfy that gate. The callable fresh-restore coordinator is locally qualified; actual live proof remains pending.

The callable [independent restored-data step](BORTUS-RESTORE-DATA.md) composes the direct reader, borrowed live Collector prerequisite, fresh source/healthy identity fences, protected durable data intent, both authenticated tmpfs normalizations, full recovery row comparison and independent exact cleanup under one deadline. It has no API launcher or holder deletion and keeps overall live/image/admission acceptance false. Callback and local-fixture qualification do not establish a production restore. Existing pending/refused intents cannot be replayed or adopted. The scoped [read-only metadata adapter](BORTUS-OPERATOR-MTLS.md) supplies bounded fresh GETs and complete lists; it does not grant the executor's source/health gates itself.

`inspect-bortus-independent-restore.validate_source` repeats the full original checkpoint, source/consumer, snapshot, backup, StorageClass and alternate-node fences without checking or adopting new restore targets. `prepare` additionally requires all target names absent before generating proposals. The executor can therefore repeat the original-source fences after its own target creation without concealing existing targets or fabricating an inventory. Source and target validation remain distinct, mandatory checks.

The callable `bortus-restore-source.py` supplies those repeated checks from the pinned original journal and fresh bounded TLS metadata. Every call rechecks journal SHA/inode/ownership before and after the source reads; it returns selected original identities and exact checkpoint/ciphertext bindings only. The coordinator owns its descriptors and must close them in its outer cleanup. All 12 source-fence and 365 combined root local cases pass without skips on frozen inputs. This callable cannot authorize image/admission or restore acceptance alone; the [integration evidence](../evidence/bortus-restore-source-integration-20261011.json) records its exact scope.

Native review's additional constructor fault regression reproduced a directory-FD leak before `fstat` registration. The correction registers each opened directory FD immediately for independent cleanup, preserving the original failure and qualification sources. All 13 corrected source-fence cases pass with frozen inputs; the [correction evidence](../evidence/bortus-restore-source-init-correction-20261011.json) keeps the original actual failure separate. This was a local fault test, with no live resource access.

The new `checkpoint-bortus-volume.py capture --preflight-report <fresh-report.json> --holder-image <qualified-tagless-OCI-digest>` implements the BORTUS-only native checkpoint sequence. It rechecks the report's actual claim/PV/Longhorn/Deployment/Flux UIDs and writer, server-dry-runs and creates one inert read-only holder, then conditionally suspends the existing shared Kustomization and only the BORTUS HelmRelease. Other HelmReleases and application writers are not stopped. Every controller mutation tests UID, current resourceVersion and the controlled field through JSON Patch; private resource bodies/errors stay out of argv and reports. It scales only BORTUS to zero, waits until the original writer is gone and the sole remaining consumer is the owned holder, streams complete SQLite database/WAL/SHM/journal files directly through age, verifies authenticated decryption in memory and a matching NAS ciphertext copy, then keeps checking the cold/storage/controller fences until the owned Longhorn snapshot is Ready. It releases only the owned holder with a durable once-only UID/resourceVersion delete intent and proves complete namespace-list name/UID absence before restoring the original replica/suspend flags. This lets a resumed writer attach the RWO volume on another node. It proves the real resumed writer owner/Ready state and healthy original storage, then completes a full native NAS backup. Capture failure also independently attempts holder release and conditional restoration; pending or uncertain deletion is retained and never replayed.

`scripts/migration/normalize-bortus-sqlite-archive.py --archive <protected-age-file> --ciphertext-sha256 <retained-ciphertext-sha> --output <new-metadata-report.json>` prepares a comparator input from an authenticated archive. It pins and hashes the original ciphertext inode, decrypts only into a new mode-0700 directory on the actual `/dev/shm` tmpfs, and uses the same bounded four-file framing validator to create mode-0600 copies. The original operator SSH identity is supplied by path; values, private keys and plaintext digests never enter argv or reports. Only after age exits successfully does SQLite checkpoint/recover that private memory copy. Integrity, foreign keys, deadline, normalized size and empty WAL/journal gates must pass; the active application database/volume is never opened. Current-generation WAL headers/frames are checksum-checked before normalization; old-salt tails from reset WALs are permitted, while truncated or damaged current frames and ambiguous returning current-salt frames fail. This follows the [SQLite WAL format](https://www.sqlite.org/fileformat2.html#wal_format). It preserves the encrypted source rather than silently normalizing a damaged current WAL.

Use the returned `database_path` with the complete-row comparator after independently preparing the other input. After comparison, `normalize-bortus-sqlite-archive.py --cleanup-report <retained-metadata-report.json>` checks the exact directory device/inode/owner and removes only its four known files and empty directory. It never recurses; identity drift, unexpected files or symlinks refuse cleanup for review. Failed preparation removes only its own partial tmpfs copy and closes the owned decryption child. Output reports are exclusive mode-0600 and contain verification metadata only. [Hash-bound qualification](../evidence/bortus-sqlite-normalization-qualification-20261011.json) at `c78aeee0f275f878c5192c5f4aa87f9f46ede1a8` records eight local normalization regressions and the complete 50-test migration-helper suite, including actual age authentication, committed WAL replay, both checksum byte orders, legitimate reset tails, damaged-WAL refusal and exact cleanup. These use disposable public fixtures and synthetic identities; this transformation does not prove cold source consistency, correct image migration, native Secret/history preservation or independent Longhorn NAS restoration. Fresh live capture and independent restore remain pending.

`bortus-sqlite-archive.py` bounds framing to the four exact SQLite filenames, 256 MiB per file and 512 MiB total, with 64-KiB body buffers and bounded pipe deadlines. The inert Node reader opens nonblocking with no symlink following, refuses nonfiles, detects changing size/inode/timestamps and newly appearing sidecars, and streams fixed framing without application startup or Secret access. Nonblocking open ensures a FIFO is rejected by the file-type check instead of hanging before it. The archive is created exclusively mode-0600 in the protected run directory. Plaintext hashes stay in memory; only ciphertext hashes, generic filenames, byte counts and verification flags enter the journal. The original SSH public key selects the age recipient and its operator-held private key authenticates recovery; key contents never enter argv or Git. Interrupted encrypted partials remain unaccepted. Output-overwrite refusal also closes the exact owned source child; it cannot leave a producer waiting on a full pipe. Encryption/decryption equality does not establish SQLite integrity, checkpointed comparator inputs, whole-row preservation or independent native-volume restoration. Local framing, actual age encryption/decryption and interrupted-archive resume tests passed. The earlier `tests/test_node_sqlite_reader.py` qualification passed seven actual Linux Node fixture cases against the installed Node 22 image; an added FIFO fixture reproduced a five-second timeout, with exact owned cleanup. The [nonblocking correction qualification](../evidence/bortus-sqlite-reader-fifo-qualification-20261011.json) binds the expanded eight-case actual Linux run, with every owned process and container closed. These tests use disposable public fixtures and the production reader, with no application entrypoint, production mount or native Secret access. They do not test concurrent file changes or prove final release image qualification, integrated live capture, NAS copying or independent restoration; those gates remain pending.

The cold holder requires the exact proposed tagless `spec.image` and literal matching runtime `status.imageID`; bounded `status.image` is display-only. A Running holder must have only a running state, zero restarts and one Ready container. Checkpoint preflight, repeated consumer checks and holder absence use a raw bounded complete PodList (namespace BORTUS, at most 10,000 distinct identities, collection resourceVersion, no continuation or remaining items; embedded item TypeMeta may be omitted, but supplied types must be v1/Pod). Missing or malformed inventories refuse instead of implying absence. Resume alone may restore the original Deployment replica field while the same owned encrypted two-replica volume is normally detached/detaching/attaching with unknown robustness; identities, retention, sole physical handle, nondeletion and consumer fences remain mandatory. Cold/read/snapshot gates still require healthy storage; writer readiness and backup completion require healthy storage. Faulted volumes are never allowed. A resumed writer wait can observe normal attachment transitions without recording success prematurely. These source changes and local synthetic tests do not grant live capture, image, admission or restore acceptance.

Per-run journals live outside Git in the operator's `~/.local/share/branconet-migration/recovery/bortus-checkpoints/<run-id>/`, with exclusive locks, atomic mode-0600 writes and pending/confirmed/uncertain outcomes. API timeout or ambiguous mutation response is never automatically replayed. Conditional resume waits for a known original writer still terminating after a lost stop reply; a foreign consumer blocks unsafe restart. An interrupted run retains its encrypted archive, snapshot, backup and holder evidence; inspect the actual controller state first. `checkpoint-bortus-volume.py resume --run-id <retained-run-id>` conditionally restores recorded controller fields and checks the actual writer; it does not repeat capture, create missing archives/backups or delete retained recovery artifacts. A stale process lock requires explicit inspection, not blind deletion. Holder syntax/server dry-run is not image qualification or preload proof. The helper reads SQLite bytes directly into encryption, never reads native Secrets or persists plaintext, and does not independently restore the volume or qualify whole-row preservation. Those release gates remain required. The earlier [local qualification](../evidence/bortus-cold-checkpoint-helper-qualification-20261011.json) binds the pre-archive source's 12 fault/ownership/privacy regressions and complete 33-test migration-helper suite. The subsequent [encrypted archive qualification](../evidence/bortus-encrypted-sqlite-archive-qualification-20261011.json) binds the integrated archive source, 40 helper tests and seven actual Linux Node fixture cases, with the original overwrite-cleanup failure retained. The initial lost-stop-reply cleanup failure is also retained. The cited qualification was local only; fresh live checkpoint evidence is recorded separately by the coordinator.

The cold checkpoint journal accepts the existing operator-owned runtime anchor when it is not group/world writable (currently mode 0755); it does not chmod that anchor. It durably establishes owned mode-0700 recovery parents and flushes each parent entry before any API client is used. A run pins parent/directory descriptors, owns an exclusive nonce/inode-bound mode-0600 lock, and uses bounded no-follow nonblocking reads. Every save flushes its record, atomically replaces it through the pinned directory, then flushes that directory before a mutation callback can proceed. Changed run/lock/record identities refuse rather than overwrite foreign state; initialization failures close owned descriptors and retain partial runs for inspection. This corrects the older helper's missing directory-flush ordering. The [durability qualification](../evidence/bortus-cold-journal-durability-qualification-20261011.json) binds all 110 passing helper tests, including nine actual POSIX filesystem/fault cases, the original failures and independent review. It uses synthetic API callbacks and disposable encryption/Linux reader fixtures; it is not a power-loss or live capture test. The subsequent [runtime-anchor refinement](../evidence/bortus-cold-runtime-anchor-qualification-20261011.json) passed 23 focused cold-control/journal tests, including a tenth POSIX journal case proving an owned 0755 anchor is preserved while 0775/0757 anchors refuse. The 110-test full suite belongs to the preceding source; it was not rerun for this refinement. The [physical-volume fence integration](../evidence/bortus-physical-volume-fence-integration-qualification-20261011.json) closes the prior PV-alias inventory gap: all 100 combined pure BORTUS tests pass, and an unchanged live read-only preflight confirms a complete 53-PV list with only the expected original PV UID using that Longhorn handle. These separate reads are not atomic and must be repeated under execution/consumer/admission coordination; they do not establish a live checkpoint or restore. Holder deletion now saves the exact live holder UID/resourceVersion as pending before its existing preconditioned API request, records ambiguous outcomes as uncertain and confirms successful submission durably. A retained deletion intent always refuses another deletion request; resume only restores original controller fields and never replays deletion. The [delete-intent qualification](../evidence/bortus-cold-delete-intent-qualification-20261011.json) passes all 29 focused cold-control/journal tests, including six new actual POSIX delete cases with synthetic API callbacks. No full helper suite or production capture is claimed for this source; observed holder disappearance and final executor acceptance remain required.

`scripts/migration/inspect-bortus-release-rbac.py` inventories the old service account's direct, username and group grants before the guarded release. Supply the operator kubectl/kubeconfig and a new output path; it reads only Roles, ClusterRoles and bindings and refuses evidence overwrite. The report preserves exact binding/role UID and resourceVersion, rules, unresolved references and the count of unrelated subjects. Review every matching grant, including `system:authenticated` and service-account groups, while preserving unrelated subjects. Separate reads are not atomic; this inventory neither changes permissions nor proves actual authorization or revocation. Recheck immediately before release and qualify actual principal access afterward.

The [2026-10-11 02:25 UTC inventory](../evidence/bortus-legacy-rbac-20261011T0227Z.json) resolved all 42 matching bindings: the expected 37 direct service-account grants plus five built-in group grants. Those group rules cover self-subject reviews, public discovery, issuer keys and cluster trust bundles; retain them and unrelated subjects. The direct credential-reaching grants still require reviewed revocation and actual principal checks during the guarded release.

The [603-alias administration/rotation handoff](../evidence/bortus-kv-workflows-handoff-qualification-20261011.json) qualifies ten actual local browser checks against unchanged production code, with original failures retained. It supports UI workflow readiness only; actual workload consumption, full assistive-technology/zoom, final image and live engine/data recovery remain release gates. Root independently verifies the entire 965-blob/mode archive and all 20 retained artifacts; source scan remains exit 1 with two unresolved historical byte-provenance findings.

The [current delivery refresh](../evidence/bortus-delivery-current-refresh-20261011.json) confirms matching successful-CI/main/validated/Flux revisions while BORTUS still uses its original accepted image, principal and PVC. The [optional-code contribution measurements](../evidence/bortus-optional-code-handoff-qualification-20261011.json) are local characterization only. Neither record qualifies the final KV image/schema/principal/admission or replaces the unchanged frozen performance and full-data recovery gates.


The checkpoint source fence also requires the complete cluster PV inventory described in [BORTUS-PHYSICAL-VOLUME-FENCE.md](BORTUS-PHYSICAL-VOLUME-FENCE.md). Only the original PV name/UID may reference the original Longhorn volumeHandle through driver.longhorn.io; any duplicate or foreign PV alias refuses even when inactive, unbound or deleting. The fixed raw API list accepts at most 10,000 PVs within the existing 8 MiB output check and refuses continuation, malformed/missing lists or absent original identity. Independent restore preflight inherits this fresh source fence. Every cold storage check repeats it, including the existing before/after encrypted archive streaming and NAS-copy checks. These separate reads are not atomic and do not establish live capture or restore acceptance.

## Actual immutable recovery-holder preparation

The [7e30 holder receipt](../evidence/bortus-holder-source-image-7e30-20261011.json)
binds independently verified source/test artifacts to an actual immutable build
and verified export. The application candidate's performance gate remains failed;
this preparation is for an explicit inert Node reader, with no application startup.
Default image/image-config Secret scanning has zero findings. The scanner reports
346 vulnerability entries, including four fixable High bundled-kubectl entries;
production remediation and inert-holder reachability review remain required.
Three-node OCI preload and actual inert public-fixture Node/Prisma/reader runtime
now pass with [separate actual evidence](../evidence/bortus-holder-preload-runtime-7e30-20261011.json).
Read-only production-holder fencing, active guard qualification, fresh checkpoint
and independent complete-row restore remain open. All original sources
and data stay retained. No build/export/scanner result grants those later gates.

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

## c29fc staging and bounded image metadata checkpoint

The [single sequential preload](../evidence/bortus-app-preload-c29fc-20261011.json)
completed at12:37:08 UTC on all three nodes. Archive/config/source labels and
selected/runtime OCI manifest match on every node; root verifies the terminal
and exact process closure. This is immutable cache staging. At this12:37
checkpoint, digest aliases and inert Kubernetes runtime were pending; their
later completion is recorded below. No production app, PVC consumer, schema
or admission change was dispatched.

The [bounded selected-file probe](../evidence/bortus-app-minizip-metadata-c29fc-20261011.json)
found no MiniZip pathname/ELF token/linkage in its selected package/runtime
files, with one copyright text reference. Eight Linux owners, the Windows child
and complete labelled container list are verified absent. Whole-image security
and reachability are not accepted; original default scan findings remain.
Complete production-row independent recovery, compatible guard withdrawal,
final performance/security and actual engine acceptance stay required.

## Immutable application audit reconciliation

The [root acceptance-ledger review](../evidence/bortus-app-acceptance-ledger-review-20261011.json)
verifies all22 original validation clauses,45 source blob/mode/working-byte
bindings,25 retained evidence byte bindings and seven exact publication files
at immutable55fdb44e/c29fc. All delivered acceptance flags remainfalse; this
is a source/evidence review, not another runtime or final image qualification.
Git LF, Windows CRLF and one retained mixed-EOL source relation are explicit.
The original selected default scan remains exit1 with one individually verified
historical prose match and no suppression; a corrected three-word UTF8byte
column review retains the original mistaken count. Two older whole-history
provenance findings remain unresolved. Later handler work is qualified separately.


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

## 2026-10-11: live collection metadata refusal

The next read-only phase-one preflight refused at BORTUS PodList item validation:
the validated collection's items omit `apiVersion` and `kind`. The retained
diagnostic reports only shape booleans and fixed error codes. No guards, restore
resources or application mutations were dispatched. The adapter now supplies
only absent headers from a fully validated typed collection, while retaining
explicit-header, identity, completeness and duplicate refusals. Current-source
local TLS controls and a fresh actual preflight pass as recorded below; old
receipts remain bound to their original reader.

The current reader passes 57 scoped metadata/source/checkpoint preflight tests
with frozen inputs and an actual reaped child. Fresh actual SourceFence.prepare
also passes using the same metadata bytes: original storage/controller identities,
completed backup and unused restore target are confirmed. This is read-only
preflight evidence; admission publication, actual probes and whole-row restoration
remain open. The earlier metadata_shape refusal is retained. See the
[typed-collection evidence](../evidence/bortus-typed-collection-preflight-20261011.json).

## 2026-10-11: coordinator review and subagent ownership

Coordination now uses this migration coordinator and the two existing application
and native/recovery subagents. The seven old BORTUS chats are archived; no new
chats or chat messages are part of this orchestration. Application edits remain
in the isolated application worktree, and the recovery module in its own branch.

The [independent FIFO review](../evidence/bortus-account-fifo-root-review-20261011.json)
verifies 338 raw source Git blobs/modes, 16 raw qualification blobs/modes, 37
private originals, all 351 ZIP members, 337 executed source files and the 4,262
compiled hash inventory. The retained five stages have actual zero exits, with
235 unit tests and four original strict HTTP tests passing. The default scanner's
actual exit remains one: all 159 selected public checksum/prose byte spans were
independently rehashed; two historical provenance findings remain open. This
receipt covers a48601a/b6fde8d only, not the subsequent shell-error correction,
final image, live application acceptance or performance.

Automatic approval review rejected the combined guard chart push/PR command,
stating "blocked by policy", before execution. The
[rejection record](../evidence/bortus-phase1-publication-review-rejection-20261011.json)
leaves guard publication, live admission probes and independent whole-row restore
open. Existing source, storage, credentials and running writer are preserved.
The active goal remains incomplete; local recovery and app qualification continue.

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
probes or independent whole-row restore: neither has run yet. Review identified
an additional typed collection item-header assumption in probe cleanup; its
qualified correction is required before fixture creation. No forward schema or
new application entrypoint has started. Two subagents and the migration coordinator
continue the active goal; the seven old BORTUS chats remain archived.

## 2026-10-11: continuous source-control preparation

The [quiescent checkpoint](BORTUS-QUIESCENT-SOURCE.md) composes capture, full
backup and owned-holder removal while the source stays at zero writers. Its
[control observer](BORTUS-QUIESCENT-WATCH.md) owns three concurrent verified TLS
streams and fsynced metadata; a caller must check the actual prerequisite before
and after mutation dispatch and independently close the borrowed resources.
Only the explicit once-only owner transition resumes `migration-releases` so
validated Flux can withdraw the legacy image from the guards. The BORTUS
HelmRelease remains suspended and Deployment remains zero throughout that future
transition. This preparation has not run against the live source.

Independent root mTLS fixtures reproduced a deadline-renewal defect in the first
immutable observer: three late bookmarks left its readers live after the absolute
lease. The corrected source refreshes the remaining original budget before each
read; the same root fixture now observes sticky deadline failure and zero live
readers. The original handoff and failing observation are retained. The corrected
handoff passes 86 scoped local controls; root combined integration qualification
now passes all 524 test_bortus*.py cases with zero failures/errors/skips and 151
frozen inputs, including the required JSON fixture. The initial fixture-omitting
staging run is retained; production Python sources did not change between runs. These checks grant no live restore, forward-schema, image, rollback
or whole-row acceptance. The deadline-aware encrypted archive callback and
actual source/image/schema/guard producers must still be wired before live use.

See the [root integration evidence](../evidence/bortus-quiescent-root-integration-20261011.json).
