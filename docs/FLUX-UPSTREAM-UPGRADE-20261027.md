# Flux 2.10 upstream upgrade and fleet security checkpoint

Flux 2.10.0 is deployed and accepted on the existing three-node cluster.
The upgrade finished at October27,04:09:50UTC. All seven replacement controllers
are Ready with zero restarts and verified immutable runtime image identities.
No application rollout, native Secret change, claim replacement, node restart,
image prune or BORTUS release adoption occurred. The full migration/security
goal remains active; this checkpoint does not establish clean cluster security.

## Applied change and repeatability

The [official release](https://github.com/fluxcd/flux2/releases/tag/v2.10.0)
was published October26,15:37UTC. Its supported Kubernetes1.37 path includes this
cluster's1.37.1. The actual43-object installation contains **15CRDs**, including
`artifactgenerators.source.extensions.fluxcd.io`; an earlier observer's14-count
excluded that exact group suffix. The corrected inventory was validated against
the actual vendor bytes. The initial14-count guard refused before any mutation;
its original source and failed receipt are retained.

The opt-in [Ansible playbook](../k8s-rewrite/ansible-playbook/playbooks/flux-upstream-upgrade.yml)
and [operation](../k8s-rewrite/ansible-playbook/roles/flux_upstream_upgrade/files/upgrade.py)
provide prepare/apply/verify phases. The
[committed pins](../k8s-rewrite/ansible-playbook/roles/flux_upstream_upgrade/files/pins-v2.10.0.json)
record all seven index, amd64 manifest and configuration digests, compressed-layer
estimates and the exact public manifest URL/SHA256. Materialize those public inputs
inside the same authorized output root before a new reviewed operation; do not
substitute `latest`. The default input paths identify the retained executed inputs.
The prepared evidence directory is single-use: never replay a completed or
interrupted apply marker. A future update requires a fresh baseline/review within
the same declared root, not a source reset or second output root.

The manifest's SHA256 is
`a8c838ccd9be5d30eba9df87cd229b7c4eb80c0049fba1bc3b9840829f267f28`.
All43 existing objects retain their UIDs and the original `kubectl` server-side
Apply manager; no force-conflicts or competing Helm ownership is introduced.
The reviewed differences are15official CRD schema updates, replacement of the
unused `serviceaccounts/token` create rule with `subjectaccessreviews`, four
official HTTPS Service-port additions, and seven image-only Pod-template updates.
Existing controller args, ports, resources, security and unrelated settings stay
unchanged. No deprecated notification fields/instances, object service accounts,
remote ConfigMap authentication or image-reflector objects required conversion.
All old stored/served CRD versions remain supported. Alerts/Providers now also
serve/store v1 while continuing to serve v1beta3.

|Controller|Accepted upstream version|
|---|---|
|helm|1.7.1|
|image automation|1.3.0|
|image reflector|1.3.0|
|kustomize|1.10.1|
|notification|1.10.0|
|source|1.10.1|
|source watcher|2.3.1|

## Recovery and live acceptance

Before mutation, a fresh etcd3.7.3 snapshot and46configuration/PKI/encryption files
were encrypted and fully authenticated off-node. The76,921,380-byte ciphertext
has SHA256`de348e280924bfaa4637aaeb4f94cef4396612be973eda0732209fa5516ee268`.
The NAS copy passed full hash/read-back decryption authentication using the
already protected recovery key. The original local receipt truthfully retains
`nas_copy_verified:false`; the separate completed NAS receipt establishes the
subsequent copy. This is not an independent restore or application-quiescence claim.
Original remote plaintext was removed by the existing backup role.

The43 original Flux objects are separately retained only as authenticated
encrypted rollback bytes, SHA256
`7194c5b0a977f3c94f43afb2252c65a422bda9c4ca1580b6577d2b87a7b19fc2`.
No native Secret values, full environment snapshots or plaintext PKI were saved.
The operation deliberately prohibits automatic CRD downgrades. A failed controller
can return to its previous UID/spec-bound image without pretending a schema/data
rollback has been qualified. No rollback was needed.

Actual Ansible prepare, apply and verify completed successfully. The successful
prepare was a complete API server-side dry-run, reviewed before mutation and
repeated immediately before apply. Supporting objects were applied first;
controllers rolled individually with a bounded Ready/image check before the next.
The final observer verifies36supporting objects exactly against their reviewed
server results. For seven Deployments, the only extra metadata change was the
expected **single revision increment**, proved against decrypted originals in RAM
and the `kube-controller-manager/Update` field owner. Every other field matches
the reviewed API result. The first exact-metadata mismatch receipt remains;
it was not hidden or passed by broadly ignoring annotations.

Before/after equality passed for63Flux specifications,57PVCs,57PVs,
50application workload specifications,184native Secrets and3node/boot identities.
Native values were compared through keyed HMACs, never exported. BORTUS remains
suspended; the old migration source also retains its original suspension.
All30HelmReleases remain Ready, with the intentional BORTUS hold unchanged.
Fresh explicitly requested reconciliations passed for `branconet-charts`,
`migration-releases` and `qbit-monitor`, with matched last-handled request tokens,
unchanged specifications and observed generations. Charts main/validated/live
remains`3a8de93a4034780519bac191bf4a02b4a4c96f96`. Actions was not used.

## Fresh security results and remaining work

The seven exact replacement images were scanned against the same verified
October27,01:25UTC feed as the old runtime images. Previous package/target rows
totaled94High/151Medium/83Low/20Unknown; current results are **six Unknown rows**,
with no Critical/High/Medium/Low or CISA KEV matches. Source-watcher has no
findings. Unknown rows remain visible; this is not a claim that undisclosed
vulnerabilities do not exist.

The fresh post-upgrade fleet binds87Running Pods to61distinct actual runtime
digests. **60have complete same-feed scans; one BORTUS cached-image scan remains
unknown** because its registry returns authentication failure. Its historical
cached audit remains evidence, not a fresh scan. No mutable tag was guessed and
no incomplete scan was counted as clean. Reused reports require exact digest,
same feed and matching result hashes; unchanged images were not needlessly rescanned.

The60covered images contain85Critical/2764High/3462Medium/1952Low/1422Unknown
package/target rows, representing2363unique CVEs. These are raw scanner records,
not2363 independently confirmed exploitable application paths. Existing module
attribution, vendor backport and unsupported-release exceptions still require
reconciliation. One CISA KEV match is **CVE-2026-87491 in FlareSolverr Chromium**:
installed152.0.7977.82, listed fix153.0.8010.52. Both official `v3.5.2` and `latest`
still resolve to the deployed September12 image digest. The upstream release
check and registry/configuration hashes confirm there is no refreshed image at
those tags. No bespoke third-party rebuild, silent shutdown or clean-security
claim was substituted. This remains an explicit unresolved finding.

Remaining: compatible platform/sidecar updates and vendor-finding reconciliation;
Longhorn capacity/recovery prerequisites and upgrade; Windows LAN root trust;
final Seerr/YTPTube IAB and whole-fleet acceptance. BORTUS application release
development/adoption remains with its separate owner. NAS media stays on SMB CSI.
Privileged capacity inspection found no free VG extents on the two smaller nodes;
other listed devices are active encrypted Longhorn devices, not spare disks.
No eligible source/data deletion or image-pruning permission was inferred.

## Evidence and cleanup

All new evidence stays in the existing single F-backed root under
`platform-upstream-review-20261027`, `security-review-20261026` and
`operator-control`. Main receipts are `flux-upgrade/{prepare,review-approval,
apply,verify,fresh-reconciliation,server-object-adoption,
controller-revision-reconstruction}.json`, `fleet-after-flux-security-summary.json`,
the65individual scan directories and their raw Results-only files, the frozen
executed source and all actual Ansible logs/source bindings. The fleet scanner
unit's successful termination does not override its one failed coverage receipt.
No plaintext application/runtime snapshots or secrets were committed.

Cleanup removed **30,310,400allocated Linux bytes** after all scanner and Ansible
processes were terminal and full inode/FD/maps/mount/source/owner checks passed:

- `security-review-20261026/cache-r4/fanal/fanal.db`:30,277,632B.
- Empty `cache-r4/fanal`, scanner `tmp` and `home`:12,288B.
- Empty `platform-upstream-review-20261027/flux-ansible-scratch` and its
  `home`, `local`, `tmp`, `cp` children:20,480B.

Exact before/after protected hashes and removed paths are in
`operator-control/flux-fleet-scratch-{plan,reconciliation}.json`.
Required vendor inputs, scanner feeds, frozen source, raw findings/failures,
encrypted rollback/control-plane/NAS backups and unique receipts are retained.
`operator-control/tmp/system-commandline-sentinel-files` and its parent remain
for the previously recorded creator/regeneration/Windows-handle proof gap.
No Windows disk recovery is inferred from these Linux allocation measurements.

The new evidence-only recovery package is44,964,772bytes, SHA256
`e654ad8469b426153e28e8cc5b05619fce690c0f350643a90c7748df7516a5f6`.
Every member/source hash and full age authentication passed, followed by full NAS
hash/read-back authentication. The prior control-plane ciphertext, older metadata
archives and scanner DBs were not duplicated inside it. Exact local/NAS proofs:
`operator-control/flux-fleet-upgrade-metadata-receipt.json` and
`smb-flux-fleet-upgrade-metadata-copy-status.json`. Source originals are retained.
