# Pi-hole OS-only patch: preservation and acceptance

This is prepared source, not a completed backup or cutover. Root owns the exact
local build/scan/preload, Flux stop/adoption/restart and live acceptance.
No application version, entrypoint, command, UID, persistent mount, API password
or DNS upstream change is intended. The recipe in `images/pihole` starts with
the actual original image and requires byte-identical Pi-hole/FTL/web/entrypoint
files across the signed same-Alpine-branch OS upgrade. An exact derivative image
and its unsuppressed scan remain prerequisites; a source recipe is not proof.

## Actual original resources, inspected October 24

| Resource | Identity / binding |
|---|---|
| Deployment `pihole/pihole` | `a00fc6d2-55f3-4182-baf9-5ffc97544f0b` |
| HelmRelease `flux-system/pihole` | `db6aabc6-dd2c-46c3-bbfd-b35ddf453078` |
| PVC `pihole-data-0-retry1` | UID `b06ca45b-e902-4f0c-a2bf-77e9fca960e8`; `/etc/dnsmasq.d` |
| PVC `pihole-data-1-retry1` | UID `e19b6e39-6a4f-4c6d-b2fe-be27085e1ea9`; `/etc/pihole` |
| Service `pihole/pihole` | UID `d24761ff-af16-4079-b6f6-9d19b1de3f93`; ClusterIP `10.96.11.155`; TCP/UDP 53 and HTTP 80 |
| Original running image | `pihole/pihole:latest@sha256:ee348529cea9601df86ad94d62a39cad26117e1eac9e82d8876aa0ec7fe1ba27` |

Both actual retry1 claims are Bound Longhorn claims using their original
`pvc-<UID>` PVs. Their PV UIDs are respectively
`1d95c7d9-93ba-4d7b-93c4-7b97bb17ec79` and
`93d699db-4039-4836-a733-2573997c4406`; both actual CSI drivers are
`driver.longhorn.io`, with matching original claim UID/name/namespace bindings. The similarly named old `pihole-data-0`/`pihole-data-1` partial
migration claims remain retained and are not substituted or deleted. The
original Pod was Ready on workernode2; actual `pihole-FTL --version` returned
`v6.5`. These are discovery observations, not later cutover acceptance.

## Full two-claim cold archive

[`cold-pihole-state-backup.py`](../scripts/migration/cold-pihole-state-backup.py)
is an independent fixed Pi-hole scope using the unchanged existing MeTube
inventory/archive/authentication primitives. It does not broaden the existing
five-application helper or replay BORTUS recovery. Root first publishes only
Pi-hole's zero writer through the existing local-validation -> validated -> Flux
path and waits for the unsuspended Ready HelmRelease and observed zero-replica
Deployment. DNS availability during that cold interval must be observed; do not
silently change host, cluster or LAN DNS configuration to make the backup pass.

The helper requires the exact original image, Deployment/HelmRelease, both
claim/PV identities and original mount paths. Every other live/terminating/
initializing Pod mounting either claim refuses capture. It mounts **both full
claims read-only**, without exclusions, Secrets, NAS, token, hostPath, envFrom,
app entrypoint or fsGroup/chown. The helper never stops/resumes a writer.

Discovery found two entries/48 bytes under dnsmasq and 93 entries/about 1.087 GB
under Pi-hole. Directories were 0755; three files were 0600 owned by UID1000,
and one file was 0640 owned by root:root. This requires the explicit reader
**UID1000/GID0**, rather than guessing 1000:1000 or adding DAC capabilities.
A cap-dropped in-Pod probe opened the regular files with this UID/GID, but its
inherited supplemental groups were broader; it is not claimed as the exact
future reader proof. The vendor capsh group-reset option refused on a libc
`sysconf` error. Fresh node status reports Strict supplemental-group support on
all three nodes. The prepared reader therefore requires `supplementalGroupsPolicy:
Strict`, no extra groups, all capabilities dropped, no privilege escalation,
read-only rootfs, RuntimeDefault seccomp, and verifies actual effective UID/GID,
groups, zero effective/permitted/ambient capabilities and no-new-privileges
before inventory. Every full file read must succeed; metadata alone is not
readability or backup acceptance.

