# Dedicated local build storage

## Existing152GiB remount recovery, October26 19:42UTC

The task mount was absent during a later health-script write; that write failed
instead of falling back into the underlying WSL filesystem. Read-only inspection
found no associated loop, a clean ext4 filesystem and the original backing-file
inode `115123265474727363`, UUID `3c792469-ea0e-4a2c-98e8-1185b141607b`,
size163208757248 bytes. The earlier documented online growth to152GiB had not
been added to the installed144GiB remount helper.

The Ansible source now recognizes152GiB only for `--mount-existing` on that
exact original inode. Creation and growth generations are unchanged. The
installed helper was verified against the prior pinned source, then updated
from the reviewed role source. It restored the same loop-backed filesystem,
`rw,nodev,nosuid`, with512-byte sectors and direct I/O. No formatting, growth,
filesystem repair, shutdown or workload stop ran. The remount receipt is
`operator-control/local-build-storage/storage-832f553365cf4b12a0839fa845542cc3.json`,
SHA256 `6fa1fa3b626af002b6ae32380b8b2a86e42727242bce806989bbfd27e061661b`;
helper source SHA256 is
`8ba04629d2c349d3291b775a444b6564a2e77d6ec06785a1268f3f81e8e0f220`.
This existing152GiB path records new receipts inside the same authorized root.

The completed Ruckus encrypted recovery archive still matches its exact hash
after remount. The existing `Branconet Charts Local CI` scheduled task was
started after its old process was confirmed absent; its new Windows Python
process is live. This did not create a new publisher or replay an old revision.
The19:42UTC cluster check found3Ready nodes,55Bound PVCs, every release Ready,
no unavailable workloads and41healthy attached Longhorn volumes. All prior
failed Pods remain retained. No new disk-recovery claim is made.

The existing cluster disks remain unchanged. New build stages must satisfy the
15 GiB C-drive launch minimum described below. A separate
96 GiB native ext4 filesystem was initially created in
`F:\branconet-build-storage\native-build-20261025.ext4`, UUID
`3c792469-ea0e-4a2c-98e8-1185b141607b`, and mounted at the operator runtime's
`local-image-build-offload-20261025`. Strata and other projects were left running.
Only this new, explicitly verified regular file was formatted; no host partition
or existing filesystem was changed. Its Windows directory has a private ACL.

`playbooks/local-build-storage.yml` is opt-in and must run as local WSL root.
Default/check mode do not create or mount anything. Repeated execution verifies
the existing file, filesystem UUID and mount rather than reformatting it. No
formatting is performed at startup. The successful creation receipt SHA is
`8a68474285391cffe386c69973da0aee21e6dabfb4df74a4d0ff74b09bcf2c37`.
An initial format attempt timed out before creating a filesystem; its original
file identity and zero header were checked before the explicit guarded resume
with `mkfs.ext4 -E nodiscard`. Both attempts are retained.

The private charts repository's separate offloaded builder admits CoreDNS,
Jackett, Plex, Unpackerr, Homepage, http-echo, qbittorrent-current, pihole-exporter, Mealie, qbit-monitor, xTeVe, RuckusDB, jtmb-dev and ruckus-bot only. It keeps the existing 3 GiB memory, no-swap, 1.5 CPU,
512-task, 8 GiB cache, 12 GiB fresh allocation and 4 GiB OCI bounds. The original
global build lock prevents overlapping builders. It checks both the dedicated
F filesystem/physical drive and the shared Docker bootstrap on C; Docker's new
mutable layer is bounded to 64 MiB, logs to two 16 MiB files, and its original emergency C-drive floor remains2 GiB during an already running
build. The newer15 GiB launch requirement is additional, not a reason to stop
existing work.
It never clears shared caches or changes the default builder.

The offloaded scanner is opt-in. Its original memory/CPU/deadline, complete OCI
and source proof, 24-hour database age and full database hashes remain enforced.
It retains 25% plus 8 GiB free in the native filesystem, 8 GiB physically on F,
and an 8 GiB private scanner allocation ceiling. Old C-drive scanner guards and
frozen helpers remain unchanged. New helper setup rehashes existing complete
immutable inputs once, avoiding redundant reads of both original and copy.
No credential, database, image archive or private receipt is committed to Git.

The existing local charts publisher now stages on the same native F filesystem.
Its 29 controls and unchanged chart validator passed for source
`03aa16e785a7c74779bb72799056af0683311c04`; publication receipt SHA256 is
`54a197827798d9f88fe1d2971d821f8f037f35c78ee4bc9ffb2d27f66dd1942e`.
There is still one serial publisher and no GitHub Actions execution.

The opt-in `local_build_storage_configure_ci` Ansible setting installs an
owner-root existing-only mount helper and updates the existing idle Windows
scheduled task with `--offloaded-storage`. At startup, the watcher invokes this
helper before watching; a missing backing file refuses instead of creating or
formatting one. Configuration receipt SHA256 is
`a7fc81364984c7b66f001ac344fb487f8b416e422f999141e93de2c2821e4e0c`.
The mount helper verifies the original file, filesystem and owner identities.

