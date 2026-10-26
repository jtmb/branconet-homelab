# phpMyAdmin upstream transition

Owner: maintenance chat `01a12045-bf7e-73b3-8557-752d17c72ffd`. All new generated
controls, frozen source, private observations and recovery metadata stay in the
existing authorized F:-backed ext4 root in
[the output inventory](TASK-OUTPUT-INVENTORY.md), under `operator-control`,
`control-source/upstream-phpmyadmin-20261025` and
`upstream-phpmyadmin-20261025`. No build, dependency install or publication of an
image is part of this stage.

Inspect the actual Deployment, Services, native Secret references and official
release metadata before rollout. Preserve all existing workload identities,
environment, resource policy, ports and database accounts. Verify whether the
admin frontend has persistent volumes rather than assuming it owns database
storage. Never stop or change WordPress, its database or its PVCs for this image
transition. Existing database backups and old images remain rollback sources.

Use a fresh before/after/restart comparison of exact runtime image, Secret and
configuration bindings, read-only database authentication/account fingerprints,
and normal HTTP login routes. Keep credentials, cookies and response bodies in
memory only. Any transient test login must be logged out without affecting
other sessions. Publish only reviewed chart changes through private main →
local validation → validated → Flux; do not mix direct Deployment writes.

Regenerate observations using the maintained qualification helper with its
explicit phase and private output directory. Keep immutable receipts and source
hashes. Any recovery metadata is encrypted directly into the existing root,
fully authenticated and copied to the approved NAS recovery folder. Reconcile
all generated scratch before checkpoint completion. Final IAB remains after
implementation; current vendor CVE findings must be reported separately.

Preparation only: no deployment or acceptance is claimed here.
