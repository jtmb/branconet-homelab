# xTeVe original-state and HTTP acceptance

`scripts/migration/qualify-xteve-state.py` observes only `/root/.xteve` and
`/config`. It never walks `/iptv`, opens a provider stream, logs in, requests an
update, scales a workload or restarts it. It uses the existing strict WSL SSH
connection, the master kubectl context and `tar` in the existing xTeVe container.
No Python installation, temporary Pod or plaintext configuration export is
needed. Tar bytes are streamed through master RAM; only HMAC receipts return to
the controller. Regular files are read in bounded chunks, not retained together
in memory. Parsed system files have a 32 MiB limit; each complete tree has a
4 GiB/4096-entry limit. Symlinks are recorded without traversal; hardlinks and
unsupported types refuse observation.

The authorized original baseline passed on October 25:

- Private receipt: `FBASE/acceptance-xteve-20261025/baseline-attempt-01.json`.
- Receipt SHA256: `6868f2620a8d88b64e31ab41b136b4baa401782de5faa5066707439b752dde78`.
- Original observer SHA256: `32f6530f0a2f84d18d849dbc9eda257101ab962c85512c60cb8c3f107a701308`.
- `/root/.xteve`: 42 entries, 138,529,487 regular-file bytes; `/config`: 4 entries,
  3,264 bytes. All original files, owners, groups, modes, kinds and content are
  covered. Authentication/user-account bytes and UUID/mapping values are HMAC
  protected; no raw credentials or provider URLs enter receipts.
- 108 mappings, 29 active. Discovery, device XML, lineup status, lineup, XMLTV
  and M3U returned HTTP 200. `/api/` returned the source-correct 423 because
  `api=false`; this is not a claim of an enabled API or a successful login.
- One raw generated-cache rewrite occurred during the approved read GETs;
  complete semantic comparison and every other file check passed. The receipt
  retains before/after raw HMACs and changed-path HMACs, not a byte-equality claim
  for that rewritten cache.

`FBASE` is the already approved mounted ext4 task-output root
`/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025`.
Reuse its owner-only `acceptance-xteve-20261025` directory and existing
`hmac-key` (0600). Feed its 64-hex-character value through stdin, never arguments
or environment. Output receipts are new 0600 files, HMAC-authenticated and
outside Git. The original baseline source is retained beside the receipt as
`observer-baseline-32f6530f.py`, reconstructed and verified against its exact
hash. The successor adds cold-before-updater and baseline anchoring checks.
AST comparison verified that only `main` and `read_receipt` changed: all node,
tar, file and HTTP interpretation functions are identical. This exact earlier
hash is the sole allowed earlier baseline revision; archive primitive hash and
upstream commit must still match. Attempt02 correctly refused while the writer
was quiescing and remains preserved as a failure, not a replacement baseline.

## Execution sequence

The coordinator owns every pause, boolean edit, deployment and restart. Use the
two existing generic cold scopes, `xteve` and `xteve-config`, sequentially while
the same original writer remains quiescent. Both use workernode2, Strict UID/GID
0:0, all capabilities dropped, and preserve the source roots at 1000:65534/0755.
Both local-state claims must have no active consumer. SMB claim/PV identity is
checked but never mounted. The second scope archives `/config`; its receipt
explicitly distinguishes source alias `data-1` from archive root alias `data-0`.

Run the acceptance helper on WSL with the persistent HMAC key on stdin:

1. `baseline --receipt NEW_BASELINE` observes only the exact original image.
   The successful baseline above already exists; do not resume a writer solely
   to replace it.
2. `cold --baseline BASELINE --cold-state-receipt STATE_RECEIPT
   --cold-state-sha256 STATE_RECEIPT_SHA256 --cold-config-receipt CONFIG_RECEIPT
   --cold-config-sha256 CONFIG_RECEIPT_SHA256 --receipt COLD` fully authenticates
   both complete encrypted archives using the existing pinned age/shared reader
   primitives. A second authenticated pass computes every file's preservation
   record entirely in RAM. Both cold trees must match the original baseline,
   and the archived updater boolean must still be true. Do this before the
   coordinator changes that one boolean.
3. After the separately reviewed candidate rollout, use
   `after --baseline BASELINE --cold COLD --receipt AFTER`. Require exact
   `docker.io/library/xteve-security-20261023@sha256:0ab77160ccccaf9235dcb3864624440551d6dd63c771cfaf97094db869a28656`
   in both the Deployment and observed runtime. Require `xteveAutoUpdate=false`.
4. After the coordinator's controlled restart, use the same arguments with mode
   `restart --previous-after AFTER --receipt RESTART`. Require a changed Pod UID
   or increased restart count, the same candidate image, the same original
   baseline/cold anchors, and repeated complete file/identity/HTTP comparisons.

## Exact comparisons and limits