Existing bounds remain **4 GiB total data, 4,096 entries**, 256 MiB reader memory,
500m CPU, 1,800-second reader lifetime and bounded 900-second archive observation.
The pinned reader image sleeps instead of starting its application. The full
archive streams directly into pinned age encryption on the native operator;
no ordinary-disk plaintext extraction occurs. The complete ciphertext is
then decrypted/authenticated to EOF and every original member/content/metadata
is verified. The original plaintext tree is fenced before and after capture.
Only the uniquely owned reader is deleted, with a UID precondition, after
success. Failure retains its receipts and bounded reader for root inspection.

Repeatable opt-in entry point:
`playbooks/cold-pihole-state-backup.yml`, role `cold_pihole_state_backup`.
The default apply flag is false. Protected nonsecret settings:

```json
{"cold_pihole_state_apply":true,"cold_pihole_state_output_dir":"/home/brajam/.local/share/branconet-migration/pihole-cold-20261024","cold_pihole_state_node":"workernode2"}
```

After source review and the independent Flux zero-writer fence:

```bash
/home/brajam/.local/share/branconet-migration/venv/bin/ansible-playbook playbooks/cold-pihole-state-backup.yml --extra-vars @/protected/pihole-backup-settings.json
# Equivalent exact-scope helper, from the reviewed source tree:
/home/brajam/.local/share/branconet-migration/venv/bin/python scripts/migration/cold-pihole-state-backup.py --apply --node workernode2 --output-dir /home/brajam/.local/share/branconet-migration/pihole-cold-20261024
```

The successful private receipt binds both claim identities, source/helper
hashes, full manifest/ciphertext SHA256, bytes and complete authenticated
verification. This proves preservation of the entire original source; it does
not prove an independent restore or that a restarted application retains every
logical row. Preserve all original archives and failed attempts.

## Functional and restart acceptance required from root

1. Bind the qualified derivative's exact OCI digest/provenance/OS delta to
   byte-identical application/entrypoint hashes. Retain original image/cache and
   both original claims. Adopt only through the same private Flux publisher.
2. Verify actual FTL remains v6.5, exact new Pod imageID, original Deployment/
   HelmRelease/PVC/Service identities, one Ready writer, unchanged native Secret
   reference/UID, mounts, DNS configuration and routes. Do not run gravity,
   database rebuild, update, password reset or config setters as a smoke test.
3. Observe **UDP and TCP DNS** separately, including actual framed TCP replies,
   transaction ID/question validation, nontruncated NOERROR answers for a public
   known name and existing local resolution against the original baseline.
   Probe the actual ClusterIP from inside the cluster and existing externally
   exposed routes after inspecting their current bindings; do not assume the
   ClusterIP service has node ports. Repeat on all existing public node routes.
