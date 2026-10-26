# Pi-hole maintained upstream transition

Owner: migration chat `01a12045-bf7e-73b3-8557-752d17c72ffd`.
Status: maintained upstream data/DNS/API/routes/restart accepted. Final IAB,
remaining application transitions and broader security/publication gates remain open.

The official current stable Docker release is 2026.10.0, with FTL v6.8, Web
v6.6.1 and Core v6.5. Fresh live observation also reports FTL v6.8. Evaluate
the exact official registry artifact without building or patching it:
`docker.io/pihole/pihole:2026.10.0@sha256:d34134716fc32038b052a8674c7c6879e0ff21f0e6d8af345166fffa2c27c113`.
Its amd64 manifest is
`sha256:d8d848307ffe7f8c4b42be423b33295d6a45282215eb5a96fe25e05fa39b1abc`.

Reuse only the existing F:-backed root, ext4 UUID
`3c792469-ea0e-4a2c-98e8-1185b141607b`, backing file
`F:\branconet-build-storage\native-build-20261025.ext4`. Public metadata and
source controls use `operator-control`, pinned scan inputs/results reuse
`security-review-20261026`; any new application recovery state will use
`upstream-pihole-20261026`, with exact executed sources in
`control-source/upstream-pihole-20261026`. Set scratch/cache environment there
and enforce capacity guards before each download. No second root, GitHub Actions,
local deployment-image archive or new publication route is authorized.

Retain the original retry1 claims, all query history, gravity/configuration,
password and DNS settings, native Secrets, ports, resource bounds and other
recovery/failure sources. The approximately 876-MB live FTL database and 83-MB
gravity database are current metadata observations, not authenticated backups.
Review startup behavior and full current schema/configuration before stopping
DNS. Use the existing two-claim cold archive and local validation → validated →
Flux delivery path, with exact current-image guards. Require complete encrypted
backup and NAS read-back before adoption; preserve logical query rows and check
only source-proven runtime bookkeeping changes. Verify DNS TCP/UDP, actual
authenticated application reads, routes and a distinct restart without replacing
the password or silently changing DNS upstreams. No personal login or final IAB
acceptance is inferred from a Ready Pod. Cleanup and exact retained exceptions
are required before this checkpoint is accepted.

The unsuppressed vendor scan completed successfully with 0 Critical / 13 High /
4 Medium / 44 Low / 2 Unknown findings. All 13 High package rows have fixes
absent from this published artifact; they remain open vendor findings. The CISA
KEV intersection is empty, which does not establish absence of unknown flaws.
No private rebuild or live package patch substitutes for the maintained image.

Fresh original checks passed FTL v6.8, six authenticated read operations, own
CLI-session logout, 16 TCP/UDP DNS probes (internal and all three published node
addresses), unchanged native Secret/storage/resource bindings and 27 web routes.
The actual host is `pi.branconet.lan`; `/admin/` redirects to `/admin/login`,
and anonymous `/api/groups` access is unauthorized. Initial observer assumptions
about the root response/hostname were corrected against the actual source/live
routes; both original frozen sources and failure diagnostics remain.

The first same-release schema check identified a historical contract omission:
the original gravity database already has
`CREATE INDEX idx_antigravity ON antigravity (domain, adlist_id)`. Complete live
schema/column inspection confirms this is the only difference from that older
contract. Both exact current/new schemas now require that index; no schema-change
exception is introduced. Original failed source, receipt and reader diagnostics
remain. Only its UID-bound temporary reader was deleted after capturing evidence;
the copied SQL executable was tmpfs-only and both source claims stayed read-only.
The pinned original official SQL CLI remains an isolated diagnostic tool, with
no app entrypoint, token, credentials or network API and unchanged resource bounds.

## Complete original baseline and native startup records

The full two-claim archive contains 85 files / 1082678613 original file bytes.
Ciphertext: 1083042148 bytes, SHA256
`b5337c5e925e224349c2e109dd151b0bc9ad37f0077a4fcda1699e5be4bcc877`.
Complete NAS read-back and age authentication passed; originals remain.
The exact cold baseline includes gravity schema 21, FTL schema 22,
9069270 query records, 1337044 gravity entries, nine adlists, the original
group/domain settings and all 166 canonical configuration entries. The existing
91-day retention setting remains; preserving old history is not waived.

The first live comparison preserved every original query and all configuration/
static-file hashes, but correctly refused to equate two native startup records.
Full authentication of the original archive and a private read-only original DB
projection established exactly one already-expired API session and one
`RATE_LIMIT` diagnostic. The complete records remain in the cold archive; no SID,
CSRF value, address, user-agent or diagnostic payload was printed or replayed.

