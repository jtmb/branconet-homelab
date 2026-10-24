# Migration and maintenance status

**The full goal remains active.** This source checkpoint is isolated from BORTUS
application development. Facts below come from the retained public maintenance
receipt, latest recorded progress `2026-10-24T02:46:45.685374+00:00` and its later
acceptance blocks. Historical failed/pre-cutover fields in that chronological
receipt remain preserved; the accepted checkpoints below take precedence.
No new live checks were performed while assembling this branch. Root separately
reported the corrected Flare CI attempt below; its exact scan remains pending.

## Verified checkpoints

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
| Vaultwarden 1.37.4 candidate | Seven available OS fixes; whole `/data` backup, forward schema migration, credentials/2FA/org/sends and client-sync checks |
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
