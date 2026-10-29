# Cluster hardening — October 28–29 follow-up

> **LATEST — 2026-10-29 10:51:27Z:** Available fixes, runtime preservation, master/worker2 headroom and normal Windows HTTPS are verified. Kubernetes1.37.2/Go1.26.10 and kernel202 are deployed; charts/Flux remain1c6f, Actions off and BORTUS held. Owned disposable cleanup is complete with explicit protected exceptions. Both nodes passed the unchanged extra2GiB margin and15GiB usable-space floor at this measurement. Upstream CVEs and the Bazarr strict source-drift exception remain; this is neither permanent capacity assurance nor a zero-CVE claim. Historical failed/open checkpoints below remain dated evidence.

This report covers the additional request to fix master/worker2 disk headroom,
remaining security concerns and BORTUS HTTPS. The accepted migration and its
pending authenticated Seerr UI exception remain historical. BORTUS application
development and its held release remain separate.

## Implemented and verified

| Area | Actual result | Preservation |
| --- | --- | --- |
| Master disk |25.3 GiB usable; final reserve check passed | Every original image/blob, container/lease and data volume retained |
| Worker2 disk |24.5 GiB usable; final reserve check passed | Same original payload/reference and no-retry guards |
| BORTUS HTTPS | Existing trusted CA, correct host/SNI, verified TLS to all three node443 addresses | Same backend, accounts, claims, image and suspended HelmRelease |
| Certificates | Strict signature/host/usage verifier passes all 12 leaves; Ingenium serverAuth usage explicitly renewed through cert-manager | Original CA and TLS Secret UID retained |
| FlareSolverr | Chart0.1.3: UID/GID1000, capabilities0, NoNewPrivs1, RuntimeDefault seccomp; token absent; Mealie boundary denied | Same browser image; separate real request.get returned HTTP200, detailed revision limits below |
| Admission | whoami/http-echo enforce baseline v1.37; real workload templates pass server dry-run and no Pod persists | Existing platform/application namespaces untouched |
| Bazarr | Official same-version1.6.2 rebuild86b76c5c..., full scan and native staging on all 3 nodes; live after and post-kernel restart preservation comparisons passed | Historical comparisons passed; post-core strict metadata comparison failed as detailed below |
| Kernel recovery | All3 nodes booted5.15.0-202-generic and recovered; fallback198 and master NVIDIA390 retained; fresh28-volume/control-plane recovery checkpoint | All58 PVC/58 PV and44 Longhorn identities frozen;16 offline volumes retained |

Kernel202 rolling maintenance and Kubernetes1.37.2 are complete. The immutable `56f152a9adc044478db62e3cacc65288-result.json` (SHA256 `583d6a0eece75e23940ff4d6f1a4a805dfe6b58148fc8a3d0f44a1d5a9736072`) and all three host completion receipts bind the installed native versions/Go1.26.10, kernel 202, all219 preserved identity/spec rows,28 healthy active volumes and16 retained offline volumes. Earlier carrier, transfer, preflight and upgrade failures remain historical failures; terminal success does not overwrite them.

Bazarr's earlier after-rollout and post-kernel comparisons passed, but its **post-core strict comparison FAILED** on13 original episode metadata rows. Episode count changed5320→5321; no original rows are missing, configuration leaves are preserved and semantic subtitle differences are zero. Read-only correlation found all13 current file IDs, paths and sizes match the configured Sonarr source. That explains the observed source agreement; it does not turn the original comparator into a pass or rebase its baseline. Final Bazarr strict preservation acceptance remains open.

**Historical disk checkpoint before final acceptance:** The earlier coordinating checkpoint recorded approximately30.934GB root free against the25%+512MiB guard of29.462GB. The later qbit completion receipt records30,865,383,424B root free and an exact guard of29,462,389,761B:1,402,993,663B above the guard, still below the required additional 2 GiB. These are separate observations amid concurrent activity, not a measured delta attributable to one cleanup. These early disk results were superseded by the final October 29 receipt below; no bound was lowered.

