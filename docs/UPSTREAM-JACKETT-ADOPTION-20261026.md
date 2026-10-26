# Jackett maintained vendor transition

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

Preparation only; no Jackett deployment or security acceptance is claimed yet.

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
