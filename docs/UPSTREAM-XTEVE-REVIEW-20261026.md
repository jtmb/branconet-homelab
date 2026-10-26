# xTeVe maintained-release review

Owner: migration chat `01a12045-bf7e-73b3-8557-752d17c72ffd`.
Status: current-state and maintained-successor source/security review complete;
no replacement deployed. Only the previously authorized read GETs and ordinary
cache behavior were used; no login, provider stream or update requested.

Reuse the existing authorized F:-backed root
`/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025`,
ext4 UUID `3c792469-ea0e-4a2c-98e8-1185b141607b`, backing
`F:\branconet-build-storage\native-build-20261025.ext4`. New observations use
`upstream-xteve-20261026`; exact source uses `control-source/upstream-xteve-20261026`;
small public release/image/source metadata and controls use existing
`operator-control`. No second drive/root or node-side source export is introduced.

Preserve the existing xTeVe Deployment, native Secrets, both Longhorn config
claims, SMB IPTV media, tuner identity, accounts, providers, channels/mappings,
filters, guide data and URLs. Preserve all original cold and failed evidence.
Read the current complete state with the existing bounded HMAC observer and
read-only Kubernetes/HTTP inspection before selecting a transition. Do not
substitute the historical 108/29 mapping counts for a fresh inventory.

The original xTeVe release page still lists 2.2.0. The related Threadfin project
publishes maintained successor artifacts and a different configuration path;
its name alone is not proof of compatible restoration. Inspect primary release,
image and configuration/backup sources before changing any workload. No
third-party derivative build, auto-updater, new registry or Actions is authorized.

Public metadata and exact observation sources are required evidence, retained
with hashes; no dependency or build outputs are planned during discovery.
Reproduce discovery from the exact retained observer and public URLs. Any later
download/build must pass fresh Windows C: and native destination capacity floors.
All temporary files must stay in the configured existing operator scratch and
be reconciled before the checkpoint, with unique failures and runtime data retained.

## Verified findings, October 26

Fresh complete observation at 16:18 UTC passed against current derivative
`docker.io/library/xteve-security-20261023@sha256:0ab77160ccccaf9235dcb3864624440551d6dd63c771cfaf97094db869a28656`.
Pod `caab9ccf-3301-4d39-8559-d44d316a14df` has zero restarts. Both local
trees/native identities, **108 mappings / 29 active channels**, discovery,
device, lineup, M3U and XMLTV passed. API remains disabled (423); login is not
credited. Exact receipt: `upstream-xteve-20261026/current-baseline.json`, observer
SHA256 `87da06727ed0dd31a4bc1272d8a2c580583e8241d05cf884236852e463e0b38b`.

The original xTeVe release is still March 2021's 2.2.0.200; alturismo's image
is unchanged from August 2021. Threadfin/Threadfin 1.2.37 is from September 2025.
The independently maintained volschin fork released **v3.4.0 on October 20, 2026**,
source `0d9c81151e995ee89cb1baabd8580cc3d7e4369e`, public image
`ghcr.io/volschin/threadfin:v3.4.0@sha256:79ba430d81feccaa36865cc9ecc905e5cb5d16f593965e30cb2feda128b43216`,
amd64 manifest `c08ba41338bf9660406e6528e765050c5d3b7484483b7ca34f6edbae1d37c748`.
Version/latest resolve identically. The first unprefixed `3.4.0` tag probe
returned 404; `v3.4.0` is the actual tag. No derivative was built.

Pinned source establishes these required compatibility steps before deployment:

- Explicitly select the existing `/root/.xteve` config path rather than the
  vendor default `/home/threadfin/conf`; preserve both Longhorn and SMB claims.
- Preserve UUID/tuners/accounts/providers/filters/mappings/FFmpeg configuration;
  compare source-supported new settings and startup cache/provider updates.
- Preserve existing client guide URLs: `src/webserver.go` accepts only
  `/xmltv/threadfin.xml` and `.gz`, so direct adoption breaks the proven
  `/xmltv/xteve.xml` and `.gz`. Repository-managed compatibility routing is needed.
  M3U uses prefix routing and does not enforce the old filename.
- Explicitly map disabled `xteveAutoUpdate` to `ThreadfinAutoUpdate=false`.
  The new container-detection default alone is insufficient preservation proof.
- Verify the legacy account/password migration, fresh cold/NAS backups, complete
  data and media integration, routes and a distinct restart before acceptance.
  No new cold interval or replacement deployment started during this review.

The exact candidate scan completed with pinned public feeds rehashed before/
after, under the existing 1-GiB/no-swap/two-CPU credential-hidden unit. Findings:
**0 Critical / 8 High / 287 Medium / 16 Low / 1 Unknown**, eight fixable High
rows, no current CISA KEV intersection. Four High identifiers each appear in
two bundled Go targets (1.27.0/1.27.1): `CVE-2026-111943`, `CVE-2026-78667`,
`CVE-2026-78669`, `CVE-2026-97031`. This is not security clearance or adoption.

Private evidence: `operator-control/xteve-successor-vendor-inspection.json`,
`xteve-threadfin-3.4.0-{source-review,complete-contract-source}.json`, exact
sources in `control-source/upstream-xteve-20261026`, and
`security-review-20261026/apps-threadfin-current-r3-0/{receipt,results}.json`.

Completed scan cleanup removed **1658880 allocated Linux bytes** after full
source/hash/inode/ownership, containment and process/FD/map/mount checks:
`security-review-20261026/cache/fanal/fanal.db` 1646592 bytes, plus
`security-review-20261026/cache/fanal`, `security-review-20261026/tmp`, and
`security-review-20261026/home` at 4096 bytes each. Exact paths, protected hashes
and regeneration: `operator-control/xteve-review-scratch-{plan,reconciliation}.json`.
The terminal unit was inactive/dead, Result success, exit 0. Baseline, all
sources/results, original/failed/rollback/recovery data and prior retained
exceptions survive. Unresolved `operator-control/tmp/system-commandline-sentinel-files`
and its nonempty parent remain protected. No Windows recovery is claimed.

Sources:
[original releases](https://github.com/xteve-project/xTeVe/releases),
[Threadfin releases](https://github.com/Threadfin/Threadfin/releases),
[Threadfin image and volume contract](https://github.com/Threadfin/Threadfin#docker-image).
