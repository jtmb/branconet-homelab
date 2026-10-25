# Qualified Ruckus MySQL copy: encrypted archive and fresh-claim restore

The 2026-10-25 archive action completed against the existing isolated, stopped
MySQL 5.7.44 **new tmpfs copy**. It did not run SQL, start a server, create or
delete resources, mount the original claim, or write production storage.

## Retained result

Approved generated root:
`/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025`.
All new archive/restore receipts use its `ruckus-upgraded-cold-20261025` subtree.

Completed archive directory:
`archive-1eaa4197956e42a4b319996b0d179bbf`.

- Cipher: `ruckusdb-5.7.44-qualified-data-0.tar.age`
- Cipher SHA256: `b9fe57342ddeac73e1877788f24d520d501e19cd3a483020c3a583878cf52fe8`
- Cipher bytes: 213,689,476; full file bytes: 213,330,338
- Scope: 296 entries, 290 files, **no exclusions**
- Manifest SHA256: `bcc90de4d0e079eadcfa327572b56723295b71ed6762837921f0d700f6d1f945`
- Receipt SHA256: `0181fa8442048910a51972a2294274aefb48dca41d98db4c8e38251e805ca30c`
- Executed archive helper SHA256: `b656020f87eb36a32cc194a25052ef8d42047cdb4585e29616779bd513e05c7f`

Before transfer, Windows C: had 139,412,414,464 bytes free and the verified
approved destination mount had 34,427,441,152 bytes free. Both exceeded the
15 GiB floor after the bounded projected archive stage. Output directory mode
is 0700; archive and receipt files are created under umask 0077.

The unchanged shared `pod_reader.py` inventories and archives only
`/copies/new/data-0`, aliased to `data-0`. It checks every file's content hash,
ownership/mode, timestamps and source fingerprint before/during transfer.
Age encrypts directly from SSH stdout to the local cipher; no plaintext archive
or manifest is written locally. Complete age decryption/authentication and the
shared tar verifier consume all encrypted data in memory, then a second full
source inventory must equal the first exactly. Original cold archive SHA256
`d9055b97e35af0afc9b2d6a9379697dd8b889e1633c27d5822e840e726cf86e0`
was checked before and after and remains retained in its original directory.

The existing recorded Pod, namespace, deny-all policy, images, resources,
tmpfs-only volumes, no-token/no-credential and UID contracts are checked using
the pinned existing observer's read-only guard. Both old/new launch.pid and
mysqld.pid must be absent. Any lingering MySQL process entry must have state Z
(unreaped zombie); no running/sleeping MySQL process is allowed. The successful
receipt retains the same original Deployment/HelmRelease/PVC/PV identities,
zero replica state and native Secret HMAC as before transfer. Secret values
remain in master RAM; the controller sends only the existing HMAC key on stdin.

Two failed **pre-transfer** attempts remain intact:
`archive-ca98eac86c5944e6a4fad51aad27cfcb` and
`archive-3322e71613ed45a681d79cb6a1c14561`. The first broad guard and then its
filtered diagnostic identified exited MySQL zombies. The corrected guard
distinguishes those from executable servers; it does not remove PID files,
kill processes or weaken the requirement that the copies remain stopped.

The prior normal-auth comparison already passed for 3,962 application rows and
the native account. The coordinator separately reviewed the upgraded system
schema difference (`mysql.gtid_executed` STATS_PERSISTENT=0) and preservation of
all rows/account hashes. This archiver does not repeat administrative SQL or
grant-bypass inspection; full physical scope includes all system grant files.

## Explicit archive invocation

Run from WSL using the canonical source checkout, only while the same qualified
copy and original cold guards still hold:

```sh
python3 -B scripts/migration/archive-ruckusdb-qualified-copy.py --archive-qualified-new
```

Every attempt creates a unique receipt directory; failures and prior ciphers
are retained. The helper creates no Kubernetes resources and performs no cleanup.

## Fresh-claim restore: completed, with original source retained

The parent completed the guarded restore on 2026-10-25. Receipt
`ruckus-upgraded-cold-20261025/restore-7cb2181d5197445e9cea2956455814c9/receipt.json`
has SHA256 `26ad95198e83ca170d721ad020b4994edb1c7e1cd8f40026ebf9f193a3b84f6b`.
It records `status=completed`, all 296 entries / 213,330,338 file bytes restored
with full file/metadata equality, source claim never mounted, and original
archive retained. The destination is `ruckus-db-data-0-security-20261025`, UID
`0bf707c8-628e-4284-9aa0-35b711c8749b`; it is separate from the original claim.
Normal production authentication, application acceptance and restart evidence
remain the coordinator's separate work; physical restore is not that proof.

`restore-ruckusdb-qualified-copy.py` never creates or deletes resources. Root must
first publish a **fresh**, separately named Longhorn claim through the existing
chart while both bot and DB remain at zero through observed, Ready Flux releases.
The original claim `ruckus-db-data-0`, UID
`2f604004-b45f-4061-bdc4-43f5ca2f7fd8`, must remain untouched and unmounted.
The paused DB template must already select the reviewed 5.7.44 image and the
fresh claim at `/var/lib/mysql` with `subPath: data-0`, retaining its native Secret
reference, original resources and unmodified normal entrypoint.

The helper requires a fresh claim created after the archive, no dataSource or
dataSourceRef, a distinct Longhorn PV/volumeHandle, and exact supplied claim UID.
It rejects any nonempty destination except an empty ext4 `lost+found` directory.
It never overwrites or resumes a partial restore. Retain a failed destination
and its receipt for review; do not delete it through this helper.

Set the following nonsecret operator arguments (paths shown relative to FBASE):

