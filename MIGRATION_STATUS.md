# Migration and maintenance status

**October25 22:24 UTC:** FlareSolverr and http-echo joined Whoami, Seerr and
YTPTube on official upstream images. Latest private source is
`5cfa97c446035d403f3486a9786b53f71cb62872`. Paired live checks proved unchanged
configuration, resources, Service/ingress/PVC/native Secret metadata, correct
new Pod digests, echo responses through all three nodes and FlareSolverr browser
retrieval/session cleanup. [Exact evidence](evidence/stateless-upstream-adoption-20261025.json).
Official FlareSolverr advertises Chromium 152 versus the former custom 156;
vendor findings remain unresolved. No new zero-CVE claim is made.

All three nodes were Ready without pressure at 22:16 UTC; all 55 PVCs were Bound,
all desired workloads and all 34 HelmReleases/Kustomizations Ready, and attached
Longhorn volumes healthy. Only the two intentionally preserved failed Seerr
diagnostic Pods remain outside Running/Succeeded. The current ownership matrix
covers 68 main/init/ephemeral image references and 33 app charts; 21 third-party
derivative chart transitions remain. Four owned app charts still require their
approved repository/publication ownership path, with BORTUS kept separate.

Controller cleanup removed 2,903,916,544 allocated Linux bytes after complete
source/OCI/process/mount checks. All archives, recipes, logs, runtime images and
unique evidence survive. [Exact paths and retained exceptions](docs/TASK-OUTPUT-INVENTORY.md).
Earlier encrypted NAS backups and migration/restart evidence remain valid.
Final IAB acceptance and remaining security/image work stay open; the goal is
active and incomplete.

**October 25 scope correction:** use maintained upstream releases for third-party
services; no further bespoke derivative image maintenance. Owned image changes
require repository-backed provenance and an approved publication path. Existing
derivative deployments and archives remain preserved for safe transition and
recovery. Actions stays off. The owned-image publication path is unresolved.
[Revised objective and supported goal readback](docs/REVISED-GOAL-20261025.md).

**The revised full goal is saved and active.** Cleanup and verified SMB handling
passed the October 25 20:23 UTC health gate. The goal is not done.
[Supported tracker readback](evidence/revised-goal-readback-20261025.json).
This source checkpoint is isolated from BORTUS
application development. Facts below come from the retained public maintenance
receipt, latest recorded progress `2026-10-24T02:46:45.685374+00:00` and its later
acceptance blocks. Historical failed/pre-cutover fields in that chronological
receipt remain preserved; the accepted checkpoints below take precedence.
Later root-executed live checks are recorded in the dated acceptance blocks.
Early pending/failed entries remain historical and do not supersede those blocks.

## Verified checkpoints

- October 25: Ruckus same-image HA recovery passed fresh full-state, SQL,
  after/restart and existing two-replica checks. The bot is resumed through Flux
  `758ba4c`; both claims and all failed evidence remain. The newer bot candidate
  is undeployed. [Exact execution ledger](docs/RUCKUS-HA-RECOVERY.md).
- October 25 artifact cleanup: 47 controller-verified node OCI transfer copies
  removed, reclaiming 6,303,870,976 allocated bytes. All controller originals
  remain. Twenty-six recovery archives (11,155,870,024 bytes) now have full
  checksum/read-back/age-authentication proof on the dedicated SMB backup folder;
  encrypted companion metadata is also copied and verified. No NAS media or
  Kubernetes SMB CSI volume was removed. Further generated-state cleanup is
  recorded separately when complete.

- All three nodes recovered Ready/uncordoned without pressure, running kernel
  `5.15.0-198-generic` and independent containerd `2.4.2`. Original frozen recovery
  confirmed 30 Longhorn volume UIDs, 54 Deployment UIDs and seven DaemonSet UIDs.
  Later post-app health records 30 healthy attached volumes and zero unavailable
  Deployments/DaemonSets. No Longhorn threshold/failure-metadata bypass occurred.
