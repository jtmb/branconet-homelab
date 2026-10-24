# Cold configuration backups before compatible application updates

Current checkpoints and unresolved gates are summarized in [MIGRATION_STATUS.md](../MIGRATION_STATUS.md). This document retains operational contracts and dated attempt history.

Radarr executed this path on October 24 after Flux stopped its original writer.
Its backup completed at 00:55:06 UTC: 1,197 files, 517,549,996 plaintext data bytes,
519,059,380 encrypted bytes; SHA256
`9bb2f636d27e3fd52c3be529be14b8e5847b0ea3df347366fae2760c11551897`.
Full authenticated archive verification and exact temporary Pod deletion passed.
Other applications remain prepared, with no backup claimed.
`scripts/migration/cold-application-state-backup.py` handles exactly one of Radarr,
Sonarr, Bazarr, Tautulli or Vaultwarden per invocation. It reuses the new
[MeTube preservation](METUBE-STATE-BACKUP.md) reader and archive verification
primitives; it does not import or replay the separate frozen BORTUS recovery
framework. The older `backup-native-volumes.py` scales unrelated workloads and
starts broad snapshots, so it is not this operation's entry point.

Metadata-only strict SSH discovery verified these original identities:

| App / namespace | Deployment UID | Config PVC UID (`<app>-data-0`) | Original app mount |
|---|---|---|---|
| radarr / plex | 3e2719e0-f7f5-4cf5-8ba9-9d94a68302f0 | 7f07da4f-a34e-4bd0-a4a0-90b94f5a0fec | /config |
| sonarr / plex | 30d19648-2af7-48cd-9d72-e9d41f4ecb20 | ff5158b3-cecf-46f9-b85e-ad8566cb9068 | /config |
| bazarr / plex | 2bfbbb63-e949-4a5d-afd3-a923e2d02472 | 5bddaab4-1974-4211-bcae-8392d1006804 | /config |
| tautulli / plex | 9db52ebb-23c8-47c6-82c8-ebde3b0a2775 | 97eb095e-37ec-4185-80ed-4d8f3c19f486 | /config |
| vaultwarden / vaultwarden | 668bb3cd-e382-48b0-910f-7440351bc7d1 | 0fb0e918-ea61-43f5-af95-662c12f8ffe8 | /data |

The source pins each exact original HelmRelease UID and image digest too. It
requires each config claim Bound to its original Longhorn PV. Media/download
claims are never mounted, traversed or archived. No Secret, hostPath, application
environment, service account token, app entrypoint or updater is supplied to the
reader. Native Kubernetes Secrets and the NAS corpus remain outside its scope.

Root first stops the selected app through its existing Flux HelmRelease by
setting its replicaCount to zero and waiting for reconciliation. The helper
requires an unsuspended Ready HelmRelease with observed generation and zero
replicaCount; the original Deployment must observe its current generation and
have zero desired/current/updated/Ready/available replicas. Every other live Pod
using that claim, including terminating or initializing Pods, refuses capture.
These guards run before reads and again after authenticated verification.
Root must retain exclusive ownership of this cold interval until backup ends.
The helper never scales, resumes, suspends or updates any existing workload.

The repeatable Ansible entry point is
`k8s-rewrite/ansible-playbook/playbooks/cold-application-state-backup.yml`, role
`cold_application_state_backup`. It delegates only this one-app command to the
native WSL controller without become, facts or application credentials. There
is no loop over applications. Its apply flag defaults false; check mode skips
the command and captures no backup. From a freshly staged source tree, root
later invokes the existing operator Ansible executable from the Ansible directory:

```bash
/home/brajam/.local/share/branconet-migration/venv/bin/ansible-playbook playbooks/cold-application-state-backup.yml --extra-vars @/protected/one-app-backup.json
```

Example protected nonsecret settings (change only the one selected app per run):

```json
{"cold_application_state_apply":true,"cold_application_state_app":"radarr","cold_application_state_output_dir":"/home/brajam/.local/share/branconet-migration/application-cold-20261023","cold_application_state_node":"workernode2","cold_application_state_reader_uid":1000,"cold_application_state_reader_gid":1000}
```

The equivalent direct helper call is:

```bash
/home/brajam/.local/share/branconet-migration/venv/bin/python scripts/migration/cold-application-state-backup.py radarr --apply --reader-uid 1000 --reader-gid 1000 --node workernode2 --output-dir /home/brajam/.local/share/branconet-migration/application-cold-20261023
```

Full-tree read-only `find`/`stat` discovery on 2026-10-23 found these owner/mode
sets without reading any file contents:

| App | Entries | Ownership and access |
|---|---|---|
| Radarr | 1386 | All 1000:1000; dirs 0755, files 0755/0644 and two 0600 |
| Sonarr | 1805 | All 1000:1000; dirs 0755, files 0755/0644 and two 0600 |
| Bazarr | 116 | All UID 1000, GID 1000 or 65534; dirs 0755, files 0755/0664 |
| Tautulli | 801 | All 1000:1000; root 1750, other dirs 0755, files 0644/0755 |
| Vaultwarden | 9 | Root 1000:65534 mode 1750; four dirs 0:0 mode 0755 and four files 0:0 mode 0644 |

