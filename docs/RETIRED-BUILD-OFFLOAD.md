# Retired public build artifact offload proposal

Current checkpoints and unresolved gates are summarized in [MIGRATION_STATUS.md](../MIGRATION_STATUS.md). This document retains operational contracts and dated attempt history.

Prepared source only: no archive or cleanup has been run. This is host artifact
capacity maintenance, independent of application/security qualification and
recovery acceptance. It never executes an old helper, replays a failed build,
accesses workload data, inspects credential values, changes a service or removes
an entire build tree. The existing failed attempts remain authoritative history.

The only source roots are these exact master paths:

| ID | Whole tree archived | Sole expendable directory eligible later |
|---|---|---|
| b5d6d1 | `/home/james/.local/share/branconet-migration/root-custom-kubectl-build-20261012-b5d6d1` | `kubectl-security-a4cc69125f81/cache` |
| f73dc0 | `/home/james/.local/share/branconet-migration/root-custom-kubectl-build-20261012-f73dc0` | `kubectl-security-53c90b1e408a/cache` |

Root's privileged metadata tally on October 23 measured inner-tree allocated
bytes as follows. These are observations, not guaranteed reclaim amounts:

| Inner child | b5d6d1 bytes | f73dc0 bytes | Deletion permission |
|---|---:|---:|---|
| Inner root total | 1,791,197,184 | 2,777,735,168 | Retain |
| cache | 44,937,216 | 923,328,512 | Separate reviewed phase only |
| go SDK | 282,308,608 | 282,312,704 | None; possible later proposal |
| gopath | 6,209,536 | 6,209,536 | None |
| kubernetes source/output tree | 1,009,573,888 | 1,133,371,392 | None |
| tmp | 4,096 | 4,096 | None |
| home | 40,960 | 65,536 | None |

The cache-only total is 968,265,728 bytes. The two SDKs total 564,621,312 bytes
but remain outside this deletion allowlist. The helper records identities, logical bytes and cache
allocated bytes before work. No Go source, compiled output, receipt, log, failure
evidence, lock or other directory is on the deletion allowlist.

Inspect receipts also tally allocated/logical bytes for direct children and one
level beneath each inner build root, identifying SDK/tool/gopath/temp capacity
for later review without adding any deletion permission. Hardlinks are deduped
for the allocation tally, but cache directory allocation is not a guarantee of
freed filesystem bytes if other hardlinks still retain blocks. Expected OCI
import/unpack space requires the actual new archive/config/layer measurements;
neither these cache tallies nor a recovered node establish that capacity.

## Explicit phases

The new `playbooks/retired-build-offload.yml` and `retired_build_offload` role
target only masternode/192.168.0.4, james, SSH 2002. Apply defaults false; mode
defaults inspect and cache selection defaults empty. The launcher is
`scripts/migration/run-retired-build-offload.py --settings-file <absolute-file>`.
The protected dispatcher supplies only the sudo credential JSON on stdin. The
launcher retains it only in the private child environment; the controller helper
removes it before spawning SSH/age and passes it to sudo through a pipe. No value
is present in argv, settings, output or a credential file. Ansible command output
is no_log, and only protected evidence locations are reported.

Example nonsecret settings for **inspection only**:

```json
{
  "retired_build_offload_apply": true,
  "retired_build_offload_mode": "inspect",
  "retired_build_offload_output_dir": "/home/brajam/.local/share/branconet-migration/retired-kubectl-offload-20261023"
}
```

Inspection reads actual hostname, root UUID/source/type, exact tree/cache inodes,
owners/modes and bounded recursive metadata. It scans the complete active,
activating and deactivating systemd inventory's ExecStart/WorkingDirectory in RAM
for those exact paths; a match refuses. It records only inventory hash/count,
never raw unrelated commands. Optional `retired_build_offload_additional_units`
requires those exact historical units inactive too, if their names are known.
Absent transient unit names are not invented or treated as a prerequisite.
It checks process cwd/root/exe/fd/mapped-file targets and mount tables in every
readable process mount namespace, filtering only the two paths. Any matching
reference/mount or permission-denied/incomplete inspection refuses. Process races
that vanish are tolerated. Nothing is killed to make a tree idle. These are
bounded path-reference guards, not a workload/security inspection or a kernel
guarantee against a privileged concurrent actor.

