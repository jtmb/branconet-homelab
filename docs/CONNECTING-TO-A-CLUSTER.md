# Connecting to the migration cluster

## Notification endpoint — DNS and trusted serving verified

`notifications.branconet.lan` serves TLS through the existing ingress VIP
`192.168.0.252:443`, with the existing name-constrained private root and
separate native publisher/subscriber identities. Trusted explicit-address/SNI
verification and automatic rotation's first native check passed. The serial
v4 rollout is now complete on both cluster backends and standalone node03.
Both advertised resolvers passed actual Windows LAN UDP/TCP queries; ordinary
Windows/WSL resolution returns192.168.0.252 and DNS-based trusted HTTPS returns200,
without a hosts override or address-pinned connection. Phone/PWA notification
and attended receipt remain unaccepted. Never replace both resolvers
simultaneously. Do not use
the earlier unsuitable draft `notifications.lan` or disable verification.
`proxy.branconet.lan` has a separately recorded pre-existing self-signed
dashboard trust gap; its native Secret was preserved, not counted as healthy. (Resolved 2026-11-18: proxy.branconet.lan now serves a certificate from branconet-local-ca via private-charts `flux/releases/foundation/proxy-dashboard-tls.yaml`, commit f269e31; sign-in unchanged. See docs/NETWORK-HARDENING.md.)
DNS used immutable v4: secondary first (`4a352444…`), primary second
(`8ecc9f87…`), then the standalone records-only Ansible update. All48 legacy
names and the new alias remain identical on both advertised paths:
floating `192.168.0.253` and independent `192.168.0.5`.
The scoped driver `scripts/migration/refresh-notification-dns.py` uses the
existing records-only Ansible play, then separate one-service `loopback`/`lan`
phases. It preserves existing launchers, filtering DB and DHCP invocation;
each phase refuses replay and rechecks floating DNS before/after refreshing
one service. A source/staging pass alone is not a live independent DNS pass.
`scripts/migration/verify-notification-dns.ps1` verifies the existing Windows
lease's two advertised resolvers without renewing or changing the adapter.
It checks actual UDP answer addresses, explicit TCP resolution, and ordinary
Windows DNS for the new name. Machine DNS evidence is not attended phone/
subscriber receipt.
The records-only controller uses the existing abstract AF_UNIX bootstrap from
`run-lan-dhcp.py` while keeping temp output on H. The initial RPC startup failure
was before all Ansible tasks; its separately named recovery does not overwrite
that failure or authorize replay after an uncertain remote task.
SSH multiplexing is disabled for this bounded controller, matching the existing
DHCP driver. The first abstract-RPC attempt failed before its first delegated
read on SSH ControlPath formatting (ok0/changed0); its separate no-multiplex
recovery is not permission to repeat uncertain or completed host mutations.
The policy play explicitly binds sudo to the existing in-memory migration
environment credential, matching the other managed-host plays. Its playbook
location does not automatically load the parent group-vars file. The first
no-multiplex attempt completed read-only checks then stopped for missing sudo
binding (changed0), before rendering/staging any host file; that failure remains.
Each service refresh waits up to20s for actual TCP/UDP readiness without
restarting again, then rechecks config/filter/launcher hashes and DHCP.
The standalone LAN process listens on192.168.0.5:10554; inbound LAN port53
uses the existing PREROUTING DNAT. Same-host checks use10554, and separate
node/Windows client checks must verify advertised53. Local OUTPUT to53 is
not a valid advertised-path probe. A post-restart collector mistake at this
boundary is retained; the actual successful restart is not repeated.

## Current storage/runtime - 2026-10-19 UTC

Gluster and the obsolete Docker/Swarm service/socket are stopped and disabled on all three nodes. Kubernetes uses the independent `containerd-k8s` runtime/socket shown below. Keep original brick/Docker state directories and encrypted NAS recovery archives. Legacy host CIFS mounts under `/mnt` and their boot entries are retired; those directories no longer provide NAS access. Kubernetes SMB CSI media mounts and Longhorn's native CIFS backup target remain active. NAS media stays in place under the user's confirmed scope. See [retirement operations](MIGRATION-OPERATIONS.md) and [actual evidence](../evidence/legacy-storage-retirement-20261019.json).


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
| TCP 80 / 443 | LAN to cluster ingress | Kubernetes application routes |

Pod CIDR is 10.244.0.0/16; service CIDR is 10.96.0.0/12. Calico does not use Swarm's UDP 4789 VXLAN socket. Existing resolver configuration is preserved; kubelet uses /run/systemd/resolve/resolv.conf. Validate application URLs with their actual Host headers through temporary ingress before production routing changes.

BORTUS application access is a separate deployment dependency. Its running integration must use native Kubernetes Secrets and satisfy authorization/restart tests. Development is assigned to scoped application and native-transport sub-agents; migration operations and live acceptance remain with the coordinator. Former execution chats are archived.

The delivered BORTUS container connects through its mounted service-account token and CA. Secret namespaces are explicitly allowlisted, each with get/list/create/update Roles; values are never recovered from SQLite. Explicit lookup aliases identify namespace/name/key without underscore parsing. Other dashboard/Flux/exec permissions are separate. See [BORTUS-DEPLOYMENT.md](BORTUS-DEPLOYMENT.md) and [SECRETS-ENGINE.md](SECRETS-ENGINE.md). Local operator kubeconfig and provisioning credentials remain independently available for recovery.


## TLS trust and workload mTLS - 2026-11-16

kubectl keeps the Kubernetes cluster CA (`k8s-api.branconet.lan` / `192.168.0.251:6443`). The API servers now also verify each kubelet's cluster-CA-signed serving certificate (`--kubelet-certificate-authority`), so `kubectl logs/exec/port-forward` is authenticated end to end. Kubelet serving certificates need CSR approval on rotation; see [cluster TLS](CLUSTER-TLS.md). Enrolled application namespaces (homepage, http-echo, mealie, ruckus, vaultwarden, web-apps, website-stack, whoami) plus Traefik and cloudflared use Istio ambient mTLS (namespace `istio-system`, canary `mesh-pilot`); ztunnel uses TCP 15008 between pods. Plex, Pi-hole, BORTUS, Ingenium and infrastructure namespaces are not enrolled.

## 2026-10-15 operator observation

The WSL operator kubeconfig path in the fetch example is currently absent. Do not replace another kubeconfig or copy credentials into Git to compensate. The [current read-only snapshot](../evidence/bortus-live-cluster-metadata-root-20261015.json) uses the established SSH identity with strict host checking and runs kubectl on the master, where its existing operator configuration works. No credential values are emitted. WSL restart also changes process boot identity; later local verification must distinguish original-boot records from current processes.