Use explicit UID/GID **1000:1000 for all five current trees**. No UID 911 was
observed. The mixed owners in Vaultwarden still permit UID 1000 to read every
observed file and traverse every directory; UID 0/GID 0 with dropped capabilities
cannot traverse its current 1750 root. The explicit 0:0 option remains available
only for a separately reviewed tree whose modes actually permit that pair.
The helper accepts only 0:0 or 1000:1000, without supplemental groups or capability
overrides. These live metadata observations are not a cold fingerprint or proof
of the later reader's full file reads. No identity is inferred from a successful
Pod start. Any unreadable file fails the full inventory/archive;
metadata-only success cannot satisfy the gate. The helper has read-only PVC and
root filesystem mounts, no fsGroup or chown, no added capabilities, and all
capabilities dropped even for UID 0. It runs sleeping Python from the already
qualified immutable MeTube image, limited to 500m CPU/256 MiB memory and a
30-minute deadline. The selected worker must be Ready and free of pressure.

The entire config root becomes `data-0` in the tar, with no exclusions: SQLite
databases, WAL/SHM files, backups, attachments, keys, settings and recovery files
are included if present. The shared reader hashes every regular file in one-MiB
chunks and records directory, ownership, mode and symlink metadata without
following symlinks. Hardlinks/special files, unreadable files, mutation during
capture, more than 4096 entries, over four GiB data or over eight MiB manifest
metadata refuse the operation. A refusal requires review; it never silently
skips data or relaxes limits. This is a filesystem backup, not an app/schema
compatibility test or an independent restoration.

Tar streams straight from strict SSH (`james@192.168.0.4:2002`, existing
`id_ed25519`, no forwarding/sudo) into the existing SHA-bound age v1.3.2 on WSL.
No plaintext tar is staged and no archive-sized read occurs. Verification fully
decrypts and traverses the tar in bounded chunks, checks every SHA/size/member
and metadata against its manifest, drains EOF and requires age's authenticated
successful exit. Only ciphertext and a private metadata receipt persist outside
Git under owner-only 0700 directories and 0600 files. Filenames and file hashes
remain in the encrypted manifest; raw contents, credentials and errors are not
printed. Existing identity and recipient files are neither created nor rotated.

After successful archive verification and final source/UID/quiescence checks,
cleanup deletes only the newly created read-only Pod using its exact UID as a
server-side precondition. A failed run retains its Pod and partial ciphertext
for review (the deadline eventually terminates its process); there is no force
deletion, automatic retry, resume, PVC deletion or original file removal.
Root keeps the original image reference, PVC/Deployment identities, archive,
receipt and operator identity available before publishing the compatible update.
Archive verification does not prove an independent restore or full application
acceptance. Source preparation and AST checks do not prove runtime backup.