[FTL v6.8 session restore](https://github.com/pi-hole/FTL/blob/v6.8/src/database/session-table.c)
prunes expired sessions and clears their disk persistence after restoration.
[Its message flush](https://github.com/pi-hole/FTL/blob/v6.8/src/database/message-table.c)
clears run-scoped diagnostics while retaining `TELEPORTER_SKIPPED` messages.
The new observer admits only these two authenticated original records, pinned
vendor-source hashes, exact baseline/ciphertext/source identities, original
counts/IDs and observed expiration. Every other table, original query prefix,
typed digest, schema/configuration and native identity predicate remains strict.
No user password/account setting was replaced; diagnostic/session-row equality
is not claimed. Future unexpected differences still refuse acceptance.

For this investigation, one regenerated 875638784-byte original DB input uses
`upstream-pihole-20261026/cold-runtime-source/pihole-FTL.db` under the declared
F:-backed root. Its SHA256 is
`663b2ba82ce151ff531ab2ff1d761f3e10c1e8ae1626b07f2c3e754bd79c8cd9`.
It is a temporary, reproducible archive projection, excluded from the metadata
archive to avoid duplicating history. Reconcile it after the restart proof;
retain the original ciphertext, typed proof, sources and every failed generation.

## Accepted checkpoint, October 26 15:03 UTC

Private main, validated and live Flux are
`78e1d1f902178c0a1e64faa54599610aafd3a671`. Adoption revision was
`09faa677106d699b6c505056572487a3bcfe90f5`; the protected pause was
`0988ef956de33afe78bacee8b886addcbf246689`.
The adopted writer UID `2d904da6-fc28-4750-8c15-7eeae594dfa8` and distinct restart
writer UID `9c46d1e9-2406-488c-974d-90fa488cbb74` passed the exact vendor runtime
digest, original native Secret UID/resourceVersion/type/value fingerprints,
complete normalized workload/resource/storage/service/ingress bindings, 27 web
routes, six authenticated API reads with own-session logout and 16 TCP/UDP DNS
checks across the internal service and all three published node addresses.

Every original query remains. Counts progressed from 9069270 to 9069518 after
adoption and 9069623 after restart; both the original prefix and initial live
checkpoint typed digests passed. Gravity/FTL schemas 21/22, all retained user/
configuration rows, 1337044 gravity entries, nine adlists, canonical configuration
including the original password hash and 91-day policy, static settings/TLS/
backup-file hashes and original claims remain. Native counters, network/resolver
bookkeeping and new query rows advance under the declared source checks. Only
the exact original expired session and run-scoped warning follow the proven
native startup retirement above. Their complete originals remain recoverable.

Both the 1083042148-byte cold ciphertext and distinct 2028212-byte recovery
metadata ciphertext passed complete NAS read-back and age authentication.
Metadata SHA256:
`1521a63a29f3f0bd2b1cf4bf282618253f92785038e15daa83e190880bf4cc62`.
Exact executed source generations, verification keys, complete typed acceptance
and every failed observation are retained; ancestor cold data/public feed
binaries were not duplicated into metadata. The regenerated DB input is now
removed safely. Before rerunning the dated verifier, recreate it with the
source-pinned `operator-control/regenerate-pihole-runtime-source.py` command;
the original archive and proof receipts are never overwritten.

At 14:58 UTC all three nodes were Ready without pressure, 55 PVCs were Bound,
all 34 HelmReleases/Kustomizations were Ready, no Deployment/DaemonSet was
unavailable, and 41 attached Longhorn volumes were healthy. The two earlier
failed Seerr diagnostic Pods remain protected. The complete running-image owner
inventory covers 91 Pods, 296 controllers, 68 main/init/ephemeral references,
33 charts and 34 releases. Five application derivative transitions remain:
Plex, qBittorrent, Ruckus database, WordPress and xTeVe.

Cleanup removed **1408999424 allocated Linux bytes**, preserving original Git
source, pinned runtime tools, all source/failure/recovery evidence and original
production data. The first scratch safety check retained everything on finding
SQLite sidecars; reconciliation proved an empty WAL, a transient shared-memory
index, an unchanged authenticated original DB and no active references before
removal. The failed check remains recorded. [Exact paths, regeneration and all
retained exceptions](TASK-OUTPUT-INVENTORY.md#pi-hole-checkpoint-reconciliation-october-26-1503-utc).
No Windows recovery, shutdown, compaction, blanket pruning, GitHub Actions or
third-party build/publication is claimed. The root PR remains draft/unmerged.
The 13 High vendor findings, broader platform/fleet security, owned publication,
existing untrusted ingress TLS and final IAB remain open. The full goal is active.
