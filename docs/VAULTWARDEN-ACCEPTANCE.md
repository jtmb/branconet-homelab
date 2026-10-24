# Vaultwarden 1.35.4 to 1.37.4 preservation observation

The prepared [`verify-vaultwarden-state.py`](../scripts/migration/verify-vaultwarden-state.py)
and adjacent [`vaultwarden-state-observer.py`](../scripts/migration/vaultwarden-state-observer.py)
compare the complete authenticated cold archive with the adopted application's
current SQLite state and non-database files. Source preparation and local
synthetic checks do not claim a production backup, rollout or acceptance.

The immutable candidate is
`docker.io/library/vaultwarden-security-20261023@sha256:c6a9b959228bf484038fe502bc0697e5ca5d2d10a515de47969c2611d36cdb0d`,
from private artifact-only run `40060033423`, artifact `12546559116`, source
`e7aad9893d9823aae489483e8fdba0dc94418c65`. Its original OCI archive SHA256 is
`ad0c9750afb40816382c33b669e7250c294adf7cda841566f94abbe19036c949`.
Root must review the exact unsuppressed scan and inherited runtime settings
before any deployment; this helper does not build, import or deploy images.

## Cold state and resource binding

Use the existing [whole-application cold backup](COLD-APPLICATION-STATE-BACKUP.md)
for `vaultwarden`, after its existing Flux release stops all writers. The archive
must contain the entire `/data` root, including matching SQLite/WAL/SHM files,
attachments, Sends, RSA keys and configuration, with no data exclusions. Confirm
the actual configured backend is default/valid SQLite first; this observer
refuses to substitute a SQLite file for a different configured database backend.
An external database needs its own consistent native backup and acceptance.

The controller pins namespace `vaultwarden`, Deployment UID
`668bb3cd-e382-48b0-910f-7440351bc7d1`, HelmRelease UID
`3022a586-c52e-4dcd-850b-149f6b38b603`, and `vaultwarden-data-0` PVC UID
`0fb0e918-ea61-43f5-af95-662c12f8ffe8`. The claim must remain Bound to its
original Longhorn PV. It requires a SHA-bound completed cold receipt, checks
ciphertext size/SHA and authenticates the entire archive again with the existing
pinned age binary and identity. Archive/receipt/source identities are rechecked
after observation. Originals, ciphertext and operator identities remain intact.

Only exact `data-0/db.sqlite3`, `-wal` and `-shm` members are extracted into a new
owner-only `/dev/shm` directory, with a combined 128 MiB ceiling, verified member
hashes and authenticated EOF. Other files stream through without extraction.
The temporary plaintext SQLite directory is removed on exit; plaintext is never
staged on a normal filesystem. Archive filenames remain in RAM rather than
receipts. A read-only `mode=ro`, `query_only`, explicit transaction and normal WAL
semantics are used; there is no `immutable=1`, checkpoint, vacuum or journal-mode
change.

## Exact migration and data comparison

