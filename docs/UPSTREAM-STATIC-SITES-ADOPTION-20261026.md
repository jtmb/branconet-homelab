# Static-site vendor image transition

Owner: maintenance chat `01a12045-bf7e-73b3-8557-752d17c72ffd`. All new generated
controls, sources, observations, scanner state and encrypted backups stay in
the existing F:-backed ext4 root recorded in
[the output inventory](TASK-OUTPUT-INVENTORY.md). Stage children are
`operator-control`, `control-source/upstream-static-sites-20261026`,
`upstream-static-sites-20261026` and `security-review-20261026`. They are children
of the same existing root, not additional output roots or drives.

Scope: aplb, lucinda-art-gallery, minecraft-website and santos-web. Their chart
values currently select one custom Nginx image and separate Longhorn content
claims mounted at `/usr/share/nginx/html`. Preserve every site's content,
configuration, Secrets, original resource identities and routes. The Minecraft
website is a static site; no game server is installed or restored by this work.

Compare maintained official vendor variants and current security findings before
selection. Use the existing trusted scanner binary and public vulnerability
database, with all new caches/HOME/TMPDIR under the declared root. No scanner
container, image build, dependency install, GitHub Actions or image publication
is introduced. Check C: and destination capacity before downloads, and retain
the source/tool/database provenance, exact finding rows and limitations.

Before image adoption, bind each live workload/claim/Secret identity, hash all
served content and configurations, validate Nginx configuration and actual
published/ingress routes, then take complete encrypted content backups through
quiescent read-only readers. Authenticate source archives and NAS read-back.
Only then publish reviewed chart changes through local validation → validated →
Flux. Repeat state/routes on adopted and distinct restart Pods. Preserve all
rollback artifacts and failures. Final IAB remains after implementation.

Regeneration uses the maintained qualification/cold-backup/scanner scripts with
their recorded exact phases, image/tool digests and private output paths. Keep
unique receipts, source manifests, keys and required encrypted recovery data;
remove proven reproducible inactive caches/scratch with exact path/byte receipts.
No recursive broad prune or Windows disk-recovery claim is authorized.

## Verified rollout — October 26, 01:41 UTC

All four sites now use the maintained official image
`docker.io/library/nginx:1.30.6-alpine3.24-slim@sha256:dede8895648b461178c3bc604f7eed4423efe5220b2c4d839f5eb3d34ac3f8f7`.
Its observed amd64 child is
`sha256:8f06fd647c6687eae0fd7bee8a43df66e61edb9f093bb0a9079d69cb355b879b`.
The previous custom image and recovery sources remain available; none was
rebuilt, pruned or presented as the current maintenance source.

The private charts pipeline published these exact revisions:

| Phase | Revision |
| --- | --- |
| Quiesce writers for complete backups | `3b2d83dcceacb124833a58cc482192199107a9ad` |
| Adopt official image and resume all four sites | `73dbbd10478482afe618eb1fb817102ee01cfcfa` |
| Distinct-Pod restart verification | `0ed2ad27ce0a32055c37c3e2d4d22026535a9b15` |

Local validation promoted the exact revisions to `validated`; Flux observed
the final revision and all four releases were Ready with one available replica.
GitHub Actions stayed off. Deployment, release, content PVC/PV, Service, ingress
and native Secret identities were preserved, as were Secret versions/content,
resource settings and the complete Nginx configuration. Changes were limited
to image selection, temporary replica counts and restart annotations.

| Site | Complete content bytes | Files | Route/asset checks per observation | Final Pod UID |
| --- | ---: | ---: | ---: | --- |
| aplb | 108295431 | 172 | 19 | `c80d0629-6b98-4387-8586-1c831adb6736` |
| lucinda-art-gallery | 200662514 | 198 | 20 | `ba17056b-1f7f-40b6-8ee9-5f0a06ea3ccf` |
| minecraft-website | 30993388 | 61 | 13 | `cd3d286c-1eb0-4e58-9eaa-7135d3cefe8d` |
| santos-web | 73884662 | 49 | 18 | `a291e4e3-9246-40b9-bc01-36c7a129ffc7` |