After reviewing inspection, choose mode `archive`, with no cache selection. Both
whole trees must finish before any clearing is possible. GNU tar streams over
strict known-host SSH directly into checksum-pinned age 1.3.2 on native WSL; no
plaintext tar or archive staging file is written on the master. The fixed age
binary SHA is `eb7dd1b518f0a307c99cd97782623c5321da049154b04acd2d98d21aa7bc9b2c`.
It uses the existing operator SSH public recipient and existing private identity
for authenticated decryption, without copying either key. Destination must be
owner-only native ext4 under the migration runtime, outside actual Git ancestors.
Each invocation gets a new UUID directory; partial outputs are retained on error.

The complete tar uses POSIX/PAX format, numeric owners, ACLs, all xattrs, SELinux
metadata, sparse-file metadata and no-atime reads; symlinks are archived as links,
never dereferenced. Original ctime/atime are represented by PAX metadata; inode
numbers are not restorable filesystem identities. Root/cache inode/device and
root UUID are separately pinned for the destructive gate. Special entries that
cannot be safely represented refuse instead of being silently omitted. No
archive exclusions or missing-file tolerance is configured. Source metadata must
remain unchanged before/after streaming, and both idle checks must pass. GNU tar
must exit zero, including its changed-file/error checks.

Receipts bind source metadata, remote plaintext tar SHA/bytes, controller-received
SHA/bytes, local ciphertext SHA/bytes, full authenticated decryption through EOF,
and complete tar traversal/entry counts. Verification never extracts source or
executes a file. Complete decrypt authentication is required after tar EOF. Keep
the private identity and the encrypted archives independently recoverable; this
verification is not a full filesystem metadata restore rehearsal.

## Review before exact cache clearing

Archive mode never deletes. Root reviews the completed `verified-no-deletion`
receipt and records its exact SHA256. A new, explicit `clear-cache` invocation
requires all of:

```json
{
  "retired_build_offload_apply": true,
  "retired_build_offload_mode": "clear-cache",
  "retired_build_offload_output_dir": "/home/brajam/.local/share/branconet-migration/retired-kubectl-offload-20261023",
  "retired_build_offload_selected_caches": ["f73dc0"],
  "retired_build_offload_verified_receipt": "<absolute-verified-receipt.json>",
  "retired_build_offload_reviewed_receipt_sha256": "<reviewed-64-hex>"
}
```

Both ciphertexts and their authenticated plaintext/tar bindings are reverified
before deletion. Current source metadata/UUID/inodes must match the archived
receipt, with complete fresh idle/reference/mount checks. Only the selected
fixed cache paths can be removed, with fd-relative symlink-resistant rmtree after
pinning the exact parent/cache inode. Other archived files and the roots remain.
No recursive whole-tree removal, arbitrary path, automatic cleanup, retry,
overwrite, service stop or failed-attempt replay is implemented. A partial clear
requires operator review of its new evidence; nothing is automatically undone.

The helper is streaming/bounded, lowers CPU/I/O priority and uses a 30-minute
controller deadline. Each tree is limited to 500,000 entries, 16 GiB logical file
bytes and an 18 GiB tar stream. WSL free capacity is checked before archiving;
the initial check includes per-entry tar overhead and a 2 GiB reserve, which is
also checked while streaming each chunk. Archive verification and clear-plan/
per-cache results get separate exclusive receipts to preserve partial progress.
no host cleanup or disk expansion is attempted. Actual reclaimed bytes and
master/Longhorn reserve must be re-observed independently after an authorized
cache clear. No archive, cache clear or cluster health outcome follows from
source syntax checks alone.