- Encrypted control-plane/configuration backup authenticated in full; fresh
  online off-node Longhorn checkpoint retained. A full disaster-recovery restore has not been performed and is not implied by
  archive authentication; the separate BORTUS recovery goal is not resumed. Worker1 ext4 filesystem grew within the
  existing partition/LV; no partition/LV changes occurred.
- Traefik 2.11.60, FlareSolverr 3.5.2 and whoami 1.12.0 have prior functional/route
  evidence. Their remaining security findings are open. Flare derivative run `40055919730` initially failed; its corrected attempt 2
  succeeded at source `613f90f`, artifact `12545656757`. Both attempts remain
  preserved. Root owns reception/scanning; no clean scan or rollout is claimed.
- Radarr 6.4.4.10685 retained API movie/history/config fingerprints, original
  SQLite Users fields, restart persistence and routes. Sonarr 4.0.20.3014 retained
  155 series/14,728 episodes/5,319 episode files/13,099 history rows and Users.
  Bazarr's source-proven default cleanup has a separate normalization proof;
  its after/restart qualification passed. Their complete UI workflows remain
  separate acceptance rather than implied by backend checks.

## Seerr: production cutover and backend acceptance passed

Accepted CI run `40048938336`, source
`e970316ce8ba23d4b1f61f7f0a8b2126de6d3fb6`, runtime
`docker.io/library/seerr-security-20261023@sha256:7bf03e8c4433460c0d93f789da56db457e3484412c448997102885af185db93c`.
The exact image scan recorded 0 critical/1 high without an available fix in the
pinned snapshot. All-node preload and native runtime qualification passed.

All six original accounts' credential/permission fields and all eight history
tables survived. Original settings initially matched literally; two later
source-proven runtime scan-clock advances have an independently bound proof.
After-cutover and new-Pod restart preservation passed, with Arr tag proof retained.
Browser login/Plex/permission/history workflow acceptance is still open.

- After receipt SHA256: `f101f1357799b315e7a3950b4d59540f9112bf5234e0b8958898817740e17146`
- Restart receipt: `dd427a21312153443ed1dcd157cadf89d3837224ee8a56265f9e3734d1fc6375`
- Arr tag proof: `7c7caa6586b8bf49c90e0a7c12afade8e2877fbea2385fe5826300a3e0fd4ab4`

## YTPTube: real retrieval, legacy preservation and restart passed

Accepted private CI run `40052586445` at
`3959595f3a6b1136472edca816e93cfe2eb7edfb`; OCI runtime root
`sha256:7c637f7e9cadf6f7def2243b517ff6101354287e17f9aebed8b0aa386fd1b754`.
The exact scan recorded 1 critical/68 high, all without available fixes in the
pinned snapshot; the prior four fixable installer findings were removed by
removing complete install-only code, without suppressing the analyzer/SBOM.

The actual application retrieved a five-second YouTube sample, 110,645 bytes,
H.264/AAC at 144p. The same media/history persisted in a new Pod. Seven legacy
files totaling 618,241,982 bytes remained unchanged after reobservation. Original
PVCs/NAS files and cold backups remain; normal UI login/playback/download workflow
acceptance is still open.

- Sample receipt: `4ef85843a9368beda9442d98616c969a2cc816b9da19900e9192601915f5bb70`
- Media SHA256: `7e05e92ad9b008d22990cfdc69f18f7023f7fc9bc6e0583739ead1f7b6adc457`
- Restart receipt: `13fd97d6f485f7c98abdbdaf3580ecc63d2da8c14d481336582a2bddf2d5320d`
- Legacy reobservation: `3dd6c77cdc5a5573e98f1ae3e9c758114e2893affcdd7e1cc428bacbe4e2036d`

## Routes and remaining security work

Chart commit `22dd5a2c816c37cc73fb17508bb2ae98720cceb7`, validation run
`40055143704`, restored 12 tested routes through all three nodes. Media HTTPS
certificate verification passed; TLS verification was not disabled. Route proof:
`8d2e02f891098298ed86c92e524fe0a7552f45b10958aa32e0069e943e9fe38d`.

