# October 28 upstream security checkpoint

This is an incomplete delivery checkpoint. The private chart changes for MySQL
and YTPTube are prepared but are not yet deployed. BORTUS remains held by its
separate application owner. Normal browser acceptance follows implementation.

The October 28 public database refresh covered all 65 distinct running/init
image digests with no failed or uncovered image. Reports retain remaining CVEs;
this is neither a zero-CVE result nor proof that undisclosed vulnerabilities do
not exist. CISA catalog 2026.10.27 identifies three applicable KEV identifiers.
The only newly available compatible third-party candidates found in this refresh
are official MySQL 8.4 (same 8.4.13 binary, new operating-system packages) and
YTPTube v2.7.6 (upstream dependency release). Their individual scans remove the
Brotli KEV finding; other CVEs remain. No vendor derivative is being built.

All three host installations now contain `libbrotli1=1.0.9-2ubuntu0.1`, the
Jammy fix in [USN-8956-1](https://ubuntu.com/security/notices/USN-8956-1).
Worker2's native unattended updater installed it at 06:44 local time. Our first
controller attempt stopped before installation on the exact package trigger;
the reviewed retry then refused changed host/cache state before dispatch. No
second installer, reboot or service restart was performed. Both refusals remain
evidence. The explicit, disabled-by-default Ansible entrypoint preserves the
repeatable procedure; it must not be replayed against the now-fixed host.

The [exact cache and host ledger](../evidence/upstream-maintenance-checkpoint-20261028.json)
records another 4,732,964,864 allocated node Linux bytes observed absent:
908,210,176 bytes of retired master derivative caches, 1,667,665,920 bytes of
retired master web caches, and 2,157,088,768 bytes of superseded worker2 platform
caches. These are exclusively qualified unpack caches, removed through native
containerd snapshot APIs. Image records, compressed original OCI payloads,
application data and volumes remain. This is separate from prior cleanup and
does not establish Windows disk recovery.

The worker2 platform removal stopped on `sha256:759c0b74e5755b28b532b85de2fec57da2aaa407964e8c74a1e8a149d4588858`
with a native parent/child precondition failure. It was not retried. Its journal
has 45 direct removal acknowledgements. A separate read-only reconciliation
found all 88 qualified physical paths absent, all 229 original blobs fully
hash-correct, unchanged image records, no missing non-target backend IDs and no
orphan directories. The cause of each unacknowledged path's disappearance was
not observed; the original failed API run is not relabelled successful.

The new native preload procedure checks actual compressed hashes and committed
parent-linked snapshots, exact streamed layer bounds, all three nodes and the
unchanged 25% Longhorn floor plus 512 MiB, independently of the 15 GiB available
space guard. It never repulls an uncertain prior attempt. Its first master
MySQL pull completed with full image/layer verification, unchanged runtime/boot,
1,102,913,536 bytes allocation and both retained floors. However, the prior-record
subset check failed and the original implementation retained only aggregate
inventory hashes. That historical acceptance failure cannot be reconstructed
into a pass. The receipt and original source remain; subsequent runs now record
the exact differing keys without weakening the check. Master is observation-only
for that attempted pull, while the untouched worker stages are independent.

Minimal new receipts, source and exact failure witnesses stay in the existing
F-backed root, UUID `3c792469-ea0e-4a2c-98e8-1185b141607b`. Per-cohort zero-byte
locks still have final reconciliation as a concrete consumer. Original failed
cleanup targets remain protected, including the 4,096-byte worker2 tool directory
and the 12,288-byte root-owned checkpoint scratch subtree. The fresh public-feed
and scanner bulk was reconciled separately: 3,242,889,216 allocated controller
Linux bytes removed, with minimal reports/metadata retained. No Windows recovery
is inferred and no WSL shutdown or compaction occurred.
