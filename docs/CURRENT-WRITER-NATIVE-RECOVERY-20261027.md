# Current Ruckus and Ingenium native recovery

Both current writers have completed full native backups on the existing NAS.
The opt-in Ansible checkpoint preserves each exact original writer Pod UID,
image, restart count, Volume specification and two original replica UIDs.
It does not stop applications, alter attachments or change storage settings.
[Exact receipts](../evidence/current-writer-native-recovery-20261027.json).

| Dataset | Native backup | Independent RAW verification |
| --- | --- | --- |
| Current Ruckus | `migration-preserve-5ff4ab4a37cc-backup` | 420 blocks; stock restore command exited zero |
| Current Ingenium | `migration-preserve-780aa9b0a19b-backup` | 4,869 blocks; complete native RAW backing verified; optional RAW-to-RAW copy timed out |

These are live native sync/atomic snapshots. No database quiescence, filesystem
freeze, decrypted mount or application-row recovery is claimed. Longhorn's
[documented snapshot behavior](https://longhorn.io/docs/1.12.0/references/settings/#freeze-filesystem-for-snapshot)
is distinct from an application-consistent cold backup. Original application
backup/acceptance receipts remain separate and protected.

## Ingenium timeout and exact recovery

The native engine completed `backup.img` before its optional qemu RAW-to-RAW
conversion exceeded the original five-minute subprocess limit. The original
`TimeoutExpired` result and log remain unchanged; the original command did not
exit successfully. An initial follow-up also refused its simplistic assumption
that every allocated partial-output extent matched the source. Neither follow-up
modified either original image.

The unchanged original verifier then checked the complete `backup.img`: every
one of 4,869 independently decompressed backup blocks, every unbacked zero
region, the LUKS header, full 11,827,937,280-byte size and full SHA256 passed.
Stock qemu independently identified that backing as RAW. Its SHA256 is
`b6be7d4e33ed72b6f877928dd6f3d5dd8fde4226e45da97083a495473c9c39ba`.
No second full conversion or NAS download was necessary.

The maintained `preserve-large-native-restore.py` reads original files with
position-independent `pread`, classifies source-copy ranges and implicit zeros,
and bounds exceptional literal data to 16 MiB. For this actual partial image,
52 source-copy ranges and **zero literal bytes** reproduce its complete original
SHA256. A separate streaming reconstruction verified that recipe without
materializing another image. Original file identities remained unchanged.
The explicit acceptance status is
`native_raw_backing_verified_after_optional_conversion_timeout`; it never
relabels the failed original command as exit zero.

The original failure source, logs, invocation bindings, lossless partial recipe,
all block/header/hash proofs and original NAS backup remain under the existing
F-backed recovery operation. Restore scratch is subject to the same complete
Linux unit/process/FD/map/mount checks, native Windows exclusive file handles,
full original NAS readback, exact final identities and protected-source checks.
Cleanup completed: **27,452,293,120 allocated controller Linux bytes** across
9,861 paths removed; all 269 protected files unchanged. Exact selected roots
under `platform-upstream-review-20261027/detached-volume-backups-20261027/`:

- `ingenium-current/nas-stage`
- `ingenium-current/restore-work`
- `ansible-ingenium-current-prepare-scratch`
- `ansible-ingenium-current-apply-scratch`

The full per-path byte ledger is `ingenium-current/restore-scratch-reconciliation.json`
under the existing F-backed task root. Total recovery scratch retirement across
eleven datasets is **30,962,319,360 allocated Linux bytes**. No Windows physical
disk recovery is inferred. The shared 65,241,088-byte stock recovery toolset remains for
the supported platform upgrade's recovery window; retire it after that concrete
consumer closes. It is separate from build/dependency caches.

## Fresh cluster observation

Fresh metadata shows **74 Completed backup records covering all 43 initialized
Longhorn volumes**. The remaining 44th volume is the separately qualified unused
WordPress destination with no initialized payload. This is exact backup coverage,
not a claim that every historical backup is current to this observation.
The current-writer backups above close the two previously identified live-data
gaps. All three nodes are Ready, all 58 claims are Bound, and every Deployment
and DaemonSet is available. Exact UID/binding and unsuspended Flux comparisons
remain in the sanitized health receipt.

Across the eleven newly recovered datasets, **5,831 blocks** have independent
RAW verification. Ten original restore commands exited zero; Ingenium's native
RAW backing has the explicit qualified timeout acceptance described above.
This does not complete the platform upgrade or full migration/security goal.
Fresh production cache/capacity/placement, supported Longhorn upgrade, final
fleet/security exceptions and normal Seerr/YTPTube browser acceptance remain.