The original audit covered 67 runtime image digests. That coverage is not a
clean-cluster verdict or proof of absence of unknown zero-days. Remaining work:

| Scope | Concrete next work / unresolved gate |
|---|---|
| FlareSolverr 3.5.2 | Patched derivative adopted through Flux; exact scan and native browser/version/route checks passed, with 4 critical/193 high unfixed residual rows |
| Tautulli 2.18.2 candidate | 68 recorded fixable critical/high rows; Debian/Python attribution patch, complete cold config/SQLite backup and history/account/notifier compatibility |
| Vaultwarden 1.37.4 | Seven available OS fixes adopted; whole cold backup and complete SQL/file preservation passed before and after restart. Public route restoration in progress; personal login/client sync remain unverified. Existing2FA/org/Sends counts are zero. |
| Unpackerr 0.16.1 candidate | Five linked Go findings: reviewed same-source Go 1.27.3/x/net 0.60.0 rebuild and extraction-policy compatibility |
| Pi-hole | Prepared same-app OS derivative; DNS-critical config backup and UDP/TCP DNS/API/metrics checks before adoption |
| Plex | Resolve actual app/bootstrap/channel versus immutable image; 15 recorded OS high rows and machine-identity/library/transcoding preservation |
| Other inventory | Source/derivative review or major migration for Homepage, MySQL/WordPress, xTeVe/phpMyAdmin, nginx/Redis/exporter/Gluetun; coordinated infrastructure trains |
| Jammy kernel | Recorded CVE-2026-98260 remains unresolved; preserve official fix availability evidence and revisit supported patch when available |
| Jackett runtime candidate | Existing static artifact/dependency applicability review is distinct from a live adoption and unsuppressed exact scan result |
| BORTUS image/release | Separate source owner; this maintenance branch neither resumes nor publishes it |

Full browser acceptance, final complete-inventory residual disposition and final
cluster/application health review are required before completing the goal.
All repeatable source entrypoints are listed in the
[maintenance README](k8s-rewrite/ansible-playbook/README.md). Secret values,
private receipts/keys, encrypted archives, OCI artifacts and runtime binaries
are deliberately outside this branch.


## Prepared exact cert-manager security patch scan

Official1.21.3 is available within the running1.21 line; it fixes the published
Go/x/net/trust and next-private-key ownership issues. The exact five-image
upstream-registry scanner is prepared under the existing W1 resource bounds,
with no application/Secret/CRI/deployment access. Its setup, actual five scans,
residual review and existing-owner Flux patch are not yet accepted or executed
by this source-only change. The full goal remains active.


## FlareSolverr exact Python/OS artifact scan, 03:44 UTC

Run `40058492329` at private charts source `5968b8f9c2ae0b45495fde6539f976fbc71a5bc3`
built artifact `12546303370`. The authenticated OCI archive SHA256 is
`db6315339f46a96d02d80bac4687de6929b1b900b640d1c9a146e54570209a7e`;
runtime manifest is
`sha256:29a981aec497ec47ccc25d67309c404593992a465501632e115010282ef61ec7`.
Actual scan `flaresolverr-f85f4bc513b5` finished successfully with 4 critical,
193 high, 300 medium, 373 low, six unknown and zero fixable critical/high rows
in the frozen database. Results SHA256:
`1f1895c34b93774573fb598dc69ee6419f375551ed9c4f41a3f456e523902492`.

This supersedes the earlier pending-artifact entry only. Preload, rollout, real
browser request, route and restart acceptance are separate and still open.
The goal remains active.


## FlareSolverr production acceptance, 03:53 UTC

Private charts commit `e7aad9893d9823aae489483e8fdba0dc94418c65` passed
validation `40059981764` and reconciled through Flux. The same Deployment and
HelmRelease UIDs now run the scanned immutable derivative in new Pod
`910adb88-cce7-4101-a864-386d73c1b091`. Native LOG_LEVEL/TZ references and
25m/64Mi requests remain; inherited legacy envFrom is cleared.