Master totals comprise the original60 paths/3,598,614,528B, a further30/2,370,383,872B, and47/1,159,852,032B confirmed absent by read-only reconciliation of an interrupted native operation. Those47 include40 previously observed absent plus7 later absent/202,321,920B. No interrupted mutation was retried or reclassified as successful. Worker2 adds27 paths/1,507,631,104B to its prior68/3,440,361,472B.

Worker2's exact five obsolete157 packages and18 completed installed `.deb` duplicates were subsequently removed through signed-source, exact-simulation and preservation guards. Journal device IDs distinguish **715,313,152B on root** (600,252,416B kernel files plus115,060,736B archives) from **18,276,352B on separate `/boot`**. Observed root free increased744,992,768B; its difference from recorded allocations is not attributed because concurrent activity and generated package artifacts affect free space. Master173 remains installed: its proposed removal also selected NVIDIA packages and was rejected.

The completed qbit native replica operation restored the original volume specification and confirmed removal of worker2's exact old replica path `/var/lib/longhorn/replicas/pvc-999128b4-0ae2-4396-a8e4-eebace5d26f0-b2aff16b`. Its recorded pre-removal allocation is **1,120,243,712B**. `qbit-three-copy-headroom/completed.json` reports native removal, path absence, no raw deletion and untouched old failure witnesses. This replica result is separate from native image-cache retirement and does not by itself establish final disk-margin acceptance.

Flare's real browser request.get returned HTTP200 at charts revision`dd7ddd2833e402bab9684dff1a578964be4692b8`; the historical process receipt at`334d9bba3359458fc52a0aac06afccaf0abbeb51` records chart0.1.3, UID/GID1000, CapEff0, NoNewPrivs1, Seccomp2 and no token. These are separate observations, not an invented browser rerun at334d. That historical chart transition changed Ingenium image/checksum only. Source and runtime least-privilege evidence do not patch the embedded Chromium/Brotli vulnerabilities.

The compact [hash-bound evidence index](../evidence/cluster-hardening-20261028.json) names the original receipts without copying cumulative logs.

## Repeatable implementation

- `playbooks/node-headroom-cache.yml`: explicit inventory/qualify/retire phases,
  fixed hosts and exact superseded upstream roots. Original inventory/physical/
  retirement source hashes, compressed hashes and every uncompressed diffID,
  bbolt mappings, xattrs/hardlinks, full process/unit/FD/map/mount references and
  permanent prior-submission journals remain enforced. Native snapshot API only;
  no image/content/volume pruning or raw cache-directory deletion.
- `playbooks/bazarr-vendor-preload.yml`: the exact scanned official image,
  all 3-node preflight before pull, full native cache/continuity proof and original
  25%+512MiB/15GiB floors. A new RAM carrier preserves original SQLite/API/HMAC
  qualification and keeps source, keys and receipts off nodes.
- `playbooks/lan-tls.yml`: optional BORTUS route verification and bounded normal
  renewal for the exact Ingenium leaf missing explicit EKU. Repeated verification
  is read-only after repair. No trust bypass/root replacement.
- `playbooks/cluster-hardening-verification.yml`: exact Flux revision, preserved
  claim bindings, native storage controls, disk margins, token/policy/admission
  checks and all-controller availability.
- `playbooks/kernel-security-maintenance.yml`: see [finite kernel profile](KERNEL202-MAINTENANCE.md).
  Signed index refresh, exact package preflight and explicitly selected apply;
  workers serially then master, real eviction/PDB protection and full recovery.
  Legacy30 remains the default profile with its original assertions. Newcurrent58
  pins every original claim/PV/Longhorn/controller specification and fresh backup.

The FD aliases used for Ansible shorten UNIX socket names only. All scratch,
receipts and archives resolve to the same declared F-backed physical filesystem.

## Security findings that remain visible

The Bazarr candidate's complete scan has **1 Critical,6 High,7 Medium and zero CISA
KEVs**. It fixes four Python critical rows and Brotli, but certifi, Js2Py and
other embedded Python dependencies still require compatible vendor updates.
The scan's clean-security acceptance remains false. Runtime/data acceptance
cannot turn these package findings into patched results.

