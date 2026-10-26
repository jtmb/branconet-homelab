# Jackett maintained vendor transition

**Accepted backend/state/restart checkpoint, October 26 03:47 UTC.** Private
charts main/validated/live Flux reached
`fd0b167de8923e46aeeccece5a783522e65fef90`. Official Jackett 0.24.2910 is Ready
on new Pod `d924b2fc-42e6-481f-88bd-bfb8e5f8e73e`. All 27 protected files,
six configured indexers, authenticated capabilities, nine routes, native Secret
content/identity, resource settings and original PVC/PV identities passed.
Original `UpdateDisabled=false` and effective `--NoUpdates` remain unchanged.
The 1337x torrent-first / magnet-fallback preference now survives startup.
Final browser acceptance and whole-fleet security acceptance remain open.

| Recovery evidence | Authenticated encrypted bytes | SHA-256 |
| --- | ---: | --- |
| Complete original claim, 39 files / 24001474 plaintext bytes | 24049588 | `67e9e213461bfc47ab1ad4d5e29e6ba75cddbe05afbc214130b6e227b7e191f5` |
| Changed 1337x file captured before repair | 2555 | `da75f26dfe1345687e4e664eb86eb44478604b1a99e981c9f762b2c453d7039e` |
| Final recovery metadata, frozen sources and failed observations | 655716 | `25b3c0471568de55c55fcd67f11c7935d4982384b6907ba5699d887c8a6c05e0` |

All three archives passed complete NAS read-back and age authentication; source
originals and recovery identity remain. Final restart receipt SHA-256 is
`643b7d246edb881ccd302923701d348f1a8ba630d7192dc2a40ac4ffff5e5d6d`.
The final health check found three Ready nodes without pressure, all 55 PVCs
Bound, all 34 HelmReleases Ready, no unavailable Deployment/DaemonSet, and all
41 attached Longhorn volumes healthy. Two pre-existing failed Seerr diagnostic
Pods remain retained as failure evidence.

The repaired configuration's second comparison failed on vendor display labels
and option descriptions, rather than choice values. Both pinned definitions and
actual saved shapes were inspected. Observer generation 5 requires the exact old
or exact new labels, type and complete option map before canonical comparison;
it never discards arbitrary attributes. All 27 files and metadata matched, and
a reversed-choice negative control failed as required. Both earlier failures,
source generations and original baseline remain. Exact proof is
`operator-control/jackett-r5-schema-comparison-proof.json`; observer source hash
is `d618b50ad4cdcb234d4459d8abd944f16780194c05e97d7852e28977b263b6d6`.

