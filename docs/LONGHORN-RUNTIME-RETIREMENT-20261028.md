# Longhorn runtime retirement: canary accepted, remaining cycles open

HTTP Echo now runs on the pinned v1.13.0 instance manager after a real Flux-driven
detach/reattach. Its original Deployment, claim, PV, volume, replica directories,
application image and Pod template remain. The new Pod has zero restarts; its
mounted directory read and two actual healthy RW replicas passed. All58claims
are Bound, fourteen NAS bindings survive, all three nodes are Ready and no
desired Deployment/DaemonSet is unavailable. The release and migration
Kustomization are Ready at private charts main/validated/live
`b5286ec8bf287ca4c248356ee59e860fccb43749`.
[Exact acceptance](../evidence/longhorn-runtime-canary-20261028.json).

The stop/restore source commits are `79d708e3c213430f0387c3daf9f1603b54d8ab28`
and `35e80a4d06e3a3b4a002aaa0fd1859ebd16a1b68`. Both used the existing local
validation/promotion service and Flux; no direct replica patch or controller
suspension was used. An isolated private charts worktree on the same declared
F-backed root preserves all existing dirty checkouts. Windows Git trusts only
that verified exact UNC worktree through a process-scoped safe.directory option;
no global Git configuration changed. The original ownership-preflight refusal
and source remain preserved.

The restore exposed a real host conflict: multipathd captured the Longhorn
virtual disk and grouped it with another Longhorn disk under the same WWID.
The unused map had zero opens, no mounted-filesystem reference in any inspected
mount namespace and no process block descriptor. No LUKS mapping existed for
the canary. The first mount error and Helm timeout remain failed historical
evidence. The new Pod was created at02:17:04UTC and became Ready at06:12:04UTC:
**14,100seconds**, rather than a successful brief restart.

The opt-in `longhorn-multipath-guard.yml` playbook dispatches the maintained
guard worker. On each of the three original nodes it verified every observed
IET/VIRTUAL-DISK disk belonged to a `/dev/longhorn/pvc-*` device, then installed
only `/etc/multipath/conf.d/90-branconet-longhorn.conf`. It excludes that exact
vendor/product pair. Other disk types, all preexisting configuration hashes,
containerd/multipath process IDs and boot IDs survive. The daemon accepted the
rule through reconfigure, without restart, and removed the idle map itself.
No filesystem unmount, forced device removal, service stop, key change, data
copy, formatting or encryption change occurred. A real worker2 rerun created
no file and released no map. The standard config directory/file are retained
required runtime configuration for future Longhorn attachments.

This follows the documented multipath conflict while using the narrower
vendor/product exclusion supported by the Ubuntu configuration format.
[Longhorn diagnosis](https://longhorn.io/kb/troubleshooting-volume-with-multipath/),
[Ubuntu device blacklist syntax](https://manpages.ubuntu.com/manpages/jammy/man5/multipath.conf.5.html).
The master's first guard attempt treated multipathd's empty-list `ok` response
as a map name and stopped before configuration writes. The corrected worker
enumerates actual kernel `mpath-` devices; its original source/refusal remain.

After the host fix, chart0.1.1 supplied a fresh validated revision for the already
healthy Pod and cleared the recorded Helm timeout. Its application image/data
and template stayed unchanged. Original failed observations and immutable
validation reports were retained; no failure was rewritten as success.

The separately qualified unused WordPress destination's future engine reference
also moved to v1.13.0 without attachment or initialization. Both workers proved
its exact original replica directories absent before and after; every original
claim/PV/replica/engine/volume identity survives. The old EngineImage reached zero
references and Longhorn subsequently removed it normally.
[Exact unused-volume proof](../evidence/unused-retired-volume-engine-20261028.json).

Cleanup removed **533,581,824 allocated Linux bytes /2,418paths** from the three
consumed successful publisher stages: exact regenerated source exports, tools
and empty home/tmp directories. Original reachable Git blobs/lockfiles, pinned
tools and fifteen validation/publication records are unchanged. Full Linux
process/unit/FD/map/mount exclusion and2,418exclusive Windows handles passed.
The per-path ledger is under the original F-backed root:
`platform-upstream-review-20261027/longhorn-runtime-retirement-20261028/publisher-cleanup-64d390d67a4d7082/receipt.json`.
Failed/unselected stages remain protected. The isolated tracked charts source
worktree remains required by the remaining runtime cycles; unique minimal
source/failure/receipt metadata remains. Previous retained exceptions, including
the12,288-byte root-owned packaging subtree, are unchanged. Windows recovery is
not inferred from Linux deletion; the independently observed free bytes are
C:58,823,311,360 and F:193,673,609,216.

The three old instance managers still host other upgraded live engines. Their
remaining workload cycles, final exact-image/security review and normal Seerr/
YTPTube IAB acceptance remain open. BORTUS's application release stays held under
its separate owner. The full tracked goal is active.
