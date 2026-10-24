# Exact official etcd and CoreDNS patch scans

Read-only inventory on October24 found Kubernetes1.37.1 throughout this cluster,
with etcd3.7.0-0 and CoreDNS1.14.6. The three hosts' kubeadm/kubelet/kubectl
executables are under `/usr/local/bin` without dpkg package ownership. Official
`stable-1.37.txt` still returns1.37.1; the1.37.2 release API returns404. A scheduled
target date is not a published patch, and this work proposes no Kubernetes minor
upgrade. Known fixed Go/module rows in the existing1.37.1 image audit remain
separate source-rebuild or future-vendor-patch work.

Two official compatible patches are available. Their exact public registry
index and amd64 manifests were SHA-verified without fetching image configuration
or layers. A prepared separate scanner accepts **only** these references:

| Component | Exact reviewed image | amd64 manifest |
|---|---|---|
| etcd3.7.3 | `registry.k8s.io/etcd:3.7.3-0@sha256:0d27b9478551f431f82d1e0ddb6c87ad07ebae8b904c637f3a99213349523910` | `sha256:b4a41c6864baf573f5213dce18b2a95e1002ec6c5a1a26ad900c2ea166ac6d0b` |
| CoreDNS1.14.7 | `registry.k8s.io/coredns/coredns:v1.14.7@sha256:7efd3c635b03efd68c4e8398fc45f0d993d0e9ab016f72c1cefb0fd6d01aa286` | `sha256:2329f5f0e7e79fbe56dcdf11ecc4337ee2476bb251095bc275fe9461cb88a55b` |

