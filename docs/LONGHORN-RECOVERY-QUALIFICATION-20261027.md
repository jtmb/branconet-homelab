# Longhorn configuration backup and offline control-plane recovery

Owner: migration chat `01a12045-bf7e-73b3-8557-752d17c72ffd`.
The full migration/security goal remains active. No Longhorn upgrade or
application-volume restore is credited by this checkpoint.

## Native configuration backup completed

The original available NAS target and its UID were checked immediately before
submission. One native SystemBackup was created through the new opt-in Ansible
role: `preupgrade-20261027-d9c7f2b7`, UID
`a080356f-744a-4adf-81d9-d313f19ff8ef`. It reached `Ready` on installed v1.12.1.
Its per-operation `volumeBackupPolicy: disabled` requests a configuration bundle
without volume snapshots/backups. It does not disable any existing backup job
or change a global setting. There were no backing images to trigger separate
backing-image work, no image pulls and no deliberate volume attachments.

Final native files reside in the existing target:
`\\TRUENAS\container_backups\k8s-migration-20261009\longhorn\backupstore\system-backups\v1.12.1\preupgrade-20261027-d9c7f2b7`.

| File | Bytes | SHA-256 |
| --- | ---: | --- |
| system-backup.zip | 79,255 | `7f9cae90444bf68e3283b81bfb1f0eec15aa1b7237b8c5848af8c65e206487d7` |
| system-backup.cfg | 494 | `71bbec7ad0f50e48e863f026486dfd3cde0083ada7c2dc04ec8af172c42a6044` |

Two full NAS readbacks passed. The ZIP's checksum matches its native configuration,
every member passes CRC, and all 20 YAML documents parse in memory. The bundle
contains all 44 prepared Longhorn volume UIDs and all 44 exact volume/PV/PVC
binding chains. No payload was copied to local disk. It contains no Secret
objects and is not an application-data backup. Native Secret/encryption-key
recovery requires the separate protected control-plane archive below.
[Official scope and policies](https://longhorn.io/docs/1.12.1/advanced-resources/system-backup-restore/backup-longhorn-system/).

`playbooks/longhorn-system-backup.yml` supplies prepare/create/observe phases.
Prepare is a server dry-run; create requires its explicit apply flag, unchanged
prepared source/volume identities, and a fresh intent receipt. Existing evidence
and backup names cannot be overwritten or blindly resubmitted. The first
observer encountered a null conditions list; its failure and submitted source
remain. The corrected observer verified the same UID. The native bundle uses
lowercase metadata keys; the initial parser and corrected verifier are retained.
These were local inspection errors, not failed backup or policy rejections.

## Actual offline database restoration qualified

The existing control-plane ciphertext was freshly read in full from the approved
NAS recovery store: 76,921,380 bytes, SHA-256
`de348e280924bfaa4637aaeb4f94cef4396612be973eda0732209fa5516ee268`.
The retained local ciphertext has identical bytes. Complete age authentication
and all 46 configuration-file hashes passed again. Encryption configuration
contains valid native-Secret encryption keys, and the original Longhorn volume
encryption key is present. No configuration or key file was extracted to disk.

The restore utility came from the exact public image already running in
production, not a bespoke rebuild:
`registry.k8s.io/etcd:3.7.3-0@sha256:0d27b9478551f431f82d1e0ddb6c87ad07ebae8b904c637f3a99213349523910`.
The amd64 manifest and each downloaded layer were SHA-256 checked; only the
16,601,250-byte `etcdutl` binary was written locally. Binary SHA-256:
`e3bd459308395080493488003f8cd4498db7ad4237584881b00f948a47950d2f`.
No layer archive or container image was staged on a cluster node.

`etcdutl snapshot restore` completed into an isolated local directory. A fresh
authenticated probe and that restored database have:

| Check | Original | Restored |
| --- | ---: | ---: |
| Revision | 10,110,797 | 10,110,797 |
| Key count | 2,568 | 2,568 |
| Native key-history hash | 1,316,829,015 | 1,316,829,015 |
| History hash revision | 10,110,797 | 10,110,797 |
| Compaction revision | 10,107,264 | 10,107,264 |

The initial comparison wrongly required the whole database hash to remain equal
across membership restoration. Its failure and exact source remain. The native
key-history comparison is distinct from that whole-database hash. `hashkv` opens
a backend and can update disposable database metadata; it was used only on
generated probes. A second freshly authenticated probe reproduced the first
probe's modified bytes exactly. Both sources and native code explaining these
semantics remain with the evidence.
[Native hash implementation](https://github.com/etcd-io/etcd/blob/v3.7.3/etcdutl/etcdutl/hashkv_command.go),
[native snapshot implementation](https://github.com/etcd-io/etcd/blob/v3.7.3/etcdutl/snapshot/v3_snapshot.go).

Jobs ran as the ordinary controller user with 512 MiB memory, no swap, one CPU,
64 tasks, a private network namespace and filesystem writes restricted to the
existing owned qualification directory. No etcd server or network listener was
started. Production etcd, kubeconfig, native Secrets and volumes were untouched.
This is an offline restore of the dated 03:47 UTC backup. It does not compare
current Secret values, start an API server, restore Longhorn application data,
or replace the need for a fresh pre-upgrade checkpoint after concurrent cutover.

`playbooks/control-plane-restore-qualification.yml` maintains this bounded
operation, with apply disabled by default. It requires the prepared exact NAS
proof/public tool and the root controller launcher for its unprivileged job.
It refuses replacing prior results; reviewed existing-state qualification
preserves the original failed attempt and does not replay the restore command.

## Reconciliation and remaining work

All control files use the existing F-backed task root. After terminal job,
creator/inode/hash, complete process/file-descriptor/mapped-file/mount/unit,
source/lockfile and regeneration checks passed, exactly 12 generated entries
under `etcd-restore-qualification/{tools,scratch}` were removed:
**305,160,192 allocated controller Linux bytes**. The original encrypted backup,
registry/source manifests, all failed sources and receipts, native NAS bundle
and minimal qualification evidence remain. No node or Windows disk recovery
is inferred from this controller allocation measurement.

Ingenium's separate owner completed data transfer to the worker1/worker2 pair
and is performing application cutover. No driver upgrade, new pull or Longhorn
volume change is permitted here during that interval. Further node deletion
requires the same qualified preservation checks; protected legacy data is not
an unused-cache assumption. Application-consistent/detached-data coverage,
fresh pre-upgrade recovery, platform upgrade capacity and implementation, vendor/
host exceptions, final Seerr/YTPTube IAB and whole-goal acceptance remain open.

The corrected recovery metadata packet contains 51 explicitly checked members,
471,364 bytes, SHA-256
`2acc290180bad5ecb014147d9c4e60265fc46ffd7dd928a517cf62ca178bfe34`.
Every member and complete NAS readback/authentication passed. It includes actual
preflight, native bundle, offline restore and cleanup receipts/sources. Two early
71,908-byte selection attempts had authenticated old media receipts because of
a newline-sensitive replacement. They remain labeled failure evidence and do
not count as recovery qualification; only the first had been uploaded. The
corrected operator uses explicit selection boundaries and required-member guards.
[Exact sanitized checkpoint](../evidence/longhorn-recovery-qualification-20261027.json).
