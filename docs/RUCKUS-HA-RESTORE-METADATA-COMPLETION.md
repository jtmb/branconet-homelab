# Finish the recorded Ruckus restore metadata only

This new helper supplements the immutable protocol at
`FBASE/control-source/ruckus-ha-ro-anchor-20261025`. It does not modify the core,
replay restore, create/delete a reader, change a claim/chart or start MySQL.
Only source/AST checks were performed during implementation. Root owns execution.

The exact failed restore receipt is
`ruckus-ha-recovery-20261025/restore-c467d6a6880b4dbc87a227f341d93894/receipt.json`
(SHA256 `6d11cc347fc96b2d76a4d933a23610e59b40d109c543c3b46e51a77deac2c4bc`).
Its completed copy has all 213330203 bytes and 298 entries, but chmod-before-chown
without FSETID cleared SGID on exactly `data-0` (0775 instead of2775) and
`data-0/lost+found` (0770 instead of2770). The new helper requires precisely that
full portable-manifest difference, the failed target inode292 and measured
lost+found inode598. It refuses any other change or an already/partially repaired
state. Do not rerun the original O_EXCL restore or delete/recreate the target.

## Operator commands

Freeze this new helper to an operator-selected F source path and verify its
reported SHA256. `FBASE` is the approved native external mount:
`/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025`.
`HELPER` below is that exact frozen helper path; `HMAC_KEY` is the existing
protected file containing the original 32-byte key as hexadecimal. Never print
the key or put it in argv. No new key is valid for this lineage.

Choose a new 12-character lowercase hexadecimal `RUN_ID`; never reuse the old
507afdb956d8 reader. Generate a plan on F with umask077:

```sh
umask 077
python3 -I -B "$HELPER" plan --reader-run-id "$RUN_ID" > "$PLAN_ON_F"
```

The emitted List is exactly the frozen core restore reader+deny-all policy with
only FSETID appended to DAC_OVERRIDE, CHOWN, FOWNER. Whole original is mounted
read-only; only existing `security-data-20261025` is mounted read-write at
`/restore`. No fsGroup, extra volumes, API token, host network or resource change.
The remote frozen guard checks the supplied four-capability plan exactly.
Root must remove only the old recorded reader/policy by UID, wait for absence
(up to the existing90-second bound), create this new reviewed plan and record
its actual Pod and policy UIDs. The helper itself never performs those actions.

After the new reader is Running and the old reader is absent:

```sh
python3 -I -B "$HELPER" complete \
  --reader-run-id "$RUN_ID" \
  --reader-pod-uid "$NEW_READER_POD_UID" \
  --reader-policy-uid "$NEW_READER_POLICY_UID" \
  --execute-two-directory-mode-repair < "$HMAC_KEY"
```

The complete phase repeats current exact protocol native Secret/claim/PV/
Longhorn replica/Flux zero-writer fences, existing age/tool identity checks,
complete age authentication, cold manifest hash checks and original-tree
preservation checks. It obtains a fresh full restored hash inventory and validates
only those two differences. Both directory descriptors are opened O_NOFOLLOW /
O_DIRECTORY, their inode/device/owner/group/mode/mtime/ctime checked against
that inventory, the root anchored against its read-only view, and effective
capabilities required to equal exactly the four declared capabilities. It then
uses exactly two fchmod calls: root2775 and lost+found2770. It does not chown,
change timestamps, open data files for writing, execute SQL or alter grants.

Afterward it rehashes every restored byte, demands full portable metadata equality
to the authenticated cold manifest, retains every inode/size/mtime/ctime except
those two chmod ctimes, repeats original-tree and remote guards, fully authenticates
the age archive again, and rechecks source/tool/key/cipher/receipt identities.
C/destination15GiB guards remain; temporary files and private receipts use F only.

## Receipt and later acceptance

A fresh `OUT/restore-<UUID>/receipt.json` is always used after authenticated
execution starts; earlier failures remain. It has phase=restore and the same
base protocol `sources` so normal frozen core after/restart can verify its HMAC
and `new_sibling_identity`. It additionally declares
`completionKind=two-directory-SGID-metadata-finish`, separate helper/program
hashes, exact failed lineage, and actual two-operation result. It does **not**
claim the original core main executed the repair. Full before/after manifests
are retained privately beside the receipt. A partial repair or later guard
failure remains failed and requires review; there is no permissive retry path.

Use the new passed receipt/hash as `--restored`/`--restored-sha256` for the
unchanged protocol's later after/restart observations. Root owns reader cleanup,
Flux publication and application startup. Preserve both original/current claims,
all cold archives, every failed receipt and all original source files.
