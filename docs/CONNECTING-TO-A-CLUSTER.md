# Connecting to a Cluster

How to connect to and interact with the Branconet Kubernetes cluster from different environments.

## Prerequisites

- SSH key at `~/.ssh/id_ed25519` (or configured via `ansible_ssh_private_key_file` in DB)
- Sudo password stored in Botrus DB (`ansible_become_password`)

## Option 1: Botrus Dashboard (Recommended)

The dashboard at `http://localhost:4000` provides a web UI for cluster management.

### Prerequisites

```bash
cd k8s-rewrite/front-end
npm install
npm run dev
```

Set the secrets token:
```bash
export BOTRUS_SECRETS_KEY="your-secure-random-token"
```

### What the Dashboard Does

The dashboard uses local kubectl exclusively — `~/.kube/config` is required.
There is no SSH fallback on kubectl hot paths.

**One-time kubeconfig bootstrap:**
At module load, the dashboard tries to ensure a kubeconfig exists via
`ensureKubeconfig()` (see `src/lib/kubeconfig.ts`):

1. If `~/.kube/config` already exists → done.
2. If `clusterState.kubeconfig` is stored in the DB (from a deploy) → write to disk.
3. Otherwise, SSH to the master node, `sudo cat /etc/kubernetes/admin.conf`,
   write to `~/.kube/config`.

Once the kubeconfig is in place, every kubectl call runs locally:
```typescript
// k8s.ts → kubectlJSON()
kubectl --kubeconfig ~/.kube/config get nodes -o json
```

**Deploy auto-writes kubeconfig:** When a deployment playbook succeeds, the
dashboard captures the kubeconfig from the master node via SSH and writes it to
both the database AND `~/.kube/config` — so subsequent page loads get local
kubectl automatically.

## Option 2: kubectl with kubeconfig

### Copy kubeconfig from master node

```bash
# From the master node
scp brajam@u1:/etc/kubernetes/admin.conf ~/.kube/config

# Edit the server address if needed
sed -i 's/server: https:\/\/.*:6443/server: https:\/\/192.168.0.25:6443/' ~/.kube/config
```

### Verify connection

```bash
kubectl cluster-info
kubectl get nodes
```

### Set up aliases (optional)

Add to `~/.bashrc`:
```bash
alias k='kubectl'
alias kgp='kubectl get pods'
alias kgpa='kubectl get pods -A'
alias kgn='kubectl get nodes'
alias kga='kubectl get all'
alias kd='kubectl describe'
alias kl='kubectl logs'
alias klf='kubectl logs -f'
alias ke='kubectl exec -it'
alias kns='kubectl config set-context --current --namespace'

# Per-app shortcuts
kplex='kubectl -n plex'
alias kflux='kubectl -n flux-system'
alias ktraef='kubectl -n traefik'
```

## Option 3: SSH to Master Node

```bash
ssh brajam@u1

# kubectl as root
sudo kubectl --kubeconfig=/etc/kubernetes/admin.conf get nodes

# Or copy kubeconfig to your user
mkdir -p ~/.kube
sudo cp /etc/kubernetes/admin.conf ~/.kube/config
sudo chown $(id -u):$(id -g) ~/.kube/config
kubectl get nodes  # now works without sudo
```

## Option 4: VS Code Remote (if applicable)

If using VS Code with the Remote-SSH extension:

1. Add the master node to `~/.ssh/config`:
   ```
   Host u1
       HostName 192.168.0.25
       User brajam
       IdentityFile ~/.ssh/id_ed25519
   ```

2. Connect via Remote-SSH to `u1`

3. Copy kubeconfig on the remote:
   ```bash
   sudo cp /etc/kubernetes/admin.conf ~/.kube/config
   sudo chown brajam:brajam ~/.kube/config
   ```

4. Install the Kubernetes extension in the remote VS Code

## Cluster Architecture

```
                     ┌──────────────────────┐
   Your Machine      │   Master Node (u1)    │
   (dashboard /      │   192.168.0.25        │
    kubectl)         │                       │
       │             │   kube-apiserver      │
       │ SSH         │   kube-controller     │
       │ or kubectl  │   kube-scheduler      │
       │             │   etcd                │
       ▼             │   CoreDNS             │
   ┌───────┐         │   Traefik Ingress     │
   │  API  │────────▶│   Longhorn            │
   └───────┘         │   FluxCD              │
                     └──────────┬───────────┘
                                │
              ┌─────────────────┼─────────────────┐
              │                 │                 │
   ┌──────────▼──────┐ ┌───────▼───────┐ ┌───────▼──────┐
   │ Worker Node (u2) │ │ Worker (u3)   │ │ Storage       │
   │ 192.168.0.27     │ │ 192.168.0.26  │ │ 192.168.0.8   │
   │                  │ │               │ │ (SMB/NFS)     │
   │ kubelet          │ │ kubelet       │ │               │
   │ kube-proxy       │ │ kube-proxy    │ │ samba shares  │
   │ CSI SMB driver   │ │ CSI SMB      │ │ nfs exports   │
   └──────────────────┘ └───────────────┘ └───────────────┘
```

## Firewall / Network

### Required ports

| Port  | Protocol | Source        | Destination | Purpose               |
|-------|----------|---------------|-------------|-----------------------|
| 6443  | TCP      | All           | Master      | Kubernetes API         |
| 22    | TCP      | Your machine  | All nodes   | SSH / Ansible          |
| 4000  | TCP      | Master node   | Dashboard   | Botrus API (lookup)    |
| 80    | TCP      | LAN           | All nodes   | HTTP ingress           |
| 443   | TCP      | LAN           | All nodes   | HTTPS ingress          |
| 10250 | TCP      | Master        | Workers     | kubelet API            |
| 8472  | UDP      | All nodes     | All nodes   | Calico VXLAN          |

### DNS

The cluster uses `.branconet.local` for ingress hostnames:
- `plex.branconet.local`
- `home-assistant.branconet.local`
- etc.

Configure your local DNS or `/etc/hosts` to resolve these to the Traefik ingress IP (usually the master node or a load balancer).

**`/etc/hosts` example:**
```
192.168.0.25  plex.branconet.local
192.168.0.25  home-assistant.branconet.local
192.168.0.25  whoami.branconet.local
```

## Troubleshooting Connections

### kubectl can't reach the cluster

```bash
# Check kubeconfig exists
ls -la ~/.kube/config

# Check API server reachability
curl -k https://192.168.0.25:6443/version

# Check if kube-apiserver is running on master
ssh brajam@u1 "sudo crictl pods | grep kube-apiserver"
```

### SSH connection refused

```bash
# Test SSH
ssh -i ~/.ssh/id_ed25519 -o ConnectTimeout=5 brajam@u1 echo ok

# Check SSH key is in authorized_keys on the node
# Re-run bootstrap role if needed
```

### Dashboard can't reach nodes (SSH fallback)

This means the dashboard machine has no `~/.kube/config` and can't SSH either. Check:
1. SSH key path is correct in `ansible_ssh_private_key_file` variable
2. Sudo password in DB is correct
3. Node IPs in DB match actual IPs

### Sudo password prompt in terminal

If running `kubectl` directly on a node prompts for sudo:
```bash
# Either copy kubeconfig to your user (preferred)
sudo cp /etc/kubernetes/admin.conf ~/.kube/config
sudo chown $USER:$USER ~/.kube/config

# Or use the become password from Botrus DB
echo '<password>' | sudo -S kubectl --kubeconfig=/etc/kubernetes/admin.conf get nodes
```
