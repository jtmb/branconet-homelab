# Tautulli 2.16.1 to 2.18.2 preservation contract

**Current deployment:** the subsequent [maintained vendor transition](UPSTREAM-TAUTULLI-ADOPTION-20261026.md)
passed data/API/routes and independent restart on October 26. It supersedes the
derivative image below, retains every original account/history record and records
the remaining vendor findings. The dated evidence below remains historical;
personal browser acceptance and the full migration/security goal are still open.

Initial and independent controlled-restart preservation and functional checks
passed on October25, and public routes were restored. The receipts below
distinguish observed backend acceptance from final browser and whole-goal gates.
[`verify-tautulli-state.py`](../scripts/migration/verify-tautulli-state.py) and
[`tautulli-state-observer.py`](../scripts/migration/tautulli-state-observer.py)
reuse the existing authenticated cold-archive, pinned age, owner-only tmpfs and
owned read-only Pod pattern. They never stop, deploy, patch or restart a writer.
Root owns those separate Flux operations and the actual execution gates.

## Exact source and current state

Read-only inspection of the original pinned running image on October24 finds
`plexpy/version.py:PLEXPY_RELEASE_VERSION = v2.16.1`, not merely an image label.
The SQLite file and logical page footprint are both 17,694,720 bytes. Its 24
tables include 2,878 history rows and 2,878 matching media/metadata rows, 16 users,
five library sections, one notifier, 918 notification-log records and six login
records. Mobile devices, exports and image-hash lookup are empty. These are
discovery counts; the later authenticated cold archive establishes the actual
baseline. No user identity, Plex/API/JWT token, credential or production config value is
included in receipts or documentation; defaults below are public source values.

Original image:
`ghcr.io/tautulli/tautulli:latest@sha256:746b2accd580c8551bff3570eab9c6606bbefe9b33567feace2a3c3c9863a1d1`.
Candidate:
`docker.io/library/tautulli-security-20261023@sha256:769aa67e07e35bdfe714a486591eb1a34c9ad9bd6cf2da89da130dcdab9de05a`,
artifact 12550072523 from successful private CI 40068021890/source `c0413bd`.
Its OCI archive is 108,427,776 bytes, SHA256
`e2e9fe4ce25fddf7b6944f6b00212c256a80ad9df66cda70dfbb36585a687d40`.
The controller pins this exact candidate; source preparation does not establish
its independent scan, node preload, application rollout or acceptance.

