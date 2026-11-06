# Bazarr maintained-image security refresh

This profile prepares the official `ghcr.io/hotio/bazarr` 1.6.2 image at root digest
`sha256:86b76c5c66a839ca6f6dd15ddb16b43f074dc71d41907b720e176bdede4b6562`.
It does not change Helm values, reconcile Flux, restart the app, or accept data preservation.
The complete candidate scan found **1 Critical, 6 High, 7 Medium and no CISA KEVs**;
certifi remains Critical. Four Python critical package rows are fixed. Do not describe this as clean.

## Guarded native prestaging

Controller: `k8s-rewrite/ansible-playbook/roles/bazarr_vendor_preload/files/controller.py`.
Playbook: `k8s-rewrite/ansible-playbook/playbooks/bazarr-vendor-preload.yml`.
The playbook is disabled by default and does nothing in check mode. Enable with
`bazarr_vendor_preload_enabled=true`; mode defaults to `observe`. Select `stage`
explicitly only for the authorized execution. The service is fixed to Bazarr;
node choices are `all`, `master`, `worker2`, or `worker1`.

Direct controller arguments: `observe --service bazarr --node all` or the explicitly
selected `stage --service bazarr --node all`. The controller uses the existing hidden
TTY privilege reader by default. An existing protected pipe/private owned file can
supply a single password line with `--password-stdin`; alternatively use one existing
`BAZARR_PRELOAD_SUDO_PASSWORD` or `ANSIBLE_BECOME_PASSWORD` environment variable.
Never place the password in command arguments, Ansible variables/logs, generated
files or receipts. Ansible invocation has `no_log: true` and accepts the inherited
environment input. Multiple credential sources are refused.

The original `official_vendor_preload` controller is hash-pinned and unchanged.
Its main stage flow, SSH exception codec, node observation, continuity and inventory
checks, native pull, complete before/after records, and per-node non-replay intents
are reused. Remote code is the original program with only the finite Bazarr PINS
assignment appended. The wrapper adds exact candidate evidence and live registry
metadata binding, not replacements for native guards.

Every stage freshly qualifies all three nodes before the first pull. Existing
25% plus 512 MiB and 15 GiB usable-space floors remain. Per-layer compressed,
diffID, chain-parent and unpacked bounds are bound to the streamed measurement.
The complete per-node upper bound is **771,870,091 bytes**: the independently
measured 755,092,875-byte content/unpack bound, including its 64 MiB reserve,
plus the original prestager's 16 MiB metadata allowance. Cached, verified chains
may reduce missing bytes; no earlier image/content/lease/snapshot may disappear.
Native pulled artifacts are required for this exact release and its rollback
retention; there are no controller image archives or dependency copies.

All controller receipts remain under the existing F-backed root's
`platform-upstream-review-20261027/autonomous-hardening-20261028/bazarr-prestage`.
`approved-metadata.json` and `prepared-source-review.json` bind the exact root,
amd64 manifest, configuration, scan results and measurement. Existing scan evidence
stays in sibling `bazarr-full-scan`; no retired database paths are recreated.
An uncertain or failed node intent blocks another pull. Use read-only observation
and reconcile the original result; do not remove intents to retry.

## Same-version preservation observer

Use the existing protected-key/receipt harness with `scripts/migration/qualify-bazarr.py`
and both `--security-patch --vendor-security-refresh-20261028`. The new flag rejects
`--upstream-adoption` and disallows vendor normalization. Existing defaults and
other profiles remain unchanged. No key was read during preparation.

The exact transition is old root `32204ef90d4dcb54ad5fb019810f4ef805ced9c54853ae552cf09a41c056b14b`
(runtime `8696d2b429f88dcb8049357be3d24c12e6c79a3aaa9c063ac7107d59914434e5`)
to new root `86b76c5c66a839ca6f6dd15ddb16b43f074dc71d41907b720e176bdede4b6562`
(runtime `ff7b10937c15036b011b33b1d524b92ead2415564bf1ab5415268b915d4b71f9`).
Deployment image references retain the existing `ghcr.io/hotio/bazarr:latest@sha256:` form.

Capture `baseline` before the release, then `after` against that baseline, then
`restart` against the same baseline plus the accepted after receipt. Original
identity, PVC/service, SQL quick-check, API, subtitle, semantic-row, config-leaf,
foreign-key and runtime-stability assertions remain. Baseline/restart receipts must
carry the same new profile flag; historical normalizations and baselines are untouched.
These observations do not themselves claim external route or full workflow acceptance.

