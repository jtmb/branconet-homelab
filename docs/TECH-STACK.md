# Branconet migration technology and topology

The approved target is Kubernetes on the existing three Ubuntu 22.04.4 machines. [MIGRATION_STATUS.md](../MIGRATION_STATUS.md) records what has actually passed; this document describes configuration, not deployment completion.

| Host | Address | Target role |
|---|---|---|
| masternode | 192.168.0.4 | Control plane and workloads |
| workernode2 | 192.168.0.5 | Worker and storage |
| workernode1 | 192.168.0.6 | Worker and storage |

One control plane needs a documented etcd/configuration restore; it is not a highly available control plane. Longhorn application volumes use two replicas on separate nodes.

| Component | Configured version | Purpose |
|---|---|---|
| Kubernetes | v1.37.1 | kubeadm, API, scheduling and kubelet |
| containerd | v2.4.1 static | Independent Kubernetes CRI runtime |
| runc | v1.5.2 | Independent OCI runtime |
| CRI tools | v1.37.0 | Runtime diagnostics |
| CNI plugins | v1.9.1 | CNI executable prerequisites |
| Calico | v3.33.0 | Pod CIDR 10.244.0.0/16, IP-in-IP, network policy |
| CoreDNS | kubeadm-selected image | Two ready replicas; service domain cluster.local |
| Longhorn | v1.12.1 | Replicated V1 volumes, LUKS encryption, retained PVs |
| CSI snapshot controller | v8.6.0 | VolumeSnapshot API/controller for tested Longhorn restore |
| SMB CSI | v1.20.3 | Existing NAS share mounts in application pods |
| Traefik | v2.11 original digest | Native LAN 80/443 routing through NodePorts 30080/30443; application ingress |
| Flux | v2.9.6 | Source, Kustomize, Helm and notification controllers |
| Helm CLI | v4.3.0 | Individual chart validation and infrastructure install |
| Ansible core | 2.21.5 operator runtime | Host provisioning through SSH |
| age | v1.3.2 operator runtime | Encrypted configuration/data recovery archives |
| BORTUS | Repository application | Kubernetes management; native Secrets integration developed separately |

Kubernetes uses containerd-k8s.service, /run/containerd-k8s/containerd.sock and /var/lib/containerd-k8s. Existing Docker/containerd configuration, runtime and data remain available during migration. Native Kubernetes Secrets use API encryption at rest; secret values remain outside Git. Encryption keys and Kubernetes recovery configuration must be included in encrypted recovery backups.

The targeted configuration capture uses the checkpoint transport interface and
age, with no new runtime dependency. Its32 standard recovery files complement
broader historical host archives. All75 combined root controls pass. The fresh
actual32-file authenticated capture and exact NAS ciphertext readback are
accepted. The raw etcd checkpoint/registry restore is accepted separately; API decryption and independent Longhorn recovery remain pending. See
[migration operations](MIGRATION-OPERATIONS.md).

Longhorn is the default persistent application storage. Each chart declares its own PVC mounts and values. Existing NAS media at //192.168.0.8/plex_smb_share remains intact; requested integration is a separate live acceptance check. The Samba role installs the client CSI driver only. It does not create a guest share or overwrite exports, credentials, fstab or files. Host-local default storage and a new NFS server are not part of this migration.

Ansible bootstraps hosts independently of BORTUS. Nonsecret configuration is versioned in group_vars/all.yml; sudo is passed through the migration runner's stdin. Active application chart delivery uses the separate private `jtmb/branconet-charts` repository: main, successful chart CI, exact-SHA promotion to `validated`, then the existing Flux `branconet-charts` source and `migration-releases` owner at `./flux/releases`. The old migration publisher and raw-manifest roots are historical; do not reactivate them. Application source quality CI is separate and does not publish a running image. Git stores charts, values and Secret references, not Secret values. See [PLAN.md](../PLAN.md) for architecture graphs and acceptance criteria, [MIGRATION-OPERATIONS.md](MIGRATION-OPERATIONS.md) for operations, and [FLUX-GITOPS.md](FLUX-GITOPS.md) for reconciliation.

