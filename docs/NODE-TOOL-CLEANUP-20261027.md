# Node tool cleanup, October 27

Owner: migration chat `01a12045-bf7e-73b3-8557-752d17c72ffd`.
Controller outputs reuse the existing F-backed root
`/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025`,
under `operator-control` and `node-cleanup-20261027`. No new drive, download,
dependency tree, build or remote staging directory is needed.

The reviewed deletion inventory consists solely of `bin` below these existing
worker1 attempt directories under
`/home/james/.local/share/branconet-migration/worker1-image-build-20261023`:

- `jackett`
- `pihole`
- `seerr`
- `seerr-r2`
- `seerr-r3`
- `ytptube`
- `ytptube-r2`

Applied at 08:04 UTC: removed exactly **904,888,320 allocated Linux bytes**
across those 21 tool files and seven empty directories. Available worker1 space
rose from 109,144,190,976 to 110,049,079,296 bytes during that operation. A fresh
inspection then found all seven targets absent and removed zero further bytes.
[Exact file paths, hashes, byte counts and retained exceptions](../evidence/node-tool-cleanup-20261027.json).
This is node filesystem recovery; no Windows disk recovery is claimed.

Each contains only three public BuildKit tools, independently matching both the
original input seals and the hashes compiled into the cleanup helper. Inspection
at 08:03 UTC measured 904,888,320 allocated bytes across 21 files and seven
directories. This is an inventory, not a removal claim. All have passed the
72-hour retention check. Root filesystem UUID is
`5f1fd363-f7b7-44db-ace5-ad81a25a2926` (worker1 ext4).

Regeneration: obtain the original BuildKit v0.34.1 Linux amd64 release archive,
verify SHA-256
`a59539daf547fe0958efe2d07e41c0a6944e1112a66d7e519ec1cf5b673ef15b`,
extract only `bin/buildctl`, `bin/buildkitd`, `bin/buildkit-runc` into a fresh
owned build attempt and verify the three pinned hashes in the helper. Keep the
original setup role, build-input seals, recipes and lockfiles. Never replay an
old failed attempt to regenerate a disposable tool copy.

Inspection holds the original host/phase locks, validates every sealed source
and lockfile, checks all active systemd commands and working directories, and
checks process arguments, open files, mapped files and every observed mount
namespace. It refuses symlinks, hard-linked tools, changed identities, unexpected
directory contents and current references. Apply repeats these checks and
removes individual files through an opened directory descriptor, then removes
the empty directory. No recursive deletion is used. All sealed source files are
verified again afterward.

Repeatable entry point:
`k8s-rewrite/ansible-playbook/playbooks/retired-build-tools.yml`.
It defaults to inspection; explicit `retired_build_tools_apply=true` enables the
same exact helper, with no remote helper staging. The executed source and full
private receipts are retained in the existing controller output root.
The actual helper completed inspect/apply/post-inspect checks over SSH. Ansible
syntax checking passed with the explicit project configuration; the initial
automatic-config lookup failed because WSL sees the Windows checkout as world
writable. That failed check and corrected check are both retained.

Retained exceptions: the two failed Seerr BuildKit state directories (about
15.2 GB together) are unique failure evidence; all OCI archives, original
Gluster bricks, Plex databases/settings/metadata, original MySQL data, journals, active
swap, application volumes and BORTUS owner artifacts remain intact. No cached
runtime image has qualified for removal. The old master cache-only targets are
already absent; their source/SDK trees are outside that cleanup contract.

Ingenium clarification: image download/content is 1,209,310,265 bytes for
`docker.io/jtmb92/ingenium@sha256:fbb8281c832d7382982cfcfc39a074e899aa4516a6f65149dee510b879e9f0fc`.
Development checkout/history inventories are not an image-pull prerequisite.
Actual node allocation and persistent state sizing are separate measurements;
Ingenium application deployment remains with its owner chat.

At 08:05 UTC the exact image was already present on worker1. Its 68 selected
content blobs use 1,209,491,456 allocated bytes; containerd reports about 3.65 GB
across its unpacked layer snapshots (human-readable usage, rounded). These can
share storage with other images and are not exclusive/reclaimable bytes. No
development checkout is included in this image accounting.

| Node | Actual available filesystem bytes at 08:05 UTC | Longhorn state at 08:06 UTC |
|---|---:|---|
| master | 19,131,355,136 | Below existing floor by 4,493,698,049 bytes |
| worker2 | 21,937,082,368 | Below existing floor by 1,767,400,449 bytes |
| worker1 | 110,048,886,784 | Schedulable |

All three nodes are Ready without Kubernetes pressure; all desired Deployments
and DaemonSets are available, 57 PVCs are Bound, and all 43 original Longhorn
volume UIDs are preserved. All attached volumes are healthy. The four original
failed diagnostic Pods remain as evidence. All three volume groups report zero
unallocated bytes; no unused LVM capacity can resolve the two small-node floors.
Further legacy duplicate-file assessment remains in progress; no original
application data has been removed and no Longhorn placement-capacity pass is
claimed for the two small nodes.

## Worker2 generated thumbnail inventory

