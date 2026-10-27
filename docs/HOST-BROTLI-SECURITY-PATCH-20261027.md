# Host Brotli security patch — October27, 2026

Actual package/Ubuntu Pro inspection found one available standard security update
on workernode1 (`192.168.0.6`), `libbrotli1:amd64`1.0.9-2build6. Master and worker2
already reported no pending standard security updates. Ubuntu confirms the Jammy
fix for [CVE-2026-111497](https://ubuntu.com/security/CVE-2026-111497) in
1.0.9-2ubuntu0.1 ([USN-8956-1](https://ubuntu.com/security/notices/USN-8956-1)).

The new disabled-by-default `host_brotli_security_patch` role and its separate
playbook apply only that exact signed security-pocket package on the verified
worker1 identity. The real preflight verified the original version, architecture,
Jammy security origin and one-package/no-removal simulated transaction. Actual
Ansible application and its real rerun passed. The first run changed only
`libbrotli1`; the rerun changed no installed package. Before/after full package
inventories, boot ID, running kernel and kubelet/containerd-k8s/SSH process IDs,
start times and restart counters proved continuity. There was no drain, reboot,
runtime restart, Pro attachment or account modification. Three new local receipt
files on the idempotent run are recorded separately from zero production changes.
The existing sudo credential was supplied through a non-echoing terminal into
process memory, then discarded; it is absent from source, argv and receipts.

Afterward Ubuntu reported zero pending standard security updates on worker1.
All three nodes still report five ESM Apps updates in `pending_attach` state:
virtualenv, python3-virtualenv, python3-pip-whl, python3-pip and python3-filelock.
These are explicit unresolved entitlement/security exceptions; no subscription
attachment, account change, removal of user tooling or false clean-host claim was
made. Package availability here reflects the hosts' existing APT/Pro metadata,
not a promise that no later advisory can appear. An unprivileged maps inspection
found no readable Brotli mappings; inaccessible root processes were skipped, so
that observation is not an exhaustive mapped-library audit.

Exact applied source is frozen under
`control-source/host-brotli-security-patch-20261027`; full original/after/rerun
snapshots, source hashes and Ansible logs are under
`host-brotli-security-patch-20261027`, inside the single existing F-backed task
root. Empty controller home/temp directories were removed after process/FD/map/
mount checks; source, logs and receipts remain. No node runtime data was deleted.
Fresh cluster verification at00:39UTC passed three Ready/no-pressure nodes,
57Bound claims, all30HelmReleases, all Kustomizations and all43attached healthy
Longhorn volumes. This host checkpoint does not close remaining platform/image,
client-trust or final browser acceptance work.

Combined checkpoint recovery metadata:2540340bytes,
SHA256`515f5d58d22946cbd1de2087eb6486baa1c8e4053bd17c6d2f96a98c6a4756f0`;
every metadata member and full authenticated NAS read-back passed. Existing
protected recovery-key backup was reused and verified; originals were retained.