4. Use the deployed v6.5 self-hosted `/api/docs` specification. The
   [official authentication contract](https://docs.pi-hole.net/api/auth/) uses
   `POST /api/auth` with an existing password in the JSON body, then
   `X-FTL-SID` for authenticated GETs; no credential goes in query URLs, argv,
   logs or artifacts. Observe `info/version`, DNS blocking/status, summary and
   configuration/list read behavior using exact deployed docs. Delete only the
   observer's own transient session afterwards. Never create an app password,
   reset production auth or disable authentication to obtain a green check.
5. Existing `pihole-runtime` Secret metadata contains `WEBPASSWORD` but no new
   `FTLCONF_webserver_api_password` key. The pinned
   [vendor startup source](https://github.com/pi-hole/docker-pi-hole/blob/b890f5db95e837f8b94f954a25f2ea3d2dc54765/src/bash_functions.sh)
   preserves an existing TOML password hash when no new password override is
   supplied. Do not assume the legacy Secret key actively sets a v6 password.
   Any authenticated test uses preserved existing credentials in RAM and
   retains an honest failure rather than changing the password or Secret.
6. Before entrypoint adoption, retain cold SQLite integrity/schema/table counts
   and preservation fingerprints for configuration, credentials, groups,
   clients, adlists, domain rules and query history. Observe after adoption and
   after a separate controlled Flux restart with a different Pod UID. Same app
   bytes mean no intended app migration, but normal startup/background writes
   still require comparison: do not claim whole-file byte equality or waive
   lost rows because the Pod is Ready. The full original encrypted two-claim
   archive remains the rollback/recovery source. Query counts alone do not
   establish original-row/credential preservation.
7. Repeat exact image/DNS/auth/config/database/route checks after that restart;
   then final Codex IAB validation follows the completed implementation. The
   exporter is a separate Deployment and security scope; it is not silently
   included in this app cutover or described as patched by this OS derivative.

Only source/metadata preparation was performed here. No writer stop, backup,
new reader, build, scan, derivative adoption, API login, DNS mutation, restart,
notification or live application acceptance is claimed.


## Prepared fixed-vendor data and functional observers

New helpers (source preparation only): `verify-pihole-state.py`,
`pihole-sql-observer.py`, `pihole-schema-contract.json`, `qualify-pihole.py` and
`pihole-functional-observer.sh` under `scripts/migration/`. Root owns reviewing,
freezing and executing them. No reader, baseline, login, rollout or restart was
performed while preparing this source.

Fresh read-only discovery found **9,980,256** `query_storage` rows in an
875,638,784-byte FTL database, and **1,339,185** gravity entries. Gravity's
schema version is20; FTL's is21. A full database RAM copy is unsuitable here.
The vendor's native SQLite `sha3_query()` is available. The observer therefore
uses constant-memory native typed-row hashing in a controlled SQL-only reader,
with an independent operator HMAC over returned digests. No DNS traffic rows,
domain/client values, credentials or query cells leave the reader in its SQL
output. The HMAC key is generated only in operator RAM, encrypted with the
existing pinned age/SSH identity, round-trip authenticated, and retained outside
Git. Config TOML is parsed in operator RAM and only canonical HMACs are recorded;
no plaintext config/key file is written.

### Source-qualified migrations and exact original-data proof

The fixed official candidate is Docker2026.10.0, FTL6.8/Core6.5/Web6.6.1, not the
older OS-only derivative retaining affected FTL6.5. Its pinned primary sources
are FTL commit `29c8b13f4bba0c4f4f47598e45a65cbf1cedac88` and Core commit
`f503a65d3a07cb71fd931389f1d3babf718249aa`.

The public schema contract was derived by applying the exact source migration
to an **empty RAM copy of the original schema**, never production data. Gravity
20->21 reconstructs four keyed tables as WITHOUT ROWID, adds two group indexes,
changes two update triggers and four view ordering clauses, and advances the
version property. FTL21->22 replaces only the `queries` view and version property.
Every old table/column/value remains in the data projection, ordered by explicit
columns or indexed primary keys. No implicit rowid preservation is assumed.
The controller requires the complete exact expected new schema and typed old-row
digests, including all gravity entries, rules/groups/client mappings, aliases,
users' history and lookup dictionaries. Original query/dictionary rows are
checked through their fixed original maximum IDs. New IDs are measured
separately. After a controlled restart, the initial live checkpoint's additional
query/dictionary rows must also remain, with their exact typed digests.

Only source-proven runtime changes are admitted and counted: cumulative counters,
latest-query timestamp, network last-query/count, address last-seen/resolution
clock/name and sequences. Network identity/hardware/alias fields must match;
original address identities must remain. Both full-row and projected digests are
recorded, so changed runtime columns are not described as whole-row equality.
Gravity's DROP/CREATE migration removes optimizer-stat rows only for the four
rebuilt tables; those exact removals are counted, all remaining statistics must
match and no blanket statistics exemption exists.

Canonical TOML preserves every old value, including `webserver.api.pwhash`,
headers, DNS upstreams/hosts and **the existing91-day retention policy**. The only
admitted structural changes are the removed `files.pid` when its original value
is exactly `/run/pihole-FTL.pid`, plus source defaults `resolver.macNames=true`
and `debug.performance=false`. A custom retired PID path or another old-value
change refuses. There is no retention override, password reset or broad header
waiver. Static DNS settings, TLS files and retained `gravity_old.db` are separately
HMACed. The complete encrypted original two-claim archive remains authoritative
for all other original files/backups. Full live file/database byte equivalence
is explicitly not claimed.

### Read-only SQL resource and WAL handling

The owned reader uses the original pinned image but explicitly runs a sleeping
command. It has UID1000/GID0 with Strict groups, no added capabilities, NNP,
read-only rootfs/claims, no Secrets/NAS/token/envFrom, and the existing
**500m CPU /256MiB memory /1,800-second lifetime**. SQLite has a128MiB hard heap,
8MiB page cache,1MiB cell/result-length ceiling and bounded900-second execution.
All returned metadata remains within8MiB. No entire DB is copied into RAM.

Original FTL has file capabilities; direct execution with an empty capability
bounding set returned EPERM in a read-only probe. A direct loader probe also
failed. The prepared reader instead copies the exact27,867,849-byte original
binary, SHA256 `771bc4e23aec29eb95969272fbc13ca26a18a13285b9c4cd0078bfcc6f828c22`,
into its own **64MiB memory scratch**, verifies identical bytes and absent file
capabilities, and runs that ordinary unprivileged copy. It changes neither the
image binary nor production capabilities. This copy/read sandbox remains a
pending live proof; source preparation does not establish that it ran.

Main DB files are bound read-only by PVC subPath into that scratch directory.
With a cold zero-writer source and both WAL/SHM absent, SQLite may create its
small derived sidecars only in owned RAM, while the main file remains read-only.
Live FTL requires both real WAL/SHM files bound read-only beside the DB; missing
or incomplete live pairs refuse. Source/bound-file device/inode identities are
checked before and after, and normal read-only WAL transactions are used.
There is no `immutable=1`, checkpoint, VACUUM or journal-mode mutation.
[SQLite's read-only WAL rules](https://sqlite.org/wal.html#read_only_databases)
explain the writable sidecar-directory requirement. Only the owned reader is
UID-precondition deleted after success; failure retains its bounded evidence.

### Nightly retention window

The pinned FTL6.8
[database thread](https://github.com/pi-hole/FTL/blob/29c8b13f4bba0c4f4f47598e45a65cbf1cedac88/src/database/database-thread.c)
selects a cleaning minute10..49 and performs on-disk pruning only during local
hour3 after that minute. It does **not** unconditionally prune at startup.
Starting during that nightly window may immediately prune old queries. On
October25, metadata showed a92.65-day query span with configured retention91;
that difference must not be waived as successful original-row preservation.

Root will preserve91 and finish cutover/initial/restart proofs outside03:00-04:00
in the actual configured Pod timezone. The `window` phase is an explicit
pre-entrypoint check with zero writers. It decodes only the existing benign
native Secret TZ key in RAM, returns no zone value, and binds the unchanged
Secret UID/resourceVersion. Live/functional checks read the actual writer's
local clock, verify its offset against that reference, and refuse if any
03:00-04:00 window opens during capture, including a capture spanning the entire
window. This is a migration observation window, not a promise that the user's
normal91-day retention policy will never delete data in the future. Original
full history remains retained in the encrypted cold archive.

### Exact execution sequence after root review

Use a frozen source tree and private native output directories. Placeholder
paths/hashes are mandatory exact successful receipts, not arbitrary booleans.
No application image is installed by these commands.

```bash
# Optional original API/DNS baseline BEFORE independently stopping the writer:
python scripts/migration/qualify-pihole.py --original --apply --output-dir /home/brajam/.local/share/branconet-migration/pihole-functional-20261025
# Root independently stops through Flux and completes the full cold archive.
python scripts/migration/verify-pihole-state.py baseline --apply --cold-receipt <cold-receipt> --cold-receipt-sha256 <sha> --output-dir /home/brajam/.local/share/branconet-migration/pihole-state-20261025
# Immediately BEFORE first candidate entrypoint, while still zero writers:
python scripts/migration/verify-pihole-state.py window --apply --cold-receipt <cold-receipt> --cold-receipt-sha256 <sha> --baseline-receipt <baseline-receipt> --baseline-receipt-sha256 <sha> --output-dir /home/brajam/.local/share/branconet-migration/pihole-state-20261025
# Root independently adopts the qualified fixed immutable image through Flux.
python scripts/migration/verify-pihole-state.py verify --apply --candidate-image <qualified-image-at-digest> --cold-receipt <cold-receipt> --cold-receipt-sha256 <sha> --baseline-receipt <baseline-receipt> --baseline-receipt-sha256 <sha> --output-dir /home/brajam/.local/share/branconet-migration/pihole-state-20261025
python scripts/migration/qualify-pihole.py --apply --state-receipt <successful-live-state-receipt> --state-receipt-sha256 <sha> --output-dir /home/brajam/.local/share/branconet-migration/pihole-functional-20261025
```

If the zero-replica template already names the qualified candidate, supply that
exact `--candidate-image` to `window` too; it still requires zero writers.
After root's separate controlled Flux restart, repeat `verify` with
`--previous-live-receipt <initial-live-receipt>` and its exact
`--previous-live-receipt-sha256`. Then repeat `qualify` with the new successful
state receipt and `--previous-functional-receipt <initial-functional-receipt>`
plus `--previous-functional-receipt-sha256`. A different writer Pod UID and the
same original workload/storage/Secret bindings are mandatory.

The functional observer creates exactly one own transient CLI API session using
the existing `/etc/pihole/cli_pw` **inside the writer Pod RAM only**, reads six
fixed endpoints, and explicitly deletes that session. It checks unauthenticated
rejection first. It never logs in with the administrator password, so legacy
password-hash upgrades are not triggered merely to prove auth. No credential
enters argv/query URLs/files/reports; curl defaults/proxies/redirect following
are excluded. DNS probes separately verify UDP and actual TCP, disable automatic
UDP->TCP fallback, reject truncated replies, check a public answer and an actual
configured local host (or built-in `pi.hole` when no such host exists).

The actual original ClusterIP is always tested. Add one `--dns-target IP:port`
per **inspected existing** external node route; no node port is invented. The
receipt explicitly reports the external target count and does not claim whole
external-route acceptance from a default internal-only run. A native CLI read
session creates/deletes session state and DNS requests naturally append query
history; neither changes production configuration or normal retention policy.
All source AST/shell syntax, generated SQL preparation and clock refusal controls
are preparation only. Actual reader/cgroup/data/API/DNS/restart and final IAB
acceptance remain root's required execution gates.


## Actual October25 completion checkpoint

Initial and controlled-restart full query/gravity/configuration proofs passed,
with the original password hash,91-day retention, native Secret and PVCs intact.
The restart state receipt SHA256 is
`210bd6f8a101ec2f0d21790f2e5171a6e83b465c990cd852dc90c8024cdaff63`;
restart functional receipt is
`6ee91a6ede804a7c20bf3cb44e176abfd70d7df8b6760b31199a09dbd640d211`.
The final all-node route receipt is
`051ef9ff7c4c7c93b055edbf61432722e05c9882eeb564fcc675bd2542396fd2`:16
UDP/TCP DNS checks, six authenticated reads and six HTTP routes passed.

The initial restart observation correctly refused a disappeared mock ARP row.
Source review of pinned FTL network-table.c established its normal replacement
of the unconfigured `ip-<address>` mock by discovered hardware. A separately
authenticated sparse private RAM view of the original network tables proved all
12 original addresses retained, the sole ID2-to-ID11 reassignment, stable names
and aliases, earliest firstSeen and monotonic counters. Fresh full observation
then passed with that exact narrow correspondence; no old receipt was rewritten.
All other network records, query prefixes, gravity/configuration and identities
remain strict. Whole network-row equality is explicitly not claimed.

The sparse reader allocated1,052,672 bytes under its16MiB RAM ceiling and fully
authenticated the original encrypted archive; it did not materialize the large
query DB or write plaintext to ordinary disk. Its execution closure identity is
`95582b67bea7` (full manifest retained privately). Final IAB remains outstanding;
this backend checkpoint does not close the whole cluster goal.
