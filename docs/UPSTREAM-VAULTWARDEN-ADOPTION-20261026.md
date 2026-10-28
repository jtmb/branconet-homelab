# Vaultwarden maintained upstream transition

Owner: migration chat `01a12045-bf7e-73b3-8557-752d17c72ffd`.
Status: official upstream backend/data/routes/restart accepted; personal client
login/sync, final IAB and remaining fleet/security gates are open.

## Selected artifact and completed cutover prerequisites

Selected official artifact:
`docker.io/vaultwarden/server:1.37.4-alpine@sha256:19ea2b669945d842dadc3d500f2d6a795866a003330f59a47b9634658bae98bb`;
amd64 manifest `sha256:7d90670a4e2531e752f014e58f7283b9d197847b6f073bf84e99598f49d80ffd`.
The Alpine scan completed against the October 26 advisory database with
0 Critical / 3 High / 3 Medium / 44 Low / 2 Unknown findings. The three High
rows have available package fixes absent from this artifact; they remain open
vendor findings. Its CISA KEV intersection is empty, which does not establish
absence of unknown vulnerabilities. The official Debian variant has 4 Critical
and 77 High findings. No derivative build or package modification is used.

The original binary and web-vault versions, complete native resource/Secret
bindings and 45 routes passed the baseline. Private charts pause revision
`6af0384b9441dfcde381512b1703d3af18befda6` reached validated and live Flux with
zero writers before capture. The complete authenticated cold archive is
358692 bytes, SHA256
`c507a9421c214d19ed88d7a2fe08f96a64511179371db1511c3418352a910a3f`.
NAS read-back matched the entire ciphertext and completed age authentication;
the original and the existing profile-bound recovery-key backup remain.
Cold SQL preflight records 29 tables / 86 rows, one user, 24 encrypted items
and four devices, with every typed cell and the complete schema fingerprinted.
The signing-key file and all non-database entries are included without exclusions.

The same-release observer retains one verified private `state/cold-sql` source
under the declared F:-backed root and reuses it across observations. It does not
reuse the historical acceptance document's `/dev/shm` extraction procedure or
its older additive-schema exception. Source bundle, verification key and
observations require encrypted recovery retention. The reviewed six-resource
render changes only the immutable image and pull policy. Adoption and distinct
restart acceptance remain required before calling this transition accepted.

Adoption revision `aedc12c9f415bbe43a57ce18441686e785bc1b03` reached private
main, validated and live Flux. Actual writer Pod UID
`734bc88c-71ac-40f7-a53e-2958a5c0faae` passed the complete same-release schema,
typed row/cell and non-database file comparison, including original RSA material
and uid/gid/modes. The read-only helper was deleted with its exact UID precondition
after verification. The binary remains Vaultwarden 1.37.4 / Web-Vault 2026.7.0.
All 45 routes passed, public configuration is unchanged, and anonymous sync/profile
requests remain unauthorized. Native Secret UID/resourceVersion/type/value HMAC,
complete normalized workload spec, original PVC/PV identities, Services and
Ingresses match the baseline.

Remaining Alpine High rows are `CVE-2026-111497` in `brotli-libs` 1.2.0-r1
(fixed 1.2.1-r0), and `CVE-2026-92392` in `curl` / `libcurl` 8.22.0-r0
(fixed 8.23.0-r0). These findings are retained in the unsuppressed report.
Existing ingress TLS uses the self-signed Traefik default certificate; route
checks identify that exact certificate and explicitly do not credit trusted TLS.