The etcd index is identical to official `gcr.io/etcd-development/etcd:v3.7.3`.
Its [October22 security bulletin](https://etcd.io/blog/2026/oct-22-patch-release/)
describes patched Go1.26.10/x/net/OTel dependencies and remaining unpatched issue
reports. [CoreDNS1.14.7](https://github.com/coredns/coredns/releases/tag/v1.14.7)
fixes [custom-transport allocation](https://github.com/coredns/coredns/security/advisories/GHSA-mrg3-qvqr-jw29)
and [UPDATE validation](https://github.com/coredns/coredns/security/advisories/GHSA-9gm5-9rfh-m6vx).
Its release says Go1.26.6; do not infer that it fixes every newer Go/module CVE.
The current Corefile's transport exposure was not inspected by the metadata
audit. An exact unsuppressed candidate scan and applicability review are needed.

## Separate scanner and reused public inputs

[`vendor-core-scan.yml`](../k8s-rewrite/ansible-playbook/playbooks/vendor-core-scan.yml),
role `vendor_core_scan`, and
[`run-vendor-core-scan.py`](../scripts/migration/run-vendor-core-scan.py) are new,
opt-in source. They do not expand or modify the existing cert-manager five-image
scan, its helpers, inputs, attempts or accepted results. No runtime scan is
claimed by this source preparation.

The new helper/root is
`/home/james/.local/share/branconet-migration/vendor-core-scan-20261024`.
Setup hashes the **already existing** public input snapshot at
`/home/james/.local/share/branconet-migration/vendor-cert-manager-scan-20261024/inputs`
in place. It never copies another1.8GB, changes permissions/ownership or modifies
original files. The shared existing read-only batch lock coordinates with the
cert-manager scanner; no lock contents are written. Root must retain independent
serial admission against every other scanner as well.

The reused fixed inputs are Trivy0.76.1, SHA256
`d1dfca6ae10a1ad4540bb94e64f0510077c47008920a9b554986b39dca573d83`,
the exact retained main vulnerability database/metadata, and the Results-only
template. Sizes, hashes, canonical paths and root ownership are checked again
before and after the batch. The DB must be no older than24hours at execution.
There is no Java DB copy or Java-analysis suppression; unexpected Java evidence
or missing analysis fails instead of becoming a clean result.

The new public-registry unit runs as James with all capabilities removed,
`NoNewPrivileges`, hidden operator home, strict read-only system filesystem,
private devices/tmp, and inaccessible Kubernetes/Longhorn/CRI/credential paths.
Only the existing public input subtree and new scanner root are rebound
read-only; only the exclusively created current attempt is writable/noexec.
Its Docker configuration and HOME are new/empty. No existing credentials,
service-account token, kubeconfig, app environment or Secret is supplied.

The unchanged batch bounds are1GiB RAM/no swap, two CPUs,128tasks, nice10 and
900seconds for the entire sequential two-image batch. The helper additionally
enforces the25%-filesystem-plus8GiB and inode reserves, the existing2GiB working
reservation before preparation, per-report/cache/log bounds, and the same
deadline/cancellation behavior. It cannot import or execute an application
image, access CRI, change a workload, or deploy a patch.

## Public manifest redirects and provenance

On workernode1 at05:21:45UTC, both fixed index requests followed one HTTP307
from `registry.k8s.io` to `us-east5-docker.pkg.dev` under the exact public project
path `/v2/k8s-artifacts-prod/images/<reviewed-repository>/manifests/<digest>`.
Each original index SHA matched the final bytes. The new metadata helper allows
only this observed HTTPS host/project/repository/digest path, one307, and an
optional hexadecimal `rid` routing parameter. It rejects other hosts, ports,
credentials, fragments, query keys, repository paths or additional redirects.
Unknown regional redirects require new primary evidence and source review;
the helper does not follow an arbitrary `*.pkg.dev` destination.

Index and amd64 bytes are saved exclusively in the new attempt and SHA-bound
to the fixed original registry identities. Config digests are recorded from
the manifest without serializing image config/Env/history. Trivy then pulls the
same digest-bound public image through its normal remote-registry transport and
performs vulnerability-only/offline-database analysis. The Python redirect
allowlist governs provenance manifest reads; it is not an operating-system
network-egress firewall or a claim that every blob redirect is intercepted.

Receipts correctly record `sourceKind: upstream-registry`; there are no invented
CI runs/build artifacts or substituted provenance. Registry SHA chains do not
claim image signature verification. Reports serialize Results only and preserve
all findings. `securityAcceptance` remains false even when the batch completes.

From a freshly staged reviewed source tree, the native WSL controller accepts
the existing sudo credential through protected JSON stdin only:

```bash
/home/brajam/.local/share/branconet-migration/venv/bin/python scripts/migration/run-vendor-core-scan.py --syntax-check
/home/brajam/.local/share/branconet-migration/venv/bin/python scripts/migration/run-vendor-core-scan.py --apply --phase setup --output-dir /home/brajam/.local/share/branconet-migration/vendor-core-scan-execution-20261024
/home/brajam/.local/share/branconet-migration/venv/bin/python scripts/migration/run-vendor-core-scan.py --apply --phase scan --attempt <new-12-hex-id> --output-dir /home/brajam/.local/share/branconet-migration/vendor-core-scan-execution-20261024
/home/brajam/.local/share/branconet-migration/venv/bin/python scripts/migration/run-vendor-core-scan.py --apply --phase status --attempt <same-id> --output-dir /home/brajam/.local/share/branconet-migration/vendor-core-scan-execution-20261024
```

Status observes the existing unit/receipt; a controller observation timeout does
not authorize replay. Failed attempts remain preserved and cannot be reused.

## Patch ownership and live gates

Observed etcd and APIserver Pods are static mirror Pods with source`file` on
masternode. Only one APIserver and one etcd Pod were seen; actual etcd membership
was not queried, so do not assume three-node etcd HA. Fresh encrypted etcd and
control-plane/config backups, authenticated snapshot integrity, actual endpoint/
member/alarms/revision checks and retained PKI/encryption keys/old image/manifests
are required before the separately reviewed static image update. Account for the
control-plane interruption and verify data-compatible recovery afterward.

The existing `security_maintenance` role owns the reviewed Jammy/containerd path,
not these unmanaged Kubernetes binaries/static images/addons. Do not use APT
package selection to pretend `/usr/local/bin` is patched, and never replay the
cluster installer/reset. The current `control_plane_backup` defaults/assertions
pin etcd3.7.0-0; deliberately review its accepted exact backup-image contract and
tool/server compatibility alongside future etcd maintenance.

CoreDNS's observed Deployment lacks Helm/Flux ownership metadata and no CoreDNS
resource matched private Flux manifests. Select one repeatable owner path before
any update; do not invent an existing chart owner or introduce two publishers.
Retain its Deployment/Service UIDs, Corefile, DNS domain/upstreams/clusterIP,
replicas, RBAC and resource limits; then verify UDP/TCP service/external/local/NAS
DNS, readiness and routing. Kubeadm1.37.1 defaults still name old etcd/CoreDNS
images; retain reviewed image overrides in authoritative kubeadm configuration
before future kubeadm operations so patches cannot silently revert.

All serial node/PDB/Longhorn last-replica drain protections and original volume,
PVC and Deployment identities remain. This document and scan source authorize no
rollout or weakening of existing backup/data/resource/publication gates.

## Actual fixed-input scan, October24 05:45 UTC

The new source was frozen and syntax-checked, then setup verified the existing
public inputs without copying them. Batch `fc40e27815d6` completed successfully
within the unchanged bounds, preserving input hashes and exact image identities.
Receipt fingerprint (SHA256):
`7c8e8a2a3a37db4f6b9f63e5c177022e71740cef76941ba0db44fdb52a902a10`.

Etcd3.7.3 has zero critical/high rows and five unknown rows. These include
available Debian tzdata/CA-bundle updates and an unfixed x/crypto advisory;
this is not a claim that every severity has been remediated. Results fingerprint:
`dd149147a218e80a41c666ce0375b352f061a8a4be16865c23b7b629d150b64e`.

CoreDNS1.14.7 has22high,22medium,1low and3unknown rows, including22high rows
with fixed-version metadata. Compiled Go/modules need actual updates; the
binary's pseudo-version also requires source/version attribution review rather
than treating old already-fixed advisories as confirmed exploitable defects.
No finding has been suppressed or reclassified in the original report. Results:
`83ecff1f5329aebef11e024567922c8ea07ee1a0f79f7070519c4272cd6b103c`.

Neither scan changes the live etcd/CoreDNS version. The protected backup,
repeatable owner/configuration path and service/data verification remain required
before a patch is accepted. CoreDNS's vendor version bump alone cannot close its
available dependency fixes. Original attempts and reports remain intact.