The next reviewed candidate is exclusively
`/var/plex-stack/plex2/config.old/Library/Application Support/Plex Media Server/Cache/PhotoTranscoder`
on worker2, ext4 UUID `960bc2c7-2a7e-4bc2-b2c5-dbb6d71207f4`. Controller source
and private exact-entry receipts stay in the same F-backed output root, under
`operator-control` and `node-cleanup-20261027`. No original configuration tree,
database, metadata, media, codec or directory is selected for removal.

[Plex's own support documentation](https://support.plex.tv/articles/204041406-where-are-plex-media-server-cached-images-stored-on-my-computer/)
identifies this location as generated image derivatives cached after clients
request artwork. Normal client artwork requests regenerate the cached images
from Plex's retained originals. This classification uses the documented
function, actual JPEG/PNG/GIF/WebP headers, filesystem identity, single links,
72-hour inactivity and complete live reference checks, not the directory name
alone. All 56,854 original non-cache file/directory identities are fingerprinted
before and after the operation; their contents are never emitted.

At 08:22 UTC the reviewed plan selected 10,658 generated image files,
3,243,261,952 allocated bytes. It retains 8,947 entries / 188,932,096 bytes that
did not pass image-format qualification, and keeps every directory. The earlier
whole-cache inspection refused the non-image entries without deleting anything;
those entries remain excluded. Reviewed plan SHA-256:
`4e405d105e877bf48dd4fc1d0070c0b599c8a0f6872d7bc369355043c11bffa0`.

Repeatable entry point: `playbooks/legacy-plex-cache.yml` and `legacy_plex_cache`.
Defaults inspect-only; apply requires the exact reviewed plan fingerprint and a
fresh receipt in the existing controller output root. Reuse the reviewed
`retired_build_tools` reference checker, with its source hash verified before
loading; do not run a retired build helper. No service is stopped, live PVC
mounted or runtime image removed.

Applied at 08:23 UTC: all 10,658 qualified image files were removed, recovering
**3,243,261,952 allocated Linux bytes**. The 8,947 unqualified entries and every
directory remain. All 56,854 original non-cache identities match afterward.
Available filesystem bytes changed from 21,939,859,456 to 25,183,113,216 during
the operation. That delta is 8,192 bytes smaller than the allocation tally; these
two measurements are reported separately without attributing a cause. Ansible
syntax checking passed.
[Public result and hash of the complete exact-entry receipt](../evidence/node-legacy-plex-cache-cleanup-20261027.json).
The full private path/identity manifest is retained as
`node-cleanup-20261027/legacy-plex-cache-removal.json` in the declared output root.

Total node recovery in these two operations: **4,148,150,272 allocated bytes**.
At 08:26 UTC, Longhorn reports worker2 **Schedulable=True**, available
30,408,704,000 bytes, or 1,483,185,151 bytes above its unchanged 25% floor.
Worker1 remains schedulable; the master still falls short by 4,493,698,049 bytes.
All workloads remain available, 57 PVCs are Bound, original volume UIDs survive,
and all attached Longhorn volumes remain healthy.

The Ingenium owner subsequently measured separate application-state transfer at
8,858,276,008 bytes. Worker2 still needs **7,375,090,857 additional bytes** freed
to write that state while retaining the floor, before growth/rebuild margin.
Clearing current admission pressure is not a completed capacity qualification.
Legacy download files lack matching same-path NAS copies and remain protected;
that limited comparison does not establish whether duplicates exist elsewhere.

## Actual eviction and 11 GiB claim qualification

At 08:31 UTC kubelet's live configuration on all nodes has
`imagefs.available: 15%` and `nodefs.available: 10%`. Its reported image and
node filesystems have identical capacity and available-space observations.
[Kubernetes documents these signals and their eviction behavior](https://kubernetes.io/docs/concepts/scheduling-eviction/node-pressure-eviction/).
These are separate from Longhorn's 25% admission floor: a later false Longhorn
schedulability condition alone does not prove failed existing replicas.

Worker2's logical scheduling remainder is 12,271,976,039 bytes after its exact
34,710,622,617-byte reservation and 68,719,476,736 scheduled bytes. Thus an 11 GiB
claim (11,811,160,064 bytes) fits this accounting; a 16 GiB claim does not.
That does **not** qualify physical capacity. Live worker2 image/node available
space is 25,149,448,192 bytes. The separately measured transfer allocation of
9,521,545,216 bytes leaves 15,627,902,976 bytes, about 13.5% of the filesystem,
below the unchanged 15% threshold of about 17,355,311,309 bytes. The shortfall
is 1,727,408,333 bytes even before new filesystem overhead, another image pull,
application growth or logs. No reliance is placed on automatic garbage collection.

For a conservative 4.9 GB image-allocation scenario, plus the full 11 GiB claim,
worker2 needs another 8,917,023,181 bytes recovered merely to remain above that
15% threshold, before additional operating margin. This scenario is a sizing
calculation based on the observed roughly 4.86 GB image footprint, not a measured
future pull delta: layers might be shared. Worker1 has sufficient observed space;
neither worker2 nor master is qualified for the proposed redundant state yet.
No floor, reserve, admission, garbage-collection or replica setting was changed.