Preparation validated Python syntax, YAML structure, live immutable metadata,
negative profile selections, and AST parity for every non-main observer function
and every pre-existing named observer guard. No image pull, cluster mutation,
production observer run or credential read was performed during preparation.

## Controller-only RAM observer transport

`run-bazarr-vendor-observer.py` is the prepared carrier for the profile above.
Use `--mode baseline|after|restart`, an absolute new `--receipt` path under the
existing F root's `autonomous-hardening-20261028/bazarr-observation`, and exactly
one of `--key-file` (the existing owner-600 key file) or `--key-stdin` (a protected
pipe or owner-600 file). `after` requires `--baseline`; `restart` additionally
requires `--prior-receipt`. Do not create a new key or put key bytes in arguments.

The carrier pins the complete local qualifier and SQLite/API observer bytes.
Public code and hashes plus the existing key travel only in authenticated SSH
stdin. The remote bootstrap keeps sources in RAM, invokes original identity
before/after the actual observer, and returns sanitized identity and observation.
It creates no node source or receipt files. The optional `reader_source: bytes`
argument preserves the default file-backed behavior and checks immutable bytes
and the observer SHA after execution.

On the controller, unchanged main-function argument and finalization statements
are compiled from the pinned qualifier AST. Original `protected_file` checks read
actual baseline/prior files on the controller; there is no virtual-file override.
Source and prior-file identities/hashes are fenced across the remote observation.
Original `write_new` saves the final private receipt only after all checks pass.
No normalization exceptions are introduced. Receipt flags still report external
route, integration and full workflow acceptance as incomplete.

The public synthetic transport control proves default/injected-source command
and result parity, rejection of mutable/substituted source, original baseline/
after/restart comparison behavior, and negative data/key/service/profile/restart/
permission checks. Its temporary fixtures were removed. These are transport and
preservation-logic controls, not a production SQL/API observation, rollout, or
browser acceptance. Root review and an actual observation remain separate steps.

## Verified scan and native prestage checkpoint

The complete scan receipt is bound to results SHA256
`24dd3da1c7069beee4fb6c4f003d21c6e49ecc0417829b4007ef13786cb84110`
and receipt SHA256
`c0308f9314aee62d8621f61196321ba8e367af1c5462ea101c4f56df29b7cdb4`.
It used the October 29 01:22 UTC vulnerability feed and October 29 01:08 UTC
Java identification feed without suppressions. Findings remain 1 Critical,
6 High and 7 Medium; there are no CISA KEVs. The scan's security acceptance flag
remains false. Database/analysis bulk was retired after verification; exact
sources, hashes, manifests, results and cleanup receipts remain.

Native prestage receipts for master, worker2 and worker1 are all accepted and
fully cached. Each confirms prior native records, service/boot continuity,
measured budgets and disk floors were preserved. The receipts are
`bazarr-prestage/bazarr-{master,worker2,worker1}-result.json`. This establishes
native image availability only; it does not establish application rollout or
workflow acceptance. The earlier protected-input failure remains preserved.
Its transport adapter now consumes protected input into bounded RAM before
inherited-stdin SSH checks and returns the value once.

Pinned source facts at this checkpoint:

- Prestage controller: `3821abb39e43248c998af39431f06ba8cae048d097504b815d6344782dc5ff78`
- RAM carrier: `200ef3eec7d26577b63bc5d065873f3e40fbd661080cb2382067800d09fd1b87`
- Qualifier with optional RAM reader: `c6f264ff1a38663edd46af2918715dfce8e116ac51e0ae3dcfecf300e37e7ba7`
- Unchanged SQLite/API reader: `b010865bc00cf909bb74a9bfbb18625f5a5aae632eade28385360addd7ce8728`

The controller-side baseline receipt is present for the original `32204...`
image and the exact new preservation profile. After/restart checks and application
acceptance belong to the coordinating rollout; this checkpoint makes no claim
about their completion. Independent source review found no preservation-check
gap: original non-main functions other than the allowed observer injection are
unchanged, all original named guards survive, and main comparison/receipt
statements are reused without protected-file virtualization. See
`bazarr-observation/preservation-source-review.json` for the review scope and
`transport-parity-control.json` for the synthetic controls.
