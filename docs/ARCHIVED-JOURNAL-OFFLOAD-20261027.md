# Preserve closed journals before node-space recovery

Owner: migration chat `01a12045-bf7e-73b3-8557-752d17c72ffd`. Control, profile,
receipts and bounded restore scratch reuse the existing F-backed task root,
under `node-cleanup-20261027/worker2-journal-offload-20261027`. No model, service,
image, volume or running workload is stopped, changed or removed.

The reviewed worker2 selection is 23 regular, single-link, closed `@*.journal`
files under `/var/log/journal`. All are older than 72 hours and have passed full
active-unit/process/mapped-file/mount reference checks. Current journals,
directories and every unselected journal remain untouched. No sealing-key file
is present. The filesystem is the existing ext4 root, UUID
`960bc2c7-2a7e-4bc2-b2c5-dbb6d71207f4`.

Exact selected paths, inode/device identities, numeric ownership, mode,
nanosecond modification times, full SHA-256 and extended attributes are retained
in the private `profile.json` in that run directory. File data totals
2,097,152,000 bytes; original allocation totals **2,097,229,824 bytes**.

The existing strict SSH identity streamed these files directly through the
existing pinned age binary into the approved NAS recovery destination. There
was no local archive or plaintext tar staging. The complete source manifest is
inside the encrypted tar; standard PAX fields retain exact times and SCHILY
extended attributes, including POSIX access ACLs and original creation metadata.

Qualified NAS archive:

- Path: existing `Branconet-Recovery-Backups/2026-10-25/ciphertexts/sha256-9b3629f07ffaa9330462ce42e06baa95b56b1a64895a0c191c259b4577142600.age`
- Bytes: `2,097,725,652`
- SHA-256: `9b3629f07ffaa9330462ce42e06baa95b56b1a64895a0c191c259b4577142600`
- Full NAS ciphertext read-back and age authentication passed.
- Existing independently verified Windows CurrentUser DPAPI recovery-key backup
  is reused; the original WSL identity remains protected.

Every one of the 23 archive files was independently restored onto the F-backed
ext4 filesystem, one file at a time, with a maximum 128 MiB plaintext file. Full
bytes/SHA-256, uid/gid, mode, nanosecond mtime and every extended attribute matched.
Each restored file passed `journalctl --verify`. Restore ran in an isolated job
limited to 256 MiB RAM, no swap, one CPU, 64 tasks and no network. Each restored
file was removed only after verification and complete inactive-reference checks;
the empty restore directory was removed too. The 15 GiB free-space floor held.
`restore-receipt.json` records the measured scratch allocations reconciled; those
are temporary allocations created and removed during verification, not net
controller or Windows disk recovery.

Retirement completed at 10:10 UTC on October 27: the exact 23 selected files were
removed, recovering **2,097,229,824 allocated node bytes**. Worker2's measured
available filesystem space increased from 25,123,418,112 to 27,220,647,936 bytes
during this operation. Active and unselected journals remain. No retention
setting, service or journal vacuum was changed.

The Windows operator rechecks and holds the authenticated NAS archive open with
read-only, deny-write/delete handles through the node operation. The node helper
rechecks full source hashes, extended attributes, identities, age, filesystem and
active references, then unlinks individual names through opened parent directory
descriptors. It does not run a blanket journal vacuum or alter journal retention.
Full partial outcomes survive if any later check fails.

The successful private receipt is
`retirement-result-93403c97f15943a890b2edcbbab51fe4.json` in the run above.
The [sanitized receipt](../evidence/archived-journal-offload-20261027.json) records
all 23 exact removed paths and allocations. The independent restore reconciled
**2,097,156,096 allocated scratch bytes** one file at a time; these were created
and removed for validation, not net controller recovery. `restore-scratch` no
longer exists. Required ciphertext, manifest, receipts and frozen operators
remain. No Windows disk recovery or VHDX compaction is claimed.

Recovery: decrypt using the existing identity or its verified DPAPI recovery key;
extract into an explicitly chosen empty recovery directory using GNU tar with
`--numeric-owner --same-owner --preserve-permissions --xattrs --xattrs-include='*'`.
Verify all files against the encrypted manifest and use `journalctl --directory`
on the recovered journal directory. Do not overwrite current journal files.

Repeatable entry point: `playbooks/archived-journal-offload.yml`, with default
inventory mode and apply disabled. `backup-archived-journals-to-nas.py` supplies
the existing Windows NAS transport and bounded independent restore;
`lock-verified-nas-media.py --journal-profile` keeps the backup locked for
retirement. Apply requires the live operator and exact qualified profile.