`qualify-flaresolverr.py` passed on the actual master: nonroot UID1000, exact
Python package versions, Chromium/ChromeDriver both 156.0.8078.47, version3.5.2
through all three node routes, and a real browser `request.get` to
`https://example.com/` returning HTTP200 with the expected page. No cookies or
page contents are retained. Receipt SHA256:
`ddc96a6f0efe73e246ef2b07f02698aa95bc7d782c3113958dfdd1c625c3cf0f`.
The 4 critical/193 high residual rows remain explicitly unfixed in the retained
database; application acceptance is not a clean-cluster verdict.


## Cert-manager1.21.3 adopted through Flux

Charts commit `09a8d9f158eb4ce780915c3a4f33863afc03a2a2`, successful validation
`40063040565`, selected the reviewed official chart and five image pins. The
actual full scan batch completed with no critical/high findings and four
unfixed unknown `GO-2026-5932` rows; its earlier partial attempt is preserved.
All three controllers are Ready with exact runtime digest bindings.

All six original CRD UIDs/stored versions and all original CRD specs remain,
except the single reviewed additive Certificate ARI certID field. Certificate
and ClusterIssuer UIDs/specs/readiness remain; webhook UIDs/CA bundles match.
Server-side dry-run admission and unchanged verified HTTPS certificates across
all three nodes passed. Adoption receipt fingerprint (SHA256)

`17dbb82fbb54e6905ae4d623da7a8ee743201a86dcb1329a336194d6fadbd276`.

The maintenance source is now published as draft PR29 at commit `c0c19123`,
with all15 playbook syntax checks and the exact146-file credential scan passed.
It is source only; application Actions remain disabled and the separate BORTUS
release is excluded. This checkpoint does not complete the full goal.

## Goal tracking and Vaultwarden restart, 05:37 UTC

The tracker is active for the full Seerr/downloader/security/Ansible/Flux scope,
including final implementation and browser acceptance. No duplicate goal was
created and no checkpoint was marked complete.

Vaultwarden1.37.4 now runs the scanned immutable derivative. Its authenticated
whole cold archive is retained. Both initial-start and new-Pod restart comparisons
preserved all28original tables,24vault items, oneaccount/fourdevice records and
the original RSA file, permitting only four reviewed additive vendor migrations.
Restart receipt SHA256:
`997ab1c8964281cfb482d51b1f5e75e75b11cf1ab0d32b07951e929b8be12c5b`.

The new Pod also passed version1.37.4, alive/config/web-root200 and anonymous
sync/profile401 checks. Observation fingerprint (SHA256):
`a57d84b0398d63c16c9ec80e03e4458b06605928ac3efc3b402d56121b369549`.
Personal account login and client sync remain unverified; no account or key was
reset. Public route restoration passed private charts validation40067096633 at
commit `05e1c8a1debe35bf318b544f7808847d5fb0ba59` and reconciled through Flux.
All24HTTP checks (existing ingress and published service through each node)
passed, including the401 boundary. Route observation fingerprint (SHA256):
`7623ca34e37eb583c71d61dbfdc9607b8b416819a47e6a83bf90c67adc0945ec`.
These are HTTP checks; verified LAN TLS is not claimed. The original Deployment,
HelmRelease, PVC, native references and resources remain. The first documentation
wording caused a public receipt fingerprint to match the credential scanner;
that CI attempt refused safely. The wording was corrected without an exclusion
or change to the scanner, and the subsequent complete pipeline passed.

## Exact core scans and Tautulli image work, 05:50 UTC

The separate16th opt-in playbook completed exact official etcd3.7.3/CoreDNS1.14.7
scans using the already verified public input snapshot. Etcd has0critical/high
and5unknown rows; CoreDNS has22high,22medium,1low and3unknown. Available compiled
Go/module fixes and pseudo-version attribution require further CoreDNS work.
Neither live component has been changed. See[core scan evidence](docs/CORE-PATCH-SCANS.md).

