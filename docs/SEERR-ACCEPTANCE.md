# Seerr post-cutover verification

## Official upstream image accepted October 25

The current image is official upstream
`ghcr.io/seerr-team/seerr:v3.5.1@sha256:d8fab675b55ad293ded98fd71efcfd46054cbad9746534ae1cc4794a88c0b3be`.
It identifies the same application source revision used by the preceding
derivative. The user has superseded bespoke third-party image maintenance.
The older derivative and every original backup remain retained for recovery.

Fresh complete cold backup: 119 files / 7,777,919 file bytes, ciphertext
7,917,652 bytes, SHA256
`b70eb9a319fda964a445fb4e8d11a9b38abacf7fd8e46a0ca28f95310e19cdce`.
Full authentication and exact archive/manifest comparison passed. A copy on the
dedicated SMB recovery share passed full checksum read-back and age authentication;
encrypted companion metadata was also copied and verified. The readonly reader
was deleted with its UID guard and observed gone. The initial mount guard refused
an API-omitted default false field before creating a reader; its failed receipt
and original source remain. The corrected guard normalizes that false default only.

The explicit modern cold-baseline mode verified SQLite in private RAM and
fingerprinted all six accounts, 654 requests, 1,099 media records, 1,405 seasons,
634 season requests, three issues, four comments, three user settings and zero
push subscriptions, plus 199 current settings leaves. No legacy Overseerr
transformation was applied to this already-migrated snapshot. Full data,
credentials/permissions, Plex and Arr integration checks passed after upstream
adoption and again after the chart-driven restart. An early observation was
refused during the changing rollout; a later stable Pod passed. No false cause
or successful result is attributed to the early refusal.

After receipt SHA256:
`fbc4bf6cb51e4054a9bab9ff09d76f0681d777e61dfed40a31613d81f40f07b1`.
Restart receipt SHA256:
`4e488c108b4f67fb964addfacaa5a7dd6438892a9d2b7947993b16793eaef631`.
The restart Pod UID is `b0f4624f-813e-4eb7-917e-c87c44e244f4`.
Charts main/validated/live Flux reached
`08392b8d6d9b3a682442cd734b484e27550f9249`; release revision151 is Ready.
Both normal `https://media.jtmb.cc` public API routes returned200 with verified
TLS and expected initialized/version state. This proves external route/backend
acceptance, not interactive login or final UI workflows. Those remain open until
implementation is finished. No fresh zero-CVE scan claim is made for the vendor
image. [Public adoption receipt](../evidence/seerr-upstream-adoption-20261025.json).

## Earlier migration and derivative evidence

Current checkpoints and unresolved gates are summarized in [MIGRATION_STATUS.md](../MIGRATION_STATUS.md). This document retains operational contracts and dated attempt history.

`scripts/migration/qualify-seerr.py` and its sibling `qualify-seerr.cjs` actually
passed full account/history/configuration, startup and integration checks on
October24, then passed again after a controlled new Pod. Root verified the
complete encrypted cold backup, exact image, Arr tag changes and restored routes.
Final browser validation remains pending after implementation. The helper creates no Kubernetes object and changes no
application configuration. It runs only explicit read checks, then creates one
new private local receipt. It cannot complete migration acceptance alone.

## Pinned migration contract

