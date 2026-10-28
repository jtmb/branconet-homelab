# Fresh control-plane recovery checkpoint

Completed October 27 at 18:15 UTC. Maintained Ansible roles captured a new encrypted
checkpoint and performed an independent offline etcd restore. Production was
never restored or stopped. [Exact evidence](../evidence/fresh-control-plane-recovery-20261027.json).

| Check | Actual result |
| --- | --- |
| Backup ID | `e90319b39ff741ab9dbc9f7d09cc6187` |
| Ciphertext | 76,921,380 bytes |
| SHA256 | `ea57aacc08d41a98a88689003915e14d96d15865b1b263a8b54440f963ac4a3a` |
| Local authentication | Complete age authentication; all 46 configuration files verified |
| NAS copy | Full ciphertext readback, identical to authenticated source; no plaintext copy |
| Key configuration | Native Kubernetes Secret encryption configuration and volume key present |
| Actual restore | 2,801 keys; revision 10,442,118 unchanged |
| Logical key-history hash | 3,191,081,841 unchanged |
| Production mutation / listener | Neither occurred |

NAS artifact:
`\\TRUENAS\plex_smb_share\Branconet-Recovery-Backups\2026-10-25\ciphertexts\sha256-ea57aacc08d41a98a88689003915e14d96d15865b1b263a8b54440f963ac4a3a.age`.
The producer's historical `nas_copy_verified=false` records the initial stage;
the separate full-readback proof closes NAS copying. No separate direct NAS
age-decryption stream is claimed.

The backup action now consumes Ansible's existing in-memory become credential,
collected through a protected terminal before worker creation and sent through
SSH stdin. No credential environment, argument or file is used. The first
child-terminal attempt failed before creating any backup; its evidence remains.
Actual backup execution passed: three tasks OK, one changed, zero failed.

The restore role accepts a paired explicit backup UUID and ciphertext SHA256,
bounded to the existing task root. Separate proof/scratch/result/unit names
preserve earlier checkpoints and failures. Actual execution passed: three tasks
OK, zero failed. The ordinary-user job had a private network namespace, 512 MiB
memory, no swap, one CPU, 64 tasks and writes confined to its recovery directory.
Whole-database hashes differ after membership metadata rewrites; logical key
history, revision and key count are unchanged.

The pinned official etcdutl 3.7.3 program was exported read-only from the existing
etcd container after binding Pod UID, image, native containerd task and full hash.
No external download, image pull or cluster change was needed. An earlier
external-download helper was rejected before execution by automatic review,
which supplied only "blocked by policy"; that route was not retried. A preliminary
lookup failed before creating a binary because the node lacks crictl; the native
containerd lookup succeeded. Failed sources and diagnosis remain.

Cleanup removed **213,725,184 allocated controller Linux bytes**: only this
restore's raw snapshot/database/WAL files and verified empty Ansible scratch.
Exact paths and counts are in the linked ledger. Terminal unit state, complete
unit/process/FD/map/mount checks, identities/hashes and all unselected source,
ciphertext and failure preservation passed. Late framework cleanup was not
measured or credited. No Windows recovery is inferred.

Retain one operational `etcd-restore-qualification/tools/etcdutl`: 16,601,250
logical / 16,605,184 allocated bytes, SHA256
`e3bd459308395080493488003f8cd4498db7ad4237584881b00f948a47950d2f`,
for the final pre-upgrade recovery gate; reconcile it afterward. The checkpoint
retains 26 source/evidence files, 138,246 logical bytes excluding its index, in
the existing F-backed root. No raw recovered database remains. All original
local/NAS ciphertexts and prior evidence remain.

This proves the dated control-plane checkpoint and offline native restore.
API decryption, whole-cluster restoration and application-volume recovery are
separate. Recheck recovery coverage and take the final checkpoint immediately
before the platform upgrade. Longhorn capacity/upgrade, application/detached-data
coverage, security exceptions and final application/fleet acceptance remain;
the full goal stays active.
