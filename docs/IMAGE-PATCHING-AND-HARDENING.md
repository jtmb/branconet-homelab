# Image patching and runtime hardening

**Controlling correction, October 25 20:19 UTC:** the user rejects maintaining
third-party bespoke derivative images. The table below records historical work
and current deviations, not the future maintenance strategy. Transition those
services safely to maintained upstream releases using repository-managed
version/digest changes. Maintain only owned images, with repository-backed
definitions/provenance and an approved publication path. No further derivative
rebuild or promotion is authorized. [Full correction and goal-control receipt](REVISED-GOAL-20261025.md).

Recorded October 25, 2026. This is an account of maintenance already performed
and remaining work, not a claim that the cluster is free of vulnerabilities.
The main goal is paused during the explicitly requested artifact cleanup.
GitHub Actions remains disabled; local validation promotes reviewed charts to
`validated`, which Flux reconciles. No image build deploys itself.

## Who maintains the images

Most services are upstream applications. We maintain reviewed derivative recipes
in the private charts repository rather than claiming ownership of those apps.
Those recipes pin inputs, update available OS/runtime/compiler dependencies, and
retain the application's existing data/configuration contract. A compatible
upstream application release can replace an older release after state and
integration checks. An unsupported dependency requires a separate migration or
an explicitly recorded residual finding; rebuilding alone does not fix it.

| Services | Work performed / ownership boundary | Evidence or remaining gate |
| --- | --- | --- |
| Overseerr → Seerr | Upstream replacement, locally built derivative; accounts, permissions and request relationships retained | [Seerr](SEERR-ACCEPTANCE.md); final normal UI workflow remains open |
| MeTube → YTPTube | Upstream replacement, reviewed local image; original download storage retained | [YTPTube](YTPTUBE-ACCEPTANCE.md); real download and restart verified |
| Radarr, Sonarr, Bazarr, Whoami | Locally built compatible derivatives; runtime/dependency fixes while preserving state | [Exact-image and state acceptance](../scripts/migration/media-security-acceptance-20261025.md); residual findings retained |
| Plex, Jackett, Mealie, Tautulli | Upstream applications with reviewed runtime/OS dependency updates | Individual acceptance documents; some unfixed or unsupported components remain |
| qBittorrent, Unpackerr, Homepage, http-echo, Pi-hole exporter, xTeVe | Reviewed derivatives, preserving application behavior and integrations | Individual security/acceptance documents; scan results apply only to their exact artifacts and database snapshot |
| Vaultwarden, Pi-hole, Redis, WordPress, phpMyAdmin, static sites, FlareSolverr | Reviewed compatible application/runtime/base-image updates | Dated blocks in [status](../MIGRATION_STATUS.md); not a blanket zero-finding claim |
| Ruckus database | Same MySQL 5.7.44 compatibility boundary; updated supporting packages and recovered redundant storage | [Database](RUCKUS-DATABASE-SECURITY-PATCH.md), [HA recovery](RUCKUS-HA-RECOVERY.md); MySQL 5.7 remains an unsupported application dependency |
| Ruckus bot | An accepted earlier derivative is running; a newer dependency candidate is built and scanned | [Ruckus](RUCKUS-SECURITY-PATCH.md); newer candidate has not been deployed |
| Traefik | Existing upstream-compatible version remains running; reviewed Go rebuild has not completed | New build stopped on controller memory floor; remediation remains open |
| CoreDNS, cert-manager, etcd, SMB CSI | Component-specific compatible updates, preserving configuration and resource identities | Status and component evidence; no general disaster-recovery restore claim |
| Calico | Vendor component, current deployment retained | [Compatible proposal](CALICO-COMPATIBLE-REMEDIATION-PROPOSAL.md), source-only; not applied |
| Longhorn | Vendor storage component; existing data and thresholds preserved | [Compatible proposal](LONGHORN-COMPATIBLE-REMEDIATION-PROPOSAL.md), not applied |
| BORTUS | First-party application, developed and released by its separate owner chat | Exact deployed-image audit still contains findings; its unfinished release is excluded here |
| Ubuntu hosts | Signed compatible package maintenance through opt-in Ansible | [Ubuntu Pro evidence](UBUNTU-PRO-SECURITY-PATCH-20261025.md) |

## What qualifies a patch

Each candidate binds its source/recipe, immutable runtime digest, full OCI archive
checksum and scan output. Raw findings are retained. Where scanner metadata
misidentifies a source-proven backport or an unused reference assembly, the
explanation and exact runtime evidence remain alongside the raw result; the
finding is not silently suppressed. Scan severity alone does not prove practical
exploitability, and a clean result does not rule out unknown vulnerabilities.

Stateful changes require protected recovery material and before/after application
checks. Deployment follows the private charts and Flux path. Restart and data
checks establish persistence; they do not substitute for the final browser
workflows. Secrets stay in native Kubernetes Secrets managed through BORTUS.

## Runtime hardening versus image updates

Image patching and Pod hardening are separate. Existing application resource,
storage, account and integration contracts have been preserved. This work does
**not** establish that every application runs as non-root, drops all capabilities,
uses a read-only root filesystem or has a restrictive NetworkPolicy. Isolated
backup/build helpers have their own token, capability, network and resource
bounds; those helper controls must not be represented as controls on every app.

There is currently no verified automatic advisory-to-rebuild schedule. The local
pipeline validates chart changes; it is not an automatic CVE monitoring system.
Compatible platform remediation, unsupported dependencies, final exact inventory
and normal UI acceptance remain explicit work before the goal can be complete.
