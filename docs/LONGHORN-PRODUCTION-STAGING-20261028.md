# Guarded production image staging

The opt-in `longhorn-upgrade-preload.yml` Ansible playbook and maintained
`run-longhorn-upgrade-preload.py --repository <existing checkout>` launcher now
implement serial staging of the complete thirteen-image reviewed candidate.
All thirteen images are now staged and fully verified on all three production
nodes, from source commit `1a4701b2`. The final comparison preserved all 58 claim
bindings, 44 volume identities, engine/replica identities and fourteen NAS
bindings. Every attached volume retains two healthy actual RW replicas.
Longhorn itself still runs v1.12.1; manager/engine upgrade remains outstanding.

Actual filesystem consumption was 3,838,693,376 bytes on the master,
3,836,723,200 on worker2 and 3,837,292,544 on worker1. Exact results are in
[`evidence/longhorn-production-staging-20261028.json`](../evidence/longhorn-production-staging-20261028.json).
The two empty controller Ansible directories were removed after full Linux
reference and Windows exclusive-directory-handle checks: 8,192 allocated Linux
bytes. Fifteen protected receipt/source files remained unchanged. No Windows
disk recovery is claimed.

Before each node, the action reads its actual Ready/pressure, Longhorn disk,
kubelet filesystem/eviction counters and manual-upgrade/storage controls.
The root worker repeats full public cached-blob hashes and exact committed
snapshot/parent/allocated-usage inspection and recomputes the entire coexistence
budget. The unchanged 25% floor, 512 MiB operating margin and authenticated
64 MiB host-payload budget all remain. The earlier passing dated calculation
does not override the worker's fresh checks.

Each node stages one official digest at a time. A fully verified existing
official cache can supply an additional pinned alias. Otherwise native
containerd 2.4.2 pulls/unpacks directly from the original official registry with
TLS verification, one concurrent download and an amd64-only selection. Pinned
and canonical aliases must resolve to the exact reviewed root digest; every
committed layer chain is verified. The operator does not start containers,
change workloads/volumes, import custom images or prune old images.

The worker uses 512 MiB resident memory, zero swap, one CPU and 96 tasks. Its
result records actual filesystem consumption, final full content/chain checks,
the original runtime PID and boot identity. Global before/after preflight
compares all 58 claim bindings, 44 encrypted V1 volumes, replica/engine UIDs,
fourteen NAS bindings and unchanged controls. Every attached volume must retain
two healthy actual RW replicas. Original unused WordPress data stays unattached.

All disposable controller outputs remain in the existing F-backed task root,
operation `platform-upstream-review-20261027/longhorn-production-prestage-20261028`.
Owner, filesystem, complete 64 MiB metadata/scratch peak, exact output names,
source hashes, regeneration and retained originals are recorded before staging.
Existing lockfile-keyed Ansible dependencies are reused. Privilege input uses
the existing non-echoing TTY/RAM-only mechanism, never argv, environment or files.
CurrentUser Root trust is unrelated to these SSH/native API operations.

Required runtime artifacts go only to the existing production containerd stores;
their concrete consumer is the reviewed supported Longhorn manager/engine
rollout. No node-side build, temporary archive or dependency copy is generated.
Controller Ansible scratch must be reconciled independently after execution.
If observation fails, inspect the actual node unit/handle before treating it as
terminal; never restart solely because a tool wait expired.

Manager/engine execution remains separate, through the existing installation's
kubectl ownership, preserved prepared manifest and recovery gates. The full
tracked goal remains active, including final security/fleet and browser checks.
