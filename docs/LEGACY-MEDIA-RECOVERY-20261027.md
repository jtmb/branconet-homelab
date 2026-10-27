# Preserve legacy media and retire verified duplicate files

Owner: migration chat `01a12045-bf7e-73b3-8557-752d17c72ffd`. This is the existing
NAS-media migration, not a new storage layout or image publication route.

Two legacy media files beneath the master's retired, unmounted
`/mnt/plex_smb_share/downloads` had no same-path NAS copies. Their exact private
names, source inode/device/ownership/mode/times, SHA-256 and NAS paths are kept in
the existing F-backed root under
`node-cleanup-20261027/legacy-media-recovery-d69c6e4627d049108d65185fd828de56/receipt.json`.
User filenames are not published in Git. Total file bytes: **5,639,537,729**.

The Windows operator streamed both files directly from the existing strict WSL
SSH connection into their intended existing NAS downloads folder. It staged no
media locally, refused all name collisions, flushed the NAS writes, and read
every final byte back for SHA-256 comparison. Both copies passed; a final source
inventory confirmed unchanged source identities and hashes. NAS modification
times are preserved to SMB precision; exact original ownership/mode/nanosecond
times remain in the recovery receipt. Originals have not been removed by the
copy program.

Before retirement, the complete original metadata, copy receipt and reviewed
operator sources were encrypted using the existing pinned age binary and SSH
recipient. Every archive member and full age authentication passed locally.
The existing approved NAS recovery destination then passed full ciphertext hash
read-back and age authentication:

- Bytes: `61,652`
- SHA-256: `a4dcf9aa883463add42f9d426158e78d2e2e503c27e2509af1c4db790ab6192a`
- NAS: existing `Branconet-Recovery-Backups/2026-10-25/ciphertexts/sha256-<hash>.age`
- Existing independently verified DPAPI recovery-key backup is reused.

Retirement completed at 09:13 UTC on October 27. Only those two verified local
duplicates were removed, recovering **5,639,553,024 allocated node bytes**.
The three original `.metube` state files and all other legacy data remain.
The existing YTPTube pod, running as uid 1000, subsequently read both canonical
NAS files through its unchanged SMB CSI claim: sizes and initial bytes matched.
Full-file integrity was verified by the preceding complete NAS readbacks.

`lock-verified-nas-media.py` holds read-only Windows/Samba file handles that allow
readers but deny writes/deletion, repeats the complete NAS hashes, and keeps
those handles open until the reviewed child operation terminates. A private
fresh proof binds both actual handles' files and original source identities.
The node helper repeats the original complete hashes, enforces the actual ext4
UUID `763cda3d-0777-4b03-a882-9d21060466e3`, refuses Git ancestors, active unit/
process/mount references and changed/hard-linked files, and unlinks individual
names through the verified parent directory descriptor. It preserves the entire
`.metube` directory, every other download and the old directory itself.

Recovery: authenticate/decrypt the metadata packet using the existing operator
identity or verified DPAPI recovery key. Copy the canonical NAS media named in
its receipt to the explicitly chosen recovery location, verify the recorded
SHA-256, and restore the recorded numeric uid/gid, mode and modification time.
The active NAS media files themselves remain available through the established
SMB CSI downloads volume. Do not reactivate a legacy host mount or overwrite a
current file to perform recovery.

Control/evidence and frozen sources remain in the same declared F-backed output
root. The only large outputs are the two intended NAS runtime media files;
completed transfer partials were renamed into those final paths, so there is no
extra local staging tree or new build/cache root. The initial metadata-copy
plan-name typo failed before NAS writes; its source is retained, and the corrected
copy succeeded. Repeatable host retirement is maintained in
`playbooks/legacy-download-retirement.yml`; keep its default inspect-only setting
and invoke apply only under the live Windows NAS-lock operator.

The initial native lock implementation failed on Windows `os.fstat` before
starting the node child. Its source and failure record remain. The corrected
implementation uses Win32 handle metadata and reads, and explicitly proves that
write and delete access are denied while ordinary readers remain allowed.
Both NAS handles stayed open through successful child termination. Exact paths,
per-file hashes and measured filesystem change are in
`retirement-result-38dd2ba11b0c48b7af77f75a9f00906d.json` in the private run above;
the sanitized [receipt](../evidence/legacy-media-recovery-20261027.json) binds its
SHA-256 without publishing user filenames. This is Linux node recovery; it does
not claim Windows filesystem recovery.