The live binary and [current stable upstream release](https://github.com/dani-garcia/vaultwarden/releases/tag/1.37.4)
are both 1.37.4. Both official variants were evaluated against the same pinned
current advisory inputs. The maintained Alpine artifact owns its web-vault
packaging; no third-party image was built or patched. The inspected vendor
entrypoint does not recursively change data ownership. Original environment,
credential values and resource/storage settings remain unchanged.

Use the existing F:-backed output root and physical UUID. New protected
observations/key/archives use `upstream-vaultwarden-20261026`; exact sources use
`control-source/upstream-vaultwarden-20261026`; public metadata, scans and controls
reuse `operator-control` and `security-review-20261026`. No second output root,
drive fallback, registry publication or GitHub Actions is authorized.

Preserve the original Deployment, release and Longhorn claim UIDs in
[the application contract](VAULTWARDEN-ACCEPTANCE.md), all account credential/2FA
fields, encrypted items, organization/membership/device/attachment/Send records,
RSA keys, complete non-database files and file ownership/modes. Compare complete
schema and typed original row/cell fingerprints for this same-version transition.
Do not apply the older 1.35-to-1.37 additive-migration exception to current data.

Quiesce only this writer through private charts/local validation/validated/Flux.
The dated Ansible/controller cold profile uses UID/GID 1000 on workernode1 and
the complete four-GiB/4096-entry bound. Require authenticated full cold capture
and NAS read-back before adoption. Verify actual runtime digest, native
Secret/resource/storage bindings, binary/alive/config/web routes and anonymous
authorization boundaries, then repeat data/file/route acceptance on a distinct
restart Pod. Personal login/client sync must not be fabricated or achieved by
resetting credentials or forging tokens. Codex IAB remains deferred until all
implementation is done.

Keep every original backup, failure, source and rollback artifact. Restore only
after quiescing writers and preserving newer complete state; do not overwrite
new vault data as a rollback shortcut. Reconcile generated validation/scan/scratch
outputs after checks finish, with exact paths/bytes and retained safety exceptions.

## Final checkpoint, October 26 14:00 UTC

Private main, validated and live Flux are
`aee71f041ad69e5bf16fb9e2f6f1c55dbebe6f55`. A distinct restart writer Pod UID
`81c6cc43-fbd1-424c-b878-9a630efc3c4e` passed the same complete 29-table / 86-row
comparison, original non-database files/ownership, exact vendor runtime digest,
native Secret/resource/storage identities, canonical public configuration and
all 45 route checks. Both temporary read-only verifier Pods were deleted only
after successful checks. No credentials, account records or signing keys were
replaced, and no personal token was forged or consumed to simulate a login.

Cold archive and the separate 2458404-byte encrypted recovery-metadata archive
passed complete NAS read-back and age authentication. Metadata SHA256:
`c0b41f857699d2ed06a5d90e87e7f35a5f6d43a021ccea087d99d23544584999`.
This preserves the exact sources, verification key, baseline/after/restart
observations and unsuppressed scan reports without duplicating the ancestor
cold ciphertext or public advisory database binaries.

Fresh health: three Ready nodes without pressure, 55 Bound PVCs, no unavailable
Deployments/DaemonSets, every HelmRelease/Kustomization Ready, and 41 healthy
attached Longhorn volumes. Two earlier failed Seerr diagnostic Pods remain
protected evidence. The complete image/owner inventory covers 91 Running Pods,
294 controllers, 68 distinct main/init/ephemeral references, 33 charts and
34 releases. Six application derivative transitions remain: Pi-hole, Plex,
qBittorrent, Ruckus database, WordPress and xTeVe. Broader platform/fleet security,
owned-image publication, trusted ingress TLS and final IAB remain open.

Checkpoint cleanup removed **534106112 allocated Linux bytes** after source,
inode, containment, inactive-reference and regeneration checks. Exact paths,
bytes and all retained exceptions are in
[the output inventory](TASK-OUTPUT-INVENTORY.md#vaultwarden-checkpoint-reconciliation-october-26-1400-utc).
No Windows disk recovery, WSL shutdown, compaction or blanket pruning is claimed.
GitHub Actions was directly verified disabled. The root PR remains draft and
unmerged; this accepted backend transition does not complete the full goal.