The official FlareSolverr image still embeds vulnerable Chromium; its current
maintained tag has not changed. Its ingress boundary reduces exposure and does
not patch Chromium. Byparr3.0.4 was reviewed without pulling its929MB image and
is not a complete replacement for Jackett's request.post/session interface.
Other unchanged upstream images still carry previously recorded package/KEV
findings, including embedded .NET/Brotli in the media applications. No bespoke
third-party forks or ephemeral package modifications inside containers are used.

Ingenium's Rapid Reset finding is assessed as mitigated by the observed routing:
actual nginx master uses `/app/nginx/gateway.conf`, which exposes no HTTP/2
listener; Traefik terminates TLS without an h2c override. This is an exposure
assessment, not a package patch or SBOM suppression. The latest reassessment binds image`b9484ea1ee956dd776200b8251886464364a6083b403b5d63447d736c94c5c64` under charts334d. nginx1.22.1 masterPID1454 selected the actual gateway configuration, SHA`1f0ec0c1a111a79d056abab5759a8d001324cce197a208ae57d7b09f256e8b25`; no HTTP/2 listen/directive is enabled. The earlierb52 observation is preserved. `nginx -T` tests selected on-disk configuration, not an in-memory worker dump; Traefik's own HTTP/2 implementation remains outside this assessment. Reassess after relevant image/config/routing changes.

Fresh signed APT indexes show zero additional standard `jammy-security`
upgrades on all 3 hosts. That count alone was incomplete: exact202 kernel
packages in `jammy-updates` contain security fixes. Canonical's current JSON
tracker still marks CVE-2026-98260 needed for Jammy GA; its HWE status is pending.
Kernel202 is a partial patch improvement, never a zero-CVE verdict. Five optional
Python build-tool packages still require ESM access; Pro is unattached. Their
removal is not justified solely by empty reverse dependencies or a process-name
search, so their original files remain preserved.