Current vendor security exceptions remain 2 High / 2 Medium / 44 Low finding
rows, including two curl/libcurl rows with an upstream package fix absent from
the image. No bespoke third-party rebuild or runtime patch was introduced.
Checkpoint cleanup removed **290816 allocated Linux bytes**, with all protected
input hashes unchanged. [Exact paths and retained exceptions](TASK-OUTPUT-INVENTORY.md#jackett-checkpoint-reconciliation-october-26-0347-utc).

Owner: maintenance chat `01a12045-bf7e-73b3-8557-752d17c72ffd`. Reuse the same
F:-backed output root in [the inventory](TASK-OUTPUT-INVENTORY.md). Stage paths:
`upstream-jackett-20261026` for observations/key/complete cold archive,
`control-source/upstream-jackett-20261026` for immutable source/manifests,
`operator-control` for controls and receipts, and the existing
`security-review-20261026` for bounded scans/current verified inputs. No additional
drive/root, dependency installation, image build or publication is introduced.

Live registry inspection binds version 0.24.2910 and `latest` to official
LinuxServer index `19d90927b95397f2d1364e4999e11456abdbbb382b54cd765fc3b3da24d7088b`,
amd64 `c7089eab050a2bbd6b71c33030c7fe7f560c93e50ec07029164a15a8200557f6`.
The existing chart already sets `AUTO_UPDATE=false`; the exact published vendor
source selects `/app/Jackett/jackett --NoUpdates` for that setting. Preserve it,
the native Secret, entire original Longhorn state, API/admin identity, configured
indexers/protection files, resource settings and routes. Vendor source and OCI
metadata hashes are in `operator-control/jackett-current-vendor-inspection.json`.
[Vendor configuration](https://docs.linuxserver.io/images/docker-jackett/).

Before adoption: observe the current custom image, authenticated native Torznab
capabilities, complete configuration and original resource/Secret identities;
review the fresh verified-input vendor scan; quiesce only Jackett through Flux;
capture/authenticate its complete claim and NAS copy. Then adopt the maintained
version/digest through private local validation → validated → Flux, repeat state/
API/routes and different-Pod restart checks, authenticate recovery metadata and
reconcile exact owned inactive cache/scratch. Final IAB remains after implementation.

Regeneration uses the recorded immutable qualification source and exact phase/
Flux revisions, the explicit complete cold-backup profile and existing trusted
scanner in its bounded credential-hidden user unit with read-only database
mounts and complete post-scan hashes. All cache/temp paths stay inside the root.
Retain source, locks, keys, archives, failures, original feeds and rollback data.
Four named rotating anti-bot cookie values on three public no-login indexers
retain their existing narrow comparison contract; no account credential is
omitted. Cold backups include all bytes, including logs/cache and those values.

The preparation history below is retained; the accepted deployment checkpoint
above supersedes its earlier preparation-only state. Security acceptance remains open.

The reviewed baseline passed on the existing custom 0.24.1440 image: six
configured indexers, 27 configuration/protection files, authenticated Torznab
capabilities and nine published/HTTP/HTTPS UI routes. The stored `UpdateDisabled`
value is false; `AUTO_UPDATE=false` and the actual native `--NoUpdates` process
argument disable updates. Preserve those exact persisted and runtime states.
All ServerConfig fields are now compared canonically, including that value;
the earlier historical helper omitted it. Native Secret content/type/UID/RV,
complete Deployment/PVC/PV specs and Service/ingress identities/specs are compared.

The initial observer incorrectly expected `/UI/Login` to return a final page
directly, then incorrectly required the stored update flag to be true. Both
failed receipts and frozen sources remain; neither changed the cluster. Actual
Jackett redirects through `TestCookie`; the observer now follows at most six
same-origin, same-scheme `/UI/` redirects with RAM-only client cookies before
requiring the real password form. HTTPS retains the explicit existing untrusted
Traefik-generated-default-certificate limitation, never authenticated TLS credit.

The fresh current-image scan completed with read-only DB mounts and full
post-scan input hashes: 2 High / 2 Medium / 44 Low rows, no CISA KEV intersection.
Both High rows are CVE-2026-92392 in curl/libcurl 8.22.0-r0, fixed in 8.23.0-r0
but absent from this vendor image. Result SHA-256:
`9755458e58f8d38c10db5acda78f4b82b24eeb668b76e6035afff0225ee388b8`.
No in-container package patch or derivative rebuild is introduced. The scanner's
first launch failed at namespace setup because its previously cleaned private
temporary directory had not been recreated. Its terminal 226/NAMESPACE state
and journal were retained; recreating those directories and starting the same
unit succeeded. Resource, credential-hiding and database controls were unchanged.

Exact preflight: `operator-control/jackett-transition-preflight.json` binds the
baseline, frozen source manifest, current vendor result and C:/native/node free
space. Cold backup keeps the existing complete 4 GiB / 4096-entry profile, exact
original workload/release/claim identities and UID/GID 1000 read-only reader on
the original pinned workernode2. No other app/profile is changed.

The first adoption passed, but the distinct-Pod restart exposed a real deferred
configuration migration in 1337x. Vendor 0.24.1440 used the saved IDs
`downloadlink` / `downloadlink(fallback)`; 0.24.2910 uses
`primarydownloadlink` / `fallbackdownloadlink` and a new iTorrents selector enum.
The application replaced the old choices with defaults, reversing the original
torrent-first / magnet-fallback preference. All other files and setting values
matched; only the already scoped Cloudflare challenge value also rotated.
The failed restart, field-only comparison and exact old/new vendor definitions
are retained. This failure has not been accepted as a passing restart.

The native settings request with the application key did not return admin
configuration. No credential is reset or forged. The explicit dated
`jackett-config-schema-migration.yml` playbook and `repair-jackett-1337x.py`
instead require the original Flux writer stopped at an exact reviewed revision,
original controller/release/claim/node UIDs and no other claim consumers. A
short-lived non-root, tokenless, resource-limited official Python Pod mounts only
the existing Indexers subdirectory. Capture and authenticate the changed file,
verify its NAS copy, then atomically restore only the two new setting values
derived from the authenticated original complete snapshot. Every other field,
file owner/group/mode and app credential remains unchanged. The adjacent atomic
temporary file is part of this scoped runtime configuration update, not a second
controller output root; retain it on failure rather than sweeping state.
Delete only the helper's exact Pod UID, resume through Flux and repeat on a new
application Pod. The observer compares the two declared ID/enum representations
semantically while still rejecting reversed choices; no baseline is overwritten.
All frozen observer generations and failed observations remain preserved.
