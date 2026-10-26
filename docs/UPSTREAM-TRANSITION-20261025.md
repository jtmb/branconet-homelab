# Repository-backed image transition

Latest accepted revision, October 26 01:41 UTC:
`0ed2ad27ce0a32055c37c3e2d4d22026535a9b15`, private main/validated/live Flux.
The four static sites now use official Nginx 1.30.6 Alpine Slim; all complete
content/configuration, Secret/resource identities, routes and different-Pod
restart checks passed. Fully authenticated cold archives and final encrypted
metadata passed NAS read-back. [Exact acceptance](UPSTREAM-STATIC-SITES-ADOPTION-20261026.md).
The refreshed 91-Running-Pod / 68-main-init-ephemeral-image inventory identifies
11 remaining third-party derivative chart transitions: homepage, jackett,
mealie, pihole, plex, qbittorrent, ruckus-db, tautulli, vaultwarden, wordpress and
xteve. The four owned application repositories remain separately classified;
their non-Actions publication gap is unresolved. Full security remediation and
final IAB are still required. The selected Nginx image's fresh zero-finding OS
scan does not close the fleet's open security findings. Older dated snapshots
below are historical.

October 26, 00:20 UTC: phpMyAdmin now runs the official 5.2.3 Apache image.
Native login/logout, all 3 published routes, the configured SQL account/grants
and all 12 WordPress tables matched before, after and on a different restart Pod.
The original MySQL Pod, credentials and data claim were unchanged. Encrypted
recovery metadata passed NAS full read-back and authentication.
[Exact acceptance and unresolved vendor findings](UPSTREAM-PHPMYADMIN-ADOPTION-20261025.md).
Private charts main/validated/live Flux is
`4e792ea690e2cbda21168510051345f865c47421`. All 3 nodes, 55 PVCs, 34 HelmReleases
and desired workloads passed the 00:17 health check; attached Longhorn volumes
are healthy. There are 15 third-party derivative transitions remaining. The exact
phpMyAdmin vendor digest's prior scan reported 8 Critical/131 High finding rows,
including 11 with package fixes; its database is older than 24 hours now. This is
backend/ownership acceptance, not security acceptance. Fresh vendor vulnerability
review and final IAB remain open; no bespoke third-party patch was rebuilt.
Cleanup removed 4096 allocated Linux bytes from one empty scratch directory,
retaining all recovery originals, sources and failure evidence. The goal is active.

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
