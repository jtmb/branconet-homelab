# Pi-hole and Ingenium restored on current runtimes

Both original applications and all three volumes now pass the strict runtime
verifier. Original images, templates, Deployment/HelmRelease/PVC/PV/volume UIDs,
replica directories and mounted-data reads survive. Every volume has two actual
healthy RW replicas on the pinned Longhorn 1.13 instance manager. Pi-hole's full
native CNAME list is unchanged. Normal Windows HTTPS returns 200 at
`https://pi.branconet.lan/admin/` and `https://ingenium.branconet.lan`.
[Exact identities, source and path/byte evidence](../evidence/longhorn-remaining-runtime-20261028.json).

Stop `35c61b9edd35dc8b851240d02ee8fa2896ea1af9` and restore
`cae6f2ac6e1c12afd4104df751b793db3fa94c62` passed unchanged local validation,
atomic validated promotion and Flux. Only two existing release replica counts
changed. All consumers disappeared and all three volumes detached normally
before restore. No direct scale/suspend, forced detach, data copy/rewrite,
Secret mutation, application rebuild or limit change occurred. Ingenium's normal
API/web startup took several minutes; the original startup warnings remain
observations, and accepted new application containers have zero restarts.

Only held BORTUS's engine still uses an old runtime. Its release/adoption hold and
data were not changed. The rest of the migration and security acceptance stays
in scope; this cohort is not full-goal completion.

## Capacity and DNS dependency

The first read-only preflight found missing Pi-hole native caches on both workers
and refused the cycle. The unchanged Ingenium image was already complete on its
only eligible node, worker1. A fixed bounded preloader measured the master's
original Pi-hole descriptors and allocated cache layers and budgeted 285,249,774
additional bytes per worker, retaining the original 25% plus 512MiB Longhorn guard
and an independent 15GiB nonprivileged free-space floor. Both workers now have
the complete unchanged official image; every eligible node was qualified before
the cycle. No storage reserve, reserved ext4 block count or threshold changed.

The initial profile failure lacked captured native stderr; its exact source and
limited actual failure witness survive. A later precheck incorrectly compared
Longhorn's free-space metric with `f_bavail` and stopped before a pull. The
corrected source enforces Longhorn's `f_bfree` metric and the separate user-space
floor together. The original failed sources/intents/receipts are preserved;
neither failed check submitted a native pull. A completed or uncertain pull is
not automatically replayed.

Before Pi-hole stopped, a temporary hostname-specific GitHub resolver was
qualified with normal TLS and existing credentials. It affected only the
dedicated publisher's local config and per-command Git settings in this task's
chart worktree. Windows/global DNS, shared chart config and credentials stayed
unchanged. After accepted restoration, the exact original publisher config was
restored and GitHub access passed through normal DNS. The publisher remained
the sole existing process; no second publisher or GitHub Actions was used.
[Git's documented resolver option](https://git-scm.com/docs/git-config#Documentation/git-config.txt-httpcurloptResolve).

The opt-in Ansible entrypoint is `playbooks/longhorn-remaining-runtime.yml`.
Its maintained role documents explicit budget, preload, DNS-window and controlled
cycle phases, immutable source/data fencing and refusal of receipt replay.

## Output reconciliation

Same owner and existing F-backed root, UUID
`3c792469-ea0e-4a2c-98e8-1185b141607b`. Removed **355,721,216 allocated controller
Linux bytes / 1,612 paths** from consumed terminal publisher exports
`4e82fd805ad54ed5a938857b5794545b` and `03a55723b4154f9dafb0586ff4eda93e`.
Full Linux process/unit/map/FD/mount exclusion, original Git blob/tool checks
and all 1,612 exclusive Windows handles passed. Original sources and ten unique
validation/publication/lock records survive. Per-path ledger:
`platform-upstream-review-20261027/longhorn-runtime-retirement-20261028/publisher-cleanup-26b8dd5329c557a4/receipt.json`.

The cohort's `checkpoint-inventory.json` lists 30 retained unique metadata/source/
failure/data/route witnesses, 52,559 logical bytes excluding that inventory.
No controller build/dependency/archive payload or other disposable scratch was
created. Native Pi-hole caches are required runtime artifacts for unchanged
eligible-node scheduling. All earlier protected safety-check/original rollback
exceptions remain protected. No Windows/VHDX disk recovery is inferred from
Linux deletion.
