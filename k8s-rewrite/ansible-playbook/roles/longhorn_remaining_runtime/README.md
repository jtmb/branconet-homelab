# Pi-hole and Ingenium runtime maintenance

Fixed two-application/three-volume normal stop/detach/restore through the existing
private charts main, unchanged local validation, validated branch and Flux. Only
existing release replica counts change. Every template/image/claim/PV/volume UID,
replica directory, native Secret reference and original Pi-hole CNAME survives.
BORTUS remains held; this role cannot suspend/unsuspend it or adopt its release.

Use `playbooks/longhorn-remaining-runtime.yml` with explicit
`longhorn_remaining_runtime_enabled=true` and one phase at a time:

1. `budget`: read native complete-content/unpacked status for Pi-hole on all
   three eligible nodes and Ingenium on its unchanged worker1 selector. Missing
   caches stop the cycle without an automatic download.
2. `preload-stage`: qualify exact master image descriptors and cache allocations;
   require the unchanged Longhorn 25% plus 512MiB margin plus complete native
   payload/unpack peak on each worker. Independently retain 15GiB nonprivileged
   filesystem space. Stage only the exact existing official Pi-hole digest;
   keep image/content/data records. Controller C/F floors are rechecked before
   each native pull. `preload-qualify|preload-apply` expose separate phases too.
3. `dns-begin`: Windows Python qualifies GitHub's current public IP with normal
   TLS/existing authentication. Add a hostname-specific resolver and explicit
   TLS verification only in the dedicated publisher clone's local config.
   The task-owned chart worktree uses the same override per Git invocation;
   its shared repository config, Windows/global DNS and credentials stay intact.
4. `prepare|stop|observe|detached|resume|verify`: persist immutable source/data
   identities, submit only two replica-count changes, wait for real validated
   Flux state, prove every consumer gone and normal native detach, then restore
   through the same pipeline. Verify original images/templates/bindings, two
   actual healthy RW replicas, mounted-data reads and unchanged Pi-hole aliases.
5. `dns-end`: after accepted workload restoration and normal DNS resolution,
   restore the exact original dedicated-publisher config and verify GitHub refs
   through its normal resolver.

Run operator phases from the existing WSL environment; the two DNS phases use
existing Windows Python. Privilege input uses the original non-echoing terminal
primitive; no password enters argv, environment, files or logs. Commands refuse
to overwrite receipts or replay submitted mutations. Inspect incomplete intent
before continuing; do not force detach, delete data, lower thresholds or replay
an uncertain pull/push. Neither old native cache preflight failure was a pull.
Their exact executed sources and actual/limited failure evidence remain.

Longhorn's reported available space corresponds to filesystem `f_bfree` here;
the independent user-available metric is `f_bavail`. The corrected preloader
requires both the unchanged Longhorn floor/margin and the separate 15GiB user
floor, without changing ext4 reserved blocks. Its former precheck compared the
Longhorn floor to the other metric and stopped before the native pull; preserve
that failure instead of rewriting it as a successful stage.

All generated metadata stays inside the existing F-backed task root, under
`platform-upstream-review-20261027/longhorn-remaining-runtime-20261028`.
Original Git blobs, retained native image payloads and unchanged publisher/tools
are regeneration sources. Controller peak is one GiB including two publisher
exports; remove consumed exports with the existing full Linux/Windows workflow.
Native Pi-hole image caches are required runtime artifacts for the eligible-node
scheduling contract, not disposable analysis copies. Keep unique source/failure/
execution/data witnesses and reconcile all other scratch at completion.
