# Ruckus MySQL full-data/account preservation qualifier

Source-only preparation. No SQL connection, MySQL start, Pod creation, upgrade,
backup restore, cluster mutation or live baseline was executed during preparation.
The helper runs on the master with existing kubectl authorization. It does not
create resources, restore/decrypt archives, scale workloads or delete anything.
The coordinator owns those operations and retains every original cold archive.

The helper pins the actual Ruckus Deployment/writer/HelmRelease/PVC/native Secret
UIDs. WordPress names and profiles are outside its scope. Original server is
5.7.41, candidate is the built5.7.44 artifact
`sha256:2f0c391e6c04501862598bbc5446165f8ebba08025168451f6f6447352316349`.
All fixture images use Never pull and must already be present on workernode2.

## Live application baseline and after/restart checks

Quiesce the bot through Flux first: its Deployment and HelmRelease must both
converge to zero, with no surviving bot Pod. Leave the database running at one
replica for authenticated capture. Full backup subsequently requires BOTH bot
and database Flux/Deployment replicas zero and no surviving source-claim user;
use the existing `cold-application-state-backup.py --application ruckus-db`
workflow and its original UID/mount/reader guards.

Every command except plan reads the SAME32-byte hex HMAC key from stdin.
Use an existing protected input FD/pipe; never place key or credential values in
arguments. Example commands assume FD3 supplies one hex-key line per invocation:

```sh
python3 -B qualify-ruckusdb.py observe-live \
  --expected-image 'mysql:5.7.41@sha256:bf18020f32cc5d8f5e2add516d52fbf3afc3de431457076340e938596c528171' \
  --receipt /private/ruckus-live-before.json <&3
```

After approved adoption and again after a normal restart, run observe-live with
the exact deployed image reference, a new receipt path and the same key while
the bot remains quiesced. Compare before/after using:

```sh
python3 -B qualify-ruckusdb.py compare \
  --baseline /private/ruckus-live-before.json \
  --restore-proof /private/ruckus-live-after.json \
  --receipt /private/ruckus-live-comparison.json <&3
```

For compare, `--restore-proof` means the second observation receipt; it is not
an archive path. Native Secret values are decoded only in master RAM and piped
to the existing mysql client's RAM-only option-file FD. SQL identifiers/queries
also travel over stdin, not argv. No MYSQL_PWD environment export, plaintext
credential file, root password lookup/reset or server-log read is performed.
The master receives raw query results only in RAM and emits HMACs/counts. It
disables core dumps and catches failures without printing SQL stderr/tracebacks.

The observer connects through the actual Ruckus Service clusterIP using the
original application credential. It hashes the entire native Secret data map,
UID and records resourceVersion. It records native PVC/PV/Deployment/release
identities and resource limits for comparison. Every accessible non-dynamic
schema/table is enumerated; every base-table row is encoded with explicit NULL
markers and binary hex columns, then keyed and sorted as a multiset, preserving
duplicates. Definitions, column order, triggers, routines and events are keyed; stored objects include full SHOW CREATE output. The native application schema must be visible.
Views are definition-checked, not executed as dynamic performance views.
Per-table limit100,000 rows and per-client-result64MiB fail closed. The initial
measured app footprint (two InnoDB tables, approximately1.6MiB) is below these
bounds. Live capture is repeated and must match under the quiesced identity.
No sampling, estimated-row substitution or data exclusion is used.

This is all data ACCESSIBLE to the app credential, not proof of invisible system
schemas. The full cold archive and administrative clone comparison provide that
second scope. SQL reads/normal authentication can change server counters/logs;
no data-changing SQL or grant command is issued by observation.

## Disposable full copies, all accounts and upgrade

1. After the existing full cold backup passes, emit an isolated fixture plan:

   ```sh
   python3 -B qualify-ruckusdb.py plan --run-id 012345abcdef > /private/ruckus-copy-plan.json
   ```

   Use a fresh random12-hex run ID. Review then create these dedicated resources
   through the coordinator's authorized kubectl workflow. Record their actual
   namespace/Pod/policy UIDs. No image entrypoint runs: database containers sleep,
   and the reader runs only a sleeper Python process.

2. Restore the **entire** verified `data-0` archive root into BOTH reader-visible
   `/copies/old/data-0` and `/copies/new/data-0`, using the existing manifest-aware
   restoration procedure, preserving numeric owners/groups/modes/timestamps,
   links, grants, system tables, redo, SSL and all user schemas. Never mount the
   source, rollback or any PVC in this Pod. The helper deliberately does not
   invent an alternate decryptor or trust an unverified plaintext archive.
   Keep the original encrypted backup and its complete restore manifest.

3. Run physical-copy with exact namespace/Pod UID and same HMAC key. It requires
   the source bot+database Flux identities cold, validates emptyDir-only memory
   mounts and compares EVERY restored object/file/owner/group/mode/mtime plus
   contents between the two copies. It requires mysql/user.frm and ibdata1 and
   rejects escaping links. It caps each logical copy at384MiB; the earlier
   physical allocation was approximately219MiB. If actual restore is larger,
   stop and review explicit fixture memory sizingâ€”do not discard data.

   ```sh
   python3 -B qualify-ruckusdb.py physical-copy \
     --namespace ruckusdb-copy-012345abcdef --pod-uid ACTUAL_POD_UID \
     --receipt /private/ruckus-physical.json <&3
   ```