The helper pins Deployment/HelmRelease, three PVC/PV bindings, node, Service and
Native Secret identities. It HMACs the complete native Secret data in master
RAM. Deployment specs are compared apart from the reviewed image and restart
timestamp; the actual HelmRelease spec has no invented `values.image` field.
PVC/PV/Service specs remain compared. The only admitted extra Pod volume is the
exact standard service-account projection (token/CA/namespace) and its read-only
mount; its contents are never read. The Pod must belong to the original
Deployment and be the only active consumer of either local state claim.

Every file retains its raw HMAC and metadata. Exact-byte comparison is the
default. Narrow source-proven representation rules are:

- `settings.json`: complete JSON equality except **only** `xteveAutoUpdate`.
  Baseline/cold require true; after/restart require false. UUID, credentials,
  authentication settings, providers, filters, counters and every other field
  remain compared.
- `xepg.json`, `urls.json`, `pms.json`: complete JSON equality, permitting only
  object serialization order/whitespace. No mapping or stream record is dropped.
- Generated `data/xteve.xml` and `.xml.gz`: complete XML data, allowing Go-map
  iteration order of root channel/program elements and gzip representation.
  Programme dates, content, channel identities, attributes and child order stay
  compared. There is no generic timestamp exclusion.
- Generated `data/xteve.m3u`: retain every line and stream ID; canonicalize only
  its single generated HTTP origin in the two XMLTV header URLs and validated
  `/stream/<32-hex-ID>` URLs. Provider playlist files remain exact bytes.

These rules follow pinned commit
[`0e999b85…`](https://github.com/xteve-project/xTeVe/tree/0e999b85b9c77c3fdcfcfaf5e96150523fd4481b):
[`system.go`](https://github.com/xteve-project/xTeVe/blob/0e999b85b9c77c3fdcfcfaf5e96150523fd4481b/src/system.go),
[`xepg.go`](https://github.com/xteve-project/xTeVe/blob/0e999b85b9c77c3fdcfcfaf5e96150523fd4481b/src/xepg.go),
[`m3u.go`](https://github.com/xteve-project/xTeVe/blob/0e999b85b9c77c3fdcfcfaf5e96150523fd4481b/src/m3u.go),
[`hdhr.go`](https://github.com/xteve-project/xTeVe/blob/0e999b85b9c77c3fdcfcfaf5e96150523fd4481b/src/hdhr.go) and
[`webserver.go`](https://github.com/xteve-project/xTeVe/blob/0e999b85b9c77c3fdcfcfaf5e96150523fd4481b/src/webserver.go).
Lineup GET rewrites `urls.json`; M3U GET rewrites the generated playlist.
These ordinary cache writes were explicitly authorized. API `status` is used
only when the existing API is enabled without authentication; no login/token
generation or update command is requested. HTTP errors expected from existing
disabled/authenticated surfaces are recorded accurately, not treated as content
success. No returned streaming URL is opened.

**Concrete remaining startup boundary:** the original `files.update` is true.
[`config.go:205-241`](https://github.com/xteve-project/xTeVe/blob/0e999b85b9c77c3fdcfcfaf5e96150523fd4481b/src/config.go#L205)
can refresh provider files and create an automatic backup on startup. New backup
files, changed provider bytes/counters, changed dummy-guide programme dates or
deleted mappings therefore fail the current strict comparison. They are not
silently excluded because they are generated. Preserve the complete cold
archives and inspect a concrete difference before extending any rule; no
additional application setting is changed by this observer.

Passing these observations does not prove personal login, external TLS/routes,
provider streaming, media playback, or restoration. Keep the independent media
fixture and cold/data/controlled-restart evidence separate. Focused synthetic
checks covered tar parsing, updater-only normalization, UUID-change detection,
XML order and generated-origin handling; actual baseline success is recorded
above. Cold/after/restart were not executed by this worker.

## October 25 final cold/after/restart result

The complete authenticated original config archives remain. Root inspected and
implemented only the concrete source-proven startup changes: each existing
provider refreshes its download/error metadata, dummy-guide dates/programmes
refresh while all663 channel identities remain, and backup.keep10 rotates the
oldest ZIP before creating one new timestamped backup per startup. New archives
are CRC/member/config verified; the old rotated ZIPs remain in the cold archive.
No provider identity, URL, UUID, account/authentication field, mapping or stored
credential is excluded. Only the authorized auto-updater Boolean changes.

The final observer SHA256 is
`87da06727ed0dd31a4bc1272d8a2c580583e8241d05cf884236852e463e0b38b`.
`cold-r2.json`, `after-r2.json` and `restart-r2.json` under
`FBASE/acceptance-xteve-20261025` passed. Restart receipt SHA256:
`700e860de046ce52464af30f8ccbf39c7592db3e02d00b2409a1412b402074c3`.
Original native Secrets, all three claims including the untouched SMB binding,
Service,108 mappings/29 active mappings and six HTTP surfaces are preserved.
The disabled API correctly returns423; no enabled-API/personal-login claim is made.

The configured FFmpeg fixture separately passed100 real decoded frames with
H264 video preserved and AAC converted to stereo48k AC3. Earlier full VLC
failures remain recorded; no VLC acceptance is claimed. Final browser/external
TLS and actual provider streaming remain separate checks.
