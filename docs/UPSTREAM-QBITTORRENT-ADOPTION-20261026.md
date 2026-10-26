# qBittorrent maintained upstream transition

Owner: migration chat `01a12045-bf7e-73b3-8557-752d17c72ffd`.
Status: preparation; the existing download/VPN/monitor writer remains unchanged.

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
than reusing the older 5.1-to-5.3 preference projection. Production remains unchanged.

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
