# Same-version media security overlay acceptance

Source-only profiles prepared on 2026-10-25; no API, SQL, backup, deployment or restart was executed during this change. The original migration profiles remain the default. Opt in with `--security-patch` on every baseline, after and restart observation. Receipts from different profiles are rejected.

| Application | Required version on both sides | Vendor baseline index | Local after/restart digest |
|---|---|---|---|
| Radarr | 6.4.4.10685 | `fc0ae3c50f8128b97e84381903ec8d6845c3a569641cb7117c124376cccb57c1` | `b79e4e0e3bec790e4f8a48cca83fd5b34e1267f672e27496cf1b95e732fed83c` |
| Sonarr | 4.0.20.3014 | `889dcc58c6aea859033985894b519b2e6b1e55d92527ed123f9f52e42ae7c97b` | `7d297bbadfd74dd2c346b48d32530d6fa632bc902739d4f7aaadbd898375f593` |
| Bazarr | 1.6.2 | `c63aa057947400abded2583f7027d6ac1f8d70a8130401c36d5a244ef5999466` | `bcf9a782f3381b4182bed0985e0d38df79da0218ead2ca47c577595e9dafe21b` |

The complete references and amd64 vendor child digests are fixed in the helpers and frozen `profiles.json`. Local references are `docker.io/library/<application>-security-20261023@sha256:<digest>`. Sonarr's exact vendor recipe inputs and existing accepted observer pin **4.0.20.3014**, not 4.0.20.2946; live observations must satisfy that strict version check.

Radarr and Sonarr apply their existing modern qBittorrent field projection on **both** sides, including the guard that the added API-key field is empty. No new exception permits changed credentials or settings. Bazarr uses its existing modern SQLite/config projection on both sides and accepts no `--vendor-normalization-proof`. The already captured Bazarr `security_patch: true` modern baseline remains usable: its vendor image/runtime and version are unchanged by updating the target local digest. Radarr and Sonarr require fresh security-profile baselines.

Run each API observer on the master using the existing protected HMAC key through stdin. Set `SCRIPT` to the frozen `qualify-<application>.py`, `PRIVATE` to an existing mode-0700 receipt directory outside Git, and `KEY` to the existing mode-0600 key file. These helpers require 64 lowercase hexadecimal key characters (optional terminal newline). Do not pass key material in argv or logs.

```sh
python3 -B "$SCRIPT" baseline --security-patch --receipt "$PRIVATE/baseline.json" < "$KEY"
python3 -B "$SCRIPT" after --security-patch --baseline "$PRIVATE/baseline.json" --receipt "$PRIVATE/after.json" < "$KEY"
python3 -B "$SCRIPT" restart --security-patch --baseline "$PRIVATE/baseline.json" --prior-receipt "$PRIVATE/after.json" --receipt "$PRIVATE/restart.json" < "$KEY"
```

Use new filenames; helpers never overwrite existing receipts. Keep `bazarr-sqlite-observer.py` beside `qualify-bazarr.py`. The owner performs the controlled restart between after and restart; the observer requires a different pod UID or an increased container restart count, then compares again against both prior observations. These commands do not initiate restarts, provider requests, connection tests or login writes.

Before adoption, the owner quiesces the existing writer through the established Flux workflow and captures a fresh complete config-PVC archive using the existing cold helper. Supply the actual confirmed node and permitted reader identity; do not infer them from this document:

```sh
python3 -B "$FROZEN/scripts/migration/cold-application-state-backup.py" "$APP" --generation media-security-20261025 --node "$NODE" --reader-uid "$READER_UID" --reader-gid "$READER_GID" --output-dir "$COLD_OUTPUT" --apply
```

That finite generation pins the vendor images above and preserves the existing original deployment, release and config-PVC UID guards. It never walks NAS claims. Its existing archive authentication, ownership and launch-space guards remain mandatory.

For **Radarr and Sonarr only**, run the full original SQLite Users comparison after adoption and again after the controlled restart. Set `APP` to `radarr` or `sonarr`, `COLD_RECEIPT` to the completed new-generation receipt, and `COLD_RECEIPT_SHA256` to its exact SHA256. Supply the same existing SQL-verification HMAC key on each run; this helper retains its existing raw stdin key semantics and does not hex-decode it. Keep output roots private and outside Git.

```sh
python3 -B "$FROZEN/scripts/migration/verify-arr-sqlite.py" "$APP" --security-patch --cold-receipt "$COLD_RECEIPT" --cold-receipt-sha256 "$COLD_RECEIPT_SHA256" --output-dir "$SQL_OUTPUT" --apply < "$SQL_KEY"
```

The verifier authenticates the complete encrypted cold archive before extracting SQLite inputs to bounded tmpfs. It compares every original Users row, ID, column and credential value by HMAC, retains the original resource/runtime fences and permits no added Users columns in the same-version security profile. Its owned temporary pod mounts only the config PVC read-only and is UID-guarded on cleanup. It does not scale the writer. Bazarr's existing observer separately checks its configured authentication, modern application tables, config and SQLite integrity; no nonexistent Bazarr Users-table claim is added.

Freeze the four modified helpers plus `bazarr-sqlite-observer.py`, `cold-application-state-backup.py`, and `metube_state_backup.py`/`pod_reader.py` under their original repository-relative paths. The latter shared files live in `k8s-rewrite/ansible-playbook/roles/metube_state_backup/files/`. Keep the existing pinned age binary, recipient/identity, SSH configuration and cached reader image used by the shared primitives. The source manifest records exact file hashes; no credentials or data belong in this source bundle.

Source validation consists of Python AST parsing and inspection of the finite image/version/profile mapping. Runtime data, route and integration acceptance remains the owner's next execution stage; the observers continue to report `full_acceptance_complete: false` rather than claiming those additional checks.

## Actual adoption and restart, October25 2026

The local publisher validated private charts commit356ae3a; Flux adopted all
four exact candidates on their original resources and claims. Commitc10ca49
requested the controlled restart. Fresh full encrypted cold config archives
were authenticated before each stateful cutover. Radarr/Sonarr API, native
credentials, complete original SQLite Users rows/columns/values, library and
client settings passed after adoption and again after restart. Bazarr's auth,
configuration, current SQLite tables/integrity and library checks passed twice.
Whoami's original Deployment/Service/Ingress identities/specs and six actual
HTTP replies across three nodes passed after adoption and a different-Pod restart.

Private evidence is under `FBASE/acceptance-<service>-security-20261025` and
`FBASE/control-logs/media-{cold,after,restart}-results-20261025.json`. The frozen
acceptance source manifest is7eaff6c79ddb787ea970941210d9f2739a176ed1f6b9c6ff9387e962ca1c90dd.
Radarr restart receipt5d139973efcc48be2c603c97b65bda231c8f684a7c3e1fc8bab8927fe92b04e6;
Sonarr9f9a74e2606b9e838b1e217b48a293b83cedf4a8e12325bdc185dab313d85d23;
Bazarrcb3d287d572db648b986e281791dc9e878eed61dc2a7a5ea5b99b6a69f7ed78a.
External media HTTPS/browser acceptance remains open; these targeted results do
not assert whole-goal completion or erase residual scan findings.
