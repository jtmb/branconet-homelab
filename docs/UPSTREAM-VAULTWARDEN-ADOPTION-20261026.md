# Vaultwarden maintained upstream transition

Owner: migration chat `01a12045-bf7e-73b3-8557-752d17c72ffd`.
Status: preparation; the existing derivative remains the running writer.

The live binary and [current stable upstream release](https://github.com/dani-garcia/vaultwarden/releases/tag/1.37.4)
are both 1.37.4. Evaluate the official Debian and Alpine artifacts against the
same pinned current advisory inputs; select and qualify an immutable maintained
artifact without building or patching a third-party image. The vendor artifact
also owns its web-vault packaging. Preserve all native environment/credential
values and review the published startup behavior before adoption.

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