Radarr also has a separately prepared, GET-only before/after/restart helper:
[`qualify-radarr.py`](../scripts/migration/qualify-radarr.py). Its scope and
invocations are in [the maintenance plan](CLUSTER-SECURITY.md#radarr-api-preservation-observation).
Capture its old-image baseline before stopping the writer. This API observation
does not replace this complete cold encrypted config backup, SQLite integrity,
raw user/password-table checks, external routes or integration connection tests.

The corresponding prepared Sonarr helper is
[`qualify-sonarr.py`](../scripts/migration/qualify-sonarr.py); capture its old-image
baseline before the Sonarr Flux stop. Its bounded per-series episode/file reads,
history and config fingerprints are documented in
[Sonarr API preservation](CLUSTER-SECURITY.md#sonarr-api-preservation-observation).
It has the same explicit separation from complete cold backup, SQLite/user-table,
route and real connection acceptance. Source preparation makes no live calls.

## Radarr/Sonarr SQLite integrity and Users preservation

`scripts/migration/verify-arr-sqlite.py` is a separate, source-only prepared
observation for exactly Radarr or Sonarr after its compatible image update. It
does not use the frozen BORTUS recovery framework and does not scale the writer.
Its original Deployment/HelmRelease/PVC/image identities match the cold-backup
helper above. The accepted new image and platform digest are pinned explicitly.
No mode has executed merely because this source exists or parses successfully.

Run on the native WSL controller from a reviewed source stage, supplying the
existing operator verification key through protected stdin only:

```bash
/home/brajam/.local/share/branconet-migration/venv/bin/python scripts/migration/verify-arr-sqlite.py radarr --apply --cold-receipt /protected/radarr-cold/receipt.json --cold-receipt-sha256 <reviewed-receipt-sha256> --output-dir /home/brajam/.local/share/branconet-migration/arr-sqlite-observation-20261024
```

The key is not an argument, environment variable, manifest, Secret mount or
regular file created by this helper. Root supplies the already held key through
stdin; the script forwards it in memory through SSH/kubectl exec stdin only.
Receipts contain key-bound HMACs, counts, numeric IDs, column names and resource
metadata, never raw usernames, passwords, salts or other cell values. Operator
output/receipts remain owner-only outside Git. These fingerprints are private
acceptance metadata and do not authorize publishing credential-derived records.

The helper binds the exact cold receipt SHA, completed status, application,
original resource identities, ciphertext size and full SHA. It reuses the MeTube
controller's complete streaming archive verifier and requires age's successful
authenticated EOF. A second authenticated streaming pass extracts only
`data-0/radarr.db` or `data-0/sonarr.db`, together with any exact `-wal`/`-shm`
siblings, into a new owner-only `/dev/shm` directory. Every selected file is
checked against the encrypted manifest. The combined extracted size is capped
at 128 MiB; all other members stream through without extraction. The ciphertext
and receipt identities/hashes are checked again before acceptance. The complete
encrypted archive is retained. No plaintext SQLite file is staged on an ordinary
filesystem, and the tmpfs copy is removed when the cold observation ends.

The original SQLite copy opens with URI `mode=ro`, `query_only`, memory-backed
temporary storage and an explicit read transaction. It uses the copied WAL/SHM
instead of pretending a WAL database is immutable. It requires `quick_check=ok`
and reads every original Users column, ordered and bound by its integer primary
key. The same code records per-field/per-row and per-column HMACs, with type tags
for NULL, integer, float, text and binary values. There is no password-column
redaction from the comparison and no normalization or ignored original column.
At most 64 columns, 1,000 users, one MiB per cell and eight MiB aggregate encoded
user values are admitted. Exceeding a bound refuses rather than truncates.

For the current database, the helper requires the exact single Ready Deployment,
owned ReplicaSet/Pod, configured image/platform digest, original Longhorn PVC and
healthy original node. It creates one explicitly named MeTube Python reader on
that same node, mounting only the state claim read-only. The reader has no NAS,
Secret, service-account token, application environment, init/ephemeral container,
fsGroup or added capability. It runs as 1000:1000, drops all capabilities, uses a
read-only root, 500m CPU/256 MiB and a ten-minute Pod deadline.

The live reader uses SQLite `mode=ro`, `query_only` and a read transaction,
including normal WAL semantics. SQLite's backup API copies its bounded logical
snapshot into an in-memory database, then releases the live connection before
the full quick-check and Users comparison. It never checkpoints, vacuums, sets
journal mode, opens the source database read/write, copies a changing database
file with ordinary file reads or falls back to `immutable=1`. A missing/unusable
WAL/SHM, hot journal, lock/access failure or timeout refuses the observation.
The read-only mount blocks filesystem writes; nevertheless, SQLite WAL readers
participate in shared-memory coordination/locking, so this operation does **not**
claim zero SHM coordination or metadata effects. Its read lock can temporarily
delay a writer/checkpoint; acquisition is bounded and the snapshot has a
90-second deadline. The source must not be forced through a readonly failure.

Acceptance compares every original column and ID, row count, aggregate,
per-column and per-field HMAC, including key binding. New columns are listed
separately and cannot replace an old column. Writer and reader resource fences
run again after the snapshot. On success, the helper deletes only its own
temporary Pod using a server-side UID precondition. Failure retains the Pod and
private receipt; the Pod deadline limits its lifetime. It never deletes a PVC,
modifies data, restarts an app or retries with weaker SQLite settings.

This closes only the named SQLite integrity and Users-table comparison when
actually executed successfully. API/history preservation, integration tests,
routes, restart persistence, backup restore and full migration acceptance remain
separate. Primary behavior references: [SQLite read-only WAL](https://sqlite.org/wal.html#read_only_databases),
[online backup](https://sqlite.org/backup.html),
[Python SQLite backup](https://docs.python.org/3/library/sqlite3.html#sqlite3.Connection.backup).

Bazarr's prepared before/after/restart pair is
[`qualify-bazarr.py`](../scripts/migration/qualify-bazarr.py) with adjacent
[`bazarr-sqlite-observer.py`](../scripts/migration/bazarr-sqlite-observer.py).
Its old-writer baseline must pass the strict legacy-subtitle preflight before
the Flux stop and complete cold encrypted backup. The later Alembic conversion
can silently skip malformed/colliding old subtitle entries and remove their
original column; a Ready app therefore cannot prove preservation. See
[the exact SQL/API observation contract](CLUSTER-SECURITY.md#bazarr-sql-and-api-preservation-observation).
The observer does not create a Pod, backup, SQLite copy, migration or writer stop.
After the proven upstream default cleanup, `after`/`restart` additionally require
the exact protected `--vendor-normalization-proof` described in that contract.
The proof binds the unchanged original cold archive/baseline; it permits only
the 25 source-proven absent default leaves and two exact disabled empty notifier
rows. It does not accept changed credentials, customized scores or unrelated loss,
and does not claim the new upstream scoring weights behave identically.


For Vaultwarden, follow the mandatory original-schema preflight and complete
SQL/file comparison in [Vaultwarden acceptance](VAULTWARDEN-ACCEPTANCE.md) before
allowing the new writer. Whole archive authentication alone does not establish
that its forward migrations preserve every original record.