The Tautulli build selector/receiver/stager/scanner/preloader now support the
seventh service without changing resource or publication bounds. The first
private build retained its original failure artifact: runtime linkage checking
incorrectly included the official ET_REL SDK link object. Its exact primary
digest/header were independently verified; the corrected source still checks
all81runtimeELFs and retains all82objects. A new build is running at source
`cea9327b74c30fd4e138cca54856befb8a63dcc3`; no Tautulli rollout is claimed.

## Local delivery replaces GitHub Actions

The user explicitly instructed “stop using github actions” and “stop asking
questions. finish the goal.” Private charts Actions was disabled and verified
`enabled:false` on October24. New builds and chart validation/promotion move to
the local workflow, preserving immutable artifacts, existing resource limits,
all validation checks and Flux deployment. Completed historical CI artifacts and
their original evidence remain valid and retained. No further billing action or
question is needed from the user. This supersedes earlier Actions instructions.


## Etcd3.7.3: live patch and post-backup accepted

The exact official digest, membership/frozen revision HashKV, original data
folders and original workload/PVC/PV/Longhorn identities passed the protected
patch receipt. A new encrypted snapshot plus all46 configuration files was fully
authenticated off-node at23:14UTC. All3 nodes,54 Deployments,7 DaemonSets and
attached Longhorn volumes were healthy in the fresh observation. Details and
receipt fingerprints are in [ETCD-STATIC-PATCH.md](docs/ETCD-STATIC-PATCH.md).
No independent restore or full-goal completion is claimed. The remaining
application work continues through local validation -> validated -> Flux;
GitHub Actions is disabled by the user's current instruction.

## October25: local delivery and application acceptance

The dedicated Windows local validation service is installed and running. Exact
new main commits have automatically passed all29 existing controls and the
unchanged33-chart/34-release validator, atomically advanced validated plus the
immutable commit tag, and reconciled through Flux. No new Actions requests are
used. The independent clean service clone preserves the dirty operator checkout.

Tautulli2.18.2/Python3.13.17 passed complete cold authentication, initial and
independent controlled-restart data preservation, eleven authenticated API/Plex
checks on both writers, and all six actual public HTTP routes. All16 users and
2,878 history/media/metadata rows remain. Its fresh scan reports0critical/48high,
with0available critical/high fixes. Exact receipts and narrow source-proven
avatar/log/cache changes are in [Tautulli acceptance](docs/TAUTULLI-ACCEPTANCE.md).
Final browser acceptance remains open.

Pi-hole's original two claims are fully archived off-cluster:84files,
1,082,838,955 plaintext bytes; encrypted archive SHA256
`ee490a2b19a2a8a302d72f82cde05fd7c3fad288159168c54a36ba49c48e1289`.
Original SQL baseline includes9,982,551 query rows and1,339,185 gravity rows.
The new official FTL6.8/Core6.5/Web6.6.1-based signed-OS-patched artifact passed
the fresh unsuppressed image scan with no findings and separate upstream advisory
review. It is preloaded on all3nodes; the older FTL6.5 derivative was never adopted.
Initial live schema/config/history preservation and six authenticated API reads
plus internal UDP/TCP DNS passed. Controlled-restart preservation and authenticated API checks passed. All three
external nodes passed UDP/TCP DNS and HTTP route checks. Only final browser
acceptance remains pending for this application.
Retention remains91days and the existing password hash is preserved.

Redis was patched within8.6 to8.6.7 after a complete authenticated cold RDB/PVC
archive. The same Longhorn claim and the exact original RDB SHA passed on the
new Ready writer, with PONG, actual8.6.7 and healthy persistence. Its exact image
scan has no reported findings. Normal cache expiration/writes are not claimed
as immutable cache-value equivalence. Public routing is restored through the same local validator and Flux; all three
external nodes returned PONG.