```sh
RECEIPT=/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025/ruckus-upgraded-cold-20261025/archive-1eaa4197956e42a4b319996b0d179bbf/receipt.json
RECEIPT_SHA=0181fa8442048910a51972a2294274aefb48dca41d98db4c8e38251e805ca30c
# Supply the new chart-owned claim name/UID and a fresh 12-hex run identifier.
python3 -B scripts/migration/restore-ruckusdb-qualified-copy.py plan \
  --archive-receipt "$RECEIPT" --archive-receipt-sha256 "$RECEIPT_SHA" \
  --claim "$NEW_CLAIM" --claim-uid "$NEW_CLAIM_UID" --run-id "$RUN_ID"
```

`plan` performs read-only guards and emits exactly one finite restore Pod and a
label-scoped deny-all NetworkPolicy for root to review/create. It mounts only
the fresh claim. The pinned Python reader runs on workernode2 with no application
entrypoint, no API token, no credentials, read-only root filesystem, 500m CPU /
512 MiB memory limits and only CHOWN/FOWNER/DAC_OVERRIDE capabilities. The
1,800-second finite lifecycle is not a production workload. After root creates
those exact objects, records their UIDs and waits for Ready:

```sh
python3 -B scripts/migration/restore-ruckusdb-qualified-copy.py restore \
  --archive-receipt "$RECEIPT" --archive-receipt-sha256 "$RECEIPT_SHA" \
  --claim "$NEW_CLAIM" --claim-uid "$NEW_CLAIM_UID" --run-id "$RUN_ID" \
  --pod-uid "$RESTORE_POD_UID" --policy-uid "$RESTORE_POLICY_UID"
```

The restore action first fully authenticates the archive without writing,
rechecks contracts, then streams a second authenticated decryption to the exact
destination. It reuses the pinned existing safe tar receiver, scoped only to
`/restore`; all original path/type/hash/ownership/mode/size bounds remain. Every
restored file is rehashed, and complete metadata equality includes nanosecond
mtime. Only filesystem-specific inode/device/ctime fingerprints are excluded
from this **cross-filesystem** comparison. Before/after original PVC/PV spec
hashes, fresh claim UID and native Secret HMAC must match. No SQL executes.

Root owns cleanup of only the reviewed restore Pod/policy with UID preconditions,
subsequent normal-auth DB startup, bot restart, original-account/app row acceptance,
and final cutover. Neither helper deletes the original claim, ciphers, failures
or restore resources. The actual restore result above supersedes the earlier
source-only checkpoint. All original rollback sources remain required.

## Completed cleanup of stopped tmpfs qualification copies

At 15:29:04 UTC on 2026-10-25, the separately authorized cleanup removed only
the three objects recorded in the immutable `acceptance-ruckus-20261025/copy-run.json`:

| Object | Name | Recorded UID |
| --- | --- | --- |
| Pod | `qualifier` in `ruckusdb-copy-808152145c8e` | `3dba58c4-3f25-4808-be75-42a9681a8ff2` |
| NetworkPolicy | `deny-all` in that namespace | `eb9d602e-3178-4db8-a422-b3a143725830` |
| Namespace | `ruckusdb-copy-808152145c8e` | `5d69f2d1-d3a9-440b-a80e-7990d651a3c9` |

New private receipt, relative to FBASE:
`acceptance-ruckus-20261025/cleanup-stopped-copies-baf3d4a2c94247939242c691474ceb22/receipt.json`.
SHA256: `ec6595e9bf719007d8b2430e57cda3377cb3b54792d1cd127e3a0301b0278aff`.
The receipt retains the exact remote cleanup source hash and all delete/wait results.

Before deletion, the master imported only the hash-verified
`copy-observer-3284b56f3d7e.py` and invoked its unchanged `copy_guard`, without
calling its production/cold guard, native Secret reader, SQL or server launch.
It rechecked namespace ownership, original image/container/resource contracts,
tmpfs-only mounts and the exact Pod/policy/namespace identities. Every persisted
namespaced resource type was listed; there were no foreign Pods, policies,
PVCs, workloads, Services or Secrets. Only the owned Pod/policy, standard default
ServiceAccount/root-CA ConfigMap, and events referring to owned UIDs existed.
Observational metrics resources are not persisted namespace contents.

Both `launch.pid` and `mysqld.pid` were absent on each side. Process scans found
zero executable MySQL servers: two old-side and three new-side process entries
were Z-state zombies with no executable. These checks passed again immediately
before deleting the Pod. Deletion used API `DeleteOptions` with both UID and
resourceVersion preconditions, normal grace periods and explicit absence waits.
The deny-all policy remained until the Pod was gone; the namespace was checked
again for foreign resources before its own deletion. No force deletion occurred.

Before removing the temporary copies, both retained ciphers were freshly read,
fully decrypted/authenticated and tar-verified in bounded RAM, without writing
plaintext. Original cipher `d9055b97...` is 216,854,420 bytes / 295 entries /
216,491,611 file bytes. Upgraded cipher `b9fe57342...` is 213,689,476 bytes /
296 entries / 213,330,338 file bytes. Their full hashes and paths, authenticated
manifest hashes and the exact successful fresh-claim restore lineage are bound
in the cleanup receipt. Both cipher hashes were checked unchanged after cleanup.
The original `copy-run.json` remains byte-identical with SHA256
`a0b389dc3d9c722af8398cd627d04de79c1a48ac766cc0317d26fea66be4c47d`;
stop/qualification/failure/restore receipts remain historical evidence.

No object in production namespace `ruckus` was accessed or changed by this
cleanup. No original/source/destination PVC, persistent data, archive, cache,
image or local evidence file was deleted. Removal releases the Pod's temporary
memory volumes; no Windows or Linux disk-space recovery amount is claimed.
