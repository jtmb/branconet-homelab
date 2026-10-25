# Repository-backed image transition

October25 22:35 UTC: Pi-hole exporter v1.2.0 is adopted through private
charts main/validated/live Flux `25d6ec1b67d37c4881386b58a3fa02b9e31ef6bf`.
Paired checks passed for all 20 Pi-hole metric families, positive authenticated
query statistics, readiness/liveness and metrics through all three node
addresses. The complete Deployment specification changed only its image;
Service and native Secret metadata stayed exact. [Exact evidence](../evidence/pihole-exporter-upstream-adoption-20261025.json).
The 22:34 cluster check found all three nodes Ready without pressure, all 55
PVCs Bound, all desired workloads and 34 HelmReleases/Kustomizations Ready,
and all attached Longhorn volumes healthy. There are 20 third-party derivative
transitions remaining. This is upstream ownership adoption; vendor dependency
findings, final browser acceptance and the full goal remain open.

The next stateful batch has newly resolved official vendor rebuilds for Radarr
6.4.4.10685, Sonarr 4.0.20.3014 and Bazarr 1.6.2. Their application versions match
the current installations; vendor image revisions are newer than the earlier
baseline. [Immutable candidates](../evidence/media-upstream-candidates-20261025.json).
Before adoption, extend the finite preservation profiles, capture fresh current
API/config/SQL baselines and authenticated cold backups, then verify data and
new-Pod restart persistence. No stateful cutover is claimed by this inventory.
No local build or new dependency/compiler/cache tree was created in this
checkpoint; new operator receipts remain inside the established F: root.

October25 22:24 UTC update: official Whoami, Seerr, YTPTube, FlareSolverr
and http-echo adoption are accepted for backend behavior at private
main/validated/live Flux `5cfa97c446035d403f3486a9786b53f71cb62872`.
The [current image/controller matrix](../evidence/image-ownership-current-20261025.json)
contains 68 main/init/ephemeral references and 33 app charts; 21 third-party
derivative transitions remain. Final browser acceptance stays after implementation.

FlareSolverr v3.5.2 and http-echo 1.0.0 retain their exact upstream application
versions. Only their image and FlareSolverr pull policy changed. Complete
Deployment specification comparisons, Service/ingress/claim/Secret metadata,
real HTTP GET/POST/health requests, three-node ingress and FlareSolverr browser
retrieval passed. The latter created no persistent session. Its vendor browser
advertises 152 versus the previous custom 156; vendor findings remain open. The
October23 scan of this exact FlareSolverr base recorded 32 critical/1091 high
package-advisory rows; that dated evidence is not represented as a fresh scan.
HashiCorp's latest official release is still 1.0.0 from 2023, with known Go
advisories. These transitions satisfy upstream ownership, not security closure.
[Exact paired identities and checks](../evidence/stateless-upstream-adoption-20261025.json).

The controlling objective is [the revised active goal](REVISED-GOAL-20261025.md).
Earlier derivative recipes and scans remain historical, not an execution plan.

## Authoritative charts delivery

Observed October 25: Git resolves the authoring checkout to
`C:/Users/james/AppData/Local/Packages/OpenAI.Codex_2p2nqsd0c76g0/LocalCache/Local/BORTUS/repos/branconet-charts`
(the app-visible path is `C:/Users/james/AppData/Local/BORTUS/repos/branconet-charts`).
Fetch and push origin both equal `https://github.com/jtmb/branconet-charts.git`.
Authoring branch `codex/overseerr-to-seerr` tracks `origin/main`.
HEAD, remote `main`, remote `validated` and live Flux all reached
`7fa88544d8b20924ff4b4ab37b1f7e394a220eea`. The checkout's older local `main`
is not the publication source and is not reset. The dedicated local validator
exports the exact remote-main revision, checks it, then promotes `validated`.
Actions remains off. Application chart values/templates belong in
`charts/<service>`; effective release overrides belong in `flux/releases`.
`flux/source.yaml` selects the same private repository's `validated` branch.
Existing vendor/OCI infrastructure sources retain their ownership; change their
versions/digests through the private repository's foundation definitions.

## First completed transition

Whoami now uses official upstream `traefik/whoami:v1.12.0`, immutable index
`c4717a8d1f0134a7444e24f881160e033991f23027c6c5a9a3f8fd22e70d1d44`.
Local CI passed its existing 29 controls and complete validator; Flux upgraded
release revision 148. New Pod UID `ff3e0617-64ed-4500-b84d-8ecd0d568cac`
passed three real Service requests and three ingress requests, with restart0.
Deployment/Service identities, complete specification except image/pull policy,
ingress and Secret references remained exact. No build or OCI publication ran.
The older vendor scan's 16 high/14 medium/one low findings remain reported;
latest upstream release is still v1.12.0. This policy transition does not fix
those vendor dependencies. Prior derivative and archive remain for recovery.
Private receipts: `FBASE/image-ownership-20261025/whoami/{before,after}.json`.

## Owned-image publication findings

Connected GitHub confirms ownership/admin access for `jtmb/ruckus_bot`,
`jtmb/qbit-monitor` and `jtmb/jtmb-dev`. The latter two already contain
`.github/workflows/docker-build.yml` publishing to their existing Docker Hub
repository names, using `DOCKER_USERNAME`/`DOCKER_PASSWORD` secret references.
Their workflows require Actions; do not run or enable them. Ruckus has Dockerfiles
but no root `.github` directory at this observation. BORTUS stays with its
separate owner. Historical homelab Ansible also contains Docker Hub publication,
but its use of a sudo password for registry login must not be replayed.

The registry destination need not be invented. The smallest candidate route is
a commit-pinned, repository-owned local build/publish entrypoint targeting the
existing Docker Hub namespaces, with immutable source tags and recorded registry
digest/provenance; charts then consume that digest through the existing pipeline.
It needs confirmation of the permitted non-Actions publisher and a usable scoped
push credential reference. WSL Docker config is absent, Windows config points to
an absent Desktop credential-helper executable, and the cluster has no
dockerconfigjson Secret. No secret was printed or new publication attempted.
Those observations do not prove that no credential exists elsewhere. Existing
services are retained while this exact route/credential gap is resolved.

## Historical Seerr preparation, since executed

Upstream official v3.5.1 index
`d8fab675b55ad293ded98fd71efcfd46054cbad9746534ae1cc4794a88c0b3be`
labels the same application source `564bfb08b54caa374bddaf820abfd226e5e69151`
already running. Before chart adoption, quiesce only Seerr through Flux, capture
and fully authenticate a fresh complete claim archive, and derive modern SQL/
settings/account HMACs. The explicit `upstream-seerr-20261025` cold profile pins
the existing Deployment/release/PVC/node identities; it never scales a writer.
Its read-only root reader adds only DAC_READ_SEARCH to cover both root-owned
filesystem metadata and private app-owned files. All caps otherwise stay dropped;
no token, host mount or writable source is supplied.

`qualify-seerr.py cold-baseline --already-seerr` accepts only that completed
fully authenticated profile and performs SQLite quick_check in private RAM. It
skips all old Overseerr transformations and preserves current settings literally.
The original legacy baseline mode remains available unchanged. Same-source
application/account/history/provider checks and restart verification remain
required after adoption. These additions are preparation, not a completed
Seerr upstream transition or final browser acceptance.
