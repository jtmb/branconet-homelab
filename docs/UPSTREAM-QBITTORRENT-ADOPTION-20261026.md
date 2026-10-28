# qBittorrent maintained upstream transition

Owner: migration chat `01a12045-bf7e-73b3-8557-752d17c72ffd`.
Status: maintained upstream deployed and verified through an independent Flux
restart at `902dae6c51b25ed2f1dd313511ed1841c618c385`. Full cluster goal remains active.

Fresh live observation reports qBittorrent 5.3.0. The current maintained
LinuxServer artifact is
`ghcr.io/linuxserver/qbittorrent:5.3.0_v2.1.2-ls485@sha256:75ecbb1c89ab7b0a21c4bde40b4820e4f1649d2d56d83b91913422155e8d2a5f`,
amd64 manifest
`sha256:236a7a3a81a3706182ae1f12ee55aa3781c753963e680b2d9c8e55541686d0ce`.
The maintainer's current bundle changes libtorrent as well as base packages.
Review its published compatibility and the actual retained resume format before
adoption; do not select an obsolete artifact solely to make an old test pass.
The original launch Secret points to `/init`, so neither its value nor credentials
need changing to follow the vendor's `/app/qbittorrent-nox` packaging.

Reuse only the existing F:-backed output root, physical ext4 UUID
`3c792469-ea0e-4a2c-98e8-1185b141607b`, backing file
`F:\branconet-build-storage\native-build-20261025.ext4`. Public metadata, source
controls and reports use existing `operator-control` and
`security-review-20261026`; application recovery/observations will use
`upstream-qbittorrent-20261026`, with exact executed sources in
`control-source/upstream-qbittorrent-20261026`. Configure scratch there and
enforce capacity floors before downloads. No new root, derivative image build,
GitHub Actions or new registry/publication is authorized.

Preserve the original Longhorn config claim, all paired torrent/resume IDs,
native credentials, per-torrent/file priorities and non-regressing progress,
all effective preferences/categories/tags, SMB downloads and VPN/monitor wiring.
Capture the current complete inventory rather than substituting a historical
torrent count. Store only keyed identities/metadata in private observations;
credentials, cookies and API values stay in node RAM. New node-side generated
source/receipts must not create another disposable-output root: stream the
bounded observation back to the declared controller root.

Use the existing private local validation → validated → Flux pipeline. Require
complete authenticated cold config backup and NAS read-back before adoption.
Verify the actual immutable runtime, original Secret/resource/storage bindings,
native authentication, forwarded port and live VPN/monitor integration, then a
distinct restart. Preserve every original/failure/rollback artifact. Final IAB
remains deferred until all implementation is complete; reconcile exact generated
paths/bytes and retained exceptions before accepting the checkpoint.

## Preparation evidence

The fresh authenticated baseline contains **232 torrents / 455 files**, all
paired Legacy resume identities, native API credentials, preferences/categories/
tags and VPN-forwarded listen-port checks. This supersedes the old observer's
historical 231-torrent assumption. Actual libtorrent is 2.0.15.0; the target is
2.1.2. The new observer compares complete current 5.3 responses directly rather
than reusing the older 5.1-to-5.3 preference projection. This was the original
pre-cutover baseline; the completed transition is recorded below.

Pinned libtorrent 2.1.2 source accepts resume-file versions 1 and 2 and writes
version 2 with the same `libtorrent resume file` format tag. This is source
compatibility evidence; actual resume/file/progress and restart checks remain
mandatory. The immutable maintained-image scan completed with 0 Critical /
2 High / 2 Medium / 44 Low findings, two fixable High package rows and an empty
CISA KEV intersection. The findings remain open vendor rows; this is not an
unknown-vulnerability clearance.

Fresh profile metadata shows root-owned config, torrent/resume files and a
root-owned mode-1750 `/config`. A UID1000 read-only preflight correctly refused
access; it did not alter permissions. Use the dated complete cold profile with
**UID/GID0 on masternode**, all capabilities dropped and no privilege escalation,
rather than changing existing ownership or adding filesystem override grants.
The full four-GiB / 4096-entry archive and 15-GiB retained-space guards remain.

The current 2.0.15 writer emits resume format 1; both its reader and the selected
2.1.2 reader accept formats 1 and 2. The target writer emits format 2. Preserve
complete original state and newer post-cutover state before any rollback;
source-format compatibility alone is not an independent recovery proof.

During the short cold interval, quiesce qBittorrent and its queue/port monitor
through their existing Flux releases, then restore both original one-replica
settings. This prevents monitor writes/restart requests against the deliberately
stopped client. Keep the monitor state claim, image, alert configuration and
native Secrets intact; no notification test or password change is included.

## Deployed checkpoint, October 26 16:13 UTC

The private local publisher validated and promoted four exact revisions, with
GitHub Actions still disabled: pause both writers `83ada19deac1394b0e9f3da2d62d35aca9d2e2d1`,
adopt the maintained image and restore both replicas `ee39223d0cd6a62c970489249bb320098605e2b6`,
repair the monitor port poll `4f910b5cd7119ce471fb98037e6dd81d6c6c21e1`, then
independently restart qBittorrent `902dae6c51b25ed2f1dd313511ed1841c618c385`.
Private main, validated, Flux source and both actual releases reached the last
revision. All native Secrets, original PVCs, NAS downloads, services, VPN image,
resources and monitor alert settings remain. Runtime CRI reports the pinned
registry index `75ecbb1c…`; the selected amd64 child is `236a7a3a…` above.