The signed Debian13/PHP8.3.36 WordPress and phpMyAdmin derivatives are adopted.
WordPress preserved its account, all12 tables,55 posts,227 comments and4,951
files; complete encrypted SQL and file backups were authenticated first. The
first empty SQL dump was rejected and corrected before deployment. phpMyAdmin
retains all58 production dependencies, MFA/PDF and database connectivity. Four
static sites passed complete per-file content, ownership, mode and file-timestamp
comparison after nginx patching. Directory mtimes are excluded from equality,
with individual private manifests retained. All45 HTTP/Redis route checks passed;
WordPress preserves its existing canonical HTTPS admin redirect. These artifacts
have no available fixes in the recorded scan; unfixed rows remain visible.
The full goal and whole-inventory residual review remain active.

CoreDNS now runs the reviewed1.14.7 security build on both original replicas.
The fresh exact scan has no Critical/High/Medium/Low findings (three Unknown
rows retained). All18 UDP/TCP DNS queries and four Pod health checks passed;
only the image changed. Original Corefile/Service/deployment identities remain.
See [CoreDNS evidence](docs/COREDNS-SECURITY-PATCH.md). Dedicated native F-drive
build storage was installed through Ansible without changing existing cluster
disks, old build guards or Strata. Jackett and Plex cutovers remain in progress;
this checkpoint does not complete the goal.

Jackett's complete cold archive, six-indexer/API/credential comparison, controlled
restart and six external routes now pass; see [acceptance](docs/JACKETT-ACCEPTANCE.md).
Plex's complete encrypted cold config is authenticated and its same-beta OS patch
is Ready through Flux. The first hot-baseline section-table mismatch is retained;
a whole-archive comparison proved every cold section row/column equals live, with
no excluded field. The corrected full qualifier passed; routes are being restored.
Unpackerr's pinned Go1.27.3/current signed-Alpine rebuild succeeded and exact scan
is running; Homepage's patched build is running. Neither is adopted yet.

Plex's six external identity/web checks now pass. Unpackerr's complete cold
config backup, real isolated ZIP/mock-import cleanup and live native bindings/
config/startup checks passed. http-echo's unchanged-source rebuild has zero scan
findings and identical Service/ingress replies and retained claim/spec. See
[Unpackerr](docs/UNPACKERR-ACCEPTANCE.md) and [http-echo](docs/HTTP-ECHO-SECURITY-PATCH.md).
Homepage1.13.2 now runs the exact patched runtime with zero scan findings. Its
complete cold archive is authenticated; all nine active configuration files,
Native Secret bindings, original PVC/spec and internal HTTP checks passed.
qBittorrent5.3.0/LT2.0.15 retained all231 Legacy torrents and454 file identities,
original credentials, paths, priorities and progress after full cold backup and
source-proven settings compatibility fixes. Its exact image has zero findings.
The shell monitor's204/cookie repair is now deployed through the same private
local-validation/Flux owner. Six real queue cycles, original notification-state
preservation, authentication and automatic VPN-port reconciliation passed; the
full231-torrent/454-file comparison passed again. All15 Homepage/qBittorrent
external route checks passed. Pi-hole exporter's same-source patch
and three real scrapes passed with zero findings. See
[Homepage](docs/HOMEPAGE-SECURITY-PATCH.md),
[qBittorrent](docs/QBITTORRENT-SECURITY-PATCH.md) and
[exporter](docs/PIHOLE-EXPORTER-SECURITY-PATCH.md). Mealie/xTeVe/Ruckus and the
remaining exact inventory continue; final browser and whole-inventory acceptance
remain open. This checkpoint does not finish the tracked goal.

October25 latest execution: Mealie, xTeVe and jtmb-dev after/restart checks passed.
Their images are respectively a3fc64d6…,0ab77160… and6432c718…. Mealie preserved
53 tables/847 rows,3 users and 33 recipes; xTeVe preserved accounts/credentials,
provider identities,108 mappings/29 active mappings and all claims, including
untouched SMB. xTeVe source-proven provider refresh/backup rotation is verified
explicitly; its configured FFmpeg media fixture passed, while failed VLC tests
remain recorded. The website preserved23 files and11 routes. Personal login and
final browser validation are not implied by these receipts.

