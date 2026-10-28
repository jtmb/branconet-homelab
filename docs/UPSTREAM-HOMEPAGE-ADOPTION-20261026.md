# Homepage maintained-vendor transition

Owner: maintenance chat `01a12045-bf7e-73b3-8557-752d17c72ffd`. Generated outputs
reuse the existing F:-backed ext4 root in [the inventory](TASK-OUTPUT-INVENTORY.md).
New children: `upstream-homepage-20261026` for private observations/cold archives
and `control-source/upstream-homepage-20261026` for immutable source/manifests.
Controls reuse `operator-control`; vendor scans reuse `security-review-20261026`
and its existing immutable public advisory/Java-identification databases. No
dependency installation, derivative build or new publication route is introduced.

Candidate: maintained official Homepage 2.7.0, index
`19c5c09184458a41b7b5915e71463a39f36cd33540f41bdbed008791b8182d5f`,
amd64 child `f1c9e802a0b9de6f64ef8d3e3d3aac4283f250e0a8ff5ebd170d791811431c99`.
[Official release](https://github.com/gethomepage/homepage/releases/tag/v2.7.0)
updates Node and application dependencies. Version 2 introduces optional
authentication; [official configuration](https://gethomepage.dev/installation/)
requires explicit enabling and credentials. Preserve existing native Secrets,
allowed hosts, auth/MCP settings, rendered configuration, Kubernetes RBAC,
original content claim and HTTP/TLS routes. Do not invent credentials or enable
new services. The older maintained 1.13.2 image is compared, not silently selected
in preference to the requested compatible upstream security updates.

Before deployment: compare all configuration content, native Secret contents by
keyed hashes, original resource identities, existing HTTP/TLS routes and the
native services/bookmarks/widgets APIs. Quiesce only Homepage through Flux, then
capture/authenticate its entire original Longhorn claim and NAS recovery copy.
The explicit `upstream-homepage-20261026` cold profile pins the current custom
image and original controller/release/claim/node UIDs; it retains the complete
generic 4 GiB bound and UID/GID 1000 read-only reader. Other profiles are unchanged.
Only after those gates, adopt the version/digest through the existing private
charts local validator → validated → Flux pipeline. Repeat the state/routes on
adopted and different restart Pods. Keep final Codex IAB after implementation.

Regeneration: maintained `qualify-upstream-homepage.py` baseline/after/restart
with exact Flux revisions and private output/key; the recorded cold helper
command and immutable source manifest; maintained `scan-maintained-apps.py
homepage-jackett` in the recorded bounded user unit with pinned public inputs.
Preserve source, lockfiles, originals, keys, distinct failures/receipts and
required recovery/runtime artifacts. Reconcile only proved inactive reproducible
analysis caches and empty scratch with exact path/byte receipts at the checkpoint.

**Backend adoption is verified; full security and final browser acceptance remain
open.** The overall five-milestone goal remains active. The preparation and
diagnostic history below is retained alongside the final result.

The fresh vendor scans completed: 2.7.0 has 6 High / 11 Medium / 1 Low rows,
including five High rows with package fixes not present in the published image.
The older official 1.13.2 has 7 Critical / 43 High rows. The compared Jackett
0.24.2900 candidate has one High row. Exact packages/fixes and result hashes remain in
`operator-control/homepage-jackett-vendor-findings.json`. No CISA KEV intersection
was detected in these three scans. Vendor ownership adoption does not imply
that those remaining upstream findings are patched; no bespoke rebuild is used.
Live registry inspection subsequently confirmed Homepage's `latest` resolves to
this same 2.7.0 digest. Jackett's current `latest` is newer, 0.24.2910-ls16 at
index `19d90927b95397f2d1364e4999e11456abdbbb382b54cd765fc3b3da24d7088b`;
that newer Jackett image still needs qualification before its own transition.

The baseline passed with nine configuration entries / 4016 bytes, four service
groups, three bookmark groups and four widgets. Existing `.lan` HTTPS uses
Traefik's default certificate, without a named TLS Secret on these ingresses.
The observer records actual hostname/chain verification results and fingerprints
each node's certificate; it does not portray an untrusted certificate as trusted.
Fixing the existing trust gap remains separate security work. Initial observer sources and
failed baseline logs are preserved: the first required a named certificate that
the actual route does not configure; the second assumed an incorrect public
health response. Both vendor versions explicitly return `up`, which the corrected
observer now checks. Neither failed observer changed the cluster or source data.

The original fingerprint-continuity attempt then stopped before HTTPS requests:
Traefik's generated fallback certificate had changed. Public-certificate
inspection on all three nodes confirmed both subject and issuer are exactly
`TRAEFIK DEFAULT CERT`; no named Homepage TLS Secret exists. This matches
[Traefik's documented generated fallback](https://doc.traefik.io/traefik/v2.11/https/tls/).
The corrected observer retains every fingerprint, preserves the baseline's
actual trust/error status and, before requests, accepts an untrusted response
only for this existing no-Secret route with verification error 18 and that exact
generated subject/issuer. It cannot accept a formerly trusted route becoming
untrusted. All actual native Secret/resource/configuration/API comparisons remain
exact. This separates generated certificate observations from application
credential preservation; **authenticated TLS remains explicitly unaccepted**.
All earlier failed observations and exact sources remain preserved.

Official-image adoption `5535b319982a4f73c106b829d42b073c0773f9ca` passed the
state/API/route comparison on Pod `b6dd8733-ee52-443f-9d29-c3750de6d892`, running
vendor Node `v24.22.1`. All configuration, native Secrets, original resources,
Kubernetes RBAC and native API results matched. The cold archive is 5459460
bytes, SHA-256 `e19a5076063ece8d7e211e9b1d739322eff2e5f98e8cff720cab42bfb97a49e7`,
fully authenticated both locally and after complete NAS read-back. The original
UID-bound temporary reader was deleted.

## Final checkpoint, October 26 02:22 UTC

Restart revision `fc13b77609f8f21ce63c93e5895c86237d8e04d7` reached private
main, validated and live Flux. Different Pod
`c607e7ab-dcee-4b83-b1c6-95cc55fa7192` passed all nine configuration entries,
native Secrets, original controller/release/PVC/PV/Service/ingress identities and
specifications, Kubernetes RBAC, four service groups, three bookmark groups and
four widgets. Native API response HMACs matched exactly; twelve HTTP/HTTPS
root/health checks passed across the three nodes. The complete cold archive
preserves 5439007 file bytes across ten files, including mutable log state;
the observation comparison preserves the 4016 configuration bytes separately.
No account, credential, auth/MCP setting, resource limit, data claim or route
was replaced. No third-party image was rebuilt or published by this work.

Final recovery metadata: 1382948 bytes, SHA-256
`3c52f9228ea870ef11464bec956ea3b83ed41471300bf863de7178599ffeb377`.
All members and the complete ciphertext stream passed authentication and NAS
read-back. Original key material and archives remain. At 02:22:04 UTC all three
nodes were Ready without pressure, all 55 PVCs Bound, all 34 HelmReleases and
desired workloads available, and attached Longhorn volumes healthy (41 total).
The two old failed Seerr diagnostic Pods remain untouched.

The refreshed runtime inventory covers 91 Running Pods and 68 distinct main,
init and ephemeral image references. Ten third-party derivative chart transitions
remain: jackett, mealie, pihole, plex, qbittorrent, ruckus-db, tautulli,
vaultwarden, wordpress and xteve. The first-party publication route/credential
gap remains; a metadata/key-name-only native Secret inspection found settings
named `docker.yaml` and `TAUTULLI_DOCKER`, not verified publisher credentials.
No credential values were returned or used. This is not an exhaustive claim
that no credential exists elsewhere.

## Advisory-input integrity correction

The first checkpoint cleanup removed 798720 allocated bytes of proved inactive
analysis cache/empty scratch, then its protected-file comparison failed. A
separate read-only recheck found the primary advisory DB's bytes no longer
matched its original downloaded SHA, while its metadata, Java index, scanner,
source and report bindings matched. No cause was established. The original
1637195776-byte DB and its metadata were preserved with the same inode, size and
observed SHA in `security-review-20261026/cache/db-integrity-failure-20261026`.
No failure state was deleted and no mismatching digest was adopted as trusted.

A new official feed was downloaded and verified by its complete OCI layer and
two stored-file SHA read-backs. Current manifest:
`sha256:df325edea0d1f66994a99d0b40bd279d8e955489453586de27b949b958e74c8e`;
advisories updated `2026-10-26T01:20:01.38093772Z`; stored DB SHA-256
`feefbadc2ac95624d885203a353f131072c2ee4a03700d8ff4462151abc4ce0a`.
The deployed Homepage digest was rescanned with both database directories mounted
read-only. Full input hashes matched again after scanning and after final cleanup.
The revalidated result remains **6 High / 11 Medium / 1 Low**, five High rows
with package fixes, no CISA KEV intersection; result SHA-256
`e736421578acf53cfa06e2392f0566e555ac4bf1714cc35d755f1c9be278b1fe`.
The original scan reports remain historical; use
`security-review-20261026/apps-homepage-current-r3-0/receipt.json` and
`public-inputs-r3-receipt.json` as the current bindings.

| Remaining High finding | Installed package | Reported package fix |
| --- | --- | --- |
| CVE-2026-102276 | brace-expansion 5.0.9 | 5.0.10 (same major) |
| CVE-2026-102278 | brace-expansion 5.0.9 | 5.0.11 (same major) |
| CVE-2026-93748 | http-cache-semantics 4.2.0 | None reported |
| CVE-2026-109869, two rows | undici 6.28.0 and 8.11.2 | 6.29.1 and 8.12.2 |
| CVE-2026-19534 | undici 6.28.0 | 6.28.1 (same major) |

These are vendor-image findings, not proof of exploitation or reachability.
No package patch is injected into this third-party image. The vendor's current
published release still contains them. Authenticated TLS is also unaccepted
because of the existing generated self-signed certificate. Migration acceptance
does not waive either security exception, whole-fleet review, or final IAB.

The new integrity/scan proof is retained separately from its parent metadata in
a 307476-byte encrypted supplement, SHA-256
`98d8fadce0b6d567500d8f2687ee063097fb933e9a2920155cdeaf7d9739648e`,
also fully authenticated and verified on NAS. It duplicates no database binary
or cumulative ancestor archive. A final cache/empty-scratch lifecycle removed
352256 more allocated bytes and passed all protected input hashes. Total
checkpoint removal: **1150976 allocated Linux bytes**, with no Windows recovery
claim. [Exact paths and retained exceptions](TASK-OUTPUT-INVENTORY.md#homepage-checkpoint-reconciliation-october-26-0222-utc).
