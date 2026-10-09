# Migration acceptance evidence

Contract: [PLAN.md](PLAN.md). Goal active since 2026-10-09 14:30 UTC; execution target before 20:30 UTC. Cluster migration is owned by this chat. BORTUS application development is owned by chat 01a12114-28d9-7623-8aed-9947e08d7065, which delivered app commit 1438b278cdf21e98429b4836c018636b01b982a3 in its isolated worktree. Live deployment/acceptance belongs here.

## Current progress

- Approved plan saved with architecture graphs, acceptance contract, migration sequence and report template.
- Migration goal active; source checked out from the inspected k8s-rewrite baseline on codex/kubernetes-migration.
- BORTUS application-development chat requested with an isolated worktree and scoped integration contract.
- Vault unsealed and HTTP-healthy; authenticated metadata inventory completed: 40 current records, 43 values.
- Three hosts inspected; sudo verified; Gluster bricks online, no reported split-brain, pending Plex log healing.
- No application cutovers, data imports or Kubernetes deployment acceptance tests completed yet.
- Encrypted Docker/host configuration recovery verified for all three hosts; metadata in evidence/config-backups.json. These are configuration backups, not application-data backups.
- Cold application-data backup started 14:56 UTC, covering logical Gluster, NFS state, all Plex directories, ETS2 and anonymous volumes. Archives are still being written; no data-recovery acceptance claimed yet.
- Ansible foundation adapted for independent containerd, current inventory, explicit pod CIDR, native Secrets encryption, retained LUKS Longhorn, existing-share SMB CSI and temporary ingress. Static Ansible syntax check passed; live provisioning remains pending the backup gate.
- First master cold archive failed: Gluster returned I/O errors for old Plex logs and vanished Jackett paths. Its partial archive is retained and is not accepted. Worker archives were written; authentication/recovery checks remain pending. Gluster brick directories remain untouched. Read-only privileged diagnostics are underway; provisioning gate remains closed.
- Privileged audit confirmed zero reported split-brain and all three bricks connected. The Jackett paths exist in every brick and are readable on worker clients; master FUSE lookups return ENOENT. Recovery backup is underway: all brick copies, worker logical Gluster (obsolete Plex Logs preserved in raw archives), primary local/NFS state and original anonymous volumes. No provisioning or cutover accepted until recovery validates.
- Recovery attempt stopped on missing baseline anonymous paths: FlareSolverr /config and Vault /vault/file and /vault/logs task volumes were removed during the initial Swarm scale-down before archival. This was a sequencing error. Their prior contents are not verified or recovered; full data preservation is not accepted. Vault's actual Consul/Gluster store remains present. User clarification about required contents is pending; no acceptance exception is assumed.
- The source restart commands succeeded in the recovery attempt. Latest readiness: six standalone containers running, 31 of 32 Swarm services           at desired count; Pi-hole is failing health checks and is not accepted as restored yet. No Kubernetes provisioning has been executed.
- Source coverage register generated: 42 entries, including every Swarm service, standalone instance, repository-only application and BORTUS dependency. Individual test fields remain pending.
- Adapted Ansible syntax check and read-only Ansible ping passed on all three actual hosts using SSH 2002; script compilation passed. Live Kubernetes readiness remains pending.
- Pi-hole diagnosis: gravity.db exists on all three bricks and on master/worker2 logical clients; worker1 FUSE returns ENOENT. Source service received temporary node.hostname==workernode2 scheduling constraint to use the existing readable database. No database was reset. Readiness/DNS validation is pending; retain the original service configuration for rollback.
- Pi-hole now reports healthy with successful health checks on worker2. Latest source register: all 32 services at desired count and six standalone containers running. Retained archive authentication and restored Vault metadata verification are underway; full backup acceptance remains open.
- User confirmed the three named anonymous directories were disposable runtime state. PLAN.md and backup scope now record that clarification; no other data exclusions are inferred. Backup tooling blocks writer shutdown for any unprotected non-disposable anonymous application paths.
- Restored Vault is active/unsealed, HTTP 200, with 40 records / 43 values matching original inventory counts. Native Secrets import and in-memory value comparison have not run.
- Source DNS tests: worker1 address 192.168.0.6 answers UDP and TCP queries; master/worker2 addresses return REFUSED. This is recorded, not claimed as a three-address DNS pass. Pi-hole container itself is healthy on worker2.
- 15:59 UTC: final recovery run wrote all three raw brick archives, worker2 logical Gluster and primary local/NFS data successfully. Source restart commands returned zero; 16:00 readiness confirms all 32 Swarm services at desired count and six standalone containers running. Complete authenticated archive traversal is running; provisioning remains gated.
- Four earlier retained archives passed authenticated decryption/full tar traversal: original worker Plex archives, worker2 raw brick and worker2 logical Gluster. See evidence/archive-verification.json; that individual verification alone is not the complete source-backup contract.
- 35 individual Helm packages prepared. Initial lint, staged-render and activation-gate checks passed; later live-manifest preparation uses measured paths/image digests and remains under validation. All releases remain disabled. BORTUS deployment is the separate dependency, and no application functional acceptance is claimed.
- 37 source bind paths measured without read errors. The prepared live charts allocate Longhorn claims from measured application data and retain exact SMB source directories. Existing Docker host mounts in Homepage are flagged for review/removal before source retirement. Gluetun is prepared as a restartable qBittorrent sidecar, preserving native runtime env/Proton WireGuard; VPN live checks remain pending.
- Redis audit confirms no mounted data path, snapshot persistence in the task writable /data directory, and a WordPress redis-cache plugin/configuration. Current regenerated cache has 19 keys. The original task's writable state was not archived before removal. Its historical state is not accepted as preserved; the cache-only role/acceptance exception still needs resolution.
- 16:10 UTC: seven required data archives passed authenticated decryption and complete traversal (603,487 tar entries). All three raw Gluster bricks, logical Gluster, primary local/NFS data and both original worker archives are covered; source restart commands succeeded. This clears the infrastructure backup gate, but does not resolve the separate original Redis writable-state exception or establish app restore/cutover acceptance.
- Live foundation stage started with tags bootstrap,kubernetes,network,dns. Independent runtime and Kubernetes installation are underway; three-node readiness is not claimed yet.
- Native Secret preparation completed successfully for 72 target Secrets, including all 40 current Vault records, source app environments and existing media SMB credentials. No native import has executed and no BORTUS integration is accepted. Source inline fstab credentials are handled only in memory from the encrypted recovery configuration.
- BORTUS app-development chat is now registered and active with the scoped native-provider/runtime/auth/test contract. It reuses the existing isolated app worktree. The older queued creation produced no registered chat and is not counted as running delivery.
- Handoff correction: the original BORTUS chat did register and completed at 15:13 UTC; earlier app listings omitted it. The recovery chat identified its ownership/commit and was archived without edits. Delivered development evidence: 11 behavior/TLS tests, production HTTP integration, migrations/schema drift, type check and build passed. Image execution/live AC7 are still pending. Deployment contract: port 4000, /api/health/live and /api/health/ready, persistent nonsecret/user SQLite at /data/bortus.db, explicit metadata-only lookup aliases, namespace-scoped Secret get/list/create/update roles.
- Provisioning first stopped before host edits on Ansible 2.21 /dev/stdin path resolution, then missing explicitly loaded variables. Runner now passes stdin-received sudo only through an in-memory child environment lookup; every play loads its group-vars file. The next run installed prerequisites but stopped on worker2 DNS resolution. A temporary per-link DNS override uses verified homelab resolver 192.168.0.6 instead of prior 192.168.0.1; GitHub resolves again. Persistent network files/Pi-hole policy remain unchanged.
- Resumed provisioning verified independent CRI on all three hosts and Docker active, initialized the control plane and started worker joins. Three Ready nodes/DNS acceptance is still pending. The separately delivered BORTUS image is building on source Docker with clean context and cluster-matching kubectl.
- Foundation Ansible completed successfully at 16:19 UTC. Live API confirms masternode/workernode1/workernode2 Ready on v1.37.1 with containerd 2.4.1; Calico 3/3 and CoreDNS 2/2 ready. Two worker test pods passed Kubernetes service DNS and bidirectional cross-worker ping; evidence/network-proof.json records actual versions/image IDs. Storage acceptance still remains.
- Delivered BORTUS image built successfully from clean context at 16:20 UTC: bortus:migration-1438b27, image sha256:a8f40f067fd2c3f8e0d8686147a95fa092430d23fece150a74e519498ef206fc. Image distribution/runtime/live checks are pending.
- Post-provision encrypted configuration recovery passed on all three hosts, including Kubernetes PKI, operator configuration and API/Longhorn encryption key files; prior snapshot metadata retained. Protected operator kubeconfig recovered outside Git and API access verified.
- Native import completed: 73 Secrets, including 40 Vault records / 43 values, source application environments, SMB credentials and fresh BORTUS runtime keys. Every API readback matched in memory. All 73 actual etcd records have the AES-CBC encryption prefix. No values were exported to Git or reports.
- Longhorn actual-device proof passed at 16:35 UTC: LUKS header, two running replicas on distinct workers, write persistence after worker relocation and restoration of an earlier snapshot into a separate PVC. These retained test resources prove storage primitives; application acceptance and off-cluster recovery remain separate.
- All 35 charts contain resources and passed lint, blocked unverified activation, staged rendering and integer replica checks. Actual application configuration, API checks and cutovers remain pending.
- BORTUS image verified in the independent containerd runtime on all three nodes with identical manifest digest. A private, one-replica staging release is running on its new Longhorn PVC; live native provider/auth/restart acceptance is underway. Its staging gate forbids public ingress/external Service exposure before application acceptance.
- Source readiness refreshed at 16:48 UTC: all 32 Swarm services at desired counts and all six standalone containers running. No production application data cutovers have occurred.
- BORTUS live checks passed at 16:51 UTC: all 80 Vault aliases returned exact native values in memory; unauthenticated and readonly value/write requests were denied; native create/update/conflict/key-delete preserved other keys/metadata; app restart retained values, user session and stable signing/lookup keys. Registration is locked. Dashboard and live-outage checks remain pending; there is no public ingress yet.
- Consistent etcd recovery passed at 17:00 UTC: encrypted operator/NAS snapshot authenticated, restored and started in an isolated loopback-only pod, and 82 native Secret ciphertext records matched, including all 73 imported encrypted objects. Snapshot transfer through exec stdin failed earlier checks; the accepted restore uses a read-only root-protected source snapshot whose bytes were compared with authenticated decryption. Production etcd was never restored over.
- Delivered BORTUS app commit integrated as d3a1755 after migration foundation commit 5363504. Conflicting documentation retains actual cluster versions/bootstrap behavior and the delivered native provider contract. App code remains owned by its separate development chat.
- Prepared one CI validation job and success-dependent publication of codex/kubernetes-validated; Flux source reads only that branch, with 35 individual HelmReleases under the new migration-releases path. All application releases remain disabled except accepted-private BORTUS staging. Remote CI/reconciliation activation is pending.