During maintenance, C: exhaustion caused the Ubuntu controller filesystem to go
read-only. The cluster nodes were unaffected. Transparent NTFS compression of
identified archival artifacts recovered capacity; full hashes, lengths and last
write times were verified unchanged. No artifacts were deleted, no unrelated
checkout was reset and no Strata process was stopped. Only the failed Ubuntu
instance was restarted; its existing Docker workload recovered healthy. The
original backing file was then remounted through Ansible, with receipt SHA256
`7ccdc24e2e904ec9afaaaa57bf5a0bf46266458cacabd93bb19206fc7a871720`.
Private recovery evidence remains under
`F:\branconet-migration-artifacts\maintenance-storage-20261025`.

## October25 launch policy and recovery

Before each new build or large transfer, measure actual Windows C: and the
receiving filesystem. C: must have at least15 GiB free; the destination must retain
15 GiB after the estimated stage. The12 GiB fresh-build estimate already includes
its OCI output. All generated stages reuse the task-owned
`local-image-build-offload-20261025` root on the approved F-backed filesystem;
C/WSL disposable output remains limited to20 GiB. Existing running work is not
stopped to enforce a new launch policy. Receiver and preload launch checks enforce
the same retained-space rule. Original in-flight emergency limits remain intact.

Ansible now verifies direct I/O on the exact existing loop device, its backing
file identity,512-byte sectors and filesystem UUID. After an approved Ubuntu
interruption, the actual remount/install run passed without creation or formatting
(receipt SHA256
`d18bc2bf327c1ad2e7acaa487d781c460d341986a4093509f3410800903ee163`).
The existing-only remount path reserves15 GiB physically on F; it does not charge
another96 GiB for a file already allocated. New creation still charges the whole
file plus15 GiB and requires15 GiB on C. The local publisher was restarted with
its existing-only mount prelude and remains the sole publisher.

The explicit recent-cache inventory found17 generated directories totaling
9,399,203,744 allocated bytes, all younger than72 hours. They are retained;
**zero bytes were deleted**. Source, lockfiles, failed observations and rollback
archives remain. The inventory does not certify their later deletion.

The user separately approved Ubuntu-only VHDX compaction and interruption.
Ingenium and the OpenCode router were gracefully stopped and their existing
identities recorded; the build filesystem unmounted normally and root trim
reported154,083,749,888 bytes. Windows then refused exclusive access to Ubuntu's
VHDX while Lean-AMD remained active in the shared WSL VM. No disk compaction or
Windows free-space recovery is claimed. The same Ubuntu container/image, SSH key,
root/build UUIDs, router and local publisher were restored. No other distribution
or remote Kubernetes node was stopped. A bounded approved retry waits for other
WSL distributions to stop naturally and still requires exclusive access; it
expires rather than stopping them. Private recovery receipts are retained in the
maintenance-storage directory named above. New builds remain gated until C:
actually reaches15 GiB free.

## Completed compaction and controller recovery

The separately approved Ubuntu-only compaction completed at09:57:44UTC on
October25. VHDX length fell from582,790,152,192 to433,029,382,144 bytes, a reduction
of149,760,770,048 bytes. Windows C: reported157,805,809,664 bytes free at completion.
No Linux files were deleted as part of compaction; Windows recovery is reported
separately from filesystem capacity. Recorded Ingenium container/image and SSH
identity were retained; the existing workloads were started again. The OpenCode
router already showed a restart condition before the final interruption; starting
its unit does not establish application health. Cluster nodes were not stopped.

The dedicated build filesystem subsequently reached the publisher's unchanged
reserve. Its existing backing file was extended to128 GiB. During the first
online growth attempt, the controller's lifetime was not secured and it stopped
before the operation was fully recorded. The unmounted filesystem then refused
to mount because its final new group descriptors were incomplete. This was a
controller build-storage fault, not a Kubernetes disk operation.

Recovery preserved the original prefix, backup descriptors, complete512 MiB
journal and per-block undo files outside the image. Official e2fsprogs replayed
only committed journal transactions; all descriptor pointers became valid. The
read-only filesystem then matched19 recorded file checksums, including the6.6 GB
Plex encrypted cold archive and new xTeVe OCI artifact. A full offline safe-preen
check completed with exit1 and no unreviewed manual repair; its optimization
suggestion was ignored. Failed attempts and their logs remain. No reformatting,
image/volume pruning or cache deletion was used.

The final Ansible mount/install run verified128 GiB, the original backing inode
115123265474727363, original filesystem UUID, direct I/O and62,786,265,088 free
native bytes. Receipt SHA256:
`516ad3670bcf5f65f9885607d87add97399eec1d395e1b2082a90d3df1d0f109`.
A further post-check archive comparison is retained separately. The root-owned
startup helper now recognizes only the96/128 GiB generations. Future growth is
explicit and **offline only**, requires the original inode and exclusive build
lock, preserves a filesystem undo file, and never kills a metadata write because
an observation deadline expires. Normal mount/startup never formats or resizes.

The existing Windows CI task now owns one Ubuntu keepalive for its watcher's
lifetime. It still has one serial publisher, the same account and interval, and
uses the existing-only mount prelude. The wrapper exits if its keeper exits and
cleans up only its own processes. This prevents WSL's idle lifecycle from losing
the build mount between polling attempts. The temporary maintenance keeper was
removed after the managed keeper and single watcher were confirmed live.
Historical96 GiB artifact receipts remain validated against their actual recorded
capacity; new builders pin128 GiB. Other resource bounds and the15 GiB launch
minimum are unchanged.
