# Unpackerr upstream transition

Owner: maintenance chat `01a12045-bf7e-73b3-8557-752d17c72ffd`.
All generated controls, observations, frozen source and encrypted backups for
this stage stay in the existing F:-backed ext4 output root documented in
[the output inventory](TASK-OUTPUT-INVENTORY.md), under
`operator-control` and `upstream-unpackerr-20261025`. No new output root,
dependency tree, build or image publication is authorized by this stage.

Select the maintained official Unpackerr release after inspecting current vendor
metadata and actual cluster identities. Preserve the original Deployment,
HelmRelease, Longhorn configuration PVC, SMB downloads PVC, native Secret,
settings, resource policy and existing downloads. The old custom image remains
rollback evidence; it is not rebuilt or promoted as the maintained target.
Vendor versions, digests and any remaining security findings must be explicit.

Before rollout, capture a fresh bounded configuration/identity/integration
baseline, quiesce only this writer through private charts → local validation →
validated → Flux, authenticate the entire encrypted configuration backup and
verify its NAS copy. Resume with the reviewed vendor digest, then compare
configuration, identities, Arr integration and restart persistence. Do not
archive or walk the SMB media corpus. Final IAB remains a separate end-of-goal
gate after implementation.

Maintained regeneration commands are the committed qualification helper and
cold-backup helper with their explicit finite upstream profile; exact commands,
frozen source hashes and actual results will be recorded before execution.
Backup archives, keys, unique receipts, failure evidence and rollback sources
remain protected. Any disposable fixture outputs require exact regeneration,
inactive-reference and source/evidence checks before cleanup.

This document describes preparation; it does not claim deployment or acceptance.
