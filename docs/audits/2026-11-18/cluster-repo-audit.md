# Cluster and repository audit — 2026-11-18

Read-only audit of `github.com/jtmb/branconet-homelab` and the three-node
cluster it supports. No cluster, chart, or repository change was made.

## Reviewed state

| Item | Value |
| --- | --- |
| Repository | `https://github.com/jtmb/branconet-homelab.git` |
| Default branch | `main` |
| Reviewed branch | `codex/seerr-cluster-security` |
| Commit | `3850836fed54d511a72345bac903f28b6621bce3` |
| Working tree | 823 modified, 907 untracked (dirty) |
| Cluster | 3 nodes, LAN `192.168.0.4/5/6`, kubeadm, Kubernetes `v1.37.2` |
| Access used | operator kubeconfig (cluster-admin), repository checkout, charts checkout |
| Observation time | 2026-11-18 19:50–20:25 UTC |

## Environment

- 3 × Ubuntu 22.04.4, containerd 2.4.2, all control-plane **and** worker.
- Stacked etcd on all three nodes; apiserver/controller-manager/scheduler on all
  three → real control-plane HA, no separate workers.
- CNI Calico `v3.33.0`; ingress Traefik `v2.11.60` (digest-pinned); MetalLB
  `v0.16.2`; storage Longhorn `v1.13.0` (CIFS backup target); cert-manager
  `v1.21.3`; Istio ambient `1.31.4`; csi-smb driver.
- 58 Deployments, 12 DaemonSets, 0 StatefulSets, 62 PVCs (all Bound), 15
  cert-manager Certificates (all Ready), 372 Secrets.
- GitOps: Flux, 12 Kustomizations and 36 HelmReleases all Ready, tracking
  `branconet-charts` at `validated@sha1:217f24f`.

## Findings

| ID | Severity | Finding |
| --- | --- | --- |
| A1 | High | API server audit logging is not enabled |
| A2 | High | Pod Security Standards unenforced in 25 of 30 namespaces |
| A3 | High | 24 namespaces have no NetworkPolicy; east-west traffic is open |
| A4 | High | Secret read/write RBAC is broad and replicated into app namespaces |
| A5 | Medium-High | Deployment manifests live in a separate repo; this repo is 1,730 files dirty |
| B1 | Medium-High | 36/58 Deployments set no limits, 31 have no readiness probe |
| B2 | Medium | Longhorn's newest backup is 3 days old; etcd snapshot schedule unverified |
| B3 | Medium | 69 pods restarted; CSI/snapshot controllers show 4–7 error restarts |
| B4 | Medium | CNI/LB/CSI images use mutable tags |
| C1 | Medium | CI actions pinned by tag, not commit SHA |
| C2 | Medium | Dockerfile runs `apt-get upgrade -y` |
| C3 | Low-Medium | 97 pods allow privilege escalation by default |
| D1 | Unverified | No local vulnerability scan; advisory coverage limited |

### A1 — No API server audit log (Confirmed)

`kube-apiserver` has `--encryption-provider-config` but no `--audit-log-path`
or `--audit-policy-file`. There is no record of who read a Secret, changed
RBAC, or opened an exec session, so A4 and any future incident cannot be
reconstructed.

**Remediated 2026-11-19** on all three API servers and in `kubeadm-config`;
see [`docs/API-AUDIT-LOGGING.md`](../../API-AUDIT-LOGGING.md). The proposed
policy below was corrected before use: it would have logged Secret values and
issued tokens. Open: logs are node-local (about 3 days of history on node01),
not shipped off-node.

### A2 — Pod Security not enforced (Confirmed)

Only `http-echo` and `whoami` (baseline), `mesh-pilot` (restricted) and
`istio-system`, `metallb-system` (privileged) carry
`pod-security.kubernetes.io/enforce`. Every application namespace — `bortus`,
`vaultwarden`, `wordpress`, `ruckus`, `plex`, `web-apps` — runs with no
admission restriction, so a chart change can silently introduce a privileged
pod.

**vaultwarden remediated 2026-11-19** (charts `6f8d1e9`): enforce `baseline`,
audit/warn `restricted`, v1.37. Verified by the agent with server dry runs
after Flux: a pod from the live Deployment template is admitted (restricted
warnings only), a privileged variant is refused with `violates PodSecurity
"baseline:v1.37"`, and the running pod was not restarted.

### A3 — No east-west policy (Confirmed presence/absence)

NetworkPolicies exist only in `longhorn-system` (6), `plex` (4), `flux-system`
(3), `bortus-notifications` (2), `mesh-pilot` (1), `ingenium` (1). Namespaces
with none include `kube-system`, `traefik`, `vaultwarden`, `wordpress`,
`ruckus`, `bortus`, `games`, `web-apps`, `cert-manager`. Calico can enforce
policy, but none is defined, so every pod can reach every other pod and the
API server.

**vaultwarden remediated 2026-11-19** (charts `0a5cf6f`, fixed in `9e6aa2c`;
design in charts `docs/NAMESPACE-NETWORK-POLICIES.md`). Verified by the agent
after Flux applied it, with the same pod (0 restarts):

| Check | Before | After |
| --- | --- | --- |
| `https://vault.branconet.lan/alive` via Traefik | 200 | 200 |
| `:8096` via node01 / node02 / node03 | 200 / 200 / 200 | 200 / 200 / 200 |
| pod → DNS, `https://github.com` (icons) | ok, 200 | ok, 200 |
| pod → API server `10.96.0.1:443`, LAN `192.168.0.6:8096` | 200, 200 | timeout, timeout |
| other-namespace pod → vaultwarden pod IP / Service | not measured | timeout (dropped) |
| other-namespace pod → Traefik route | not measured | 200 |