This helper targets Seerr 3.5.1 source commit
`564bfb08b54caa374bddaf820abfd226e5e69151` and the separately accepted immutable
[security derivative](../images/seerr/README.md). The upstream
[Overseerr merge](https://github.com/seerr-team/seerr/blob/564bfb08b54caa374bddaf820abfd226e5e69151/server/lib/overseerrMerge.ts)
copies existing user IDs, credentials, Plex identity, permissions, avatar and
timestamps. The helper compares all eleven original account fields, both the
whole ordered-row HMAC and each column HMAC. It grants no automatic exceptions
for mismatched timestamps, avatars, tokens, identities or permissions.

The merge adds Jellyfin/avatar-cache columns, creates watchlist/override/blocklist
structures, repairs text quota values, sets Plex type and replaces only the
default application/email sender title. It remaps deleted media status 6 to 7;
the later [deleted-status migration](https://github.com/seerr-team/seerr/blob/564bfb08b54caa374bddaf820abfd226e5e69151/server/migration/sqlite/1789254652493-RemapOverseerrDeletedStatus.ts)
also handles seasons. Table counts and raw database bytes are therefore not
enough to establish history equality. Do not treat a new schema or migration
record count as history loss, or relax any unexplained row/column difference.

Pinned [settings migrations](https://github.com/seerr-team/seerr/tree/564bfb08b54caa374bddaf820abfd226e5e69151/server/lib/settings/migrations)
move region/network fields, remove LunaSea, rename blacklist fields, and
[rename existing Arr user tags](https://github.com/seerr-team/seerr/blob/564bfb08b54caa374bddaf820abfd226e5e69151/server/lib/settings/migrations/0007_migrate_arr_tags.ts)
when request tagging is enabled. Startup itself can perform these writes and
start scheduled jobs. This helper never invokes those migrations, jobs, tag
updates, notification tests, scans, queues or settings routes. Root must review
the encrypted original tags against resulting IDs and expected renamed labels;
the migration marker alone is not evidence that every tag was preserved.

## Private baseline and key

Use the actual cold `cold-data-baseline.json` from the separately verified full
encrypted archive, never the earlier live observation. It must contain
`counts`, `sqliteQuickCheck:"ok"`, and `userPreservation` with `columns`, `count`,
`ids`, `hmacSHA256`, `perColumn`. Required user column order:

```text
id,email,username,password,plexId,plexUsername,plexToken,permissions,avatar,createdAt,updatedAt
```

All HMACs use the same private verification key and UTF-8 compact JSON with
Unicode preserved. Values for a column are arrays ordered by numeric ID. User
whole-row HMAC uses objects whose insertion order is the stated column order.
Python equivalents: `json.dumps(value,separators=(',',':'),ensure_ascii=False)`
and `hmac.new(key.encode(),encoded,hashlib.sha256).hexdigest()`.
Protect this metadata outside Git; do not include values in the metadata.

The existing cold backup contract supplies counts and user HMACs only. Full
history preservation requires archive-derived per-row and per-column HMACs;
counts-only metadata cannot pass. Root runs the source-only cold-baseline mode
on the approved Linux controller after the separate backup receipt exists:

```bash
python3 /protected/tools/qualify-seerr.py cold-baseline \
  --archive /protected/evidence/overseerr-cold-config.tar.gz.age \
  --verified-receipt /protected/evidence/backup-verified.json \
  --age /approved/bin/age --identity /protected/operator/id_ed25519 \
  --output /protected/evidence/seerr-cold-comparison.json \
  < /protected/verification-key.txt
```

This mode makes no live call. It binds the actual encrypted archive SHA256 to
the successful original receipt, authenticates age decryption with the existing
SSH identity, limits encrypted/plain/decompressed archive content to 128 MiB,
and restores only settings and SQLite+WAL/SHM in a mode-0700 temporary directory
on verified `/dev/shm` tmpfs. SQLite recovery affects this private RAM copy only.
The complete archive and original receipt remain unchanged. It quick-checks
the restored database, binds original counts, and creates metadata exclusively
outside Git with mode 0600. It produces these comparison fields:

```text
historyPreservation:
  <table>: { columns: ["id", ...all original retained columns],
             ids: [ordered original IDs],
             perColumn: { <column>: <HMAC of ordered expected values> },
             perRow: { <id>: <HMAC of column-ordered expected value array> } }
settingsPreservation:
  <RFC6901 JSON pointer>: <HMAC of the expected value at that pointer>
```

History tables required for the full gate: `media_request`, `media`, `season`,
`season_request`, `issue`, `issue_comment`, `user_settings`,
`user_push_subscription`. The generator selects every original column for these
tables, transforms only media/season `status`/`status4k` 6→7 and explicit
user-settings changes: null/empty dropped `region`, text affinity for integer
`notificationTypes`, and `discordId`→SQL single-element `discordIds` text. It
refuses any populated dropped region. The
[Discord migration](https://github.com/seerr-team/seerr/blob/564bfb08b54caa374bddaf820abfd226e5e69151/server/migration/sqlite/1779783365432-AddDiscordIdsColumn.ts)
defines that exact conversion. All original relationship IDs and history text
remain in the fingerprints. It does not normalize timestamps or any runtime
changes; even vendor-job changes must be reviewed as differences. The generated
transformation list records the exact projections. No wildcard exception or
post-hoc copying of observed hashes is acceptable. Missing fingerprints cannot
pass. The generator includes counts for all nine retained tables.

For settings, the generator fingerprints every retained original leaf at escaped JSON pointers,
including all credentials, notification configuration, Plex, Arr and application
settings. It applies only the documented merge/settings field migrations, adds
Plex type, replaces exact default titles, requires disabled removed LunaSea,
records required absent old paths and exact array lengths, and retains original
migration markers as a required subset. New upstream default fields may appear;
no original unknown key is ignored. Library scan timestamp changes remain false
in literal comparison. Only the explicit cold-bound runtime proof below can
separately accept the two reviewed operational fields; there is no automatic
timestamp or database-field exception.
At minimum the helper requires `/clientId`, `/main/apiKey`, `/plex/ip`,
`/plex/port`, `/plex/machineId`, `/radarr/0/apiKey`, `/sonarr/0/apiKey`; these
minimum checks do not substitute for the archive-derived complete leaf map.
The generator restricts canonical values to null, booleans, valid UTF-8 strings,
safe integers (absolute value <= 2^53-1), arrays and string-keyed objects; it
refuses floats, binary values and lone surrogates to avoid Python/Node drift.
Review the generated baseline coverage explicitly. Missing settings fingerprints leave
the full gate open. Without that optional proof, every supplied mismatch fails.

### Optional proof for the two Plex runtime scan clocks

The original retained `after.json` at 02:19:35 UTC matched all 143 settings
leaves literally before its unrelated HTTP query-validation failure. Its SHA256
is `1bf205660ac1d1b975a5ed04d691000d87180a9c36834422012b3d0ed7ad72f6`.
The later full network check passed startup/Plex/Arr/accounts/history but found
only `/plex/libraries/0/lastScan` and `/plex/libraries/1/lastScan` advanced.
The [pinned recent Plex scanner](https://github.com/seerr-team/seerr/blob/564bfb08b54caa374bddaf820abfd226e5e69151/server/lib/scanners/plex/index.ts)
processes each enabled library, then saves `Date.now()` into that library's
`lastScan`, retaining its other fields. Its source SHA256 is
`823baac8e20d471e3a1519c2855b3cdd5107820d221aa000b5cdf5c7dcdb7fcf`.
The [scheduler](https://github.com/seerr-team/seerr/blob/564bfb08b54caa374bddaf820abfd226e5e69151/server/job/schedule.ts)
invokes this routine on its configured schedule, normally every five minutes.

A separate read-only proof authenticated the complete original cold archive and
recovered the two original numeric values in RAM. Their HMACs matched the
unchanged cold-derived baseline. Both live fields were safe nonnegative integer
milliseconds, advanced monotonically about 900 seconds, fell after the literal
preservation receipt and remained within current time. Other 141 original leaves
still matched. All three original libraries remained; only the first two have
these original scan-clock pointers. Container log filtering exposed no matching
info events, so the proof does not claim a correlated log body or completed-job
event; it records this limit explicitly. The observed times align with the
five-minute routine, and the pinned write semantics identify their operational
purpose.

Root may opt in with `--runtime-scan-proof /protected/evidence/readonly-lastscan-proof-279df337843747a1a73e8ce87acb58b4.json`.
That actual proof's SHA256 is
`467d8e25228f38de9bedbab85ac5f5b3a83674fa2c0a21e69e2b749cf8c81155`.
Keep the original `after.json` alongside it. The operator checks owner-only proof
permissions, upstream source, original baseline/archive SHA, exact first-receipt
SHA and all 143 literal first-receipt settings results. Deployment, PVC, volume
and accepted image identities must match; original array and absence contracts
remain unchanged. It reads only these artifacts and never replaces their hashes
or rewrites the baseline.

Python and Node independently bind each proof's original integer value to the
original settings HMAC. Node allows only the two exact pointers, only when their
libraries are still enabled, and only a safe integer strictly greater than the
original, no earlier than the literal preservation receipt and no later than
`Date.now()`. Original values that still match literally need no exception.
Literal results remain visible in `settings.preservation`; reviewed operational
advances are reported separately under `settings.runtimeScanAdvances`, with
numeric/type/monotonic/time-bound booleans and proof provenance. All remaining
settings, accounts, credentials and every database/history column stay strict.
This does not waive SQL `createdAt`/`updatedAt`, arbitrary library fields, a
regression, string timestamp, future value or any other mismatch. The same
original proof can be supplied with a later restart observation; the restart
identity fence still requires an actual restart. Source preparation of this
option does not establish a successful complete qualification.

The key enters only raw UTF-8 stdin with an optional trailing newline. Never
pass it in argv, environment variables, logs or Git. The wrapper sends the key
and baseline to Node only through `kubectl exec -i` stdin. Application/provider
credentials are read in RAM from the existing config/database inside that Pod.
There is no Kubernetes Secret read, credential export or plaintext temp file.

## Exact operator run

Stage both siblings together on the approved operator host with existing
`kubectl`/kubeconfig. Use an owner-only directory outside Git for receipts.
The Windows operator must enforce equivalent directory ACLs; POSIX modes are
checked automatically. Root records the exact post-cutover Pod UID, existing
Deployment UID, original PVC UID and scanned image reference first.

```bash
python3 /protected/tools/qualify-seerr.py \
  --pod '<accepted-new-pod>' --pod-uid '<accepted-new-pod-uid>' \
  --deployment-uid '<existing-deployment-uid>' --pvc-uid '<original-claim-uid>' \
  --expected-image '<accepted-repository>@sha256:<accepted-digest>' \
  --baseline /protected/evidence/seerr-cold-comparison.json \
  --receipt /protected/evidence/seerr-after-cutover.json \
  < /protected/verification-key.txt
```

The fence requires one Running/Ready `app=overseerr` Pod, exact Pod identity,
Pod→ReplicaSet→existing `plex/overseerr` Deployment ownership, one desired and
available updated replica, exact spec and runtime digest, original Bound
`plex/overseerr-data-0` mounted at `/app/config` without subPath. It repeats the
fence after execution and refuses any identity/restart change. It lists the
namespace Pods and refuses every other holder of this exact claim, including
differently labelled, terminating and completed Pods. Runtime execution must be UID/GID 1000
with working directory `/app`, package 3.5.1 and its native `sqlite3` module.

SQLite opens READONLY with connection query-only mode and one read transaction,
including committed WAL contents. It performs quick_check, foreign-key check,
count/account/history comparisons and closes before network checks. No database
checkpoint, journal change, schema migration or ORM startup is performed.

The [startup API](https://github.com/seerr-team/seerr/blob/564bfb08b54caa374bddaf820abfd226e5e69151/server/routes/index.ts)
checks localhost status, initialized public settings and config permissions.
The pinned OpenAPI request validator requires the optional update-check flag
to be a boolean: `checkUpdateAvailable=false` is accepted and parsed as false,
suppressing the upstream GitHub update lookup. An empty value was actually
rejected with HTTP 400 before integration checks; that failed observation is
retained. Status must report 3.5.1,
the image's committag and no required restart. The direct Plex `/` request uses
the preserved owner token in `X-Plex-Token` and requires the configured machine
identity. Every configured Radarr/Sonarr instance receives only
`GET /api/v3/system/status` using `X-Api-Key`. No token enters any URL. Requests
use verified TLS, no environment proxy, no redirects or retries, 15-second
socket timeout and a 1 MiB response limit. The wrapper limits the overall exec
to 240 seconds. A timeout stops its transport; it does not restart the app.

Receipts contain counts, account IDs, match booleans, provider instance IDs,
source/baseline hashes and exact Pod/image/PVC identity, never raw credentials,
URLs, settings, history text, response bodies or errors. Exit 0 means all helper
checks passed; 3 means a comparison failed or required fingerprint coverage is
missing; 1 means qualification was refused/failed. Inspect the protected receipt
for booleans. Transport/fence failure emits a fixed category and may produce no
receipt. Receipts are exclusive-create and never overwritten.

## Restart and remaining adoption gates

After Root's separately authorized restart, repeat with the new Pod identity
and a new receipt path, adding
`--prior-receipt /protected/evidence/seerr-after-cutover.json`. This requires a
previous passing helper receipt, unchanged Deployment/PVC/volume/image and a
new Pod UID or increased restart count. It rechecks all baseline data and
integration health; it does not itself restart anything.

Root still verifies original account login/Plex behavior and permissions through
the normal UI, full historical records/relationships, all retained routes,
expected Arr tag IDs/renames, original encrypted backup and rollback
compatibility, resource limits and residual scan findings. Account HMACs prove
stored credential preservation, not a successful interactive login. HTTP status
checks prove authenticated reachability, not new-request fulfillment. The
receipt always states `acceptanceComplete:false`; neither Ready Pods nor a
passing helper can close those independent gates. Follow the existing private
chart rollback runbook; never start the old image on a migrated database.
