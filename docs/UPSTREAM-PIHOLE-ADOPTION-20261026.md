# Pi-hole maintained upstream transition

Owner: migration chat `01a12045-bf7e-73b3-8557-752d17c72ffd`.
Status: preparation; existing DNS writer remains unchanged.

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
