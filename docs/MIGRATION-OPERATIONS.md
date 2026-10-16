# Approved cluster migration operations

## 2026-10-15: hosted regression sensitivity and real-CLI prerequisites

The [seven-case hosted CI receipt](../evidence/bortus-hosted-seven-regressions-root-20261015.json) records successful run 38770022640 on validation commit 3420513e, with frontend 2dd777ca/workflow a8198320 equal to owning source e386e5bf; docs commit e1ef6bd6 preserves both. Clean install/build, lint/types, 342 units and eight integrations pass. Seven pristine cases pass and their separate source mutations fail at the unchanged intended assertions. The two new database controls specifically detect deleted-account JWT fallback and multiple bootstrap writers; their expected nested child assertions and parent aggregates are matched exactly. The earlier five controls remain intact. All fourteen bounded children restore inputs; no tests are skipped. Default raw-source, hosted-log and docs scans report zero findings. Whole A19 remains open for meaningful cross-process regression sensitivity and the small browser CI smoke suite. Original warm performance failures, image security, recovery and live gates remain open; main and production are unchanged.

The [exact API image metadata receipt](../evidence/bortus-a04-file-capability-metadata-root-20261015.json) records one read-only save of the acquired image and independent revalidation of its 31,201,280-byte archive, selected manifest/config, fifteen layer diffIDs and fixed binary payload. Its revision-2 file-capability record permits only NET_BIND_SERVICE with the effective flag; four pure decoder groups pass against the retained public Linux UAPI header. This is saved-file metadata, not proof of the running effective set or exclusive EPERM cause. The first reader retained exit 1 for a tuple/list comparison error; corrected reader and independent current archive/source/process checks pass. The earlier cluster attempts remain failures. The separate [finite real-API fixture](../evidence/bortus-a04-real-api-finite-root-20261015.json) now passes44 checks with independent source/process/container closure. Its disposable API roles add only NET_BIND_SERVICE. Full A04, final image/security, production policy and retirement acceptance remain open.

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

The historical `scripts/migration/backup-config.py` produced the retained encrypted host/runtime configuration backups. Do not rerun it for the guarded release: although the local credential arrives on stdin, its wrapper embeds that credential in remote command source; its capture/encryption/copy operations also reset timeouts and permit destination overwrite. Historical successful decrypt/readback receipts remain evidence for those historical archives only. Application-data backups are a separate gate.

Fresh Kubernetes recovery configuration is prepared by `scripts/migration/capture-kubernetes-recovery-config.py`. Its callable requires the separately qualified checkpoint Transport and one absolute deadline, with no historical-helper/live CLI fallback. It captures a fixed 32-file set: standard control-plane/etcd PKI, API encryption configuration, retained Longhorn key, four component kubeconfigs and four static-pod manifests. This targeted archive complements retained broader three-host runtime archives; it does not replace their containerd/systemd/fstab contents. Custom PKI outside the fixed set requires a reviewed inventory/extension.

The callable creates an exclusive protected run under `config-captures`, pins the recipient/identity, encrypts with age and authenticates exact plaintext equality in private memory. Only ciphertext goes to the fixed exclusive NAS writer, with file/directory fsync and same-inode hash readback. Two bounded source reads must match around encryption/publication; this is per-read consistency, not continuous file history. Failed/ambiguous outputs remain retained without replay/adoption. A completed receipt also requires successful caller transport closure and actual launcher terminal0. API Secret decryption, LUKS recovery and a full three-host rebuild remain separate.

[Nine initial controls](../evidence/bortus-recovery-config-local-20261012.json) pass against immutable checkpoint v11. [Root integration](../evidence/bortus-etcd-config-root-integration-20261012.json) verifies the integrated18090f8 helper: all47 local controls pass without skips or ResourceWarnings in7.992s (8.338s wall), with164 unchanged files in a private POSIX copy. The earlier source-fence refusal and Windows-mounted fixture ownership failures remain retained without weakening checks. Real age/public-key fixtures and local transport shims run; actual SSH, sudo, Kubernetes and etcd are separate live prerequisites.

The first actual configuration run authenticated the32-file operator archive but refused NAS publication because the existing CIFS mount forces encrypted file mode0755. Both equal ciphertexts and the failed journal remain retained; that run is not accepted. A scoped configuration-writer correction permits0755 ciphertext only on the exact `/mnt/container-backups` CIFS mount, with stable mount identity, exclusive create, same UID/inode/size/hash and durable readback. The operator archive stays0600; plaintext never enters the NAS writer. Other filesystems require0600; writable group/world modes refuse. Shared SQLite/etcd writer defaults remain unchanged. The configuration/etcd qualification used only explicit config/etcd prefixes; its config default bytes remain unchanged. A separate literal SQLite ciphertext opt-in now admits the closed bortus-sqlite prefix under the same qualified CIFS identity rules; see [quiescent archive](BORTUS-QUIESCENT-ARCHIVE.md). Default SQLite NAS callers remain strict600/four-field and root must explicitly select and qualify the opt-in before latest-data capture. The integrated etcd streaming consumer retains its original512MiB ceiling, separate from the smaller configuration archive ceiling. [Twelve local controls](../evidence/bortus-config-cifs-local-20261012.json) pass with real age/cipher files and mocked CIFS forcing, covering accepted mount-forced0755, refused non-CIFS0755 and refused world-writable CIFS ciphertext. A distinct fresh actual32-file configuration run now passes authentication, transport closure and complete NAS ciphertext readback; see the [actual receipt](../evidence/bortus-kubernetes-config-actual-20261012.json).

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

The historical `backup-etcd.py` runs produced the retained isolated recovery receipts. The current replacement requires explicit source Pod/image pins, a freshly authenticated configuration archive, protected recipient/identity files, tool hashes, one absolute deadline and a unique run ID. Its former password-only CLI is refused. It encrypts/authenticates a consistent snapshot, publishes only ciphertext and independently restores the authenticated copy in an isolated loopback-only pod. Complete Secret ciphertext maps are compared at the snapshot revision; production etcd is untouched. See the [fresh checkpoint contract](BORTUS-ETCD-RECOVERY.md) for durable intents, conditional cleanup, credential/body separation and local/default transport qualification. Actual fresh checkpoint, API decryption and LUKS recovery remain separate. Matching API encryption keys require retained authenticated configuration backups; repeat checkpoint recovery after later Secret changes before retirement.

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
probes or independent whole-row restore; neither had run at that publication
checkpoint. The subsequent actual attempts are recorded below. Review identified
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


The [quiescent archive adapter](BORTUS-QUIESCENT-ARCHIVE.md) is now available
with a [root composition receipt](../evidence/bortus-quiescent-archive-root-20261011.json):
45 scoped local controls pass against current dependencies. It supplies the
encrypted, authenticated SQLite stream and exclusive fsynced NAS ciphertext
copy under the original quiescent deadline; existing archive callers retain
their default behavior. No live capture was dispatched. Actual schema/image/
admission producers and independent restore still precede forward execution.

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

The [root current source/image verification receipt](../evidence/bortus-current-image-root-20261011.json) records 154 local controls and one actual isolated read-only callback passing in 17.731 seconds. Twelve sequential SSH inspections freshly verify manifest/config hashes, source labels, ordered descriptors and cache blob presence on the three Ready nodes; all owned SSH children are absent. Two new schema receipts and exact current writer/storage/guard pins accompany the explicitly reused completed43 transcript. Layer bytes and the prior inert runtime fixture are not reexecuted. The timing-only callback trace correctly remains incomplete/refused because only one of six calls ran; its graph and deadline are never reused. This establishes timing and current prerequisites, not independent whole-row recovery or application startup. The initial v19 missing fixture-directory failure is retained; frozen v20 suites passed on unchanged exact sources.

The [actual independent b473 recovery proof](../evidence/bortus-independent-live-b473-20261011.json) completed at 17:41:44 UTC in 189.566 seconds under the original 300-second deadline. The separately restored encrypted Longhorn volume passed the complete SQLite recovery-row comparison against the authenticated cold archive. Both tmpfs copies were cleaned; all four operations, six callbacks, 72 fresh SSH inspections and twelve schema receipts completed. Same-UID watch evidence records restore flags true/true at RV1220694 then true/false at RV1220836, with no later regression. The inert reader is absent by fresh named404 and complete PodList UID/name checks; its StorageClass remains retained and its PVC remains Bound. Fresh post-run metadata confirms the original Ready writer/template/storage and six guard UID/RV/spec pins, plus current Ready Flux revision. The first post-review used the wrong lowercase standby key and refused; the corrected exact Longhorn `Standby` review passed without replaying restoration. Static completed43 outcomes and prior image runtime proof remain explicitly reused. Exact schema invocation floors are enforced by executed source, not separately reconstructed from retained scalar fields. Original coordinator overall flags remain false; this separate receipt accepts the cold-baseline recovery gate only. Latest-data capture, updated app build/performance/image, forward schema migration and final rollback/live acceptance remain pending. Gluster/Vault/Consul originals are retained.

The callable quiescent graph can use the [bounded interval client](BORTUS-QUIESCENT-INTERVAL.md)
for original-lease reads and durable once-only CAS dispatches guarded by the actual
continuous Observer. This adds no CLI or live authority and changes no existing
Ready/cold default; phase/schema/image/guard producers remain separately required.

The [separate phase producer](BORTUS-QUIESCENT-PHASE.md) now supplies canonical
six-guard reads, unchanged Ready-before-stop schema receipts and static authenticated
latest-capture schema proof with fresh zero-writer/observer fences. Actual root
source/image/publication authority remains an explicit callback and must be wired
to current receipt bytes and fresh cache metadata before use; local controls do not
accept a final image, latest-data capture or forward migration.


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

## 2026-10-12 06:00 UTC: current charts delivery and cluster health

