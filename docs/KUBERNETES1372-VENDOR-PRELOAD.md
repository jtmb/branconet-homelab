# Official Kubernetes 1.37.2 qualification and native prestage

Prepared source only: no node pulls, upgrade, publication or runtime acceptance.
Kernel-maintenance controller pins and coordinator rollout ordering stay authoritative.

The four official registry.k8s.io images are kube-apiserver, kube-controller-manager,
kube-scheduler and kube-proxy. Exact root/amd64/config metadata, compressed hashes,
full uncompressed diffIDs, chainIDs and conservative allocation bounds are bound by
the controller to H/kubernetes1372-full-scan/oci-metadata.json and
oci-staging-budget.json (H is the existing F-backed autonomous-hardening-20261028 leaf).
All four full unsuppressed scans completed with original freshness, Java DB, CISA,
resource/isolation and input-hash controls. Actual binaries identify Kubernetes 1.37.2
and Go 1.26.10; CVE-2026-111943 is absent. Remaining High package rows are 5,5,5,6;
zero Critical/KEV findings here do not mean zero vulnerabilities or proven safety.
Vulnerability DB UpdatedAt: 2026-10-29T01:22:22.544155871Z; Java identity index:
2026-10-29T01:08:14.598234036Z. Full results and minimal evidence survive cleanup.

roles/kubernetes1372_vendor_preload/files/controller.py, relative to
k8s-rewrite/ansible-playbook, reuses the unchanged official_vendor_preload core
SHA256 0082325f8db7db2f7822bf3fbadb72d0b2d95b6db697fe84441eead3773b5e93.
It retains native ctr/hash/blob/chain/inventory/runtime continuity, exact floors,
error codec and immutable intent/result guards. Protected stdin is consumed once
into bounded RAM before inherited-stdin SSH GETs. No credential is written.

The additive preflight observes all four images on all three nodes, summing missing
peaks without deduplication discounts and using minimum observed free/usable space.
It enforces the original 25%+512MiB and 15GiB usable floors for the aggregate before
any pull. Original fresh per-image/per-node checks still follow. Worst-case total
is 818,614,751 bytes including 16MiB metadata allowance PER image. Registry metadata
bytes/JSON and scan/source bindings are rechecked. Outputs remain metadata only at
H/kubernetes1372-prestage; no archives or node source files are created.

Invoke one exact service at a time, sequentially, only after coordinator gates:

```text
python3 -B roles/kubernetes1372_vendor_preload/files/controller.py observe --service kube-apiserver --node all --password-stdin
```

Select kube-controller-manager, kube-scheduler or kube-proxy in subsequent explicit
invocations. Each repeats the aggregate assessment. `stage` selects native pulling;
`observe` is default. The disabled-by-default playbook
playbooks/kubernetes1372-vendor-preload.yml accepts variables prefixed
kubernetes1372_vendor_preload_: enabled, mode, node and service. Use protected
pipe/owner-private stdin, hidden TTY, or one existing KUBERNETES1372_PRELOAD_SUDO_PASSWORD
or ANSIBLE_BECOME_PASSWORD environment input. Never put credentials in argv or Git.

Source review rechecked all four live official metadata plans and RAM-only synthetic
aggregate controls, including individual-fit/aggregate-insufficient refusal. These
were not live node observations. Production acceptance still requires component
versions, API/workloads, storage/data preservation and coordinating rollback gates.

## Kubeadm imagePullPolicy Never tag aliases

After all four image stages on all three nodes have accepted results, run
`roles/kubernetes1372_vendor_preload/files/aliases.py observe --password-stdin`
from the Ansible directory. `create` explicitly selects alias creation. The playbook
`playbooks/kubernetes1372-vendor-aliases.yml` is disabled by default; variables are
kubernetes1372_alias_enabled and kubernetes1372_alias_mode (observe/create).
It uses the same protected input sources as the prestager.

All twelve exact stage receipts and freshly verified native digest caches are required.
All aliases are observed on all nodes before creation. Each node must retain the
original floors after a conservative 64MiB aggregate alias metadata allowance.
Each creation repeats fresh native checks. `ctr images tag --local` without
`--force` creates only an absent registry.k8s.io/COMPONENT:v1.37.2 alias. An existing
alias is accepted read-only only at the exact root with its managed CRI label.
The pinned containerd v2.4.2 tag.go copies the full source Image record including
Labels and changes Name before Create. The helper verifies resulting labels and
requires CRI inspecti to resolve the tag to the pinned config and root/amd64 digest.

Controller-only before/intent/after receipts prevent uncertain retries. Existing
image records/labels, contents, leases, snapshots, containers, tasks, runtime hashes
and boot identity must survive. Failure is retained without rollback/delete or
retry through another mechanism. Source/synthetic review proves preparation only;
no alias was created during review. Original prestager/core sources are unchanged.