Existing SMB release is now chart1.20.4/revision2, preserving all12 original
resource UIDs,14 PVs/14 PVCs and native credential fingerprints. A first postcheck
flagged only the two generated DaemonSet revision annotations; read-only exact
original-HMAC reconstruction passed without repeating the upgrade. Linux3/3,
controller1/1 and existing mount-root samples passed. NAS media remains on NAS.

Ruckus is deliberately paused through Flux for its complete encrypted cold
backup and isolated MySQL patch qualification. The authenticated cold archive
covers216,491,611 bytes; the original PVC and all user/system data remain intact.
The first isolated restore rejected the original external mysql.sock symlink
before any server start; only those recorded tmpfs fixture resources are being
retired, with failed receipts retained. The correction preserves that exact
socket-link metadata while using a separate private socket for cloned servers.
Bazarr's compatible security artifact is built and undergoing exact-image scan;
Radarr/Sonarr and remaining Go image fixes are source preparation, not adoption.
The tracked goal remains active and final inventory/browser acceptance is open.

Ruckus database cutover and declared restart now pass on the new retained-data
lineage, preserving all3,962 application rows/account/native Secret and original
source PVC. Bot384c86b restores one normal instance after bcrypt/Node22 checks;
readiness alone is not final dashboard/connection acceptance. Both workers'
USN8555 security37.2 package transactions passed strict package/runtime/kernel/
node continuity checks with zero failures. See
[database lineage](docs/RUCKUS-DATABASE-SECURITY-PATCH.md) and
[worker patch](docs/UBUNTU-PRO-SECURITY-PATCH-20261025.md).
Four exact security artifacts are ready for the remaining application cutovers;
raw scans and ImageSharp's per-advisory3.2 backport attribution remain separate.
Final inventory/browser gates are still open; this checkpoint is not completion.

October25 18:15 UTC checkpoint: Radarr, Sonarr, Bazarr and Whoami now run the
qualified exact security images through private local validation and Flux.
Fresh full cold backups and after/restart checks passed; Radarr/Sonarr's full
original Users rows and credentials passed again. External media HTTPS/browser
acceptance remains open. See [media receipts](scripts/migration/media-security-acceptance-20261025.md).
The cached live BORTUS image was fully audited:17 reachable blobs verified,
5C/99H/160M/154L/3U. Findings were handed to its separate owner; this chat did not
change its application. See [exact audit](docs/bortus-cached-runtime-audit.md).

Ruckus's current fresh DB claim is degraded with one healthy replica because two
nodes are below Longhorn's disk scheduling floor. SQL acceptance does not prove
storage redundancy. Read-only inspection reattached the retained original claim
with both existing replicas RW/healthy; every original file byte/metadata matches
the cold archive, with only top-level directory mtime drift recorded. A proposed
fresh-current-data sibling-directory recovery is source preparation only: no
original file is overwritten, no current data is replaced by the older archive,
and replica/space thresholds are not weakened. Do not describe HA recovery as done.

The four accepted services'12 redundant node transfer files were removed by
Ansible, recovering1,322,184,704 allocated Linux bytes while retaining complete
controller copies. A stopped successful Ruckus builder's reproducible state alone
was removed after source/artifact/reference checks, recovering2,384,879,616 Linux
bytes on F; its image, logs, recipe and all source/locks remain. Windows/VHDX
recovery is not inferred. Traefik's metadata cache is being completed under the
same bounded attempts; no incomplete build was adopted. Calico and Longhorn
compatible remediation proposals are concrete but remain unimplemented. Full
cluster security, HA recovery, final inventory/routes and final IAB remain open;
the tracked goal is active. This checkpoint is not completion.
