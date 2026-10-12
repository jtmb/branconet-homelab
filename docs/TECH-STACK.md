# Branconet migration technology and topology

The approved target is Kubernetes on the existing three Ubuntu 22.04.4 machines. [MIGRATION_STATUS.md](../MIGRATION_STATUS.md) records what has actually passed; this document describes configuration, not deployment completion.

| Host | Address | Target role |
|---|---|---|
| masternode | 192.168.0.4 | Control plane and workloads |
| workernode2 | 192.168.0.5 | Worker and storage |
| workernode1 | 192.168.0.6 | Worker and storage |

One control plane needs a documented etcd/configuration restore; it is not a highly available control plane. Longhorn application volumes use two replicas on separate nodes.

| Component | Configured version | Purpose |
|---|---|---|
| Kubernetes | v1.37.1 | kubeadm, API, scheduling and kubelet |
| containerd | v2.4.1 static | Independent Kubernetes CRI runtime |
| runc | v1.5.2 | Independent OCI runtime |
| CRI tools | v1.37.0 | Runtime diagnostics |
| CNI plugins | v1.9.1 | CNI executable prerequisites |
| Calico | v3.33.0 | Pod CIDR 10.244.0.0/16, IP-in-IP, network policy |
| CoreDNS | kubeadm-selected image | Two ready replicas; service domain cluster.local |
| Longhorn | v1.12.1 | Replicated V1 volumes, LUKS encryption, retained PVs |
| CSI snapshot controller | v8.6.0 | VolumeSnapshot API/controller for tested Longhorn restore |
| SMB CSI | v1.20.3 | Existing NAS share mounts in application pods |
| Traefik | v2.11 original digest | Native LAN 80/443 routing through NodePorts 30080/30443; application ingress |
| Flux | v2.9.6 | Source, Kustomize, Helm and notification controllers |
| Helm CLI | v4.3.0 | Individual chart validation and infrastructure install |
| Ansible core | 2.21.5 operator runtime | Host provisioning through SSH |
| age | v1.3.2 operator runtime | Encrypted configuration/data recovery archives |
| BORTUS | Repository application | Kubernetes management; native Secrets integration developed separately |

Kubernetes uses containerd-k8s.service, /run/containerd-k8s/containerd.sock and /var/lib/containerd-k8s. Existing Docker/containerd configuration, runtime and data remain available during migration. Native Kubernetes Secrets use API encryption at rest; secret values remain outside Git. Encryption keys and Kubernetes recovery configuration must be included in encrypted recovery backups.

Longhorn is the default persistent application storage. Each chart declares its own PVC mounts and values. Existing NAS media at //192.168.0.8/plex_smb_share remains intact; requested integration is a separate live acceptance check. The Samba role installs the client CSI driver only. It does not create a guest share or overwrite exports, credentials, fstab or files. Host-local default storage and a new NFS server are not part of this migration.

Ansible bootstraps hosts independently of BORTUS. Nonsecret configuration is versioned in group_vars/all.yml; sudo is passed through the migration runner's stdin. Active application chart delivery uses the separate private `jtmb/branconet-charts` repository: main, successful chart CI, exact-SHA promotion to `validated`, then the existing Flux `branconet-charts` source and `migration-releases` owner at `./flux/releases`. The old migration publisher and raw-manifest roots are historical; do not reactivate them. Application source quality CI is separate and does not publish a running image. Git stores charts, values and Secret references, not Secret values. See [PLAN.md](../PLAN.md) for architecture graphs and acceptance criteria, [MIGRATION-OPERATIONS.md](MIGRATION-OPERATIONS.md) for operations, and [FLUX-GITOPS.md](FLUX-GITOPS.md) for reconciliation.