The actual candidate app commit is
[`9484667bc1f2d159368a999320b8f495bbfbd00a`](https://github.com/Tautulli/Tautulli/tree/9484667bc1f2d159368a999320b8f495bbfbd00a).
The inspected public source bytes match the retained immutable primary-image
file manifest. Candidate `plexpy/__init__.py` SHA256 is
`4a1f3dc5a8776400a65759ea994838ebf616d165c71b8b05fa45b219fdda9e58`,
`config.py` is
`78219a36de30d8af5a80e3f57c614cc673271e61501ee7abef92d975d43e306d`.
Original running `__init__.py` is
`56765680920ceb86f4b80f05086b74f77d9ad7900ff057c553e6075c5e189dd9`,
`config.py` is
`101b23f3e4da12a5c7b760ee1eca15e5c67585c61ef65bddd9a7f8890a3e9117`.

## Cold preservation before the new writer

Use the existing [whole-application backup](COLD-APPLICATION-STATE-BACKUP.md)
for `tautulli` during root's protected zero-writer interval. Preserve the entire
`/config` claim, every file and directory, permissions/ownership/symlinks, logs,
cache, backups, exports, newsletters, configuration and matching database/WAL/SHM.
No directory is omitted because it looks disposable. The complete encrypted
archive remains authoritative, including original runtime logs and lock files.

Run this controller's `--cold-only` mode before adopting the candidate. It binds
the completed cold receipt by SHA, original image, namespace and these identities:

| Resource | Exact identity |
|---|---|
| Deployment `plex/tautulli` | `9db52ebb-23c8-47c6-82c8-ebde3b0a2775` |
| HelmRelease `flux-system/tautulli` | `e5aa088f-22a3-4f47-b7c4-094be5354bf4` |
| PVC `plex/tautulli-data-0` | `97eb095e-37ec-4185-80ed-4d8f3c19f486` |

The original Bound Longhorn PV must remain attached to that claim. Full archive
authentication, manifest hash, ciphertext size/SHA and authenticated EOF are
required. Only exact database/WAL/SHM, `config.ini`, `version.lock`,
`release.lock` and the bounded GitHub version-cache member are extracted into a new 0700 `/dev/shm` folder, with
member hashes and a combined 128 MiB ceiling. Other members stream through;
no plaintext lands on an ordinary disk. The temporary directory is removed on
exit. Age binary/identity/source/receipt/ciphertext are rechecked afterwards.

The preflight binds all 24 original table definitions and `table_xinfo` hashes
to the read-only discovery. It refuses unexpected tables/columns/definitions,
preexisting new indexes/columns, missing original indexes, nonempty mobile,
export or image-hash tables, and an unexpected version row. Those empty-table
guards prevent startup mobile revalidation, export cancellation and the new
HTTP-image cache deletion from silently changing existing records. They are
verified again against the authoritative cold state rather than assumed from
earlier discovery.

## Exact SQL projection

The candidate's
[`dbcheck`](https://github.com/Tautulli/Tautulli/blob/9484667bc1f2d159368a999320b8f495bbfbd00a/plexpy/__init__.py)
adds exactly these columns to this already-upgraded original schema:

| Table | Permitted addition |
|---|---|
| `mobile_devices` | Nullable TEXT `push_token`, NULL on original rows |
| `exports` | INTEGER `squareArt_level DEFAULT 0` and `theme_level DEFAULT 0`, zero on original rows |

Every original table, row and original field is observed. Typed NULL/integer/
float/text/blob cells feed whole-row and individual-column HMACs, ordered by
every original column. No credential, notification config, Plex token, user
field, history field or internal sequence is excluded. All original application
rows/old columns must match exactly, apart from the measured default-avatar
mapping described below; ordinary refresh/playback/login/notifier
writes can cause a strict refusal and require concrete review rather than a
blanket runtime exemption.

Two specific metadata transformations are source-proven and measured separately:
the `version_info` row for key `version` must change exactly `v2.16.1` → `v2.18.2`,
while its old-value projection and all other rows match; `sqlite_stat1` is
regenerated by `PRAGMA analysis_limit=400; ANALYZE`. Both original/current
statistics table counts and every field HMAC remain in receipts. The live table
must equal independent recomputation on a second private RAM database, using
the candidate image's actual SQLite runtime. It is not ignored. All original
indexes remain except the three explicitly removed single-column history
indexes; exactly the 14 source-listed replacement/additional indexes are
required. Trigger/view/index definitions otherwise match. Added-column table
DDL must equal SQLite's exact result for the source ALTER statements.

Existing limits remain 128 MiB combined RAM snapshots, 250,000 rows, 256 columns,
one MiB per cell, 32 MiB aggregate encoded cells and a 90-second SQL deadline. The
observed 17.7 MB database fits the two-snapshot RAM requirement; larger cold/live
state refuses instead of increasing limits. The reader retains 256 MiB memory,
500m CPU, 600-second lifetime. `quick_check=ok` and normal read-only/WAL semantics
are required. There is no `immutable=1`, checkpoint, vacuum, journal change or
write to the mounted database. WAL read-lock/SHM coordination is not claimed to
have zero metadata effects.

## Configuration and non-database files

Canonical INI section/key/string values are HMACed without printing values.
The strict parser refuses duplicate/multiline ambiguities rather than guessing
ConfigObj semantics. Current config must already be version 22, retain nonempty
API/JWT/Plex UUID fields, disable JWT regeneration and use the inspected
`/config/logs` logging location. ConfigObj's actual `write` copies unknown and
retired keys; their values must therefore remain, too. Only three exact new
source defaults are admitted: Advanced `allow_mounted_folders=0`,
`remote_app_push_url=https://relay.tautulliremote.com`, and
`x_frame_options=SAMEORIGIN`. The existing HTTP/Plex-admin setting is retained
despite a changed upstream default. The one source-written UI flag
General `update_show_changelog` must become 1 on the release transition. API/JWT
secrets and every other old value must match their original HMACs.

All non-DB paths, kind/mode/uid/gid/link targets and file contents are HMACed.
Admitted changes are canonical-verified `config.ini`, exact startup
`release.lock`/`version.lock` contents, and appends to the four source-defined
active logs. The finite websocket log set also admits the pinned logger's
5 MB/five-backup rotation: original active bytes must appear as a complete prefix
in the rotated file, and every retained old backup must match at its shifted
index. Original logs remain complete in the cold archive. The GitHub version
cache may advance its integer fetch clock and release stamp only; all cached
response data must match. Other path, metadata, cache, backup or export changes
refuse. Appending active logs must retain the original byte prefix and metadata.
No fake whole-files equivalence is claimed: changed runtime file HMACs/classes
are recorded, and `all_files_equivalent_claimed` remains false. The full original
logs are still retained in the authenticated archive. File bounds remain 4 GiB,
4,096 entries and 120 seconds, with no symlink following or device crossing.

## Later controlled execution and restart

The post-adoption mode requires one Ready writer at the exact candidate digest,
the original Deployment/HelmRelease/PVC, original `/config` mount, owned
ReplicaSet/Pod and a healthy node. It creates one uniquely owned candidate-image
Python reader on that node, with an explicit sleeping command instead of the
app entrypoint. Only this PVC is mounted read-only; no native Secret, environment,
service-account token, NAS, init/ephemeral container, fsGroup or extra capability
is supplied. UID/GID 1000, read-only rootfs and all-capabilities-dropped remain.
Source/app modules are not imported. SQLite snapshot backups go only to RAM.

Supply the existing independent verification key through protected stdin, never
argv/env/Git/manifests. Receipts stay 0600 under new 0700 native WSL directories
outside Git. The helper deletes only its own reader using a server-side UID
precondition after successful checks; failure retains its receipt and bounded
reader for review. It does not restart or scale anything.

Invocation order, after root reviews this source:

```bash
python scripts/migration/verify-tautulli-state.py tautulli --apply --cold-only --cold-receipt /protected/tautulli-cold/receipt.json --cold-receipt-sha256 <reviewed-sha> --output-dir /home/brajam/.local/share/branconet-migration/tautulli-state-20261024
# After root independently qualifies/adopts the candidate:
python scripts/migration/verify-tautulli-state.py tautulli --apply --cold-receipt /protected/tautulli-cold/receipt.json --cold-receipt-sha256 <reviewed-sha> --output-dir /home/brajam/.local/share/branconet-migration/tautulli-state-20261024
# After root's separate controlled restart, repeat with:
# --previous-live-receipt /protected/initial-state/receipt.json --previous-live-receipt-sha256 <reviewed-sha>
```

Restart mode requires a different writer Pod UID and the same original cold
archive/key binding, original workload/storage identities and exact new image.
It independently reruns preservation against cold state. Restart receipts do
not substitute for initial preservation or imply an observer-triggered restart.

## Remaining functional and recovery gates

Root still must run cold preflight, inspect the exact unsuppressed candidate
scan, publish private Flux values, verify live preservation, existing API-key
authentication, Plex/library connectivity, history/user/library/notifier route
behavior, and controlled-restart persistence. Removed
[`get_apikey` in 2.17.0](https://github.com/Tautulli/Tautulli/releases/tag/v2.17.0),
[remote push changes in 2.18.0](https://github.com/Tautulli/Tautulli/releases/tag/v2.18.0)
and [history grouping in 2.18.2](https://github.com/Tautulli/Tautulli/releases/tag/v2.18.2)
need source-aware integration checks. Never regenerate a key, regroup production
history, log in/create accounts, or send a notification as an observer probe.
This controller keeps full application/functional acceptance false. Actual
normal application startup can perform its configured integration work; the
observer makes only the fixed read-only Plex requests described here. Restore the complete original
state and original image together if rollback is needed, keeping failed migrated
state separately; an image-only downgrade is unsafe. Archive authentication is
not an independent restore demonstration.


## Bounded authenticated functional observer

[`qualify-tautulli.py`](../scripts/migration/qualify-tautulli.py) is a separate,
prepared read observer. It first requires an exact successful live preservation
receipt and the same original Deployment/HelmRelease/PVC and Ready candidate
Pod. It invokes public Python code inside that existing Pod, without creating
resources or mounting Secrets. The existing API key is read from `/config` only
inside the Pod's RAM and sent in `X-Api-Key` on loopback. No key enters argv,
environment, query URLs, reports or the operator workstation. Redirects and
proxy inheritance are refused. A missing/disabled key causes refusal; it never
generates a replacement or changes configuration.

The protocol is verified from pinned candidate commit
[`9484667`](https://github.com/Tautulli/Tautulli/tree/9484667bc1f2d159368a999320b8f495bbfbd00a).
`plexpy/api2.py` explicitly accepts the header and removes it from request kwargs;
`webserve.py` exposes the exact read aliases. The helper checks eight actual
protocol source-file hashes inside the pinned image before making requests.
Its fixed commands verify unauthenticated rejection, authenticated status,
version/Python runtime, configured Plex identity, actual PMS `/identity`, live
Plex library statistics, stored library/user views, one existing history record,
and existing notifier/configuration reads. Stored user/library/notifier IDs are
compared internally with query-only SQLite results; private names, server
identifiers, credentials, history contents and notifier config values are not
returned. Receipts contain counts, fixed read names/statuses and public hashes.

`get_server_info(return_info=True)` returns before the source's configuration
update path. `get_libraries` uses PMS GETs with one-item statistics requests,
without the library refresh command. History explicitly disables grouping and
activity inclusion and requests one row. Notifier config reads admit only the
pinned-source agents with pure config constructors/options; a device-discovery
or script-listing agent requires concrete source review instead of executing an
unreviewed path. No `notify`, login, refresh, SQL API, backup, update or restart
command is called. Normal application request logging and background activity
remain subject to the independent state-preservation contract; zero incidental
metadata effects are not claimed.

Each response is bounded to 4 MiB, all responses to 16 MiB, and the request set
to a 180-second admission deadline with 30-second individual reads. The outer
SSH observation is bounded. This proof concerns Pod-loopback HTTP and actual
Plex reads, not ingress TLS, user browser login, notification delivery or final
whole-goal acceptance.

Root executes after reviewing the helper and after live preservation passes:

```bash
python scripts/migration/qualify-tautulli.py --state-receipt <successful-live-state-receipt> --state-receipt-sha256 <exact-sha256> --output-dir /home/brajam/.local/share/branconet-migration/tautulli-functional-20261024
```

After root's separate controlled Flux restart and successful repeat preservation,
run the same command with the new state receipt and add
`--previous-functional-receipt <initial-functional-receipt>` and
`--previous-functional-receipt-sha256 <exact-sha256>`. Restart observation requires
a different Pod UID, the same authenticated cold baseline, and a preservation
receipt that independently proved restart persistence. The observer never
restarts anything. All receipts are exclusive private native files outside Git.
AST and source-scope checks remain preparation only; the later live receipts
below establish the executed initial and restart observations.


The first cold preflight refused the prepared version18 assertion before any
candidate writer started. Full authenticated cold configuration inspection found
version22. The pinned candidate's complete `_upgrade` chain also ends at22;
its18->19->20->21->22 cases are not executed for this existing state. The
assertion now requires exactly22 on both sides; every original config value
still has to match. The original failed receipt remains retained.

## October25 observed acceptance

The whole original claim was archived and authenticated with no exclusions:
792 files,157,848,900 plaintext bytes; ciphertext SHA256
`fe1da45dcb2cd69efbf4d4a26f1997f29934b0d8e9abb409974413eef0d8e810`.
Cold receipt SHA256 is
`ff297b015975b8f7a0fb06a61eb627f768e9ec7d97e134f6989fba307e20f84d`.
Both the initial and independent new-Pod observations preserved all16 stored
users,2,878 history/media/metadata rows, five stored library sections, notifier
settings and the original credentials, apart from these explicit source changes.

One user's default Plex avatar advanced. The source-verified mapping requires
two verified HTTPS GETs to the fixed Plex user endpoints, credentials confined
to writer-Pod RAM/header, and an exact HMAC match to the fresh avatar. Only
`thumb` and its default custom-avatar fallback are projected back; actual custom
choices and every other original field must match. This is a measured field
change, not whole-row byte equality. The accepted log rotation and GitHub-cache
fetch-clock/release-stamp changes are constrained as described above; original
files remain in the encrypted archive.

When a closed WAL-header database has neither sidecar, the observer verifies a
stable source descriptor/inode/size/clock before and after a bounded private
RAM copy, then uses normal SQLite read-only semantics on that copy. It requires
both sidecars still absent and deletes the RAM copy before its second independent
snapshot. Normal live WAL reads are unchanged. No immutable mode, source write
or larger snapshot/resource ceiling is used.

Initial state receipt SHA256:
`d6a835c08b6a9dd47f8c2209c8275ebed86c78244c837f1c13da527d08a5d766`.
Restart state receipt SHA256:
`ee1428a2b201773d3b6535879758caec4f859dcae98856f093a73bc9d8df21c6`.
The restarted writer Pod UID is `e07afbcd-5e0e-4d7c-90f0-a5843626373f`.
All owned successful readers were UID-precondition deleted.

The11 authenticated read checks passed initially and after restart, including
Plex identity, existing history/notifier views and actual Plex libraries.
All five historical library rows remain; connectivity checks cover the three
active real libraries. The inactive historical row and official virtual LiveTV
sentinel999999 are preserved, not required to appear as current Plex sections.
The exec observer drops its own UID/GID/groups to1000 and requires NNP and zero
effective/permitted capabilities before reading credentials; it does not change
the application's runtime identity. Initial functional receipt SHA256:
`8b460cf95316e731c7b26ff6996724d72350cdd787c2c847529279387fe74d06`;
restart receipt:
`87148e3560bd21993d62558ee3e203d584f3ea8bcf84be7afc393d09759e7c23`.

Private chart commit `659bd71` restored routing after these proofs. All six
actual routes passed: original published port9119 and hostname
`tautulli.branconet.lan` through each node, returning the expected login redirect.
Route receipt SHA256:
`b957172a48d78e8c2e9b07f1ae9caf6f88f24aed68f4a6ee20a2c7017852c76f`.
Port8181 is the container port, not the published host port.

Fresh October24 database analysis of the exact derivative reports0 critical,
48 high, with0 available critical/high fixes. Its scan receipt SHA256 is
`f2c7103acfd3e371851fae50466522f0f5720e928779eb8858ad0cd9e573a50c`.
No source, package or advisory suppression was applied. Browser acceptance and
whole-cluster completion remain separate; no independent restore drill is claimed.