All **413835995 bytes / 480 files / 587 entries** matched the baseline after
adoption and on distinct restart Pods. Checks cover every content file's keyed
hash and ownership/mode, bounded symlinks, complete `nginx -T`, version 1.30.6,
all three published node routes, both HTTP host aliases, verified TLS hostname
routes, index bytes and referenced local assets. Each of the three observations
passed all 70 HTTP checks. This is backend/data/route acceptance; final Codex
IAB acceptance remains a separate end-of-implementation gate.

## Recovery and preserved failures

The four complete cold content archives total **414545520 encrypted bytes**.
Each original archive and its NAS copy passed full SHA-256 read-back and age
authentication. Temporary read-only readers were deleted by their exact UID;
no source files, data claims or original archives were removed. The recovery
destination remains the existing NAS folder
`\\TRUENAS\plex_smb_share\Branconet-Recovery-Backups\2026-10-25`.

The first two archives were fully written before the verifier rejected an
unrecognised tighter 1 GiB profile. Their original failed receipts and original
sources remain intact. The corrected verifier explicitly allows that complete
1 GiB profile; recovery rechecked controller/claim/reader identities, fully
authenticated the existing archives against fresh complete inventories and
removed the original readers. Separate recovery receipts bind the original
failed receipts by SHA-256. No duplicate content transfer was needed. Generic
4 GiB and Plex 16 GiB backup profiles were unchanged.

The final metadata archive is **3912836 bytes**, SHA-256
`3520e834bf44ffafe677115b724ec1ad831fbd2f027bdcad3c9f6f64d867230d`.
All tar members, its complete age stream and NAS read-back were verified. It
contains the private verification key only inside encryption, exact frozen
source versions, observations, original/recovery receipts and public scan
provenance. The existing Windows CurrentUser DPAPI recovery-key copy was checked
in RAM; it requires that Windows profile/master keys and is not a portable key
backup. Original WSL key material remains protected in place.

Private evidence relative to the declared output root:

- `upstream-static-sites-20261026/<site>/{baseline,after,restart}.json` and
  each site's `cold/*/{receipt,recovery-receipt}.json` where applicable.
- `control-source/upstream-static-sites-20261026/observer-manifest-r2.json`:
  frozen observer SHA-256
  `d83370d153e62804ae5a43bb34d254704448be4b0e3be79763ed767ffd3e8c8e`.
- `control-source/upstream-static-sites-20261026/backup-r2/manifest.json`:
  manifest SHA-256
  `8c6944b9acb53d70e26a1e22e9941caea7974ee3540a543eb4fc5954bb621f15`.
- `operator-control/smb-static-sites-copy-status.json`,
  `smb-static-sites-metadata-copy-status.json`,
  `static-sites-metadata-receipt.json` and
  `static-sites-post-cluster-health.json`.

## Security scope and remaining work

The selected Slim image's fresh scan completed with **no findings in its 21
detected Alpine OS packages**, no suppression and no CISA KEV intersection.
The database was updated `2026-10-25T19:10:35.479132794Z`; the scanner, image,
database/index manifests and result hashes are bound in the private receipt.
The Java identification index was recorded separately from the advisory DB.
Result SHA-256:
`7d32c992a59ba59a05ceeb0902685793755d2acc59c8900a7cce7fd3e98aa909`.
These findings do not prove absence of unknown vulnerabilities or cover the
remaining fleet, application content, or packages the scanner did not detect.

For the same Nginx version, the compared Debian variant reported 1 Critical and
59 High rows; full Alpine reported the High Brotli finding
`CVE-2026-111497` (`1.2.0-r1`, fixed in `1.2.1-r0`). The actual four Nginx
configurations contain no optional-module directives or loaders; all active
core behavior and content checks passed with Slim. The official
[Nginx security advisories](https://nginx.org/en/security_advisories.html) and
[vendor image variants](https://hub.docker.com/_/nginx) informed selection.
No used feature was removed to silence a finding.

At 01:40:52 UTC, all three nodes were Ready without pressure, all 55 PVCs were
Bound, all 34 HelmReleases and desired workloads were available, and attached
Longhorn volumes were healthy (41 total volumes). The two retained failed Seerr
diagnostic Pods are unchanged historical evidence. The refreshed full runtime
inventory covers 91 Running Pods and 68 distinct main/init/ephemeral image
references. Eleven third-party derivative chart transitions remain, along with
the owned-image publication gap, full security review and final IAB gate.
The overall five-milestone goal remains **active and incomplete**.
