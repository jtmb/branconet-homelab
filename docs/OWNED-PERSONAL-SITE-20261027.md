# Owned personal-site release — October27, 2026

The personal site now runs from its owned repository and existing Docker Hub
publication route, on maintained Nginx1.30.6 Alpine and jQuery4.0.0. Its original
text, navigation, profile image, CSS and application script remain. No application
PVC, credential, permission identity or database/schema was changed.

- Source: [jtmb/jtmb-dev](https://github.com/jtmb/jtmb-dev/tree/5989a1491415532244ef9c67635e7c72437387ab), commit `5989a1491415532244ef9c67635e7c72437387ab`.
- Runtime: `docker.io/jtmb92/jtmb-dev:git-5989a1491415532244ef9c67635e7c72437387ab@sha256:ac5cdc8d7e1bb7d6a5bcea08d4e379ea63f2ec1e7ae93a267258a9c97593d830`.
- Maintained base: `nginx:1.30.6-alpine3.24-slim@sha256:dede8895648b461178c3bc604f7eed4423efe5220b2c4d839f5eb3d34ac3f8f7`.
- Production charts commit `8a347e9aeedce8163177aad4b0bc06fe023d8816`; distinct restart/current main/validated/live `1b66531bffd2fd7024a46d5e8686505d6ec8f137`.
- Actual production Pod `8681f5ba-4ed1-4b81-a82d-dd459916dc15`; restarted Pod `8c60b69f-3ef3-4891-ac45-25db9f9b7fc3`.

## Source and security changes

All eight original committed application files matched the live image by canonical
Git-blob hash before changes. Windows checkout CRLF representation was treated
separately; no global Git setting or user working file was normalized.
The new owned Dockerfile copies committed static source/configuration onto the
pinned maintained base. Build definition, dependency locks/provenance, publisher
and update instructions live in the owned repository. GitHub Actions remains off
for charts and all three owned-image repositories, verified through the API without
changing their settings. Existing Docker Hub credentials were consumed in memory;
no plaintext credential file, new registry or saved-image deployment was used.

[jQuery2.x is unsupported](https://jquery.com/support/). The original2.1.4 bundle
matched six published GitHub advisory records, including duplicate advisories.
The replacement4.0.0 npm distribution passed its SHA512 package integrity and an
independent byte comparison with the official CDN; its exact script SHA256 is
`39a546ea9ad97f8bfaf5d3e0e8f8556adb415e470e59007ada9759dce472adaa`.
The license is bundled, and package-lock.json/dependencies.provenance.json capture
its version, download inputs and advisory comparison. The exact4.0.0 advisory
query returned no matches. Modernizr's existing2.8.3 custom browser bundle also
returned no matching advisory and remains unchanged.

Both HTML pages reference the maintained script; the home page's missing
Modernizr path is corrected. Cached old script URLs receive relative308 redirects
to the new/correct assets, preserving HTTPS. No vulnerable old jQuery bundle is
shipped. The first published candidate was superseded before any deployment when
source review identified default absolute redirects could construct HTTP URLs
behind TLS termination. Its source, registry proof, reason and logs remain; only
the corrected5989a149 image was promoted.

The exact promoted image scan reported no CVEs across21OS packages and one Node
package (jQuery), with no suppression or KEV match. The pinned feed was within its
24-hour freshness bound at scan time. This does not claim unknown zero-days absent.

## Actual acceptance

The original site passed66HTTP/strict-TLS checks before promotion. Production and
its distinct restart each passed84checks through all three nodes: every committed
asset, home/about, both compatibility redirects, correct content hashes and trusted
hostname-verified HTTPS. Native Nginx reports1.30.6 and its configuration check
passes. All ten assets and the exact committed Nginx configuration match the source.
Six unchanged original assets preserve bytes, owners, groups and modes; two HTML
script references and the replaced library are the reviewed changes. A fresh
source build has new image-file timestamps; unchanged mtimes are not claimed.
Deployment, Service, Ingress and HelmRelease identities, all unrelated Deployment
fields/resource limits and existing native Secret identities/resourceVersions/types
are unchanged. The site has no application PVC, environment credential or schema.
No browser acceptance is claimed before the remaining implementation is finished.

Evidence root:
`/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025/owned-jtmb-dev-release-20261027`.
`verify-owned-site-release.py` is the frozen executed observer; baseline,
production, restart, dependency and exact source/registry/rollback receipts remain.
A separate operator-only qbit publisher fix at `c110a49b84bf5611958435fae4cd4de40a797dc1`
handles canonical Windows checkouts for future releases; only ops code/docs changed.
The accepted qbit application source, Dockerfile and production image are unchanged.

## Cleanup and recovery

All bulk work stayed on the existing F-backed task root. Both builders had3GiB
RAM/zero swap,1.5CPU,512processes and2GiB allocated budgets, preserving15GiB on C:
and both F: filesystems. Their exact containers were stopped/removed. No host npm
install/dependency tree was created; existing Strata and other workloads continued.

Removed **418623488 allocated Linux bytes**, with exact paths/creator/inode/hash/
process/FD/maps/mount/container checks and regeneration instructions in:

- `operator-control/owned-jtmb-03fbf34-build-scratch-reconciliation.json`:31567872B, first terminal builder's state/context/client/socket.
- `operator-control/owned-jtmb-5989a14-build-scratch-reconciliation.json`:31461376B, promoted builder's equivalent scratch.
- `operator-control/owned-jtmb-publisher-scratch-reconciliation.json`:355409920B /1580paths, two successful source/tool/empty publisher exports.
- `operator-control/owned-jtmb-review-scratch-reconciliation.json`:184320B /4paths, regenerated scanner cache and empty directories.

The initial cache guard retained both whole target sets before deletion: it had
been written for root/UID1000 files and found Nginx UID101 empty cache directories
and OverlayFS0/0 character whiteouts. Creator reconciliation proved the exact
Nginx account/cache locations and kernel whiteout metadata inside the two private
terminated builders. Every other source/inode/process/container/mount check was
preserved before same-target cleanup. Original failed guard/source/receipt remain;
no workload was stopped or policy rejection bypassed to force deletion.

Original source/Git objects/lockfiles, old images/rollback sources, unique source/
registry/resource/scan/failure/validation receipts and required runtime remain.
Existing `operator-control/tmp/system-commandline-sentinel-files` stays retained:
creator/regeneration and complete inactive Windows-handle proof remain unresolved;
its parent is not empty. No old failed cache, shared image, volume or user data was
pruned. Linux allocation recovery is reported separately from Windows free space.

Recovery metadata:3707988bytes,
SHA256`036351dace64029cb4c3f2a8374d7fd0639ce2e354fe6bb841d9be33a1f9d53f`.
Every metadata member and full NAS ciphertext read-back authentication passed,
using the existing verified protected recovery-key backup. Prior cold ciphertexts
were not duplicated into this checkpoint; originals remain.

At01:14UTC: three Ready/no-pressure nodes,57Bound claims, all30HelmReleases and
all Kustomizations Ready;43Longhorn volumes total,27attached healthy and16detached.
Four older failed diagnostic Pods remain preserved. This also corrects earlier
wording that incorrectly called all43volumes attached; the actual source health
checks and stored snapshots correctly distinguished the states.

Ruckus's owned-source transition, remaining platform security, Windows client
trust and final IAB remain open. The BORTUS production hold remains with its
separate owner. The full goal stays active.