4. Start old and new separately using `start-copy --container old|new`, the same
   namespace/Pod UID and `--restore-proof /private/ruckus-physical.json`. This
   directly launches the image's mysqld against only `/copy/data-0`; it never
   initializes a database. Default mode adds skip-grant-tables; both modes always
   use skip-networking and a private Unix socket. No root password is required.
   A successful launcher receipt is NOT readiness; observe-copy must succeed.
   Capture each with observe-copy (no normal-auth flag). All six mysql grant
   tables are mandatory and every columnâ€”including password/authentication
   hashes, plugins, host restrictions and privilege bitsâ€”is HMAC-covered.
   Other visible system/user table rows and definitions are also covered.

5. Compare the administrative old/new observations. Preserve any mismatch and
   investigate; do not add exclusions simply to pass. MySQL's internal persistent
   statistics/sys bookkeeping may legitimately change on startup/upgrade. This
   strict first-pass comparator intentionally flags those changes and does not
   silently approve them. The separate grant-table equality is available for
   review; all application rows and account/grant values must remain unchanged.

6. If approved, invoke upgrade-copy on `--container new` only, while its isolated
   socket server is5.7.44 with both skip flags enabled. The helper calls the
   candidate's mysql_upgrade, with no force, credential reset or custom GRANT.
   Its private output remains in memory; only a keyed output fingerprint and
   exit outcome enter the receipt. This action CAN modify/repair the copied DB.
   Capture the pre-upgrade administrative observation first.

7. Stop using stop-copy, then restart the new clone in bypass mode and observe
   again. The stop action targets only the guarded container's recorded launch
   PID, checks its executable is mysqld, sends SIGTERM and waits for exit; it
   never force-kills or reads logs. Recheck all grant hashes and durable data.
   If upgrade fails or unauthenticated access disappears, preserve receipts and
   clone state for review. NEVER reset root or alter existing account hashes.

8. Stop and start EACH clone with `start-copy --normal-auth`, then run
   `observe-copy --normal-auth`. This omits the grant bypass and authenticates
   over the private socket using the actual native app credential. Compare old
   vs new normal-auth data and account identity. This mode is separate from the
   administrative snapshot scope; do not compare root-bypass with app snapshots.
   Production Service-path authentication still needs the live after/restart
   observations above. No Discord bot or notification client is started.

Every copy action validates the recorded Pod UID, exact three image/command
contracts, node, resource/security settings, memory-only emptyDirs, no Secret
mounts/env, no API token, no Service, no added init/ephemeral container, and the
dedicated deny-all policy. It never accepts a production namespace or PVC.
NetworkPolicy enforcement still depends on the cluster CNI. The reader's limited
CHOWN/FOWNER/DAC_OVERRIDE capabilities allow exact restoration inside emptyDirs;
mysqld runs as original UID999:GID65534 with all capabilities dropped. Original
datadir root mode1750 is retained by restoration, not normalized by an initializer.

Each memory data volume has512MiB capacity and each server scratch64MiB. The
reader has1536MiB memory limit, each server512MiB and500m CPU. These are isolated
fixture budgets; no production resource or host memory settings change. The
fixture has a3600s deadline. Complete graceful stops before that deadline.
Stop both servers before operator cleanup. Delete only recorded owned UIDs using
Kubernetes DeleteOptions `preconditions.uid`; retain the namespace if foreign
objects appear. Do not use a broad selector, name-only delete, force-delete,
shared PVC cleanup or image prune. Failed receipts and original cold archives
remain; this helper performs no cleanup automatically.

## What primary MySQL documentation establishes

Oracle explicitly supports patch upgrades within5.7, including skipped patches.
[Upgrade paths](https://docs.oracle.com/cd/E17952_01/mysql-5.7-en/upgrade-paths.html).
Its mysql_upgrade instructions recommend running the tool on each upgrade and
then restarting; the tool may update system schemas and repair user tables.
No specific5.7.41â†’5.7.44 exemption was found. This is a documented recommendation
and a required review/qualification gate here, not an invented claim that this
particular patch must change grant-table formats.
[mysql_upgrade](https://docs.oracle.com/cd/E17952_01/mysql-5.7-en/mysql-upgrade.html).

The server documentation notes mysql_upgrade flushes privileges, so a server
started with skip-grant-tables can begin enforcing retained grants during the
procedure. A later unauthenticated reconnect is not guaranteed; the preserved
clone stop/restart procedure handles inspection without changing credentials.
[Server options](https://docs.oracle.com/cd/E17952_01/mysql-5.7-en/server-options.html#option_mysqld_skip-grant-tables).
The utility's success and exact retained grant hashes must be measured. A normal
entrypoint startup does not automatically run mysql_upgrade. The old full cold
copy remains the rollback source; never downgrade binaries over a modified copy.
