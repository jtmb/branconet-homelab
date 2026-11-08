# Migration-safe Ansible foundation

playbooks/site.yml targets the verified Ubuntu 22.04 hosts in inventory/production.ini. It provisions independent Kubernetes containerd, kubeadm/kubelet, Calico, CoreDNS, Helm, encrypted Longhorn, SMB CSI, temporary Traefik ingress and Flux controllers. It stops on errors and waits for actual readiness. No reset, Gluster removal, disk formatting, new NAS share or Docker runtime replacement is included.

Nonsecret pins and settings are in group_vars/all.yml. Do not overwrite this bootstrap file from BORTUS variable synchronization: initial cluster creation cannot depend on an application inside that cluster. Sudo is supplied at execution through scripts/migration/run-ansible.py stdin. The operator runtime and evidence live outside the application source.

From WSL, validate using the isolated Ansible installation with an explicit configuration path, because WSL considers Windows-mounted directories world writable:

```bash
cd k8s-rewrite/ansible-playbook
ANSIBLE_CONFIG="$PWD/ansible.cfg" \
  ~/.local/share/branconet-migration/venv/bin/ansible-playbook \
  playbooks/site.yml --syntax-check
```

The operational runner enforces verified data backups before provisioning. Supply JSON through a protected pipe containing sudo_password; never put the credential in arguments, Git or shell history. Provision in stages with --tags bootstrap,kubernetes,network,dns, then storage/ingress/gitops after the prior stage passes. A syntax check alone does not satisfy cluster acceptance.

The Kubernetes runtime uses /opt/containerd-k8s/bin, /etc/containerd-k8s, /run/containerd-k8s and /var/lib/containerd-k8s. Existing /etc/containerd, Docker package sources, resolver settings, Gluster bricks/mounts and NAS mounts are preserved. Swap remains a host facility, with kubelet failSwapOn=false and NoSwap for pods on cgroup v2.

Kubernetes native Secrets are encrypted at rest. Longhorn uses two replicas, retained PVs, LUKS and a native longhorn-crypto Secret; recovery copies must preserve both API and volume encryption keys. Flux retains helm-controller and does not activate the source branch until charts/values validate. Application imports, migration cutovers and final Gluster/Vault retirement follow [PLAN.md](../../PLAN.md) and [MIGRATION_STATUS.md](../../MIGRATION_STATUS.md). Full instructions: [MIGRATION-OPERATIONS.md](../../docs/MIGRATION-OPERATIONS.md).

## Application charts and Flux bootstrap

The gitops role points Flux at the separate
[Branconet charts repository](https://github.com/jtmb/branconet-charts).
When source activation is enabled, restore the read-only source credential
`flux-system/branconet-charts-readonly` through native state recovery before
running the role. Flux fetches the `validated` branch and reconciles
`./flux/releases`. Chart changes land on `main` and the local validator
promotes passing revisions to `validated`. GitHub Actions is disabled.

qBittorrent's Gluetun sidecar selects userspace WireGuard in the qBittorrent
chart. Flux applies that setting on initial deployment and during upgrades.
Restore the existing workload Secrets and storage through the usual recovery
procedure. Flux applied the recovery revision and qBittorrent became Ready.
Gluetun obtained a Proton port lease, qBittorrent listened on that port, and
Radarr and Sonarr passed their configured connection tests.
[Published chart change](https://github.com/jtmb/branconet-charts/commit/f62a31c9738406d394a37379bdeb23b9185b09a8)