Version checks use official [Kubernetes releases](https://dl.k8s.io/release/stable.txt), [Calico requirements](https://docs.tigera.io/calico/latest/getting-started/kubernetes/requirements), [containerd releases](https://github.com/containerd/containerd/releases), [Longhorn documentation](https://longhorn.io/docs/1.12.1/) and [Flux releases](https://github.com/fluxcd/flux2/releases). The final report must record effective images and live checks, rather than infer compatibility from installation success.

## BORTUS native Secrets runtime

The delivered container uses Node 22, Next.js 15.5.27 and @kubernetes/client-node 1.4.0 with verified TLS. Prisma/SQLite holds user hashes/roles, nonsecret configuration and SecretReference metadata. Native Kubernetes Secrets hold values; no database-to-cluster push or SSH startup kubeconfig bootstrap remains. See [BORTUS-DEPLOYMENT.md](BORTUS-DEPLOYMENT.md) for probes, PVC, ServiceAccount and scoped Secret RBAC. Other dashboard operations use kubectl and require separate deployment permissions and live acceptance.

Image qualification now uses a private pinned [Trivy 0.75.0 release](https://github.com/aquasecurity/trivy/releases/tag/v0.75.0)
binary verified against the immutable release asset digest and published checksum.
It is installed only under the protected operator runtime, without a global install.
Image archive and image-config Secret scanners plus vulnerability scanning use
default built-in rules, no user ignore/config files, one worker and disabled
telemetry. Raw reports stay outside Git. The [actual holder scan](../evidence/bortus-holder-source-image-7e30-20261011.json)
records findings and scope; zero Secret findings does not mean vulnerability-clean
or final runtime/release acceptance.


The separate [custom kubectl security build contract](BORTUS-KUBECTL-SECURITY-BUILD.md)
consumes pinned upstream1.37.1 source and Go1.26.9 archives, with reviewed
x/net0.60.0 and transitive pins. It is a local-only candidate for a custom
binary, not an upstream1.37.2 release or image security pass. Existing Dockerfile
and release-builder defaults remain unchanged pending separately qualified
source-linked injection and actual image/runtime acceptance.


Custom kubectl build receipts keep detailed source/cache diffs in a bounded,
protected fsynced metadata sidecar and full before/after ZIP; only count/SHA/path
stay in the1MiB ownership record. Public archive modes are preserved inside the
private run. The first actual attempt failed before compiler dispatch at the
record bound; earlier fixtures did not qualify its cache scale. Existing image
contracts and defaults remain unchanged; see [custom build](BORTUS-KUBECTL-SECURITY-BUILD.md).

## 2026-10-12 05:31 UTC: actual custom kubectl build and component scan

The [actual root receipt](../evidence/bortus-kubectl-actual-build-root-20261012.json) records all12 build stages with exit0, completed at05:18:10UTC. The 61,960,354-byte binary is a custom `v1.37.1-bortus.security.1-dirty`, built with Go1.26.9 and x/net0.60.0; SHA-256 `a3c4741294f061550b30bd2e3f357197ffbac37eefc5a45d686fe9cd29032b75`. All observed build command, helper and supervisor PIDs are absent.

Root independently verifies34 transferred originals, complete CRC-valid original/diff ZIPs and32,084 changed-file byte identities. All31,916 paths remain retained, including31,723 generated cache paths; faithful archive modes eliminate artificial mode-only changes. The detailed sidecar is12,741,184bytes while the main completion record is8,902bytes. Source changes outside generated cache are module records and x/* vendor files, including upstream-selected sync/tools/mod transitives.

Default Trivy0.75 component scan returns0 with zero vulnerability or secret findings and explicitly analyzes the kubectl Go binary and90 packages. The first protected copy had mode600 and yielded no Go analysis; that report is retained and rejected. A new owned scan uses the unchanged binary with its original0755 mode inside a private directory, confirms Go1.26.9/x/net0.60.0, retains all severities and uses no suppressions. The original image scan remains346 findings (1Critical/67High). This component result does not accept a final image, deployment, performance, schema migration or live engine. Source-linked image injection, full image/runtime gates and the latest-data cutover remain open.
