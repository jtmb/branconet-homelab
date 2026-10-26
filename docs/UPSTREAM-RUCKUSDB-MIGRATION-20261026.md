# Ruckus database upstream transition

Owner: migration chat `01a12045-bf7e-73b3-8557-752d17c72ffd`. Work is incomplete;
the running 5.7.44 deployment remains authoritative until qualified cutover.

Reuse the single authorized output root
`/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025`,
physical ext4 UUID `3c792469-ea0e-4a2c-98e8-1185b141607b`, backed by
`F:\branconet-build-storage\native-build-20261025.ext4`.
New receipts and complete encrypted archives belong in
`upstream-ruckusdb-20261026`; exact executed sources belong in
`control-source/upstream-ruckusdb-20261026`; small controls/metadata reuse
`operator-control`. Configure all temporary paths there. Preserve source,
lockfiles, existing archives, unique failures and all original runtime data.
Do not duplicate dependencies or image build caches. No build or new publisher
is authorized. Recreate source exports from the exact retained Git revisions;
reproduce observations from the retained observer with its original HMAC key.

Current verified server: MySQL 5.7.44, original Deployment and native Secret,
running with the bot in namespace `ruckus`. The current datadir is the original
Longhorn claim's `security-data-20261025/data-0` subdirectory. Both the original
root and all earlier recovery copies remain protected.