- 17:56 UTC: BORTUS dashboard reads real Ready nodes, pods, Services, deployments, namespaces and volumes. An actual network-policy API outage returns 503 for lookup/readiness without database fallback; both recover after policy removal. No cluster-admin binding or public ingress.
- 17:57 UTC: APLB, Lucinda, Santos and Minecraft websites pass stable HTTP content, actual restart and worker relocation on the same claims. Originals retained; public routing remains pending. Overseerr, Mealie and Vaultwarden cold copies also pass full manifests; further application checks are running.
- Remote GitHub CI run 37967715642 passed and published validated revision 1e6b09b. Current dashboard RBAC/private promotions are being validated for the next revision before Flux adoption. Untested releases are explicitly suspended.
- Temporary per-link node DNS uses public resolvers while Pi-hole is migrated, with prior resolver metadata recorded. CoreDNS retains conditional LAN forwarding. No persistent host network files or NAS exports changed.

## Acceptance ledger

| Criterion | Status | Evidence / remaining work |
|---|---|---|
| AC1 Three-node Kubernetes | Passed | Three Ready nodes, pod DNS and cross-worker ping passed; independent runtime preserves source Docker |
| AC2 One CI/CD pipeline | Prepared | Validation workflow covers all 35 implemented packages; remote CI and staged Flux activation pending |
| AC3 Complete service coverage | Prepared | SERVICE_REGISTER.md and sanitized detailed register account for 42 source/repository entries |
| AC4 Individual charts/values | In progress | All 35 packages implemented and packaging checks passed; live configuration/application checks remain |
| AC5 Longhorn persistence/recovery | In progress | Encrypted two-replica device, cross-worker persistence and snapshot restoration passed; per-app recovery remains |
| AC6 SMB preservation/integration | Pending | Existing share/mounts verified; demonstrate target wiring |
| AC7 Native Secrets/BORTUS | Private checks passed | Native readback/encryption, all aliases, auth/CRUD/conflicts/restart, dashboard and live API outage/recovery passed; public HTTPS pending |
| AC8 Data preservation | In progress | Seven required archives authenticated; actual restore/copy checks and original Redis-state acceptance pending |
| AC9 One Plex service | Prepared | All three configs/libraries inspected; consolidate after backup |
| AC10 Reproducibility/docs | In progress | Plan and report saved; update implementation alongside changes |
| AC11 Retirement approval | Pending | Requires completed evidence and user confirmation |

## Service evidence template

- Service/source container:
- Target chart/release and values:
- Image digest and dependencies:
- Source dataset / destination PVC / media mounts / ownership:
- Secret namespace/name/key references (never values):
- Backup and restoration evidence:
- Consistent final-copy or database verification:
- Functional endpoint/application tests:
- Restart, relocation and rollback tests:
- Status and remaining work:

## Ownership and dependencies

BORTUS changes: native Secrets provider, APIs/UI/lookup/auth, startup synchronization removal, deployable image/runtime, integration documentation and development tests. Migration changes: Ansible, charts/values, Flux, Longhorn, backups/import/cutover and live acceptance. Track BORTUS implementation here by delivery evidence without copying its development transcript.