The [read-only receipt](../evidence/bortus-current-delivery-health-20261012.json) confirms current charts `main` and `validated` both point to7828f5b5d219770077b72bd53d81fe745c61b621. The single [validation/promotion workflow](https://github.com/jtmb/branconet-charts/actions/runs/38150613416) succeeded for that exact push. The current Ready charts GitRepository and unsuspended Ready `migration-releases` Kustomization consume and apply that same validated revision. All3 nodes are Ready and all33 other HelmReleases are current, Ready and unsuspended.

BORTUS retains its original Deployment and service account and one Ready old3b076 writer. Its HelmRelease remains suspended at generation10/status observedGeneration10; its retained Ready condition belongs to generation9, so no current active Helm reconciliation or final engine rollout is claimed. This is maintenance status, not new image/schema/performance/data/recovery acceptance. No mutation or credential/Secret value was reported.


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

The [isolated API plaintext recovery preparation](BORTUS-ETCD-API-PROOF.md)
supplies fixed memory-bundle framing and an independent retained-snapshot
AES-CBC/protobuf Secret-to-API oracle. It changes no raw checkpoint acceptance,
starts no production process and creates no resources. Root must bind actual
authenticated inputs, isolation/cache/CNI and UID/RV cleanup before dispatch.
Local fixtures do not grant API decryption or full disaster-recovery acceptance.
The separate callable API transport now supplies explicit binary stdin and fixed
ConfigMap/ephemeral PUT/conditional cleanup methods under its own closed journal.
Existing checkpoint transport defaults remain unchanged. Root must wire real
source/material/cache/isolation receipt verification and the complete ciphertext
baseline before API addition; this source preparation has dispatched no resource.

## 2026-10-12: root integrated API transport and TLS readiness qualified locally

The [root qualification](../evidence/bortus-api-transport-readiness-root-20261012.json) verifies eleven native raw blobs/modes and 564 retained artifacts, then integrates the separate recovery journal/transport and fixed readiness operation. All 14 root Python transport controls and 15 actual pinned Node22 TLS controls pass, with 176 inputs unchanged and a fresh successful query proving the owned Node container absent. The first root supervisor refused during a transport run; unchanged inputs and observed child closure are retained, but its exact supervisory predicate is unproven. Successful tool output is retained by the execution tools; receipt fields are explicit transcriptions rather than claims of original stdout files.

The default checkpoint transport and CJS oracle remain unchanged. The new API journal/adapter requires actual external source/material/cache/CNI receipt authority and original absolute deadlines. Verified TLS readiness precedes the once-only oracle; pending/uncertain mutations cannot replay or adopt. These public/shim/TLS controls grant no cached-binary, live API decryption, Longhorn or complete recovery acceptance. No live resource or credential delivery occurred.

The [root retained-master preload controls](../evidence/bortus-retained-master-preload-controls-root-20261012.json) verify26 selected raw artifacts,58 closed archive members (57 originals plus exact manifest) and14 current executed source hashes. All11 public POSIX controls pass once in0.393 seconds; the gated supervisor exits0 in0.589 seconds under its original30-second bound. Default17-file scan exits0 with no findings, and fresh root checks prove all five test/supervisor/shim/scanner identities absent. V3 changes the fixture socket binding only; production helper/composer stay exactV2. The setup bootstrap and packaging failures and syntax warning remain visible. These controls exercise validators and actual public Python child/file primitives, not full privileged root_entry or image postconditions. The current retained server archive remains unobserved; a separate fixed-master caller and independent journal reader must qualify before server-side inspection/import. No image/import/Pod/policy operation is accepted here.

## 2026-10-12: current preparation gates

The [retained master inspection](../evidence/bortus-retained-master-inspection-root-20261012.json) is complete with independent closure; full archive verification/import is held. The [compile/prune partial review](../evidence/bortus-runtime-build-partial-root-20261012.json) verifies successful component commands while preserving wrapper failures. The [JWT/alias source candidate](../evidence/bortus-jwt-alias-focused-root-20261012.json) has28 affected tests, fresh types and lint,358 exact working/raw bindings and42 freshly absent process identities. Full functional/compiled HTTP and unchanged paired performance remain required. No cluster writer, schema, image alias or application source in this migration checkout was changed by these reviews.

## 2026-10-12: cache import and functional continuation

[Master cache import](../evidence/bortus-retained-master-import-root-20261012.json) is verified with full archive identity and independent closure; digest alias and API recovery remain pending. The [compiler fixture mount cause](../evidence/bortus-tmpfs-execution-cause-root-20261012.json) is measured rather than inferred. [Source9fd functional composition](../evidence/bortus-jwt-alias-functional-composite-root-20261012.json) passes280 units and8 HTTP/process controls without changing source, oracles or runtime-production permissions. Original failures remain retained. Original paired performance, immutable final image/security, latest-data backups and guarded live cutover remain open.

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

## 2026-10-12: late read-only Flux metadata refresh

The [root metadata receipt](../evidence/bortus-flux-readonly-refresh-root-20261012.json) records three fixed status-only GETs with actual outer exit zero. The charts source and migration-releases owner are Ready at validated commit7828f5b5d219770077b72bd53d81fe745c61b621; all33 active releases report Ready with matching top-level observed generations. The34th release, BORTUS, stays suspended at generation10. Its retained Ready condition is not new application or active reconciliation acceptance; this read does not query that condition's observed generation. Root separately verifies all four reader/CLI PID-start identities absent. No specs, Secret values or condition messages are requested, and no deployment changes. This refresh does not retest node health, application data, performance, security or recovery.

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

## 2026-10-13: source scans pass; performance comparison dispatched; recovery controls refuse

The [root checkpoint receipt](../evidence/bortus-qualification-checkpoint-root-20261013.json) records separate default scans of seven tested observer/lifecycle sources and eight raw documentation files: both exit0 with zero findings, unchanged selected bytes and freshly absent scanner identities; all44 retained originals are independently verified. The original paired comparison passes its66-input preflight and starts once against baseline51e8 and candidate8cf, using the unchanged five fixtures, exporter, driver, limits and three alternating pairs. Measurement and acceptance are pending.

The first public27 recovery-helper run exits1 with a late-durability/closure/deadline classification under its90-second supervisor. Its exact final refusal cause is unproved. Partial stderr contains material and TCP errors; there is no final test count, stdout or terminal journal, so no suite pass is claimed. Root independently proves the two recorded PID/start/UID identities absent and observes no members of either owned process session in a fresh97-process census. Public fixtures model age output and TCP/API replies; actual cryptography, network enforcement and recovery material are not accepted. Original failed inputs/output remain preserved. No live deployment, limit adoption or source-data retirement occurs.

## 2026-10-13: original comparison completes; warm-cache acceptance remains failed

The [root checkpoint receipt](../evidence/bortus-qualification-checkpoint-root-20261013.json) records unchanged original three-pair measurement with driver, supervisor and actual outer exit0. All six observations contain six complete profiles with equivalent expected inventories. Root freshly verifies10 PID/start identities and the separate dispatcher PID absent, eight exact container names absent,66 frozen inputs and431 exported-source hashes unchanged. CPU/memory/network/PID limits match every observation. The original summary is generated without altered fixtures, thresholds, timing windows or trimming.

Concurrent warm Pod p95 median baseline/candidate milliseconds are49.47/60.29 (small),58.57/70.99 (200),77.18/76.25 (1k),48.24/56.32 (25large),51.38/54.86 (three largest). Four comparable fixtures regress, so the required no-warm-cache-regression gate remains failed. Native Secret HTTP medians are88.82/76.30,67.90/68.84,70.83/76.09,259.42/175.48,187.85/152.31 and116.26/113.91. Whole-fixture CPU median falls35.21→30.91 seconds; peak memory rises364.39→419.56 MiB, with no observed OOM or throttling. These include fixture/driver work and do not isolate app CPU or memory. A07 remains failed/open; A21 and final image/recovery/live acceptance remain open. No source adoption, live rollout, benchmark replay or limit change follows.

A separate one-case diagnostic against the unchanged TCP helper/test captures child exit1 and one TypeError at test line232: inherited `self.state` is a PosixPath and hides the TCP fixture’s `state()` method. The diagnostic supervisor/actual outer exit0 means capture and cleanup only. Root freshly verifies13 PID/start/UID identities absent and all204 source bytes/modes/UID/link counts unchanged. This proves the selected assertion’s fixture failure, not the other original errors, a full-suite pass, actual age authentication or live TCP denial. A distinct source-only fixture correction remains pending.

## 2026-10-13: current cluster and charts pipeline read-only verification

The [current root cluster receipt](../evidence/bortus-cluster-current-root-20261013.json) verifies all three nodes Ready on Kubernetes1.37.1. The private charts repository has main7828f5b, one active validation/promotion workflow, and successful main-push run38150613416. Flux’s branconet-charts artifact and migration-releases applied revision both match validated7828f5b; their current Ready generations match. All33 active HelmReleases are Ready. BORTUS remains suspended at generation10, whose Ready condition is historical generation9; its one Ready pod still runs old image3b076fb9. No new candidate is deployed.

All54 PVCs are Bound. Observed attached Longhorn volumes report healthy, encryption enabled and two configured replicas; detached retained volumes report unknown robustness. These metadata reads do not establish data integrity, latest backups or plaintext restore acceptance. Retained game/recovery PVCs are preserved; no game release was installed. The observations span separate read-only queries, not an atomic snapshot. Final image/security, performance, recovery and guarded live acceptance remain open.

## 2026-10-13: filesystem scheduling controls and isolated HTTP cost

The [root local-controls receipt](../evidence/bortus-sync-fence-recovery-controls-root-20261013.json) qualifies an outside-production prototype that runs every ancestor/leaf lstat and access check synchronously, then yields with setImmediate before either success or refusal. All16 controls pass: fresh projections, revocation/deletion, all checks after a fault, permission/symlink/schema/config/inode failures, queue saturation, abort/close ownership, BUSY retry and deadline expiry. Root verifies130 originals, current362 source files,5384 compiled and40635 dependency objects;20 recorded identities and both exact container references are absent. No authority result or filesystem identity is cached.

A separate once-only public loopback diagnostic passes480 requests in24 untrimmed alternating batches. Both independent identical agents open20 sockets on their first batch and fully drain. Median batch latency is11.151→8.016ms; median CPU is15.296→9.203ms. Batch p95 is the maximum of12 batches,60.153→16.366ms; individual client p95 over240 requests is50.380→10.957ms. First batches and instrumentation remain included. Shared-process setup and aggregate event-loop occupancy prevent isolated syscall/startup claims; timer samples cannot prove absence of blocking. This measures one fresh session projection per request, without JWT or Next. Root confirms all current inputs unchanged,16 recorded identities absent and both exact container references absent. Production integration and the original functional/Next performance gates are still required. One-active/64-queue/5000ms semantics and native eight-request/size/item limits remain unchanged; kernel I/O has no hard wall bound. A07/A21 and deployment stay open.

## 2026-10-13: corrected recovery helper controls and bounded identity evidence

The [root local-controls receipt](../evidence/bortus-sync-fence-recovery-controls-root-20261013.json) preserves the original public27 exit1 and absent final count; its whole-run refusal cause remains unproved. The separate one-case diagnostic identifies only the fixture method shadowing by a Path. The corrected fixture renames that accessor, fixes the closed-stdin age-exit assertion, and adds two once-only replay refusals; material production remains unchanged.

Nine identity-publication controls pass, covering boundary counts, exclusive publication, partial writes, changed input/hash and manifest collision. The separate corrected29-case suite exits0 with zero errors/failures in43.260s. After actual child shutdown/reaping/absence checks, it publishes1172 observed identities across five hash-bound shards; root reads every shard and freshly confirms1173 identities including the supervisor absent and207 source files unchanged. Only this fixture's evidence capacity increases512→4096; operation, output and90-second/closure limits stay unchanged. Root verifies240 archived originals plus21 pure-control and21 diagnostic originals by bytes/hashes/CRC. The first partial copy refusal is preserved; its unrecorded Windows stat difference has unknown cause, and Windows stat is not Linux metadata authority.

These controls prove real local FD/child/pin and publication behavior using modeled age output and API/TCP replies. They establish neither actual age cryptography nor live network denial, accepted private-material delivery or Kubernetes API plaintext recovery. Actual public TCP isolation is the next independent gate, before private recovery parts. Final image/security, latest backups, guarded rollout and full recovery remain open; Gluster/Vault/Consul originals remain retained.

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

### Public TCP attempt refused; independent failure inspection (2026-10-13)

The [root failure receipt](../evidence/bortus-public-tcp-refusal-root-20261013.json) preserves both attempts. The first attempt stopped before operation setup; a separate filesystem witness found a missing external path. Its original caught exception remains unknown. Root verifies all229 immutable originals. Corrected external paths pass a six-file protected preflight before a fresh200-file stage and second attempt.

The fresh e983 attempt exits1 after14.411 seconds. Both public utility Pods are confirmed; policy creation remains pending with its observed UID. No accepted TCP result or cleanup follows. An independent30-second read-only post exits0: all200 source bytes are unchanged, all198 observed and197 registered jobs (199 unique identities including supervisor) are freshly absent, and five queries confirm the three exact-owned resources remain present with full matching specs. Root separately confirms the post reader and its five jobs absent.

The current typed NetworkPolicyList item omits apiVersion/kind. Its unchanged strict matcher refuses the item; a copy adding only the missing envelope-derived headers passes the full matcher. This identifies a current semantic defect consistent with the last durable boundary, without claiming a recorded historical exception. Cleanup must use exact UID/current resourceVersion preconditions, remove both Pods before their policy and verify complete typed absence. Cleanup is pending at this checkpoint.

Default corrected-source scanning retains literal exit1 and two public checksum-constant findings, with no suppression or overall scan pass. Performance observer V3 and its14-control preparation remain unrun after source review identifies explicit connection-attribution and late-publication gaps. No benchmark replay, limit change, private material, source adoption or original data retirement follows. A07/A21, final image/security, fresh recovery and guarded rollout remain open.

### Exact-owned public utility cleanup completed (2026-10-13)

Separate cleanup787848d38638 exits0 in1.980 seconds under its original30-second deadline, with an early recorded child gate and the same inherited deadline. Fresh full specs and fixed UIDs precede each once-only DELETE with current resourceVersion preconditions. Both utility Pods are verified absent before withdrawing their policy. All three actions and the five final read-only checks pass. Root freshly verifies the recorded supervisor, child and24 CLI jobs absent; original refused ledgers remain byte-identical. The two selected cleanup sources pass default scanning with zero findings and fresh scanner absence. This root outer is not claimed as a generally qualified failure-closure controller.

A separate five-query read-only observer exits0 and independently confirms all three names/UIDs absent from complete typed collections, all200 source files unchanged, and its reader/five jobs freshly absent. The original TCP actor remains exit1 and its gate remains open. No private material, benchmark replay, live app adoption or original data retirement follows. The [root receipt](../evidence/bortus-public-tcp-refusal-root-20261013.json) includes both failure and cleanup scopes.

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


### TCP acknowledgement and interrupted proof — 2026-10-13

The [root acknowledgement review](../evidence/bortus-tcp-delete-ack-root-20261013.json) preserves dda81 actor outer/caller1 separately from readonly0, guarded cleanup0 and typed absence0. The original target DELETE was not repeated; peer/policy used fresh UID/RV preconditions. The281 immutable originals distinguish executed Linux bytes from Windows CRLF copies and preserve the earlier packaging refusal.

Kubernetes [Pod storage](https://github.com/kubernetes/kubernetes/blob/v1.37.1/pkg/registry/core/pod/storage/storage.go#L72-L83) permits a returned Pod on deletion. Twelve pure acknowledgement controls pass: exact original Status or Pod-role v1/Pod/full original spec/name/namespace/UID/valid RV, with only a bounded deletion timestamp removed on a copy. Body, grace, deadline, wait, typed absence and confirmation remain unchanged. Historical reply/exception is unretained.

The new6de44 actor remains failed: outer1/caller-15, no caller terminal or registered-job terminal evidence, all three creates confirmed and no deletion intent. The incomplete `source_unchanged:false` flag does not prove drift: root freshly verifies200 staged files unchanged and281 recorded births absent. An uncaught `/proc` ProcessLookupError is a possible source boundary, not a proven exception. Five readonly full-spec/UID checks precede three separate guarded deletions;26 cleanup births and six independent reader births are freshly absent. Named and complete typed lists confirm all three owned identities gone. No success-only reader replay, public TCP acceptance, private holder authority/private recovery execution or original-data retirement follows. Supervisor qualification, final image/security/latest backups/guarded rollout remain open.


### Authorized account-read evaluation and initial controls

The reviewed source-only V3 proposal (handoff SHA256 `5081cd59012bef7f5eadee67a9885c7d54c1a1670240306ae32cc79e6d05fcae`, proposed reader SHA256 `ac2f761d69db7f20e6f245487ee5e2b95518f33da9baa6642a20aab7c1fea08e`) changes one retained active read to two overlapping envelopes on one synchronous readonly SQLite connection. Total admitted ownership would change from 65 to 66; the 64 waiting slots remain fixed. It includes cold-import rechecks and captured-connection fences at SQL completion and final public settlement, with 19 mandatory controls before a bounded comparison. SQL calls remain synchronous on one isolate. Both real yields, fresh checks, the 5-second result fence and all native limits stay fixed. No performance benefit is claimed.

The user instruction to continue autonomously authorizes the isolated two-read V3 evaluation, as scoped in the immediate root notice. Production source remains at one pending qualification/adoption. The initial isolated controls exit zero: contract cases01–17/19 and preliminary module-owner18a pass; original case18 actual Next compiled ownership remains open. Root verifies362 source,5384 compiled,40635 dependency objects and22 preparation inputs unchanged,23 process births absent and both exact container name/ID absent. This is control qualification only; full functional/build, actual compiled ownership and unchanged performance acceptance remain required before adoption. The changed bound applies only to the isolated evaluation. Original case18 actual Next compiled ownership remains mandatory; preliminary module-owner controls cannot replace it. Earlier V1/V2 proposals stay unrun and retained. This authorizes controls and one bounded comparison only, followed by fresh functional and original performance qualification for any later candidate. Original driver/oracles and acceptance remain unchanged.


The interrupted6de44 proof is now preserved in284 independently hash/CRC-verified immutable files (handoff SHA256 `4e5dcba6055b2a244d9cc5c98e26f9f64b782159e8776b05920d68656de4618a`). Actual caller-15 and absent caller/job terminals remain literal; separate readonly/guarded cleanup/independent absence0 do not turn it into success. No actor replay or private execution follows.


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

## 2026-10-14: legacy sorting and offline runtime-test prerequisites

The legacy /cluster/* sorting correction at fb960307 now passes a fresh build, native load, lint, fresh types,330 unit tests and eight HTTP integrations. Independent checks verify373 current source files,396 inputs,5382 compiled objects,40635 installed objects and closure of168 recorded process identities plus four exact container IDs/names; a later check verifies the nine reader/query identities closed. Its first ten-column browser run fails after six columns/twelve directions because the legacy Nodes page can match an earlier shared IP before the exact hostname. The failed run and independent cleanup remain retained; the minimal hostname-first correction at6718193 awaits a new331-unit/eight-integration build and the unchanged browser checks. The Node default-suite prerequisites now have144 exact-lock SRI-verified tarballs, an independently checked810-object offline cache and a twice-checked51,008-object retained build snapshot. These are preparation results; the unchanged default suite has not been rerun and the new runtime remains unqualified. See the [focused sorting receipt](../evidence/bortus-legacy-sort-focused-root-20261014.json) and [offline prerequisite receipt](../evidence/bortus-node22-offline-prerequisites-root-20261014.json). Original Gluster/Vault/Consul data and accepted backups remain preserved.

## 2026-10-14: Node runner guards and public volume proposal controls

Two offline controls pass against the actual corrected Node runner: a private700 workspace containing npm755 node_modules is inventoried correctly, while workspace/cache roots must remain700. Independent source and actor/suite closure checks pass. The continuation runner has started on a new copy; the default suite remains unqualified and the original V9 suite exit2 is preserved. The host has24 available CPUs and about14GiB free, sufficient for fixed Node2CPU/8GiB and app4CPU/4GiB functional checks; no performance timing is accepted from concurrent work. See the [runner guard receipt](../evidence/bortus-node22-continuation-guards-root-20261014.json).

Six pure controls pass for the ephemeral API whole-volume read-only mount proposal. An initial independent reader fails; a distinct stable-fingerprint reader and later closure pass. Root verifies70 archived members and68 original paths. These controls perform no API request or private-data release; actual admission and same-holder recovery remain unproven. See the [volume control receipt](../evidence/bortus-ephemeral-volume-controls-root-20261014.json). Original Gluster/Vault/Consul and accepted backups remain preserved.

## 2026-10-14: latest isolated qualification outcome

The [6718193 qualification receipt](../evidence/bortus-legacy-node-identity-qualified-root-20261014.json) records fresh build, native load, lint/types,331 unit tests and eight HTTP integrations, followed by all ten legacy sorting columns/twenty directions. Independent checks bind373 source files,401 functional inputs,5382 compiled and40635 installed objects;177 functional births and later nine reader/query births are absent. Browser checks bind35 inputs,77 Linux births absent and11 Windows births with no live recorded process, followed by separate later closure. The initial shared-IP lookup failure and subsequent four incorrectly encoded expected em dashes remain failed; the final attempt changes only those four expected codepoints with nine runtime files unchanged. Its frozen prose says330 tests, while actual executable gates/TAP require331+8. Root independently verifies all4849 originals against their69737176-byte CRC/SHA archive. This qualifies finite local functional/browser behavior only; actual assistive technology, performance, delivered image and adoption remain open.

The [public admission receipt](../evidence/bortus-public-admission-qualified-root-20261014.json) records one direct-TLS ephemeral-container PUT with dryRun=All returningHTTP200 against a fresh owned holder and immutable UID/resourceVersion intent. The whole proof volume is mounted read-only; all six API file flags point beneath its proof directory. Before/after persistent payloads and UID/RVs match. Independent reads verify244 current source files and415 original births absent. UID/fresh-RV cleanup naturally deletes Pod,ConfigMap,policy in order; a separate six-GET observer confirms every name/recorded UID absent, other6 Pods/1 ConfigMap/0 policies preserved, and88 cleanup/reader/query births absent. The source scanner literally exits1 with seven independently reviewed public findings: six checksums and one invalid public test PEM fixture; no suppression or green relabel occurs. No private password/backup material is released. This is current public admission proof, not private restore/API recovery acceptance; prior failed attempts remain failed.

The [Node continuation outcome](../evidence/bortus-node22-continuation-outcome-root-20261014.json) records offline documentation installation exit0 with279 exact-lock packages, then unchanged make -j2 test-only JOBS=2 exit2: two original cluster scripts time out after120seconds and the pending-DNS setServers test misses its expected exception. The version phase is not run. A live read-only sample binds114 zombies to the exact owned Python PID1; this establishes deficient orphan reaping, without retrospectively identifying the failed worker PIDs or proving the DNS cause. Independent outcome/custody checks exit0 with78 records, original51008-object workspace/physical fingerprint and810-object cache current,14 original births and exact CID/name absent; three later reader/query births are absent. The generic terminal SHA equals an older failure because its JSON bytes match; distinct started/phase/post records establish this execution. Runtime/security/image acceptance remains unproven. A separate bounded unchanged-script baseline/init and DNS observation is prepared; no suite skip, weakened oracle, performance replay or adoption is authorized by these results.

## 2026-10-14: recovery API mount integration

The migration source now integrates the exact API spec used by the [successful public admission dry-run](../evidence/bortus-public-admission-qualified-root-20261014.json). Only the ephemeral API mounts the complete proof volume read-only at `/memory-proof`; its six certificate/key/encryption file flags use `/memory-proof/proof/`. The ordinary init, utility and etcd mounts retain their existing writable subdirectory paths. Kubernetes forbids ephemeral-container `subPath`/`subPathExpr`; neither field is proposed. The matcher also permits only the literal empty `resources: {}` default on ephemeral containers; nonempty, null or mistyped resource objects remain rejected. This two-line matcher normalization was already present in the frozen diagnostic source, but absent from the migration repo. The integrated spec is byte-identical to that qualified diagnostic. Fifteen pure regression tests pass, including unsupported mounts, old file paths, writable access and resource-default drift. The added tests first fail against the old repo spec. See the [integration receipt](../evidence/bortus-api-volume-integration-root-20261014.json). No frozen old actor is repinned or rerun; a fresh private-recovery actor still needs current authorities and separate complete execution.

## 2026-10-14: Node init and DNS diagnosis

The [finite init/DNS diagnostic](../evidence/bortus-node22-init-dns-diagnostic-root-20261014.json) exits zero, followed by an independent zero-exit source/workspace/closure check. Both unchanged cluster scripts time out after 120 seconds with Python as PID 1, then both pass with the exact verified Docker init executable. In both cells the existing one-server DNS configuration yields ECONNREFUSED without the expected pending-query exception; a real reachable loopback sink receives one DNS datagram and preserves ERR_DNS_SET_SERVERS_FAILED until cancellation. Actual Node 22.23.3, OpenSSL 3.5.9 and module ABI 127 assertions pass. This supports a runner reaping and resolver-environment correction; it does not turn the failed original full suite into a pass. The selected direct-test environment differs from full-suite PATH/unused Git variables and uses new owned HOME/TMPDIR/NODE_TEST_DIR/TEST_SERIAL_ID scratch. Source, test bodies, original frozen 51008-object workspace/physical fingerprint, network-none and fixed 2CPU/8GiB/no-swap/512-PID limits stay intact. Independent checks verify 29 original host births absent and both exact created CIDs/names absent; five reader/query births and the saved later checker birth are also absent on the same boot. V1 stays unrun; the executed V1.1 adds directory fsync, held/revalidated actual-init executable/namespace FDs and independent deadline-protected socket cleanup. No original performance benchmark, private recovery, production rollout or data retirement occurs.

## 2026-10-14: standard resolver qualifies; full Node suite running

The [focused resolver receipt](../evidence/bortus-node22-local-resolver-root-20261014.json) records eight UDP/TCP protocol checks and an exit-zero unchanged upstream DNS test with both mustCall callbacks completed. The owned responder answers localhost A/AAAA immediately, local other types with NODATA and nonlocal queries with REFUSED; it does not forward or deliberately delay. Independent checks bind six sources, the original51008-object content/physical fingerprint,17 host births and exact container ID/name absence; three reader/query births and the later checker are also absent. The [new full-suite dispatch](../evidence/bortus-node22-init-resolver-dispatch-root-20261014.json) uses a fresh exact copy, unchanged make/test command and original oracles/environment, adding verified init and this private resolver. Offline documentation installation exits zero and the default test phase is running. Its source-enforced pre-create boot authority is explicit; the inherited started schema has no boot field. The original failed suite remains failed; this pending attempt grants no runtime, security, performance or deployment acceptance.

## 2026-10-14: private attempt fails before prompt; five resources independently removed

The [9df outcome receipt](../evidence/bortus-private-recovery-9df-outcome-root-20261014.json) preserves tool/outer/caller exit1 and stage6 ValueError before same-holder proof or password prompt. Both control creates are confirmed, but the retained wrapper does not identify the failing inner predicate. The sole registered -15 row is not a proved cause. No password or backup material was supplied. A separate cleanup exits zero after five UID/current-resourceVersion guarded, once-only deletes, with all three Pods absent before ConfigMap/policy deletion. A distinct observer exits zero after eight GETs, all five names/UIDs absent and1748 union host births absent; its own/eight query births are later absent. Six unrelated Pods and one ConfigMap remain. All247 source files are current. Default source scanning literally exits1 with four findings: three public source hashes and an invalid AAAA PEM fixture; each is reviewed without exclusions or scanner replay. Sixteen new input directories were restricted after their own byte/UID checks; original source permissions are unchanged. This proves cleanup, not private recovery, and authorizes no production/data retirement.

## 2026-10-14: legacy Nodes focused permission and inventory checks pass

The [focused candidate receipt](../evidence/bortus-legacy-node-permissions-focused-root-20261014.json) records11 passing actual TSX/useMutation/MutationTask model tests, fresh nonincremental types and affected-file lint. The correction gates controls/handlers with canonical fresh write/admin authority, uses encoded inventory IDs for PUT/DELETE, retains failed edit drafts with modal errors, and blocks mutations after inventory-read failure until explicit successful refresh. Model tests are distinct from DOM, session-polling and server authorization proof. Independent checks bind374 sources,386 inputs,40635 installed and5382 historical compiled-context objects;47 owned host births, all three exact CIDs/names and seven later reader/query births are absent. The initial reused preparer refuses a historical322-test count before workspace creation; a distinct preparation corrects only that count to the retained331-test authority. A new342-unit/eight-integration build and browser checks remain pending. No performance acceptance or production change occurs.

## 2026-10-14 18:19 UTC: read-only cluster metadata refresh

The [dated snapshot](../evidence/bortus-live-metadata-root-20261014-1819.json) shows3/3 Ready nodes,97 Pods,54/54 Bound PVCs and33/33 Ready active Helm releases. BORTUS remains Ready with zero restarts on its existing3b076fb9 image and suspended HelmRelease. The separate branconet-charts source and releases Kustomization are Ready at validated7828f5b5. All40 Longhorn volumes retain encryption and two replicas;30 are attached/healthy and10 detached/unknown. No Secret payloads are requested, and this snapshot does not qualify a new image, recovery procedure or deployment.

## 2026-10-14: committed Nodes correction full qualification passes

The [fresh6e2efbd full receipt](../evidence/bortus-legacy-node-permissions-full-root-20261014.json) records build/native load/lint/types,342 unit tests and eight HTTP integrations with all original commands and limits. Independent checks bind374 raw committed sources,399 inputs,5383 new compiled and40635 installed objects, all four standalone worker file bindings and the native module.190 host births and all four exact CIDs/names are absent; nine later reader/query births are also absent. This does not prove compiled middleware/handler SQL on the worker. The separate nine-case browser run fails at case4 after three accepted cases, with failed-outcome independent closure being prepared; no nine-case browser, performance or production acceptance is claimed.

## 2026-10-14: corrected full Node runner fails; originals and closure verified

The [literal runner outcome](../evidence/bortus-node22-init-resolver-outcome-root-20261014.json) preserves outer exit1, offline documentation install0, unchanged default suite2 and unrun final version phase. Its failure footer contains90 unique sequential tests; the earlier two cluster tests and pending-query DNS test are absent from that footer. Thread creation/resource refusals appear in the raw logs, but no particular exhausted limit or OpenSSL cause is proved. No limit, source/oracle or skip is changed. Independent post0 binds91 records, the frozen51008-object content/physical fingerprint,810 cache objects, ten current sources and the58210-object failed copy. Fifteen recorded host births and the exact CID/name are absent; three reader/query births are later absent. The reused generic failure-terminal SHA is not treated as run identity. No full-suite, new runtime/security or image acceptance is granted.

## 2026-10-14: public snapshot diagnostic identifies a failed guard and closes

The [b85 diagnostic receipt](../evidence/bortus-stage6-b85-diagnostic-root-20261014.json) preserves stage6/ValueError/exit1. Nine local recorder controls pass; the live trace captures the original need(ids==expected) at same-live-holder-gates.py253 as its first failed predicate,1369 events/23529 bytes within4096/64KiB. It does not retain the differing kind/field, nor prove the earlier9df cause. The first observed exception is separately labelled and is not a proved cause. Gate, graph, fullspec, UID/RV and sample rules remain unchanged; the caller physically ends before private prompting/material/restore. Independent pre-cleanup0 verifies current246 sources and public observations. Separate cleanup0 removes all five confirmed resources with UID/current-RV guards and typed Pod absence before ConfigMap/policy deletion. Independent eight-GET post0 verifies all names/UIDs absent,168 cleanup jobs and1243 union host births absent; nine reader/query births are later absent. No private or production recovery is accepted, and no original data is retired.

## 2026-10-14: failed Nodes browser workflow independently closed

The [literal failed-browser receipt](../evidence/bortus-legacy-node-permissions-browser-failure-root-20261014.json) preserves browser/server exit1, fixture child0, three completed checkpoints and24 network events ending in real PUT409. The failure is the first global alert-count assertion at browser.mjs123:10 after the modal alert was visible. Historical actual count/DOM were not retained. Installed Next source creates an additional clipped open-shadow role=alert route announcer; conflation is a grounded source inference rather than a recovered DOM fact. No all-nine workflow is qualified. Independent exact/Linux/Windows checks exit0, bind374 sources/35 inputs/5383 compiled/40635 installed objects, verify96 Linux births and exact CID/name absent, and ten Windows recorded births with no live process. Later Linux reader/two queries and Windows reader are closed. Success-only readers remain unrun. A new harness must distinguish framework announcements from exactly one owned modal error and preserve duplicate-application-alert checks; no product/performance/adoption change is made.

## 2026-10-14: retained Node thread-refusal evidence

The subsequent current-source/log review binds the996338-byte stdout and260-byte stderr to the independent Linux post records, verifies each public assertion snippet against both the frozen original and selected copy, and retains90 unique failed tests/30 Signal6 markers. The first failed test reports thread creation refused at src/node_platform.cc104; eight pthread_create/resource-unavailable messages and four uv_thread_create occurrences are retained. No contemporaneous pids/memory denial counters were captured, so the exhausted resource remains unproved. The next held proposal selects one unchanged first sequential test with bounded read-only counters and unchanged limits; no new diagnostic executes here.

## 2026-10-14: corrected finite legacy Nodes browser qualification passes

The [corrected browser receipt](../evidence/bortus-legacy-node-permissions-browser-qualified-root-20261014.json) records nine passing permission/inventory/error workflows and38 page request events against committed6e2efbd. Application/main/modal alert counts are checked separately from the pinned Next framework announcer. The two observed global/app counts are2/1 at the failed-edit modal and1/0 after pending authority withdrawal; the previous failed run remains failed with its historical count unknown. Product source and all nine business oracles are unchanged. Independent exact/Linux/Windows checks pass with374 sources,39 actual inputs,5383 compiled and40635 installed objects current;40 Linux births are absent and10 Windows births have no live recorded process. Later reader/query checks pass. The original preparation summary said35 inputs; its separate preserved metadata correction binds40 copies/39 inputs. The synthetic gateway503 proves the UI transport-error path, not a database outage. Fencing a late response cannot undo a server-accepted write. Actual assistive-technology, whole-UI, performance, runtime/image and production acceptance remain separate.

## 2026-10-14: unchanged first sequential test reaches the PID ceiling

The [single-test resource receipt](../evidence/bortus-node22-first-sequential-resource-root-20261014.json) retains actor1 and original driver1: zero passed/one failed, with the upstream120-second timeout, not the outer150-second cap. The same2CPU/8GiB/no-swap/PID512 container records61 numeric rows/3636bytes, sampled pids.current512 and35725 sticky pids.events:max denials. Every memory-event delta is zero; sampled memory.current peaks at1221668864bytes. Logs contain five pthread_create refusal tokens. These establish PID-limit denials in this new run, without retrospectively proving the cause of all90 earlier failures. No test, oracle, skip, affinity or NODE_OPTIONS changes. Independent post0 verifies the counters, seven current sources, frozen51008-object content/physical fingerprints,15 host births absent and exact CID/name absence; three later reader/query births are absent. A distinct same-test PID1024 source-only evaluation is being prepared with all other limits fixed. It grants no full-suite, runtime/image/security, performance or production acceptance.

## 2026-10-14: current compiled authorization worker ownership qualifies

The [current compiled ownership receipt](../evidence/bortus-legacy-node-compiled-ownership-root-20261014.json) verifies ten HTTP requests, twelve fresh worker SQL reads (five session/seven account projections), thirteen exact dispatch/operation/settlement joins and zero parent SQL calls. Current6e2 compiled middleware and handlers exercise role changes, session revocation, account deletion and schema outage with unchanged complete-response oracles. Independent exact/fresh/later checks pass:374 raw sources plus four generated extras,35 inputs,5383 compiled and40635 installed objects are current;19 recorded births and exact CID/name are absent, followed by three later reader/query births. This composes with the earlier full342+8 and nine-case browser qualification; it does not assert universal ownership or latency acceptance. V1 preparer exit1 at its Windows-UNC prerequisite is retained before workspace/actor creation. Distinct V2 corrects only canonical POSIX receipt paths and owner/input bindings. Its literal source default scan exits1 with one finding, independently traced to public container-name/prior-attempt status metadata; no suppression, exclusion or scanner replay occurs. Performance, runtime/security-image, private recovery and guarded live acceptance remain open.

## 2026-10-14: isolated PID1024 comparison passes; full suite remains open

The [same-test comparison](../evidence/bortus-node22-pid1024-comparison-root-20261014.json) changes only the diagnostic container PID ceiling from512 to1024, keeping2CPU/8GiB/no swap, the unchanged test/120-second driver and150-second phase. One test passes; all sticky PID/memory event deltas are zero. Three numeric rows/156bytes give sampled pids.current447 and memory.current741433344bytes; these sampled peaks are lower bounds. Independent post0 binds seven current sources, frozen51008-object content/physical fingerprint,17 host births absent and exact CID/name absence; three later reader/query births are absent. The earlier512 case stays failed with35725 PID-limit denials. A stale-pin first1024 source draft was caught before execution and remains unrun; the executed V2 has all direct executable pins verified. This supports a distinct full-suite runner preparation with PID1024; that full suite has not run. Original90-failure history and production resource limits are unchanged. No runtime/image/security or performance acceptance follows.

## 2026-10-14: snapshot equality recorder controls pass

[Five local projection controls](../evidence/bortus-snapshot-projection-controls-root-20261014.json) pass for the failure-only twelve-bit kind/identity-field equality recorder, including malformed-input refusal and the exact original snapshot guard context. Five source files remain current; original supervisor/suite coordinates are freshly absent. The six-source default scan exits0 without findings. These controls make no transport/API call, replace no guard, and do not identify the historical differing field or prove live/private recovery. A fresh public diagnostic remains separately held.

## 2026-10-14: snapshot diagnostic identifies Pod version drift; cleanup verified

The [6c public diagnostic receipt](../evidence/bortus-snapshot-6c-outcome-root-20261014.json) retains actor/caller1 at the original snapshot guard253. Its1147-event/19533-byte trace records twelve equality bits: only Pod resourceVersion differs; all name/namespace/UID fields and all ConfigMap/policy fields match. ExpectedPodRV is the first gate snapshot before later public setup, not the creation-journal RV. No writer/raw status delta or historicalb85/9df cause is proved. The guard is unchanged and no private branch is reachable.936 historical job rows include index883 exit-15; no role or all-zero claim is invented. Independent post0 verifies current246 sources and937 current-absent coordinates. Separate UID/current-RV cleanup0 removes the five confirmed resources once. Independent eight-GET post0 verifies all names/UIDs absent,172 cleanup jobs and1110 union coordinates absent; nine later reader/query coordinates are absent. A source-only candidate proposes one explicit public-staging checkpoint before real TCP proof, with strict version checks afterward; no live guard change or private acceptance follows.

## 2026-10-14: full PID1024 evaluation running; result pending

The [dispatch receipt](../evidence/bortus-node22-full-pid1024-dispatch-root-20261014.json) records actual root dispatch and a live PID/start/UID/boot witness. After the successful isolated comparison, this distinct runner changes the test-container PID ceiling to1024, keeps2CPU/8GiB/no swap and all original test commands/oracles/skips,10800-second lease/60-second closure and2400-second test bound. It uses a fresh copy of the frozen51008-object workspace and unchanged offline cache. Offline documentation installation exits0; upstream default tests have started. Actual completion is pending, not a full-suite/runtime/image/security pass. Production resource limits and the previous90-failure result remain unchanged.

## 2026-10-14: remaining five-column sort attempt fails at fixture resource lookup

The [literal A13 failure receipt](../evidence/bortus-a13-five-column-failure-root-20261014.json) retains server1/browser1. Deployments Restarts, Nodes Pods/Age and Namespaces Age complete eight directions with wire/display preconditions and unchanged complete row identity checks. Ingress stops at the six-row API length assertion; the failed body was not separately retained. Source and compiled command inspection identifies a fixture mismatch: it wrote `ingresses.json` while the app requests singular `ingress` and the fake CLI reads `ingress.json`. The whole five-column matrix remains unqualified; a separate source-only fixture correction keeps the browser and all ten expected observations byte-identical. Exact/Linux/Windows posts pass with374 source/39 inputs/5383 compiled/40635 dependency objects current,151 Linux births absent,10 Windows births with no live process and exact CID/name absent. Later reader/query checks pass. A root review-directory mode check failed after UNC creation; the exact reader inadvertently ran before root corrected0755/0644 to0700/0600 ahead of the fresh readers. This metadata error and the failed actor are retained. No application, benchmark, production image or cluster change follows.

## 2026-10-14: remaining five sort columns qualify

The [corrected five-column receipt](../evidence/bortus-a13-five-column-qualified-root-20261014.json) records server0/browser0, five columns/ten directions/five wire-display preconditions/eight successful page GETs. Only the fixture singular-ingress filename and comment change; browser and all ten expected observations are unchanged. Independent exact/Linux/Windows and later checks pass with374 sources/39 inputs/5383 compiled/40635 dependency objects current,33 Linux births absent,10 Windows births with no live recorded process and exact CID/name absent. Both default scans pass13 source and43 generated selections without findings. The prior failed attempt remains recorded. This closes these finite five columns, adding to the previously qualified count and raw-date subsets; it does not prove every UI route, assistive-technology, performance or delivered image.

## 2026-10-14: public checkpoint local controls pass

The [checkpoint controls receipt](../evidence/bortus-public-checkpoint-controls-root-20261014.json) records13 passing tests: nine actual-function controls and four unchanged API-transition regressions. It exercises one exclusive durable checkpoint after public setup, immutable creation journals, full-spec/runtime/source/metadata checks, fixed ConfigMap/policy versions, duplicate failure latching, postcommit identity/version refusal, private-before-proof refusal and the original network/API-transition oracles through scripted public I/O.188 current control sources and supervisor/suite absence are verified. Default scan literal1/one private-key finding is the exact unchanged malformedAAAA rejection fixture; unresolved0 with no suppression/exclusion/replay. A staging finalizer syntax refusal occurred before controls and was corrected in a separate metadata helper. These local controls do not instantiate live transport or prove live/private recovery; a separate public-only candidate packet is in source preparation.

## 2026-10-14: full unchanged Node upstream suite passes

The [full PID1024 qualification](../evidence/bortus-node22-full-pid1024-qualified-root-20261014.json) records actor0 and original default-test command0,4706 driver passes/zero failures, plus offline-doc-ci0 and new-version0. Node22.23.3/OpenSSL3.5.9/ABI127 retains ELF a7b77e9e,125362584bytes. Independent post0 verifies current10+6 sources, the original51008-object frozen content/physical fingerprints,810-object cache, archive/projection/tool authorities and six selected current-copy artifacts;16 recorded host births and exact CID/name are absent. Four later corrected-reader/query/failed-reader births are absent. The first post1 at267/178/5 retains a stale duplicate input hash; the distinct corrected reader changes only that hash to executed selected bytes and fresh source/owner, preserving all900/30 validation branches. Test2CPU/8GiB/no swap/PID1024, qualified init/local resolver,10800/60/2400 bounds and original commands/oracles/skips remain fixed. The old90-failure/PID512 results and production resource limits are unchanged. This passes upstream tests, not BORTUS application/native/TLS compatibility, final image/security or deployment acceptance.

## 2026-10-14: one public-only checkpoint qualification dispatched

The [843 dispatch receipt](../evidence/bortus-public-843-dispatch-root-20261014.json) records one actual600-second/no-TTY/no-input public diagnostic with the13-control-qualified checkpoint gate. The new246-source package preserves242 runtime rows and the183-row graph used by those controls; four necessary gate/composition/caller/outer sources change. Root verifies the closed255-row/256-member packet, exact actual-control receipts/current boot and exclusive247-file stage. Default scan literal1/four findings is independently classified as three unchanged public dependency hashes and the unchanged malformedAAAA fixture; unresolved0 without suppression or replay. The actor physically stops after public proof and cannot prompt/project/deliver private material. Actual completion and subsequent observed-UID cleanup remain pending; no proof, recovery, production guard/image or original-data retirement is accepted.

## 2026-10-14: public checkpoint diagnostic hits tracer bound; all five resources removed

The [843 outcome receipt](../evidence/bortus-public-843-outcome-root-20261014.json) preserves actor/caller1 after232seconds under the unchanged600-second lease. A1977-byte checkpoint is present with proved:false; no complete public proof/scoped result exists. The optional tracer reaches65524bytes/3701 valid events and refuses its next event at the original65536-byte ceiling; no closed summary/firstfalse is saved. Six partial TCP returns are retained (five positive/one blocked), not the complete seven-check proof. Caller finalizers2/5 and2356 jobs/ten shards are preserved without an all-zero claim. Independent eight-GET post0 verifies current246 sources and2357 current-absent coordinates. Separate cleanup0 uses the actual five UIDs/current versions, removes three Pods before ConfigMap/policy and uses no force/grace override/repeated DELETE. Independent eight-GET cleanup post0 verifies all five names/UIDs absent,172 cleanup jobs and2530 union coordinates absent; both pre/post later reader/query groups of nine are absent. The source default scan retains four exact previously reviewed public findings; the three cleanup sources scan0 without findings. No live/private recovery, production guard/image change or original-data retirement is accepted. A distinct source-only functional qualification will omit optional numeric tracing while retaining the same checkpoint gate, full source/CNI/spec/version guards, actual network oracles and600-second limits. The original diagnostic and its64KiB/4096-event bounds remain unchanged.

## 2026-10-14: failed diagnostic checkpoint metadata corresponds to immutable journals

The [843 receipt](../evidence/bortus-public-843-outcome-root-20261014.json) now includes a separate outcome-honest metadata reader0. It verifies current246 source rows and the retained unproved checkpoint against original creation identities/versions, creation-fixed ConfigMap/policy versions, proposal digests, source bindings, original raw journal SHA and two control journals/recorded observer identities. The literal actor1 and complete-public-proof:false remain unchanged. The reader makes zero API calls/children; its source passes the default scan without findings and its own birth is freshly absent. Its IP evidence is the canonical recorded IPv4 plus pinned gate sampling semantics; original GET bodies did not retain a second independent IP observation. Metadata correspondence does not establish live CNI enforcement or private-material authority. All five temporary resources remain independently confirmed absent.

## 2026-10-14: public functional checkpoint fails; exact cleanup verified

The [145 outcome receipt](../evidence/bortus-public-145-outcome-root-20261014.json) retains the uninstrumented public actor1 after112.88seconds under its original600-second lease. The checkpoint remains unproved; the exact refusing predicate is unknown. There is no complete public proof or private continuation, and no guard or network oracle was weakened. Before-cleanup observer0 confirms current246 sources and1561 absent coordinates. Exact-UID cleanup0 removes the three Pods before ConfigMap/policy, with184 complete cleanup jobs. The first cleanup observer1 stops before API queries because it expects the old numeric-diagnostic mode. A distinct observer corrects only that literal and its two exclusive coordinates; all helpers and original30-second/eight-GET bounds remain unchanged. Corrected observer0 confirms all five names/UIDs absent,1746 union coordinates absent and current246 runtime/two cleanup sources; a later check confirms its own birth and eight query births absent. The failed observer and original actor remain recorded. Production, private recovery, originals and backups are unchanged. Failure-only bounded context collection and new-ELF ABI checks remain separate work.

## 2026-10-14: bounded context identifies the current public guard failure

The [c7 outcome receipt](../evidence/bortus-public-c7-outcome-root-20261014.json) retains public actor1 after116.42seconds under the unchanged600-second budget, with an unproved checkpoint and no private continuation. The tested failure-only recorder writes687bytes within its4KiB bound and records the actual exception chain: gate snapshot line274 is called by the pre-exec fence of the cross-control connector list. Only the holder Pod resourceVersion differs; the other eleven identity fields match. This does not identify the list iteration, writer/status delta or causes of earlier attempts. No guard, oracle or checkpoint refresh was introduced. Independent pre-cleanup observer0 verifies current246 sources/1621 absent coordinates and the bounded context. Exact-UID cleanup0 removes all five resources using183 complete cleanup jobs; independent eight-GET post0 verifies all five names/UIDs absent,1805 union coordinates absent and current246/two cleanup sources. Both later reader/query groups of nine are absent. Source scan retains the same four exact public findings with unresolved0; cleanup three-source scan0 has no findings. Production and original data are unchanged; private recovery remains unproved.


## 2026-10-15: compiled bookkeeping checks and isolated evaluation snapshot

The [compiled fixture](../evidence/bortus-account-bookkeeping-compiled-root-20261015.json) passes all ten HTTP checks, twelve fresh SQL reads and thirteen recomputed numeric joins with the original five/seven-column expectations. Independent, fresh, later and final reader-absence checks pass for 374 sources, four extras, 35 inputs, 5,383 compiled objects and 40,635 dependency objects. Nineteen actor/post births and three later reader/query births are absent. Original 300/60-second lifecycle, 180/150-second stage/child bounds and 2CPU/1GiB/no-network limits remain unchanged. This qualifies the compiled fixture only.

The [separate Git snapshot](../evidence/bortus-account-bookkeeping-snapshot-root-20261015.json) has the exact qualified base as parent and changes only the bookkeeping core. Root independently rechecks all 374 raw Git blobs, sizes and modes against the candidate manifest. The separate index and commit-tree operation updates no ref, owning index, branch or worktree; job closure is verified. The original helper proof remains unchanged, with root review recorded separately. This is an evaluation commit, not product adoption. The original three-pair performance comparison remains required; its prior failure is unchanged.


## 2026-10-15: recovery prompt input failure; exact cleanup complete

The [DFE recovery attempt and cleanup](../evidence/bortus-private-dfe-failure-cleanup-root-20261015.json) preserves actual tool1, caller stage7/type1 and the absent durable outer terminal at the original 600-second deadline. Same-holder proof, the matched independent prompt observer and a fresh foreground/echo-off check pass. The launch did not keep tool stdin open, so credential delivery is rejected before input is delivered. Two earlier supplemental tcgetpgrp checks return ENOTTY; the matched observer remains independently successful. No credential delivery, private recovery, restore or API oracle acceptance is claimed. No deadline is extended and the failed actor is not restarted.

All 4,542 registered jobs are typed, reaped and absent: 4,541 exit0 and one exit1. Its ordinal does not identify a command or cause. Separate exact-UID/fresh-resourceVersion cleanup passes, deleting three Pods before ConfigMap/policy without force, grace override or repeated DELETE. All187 cleanup jobs exit0 and are reaped/absent. An independent eight-GET observer confirms all five names/UIDs absent. The no-child later check verifies47 public records,247 runtime sources plus manifest,11 staged cleanup/observer files,4,731 actor/cleanup births and both nine-birth observer/query groups absent; its own reader is subsequently absent. Default source scans pass11 cleanup/observer and five later files. A root owner-discovery StopIteration is retained and corrected from the actual source before the final read, without replay. Original stores, backups and production remain unchanged.


## 2026-10-15: bookkeeping comparison completes; warm performance gate remains failed

The [unchanged three-pair comparison](../evidence/bortus-account-bookkeeping-paired-root-20261015.json) completes both builds and six observations with runner, supervisor and root exit0. All six original profiles, fixture/oracle checks, alternating order, delays, resource limits and samples remain unchanged. The original pure summary is recomputed independently. Exact/fresh checks verify66 frozen inputs and439 exported sources (282 candidate/157 baseline),11 recorded births absent and all eight exact container names absent. No container IDs were retained, and dispatcher absence remains PID-only because its original start ticks were not captured. The no-child later check verifies81 current pins and nine post-reader/query births absent; its own reader is subsequently absent. All source, staged-source and observer default scans pass without findings. An unrun postcheck draft shadows its added self-identity variable with the original query variable; only the added name is corrected before staging/execution. No workload is replayed.

Two of ten warm HTTP p95 median comparisons regress: small serial10.937845 to14.668675ms, and1,000-Pod concurrent67.699072 to71.921427ms. The other eight improve. These are medians of three per-run nearest-rank p95 values; no observation is trimmed and no tolerance changes. All105 comparable latency/workflow/CPU median increases across the full summary remain in the receipt, including non-warm phases. Whole-fixture CPU median falls32.412640 to28.173989seconds, while peak memory rises363.066406 to424.125000MiB; no OOM or throttling is observed. These include fixture/driver work and do not isolate application CPU or memory. Baseline incomplete10,000-Pod results and differing Services-after-Pods semantics remain noncomparative.

The original no-warm-regression gate remains failed. The evaluation snapshot is not adopted or deployed; original production/data/Flux guards remain unchanged. Small serial workflow and whole-phase cgroup CPU are higher in all three candidate runs, with zero CLI/native calls. These do not establish higher server CPU or repeated setup; the later CPU attribution section corrects that interpretation. A07/A21, image/security, current recovery and guarded live acceptance remain open. The overall goal is active with no user action pending. Separately, one harmless public getpass probe with tool tty=true succeeds; it fixes the input-channel configuration, but supplies no future same-holder, credential-delivery or recovery proof. The distinct recovery profile remains source-only and unrun.


## 2026-10-15: fresh interactive recovery dispatch

The [fresh831 dispatch](../evidence/bortus-private831-interactive-dispatch-root-20261015.json) starts once with the corrected interactive tool channel after a successful harmless public probe. All247 runtime leaves plus manifest are independently normalized to the prior qualified source: only new run/control coordinates and dependent pins differ. Existing500-file native metadata capture, closed299-file/300-member packet, original guards, source modes/ownership/current boot and original600-second lease remain. The default301-file scan retains the same four exact public checksum/malformed rejection-fixture findings, all independently matched to unchanged qualified bytes, with no suppression or replay. This historical dispatch receipt precedes the completed failed attempt; the later recovery831 outcome and cleanup section records actual credential delivery, failure and resource absence. Previous failed attempts and their cleanup evidence remain preserved. Production and original stores/backups are unchanged.


## 2026-10-15: interactive recovery831 fails; exact cleanup verified

The [recovery outcome and cleanup](../evidence/bortus-private831-failure-cleanup-root-20261015.json) retain tool/outer/caller exit1 after491.318 seconds under the original600-second limit. Same-holder and independent prompt checks pass, and authorized input is actually delivered through the verified foreground, echo-off channel. Private inputs may have been read. Material validation stops at stage8/type2, with no optional material note; no exact inner cause, restore, API startup or recovered Secret-map acceptance is claimed. All6,854 registered jobs are typed/reaped/absent:6,853 exit0 and one exit1; its ordinal does not identify the command.

Separate exact-UID cleanup0 removes only the three Pods, ConfigMap and policy, with186 jobs all0/reaped/absent. Eight independent GETs verify all five names/UIDs absent. The first final verifier remains exit1 due to three stale checksum constants; a separate corrected verifier keeps all14 function bodies and guards unchanged and returns0. Final closure verifies57 public records,247 original runtime leaves plus manifest,11 staged sources,7,042 actor/cleanup births and both nine-birth observer/query groups absent, followed by its own reader absence. Original data/backups remain preserved. A failure-only caller diagnostic is being qualified locally before another private attempt; recovery remains open.


## 2026-10-15: CPU attribution corrected before further profiling

The [retained timing and source review](../evidence/bortus-account-smallserial-attribution-root-20261015.json) distinguishes whole-phase cgroup CPU from server CPU. At the actual100Hz process clock, server phase CPU medians are60ms for both baseline and candidate; the higher whole-phase CPU cannot establish a persistent server CPU regression. The phase includes client oracle/sampling work. Projection/serialization are already cached, all prior authorization/cold requests are awaited, and repeated startup is not established as the cause. The original two warm benchmark regressions remain failed. New diagnostic/helper checks and bounded causal profiling are separate from performance acceptance; no candidate is adopted.


## 2026-10-15: focused diagnostic controls qualify

The [two new local suites](../evidence/bortus-focused-diagnostic-controls-root-20261015.json) pass six caller-boundary cases and five profiling-helper cases, followed by independent, later and final reader-absence checks. Caller capture runs only after a failed material operation lacking an existing producer note; it preserves the original refusal/cleanup and emits at most one optional4KiB numeric record. No normal-path instrumentation or private recovery acceptance is introduced. The five helper cases exercise actual thread-CPU counters, forwarding, bounds and sample partitions in a separate restricted container. Its application/compiled/dependency inventories are explicitly empty; no compiled app or performance qualification is claimed. All16 recorded test births and the exact container ID/name are absent. Eighty-seven source/output pins and three observer/query births remain current/absent, followed by the final reader. Old test suites and the original benchmark are not replayed. Actual forwarding adapters and measured application graphs remain unqualified.


## 2026-10-15: PCRE2 evaluation commands pass; final validation refuses

The [isolated build attempt](../evidence/bortus-pcre2-evaluation-build-failure-root-20261015.json) returns wrapper1 despite successful regeneration, configure, compilation, original upstream check and DESTDIR installation. The upstream summary reports4pass/0skip/0fail/0error; POSIX macro warnings are retained. Final worker validation refuses at stage6 after publishing the staged manifest, without a build result or first-exception context. The exact cause remains unproved. The original900-second limit and resource/ownership guards remain. Independent, later and final reader-absence checks pass, preserving actor1. All five original sources, two post sources,98actor records,11post records, the unchanged445-file/10-directory source and staged manifest are current. Fifteen original host identities plus the observer/two query identities are absent; the exact container ID/name are absent, followed by the final reader. Five phase identities belong to the removed container namespace and are not compared against host PIDs. No Noble binary equivalence, consumer compatibility, image or security acceptance follows from these phase successes.


## 2026-10-15: forwarding adapters and measured graphs verified

The [profiling preconditions](../evidence/bortus-smallserial-profile-preconditions-root-20261015.json) qualify two new adapter groups: the actual retained OpenTelemetry API with HTTP forwarding, and a real Node Worker with14 read/settled forwards and28 real Immediate callbacks. Independent/fresh/later/final reader checks pass, all16 recorded births and the exact container ID/name are absent, and91 pins remain current. These are diagnostic forwarding checks, not app authorization or SQL acceptance.

A separate read-only capture hashes78,949 actual baseline/candidate files (2,149,448,901 bytes) across eight measured graphs. Root independently verifies the capture SHA under a held descriptor, exact graph name sets, every physical fingerprint, the absent baseline runtime/native directories and capture birth absence. This preserves the original byte bindings through stable physical identity; it does not claim another full content rehash. No app module, profiler workload or new benchmark executes. One bounded diagnostic observation per lane remains next, after final source review; the original performance gate remains failed.


A separate read-only [current-predicate witness](../evidence/bortus-pcre2-evaluation-build-failure-root-20261015.json) returns0 with final reader absence. The unchanged inventory rejects build/src/pcre2_chartables.c because it is an absolute symlink to the fresh copy at /output/pcre2-source/pcre2-10.42/src/pcre2_chartables.c.dist. It refuses before resolving the target, so no external target-content read or outside-root result is claimed. This explains the current predicate refusal, not the original unrecorded exception. The failed build result is retained; qualification of the already-staged libraries and their consumers remains next, with no unchanged build replay.


## 2026-10-15: retained static ABI passes; diagnostic profile refuses

The [retained-stage static ABI inspection](../evidence/bortus-pcre2-retained-stage-static-abi-root-20261015.json) passes actor, independent, later and final reader checks. Nine ELF subjects have no missing selected versions, strong symbols or direct PCRE imports, no removed baseline exports and no RPATH; 18 unresolved weak symbols remain explicit. The unchanged source455/stage239 objects and source/record bindings verify, and recorded host births and the exact container ID/name are absent. The original build wrapper remains exit1 despite its five successful phase commands. This is static evidence only: canonical-loader consumer execution, Noble binary equivalence, replacement image and A20 security acceptance remain open.

The [diagnostic profile](../evidence/bortus-smallserial-profile-failure-root-20261015.json) returns actual1. The baseline completes14 requests, but the candidate fails its first session request with HTTP500 before warm phases; no complete comparison is claimed. The controller reports final container removal, all CLI identities absent and current measured graphs. Three observer refusals remain retained: a success-only cleanup field, a historical reader record with mode0644 and an argument-dispatch error before query creation. The corrected exact reader and fresh reader pass, verifying125 pins, all eight measured graphs,27 absent host births and the absent exact container ID/name. The later reader and final root check also pass, with148 current pins and31 host births freshly absent, including the later reader. No actor or workload is replayed. Exact Node startup source shows inherited preload runs before the Worker script path is inserted into argv; the earlier eval-Worker adapter never covered that boundary. A new real file-Worker control must qualify before changed instrumentation runs. Private raw profiles stay outside Git. A07/A21 remain failed/open; no candidate is adopted.


## 2026-10-15: finite consumer dependency predicate refuses

The [finite consumer evaluation](../evidence/bortus-pcre2-consumer-runtime-failure-root-20261015.json) returns actual1 at stage4/type5 after three literal-zero jobs: tiny public harness compilation, harness ELF inspection and the baseline grep loader listing. Worker finalizers are empty and the controller reports container removal; independent, later and final root checks pass, with25 host births freshly absent and the generated harness/current455+239 objects verified. The retained grep listing contains only PCRE2-8, libc and the canonical loader, while the shared checker incorrectly also requires libselinux. This is a current source/output mismatch, not a recorded original internal assertion. Correct each consumer dependency set without admitting extra or host-fallback modules. No complete corpus, replacement-image or security acceptance follows; the original PCRE build1 and18 explicit weak symbols remain.


## 2026-10-15: affected CI checks pass; preload composition controls pass

The [affected read-only CI phase](../evidence/bortus-a19-readonly-ci-checks-root-20261015.json) passes lint, semantic type checking and all342 unchanged unit tests, with zero failures/skips/cancellations. The source fix replaces `npm test` in that read-only phase with `node --import tsx --test tests/*.test.ts`; unconditional worker generation remains in the prior writable build. This run uses a fresh374-file source copy and four qualified generated artifacts with existing dependencies/compiled output mounted read-only, under the original4CPU/4GiB limits. It proves the revised check command, not a fresh install/build, eight integrations, per-regression negative controls, hosted CI or deployment. Exact/fresh/later/final checks pass, with965 current pins and59 host births freshly absent. The owning commit is `9fbd85f` (workflow plus11 docs); root independently verifies all12 committed raw blobs and unchanged frontend tree. Hosted CI remains unproved. Four default scanner findings are exact pinned public Node header checksums; the literal scanner1 is retained with zero unresolved findings and no suppression/replay.

The [new preload composition controls](../evidence/bortus-worker-preload-composition-controls-root-20261015.json) pass all six finite groups: four actual file Workers with default inherited require arguments, forwarding/error identity checks, and actual MessagePort listener restoration with precise wrong-tuple refusal. The helper validates the script path/hash at the first public message-listener registration; the adapter declares its exact later restoration tuple separately. This proves diagnostic composition only, not prevention of earlier script execution, application/SQLite behavior or performance. Exact/fresh/later/final checks pass, with93 current pins and20 host births freshly absent. The separately qualified corrected profile now completes; the old profile failure and original benchmark regressions remain.


## 2026-10-15: corrected consumer runtime corpus passes

The [corrected retained-harness consumer run](../evidence/bortus-pcre2-retained-harness-consumer-root-20261015.json) passes all14 bounded jobs and matches baseline/candidate outputs for10 public corpus cases. Exact loaded-component sets verify separately for grep and libselinux; missing, extra and host-fallback modules still refuse. It reuses the qualified compiled harness without any compiler/readelf replay. The original runtime1 and PCRE build1 remain retained, with18 unresolved weak symbols explicit. The corrected independent, later and final checks pass, verifying149 actor records, the retained harness/current455+239 objects and27 host births freshly absent. The first independent reader1 retains a stale container-name literal and starts no query; its distinct correction preserves the original checks. This proves the selected runtime compatibility cases, not serialized SELinux databases, kernel policy, application/image or A20 security acceptance; all ten existing scanner findings remain until a separately assessed replacement image and precise residual evidence.


## 2026-10-15: corrected diagnostic observation completes

The [dual-lane observation](../evidence/bortus-smallserial-profile-v2-root-20261015.json) completes14 HTTP200 requests per lane and14 actual candidate account reads with28 real yields. Independent numeric reparse matches every published projection, verifies the exact listener-restoration proof,133 current pins,26 absent host births and the absent exact container ID/name; later/final checks also pass, with153 current pins and30 host births freshly absent, including the later reader. Raw profiles, names and URLs stay private. Warm samples are sparse (largest active leaf only2 samples), and the baseline lacks middleware association, so this does not establish a dominant source cause or equivalent middleware comparison. Instrumented thread counters and nested intervals are diagnostic only; they are not additive CPU shares or an original benchmark pass. The two warm regressions remain open; application and production are unchanged.


## 2026-10-15: system8 image preparation stops before build

The [COPY-only image attempt](../evidence/bortus-pcre2-system8-image-prebuild-refusal-root-20261015.json) refuses at stage20/type5: its added baseline image inspect returns1 because that exact saved raw-config digest is not found as a daemon-local image ID. This does not establish that the earlier Docker image identity or saved export is absent. No build or container starts. The retained raw components and exported31794-object filesystem remain the authority; a fresh source correction will remove only that unnecessary daemon-lookup requirement because this producer reconstructs FROM scratch. The planned output changes one PCRE8 payload and adds explicit provenance while requiring all31793 other existing objects unchanged. Full output/runtime/default scan and precise residual assessment remain pending; all ten original scanner findings remain visible.


## 2026-10-15: corrected system8 image assembles locally

The [fresh COPY-only producer](../evidence/bortus-pcre2-system8-image-assembly-root-20261015.json) completes all four Docker jobs with actual0 under the original300-second bound. It reconstructs the qualified current6e application/Node components and adds only the selected system PCRE8 payload and explicit public provenance. The inspected local Docker identity is681de2d3; its OCI index/leaf/raw-config relationship is not yet qualified. Independent actor closure, saved export/descriptor chain, exact31795-object filesystem comparison, fresh runtime and default security scan remain pending. No container or production workload starts in this assembly. All ten previous scanner findings and the failed first lookup remain retained; no security exception or deployment follows.


## 2026-10-15: current cluster and boot-aware image closure

The [read-only live snapshot](../evidence/bortus-live-cluster-metadata-root-20261015.json) verifies3 Ready nodes,54 Bound PVCs,91 Running/Ready Pods and6 completed Pods, with no other phases. All33 active Helm releases and chart/Flux reconciliation are Ready. BORTUS remains suspended and serves the previous3b076fb9 image. Longhorn has40 encrypted two-replica volumes:30 attached/healthy and10 detached/unknown; detached status is retained, not promoted to healthy. These metadata checks do not prove application recovery or upgrade acceptance.

The [image assembly closure](../evidence/bortus-pcre2-system8-image-assembly-root-20261015.json) now passes independent and final root checks for9 source files,26 actor records and3 owned payload files. WSL restarted between assembly and observation; the first observer1 created no owner. The corrected reader binds current boot19d54e89 and original boot7fbd3ead explicitly, records five original births in the different boot, and never compares their PID/start tuples with current processes. The current reader is freshly absent. The first export source refuses before owner/CLI/save because one input row incorrectly expects0600 for the original qualified0644 status file. That file is unchanged; only a fresh binding correction is allowed. Saved export/fullFS/runtime/security qualification remains pending.


## 2026-10-15: fresh image export completes

The [corrected export](../evidence/bortus-pcre2-system8-export-root-20261015.json) returns actual0 for all three inspect/save/inspect jobs. Its278025216-byte archive hashes to f9f5c926 and binds15 ordered layer digests to the actual saved Linux/amd64 manifest4f8cfddc and raw configf67ca934. The local Docker identity681de2d3 is recorded separately. Registry publication, attestation semantics, complete filesystem reconstruction, fresh runtime and security acceptance remain unproved. The first matched post draft is held unrun after source review finds it must also pin the staged manifest; its fresh correction preserves the archive/parser guards. No application or production workload changes.


## 2026-10-15: complete system8 filesystem equation passes

The [new ordered-layer reconstruction](../evidence/bortus-pcre2-system8-fullfs-root-20261015.json) returns actual0 and compares all31795 entries with the expected inventory. Root separately compares the entire saved baseline plus declared delta: one PCRE8 payload replacement, one public provenance addition,31793 unchanged old entries and no removed paths. Alias, parent metadata, package-origin status and Chisel visibility remain exact. Inventory3530793c binds15 layers and937737229 expanded regular bytes without extracting files onto the host. The independent export chain and final current-boot reader absence pass; native held-descriptor/fullFS closure also passes, with all3 source files/5 actor records current, the archive hash/fingerprint current and both the original fullFS process and independent reader freshly absent. This proves the filesystem equation, not fresh runtime, default security scan, residual acceptance, performance or live delivery.

## 2026-10-15: system8 runtime passes; default image findings remain

The [exact-image runtime receipt](../evidence/bortus-pcre2-system8-runtime-root-20261015.json) records actual0 for the unchanged native selector, Prisma migrations/query, real entrypoint and loopback HTTP/login/session/fresh-role checks under the original2CPU/1GiB/no-swap/PID256 limits. Independent closure verifies all5 actor sources including the manifest,81 records,21 absent host births and exact container ID/name absence; root then verifies current held-file hashes/fingerprints and the absent reader/two query births. This finite fixture does not qualify the Kubernetes TLS Secret transport, performance or live upgrade.

The [fresh default scan](../evidence/bortus-pcre2-system8-security-scan-root-20261015.json) retains literal scanner1:10 Medium findings, no secrets and no reported fixed versions. Its new DB was updated2026-10-15T07:10Z. Independent and final root checks preserve the actual report/cache/source hashes and absent scanner/reader births without rerunning the scan. The unchanged package-origin records still identify seven PCRE, two libc and one zlib finding. The PCRE payload has changed with explicit provenance; each CVE still needs its precise source-to-payload/residual mapping. The overlay supplies no libc/zlib fix. No exception, scanner-zero, security acceptance or deployment is claimed.

The [first A02 executable attempt](../evidence/bortus-a02-deleted-cookie-source-review-root-20261015.json) retains actual1 after124 protected API401 assertions. The first protected page returns307, then its exact Location assertion refuses, so zero pages and no complete160-call matrix are accepted. Installed Next code canonicalizes loopback127 URLs to localhost before middleware; a narrow fixture-origin correction is being prepared, retaining exact307/same-origin/welcome and all other oracles. The historical Location was not retained and cannot be reconstructed as an observed value. No production source or data changes.

## 2026-10-15: seven PCRE source rows mapped to the actual image

The [row mapping](../evidence/bortus-pcre2-system8-seven-row-coverage-root-20261015.json) joins each of the seven actual PCRE findings to its official fix/maintained commit and the combined23 replacement blobs. Root rereads all23 current bodies, verifies SHA256/Git blob identities and their original qualified composition records, and reviews the12-code-file diff. Consolidated10.42 JIT files are included where mainline path names differ; a filename intersection alone is insufficient. The selected a731 payload, f9f5 archive, full filesystem and finite runtime/closure are bound explicitly. This preserves the original build-wrapper1,18 unresolved weak symbols, and the absence of per-CVE exploit/sanitizer/32-bit proof. The proposed review expiry has not been accepted; the default scanner still exits1 and libc/zlib remain separate open rows.

## 2026-10-15: second A02 redirect-format refusal retained

The localhost-only fixture correction also returns1 after the same124 API401 checks and first page307; it does not resolve the exact Location assertion and accepts no pages. The first failure is independently closed, including858 current pins/22 absent host births. Its later reader1 is retained as a Windows/native name-order mismatch with exactly the same19 names; root's combined native final check verifies the unchanged names, bytes and births. The second attempt's independent closure is pending.

Installed Next router code (`resolve-routes.js:450–465`, `relativize-url.js:27–37`) converts same-origin middleware redirect destinations to relative URLs for ordinary HTTP requests. A fresh fixture correction will allow only exact `/welcome` or exact absolute base-origin `/welcome`, with explicit resolved-origin/path/empty-query/empty-fragment checks and bounded Boolean diagnostics. This matches the original same-origin destination requirement; arbitrary relative paths and external redirects remain rejected. The historical unretained headers remain unknown. Both failed attempts and all other160-call oracles remain preserved in the [A02 receipt](../evidence/bortus-a02-deleted-cookie-source-review-root-20261015.json).

## 2026-10-15: compiled issued-cookie deletion matrix completes

The [corrected160-call fixture](../evidence/bortus-a02-issued-deleted-compiled-root-20261015.json) returns actual0: four real login/session/setup calls,124 protected API401 assertions and32 protected page307 assertions. The first-page Boolean diagnostic observes exact relative `/welcome`, which resolves to the required same origin and path with no query/fragment; redirects are never followed. Both earlier absolute-only fixture failures remain retained and closed. The same actual unexpired cookie, signing key, role and sessionVersion are preserved until exact victim deletion. All other table rows/schema and the writer anchor remain unchanged; postwithdrawal main-thread CLI/native HTTPS admission counters are zero and final observer publication succeeds. Original resources,160 requests and remaining assertions stay fixed. Independent completion/current-file/process closure is pending. This is local compiled route evidence, not A05 authorized mutations, a performance pass or production/live adoption.

## 2026-10-15: deletion matrix independently closed; next UI boundary identified

Independent and final root checks now qualify the [current compiled160-call deletion matrix](../evidence/bortus-a02-issued-deleted-compiled-root-20261015.json):856 current original pins,19 completed-post files,23 absent host births and exact container ID/name absence. File hashes and full fingerprints match before/after; original resources and historical failures remain retained. This closes the finite issued-cookie/deleted-account breadth gate; the other original A02 retests and delivered/live acceptance are not inferred.

The [A05 source follow-up](../evidence/bortus-a05-current6e-source-followup-root-20261015.json) verifies11 current files/Git blobs. Shared child-error controls already cover nonzero output/timeout/missing/redaction and need no replay. The remaining focused UI seam is one actual successful and one failed harmless terminal command through the current route. Separately, overview Clear inventory sets an error but omits the existing confirmation dialog error prop; a narrow application fix is delegated to the owning checkout. That source defect has not been runtime reproduced, and no new application source, build or live acceptance is claimed in this checkpoint.

## 2026-10-15: current dialog source and hosted CI

Owning source `ea628d2` forwards the existing overview inventory error to its confirmation dialog. The [fresh isolated full run](../evidence/bortus-overview-inventory-fresh-root-20261015.json) passes build/native load/lint/types,342 units and eight integrations with independent verification of374 source files,5383 compiled objects,40635 installed objects and complete container/process closure. Earlier6e image/browser evidence remains bound to its original source. The [four finite real terminal and inventory-error/retry browser checks](../evidence/bortus-overview-terminal-four-browser-root-20261015.json) now pass with independent cleanup.

The [hosted validation run](../evidence/bortus-hosted-ci-exact-app-root-20261015.json) passes a clean locked install/build and the original checks/integrations for the exact complete frontend tree on `codex/bortus-hosted-ci-ea628d`. The branch has verified main as its sole parent and adds no qualification archives or development history. Its source and actual CI log pass default secret scans without suppression. It changes neither main nor Flux/image delivery. Original performance, final release image/security, recovery and live acceptance gates remain open; original data is preserved.

The successful hosted install reports9 npm vulnerabilities (2 Moderate,7 High). This is separate from the ten Medium image-package findings. Full and production-only audit records are required before dependency remediation or security acceptance; the successful CI job is not an audit pass.

## 2026-10-15: terminal harness failure retained and retry qualified

The [terminal failure/retry receipt](../evidence/bortus-terminal-failure-retry-root-20261015.json) records browser1/server1 with zero completed business checks: a Windows atomic process-record rename returned WinError5. The failure cause is unknown. Exact/fresh independent checks verify source/dependency/compiled stability,32 Linux births absent,10 Windows recorded births not live and exact container name/ID absent; final reader closure passes. A normal fixture child exit0 is not a browser pass.

Five focused actual-function controls qualify a fixture-only atomic rename retry: WinError5 only, five attempts maximum,500ms scheduling window within the existing lease, unchanged fsync/temp/atomic replacement and all ownership predicates. Nonmatching errors, expiry and exhaustion still fail. No hard500ms syscall duration is claimed. The first control wrapper failed on a faulty chained-comparison assertion and did not persist the child exit; its5OK output and separate absence check are retained. A distinct corrected wrapper persists actual0 before acceptance, passes5/no skips and verifies child reaping/absence. The later four-case terminal/dialog run passes against the fresh application build, as recorded below; the original failure stays unchanged and production is unchanged.

Current result: the [four-case browser qualification](../evidence/bortus-overview-terminal-four-browser-root-20261015.json) passes actual public terminal200/502 and inventory500/200 with redaction, retained input, full transaction rollback, in-dialog error and unchanged keeper rows. All three independent readers and final reader/process/container closure pass. The preceding premature root launch is a retained failed harness attempt with no browser child, independently closed; it is not a product failure or passing check.

The [actual full/production npm audits and scoped residual](../evidence/bortus-npm-audit-build-residual-root-20261015.json) now qualify: full1 retains9 development-package rows; production-only0 has zero findings. The trusted-build-only exception expires2026-10-22. It does not clear system-package findings or opaque/final-image packaging, and the full audit remains1. No dependency override, major update, live promotion or original acceptance-clause change follows.

## 2026-10-15: Flux argument-order failure isolated

The [additional real-API probe receipt](../evidence/bortus-a04-flux-order-probes-root-20261015.json) retains the separate remainder failure: eight cases complete, then Flux hierarchy returns502. With the same real CLI/API/config and duplicate JSON flags, leading `--all-namespaces` exits1 while moving only that flag after `get helmreleases` exits0 with a valid empty list. The withheld63-byte error text is not characterized. Independent checks verify290 actor records, current source/build/dependencies,57 original and11 post/query identities absent, all five IDs/names absent and final reader closure. Individual probe PID identities were not recorded; their containment evidence is the removed anchor namespace/cgroup. The three affected Flux calls are being corrected separately; the corrected compiled45-case fixture remains unproved. The earlier44-check qualification remains unchanged; full A04 and live acceptance remain open.

## 2026-10-15: compiled Pods browser CI smoke passes

The [current hosted browser receipt](../evidence/bortus-hosted-browser-smoke-root-20261015.json) binds owning source939648f5/frontend407239c9 to validation e92cfcfd. Build, lint/types,342 units,eight HTTP integrations and all seven unchanged regression controls pass. The compiled Pods browser test observes HTTP200/all208 records,100 initial rows,three filtered records,eight non-Age columns and three exact links, with no mutations. Earlier503 failures remain recorded; the diagnostic run proves noexec/EACCES, and the one-option fixture-only exec correction yields spawn0 and browser pass. Both confirmed containers and all three exact names are absent after orderly cleanup. This finite smoke does not close human AT, performance, cross-process regression sensitivity, real-cluster acceptance or final image/delivery; production is unchanged.


## 2026-10-16: remaining node text contrasts captured and corrected in isolated source

The [saved style capture](../evidence/bortus-a15-remaining-styles-root-20261016.json) reaches the active Nodes page after Cancel and retains both actual axe contrast findings: node count and Age. It records only GET/HEAD gateway requests, zero observed browser write requests and zero Secret value requests. The administration fixture has no productMutations counter; a harness assertion incorrectly expects one and ends the original actor/browser with exit1 and zero completed whole cases. The separate saved-data validator qualifies those captured facts without replaying or changing the failed report. Exact/fresh/final checks verify146 current records,33 absent Linux births,13 Windows recorded births not live and two retained exact container queries; the current Job closure is verified. The earlier four-label Job unknown remains unchanged.

Owning application commitd901ccdd changes exactly the node-count and Age classes from zinc500 to zinc400 and updates affected docs after checking all22 application docs. Its fresh build/render verification is pending. The Age glass/backdrop prevents a precise manual ratio from this capture; no blanket axe or actual assistive-technology pass is claimed. Original performance failures, production and original migration data remain unchanged. Goal active; no user action is pending.


## 2026-10-16: finite timing diagnostic complete; original benchmark still fails

The [qualified diagnostic composition](../evidence/bortus-finite-warm-diagnostic-composition-root-20261016.json) retains50 complete joins from the original failed actor and adds22 fully joined responses from one isolated candidate-only run; the original50 were not replayed. Both earlier failures remain exit1. The added observer covers both actual middleware and chunk account-reader definitions and includes a bounded failure recorder. Independent checks reconstruct every saved join, verify28 inputs/eight retained graphs and finish with135 current records,24 absent Linux births and two retained exact container queries. The final check adds no graph walk, new query or recursive reader chain.

The new20 warm observations include observer overhead and are not pooled into the original benchmark. Median worker operation is359microseconds; the broad middleware span is66.239milliseconds and includes queue/framework scheduling. These intervals overlap and do not establish exclusive CPU shares. Source review finds the next queued read is already pumped synchronously; no safe optimization is established by this trace. The frozen one-active/64-queued, fresh account/path/schema checks, two real yields and five-second deadline remain. Original performance acceptance stays failed. The separate two-CSS-class application revision is now building; production and original data remain unchanged.


## 2026-10-16: unchanged public recovery controls pass quiet retry

The [public63 retry](../evidence/bortus-public63-quiet-retry-root-20261016.json) passes all63 actual tests in21.362seconds under the unchanged30-second supervisor budget (work ends28,closure reserve2,OS-only margin1). All eight test files and supervisor functions are identical; only exclusive source/output constants change. Independent checks verify all198 inputs and original actor/suite births, then one finite final binds nine records and three absent births without graph walks, Docker queries or recursive reader checks. The default201-file scan retains literal1/one finding in the exact previously reviewed public mTLS negative-test fixture; the independent-post source scan is0/zero. No suppression or rescan is used.

The earlier54-case timeout remains failed; its cause is unknown. This qualifies public controls only: no private recovery, stored Secret consumption, release-image adoption or live changes occurred. The source-only preparation field originally called the total budget businessSeconds; this receipt states the actual unchanged30/28/2/+1 timing precisely. The application build separately passed all four phases; its independent qualification and focused rendering remain pending.
