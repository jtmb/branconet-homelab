# Longhorn image capacity audit

**Completed read-only measurement, October27. No upgrade or node deletion.**
All 14 reviewed official images were freshly authenticated from their pinned
index, amd64 manifest and configuration digests. All 97 distinct gzip layers
passed complete compressed SHA-256 and uncompressed DiffID verification. Payloads
were streamed through bounded RAM readers; no image archive, blob or extracted
tree was saved. Distinct compressed bytes total **1,164,833,698**. This replaces
the earlier aggregate layer-size assumption with actual authenticated reads.

The parser follows the [OCI gzip-layer format](https://github.com/opencontainers/image-spec/blob/main/layer.md).
It projects file allocation by rounding each TAR member to 4 KiB and allowing
8 KiB per member for metadata. It credits no deletion, replacement, hardlink
sharing or old-image pruning. This is a conservative calculation, **not observed
native containerd unpacking**. Deployment must check actual consumption against
fresh headroom before proceeding.

The isolated job ran with 512 MiB RAM, no swap, one CPU and 64 tasks. Actual
cgroup limits, filesystem UUID, hidden credential paths and source hashes were
checked inside the job. Windows and the original task filesystem passed the
15 GiB launch floor plus the bounded 8 MiB metadata allowance.

## Exact native cache and calculated headroom

The three original nodes were inspected through strict existing SSH. Only exact
public candidate blobs were read and SHA-256 checked. Native snapshot metadata
and parent chains were read without invoking pull, unpack, mount or prune.
Each node has 31 relevant committed snapshots; master/worker2 have 35 relevant
authenticated blobs and worker1 has 34. Chain IDs, rather than layer hashes
alone, determine whether an existing unpacked snapshot can be credited.

The calculation adds missing compressed blobs, missing snapshot projections,
metadata bounds and a 512 MiB operating margin. Existing installed images remain
in the baseline usage. The minimum of the dated native/kubelet/Longhorn readings
is used; the stricter applicable kubelet floor and unchanged Longhorn 25% minimum
both apply. Reserve settings and automatic engine-upgrade limit remain unchanged.

| Node | Additional core-node budget | Core headroom missing | Complete-candidate budget | Complete headroom missing |
| --- | ---: | ---: | ---: | ---: |
| master | 3,593,551,872 | 2,529,797,121 | 5,097,279,488 | 4,033,524,737 |
| worker2 | 3,593,551,872 | 0 | 5,097,279,488 | 0 |
| worker1 | 3,593,637,888 | 0 | 5,097,365,504 | 0 |

Core-node covers manager, engine, instance manager, node registrar and liveness
probe. It is a lower deployment envelope, not the final accepted upgrade scope.
The complete candidate covers every reviewed component. Exact component
placement, host-side engine payloads, recovery and replica capacity remain
separate gates. Every node is untainted; the existing Longhorn deployments have
empty node selectors and tolerations. Controllers cannot simply be assumed
excluded from the master. No placement settings were changed.

The master clears its existing floors today, but its projected post-upgrade
usage does not. Both workers clear these image projections. Neither result
authorizes an image import or driver change during Ingenium's owner's ongoing
verification. The supported manager/engine upgrade remains unapplied.

## Next qualified cleanup selection

Read-only inspection identified two old Go module-cache trees totaling
**1,269,821,440 allocated bytes**, plus two extracted SDK copies totaling
**564,621,312 bytes**. These are candidates, not deletion eligibility. The old
source archives contain matching cache member names, but full per-file/archive,
identity, retention, lock/source and complete-reference checks still need to run.
One failed build record lacks a recorded archive hash; record that gap rather
than treating it as an authenticated old backup.

Both original source trees, lockfiles, archive files, failed diagnostics and
historical binaries are protected. The old `_output` also contains executable
copies whose recorded hash differs from the installed kubectl; deleting that
whole directory would be wrong. The bounded selection is described in
[the master cleanup plan](MASTER-GENERATED-INPUT-CLEANUP-20261027.md).
A metadata-only journal survey also found five closed files older than 72 hours,
385,908,736 allocated bytes. They require their own complete preservation and
independent restore proof before any retirement.

## Evidence and reconciliation

Everything reuses the original F-backed root, under
`platform-upstream-review-20261027/longhorn-capacity-budget`. The original native
CLI attempt used an unsupported `--quiet` switch. It made no node change; its
source/failure receipt survives. The corrected collector used the installed
CLI's actual table and native info output and completed on all three nodes.

The measured job is terminal/collected. Complete reference, namespace, source
and input checks qualified its one empty `tmp` directory for removal:
**4,096 allocated controller Linux bytes**. No temporary directory remains.
The 143 retained source/input/measurement/cache/provenance/failure paths total
686,830 logical bytes excluding their inventory itself; every path, hash and
retention reason is recorded in `output-inventory.json`. No dependency, compiler,
cache or image-payload tree was created. No Windows disk recovery is inferred.
[Sanitized exact receipt](../evidence/longhorn-capacity-audit-20261027.json).

The full goal stays active. Additional qualified master cleanup, fresh recovery
coverage, guarded upgrade implementation, vendor/host exceptions and final normal
Seerr/YTPTube IAB/fleet acceptance remain open.