The first commit broke `:8096` through node01 only. On the node hosting the
pod, Calico checks policy before kube-proxy's SNAT and sees the real client,
not the node address the mesh policy sees. Adding the operator host
`192.168.0.13` (the only LAN source the node nftables profile admits) fixed
it. Next namespaces: `kube-system`, `traefik`, then the application namespaces.
`wordpress` has no pods and is the lowest priority.

### A4 — Broad Secret RBAC (Confirmed)

56 Roles/ClusterRoles can read Secrets. Notable: `bortus-secrets`
(`get,list,create,update` on the whole `secrets` resource) is replicated in
`bortus`, `bortus-secrets`, `default`, `flux-system`, `games`, `homepage`,
`http-echo`; `cert-manager-webhook` and `istiod` read Secrets cluster-scoped
by role design. Any code execution in one of those app namespaces inherits
read/write over that namespace's Secrets, including ingress TLS keys and app
credentials. `longhorn-support-bundle` is bound to `cluster-admin`.

### A5 — Source of truth split (Confirmed)

The cluster is deployed from `branconet-charts` (separate private repo). This
repository holds the app source of `bortus`, the Ansible playbooks and 1,730
uncommitted paths. Two consequences: the reviewed commit does not describe
what runs, and a large amount of unique work is uncommitted and unbacked beyond
the working tree.

### B1 — Limits and probes (Confirmed)

`36` of `58` Deployments define no resource limits, `13` no requests, `31` no
readiness probe. Without requests the scheduler cannot place fairly; without
limits one runaway pod can starve a node that also runs etcd and the API
server; without readiness a rollout can send traffic to a dead container.

### B2 — Backup freshness (Confirmed / Unverified)

Longhorn target `cifs://192.168.0.8/.../longhorn` is reachable
(`lastSyncedAt` 2026-11-18T20:20Z) with 145 backups, but the **latest backup is
2026-11-15T10:34Z** — three days old. No restore evidence was found in this
audit. etcd: the static pod uses `--snapshot-count=10000`; no
`--snapshot-save`/`etcd-snapshot` timer is visible from cluster objects, so the
host-level snapshot schedule is **unverified**.

### B3 — Restart signals (Confirmed presence, cause unverified)

69 pods report restarts. Highest: `csi-smb-controller` 7, `snapshot-controller`
6, `metallb-speaker` 5, `csi-snapshotter` 5, `csi-resizer` 4,
`kube-scheduler-node03` 4, `kube-controller-manager-node03` 4. Control-plane
restarts on a single node suggest node-level disruption (reboot, kubelet
restart, or resource pressure) rather than a component defect; that is a
hypothesis, not a finding.

### C1/C2/C3 — Supply chain and workload defaults

`kubernetes-migration.yml` uses `actions/checkout@v4` and
`actions/setup-python@v5` (mutable tags) with `permissions: contents: read`
(good). The BORTUS Dockerfile pins bases by digest, uses `npm ci`, drops to
`node`, and removes package managers — solid — but runs `apt-get upgrade -y`,
which makes the layer non-reproducible. 97 pods leave
`allowPrivilegeEscalation` at its default `true`; only the CNI and mesh pods
genuinely need host access.

## Verified strengths

- 3-node stacked etcd and 3 apiservers: no single point of failure at the
  control plane.
- All 12 Flux Kustomizations and 36 HelmReleases Ready; no suspended
  reconciliation; the recent rollout landed on the exact published digest.
- 15/15 Certificates Ready; 62/62 PVCs Bound; no node memory or disk pressure.
- Encryption at rest configured on the API server (provider type not read).
- Most application images are digest-pinned; BORTUS runs as non-root.
- No private keys, GitHub tokens, or webhook URLs found in tracked files.

## Remediation order

1. Enable audit logging with a `metadata`-level policy plus Secret and RBAC
   change capture (A1). Validation: events appear in the log file.
2. Add a default-deny NetworkPolicy plus explicit allows per namespace,
   starting with `kube-system`, `traefik`, `vaultwarden`, `wordpress` (A3).
3. Enforce Pod Security `baseline` in application namespaces and `restricted`
   where the image allows (A2/C3).
4. Reduce `bortus-secrets` to `resourceNames` it actually uses and drop it
   from namespaces that do not need it (A4).
5. Add requests/limits and readiness probes to the 36/31 deployments; start
   with anything co-resident with etcd (B1).
6. Confirm the Longhorn schedule and take a demonstrated restore; add an etcd
   snapshot timer check (B2).
7. Pin CNI/LB/CSI images by digest and CI actions by SHA (B4/C1); replace
   `apt-get upgrade` with a rebuilt pinned base (C2).
8. Commit the working tree and record which chart revision each workload
   expects (A5).

## Proposed patches

`docs/audits/2026-11-18/proposed/` holds reviewable YAML for the first three
items: `audit-policy.yaml` (superseded by the applied policy, see A1),
`default-deny-networkpolicy.yaml`, `namespace-psa-labels.yaml`. The last two
are not applied.

## Coverage limits

Not performed: image/registry vulnerability scanning, workload `exec`, log
inspection inside containers, kubelet and etcd endpoint probes, etcd snapshot
listing on the hosts, admission-controller inventory, and chart-repository
history review. Advisory check: the official Kubernetes CVE feed was read
(95 entries; none reference the 1.37 line) — that is not proof of a clean
version, and no scanner database was used.
