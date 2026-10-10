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

Ansible bootstraps hosts independently of BORTUS. Nonsecret configuration is versioned in group_vars/all.yml; sudo is passed through the migration runner's stdin. Flux is the sole application deployment reconciler after chart validation and source activation. Charts, values, Secret references and Flux configuration live in the separate private `jtmb/branconet-charts` repository; BORTUS application source remains in `jtmb/branconet-homelab`. Git contains no Secret values. See [PLAN.md](../PLAN.md) for architecture graphs and acceptance criteria, [MIGRATION-OPERATIONS.md](MIGRATION-OPERATIONS.md) for operations, and [FLUX-GITOPS.md](FLUX-GITOPS.md) for reconciliation.

Version checks use official [Kubernetes releases](https://dl.k8s.io/release/stable.txt), [Calico requirements](https://docs.tigera.io/calico/latest/getting-started/kubernetes/requirements), [containerd releases](https://github.com/containerd/containerd/releases), [Longhorn documentation](https://longhorn.io/docs/1.12.1/) and [Flux releases](https://github.com/fluxcd/flux2/releases). The final report must record effective images and live checks, rather than infer compatibility from installation success.

## BORTUS native Secrets runtime

The delivered container uses Node 22, Next.js 15.5.27 and @kubernetes/client-node 1.4.0 with verified TLS. Prisma/SQLite holds user hashes/roles, nonsecret configuration and SecretReference metadata. Native Kubernetes Secrets hold values; no database-to-cluster push or SSH startup kubeconfig bootstrap remains. See [BORTUS-DEPLOYMENT.md](BORTUS-DEPLOYMENT.md) for probes, PVC, ServiceAccount and scoped Secret RBAC. Other dashboard operations use kubectl and require separate deployment permissions and live acceptance.