The upstream [upgrade contract](https://dev.mysql.com/doc/refman/8.4/en/upgrade-paths.html)
requires 5.7 → 8.0 → 8.4. MySQL 8.0 itself reached EOL in April 2026 and is
an intermediate migration tool, not the final maintained deployment. The
[native-password compatibility option](https://dev.mysql.com/doc/refman/8.4/en/native-pluggable-authentication.html)
must be reviewed against existing accounts and the bot's actual connector;
do not generate replacement credentials or reset root.

The historical-copy trial below ran with production unchanged and online. Before
the actual cutover, prepare the exact destination and all controls, then pause
the bot and database through their existing Flux values. Observe complete
shutdown and capture/authenticate a fresh complete cold archive and NAS copy.
Restore only the separate destination and run the qualified sequential upgrade
while production writers remain stopped. Verify data before resuming writers.
If the stage fails, retain the failed destination and restore the original
image/mount through Flux. A stale historical trial must never replace newer
production writes. Never modify the original datadir for the major upgrade.

Acceptance must compare every user application row and schema object, account
identity/password hash/grants, applicable settings and TLS identity, plus normal
application authentication and bot integration. Explicitly identify vendor
system-schema/default changes rather than weakening the data contract. Verify
native Secret and existing workload/Service identity, resources and ownership.
Keep the old datadir and encrypted backups available for compatible rollback;
never attempt an in-place downgrade of the upgraded directory. Publish only
reviewed repository changes through local validation → validated → Flux, with
GitHub Actions disabled. Verify an independent restart before acceptance.

Capacity, source bindings, archive receipts, scan results and actual completion
must be recorded as observed. Generated scratch cleanup is mandatory with exact
removed paths/bytes and retained exceptions. Final IAB remains after all
implementation, not during this database preparation.

## Completed historical qualification, 18:54 UTC

The complete authenticated October 25 archive
`4b34b6920825b3e860a63e346e0dbd32fce792ffc89e30c997d10a2f63e4442c`
provided two isolated RAM copies. Neither a production PVC nor credentials
were mounted. Normal application credentials were used only through RAM/stdin
for explicit authentication probes. The server remained socket-only with
networking disabled and the namespace denied ingress/egress.

The sequence passed: 5.7.44, slow shutdown, complete file/metadata-preserving
copy, upstream 8.0.46, slow shutdown, upstream 8.4.13. The application schema,
both tables and all **3966 historical rows** match. All time-zone rows and the
server UUID match. All five original accounts survive; the three human/app
account records match across every original user-table column, including hashes
and privileges. The other five legacy grant tables match exactly.

The two changed accounts are locked vendor principals `mysql.session` and
`mysql.sys`. Their plugin/invalid-password representation changes, and
`mysql.session` gains its vendor-defined shutdown privilege. One new locked
`mysql.infoschema` principal is added. Exact version-tagged
[upstream upgrade SQL](https://github.com/mysql/mysql-server/blob/mysql-8.4.13/scripts/mysql_system_tables_fix.sql)
explains the changes; retained source SHA-256 is
`eb85b6bbe0924a91d42103f01e2b687ea0e82fd07993a7d90d9d89a108686fe5`.
These are explicitly scoped vendor changes, not permission to reset or change
human/application accounts. The sole removed SQL mode is the unsupported
`NO_AUTO_CREATE_USER`; all other compared settings match. Latin1 server defaults,
collation, case behavior and disabled binlog/GTID settings are preserved.

The final normal server ran without grant bypass, verified against its actual
process arguments. Existing app credentials authenticated; one intentionally
wrong password failed with MySQL error 1045, followed by a successful normal
query. Native Secret values/UID remained unchanged. No root password was looked
up, reset or generated. No Discord notification was sent by these probes.

Exact images:

- Intermediate only: `docker.io/library/mysql:8.0@sha256:7dcddc01f13bab2f15cde676d44d01f61fc9f99fe7785e86196dfc07d358ae2b`.
- Maintained target: `docker.io/library/mysql:8.4@sha256:76f0358884cb92d9a086d24e5671c38048d3fef40f2588703d73eb55392d6b69`;
  amd64 `sha256:2068651a18ac6048578647ea57b940ca2daed3f504ebe7fba6a93beeb39aaa1f`.

Both image runtimes were checked on worker2. The temporary preflight Pod/policy
were deleted with UID preconditions. The subsequent trial namespace
`ruckusdb-upstream-6b6dacf17d6c`, Pod `ae4f14f9-0f2f-4194-aacb-a59fd17c264b`
and policy were also retired with exact UID preconditions after clean shutdown,
acceptance and encrypted engine-log preservation. This retired **720482304
allocated RAM bytes** across 783 paths; it is not disk recovery.

The initial restore rejected a mismatch between the pretty manifest file's
digest and the archive's canonical manifest encoding before creating any
entries. Resumption required an exact read-only empty-copy diagnosis, matching
complete JSON objects and the original authenticated ciphertext digest. A
NetworkPolicy serialization check was corrected for Kubernetes omitting empty
rules. A normal-auth diagnostic variable query failed; actual process flags and
the positive/negative authentication checks established the final result.
Every failure and executed source generation remains; no receipt was replaced.

The new root helper and Ansible profile `upstream-ruckusdb-20261026` pin the
current source image, original claim and `security-data-20261025/data-0` mount.
The profile requires both writers at zero through Flux, reads the entire claim
with root read/search capability only, and never scales writers itself.
It has not yet captured the fresh production archive.

## Security, recovery and next cutover

The exact target scan completed with rehashed trusted inputs: **2 Critical /
33 High / 38 Medium / 7 Low / 1 Unknown**, no KEV intersection. All 35
Critical/High rows have upstream component fixes. Critical rows include bundled
certifi `GHSA-6q48-6c7w-9gw2` and Go standard library `CVE-2025-68121`.
These remain vendor image findings. Docker's maintained 8.4 image currently
publishes the Oracle Linux variant; no bespoke derivative is authorized.
Do not claim that 8.4 is vulnerability-free or deploy 8.0 as the maintained end
state. The 5.7-to-8.4 production transition remains **incomplete**.

The distinct encrypted recovery metadata is **1813124 bytes**, SHA-256
`274d5a34c26436571d8507206632046fcc8a6b5ca35b6d17e117e0e2db23f263`.
All members were verified and the complete NAS read-back passed age
authentication. It includes the exact source, account/grant/data comparisons,
vendor input, failures, scan and cleanup receipts, and encrypted engine logs.
Original cold archives are retained without duplicating them in this package.
Engine logs have their own authenticated 51412-byte ciphertext, SHA-256
`a517715904aeab57cd612ba4dfa1b39e834e52418fd2929c987477b1dc7da84e`.

The next production sequence is:

1. Add a separate `ruckus-db-upstream-20261026` Longhorn claim through the
   existing chart (keep policy, adequate upgrade headroom); leave the current
   Deployment's image, mount and replicas unchanged during provisioning.
2. Prepare a dedicated final-copy helper with no source write mount, all server
   generations using only the new claim, exact Pod/PVC/PV/Secret identities and
   the same socket-only sequential start/slow-shutdown contract. Preserve the
   original `ruckus-db-data-0` and its earlier recovery claim.
3. Pause bot and DB through Flux, capture the **fresh** complete claim with the
   new Ansible profile, and verify the entire NAS copy before destination writes.
   The archive root `data-0` contains the original whole claim; the active source
   below it is `security-data-20261025/data-0`, not the historical trial archive's
   `data-0/data-0` layout. Bind the embedded manifest to the fresh file manifest.
4. Restore only the new claim, snapshot the fresh 5.7 data/accounts, perform its
   slow shutdown, then 8.0 → slow shutdown → 8.4. Require the same bounded
   vendor-only account/default changes and full fresh-data comparisons. Test
   normal authentication without grant bypass, then shut down the helper.
5. Activate the official 8.4 image and new datadir through Flux, retaining the
   native Secret, Service identities, resources and old data. Preserve native
   password authentication explicitly, original Latin1/collation and compatible
   modes; do not reintroduce `NO_AUTO_CREATE_USER` or copied bypass flags.
6. Verify normal application data/authentication through the real Service,
   resume the bot and prove its actual mysql2 connection without sending a test
   Discord message. Verify a distinct Flux restart and preserved original rows.
7. Authenticate final recovery metadata on NAS, reconcile disposable publisher/
   scan/helper output, update accepted image ownership and cluster health, then
   record the actual live revision. Final IAB waits for all implementation.

Production remains at the prior accepted charts revision
`0de054992e5938543855d099efc1e484feee72be`; no production cutover is credited here.
[Exact cleanup and retained exceptions](TASK-OUTPUT-INVENTORY.md#ruckus-upstream-qualification-reconciliation-october-26-1854-utc).
