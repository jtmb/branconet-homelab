# Reviewed singleton etcd patch

The reviewed singleton rollout completed on October24. This remains an opt-in
maintenance path; it must not be replayed against the upgraded cluster. The default role
and Ansible check mode do not stage helpers or change the cluster. The separate
controller requires `--apply` even for its privileged review and status phases.
Only phase `apply` changes Kubernetes configuration or the static Pod manifest.
The additional explicit `preload` phase only caches the exact original and new
official etcd images, preserving the original rollback image's complete content.

The fixed transition is `registry.k8s.io/etcd:3.7.0-0` to
`registry.k8s.io/etcd:3.7.3-0@sha256:0d27b9478551f431f82d1e0ddb6c87ad07ebae8b904c637f3a99213349523910`.
The old runtime manifest is
`sha256:6ecefbe2510c4a30573a62a4d6dd175acf881ca67003fcd91849a16df7a724d5`;
the new Linux amd64 manifest is
`sha256:b4a41c6864baf573f5213dce18b2a95e1002ec6c5a1a26ad900c2ea166ac6d0b`,
with config digest
`sha256:380d0ce8f32cc05ce8a1ea99c74da03be90d6c1dad75c9a2ddb8d83162af7f70`.
This does not upgrade Kubernetes or change its minor version.

## Evidence and preservation contract

Read-only RPC discovery on October 24, 2026 at 05:51 UTC found one healthy,
non-learner member named `masternode`, cluster ID `6018368537312584938`, member
and leader ID `6539934570868142778`, no alarms and etcd version `3.7.0`.
The peer/client URLs matched `https://192.168.0.4:2380` and
`https://192.168.0.4:2379`. Revision was `8346888`; these are observations, not
expected current revision values. A later read-only HashKV query verified the
supported RPC response shape at a specified revision without returning keys.
Every real operation repeats membership, health, alarm and identity checks.

The root operator reported an exact official-image scan, attempt `fc40e27815d6`,
with zero Critical/High and five Unknown findings for the new etcd image. That
result is separate from this source preparation and does not establish that
the whole cluster is free of vulnerabilities. Source provenance and redirect
bounds are documented in [CORE-PATCH-SCANS.md](CORE-PATCH-SCANS.md).

Before review and again before apply, the controller authenticates the whole
existing encrypted control-plane archive, verifies every configuration member
and the full snapshot SHA/footer, and binds it to its protected completed
receipt. The first complete authenticated stream obtains the encrypted
manifest; the second reuses the existing backup verifier. Neither stream is
extracted to disk. The receipt must attest successful snapshot status and an
off-node operator copy with no remote plaintext retained. Its age must be
between zero and **one hour**. Review and apply use the same receipt SHA.

The live worker compares every `/etc/kubernetes` file to that authenticated
backup, including the original static manifest, PKI, encryption configuration,
kubeconfigs and local `kubeadm-init.yaml`. Missing files, extra files, aliases,
unexpected layout, ownership or changed bytes stop the operation. Hashes and
selected metadata may appear in protected receipts; keys, configuration values,
KV contents and credentials do not. Root must review the real privileged
manifest hashes and source layout; the earlier metadata audit did not read
those privileged files.

The original `/var/lib/etcd` and `/var/lib/etcd/member` directories must retain
their device/inode, owner and mode. The helper does not write, copy, rename,
restore or delete their data. The existing etcd process naturally writes its
database during normal operation and migration. A frozen revision HashKV must
match after the patch, member/cluster IDs remain identical and current revision
and Raft indices cannot regress. A compacted frozen revision fails validation;
it is never treated as proof of preservation.

All three nodes must be healthy and schedulable, original active controllers
ready, attached Longhorn volumes healthy and the original Longhorn drain policy
retained. Every original Deployment/StatefulSet/DaemonSet, Longhorn volume,
PVC, PV and node UID is preserved, including inactive controller identities.
There is no drain, reset, PVC/volume deletion, force-new-cluster or recovery
operation in this role.

## Configuration and operation boundaries

The controller is [run-etcd-static-patch.py](../scripts/migration/run-etcd-static-patch.py),
the playbook is
[etcd-static-patch.yml](../k8s-rewrite/ansible-playbook/playbooks/etcd-static-patch.yml),
and the worker is
[patch_etcd.py](../k8s-rewrite/ansible-playbook/roles/etcd_static_patch/files/patch_etcd.py).
The role stages only new public helpers and protected receipts below
`/home/james/.local/share/branconet-migration/etcd-static-patch-20261024`.
It stages an unchanged content-addressed copy of the existing recovery guard.
No existing helper, scanner attempt or seven-application preload allowlist is
repurposed. Existing host PyYAML is required; no dependency install is included.

The read-only review phase requires the new exact image alias and its
index/amd64/config/layers already present in independent `containerd-k8s`, while
retaining the original alias and original runtime/config/layer content. This
role's explicit `preload` phase fills only those exact caches. It uses the existing
independent runtime in a1GiB/noSwap/twoCPU/128task/300second unit, records actual
child cgroup limits, and supplies a new empty HOME without credentials. The
existing cache-import reserve (15% filesystem plus1GiB) and an additional2GiB
working reservation are required. Every existing image alias, configuration,
data-directory identity and resource identity must remain. It uses normal TLS
verification and performs no application startup or static manifest change.

Review renders an image-only manifest replacement and verifies parsed YAML
equality except the one image field. It supports one standard unquoted kubeadm
image line and the observed single-member host data layout. It refuses other
layouts rather than rewriting them. The rendered manifest's temporary file is
outside kubelet's watched manifests directory, on the same filesystem.