The [upstream 1.35.4 to 1.37.4 comparison](https://github.com/dani-garcia/vaultwarden/compare/1.35.4...1.37.4)
adds exactly these SQLite migrations:

| Version | Permitted schema addition |
|---|---|
| `20260309005927` | Empty `archives` table with user/cipher foreign keys, composite primary key and `archived_at` timestamp default |
| `20260425120000` | Nullable TEXT `sso_auth.binding_hash` |
| `20260505120000` | Nullable TEXT `sso_auth.code_response_error` |
| `20260902120000` | Nullable TEXT `users.key_id` |

The original database must not already contain `archives` or these new columns
or migration versions. This protects against the upstream archive migration's
`DROP TABLE IF EXISTS archives` destroying an unexpected existing table. The
controller's `--cold-only` mode must therefore pass **before publishing the new
writer**, after complete backup while root still owns the zero-writer interval.
It authenticates the archive and establishes this original-schema preflight
without creating a reader or requiring the new app. Do not defer this guard
until after migrations have run. The subsequent full comparison rechecks the
same unchanged cold archive independently. The
current database must retain every original table, column definition and row,
including all user credential/2FA fields, organizations, memberships, encrypted
items, devices, attachment and Send records. No credential column is redacted
from the comparison. Only the exact new schema above is admitted: new fields on
original rows must be NULL, archives empty, and exactly four new migration
records present while every old migration record remains byte-equivalent.

Every original table is ordered by all its original selected columns. Typed
NULL/integer/float/text/binary cells feed key-bound whole-row and per-column
HMACs; original counts and full table fingerprints must match. No raw user IDs,
email addresses, hashes, ciphertext, organization keys or values are output.
The observer admits at most 256 tables, 256 columns per table, 250,000 total
rows, one MiB per cell, 32 MiB encoded cell data and a 90-second SQL deadline.
Bounds refuse rather than truncate. `quick_check=ok` is required.

Run this immediate migration projection before clients create archives or
populate newly supported fields. A subsequent legitimate user operation can
make the strict initial projection refuse; that does not authorize ignoring
the difference or changing the original baseline. Review concrete source and
operation evidence for such differences separately.

All non-database files and directories are also compared with the authenticated
cold manifest. Only the exact database/WAL/SHM filenames are excluded from byte
comparison because their logical content is checked above. Attachments, Sends,
RSA keys, config and cache contents are not silently exempted. Paths, symlink
targets, sizes/content hashes and uid/gid/modes feed HMACs, keeping attachment
names and configuration values out of receipts. File iteration never follows
symlinks or crosses filesystem devices; unexpected loss, additions or changes
refuse. Files are bounded by 4 GiB aggregate, 4,096 entries and 120 seconds.
Directory timestamps/inodes are not a data-equivalence contract.

## Read-only live reader and invocation

After root adopts the exact qualified image, the controller requires one Ready
writer, its original Deployment/HelmRelease/PVC and owned ReplicaSet/Pod, exact
runtime digest, original `/data` mount and a healthy schedulable node. It creates
one independently named Python reader using the existing pinned MeTube image,
on the writer's node, mounting only this claim read-only. No application
entrypoint, updater, native Secret, NAS mount, service-account token, environment,
init/ephemeral container, fsGroup or added capability is supplied. UID/GID stay
1000:1000, root filesystem read-only, all capabilities dropped, CPU 500m,
memory 256 MiB and Pod deadline 600 seconds.

SQLite's backup API copies a bounded consistent live snapshot into RAM before
the table comparison. The source opens read-only; WAL readers still participate
in shared-memory coordination/locking, so this does not claim zero SHM effects.
Missing/unusable WAL/SHM, permission/lock/timeout errors refuse without fallback.
The full non-database tree must remain stable while read. Root should run this
during the protected migration window before allowing ordinary client writes.

Supply the already-held independent verification key through protected stdin,
never argv, environment, Git or manifests. This helper neither creates nor
rotates it. Example from a reviewed native WSL source stage:

```bash
/home/brajam/.local/share/branconet-migration/venv/bin/python scripts/migration/verify-vaultwarden-state.py vaultwarden --apply --cold-only --cold-receipt /protected/vaultwarden-cold/receipt.json --cold-receipt-sha256 <reviewed-sha256> --output-dir /home/brajam/.local/share/branconet-migration/vaultwarden-state-20261024

# Only after the cold-only preflight and all rollout gates passed:
/home/brajam/.local/share/branconet-migration/venv/bin/python scripts/migration/verify-vaultwarden-state.py vaultwarden --apply --cold-receipt /protected/vaultwarden-cold/receipt.json --cold-receipt-sha256 <reviewed-sha256> --output-dir /home/brajam/.local/share/branconet-migration/vaultwarden-state-20261024
```

The key crosses SSH/kubectl exec only through in-memory stdin. Receipts remain
0600 in a new 0700 operator directory outside Git; raw diagnostics are withheld.
On success the controller deletes only its own read-only Pod using a server-side
UID precondition. Failure preserves that Pod/private receipt for review; the
deadline bounds the reader. It never scales, patches or restarts a workload,
deletes/rebinds a PVC, changes data or weakens SQLite checks.

## Separate functional and recovery gates

A matching SQL/file observation proves only this named state comparison.
Root still needs actual application version/alive/config checks, intended
ingress/TLS behavior, authorization boundaries, existing account login, enabled
2FA/SSO methods, existing web/native-client sync and restart persistence.
Do not invent/reset credentials or rotate organization keys to make these pass.
No notification or other external message is sent by the observer. Its receipt
keeps `full_application_accepted` and `login_2fa_or_client_sync_accepted` false.

Resolve retired experimental flags, actual trusted-proxy configuration and
older `bw send receive` client compatibility from the application update
runbook before rollout. A schema rollback must restore the **complete original
state and image together**; never run the old app against a forward-migrated DB.
Archive authentication is distinct from an independent restore demonstration.
