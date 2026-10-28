# Application batch restored; capacity gate remains failed

**Subsequent recovery accepted:** the original unchanged strict verifier passed at 08:39 UTC after verified cache/tool retirement restored node capacity. [Exact recovery, original failure preservation and remaining gates](WORKER2-CAPACITY-RECOVERY-20261028.md). The account below records the original failed checkpoint; it is retained as history, not the current acceptance result.

All 14 applications are available again on their original images, templates and
storage bindings. All 17 volumes have two healthy actual RW replicas and run
their upgraded engines on the pinned v1.13.0 instance manager. Their original
volume/claim/PV UIDs and replica directories survive; mounted-data reads passed.
**This batch is not accepted:** worker2 fails the unchanged storage floor and
operating margin. [Exact observations](../evidence/longhorn-application-batch-20261028.json).

The fixed cohort is Vaultwarden, Ruckus DB, Seerr, YTPTube, Bazarr, Jackett,
Radarr, Tautulli, qBittorrent, qbit-monitor, Mealie, Threadfin, Plex and Sonarr.
The two qBittorrent/monitor consumers stopped together for their shared volume.
Pi-hole, Ingenium and held BORTUS stayed running. The normal stop/detach/restore
used only their existing Flux release replica counts, through private charts
main, unchanged local validation, `validated` and Flux. There was no direct scale,
forced detach, operator data copy/rewrite, native Secret change or image rebuild.

Stop `6013b3afb9f4d573af6b3294a868398bc860a585` passed validation. All consumers
disappeared and all 17 volumes detached normally before restore submission.
Restore `a1904230a34495dbd0ea428b8246df1f174e98d7` also passed, and the migration
Kustomization is Ready/Healthy at that exact SHA. All new application containers
are Ready with zero restarts. All 58 claims, 14 NAS bindings and three Ready
nodes survive, with no unavailable desired Deployment/DaemonSet. Full application
semantic/account/history checks and normal Seerr/YTPTube IAB remain separate.

The prepared check enforced 25% free space plus 512 MiB, but did not reserve
additional native image payload/unpack storage when Pod placement changed.
That preflight is insufficient for future batches. Any further cohort needs
an explicit per-node native payload budget before submission. No threshold is
lowered to accept the current result. The observer stopped at the original
guard; a separate read-only structural observation records data/runtime health
and the failed capacity predicate without claiming acceptance.

The recorded worker2 disk available bytes are 27,158,118,400 against required
29,462,389,761: a 2,304,271,361-byte shortfall. Master and worker1 pass. Current
attached volumes remain healthy, but worker2 cannot schedule additional replicas.
Read-only inspection found no unused LVM extents, only about 161 MB under the
node's task directory and about 562 MB of active/archived journals. It also
identified retained old derivative image entries and collected native container,
snapshot and lease metadata. No image, content blob, native snapshot, lease,
volume, application data or original artifact has been deleted. Candidate cache
qualification must establish exact regeneration and absence of container/lease/
parent/child/process/mount references before any cache retirement. Image pruning
and raw snapshot-directory deletion are outside this procedure.

The native CLI/source inspection also matters: `ctr snapshots mounts` in the
pinned release calls the mount manager's Activate operation. Do not treat it as
a read-only path lookup. [Exact vendor implementation](https://github.com/containerd/containerd/blob/v2.4.2/cmd/ctr/commands/snapshots/snapshots.go).
The maintained capacity inspector performs only metadata/size reads, never that
operation. Its two earlier executed sources are frozen beside their receipts.

The opt-in `longhorn-runtime-batch.yml` Ansible entrypoint exposes only explicit
`prepare|stop|observe|detached|resume|verify` phases. The prepared source/owner
bindings remain frozen. After capacity repair, run the unchanged strict verify
phase; do not bypass its storage check or rewrite this failure as success.

Cleanup removed **355,721,216 allocated controller Linux bytes / 1,612 paths**
from the two terminal, consumed publisher exports. Full Linux reference checks
and all 1,612 exclusive Windows handles passed; original Git blobs/tools and
ten report/lock/publication records remain unchanged. The per-path ledger is
`longhorn-runtime-retirement-20261028/publisher-cleanup-0782d79da4f052c6/receipt.json`
under the existing F-backed platform review root. This controller cleanup does
not recover worker2 space. Retain 15 unique current plan/data/capacity/source
witnesses, 862,155 logical bytes excluding the index; no dependency/build cache
or nonpublisher scratch was created. Earlier protected safety/rollback exceptions
remain, and required charts source/recovery tools still have current consumers.
Independent Windows free observations: C:55,140,528,128 and F:193,112,182,784
bytes. Linux deletion does not establish Windows/VHDX recovery.

Four engines still use the old runtime: Pi-hole's two volumes, Ingenium's one,
and held BORTUS's one. Capacity repair, strict batch acceptance, those remaining
cycles, final exact-image/security/data/route/browser reconciliation and cleanup
remain required. The full tracked goal is active and incomplete.