Both authoritative kubeadm configurations are pinned: the existing
`kube-system/kubeadm-config` ConfigMap's `ClusterConfiguration` and the existing
local `/etc/kubernetes/kubeadm-init.yaml`. All parsed values are preserved except
`etcd.local.imageRepository` and `etcd.local.imageTag`. The tag includes the
immutable digest. A memory-only `kubeadm config images list` call must generate
the exact reviewed reference before any configuration mutation. This follows
the official [kubeadm v1.37.1 image construction source](https://github.com/kubernetes/kubernetes/blob/v1.37.1/cmd/kubeadm/app/images/images.go)
and [configuration schema](https://kubernetes.io/docs/reference/config-api/kubeadm-config.v1beta4/).
The real installed binary's acceptance remains a runtime review gate. Future
kubeadm upgrade version parsing must be reviewed separately; no untested
upgrade invocation or repository provisioning replay is authorized here.

Apply requires an exact successful review ID and receipt SHA with matching
helper hashes, backup SHA, config/manifest identity, ConfigMap UID and
resourceVersion, image cache, original resources and directory identities.
It performs a UID/resourceVersion-tested ConfigMap JSON patch, an atomic local
kubeadm configuration replacement, then an atomic static manifest replacement.
The existing kubelet restarts the static Pod. The operation observes the new
runtime image, real etcd version, API readiness, unchanged frozen-revision
HashKV and original resources. It does not restart another workload.

There is deliberately **no automatic stateful rollback**. If a later step
fails, earlier kubeadm updates or the manifest may already be committed. The
protected receipt records the last stage and `manifestCommitted` state. Preserve
that state, inspect the exact existing receipt and compare actual files before
any further action. Never blindly rerun an attempt, start the old image against
migrated data, force recovery or restore a snapshot automatically.

## Review and execution interface

The controller runs from the reviewed checkout in native WSL using the existing
Ansible virtual environment. `--syntax-check` only parses Ansible source. With
no `--apply`, it invokes the disabled role. For a real reviewed operation,
`--apply --phase review` additionally requires `--backup-receipt`, its exact
`--backup-receipt-sha256` and a private `--output-dir` below
`/home/brajam/.local/share/branconet-migration`, outside Git. A unique run ID is
created unless explicitly supplied. The operator supplies the existing sudo
credential through protected JSON stdin only, never command arguments or Git.

An apply uses `--apply --phase apply`, the same still-fresh authenticated backup,
and the preceding remote review receipt's `--review-id` and `--review-sha256`.
Each apply has a new run ID. The sudo credential reaches only the child Ansible
environment; settings contain public hashes and verification metadata only.
Private output files are created without overwriting earlier attempts.

`--apply --phase status --run-id <existing-run>` only reads that remote receipt;
it does not require another fresh backup or replay the operation. A controller
observation timeout retains the original Ansible PID and means inspect that
same operation. It does not authorize starting a second attempt.

## Historical execution requirements

Root must review the new source and current official-image scan, prepare the
bounded exact-image preload, authenticate a fresh backup and execute the real
review before considering apply. A backup taken at 06:01 UTC is historical
once its one-hour bound expires; acquire a fresh one when necessary. Successful
source checks do not establish that the installed kubeadm binary supports the
exact override or that the live patch succeeded.

The control-plane backup helper separately accepts only the original source
pair or this exact new image with its reviewed index/amd64 runtime identifiers.
The matching CLI version is required (3.7.0 or3.7.3); crossed or unknown source
pairs refuse. Defaults stay on the old source until the live patch is accepted.
All original encryption, archive, size, file-identity and snapshot checks remain.
The authenticated pre-patch snapshot/config archive remains the retained
recovery source. No independent restore drill is claimed. Only a genuine live
receipt with post-patch member/data/resource/configuration checks can accept
this patch; full-cluster security acceptance remains separate.


## Accepted live patch and post-upgrade backup

Apply `53875159506e446f87bdef83320bc99b` passed after review
`7923c68c11a0456b8997aba10f31ac81`. Its protected receipt fingerprint is
`9b9361447f8611f25ed8b51ff4164b05bd732226a1b31b4157b99f9744c94e75`.
The new Pod UID is `4057f122-69a2-48a9-9783-e55ee5c6775e`. The exact image above
is running, the original member and cluster IDs remain, endpoint health passed,
there were no alarms, and the frozen revision HashKV matched. Original data
directory identities and all protected workload/storage identities survived.

Fresh cluster observation at23:14UTC found API readiness `ok`, all three nodes
Ready/schedulable without pressure, all54 Deployments and7 DaemonSets ready,
40 retained Longhorn volumes with no unhealthy attached volume, and no unready
running Pod or active HelmRelease. Observation fingerprint:
`fddd51cd2a9e3696a7314cf0810c265f8ff951ddf1b182a3461625fc509ad916`.

The post-upgrade backup completed at23:14:28UTC, run
`eb84c1363a434bde8d46a0dbe4ed8f4e`. All46 configuration files and the snapshot
were authenticated, including complete archive EOF, snapshot footer/status and
off-node ciphertext copy. Receipt fingerprint:
`297796d28ef0d166193212645c822bb36e032b05ed1d30b7a983efcf438d1a93`.
The75,006,036-byte encrypted archive fingerprint is
`336077a7782bdaa5783cab4e2de5e2e3fa554548ced6dc6f8dde5081f4ca82fa`.
The original pre-upgrade backup and failed preload/review attempts remain intact.
This is not an independent restore demonstration or full-goal completion.

The runtime reports the exact tag-plus-index digest as imageID; the backup
allowlist and defaults now include that observed representation. Other accepted
representations still require the same exact reviewed source/version pair.
