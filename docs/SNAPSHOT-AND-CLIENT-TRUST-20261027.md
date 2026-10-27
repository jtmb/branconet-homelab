# Snapshot controller and Windows trust checkpoint

Snapshot-controller **8.7.0 is deployed and separately verified**. The matching
LAN public root is installed in Windows CurrentUser/Root; a second apply changed
nothing. The fleet audit now covers all63distinct running-Pod image digests.
The full migration/security goal remains active.

## Snapshot change and preservation

The opt-in [Ansible playbook](../k8s-rewrite/ansible-playbook/playbooks/snapshot-controller-upstream-upgrade.yml)
uses [the guarded role](../k8s-rewrite/ansible-playbook/roles/snapshot_controller_upstream_upgrade/files/upgrade.py)
and committed upstream file/image pins. It defaults disabled. Eight official
source files were matched to independent Git-blob hashes and SHA256 before use.
Prepare, reviewed server dry-run, apply and a separate verify all passed.

The exact image is
`registry.k8s.io/sig-storage/snapshot-controller:v8.7.0@sha256:8511f417d0072efcd937aedd7cc79a937d5066e64ee17beb6097301c92742f19`.
Both replacement Pods are Ready/zero-restart and match the exact runtime digest.
The existing two replicas, RollingUpdate settings, arguments, resources, service
account and field owner remain. No forced ownership, RBAC expansion, owner
replacement or Flux adoption occurred.

Three new official group-snapshot CRDs were established before the image rollout.
They serve v1/v1beta1/v1beta2 with v1beta2 storage and no conversion webhook.
The original three ordinary snapshot CRDs and ClusterRole have no semantic delta.
All five existing target-resource UIDs survive; the three newly created CRDs have
their recorded new UIDs. The generated Deployment revision increments exactly once.
No group-snapshot capability or new snapshot/restore is claimed as tested.

The original class `longhorn-migration-snapshot`, snapshot
`migration-system/migration-proof-v1` and its content retain full keyed definition
fingerprints, original UIDs and Ready state. Preservation checks also match all
63Flux specifications,57PVCs/PVs,184native Secrets,49other workload specifications
and three node/boot identities. Native values remained in master RAM. Five old
resource definitions were age-encrypted, authenticated and retained for recovery:
50,494bytes, SHA256
`c8a9bc1c148f92c6a79b929662074a33b97f4d52cf49d7bceef4b024b560117b`.
The earlier fresh control-plane/NAS backup remains separately retained; no
independent restore or automatic CRD downgrade is claimed.

The first prepare stopped before mutation because a local variable shadowed the
HMAC key. The single variable-name correction and failed source/receipt remain.
The executed source SHA256 is
`0dbd198123e84b1f2da9466b20307c16d2b3c4359b6a09764c9b1f53d040a029`.
Exact private receipts: `platform-upstream-review-20261027/snapshot-upgrade/`
`{prepare,review-approval,apply,verify}.json` and the source-bound Ansible logs.

## Fresh security coverage

The same-feed exact-image comparison is **1Critical/46High/33Medium/5Low/2Unknown
→0Critical/2High/4Medium/0Low/2Unknown**. Earlier wording calling the combined
47Critical/High rows “47High” was incorrect. Raw findings remain unsuppressed.

BORTUS's unchanged cached image was scanned directly from its existing read-only
OCI layout, without another archive extraction, registry credentials, application
execution or deployment. All17blobs plus index/layout files match hashes and
identities before/after, and the current Pod/image/held-release binding matches.
The fresh result is5Critical/99High/160Medium/154Low/3Unknown, no CISA KEV match.
The stricter direct-reader limits are1GiB RAM/no swap/2CPU/128tasks, network
isolation and a2GiB fresh-analysis cap. Its old export/audit wrapper and limits
were neither changed nor invoked. The separate BORTUS application owner keeps
the production hold; a successful audit does not approve its unfinished release.

At05:59UTC, all63runtime digests have complete reports against the same pinned
r4feed, with immutable result hashes. The aggregate distinct-artifact package
rows are89Critical/2829High/3619Medium/2103Low/1427Unknown;2363unique CVEs.
These are inventory counts, not an exploitable-path count or clean-cluster claim.
FlareSolverr's current/latest official image still has the known-exploited
Chromium CVE-2026-87491. No unknown-zero-day absence is claimed.

Public current-tag review matched21deployed tags to their existing pinned
digests; two other app references are digest-only. Current official release
metadata identified newer Jackett0.24.2918 and Unpackerr1.0.0, both digest-bound
and scanned without production changes. Jackett retains the same two High curl/
libcurl findings and offers no High/Critical improvement. Unpackerr reduces
5→4High,16→10Medium, fixing its x/net finding while four Go stdlib rows remain.
No derivative rebuild or unqualified major-version rollout occurred.

