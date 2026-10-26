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

Preparation only: no Homepage deployment or complete security acceptance is
claimed yet. The overall five-milestone goal remains active.

The fresh vendor scans completed: 2.7.0 has 6 High / 11 Medium / 1 Low rows,
including five High rows with package fixes not present in the published image.
The older official 1.13.2 has 7 Critical / 43 High rows. Latest Jackett has one
High row. Exact packages/fixes and result hashes remain in
`operator-control/homepage-jackett-vendor-findings.json`. No CISA KEV intersection
was detected in these three scans. Vendor ownership adoption does not imply
that those remaining upstream findings are patched; no bespoke rebuild is used.

The baseline passed with nine configuration entries / 4016 bytes, four service
groups, three bookmark groups and four widgets. Existing `.lan` HTTPS uses
Traefik's default certificate, without a named TLS Secret on these ingresses.
The observer records actual hostname/chain verification results, fingerprints
each node's certificate and requires continuity before sending requests after
adoption; it does not portray an untrusted certificate as trusted. Fixing the
existing trust gap remains separate security work. Initial observer sources and
failed baseline logs are preserved: the first required a named certificate that
the actual route does not configure; the second assumed an incorrect public
health response. Both vendor versions explicitly return `up`, which the corrected
observer now checks. Neither failed observer changed the cluster or source data.
