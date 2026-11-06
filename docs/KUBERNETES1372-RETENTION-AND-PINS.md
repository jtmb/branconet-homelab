# Kubernetes maintenance source pins and terminal cleanup

The `cluster-headroom-security-tls` checkout contains maintenance-only
`k8s-rewrite/ansible-playbook/group_vars/all.yml`. It pins native containerd
`v2.4.2` and its independent socket, but contains no Kubernetes/etcd bootstrap
version variable or bootstrap installation role. A YAML/Jinja search found no
`1.37.1`, `kubernetes_version`, `kubeadm_version` or `etcd_version` declaration.
No unused variable was added and no independent runtime/etcd pin was changed.
The concrete native maintenance target remains Kubernetes `1.37.2` at the
original `/usr/local/bin` paths, preserving independent etcd `3.7.3`. Any separate
bootstrap repository needs its own exact source inspection before its pins can
be updated. Frozen original authority and scan pins must remain historical.

## Empty Kubernetes scratch reconciliation

`scripts/migration/reconcile-hardening-scratch.py` now supports the opt-in
`--scope kubernetes-empty`. Supply the same hash-bound terminal native runner
result for each existing phase (`inventory`, `windows`, `apply`):

```text
--scope kubernetes-empty
--kubernetes-success kubernetes-maintenance-receipts/RUN_ID-result.json
--kubernetes-success-sha256 SHA256
```

The terminal result must have exit code zero, a finish time, explicit apply true,
an intact authority hash, and exactly three successful native last-consumer
completion receipts, bound to that authority and the original three nodes.
The existing kernel/TLS terminal guards, complete Linux reference guard, physical
filesystem UUID, Windows exclusive-handle pass and protected-file hashes remain
mandatory. Only empty directory trees inside `H/kubernetes-maintenance-scratch`
are candidates. Any file, symlink, mount, unexpected metadata or active reference
protects the target. This mode does not recursively delete files.

New plan/Windows/receipt filenames use `kubernetes-scratch-reconciliation-*`.
Existing reconciliation plans and receipts are never overwritten. Default scope
retains its original target list and checks. Source hashes still bind each plan:
an existing plan made with an older script is not silently accepted by modified
source. Preserve that plan and its original source authority; do not rebase its
hash to bypass the binding.

## Binary and tool last consumers

The native vendor blobs, verified cosign executable and private signature cache
remain required by the full native authority verifier until the final all-node
preflight/apply consumers have completed successfully. Image staging or a single
node's completion is insufficient. The new empty-directory mode cannot delete
these artifacts.

After terminal success, reproducible downloaded vendor blobs/tools/cache become
eligible for a separate existing full-reference cleanup review only after their
exact paths, owners, regeneration URLs/checksums/signatures, final consumer and
inactive Windows/Linux references are verified. Preserve compact original
authority, signature/certificate and scan receipts, source hashes, unique failed
scan evidence, successful runtime/recovery receipts and the complete original
installed binary backups. Original backups are not reproducible vendor caches
and are excluded from automatic cleanup. No file deletion or remote operation
was performed for this source change; validation was syntax parsing only.