Unpackerr's live configuration inspection found one Sonarr and one Radarr entry,
no watched folders/hooks/Whisparr, metrics disabled and original native environment
bindings. Its config contains a nonempty listen address: v1 would enable a web
server that v0.16 did not enable with metrics off. Qualification must explicitly
preserve headless behavior, account for changed extraction limits and complete
the isolated extraction plus live config/integration/restart checks before Flux
adoption. The17,148-byte config and both original storage claims remain untouched.
[Vendor upgrade contract](https://unpackerr.zip/docs/install/upgrading/).

## Windows trust and precise client limitations

The original pending CryptoAPI installation completed after James's OS approval.
The public root SHA256 is
`79b3cf11aed6c404885e555ceff33819ffa4ca534959f00f80b16e09927e2fab`.
Only CurrentUser/Root was used: no private key import, certificate removal or
Windows execution/security policy change. A second exact apply found it already
trusted and made zero changes. A duplicate pending installer had earlier been
stopped by exact owned PID; its cancellation/failure evidence remains.

Default Windows curl/Schannel requests initially failed all60checks with
`CRYPT_E_NO_REVOCATION_CHECK`: this local CA publishes no CRL/OCSP endpoint.
Those failures remain. The request-only `--ssl-revoke-best-effort` comparison
then passed all20hosts across all three node addresses, using the OS trust store,
chain and hostname verification; all expected HTTP statuses match. No custom CA
override or insecure-TLS option was used. This comparison tolerates missing/offline
revocation distribution points; it is **not strict default-curl acceptance or
browser acceptance**. No persistent client setting changed. Cert-manager's CA
issuer does not generate revocation services itself, as documented by
[cert-manager](https://cert-manager.io/docs/configuration/ca/); the request option
is described by [curl](https://curl.se/libcurl/c/CURLOPT_SSL_OPTIONS.html).

Private receipts in `lan-tls-20261026`:
`windows-apply-current-r4.json`, `windows-idempotent-after-approval-current-r4.json`,
`windows-normal-https-current-r4.json` (strict failure) and
`windows-request-scoped-https-current-r4.json` (explicit request-only mode).
Final Seerr/YTPTube IAB remains after implementation, per James's instruction.

## Cleanup, recovery and remaining work

All generated work reused the single authorized F-backed root/UUID in
[the output inventory](TASK-OUTPUT-INVENTORY.md). After successful scans and
source-bound Ansible completion, full owned-path/inode/FD/maps/mount checks
removed exactly1,679,360allocated Linux bytes:

- `security-review-20261026/cache-r4/fanal/fanal.db`:1,646,592B.
- Its empty `fanal` directory and scanner `tmp`/`home`:12,288B.
- `platform-upstream-review-20261027/flux-ansible-scratch/{home,local,tmp,cp}`
  and the empty scratch parent:20,480B.

Exact absolute paths and preservation/regeneration proofs are in
`operator-control/snapshot-review-scratch-{plan,reconciliation}.json`.
The old `operator-control/tmp/system-commandline-sentinel-files` and parent
remain: creator/regeneration and complete inactive Windows-handle proof are
missing. Original image/layout/archive, application/runtime/source/lockfiles,
native data, rollback/failure evidence, reports and minimal receipts remain.
No node image/data prune or Windows disk-recovery claim occurred.

New evidence-only encrypted package:3,861,620bytes, SHA256
`bb9b153689b460d90378236f182cab71579624d81ca09a2693379adb249c0b30`.
All members and full age authentication passed, followed by full NAS ciphertext
read-back authentication. Prior metadata archives, scanner DBs and the1.15GB
BORTUS archive/layout were referenced rather than copied inside it. Receipts:
`operator-control/snapshot-review-metadata-receipt.json` and
`smb-snapshot-review-metadata-copy-status.json`. Originals remain.

Remaining acceptance gates:

1. Longhorn safe capacity/recovery and owner-preserving upgrade. Last read shows
   master4,493,698,049B and worker2 1,557,685,249B short of their unchanged floor,
   before extra upgrade/rebuild headroom. No spare VG extents; inspected replica
   relocation is insufficient. No pruning, threshold or replica reduction.
2. Unpackerr1.0 compatibility qualification and any justified upstream chart
   update; preserve accepted service/data while that work proceeds.
3. Vendor/host exceptions: FlareSolverr's current official KEV, remaining image
   findings, five Ubuntu Pro ESM Apps updates per host pending entitlement, and
   BORTUS findings with its separate owner. Do not describe these as patched.
4. Final whole-fleet/data/routes/restart reconciliation and Seerr/YTPTube IAB.
   Windows root installation is complete; strict Schannel revocation remains a
   documented client limitation. The full goal stays active.