Primary authority: [Canonical kernel tracker](https://ubuntu.com/security/cves/CVE-2026-98260.json),
[Canonical kernel 202 changelog](https://changelogs.ubuntu.com/changelogs/pool/main/l/linux/linux_5.15.0-202.212/changelog),
[Debian Chromium tracker](https://security-tracker.debian.org/tracker/CVE-2026-87491),
[Debian Brotli tracker](https://security-tracker.debian.org/tracker/CVE-2026-111497).
The exact official Kubernetes1.37.2 candidate image and signed native-binary scans found Go1.26.10 and no CVE-2026-111943. Those exact qualified artifacts are now installed with three-host terminal acceptance; residual package findings remain unchanged. The four image scans retain21 High rows, zero Critical and no listed CISA KEVs. Native kubeadm/kubelet retain five High IDs each; kubectl retains two. Exact remaining modules and vendor fixes:

| Finding | Candidate package → vendor fix | Exposure limit |
| --- | --- | --- |
| CVE-2026-56851 | x/text0.40.0 →0.41.0 | Requires affected secure/precis Nickname processing |
| CVE-2026-56854 | x/crypto0.54.0 →0.55.0 | Go SSH server authentication callbacks; not proof of node OpenSSH exposure |
| CVE-2026-78669 | x/net0.57.0 →0.60.0 | HTTP/2 stream/window CPU denial of service; patched Go stdlib does not patch separately embedded x/net |
| CVE-2026-84304 | grpc1.82.1 →1.83.1 | Fragmented HTTP/2 DATA memory exhaustion; transport reachability must be established |
| CVE-2026-84445 | grpc1.82.1 →1.82.2 or1.83.2 | xDS server/handshake authority path;1.83.2 covers both recorded grpc findings |
| CVE-2026-84782 | proxy libssl3 3.0.22-1~deb12u1 →3.0.22-1~deb12u2 | DTLS suspended-write retransmission; library presence does not prove DTLS use |

Primary advisories: [Go text](https://pkg.go.dev/vuln/GO-2026-6629), [Go SSH](https://pkg.go.dev/vuln/GO-2026-6303), [Go HTTP/2](https://pkg.go.dev/vuln/GO-2026-6611), [gRPC memory exhaustion](https://github.com/grpc/grpc-go/security/advisories/GHSA-vp52-pcj8-j9qc), [gRPC xDS](https://github.com/grpc/grpc-go/security/advisories/GHSA-2v4p-qf9q-27wj), [OpenSSL advisory](https://openssl-library.org/news/secadv/20260929.txt), [Debian OpenSSL](https://security-tracker.debian.org/tracker/CVE-2026-84782).

Unchanged affected vendor applications retain the recorded CVE-2026-111497 Brotli finding, including FlareSolverr, BORTUS, Mealie, Tautulli, Sonarr, Pi-hole, Threadfin, Plex and Vaultwarden. BORTUS release ownership remains separate and suspended. CVE-2026-87491 Chromium and CVE-2023-44487 nginx remain visible as package findings; the nginx [vendor advisory](https://www.f5.com/company/blog/nginx/http-2-rapid-reset-attack-impacting-f5-nginx-products) makes HTTP/2 exposure material to this assessment. Unsupported ESM/build-tool removals, blanket package upgrades, derivative images and bypassing held application releases are not substituted for compatible vendor fixes. Previously deployed official MySQL8.4.13/YTPTube2.7.6 fixes do not close unrelated fleet findings.

No claim is made about unknown zero days or an unperformed whole-fleet rescan.

An October29 upstream recheck found the same FlareSolverr3.5.2 and stable
Bazarr1.6.2 vendor images. Chromium's153.0.8010.36 fix and certifi2026.10.18
exist upstream, but those stable application images have not incorporated them.
Js2Py0.74 remains the published version and its proposed patch is unmerged.
Canonical still reports no released Jammy GA fix for CVE-2026-98260; the pending
HWE package is not treated as an available replacement. These are open vendor
dependencies, with the deployed boundaries recorded above.

Sources: [FlareSolverr release](https://github.com/FlareSolverr/FlareSolverr/releases/tag/v3.5.2),
[Chromium advisory](https://chromereleases.googleblog.com/2026/09/stable-channel-update-for-desktop_0808145027.html),
[Bazarr stable release](https://github.com/morpheus65535/bazarr/releases/tag/v1.6.2),
[certifi advisory](https://github.com/certifi/python-certifi/security/advisories/GHSA-6q48-6c7w-9gw2),
[Js2Py proposed fix](https://github.com/PiotrDabkowski/Js2Py/pull/323).

## Reconciliation and recovery

Actual prior failures remain preserved: the first worker2 cache attempt stopped
before any deletion because journals from the other node changed a history
binding; node-specific journals fixed that authority scope and a fresh complete
qualification passed. The first TLS UNIX-socket path failure, missing-EKU
observations and stale observation-time failure remain separate from the final
successful verification. The first Bazarr credential transport attempt failed
before any native pull intent; bounded RAM input is now consumed before child
SSH. None of these is reclassified as a pass.

The first storage checkpoint attempt failed before writes because its explicit
NAS URL pin was missing. The next prefix stopped safely when Bazarr detached
during its rollout, leaving ten completed native backups. The rollout settled,
then a new prefix `k202-settled-20261028` completed all 28 backups. Existing partial
recovery resources remain intact; no partial prefix is replayed or guard relaxed.
The new encrypted control-plane archive is76,921,380 bytes; its independent
content-addressed NAS copy matches the authenticated original. It is a fresh
recovery checkpoint, not a claim of a new independent etcd restore.

Four completed publisher exports were retired with exact reachable-Git/blob
proof, original-tool hashes, full Linux reference checks and3,239 exclusive
Windows handles. **711,512,064 allocated Linux bytes** were removed. Their exact
per-file paths/bytes are in `publisher-cleanup-118f04906bb27369/receipt.json`.
Original source/tools and 20 unique validation/publication receipts survive.
All three completed scanner cleanup receipts now bind the exact removed runtime/DB paths:

| Completed scan consumer | Allocated Linux bytes removed | Receipt under the task leaf |
| --- | ---: | --- |
| Bazarr image |3,213,975,552 | `bazarr-full-scan/cleanup-receipt.json` |
| Four Kubernetes1.37.2 images |3,213,062,144 | `kubernetes1372-full-scan/cleanup-receipt.json` |
| Kubernetes1.37.2 native binaries |3,212,693,504 | `kubernetes1372-binaries/cleanup-receipt.json` |

Each receipt records inactive consumers, no process/mount references, preserved source/unique evidence, exact regeneration inputs and removal of its owned runtime plus vulnerability/Java databases. Empty cache/docker-config directories were removed too. The native-binary scanner receipt historically retained verified binaries, pinned cosign and its private trust cache for staging/verification. After successful three-host consumption, `kubernetes1372-vendor-cleanup/receipt.json` separately removed the three binary blobs and cosign:343,461,888 allocated Linux bytes. Exact paths and per-file allocations remain in that receipt. Original backups, checksums, signatures, certificates and reports survive. The entire signature-cache remains protected because its shape check failed; it was not retried or counted as removed. Full results, manifests, failure witnesses and minimal verification evidence remain. Cleanup does not change any CVE finding or imply a new/global scan.

The observer's synthetic fixture cleanup removed3,721 logical file bytes. These are Linux/fixture measurements, not Windows/VHDX
space-recovery claims. No WSL shutdown, compaction, process termination or
unrelated/protected cleanup target was used.

The sole existing root is `/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025`,
filesystem UUID `3c792469-ea0e-4a2c-98e8-1185b141607b`, backed by
`F:\branconet-build-storage\native-build-20261025.ext4`. This task's leaf is
`platform-upstream-review-20261027/autonomous-hardening-20261028`. Minimal actual
receipts, source hashes, HMAC observations and recovery ciphertext remain for
qualification/recovery. Final scratch reconciliation follows the last consumer.

The worker2 package helper's first admission refusal is preserved: the permanent Ubuntu shutdown-wait helper was initially classified as an active package transaction. A narrow exact executable/argv/vendor-source/unit/state/lock identity check corrected that classification before any intent/ACK. The later exact transaction completed; native locks, APT pre-invoke state binding and all other transaction refusals remained intact. The first Kubernetes native carrier auth failure and all9 absent-stage observations remain separate failure evidence. No scripts, PLAN or MIGRATION_STATUS were changed by this documentation checkpoint.

## Post-core evidence checkpoint

Charts revision`1d2ab6fed53a90b1cef497907b707dcd1d137085` has actual validated FluxReady acceptance with Actions disabled. `tls-file-provider-redirect-final.log` passed with changed0: all12 leaves and strict HTTP-to-HTTPS redirects on all3 node addresses. The native Secret change adds only the public `bortus-https-redirect.yaml` key; all other Secret fields, UID and suspended BORTUS application release are preserved. The earlier8111 commit's missing Middleware CRD rejection and `tls-https-redirect-final.log` failure remain explicit failed evidence.

`flaresolverr-post-core-browser-and-boundary.json` now supplies an actual browser HTTP200/expected-page observation at1d2ab6, alongside UID/GID1000, zero effective capabilities, NoNewPrivs1, Seccomp2, absent token, stable Pod and blocked Mealie cross-namespace access. Earlier dd7/334d observations remain historical; this new request does not patch embedded Chromium or establish every browser operation.

The master post-core904e1dc cache attempt failed its physical-cleanup check. A separate read-only observation confirms33 exact qualified paths,1,620,156,416 allocated Linux bytes, absent; the original attempt remains failed and was not replayed. Snapshot directories`/var/lib/containerd-k8s/io.containerd.snapshotter.v1.overlayfs/snapshots/22` (3,235,840B),`/21` (48,611,328B) and`/20` (33,566,720B) remain protected. The exact33 absent paths and allocations are retained in `master-post-kubernetes-retirement-observation.json`. Worker2's2dae6569 attempt stopped at a native-child precondition after one acknowledgement; its full qualified123,252,736B is **not** claimed recovered. Neither failure permits raw deletion or a retry through another path.

Two more completed publisher cleanup receipts record177,889,280B (`publisher-cleanup-9b788639600e8944/receipt.json`) and355,782,656B (`publisher-cleanup-1e4df5fe64421238/receipt.json`) removed. Their exact per-file manifests remain hash-bound in the evidence index; original Git source/tools and unique witnesses survive. These and the separate343,461,888B vendor-artifact cleanup are Linux allocation measurements, not Windows/VHDX recovery claims.

At the earlier post-core checkpoint, native APT metadata cleanup was still in progress. Duplicate containerd release-copy cleanup has terminal acceptance on both nodes, as recorded below. The coordinating thread owns remaining APT terminal results. That checkpoint did not establish final disk acceptance. Preserve the25%+512MiB `f_bfree` guard, the additional 2 GiB final margin and the separate15GiB `f_bavail` floor. No earlier free-space snapshot is promoted to final acceptance.


## Earlier cleanup checkpoint before final headroom verification

The duplicate containerd 2.4.2 release trees under
`/opt/containerd-k8s/releases/v2.4.2` were removed after native and full 58
acceptance: **128,000,000 allocated Linux bytes on master** and
**127,987,712 on worker2**. Each result names the archive and four duplicate
binaries plus the two empty directories; installed runtime, configuration and
CNI are unchanged. The hash-bound result and accepted receipts are under
`containerd-release-duplicate-cleanup/{masternode,workernode2}-apply-result.json`
and `*-accepted.json` in the evidence index. This is separate from the earlier
protected snapshot-cache failures, which remain excluded and unchanged.

The b681 native-config transport repair completed at
`/etc/kubernetes/tmp/kubernetes1372-5q_tc2oa`. Its receipt records four removed
files totaling **9,666 logical bytes**, with no retained target. It does not
measure allocated directory bytes, so no 28 KB allocation claim is inferred.
The original carrier had a deterministic line 5 SyntaxError before any native
code or intent; the original source and failure remain intact. A separate
repair inventory/intent applied the unchanged allocation, exact regeneration,
full reference and live three-host gates. No hash mismatch or actual process
safety refusal was waived. Receipt SHA is
`0deeddb0050102ceff24f228a2544d95b266161e56425451456e54554e2d998c`.
Original 89's unowned configuration directory and all unrelated refusals remain
excluded. See `FAILED-NATIVE-CONFIG-RECONCILIATION.md`.

Scratch receipts confirm **40,960 allocated Linux bytes** removed by the original
scratch reconciliation and **24,576** by Kubernetes scratch reconciliation.
The four Kubernetes invocation trees 5ee18e…,89c1dc…,b70cc6…,b9a592… remain protected
by their original `/proc/1/cwd` permission-denied checks; their parent remains.
Exact paths, bytes and reasons are retained in the two indexed scratch receipts.
A separate completed full-reference check removed only the empty native dryrun
`/etc/kubernetes/tmp/kubeadm-upgrade-apply-dryrun2913256334`: **4,096 allocated
Linux bytes**. Its original diagnostic survives. No Windows/VHDX recovery is
claimed for any of these native measurements.

The format-compatible APT inventories qualified **58 master targets and 46
worker2 targets, zero retained**, with signed metadata and the exact installed
kernel 202 archives on master. These are inventory results, not cleanup totals.
Original admission/transport failures and inventories remain immutable. The
successor requires fresh signed hashes and package checks; its mountinfo EINVAL
handling requires a stable exited process without descriptors, executable,
memory mappings or mount namespace. No bad hash, permission denial or live
process reference was overridden. At this earlier checkpoint, per-file application was still in progress;
final disk acceptance and all previously documented vendor residual findings
remain open. Preserve the original 25%+512MiB floor, additional 2 GiB margin and
15 GiB usable-space guard until independently measured after completion.


## 2026-10-29 recovery and offload checkpoint — acceptance still open

Current charts/Flux revision is `1c6f142493685676f9d8fee339400e0fe8d22ee5`; earlier revisions above remain historical. Current Ingenium image `1925d5695fba242f4990748473f72d847276c10ae721be13173e974dc404ec50` has an actual nginx master/config/listener/route observation in `ingenium-1c6f-http2-observation.json`, SHA `efe35dcfad31fc59bd570e4032c8572dc05d8447d4c0d3dbf3c5f8f7b8cbbd74`. Its observed backend has no HTTP/2 listener. This assesses the existing Rapid Reset protocol mitigation, not a new vulnerability scan, patched package or zero-CVE conclusion.

`windows-bortus-https-os-trust.json` records Windows System.Net.Http default certificate validation: HTTP 301 preserves `/auth/login?maintenance=verify`, and HTTPS returns 200. No certificate bypass or authenticated session was used. This proves transport/trust and redirect behavior, not authenticated application acceptance.

All 28 fresh native backups completed at 09:32:57Z under `postcore-cleanup-20261029`. Storage SHA is `637b393ecde491bd59818229e3e200d47aa3ec2cbf2288d69086d06ea5d21643`; renewed manifest SHA `974c53fee4aeed789918fb0373a59bff22447a3e140d45fd3d22fb7c1973f455`; subsequent full validation SHA `ecba78657d63b30a2cb23e2910c618484c464a319ed94e38a55aa2bfcbd50aa8`. All original 219 identity rows remain bound with only the reviewed Ingenium three-field and proxy projections. The six-hour freshness requirement is unchanged; the original parent was not rebased. These online crash-consistent backups are not a new independent restore claim.

Worker2 APT now has **46/46 successful individual results**, totaling **475,537,408 allocated Linux bytes**. The evidence index binds each exact removed path/result hash. Master was separately still in progress at this checkpoint: its 3,137,536-byte `jammy-updates_universe_i18n_Translation-en` target is protected by a genuine PackageKit PID/unit transition refusal. No retry or all-target master acceptance is claimed.

Worker2's 19 closed files qualified at 623,443,968 allocated bytes. The encrypted NAS archive is 623,584,084 bytes, SHA `e97af7280651eb4ce14a3bfa9bd983455505740e4e1e285ef7f1a7acb3be7380`. All 19 were independently restored with complete authentication, byte/metadata parity and applicable journal/gzip checks; restore SHA `098cdafd51ab00e23420ddb1533aed3c9bdb83fe0f020d645e39853ab6526583` confirms scratch reconciliation. At that checkpoint, local retirement was still in progress: no final removal count or recovered-byte total is asserted. NAS ciphertext and recovery material remain required recovery artifacts.

The first Windows NAS-lock carrier failed before its child or any file attempt. Original source `89a2e783…`, invocation log and `path0.json` (SHA `99b425348f9398e838bbc5700d62099c794c2d8d96a50fa7cace5e3b4f3b470c`) survive. Canonical extended-UNC transport correction uses unchanged native helper `4442d412…` and runner `6bc657ab…`, with live NAS locks checked for every file. No native guard denial was bypassed.

That intermediate checkpoint left runtime, cleanup and disk acceptance open; the final receipts and measurements below supersede it. Preserve the 25%+512 MiB free-block guard, additional 2 GiB final margin and separate 15 GiB usable-space floor. All earlier failures, protected targets, Bazarr comparator failure and upstream residuals remain unchanged. Linux allocation totals do not establish Windows/VHDX space recovery.


## Completed native cleanup and final measured acceptance

Encrypted offload and independent restore completed for **19 worker2 files /623,443,968 allocated Linux bytes** and **3 master archives /109,346,816 allocated Linux bytes**. Exact paths, hashes and per-file allocations are in each `closed-file-offload/NODE/accepted.json` and the evidence index. All19+3 restored files passed full byte/metadata verification and applicable journal/gzip checks; plaintext restore scratch was reconciled. Active logs, installed runtime, user data and recovery ciphertext remain preserved.

APT terminal results now confirm worker2 **46/46**, totaling **475,537,408 allocated Linux bytes**, and master **57 completed**, totaling **605,425,664 allocated Linux bytes**. The one remaining master target, `/var/lib/apt/lists/ca.archive.ubuntu.com_ubuntu_dists_jammy-updates_universe_i18n_Translation-en` (3,137,536B), remains protected by the actual PackageKit PID/unit transition refusal. Independent untried targets completed; the refused target was never retried.

All five native Longhorn GC profiles completed with retained user snapshot names/UIDs/creation/spec, every durable BackupCR identity, two healthy RW replicas and the full core preservation gate. Only the exact already-marked-removed system snapshot was purged through the native volume-wide API. All user checkpoints and NAS backups survive. Physical snapshot parent/size changes are native coalescing behavior, not deletion of user checkpoint content.

| Profile | Worker1 observed root-free delta | Worker2 observed root-free delta | Result SHA prefix |
| --- | ---: | ---: | --- |
| sonarr | 66,547,712 B | 66,531,328 B | `57f320426a1f` |
| ingenium | 73,121,792 B | 73,175,040 B | `ca7a080b5c14` |
| radarr-data-0 | 37,720,064 B | 38,105,088 B | `64ec5835a6ad` |
| xteve-data-0 | -184,320 B | -147,456 B | `f55f4b739f2d` |
| ruckus-db-upstream-20261026 | -188,416 B | -167,936 B | `ab1d010649e0` |

These deltas include concurrent writes and are **not exclusive allocated-byte recovery claims**; the negative xteve/Ruckus deltas must not be described as recovered space. Sonarr/Ingenium used source55108b0a; the three added exact catalog entries used sourcee39441b7, with the original source frozen separately. All original gates remained unchanged.

The original GC qualification failed read-only because the API retained completed backup-history entries while the engine's active backup status was empty. Failure55b83450, original sourcef544a511 and diagnostic2e264106 remain preserved. The explicit `backup-status-repair` successor requires every API history entry to be Completed, integer100% and error-free while the engine status remains empty. Unknown, active or failed records still refuse; no actual busy backup was ignored.

Three empty fresh-backup scratch directories were removed: **12,288 allocated Linux bytes**, with exact paths in `post-core-recovery-scratch-reconciliation-receipt.json`. The12 closed-file scratch directories were subsequently removed: **49,152 allocated Linux bytes**, confirmed by `closed-file-scratch-reconciliation-receipt.json` (SHA `7499a14560f7053d9e874aef219c5d0d60fba0a8535ec8202b968904cd8df964`). Earlier protected scratch refusals, failed snapshot-cache targets and signature-cache shape refusal remain unchanged. Kernel198 headers and fallback boot components are preserved.

Normal Windows HTTPS/default OS trust evidence remains bound: HTTP301 preserves the query and HTTPS200 succeeds without certificate bypass; authenticated acceptance is not claimed. The final runtime and disk check below completed after these operations. The25%+512MiB free-block floor, additional2GiB final margin and separate15GiB usable-space floor remain unchanged. No Linux measurement is promoted to Windows/VHDX recovery.


### Final point-in-time runtime and headroom acceptance

`final-hardened-cluster-20261029.json`, SHA `09e2a1ac2fabd45bd2571def091a98a884bf9a5fa7c811b4a5e7d15986ff0d7f`, passed at **2026-10-29 10:51:27Z**. All original58 bound claim bindings and14 SMB volumes were preserved; desired controllers were available; FlareSolverr token absence, namespace ingress boundary and least-privilege process state passed. BORTUS remained held. This final receipt did not rerun browser compatibility; the separately recorded actual browser evidence retains its original scope.

| Node | Filesystem capacity | Free blocks, bytes | Usable bytes | Above25%+512MiB guard |
| --- | ---: | ---: | ---: | ---: |
| Master |115,702,075,392 |32,491,884,544 |27,175,247,872 |3,029,494,783 |
| Worker2 |115,702,075,392 |31,623,954,432 |26,307,317,760 |2,161,564,671 |

Both passed the unchanged **additional2GiB** final margin and separate **15GiB usable-space** floor. These are point-in-time Linux filesystem measurements: live workload growth continues, and no permanent reserve or Windows/VHDX recovery is asserted.

Fresh-backup scratch reconciliation removed3 empty directories/12,288B; closed-file reconciliation removed12/49,152B. Both preserved every original failed Kubernetes scratch tree and its parent where protected children remain. The exact path manifests and retained exceptions are hash-bound in the evidence index. No original refusal was cleared or retried. All16 offline volumes, Docker/Gluster data, user checkpoints/NAS backups, and198 fallback headers/images/modules remain preserved.

The available fixes and operational acceptance above do not erase residual security findings. Upstream vendor CVEs remain as documented; no new global scan or zero-CVE claim is made. Bazarr's strict post-core comparator remains **FAIL** for13 source-file metadata rows correlated with configured Sonarr, with no missing original rows/config/subtitles; the original baseline and comparator were not rebased or reclassified as passing.
