# Master journal preservation and scanner-copy retirement

Completed October 27, 18:47 UTC. Recovered **561,950,720 allocated master Linux
bytes** in two bounded operations. Cumulative qualified node cleanup is
**25,476,104,192 bytes** across nine operations.
[Exact removed paths, hashes, restore and health evidence](../evidence/master-journal-audit-cleanup-20261027.json).

## Closed journals

Five exact closed journals, each older than 72 hours, were encrypted directly to
the existing NAS destination. There was no local archive. The 385,988,820-byte
ciphertext is `Branconet-Recovery-Backups/2026-10-25/ciphertexts/sha256-e20a34a254380bacadb2f887361590d5714a50066f983a6780eb04cb20f6e7d2.age`
on `\\TRUENAS\plex_smb_share`. The complete readback passed age authentication.

Every file was independently restored on F: ext4, one file at a time, and matched
full content SHA256, numeric ownership, permissions, nanosecond mtime and every
extended attribute. Each passed `journalctl --verify`. The isolated restore used
256 MiB memory, no swap, one CPU, 64 tasks and no network. All restore scratch was
reconciled: 385,880,064 allocated bytes created and removed during verification,
not net controller recovery.

During retirement the Windows operator held the full hash-verified NAS archive
with read-only deny-write/delete handles. The node helper rechecked the original
master filesystem, every selected identity/hash/attribute, retention and complete
unit/process/FD/map/mount references. Only the five exact journal files were
unlinked; **385,908,736 allocated node bytes** were recovered. Active/unselected
journals and all retention settings remain. No service was stopped or vacuum run.

The existing opt-in Ansible journal role now supports only the original worker2
or master, binding node names to their original filesystem UUIDs and addresses.
It preserves the old default and existing worker evidence. The maintained
`run-archived-journal-offload.py` launcher collects the existing protected TTY
credential before worker creation. Syntax, live inventory, independent recovery
and actual retirement all passed. No credential environment, argument or file.

## Original public scanner duplicate

Removed only the exact old `audit20261023-20261023T203418Z/bin/trivy` and its empty
`bin` directory on master: **176,041,984 allocated bytes**. Its original official
Trivy 0.76.1 provenance and complete hash match the retained primary scanner in
`local-oci-scan/bin/trivy` on F:. Regeneration copies that identical retained
public tool to a fresh owned stage; no old audit or deployment needs replaying.

All 311 unselected audit entries retained their original identities and bytes,
including original source, provenance, reports, inputs, cache and failures. The
root directory's expected timestamp/link changes from removing its empty child
are excluded; its inode, owner and mode remain. Complete source/hash/72-hour/
unit/process/open-file/map/mount guards passed before deletion. The new default
inspect-only `retired-master-audit-tool.yml` role and maintained launcher passed
syntax, actual inspection and opt-in retirement. No image or runtime was pruned.

## Reconciliation and remaining gates

Qualified empty Ansible scratch removal recovered **65,536 controller Linux
bytes**, 32,768 for each operation. Late framework packaging cleanup was not
measured or credited. All original source/ciphertext/proof/failure files remain;
35 current source/evidence files total 434,760 logical bytes excluding their
final index. No dependency, build cache, local ciphertext or raw restore tree
remains from this checkpoint. Older recorded runtime/ownership exceptions remain.

Post-checks: three Ready nodes, all 58 original claim bindings and 44 volume
identities preserved, attached volumes healthy, no unavailable Deployment or
DaemonSet, and all unsuspended Flux resources Ready. The storage minimum is
unchanged at 25%; automatic engine upgrade remains zero. Native master
available/free bytes are 27,384,635,392 / 32,701,272,064. No Windows physical
recovery is inferred from these Linux measurements.

Longhorn reported 32,610,713,600 available bytes. Reusing the earlier image
projection, the core-node profile now clears that floor by 91,642,879 bytes;
the complete candidate still lacks **1,412,084,737 bytes**. This is a dated
capacity comparison, not fresh native cache verification, unpacking, recovery
capacity or upgrade approval. No image pull, driver change, placement/replica/
threshold change or volume attachment occurred. Application/detached-data
coverage, actual placement/capacity, supported upgrade, security exceptions and
final normal Seerr/YTPTube IAB/fleet acceptance remain. Full goal active.
