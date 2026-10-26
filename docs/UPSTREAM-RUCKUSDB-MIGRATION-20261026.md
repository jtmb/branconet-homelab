# Ruckus database upstream transition

Owner: migration chat `01a12045-bf7e-73b3-8557-752d17c72ffd`.
**Production transition accepted, October26 20:38UTC.** The official MySQL8.4.13
image is running on the separately verified Longhorn claim. Original and earlier
recovery claims remain Bound. The full migration/security goal remains active.

## Actual production result

Private main, validated and live revision:
`7383784971f0e1a0839631cf0104f8792d62f9f4`.
The activation was `ef9924f89f09a9358185a7c2a7b7e85a7a712551`; bot resumption
was `d8a04528b5e64ed697222b6d84ffdf8fe9ebf232`.

The fresh complete cold archive captured **429821721 data bytes /579files**;
its **430564180-byte** ciphertext has SHA256
`b44939c5f48d7b5b71801fb5073c95e04305eddbcb913e92a869f1fe849cfc0f`.
Full local authentication and complete NAS read-back/authentication passed
before any destination write. It includes the entire original claim and its
retained directories. The historical trial's3966rows were not used for cutover:
the fresh copy preserved **3971original rows**, including5intervening rows.

The fresh5.7→8.0→8.4 copy comparison passed every application row, all original
human/app account fields, legacy grant tables, time-zone rows and server UUID.
The same explicitly reviewed vendor account and unsupported-mode changes apply.
Normal positive/negative auth passed without grant bypass. After clean shutdown,
the helper Pod/policy were removed with UID preconditions; neither PVC nor the
existing namespace was deleted. The production image uses ordinary authenticated
TCP service operation; no helper bypass/socket-only flags were promoted.

Production native-resource and full original-row comparisons passed before bot
resumption, afterward, and after a distinct database restart. All3971original
rows remain; one normal new record persists, for3972rows. The bot's actual
mysql2client connected using its unchanged native environment and the same
qualified application principal. All28API/dashboard routes passed through the
internal Service and all three published node addresses, then passed again after
database restart. No test Discord message or personal dashboard login is credited.

The initial live database Pod UID was
`e2f8ff52-c194-44a2-a1a7-52c06d2c06ce`; the independently restarted UID is
`18473c2c-3bf4-4fa1-a928-6750d818680a`. The same bot Pod
`59f4098d-acf3-40c3-aef1-e8ad2535eae6` recovered its DB connection. Both have
zero container restarts. The destination claim UID is
`3d587252-21b5-4982-b70a-4cfee6ae49bd`; original claim UID
`2f604004-b45f-4061-bdc4-43f5ca2f7fd8` remains unchanged and Bound. Service,
Deployment, release, original PV/PVC and native Secret identities/specs passed
the reviewed normalization for the image, destination, compatibility args and
explicit restart marker. Resource budgets and Secret values remain unchanged.

At20:30UTC:3Ready nodes without pressure,56Bound PVCs, all34HelmReleases and
all Kustomizations Ready, no unavailable Deployment/DaemonSet. There are42
Longhorn volumes: **30attached and healthy,12detached**. Detached retained
sources/recovery claims are not failed workloads. Earlier prose occasionally
used the total volume count as an attached count; that wording was incorrect.
The four previously retained failed diagnostic Pods remain unchanged.

Final distinct recovery metadata: **6872916bytes**, SHA256
`0d625ad75fab423073619392dd9d1348eef70b2caca467c5322da5623ba8b036`.
All local members and complete NAS age authentication passed. It includes the
fresh proof, runtime/restart/client/routes, executed source, encrypted engine
logs, remount recovery and publisher/cleanup evidence; unchanged parent members
and the large cold ciphertext are not duplicated. The parent1813124-byte
qualification archive below remains a required authenticated recovery input.

Six successful publisher stages were reconciled, removing **1065930752allocated
Linux bytes /4680paths**. This is the new cutover cleanup; the earlier6393856-byte
scan cleanup is separately recorded below. Original Git blobs/tools,24unique
publisher receipts, all failures, every source/rollback claim and required
encrypted archives remain. No Windows disk recovery is claimed.
[Exact paths and retained exceptions](TASK-OUTPUT-INVENTORY.md#ruckus-production-reconciliation-october-26-2038-utc).

Two application derivative transitions remain: Plex and WordPress. WordPress's
database, platform/fleet findings, owned publication, trusted TLS and final IAB
remain open. The selected MySQL image still has the vendor findings below;
the transition is not a clean-security or unknown-zero-day claim.

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

Pre-transition verified server: MySQL5.7.44, original Deployment and native Secret,
running with the bot in namespace `ruckus`. Its datadir was the original
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
The later fresh production invocation completed. Its first attempt stopped
before reader creation on a wrong node-identity check; the corrected profile
pins worker2 and grants only read/search on the entire original claim. Both
failure and successful receipt remain. Runtime-only verifier import/argument
encoding errors were also retained and corrected before acceptance.

## Security, recovery and next cutover

The exact target scan completed with rehashed trusted inputs: **2 Critical /
33 High / 38 Medium / 7 Low / 1 Unknown**, no KEV intersection. All 35
Critical/High rows have upstream component fixes. Critical rows include bundled
certifi `GHSA-6q48-6c7w-9gw2` and Go standard library `CVE-2025-68121`.
These remain vendor image findings. Docker's maintained8.4 image currently
publishes the Oracle Linux variant; no bespoke derivative was built.
Do not claim that8.4 is vulnerability-free or deploy8.0 as the maintained end
state. The production transition is complete; the vendor findings remain open.

The distinct encrypted recovery metadata is **1813124 bytes**, SHA-256
`274d5a34c26436571d8507206632046fcc8a6b5ca35b6d17e117e0e2db23f263`.
All members were verified and the complete NAS read-back passed age
authentication. It includes the exact source, account/grant/data comparisons,
vendor input, failures, scan and cleanup receipts, and encrypted engine logs.
Original cold archives are retained without duplicating them in this package.
Engine logs have their own authenticated 51412-byte ciphertext, SHA-256
`a517715904aeab57cd612ba4dfa1b39e834e52418fd2929c987477b1dc7da84e`.

The executed production sequence was:

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

The prior `0de054992e5938543855d099efc1e484feee72be` source remains historical
rollback provenance. An actual rollback would select the retained original
image/mount and claims, but must reconcile any post-cutover writes first; do
not downgrade the upgraded directory or silently lose its newer records.
[Exact cleanup and retained exceptions](TASK-OUTPUT-INVENTORY.md#ruckus-upstream-qualification-reconciliation-october-26-1854-utc).