Version checks use official [Kubernetes releases](https://dl.k8s.io/release/stable.txt), [Calico requirements](https://docs.tigera.io/calico/latest/getting-started/kubernetes/requirements), [containerd releases](https://github.com/containerd/containerd/releases), [Longhorn documentation](https://longhorn.io/docs/1.12.1/) and [Flux releases](https://github.com/fluxcd/flux2/releases). The final report must record effective images and live checks, rather than infer compatibility from installation success.

## BORTUS native Secrets runtime

The delivered container uses Node 22, Next.js 15.5.27 and @kubernetes/client-node 1.4.0 with verified TLS. Prisma/SQLite holds user hashes/roles, nonsecret configuration and SecretReference metadata. Native Kubernetes Secrets hold values; no database-to-cluster push or SSH startup kubeconfig bootstrap remains. See [BORTUS-DEPLOYMENT.md](BORTUS-DEPLOYMENT.md) for probes, PVC, ServiceAccount and scoped Secret RBAC. Other dashboard operations use kubectl and require separate deployment permissions and live acceptance.

Image qualification now uses a private pinned [Trivy 0.75.0 release](https://github.com/aquasecurity/trivy/releases/tag/v0.75.0)
binary verified against the immutable release asset digest and published checksum.
It is installed only under the protected operator runtime, without a global install.
Image archive and image-config Secret scanners plus vulnerability scanning use
default built-in rules, no user ignore/config files, one worker and disabled
telemetry. Raw reports stay outside Git. The [actual holder scan](../evidence/bortus-holder-source-image-7e30-20261011.json)
records findings and scope; zero Secret findings does not mean vulnerability-clean
or final runtime/release acceptance.


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

The [qualified native-selector compiler environment](../evidence/bortus-native-builder-qualification-root-20261012.json) is the official Linuxamd64 Node22.23.3 full Bookworm image pinned to `node@sha256:c4d5523090a817b7aa86d2111241fdd4f66d1e27782b44160e6aa63b357ecb2d`. Acquisition and an isolated read-only/network-disabled tool probe exit0. Its Node executable is byte-identical to the prior runtime; GCC12.2.0, GNUld2.40, glibc2.36 and four Node headers have explicit version/SHA identities. The [official Dockerfile](https://github.com/nodejs/docker-node/blob/main/22/bookworm/Dockerfile) documents its buildpack-deps base. This is build tooling; the final application runtime stays separately qualified. A future fresh performance pair uses this same pinned environment for baseline and candidate because the unchanged runner has one image input for both build and measurement. That comparison must disclose its changed runtime provenance and cannot retroactively accept the old slim-image pair. No app image or native-addon source build is accepted by this tool probe alone.

## 2026-10-14: latest isolated qualification outcome

The [Node continuation outcome](../evidence/bortus-node22-continuation-outcome-root-20261014.json) records offline documentation installation exit0 with279 exact-lock packages, then unchanged make -j2 test-only JOBS=2 exit2: two original cluster scripts time out after120seconds and the pending-DNS setServers test misses its expected exception. The version phase is not run. A live read-only sample binds114 zombies to the exact owned Python PID1; this establishes deficient orphan reaping, without retrospectively identifying the failed worker PIDs or proving the DNS cause. Independent outcome/custody checks exit0 with78 records, original51008-object workspace/physical fingerprint and810-object cache current,14 original births and exact CID/name absent; three later reader/query births are absent. The generic terminal SHA equals an older failure because its JSON bytes match; distinct started/phase/post records establish this execution. Runtime/security/image acceptance remains unproven. A separate bounded unchanged-script baseline/init and DNS observation is prepared; no suite skip, weakened oracle, performance replay or adoption is authorized by these results.

## 2026-10-14: Node init and DNS diagnosis

The [finite init/DNS diagnostic](../evidence/bortus-node22-init-dns-diagnostic-root-20261014.json) exits zero, followed by an independent zero-exit source/workspace/closure check. Both unchanged cluster scripts time out after 120 seconds with Python as PID 1, then both pass with the exact verified Docker init executable. In both cells the existing one-server DNS configuration yields ECONNREFUSED without the expected pending-query exception; a real reachable loopback sink receives one DNS datagram and preserves ERR_DNS_SET_SERVERS_FAILED until cancellation. Actual Node 22.23.3, OpenSSL 3.5.9 and module ABI 127 assertions pass. This supports a runner reaping and resolver-environment correction; it does not turn the failed original full suite into a pass. The selected direct-test environment differs from full-suite PATH/unused Git variables and uses new owned HOME/TMPDIR/NODE_TEST_DIR/TEST_SERIAL_ID scratch. Source, test bodies, original frozen 51008-object workspace/physical fingerprint, network-none and fixed 2CPU/8GiB/no-swap/512-PID limits stay intact. Independent checks verify 29 original host births absent and both exact created CIDs/names absent; five reader/query births and the saved later checker birth are also absent on the same boot. V1 stays unrun; the executed V1.1 adds directory fsync, held/revalidated actual-init executable/namespace FDs and independent deadline-protected socket cleanup. No original performance benchmark, private recovery, production rollout or data retirement occurs.

## 2026-10-14: standard resolver qualifies; full Node suite running

The [focused resolver receipt](../evidence/bortus-node22-local-resolver-root-20261014.json) records eight UDP/TCP protocol checks and an exit-zero unchanged upstream DNS test with both mustCall callbacks completed. The owned responder answers localhost A/AAAA immediately, local other types with NODATA and nonlocal queries with REFUSED; it does not forward or deliberately delay. Independent checks bind six sources, the original51008-object content/physical fingerprint,17 host births and exact container ID/name absence; three reader/query births and the later checker are also absent. The [new full-suite dispatch](../evidence/bortus-node22-init-resolver-dispatch-root-20261014.json) uses a fresh exact copy, unchanged make/test command and original oracles/environment, adding verified init and this private resolver. Offline documentation installation exits zero and the default test phase is running. Its source-enforced pre-create boot authority is explicit; the inherited started schema has no boot field. The original failed suite remains failed; this pending attempt grants no runtime, security, performance or deployment acceptance.

## 2026-10-14: Debian advisory metadata refreshed

The [eight-source primary advisory refresh](../evidence/bortus-debian-advisory-refresh-root-20261014.json) retains each fetched HTML hash and supported-release row. All eight tracked CVEs still show Trixie vulnerable without a supported Trixie fix; fixes listed for forky/sid are not treated as supported Trixie updates. This is advisory metadata only: the original complete scanner findings remain retained, no image is rescanned or changed, and no residual exception/security acceptance is granted.

## 2026-10-14: corrected full Node runner fails; originals and closure verified

The [literal runner outcome](../evidence/bortus-node22-init-resolver-outcome-root-20261014.json) preserves outer exit1, offline documentation install0, unchanged default suite2 and unrun final version phase. Its failure footer contains90 unique sequential tests; the earlier two cluster tests and pending-query DNS test are absent from that footer. Thread creation/resource refusals appear in the raw logs, but no particular exhausted limit or OpenSSL cause is proved. No limit, source/oracle or skip is changed. Independent post0 binds91 records, the frozen51008-object content/physical fingerprint,810 cache objects, ten current sources and the58210-object failed copy. Fifteen recorded host births and the exact CID/name are absent; three reader/query births are later absent. The reused generic failure-terminal SHA is not treated as run identity. No full-suite, new runtime/security or image acceptance is granted.

## 2026-10-14: retained Node thread-refusal evidence

The subsequent current-source/log review binds the996338-byte stdout and260-byte stderr to the independent Linux post records, verifies each public assertion snippet against both the frozen original and selected copy, and retains90 unique failed tests/30 Signal6 markers. The first failed test reports thread creation refused at src/node_platform.cc104; eight pthread_create/resource-unavailable messages and four uv_thread_create occurrences are retained. No contemporaneous pids/memory denial counters were captured, so the exhausted resource remains unproved. The next held proposal selects one unchanged first sequential test with bounded read-only counters and unchanged limits; no new diagnostic executes here.

## 2026-10-14: unchanged first sequential test reaches the PID ceiling

The [single-test resource receipt](../evidence/bortus-node22-first-sequential-resource-root-20261014.json) retains actor1 and original driver1: zero passed/one failed, with the upstream120-second timeout, not the outer150-second cap. The same2CPU/8GiB/no-swap/PID512 container records61 numeric rows/3636bytes, sampled pids.current512 and35725 sticky pids.events:max denials. Every memory-event delta is zero; sampled memory.current peaks at1221668864bytes. Logs contain five pthread_create refusal tokens. These establish PID-limit denials in this new run, without retrospectively proving the cause of all90 earlier failures. No test, oracle, skip, affinity or NODE_OPTIONS changes. Independent post0 verifies the counters, seven current sources, frozen51008-object content/physical fingerprints,15 host births absent and exact CID/name absence; three later reader/query births are absent. A distinct same-test PID1024 source-only evaluation is being prepared with all other limits fixed. It grants no full-suite, runtime/image/security, performance or production acceptance.

## 2026-10-14: current compiled authorization worker ownership qualifies

The [current compiled ownership receipt](../evidence/bortus-legacy-node-compiled-ownership-root-20261014.json) verifies ten HTTP requests, twelve fresh worker SQL reads (five session/seven account projections), thirteen exact dispatch/operation/settlement joins and zero parent SQL calls. Current6e2 compiled middleware and handlers exercise role changes, session revocation, account deletion and schema outage with unchanged complete-response oracles. Independent exact/fresh/later checks pass:374 raw sources plus four generated extras,35 inputs,5383 compiled and40635 installed objects are current;19 recorded births and exact CID/name are absent, followed by three later reader/query births. This composes with the earlier full342+8 and nine-case browser qualification; it does not assert universal ownership or latency acceptance. V1 preparer exit1 at its Windows-UNC prerequisite is retained before workspace/actor creation. Distinct V2 corrects only canonical POSIX receipt paths and owner/input bindings. Its literal source default scan exits1 with one finding, independently traced to public container-name/prior-attempt status metadata; no suppression, exclusion or scanner replay occurs. Performance, runtime/security-image, private recovery and guarded live acceptance remain open.

## 2026-10-14: isolated PID1024 comparison passes; full suite remains open

The [same-test comparison](../evidence/bortus-node22-pid1024-comparison-root-20261014.json) changes only the diagnostic container PID ceiling from512 to1024, keeping2CPU/8GiB/no swap, the unchanged test/120-second driver and150-second phase. One test passes; all sticky PID/memory event deltas are zero. Three numeric rows/156bytes give sampled pids.current447 and memory.current741433344bytes; these sampled peaks are lower bounds. Independent post0 binds seven current sources, frozen51008-object content/physical fingerprint,17 host births absent and exact CID/name absence; three later reader/query births are absent. The earlier512 case stays failed with35725 PID-limit denials. A stale-pin first1024 source draft was caught before execution and remains unrun; the executed V2 has all direct executable pins verified. This supports a distinct full-suite runner preparation with PID1024; that full suite has not run. Original90-failure history and production resource limits are unchanged. No runtime/image/security or performance acceptance follows.

## 2026-10-14: full PID1024 evaluation running; result pending

The [dispatch receipt](../evidence/bortus-node22-full-pid1024-dispatch-root-20261014.json) records actual root dispatch and a live PID/start/UID/boot witness. After the successful isolated comparison, this distinct runner changes the test-container PID ceiling to1024, keeps2CPU/8GiB/no swap and all original test commands/oracles/skips,10800-second lease/60-second closure and2400-second test bound. It uses a fresh copy of the frozen51008-object workspace and unchanged offline cache. Offline documentation installation exits0; upstream default tests have started. Actual completion is pending, not a full-suite/runtime/image/security pass. Production resource limits and the previous90-failure result remain unchanged.

## 2026-10-14: full unchanged Node upstream suite passes

The [full PID1024 qualification](../evidence/bortus-node22-full-pid1024-qualified-root-20261014.json) records actor0 and original default-test command0,4706 driver passes/zero failures, plus offline-doc-ci0 and new-version0. Node22.23.3/OpenSSL3.5.9/ABI127 retains ELF a7b77e9e,125362584bytes. Independent post0 verifies current10+6 sources, the original51008-object frozen content/physical fingerprints,810-object cache, archive/projection/tool authorities and six selected current-copy artifacts;16 recorded host births and exact CID/name are absent. Four later corrected-reader/query/failed-reader births are absent. The first post1 at267/178/5 retains a stale duplicate input hash; the distinct corrected reader changes only that hash to executed selected bytes and fresh source/owner, preserving all900/30 validation branches. Test2CPU/8GiB/no swap/PID1024, qualified init/local resolver,10800/60/2400 bounds and original commands/oracles/skips remain fixed. The old90-failure/PID512 results and production resource limits are unchanged. This passes upstream tests, not BORTUS application/native/TLS compatibility, final image/security or deployment acceptance.


## 2026-10-15: affected CI checks pass; preload composition controls pass

The [affected read-only CI phase](../evidence/bortus-a19-readonly-ci-checks-root-20261015.json) passes lint, semantic type checking and all342 unchanged unit tests, with zero failures/skips/cancellations. The source fix replaces `npm test` in that read-only phase with `node --import tsx --test tests/*.test.ts`; unconditional worker generation remains in the prior writable build. This run uses a fresh374-file source copy and four qualified generated artifacts with existing dependencies/compiled output mounted read-only, under the original4CPU/4GiB limits. It proves the revised check command, not a fresh install/build, eight integrations, per-regression negative controls, hosted CI or deployment. Exact/fresh/later/final checks pass, with965 current pins and59 host births freshly absent. The owning commit is `9fbd85f` (workflow plus11 docs); root independently verifies all12 committed raw blobs and unchanged frontend tree. Hosted CI remains unproved. Four default scanner findings are exact pinned public Node header checksums; the literal scanner1 is retained with zero unresolved findings and no suppression/replay.

The [new preload composition controls](../evidence/bortus-worker-preload-composition-controls-root-20261015.json) pass all six finite groups: four actual file Workers with default inherited require arguments, forwarding/error identity checks, and actual MessagePort listener restoration with precise wrong-tuple refusal. The helper validates the script path/hash at the first public message-listener registration; the adapter declares its exact later restoration tuple separately. This proves diagnostic composition only, not prevention of earlier script execution, application/SQLite behavior or performance. Exact/fresh/later/final checks pass, with93 current pins and20 host births freshly absent. The separately qualified corrected profile now completes; the old profile failure and original benchmark regressions remain.