Both complete comparisons passed **232 torrents / 455 files**, paired resume
identities, categories/tags, every original preference, file identities/priorities,
non-regressing progress and authentication/ownership metadata. Adoption Pod UID
`70cd5934-3635-40aa-a1b2-fce02b4a977f` differs from restarted UID
`b04ebfc7-32e8-45cd-83a3-22d4863764ae`; both main and VPN containers have zero
unexpected restarts. The native API rejects anonymous preferences reads.

Two actual compatibility issues were repaired rather than waived:

- The old monitor checked forwarded ports only hourly, leaving a stale listen
  port after a VPN reconnect. Its chart now polls every **10 seconds**. The shared
  port file, image, persisted state and alerts are unchanged. The restarted client
  port matches the actual VPN-forwarded port; real monitor queue/login cycles pass.
- qBittorrent's source defaults the disk queue to 100 MiB with libtorrent 2.1,
  versus the original 1 MiB. The guarded native API helper restored exactly
  `disk_queue_size=1048576`, comparing all other preferences and native writer
  bindings before/after. The opt-in Ansible playbook
  `playbooks/qbittorrent-upstream-defaults.yml` reproduces this exact fingerprinted
  preservation repair; syntax check passes and check mode makes no API write.

The after-restart connectivity observation reports `connected`, 199 torrents with
working trackers and 224 peers, uploading 10181769 bytes/second at capture. This
does **not** claim every tracker works: 806 tracker entries reported working,
3266 reported status 4, 419 status 1, seven status 6 and two status 5. No
pre-adoption per-tracker baseline was captured. Tracker URLs, torrent names,
peer addresses and credentials never leave node RAM in these reports.

All **20** unauthenticated UI/access-control route checks passed: internal
service plus port 8112, HTTP and HTTPS through each node, using the existing
`qbittorrent.branconet.local` ingress host. HTTPS probes measured routing with
private certificate verification skipped and sent no credentials; trusted TLS
and final browser acceptance remain open. The first route probe overlapped the
authorized restart and refused a connection; its failure receipt/source remain.
Earlier digest/port/preference and tracker-observer failures also remain.

## Recovery, security and limits

The complete quiesced `/config` archive is **24315892 bytes**, SHA256
`b72d33a9ae6020b76ba3070db0fec345b3b2dd785c744863de3a434ed1dfdd6d`.
The distinct source/observation/verification metadata archive is **5060004 bytes**,
SHA256 `69e334e92e2f7680fc0481560a54976b32b8d745b6c2c609987d89de63351967`.
Both passed full NAS ciphertext read-back and complete age authentication; the
metadata archive additionally verified every archived member. Original archives,
keys, source, rollback data and all unique failures remain. No live application
restore was performed; the observer's `restore_verified` and
`full_acceptance_complete` flags remain false rather than being relabelled.
Its data-only `cold_copy_verified` and `tracker_connectivity_verified` flags are
also false: the separate NAS and current connectivity receipts provide those
specifically scoped checks, not the observer itself.

The exact maintained artifact still has **two High package rows** for
`CVE-2026-92392`: curl/libcurl 8.22.0-r0, fixed package 8.23.0-r0. There are
also two Medium and 44 Low findings, with no current CISA KEV intersection.
No bespoke image patch was built. The bundled qbt CLI has a detected .NET
dependency manifest; its unsupported-runtime status has not been independently
established here. A scan is not clearance from undisclosed vulnerabilities.

Fresh cluster health shows three Ready nodes without pressure, 55 Bound PVCs,
all 34 releases and Kustomizations Ready, no unavailable workloads, and 41
attached healthy Longhorn volumes. Two original failed Seerr diagnostic Pods
remain intentionally preserved. The fresh full image-owner inventory contains
91 Running Pods, 297 controllers and 68 image references. Four third-party
application derivative transitions remain: Plex, ruckus-db, WordPress and xTeVe.
Platform/fleet security, owned-image publication and final IAB remain open.

Checkpoint reconciliation removed **710959104 allocated Linux bytes**, preserving
all originals and 16 unique publisher receipts/reports. Exact paths, byte counts,
regeneration commands and retained exceptions are recorded in
[the output inventory](TASK-OUTPUT-INVENTORY.md#qbittorrent-checkpoint-reconciliation-october-26-1613-utc).
This is Linux filesystem recovery only; no Windows recovery, shutdown or
compaction is claimed.

Exact private evidence under the declared root: `operator-control/qbittorrent-upstream-checkpoint-summary.json`,
`qbittorrent-upstream-route-checks-r2.json`,
`qbittorrent-upstream-current-tracker-integration-r4.json`,
`qbittorrent-upstream-final-cluster-health.json`, both `smb-qbittorrent-upstream-*-status.json`
receipts, `upstream-qbittorrent-20261026/{baseline,after-r5,restart-r5}.json`,
the complete cold receipt and `control-source/upstream-qbittorrent-20261026`.
