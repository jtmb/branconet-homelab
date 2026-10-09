# Connecting to the migration cluster

The current acceptance state is recorded in [MIGRATION_STATUS.md](../MIGRATION_STATUS.md). Target hosts are masternode 192.168.0.4, workernode2 192.168.0.5 and workernode1 192.168.0.6, with SSH user james and port 2002. Preserve hostnames and the existing WSL ~/.ssh/id_ed25519 identity.

```bash
ssh -i ~/.ssh/id_ed25519 -p 2002 james@192.168.0.4
```

After kubeadm completes, the playbook creates /home/james/.kube/config with mode 0600. Fetch it into the isolated operator directory, rather than overwrite another cluster's kubeconfig:

```bash
umask 077
mkdir -p ~/.local/share/branconet-migration
scp -i ~/.ssh/id_ed25519 -P 2002 james@192.168.0.4:.kube/config \
  ~/.local/share/branconet-migration/kubeconfig
export KUBECONFIG=~/.local/share/branconet-migration/kubeconfig
export PATH=~/.local/share/branconet-migration/bin:$PATH
kubectl get nodes -o wide
kubectl get pods -A
```

The kubeconfig already points to https://192.168.0.4:6443; keep certificate validation enabled. Do not print or commit kubeconfig credentials. Server-side kubectl may use /etc/kubernetes/admin.conf under sudo; diagnostic CRI commands must address the independent runtime:

```bash
sudo /opt/containerd-k8s/bin/crictl \
  --runtime-endpoint unix:///run/containerd-k8s/containerd.sock ps
systemctl status containerd-k8s kubelet
```

| Connection | Source and destination | Purpose |
|---|---|---|
| TCP 2002 | Operator to all three hosts | SSH/Ansible |
| TCP 6443 | Operator and nodes to 192.168.0.4 | Kubernetes API |
| TCP 10250 | Control plane to nodes | kubelet API |
| TCP 179 and IP protocol 4 | Between nodes | Calico BGP and IP-in-IP |
| TCP 30080 / 30443 | LAN to nodes | Temporary HTTP/HTTPS ingress |
| TCP 445 | Nodes to 192.168.0.8 | Existing SMB share |
| TCP 80 / 443 | Existing routing | Swarm ingress until routing cutover |

Pod CIDR is 10.244.0.0/16; service CIDR is 10.96.0.0/12. Calico does not use Swarm's UDP 4789 VXLAN socket. Existing resolver configuration is preserved; kubelet uses /run/systemd/resolve/resolv.conf. Validate application URLs with their actual Host headers through temporary ingress before production routing changes.

BORTUS application access is a separate deployment dependency. Its running integration must use native Kubernetes Secrets and satisfy authorization/restart tests. Development instructions are maintained by its separate chat; migration operations and acceptance evidence remain here.

The delivered BORTUS container connects through its mounted service-account token and CA. Secret namespaces are explicitly allowlisted, each with get/list/create/update Roles; values are never recovered from SQLite. Explicit lookup aliases identify namespace/name/key without underscore parsing. Other dashboard/Flux/exec permissions are separate. See [BORTUS-DEPLOYMENT.md](BORTUS-DEPLOYMENT.md) and [SECRETS-ENGINE.md](SECRETS-ENGINE.md). Local operator kubeconfig and provisioning credentials remain independently available for recovery.
