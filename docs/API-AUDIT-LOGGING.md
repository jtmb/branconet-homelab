# Kubernetes API audit logging

Enabled 2026-11-19 (UTC) on all three control-plane nodes, closing audit
finding **A1** in [`audits/2026-11-18/cluster-repo-audit.md`](audits/2026-11-18/cluster-repo-audit.md).
Every request served by an API server is now recorded on that node: who made
it, from where, what object, which verb, and the result.

## What is recorded

Policy: [`k8s-rewrite/ansible-playbook/playbooks/files/kube-apiserver-audit-policy.yaml`](../k8s-rewrite/ansible-playbook/playbooks/files/kube-apiserver-audit-policy.yaml),
installed as `/etc/kubernetes/audit-policy.yaml` (root, `0600`). First
matching rule wins.

| Requests | Level | What the event holds |
| --- | --- | --- |
| `/healthz*`, `/livez*`, `/readyz*`, `/version`, `/openapi/*` | None | nothing (probe noise) |
| Lease `get/list/watch/update`; kube-proxy endpoint watches; node self-reads | None | nothing (heartbeat noise, about a third of traffic) |
| Secrets, ConfigMaps, `serviceaccounts/token`, TokenReviews — every verb | **Metadata** | who/what/when/result, **never the value** |
| RBAC Role/ClusterRole/(Cluster)RoleBinding writes | RequestResponse | the full grant, so it can be reconstructed |
| Everything else, including `exec`/`attach`/`port-forward` | Metadata | who/what/when/result; the exec command is in `requestURI` |

`RequestReceived` is omitted and `managedFields` are stripped.

The 2026-11-18 draft recorded Secret and ServiceAccount writes at
`RequestResponse`. That would have written every Secret value, and every
token issued through `serviceaccounts/token`, into a plaintext file on each
node. The applied policy keeps them at Metadata, above the only rule that
records bodies. `scripts/migration/tests/test_apiserver_audit.py` evaluates
the shipped policy with first-match semantics and fails if any credential
request would be recorded above Metadata, or if any rule other than the RBAC
rule records bodies.

## Where it is, and what it costs

- File: `/var/log/kubernetes/audit/audit.log` on each node (directory root,
  `0700`). JSON, one event per line.
- **Each API server records only the requests it served.** Clients spread
  across all three (the VIP plus in-cluster Service endpoints), so search all
  three nodes when reconstructing anything.
- Rotation: 100 MB per file, 30 gzip-compressed backups, 30 days
  (`--audit-log-maxsize=100 --audit-log-maxbackup=30 --audit-log-maxage=30
  --audit-log-compress=true`).
- Measured 2026-11-19: 1,151 bytes per event. Kept-request rates from the API
  servers' own counters before the change were about 10/s on node01 and about 2/s
  on node02 and node03. That is roughly 1 GB/day on node01 (about **3 days** of history)
  and 60–200 MB/day elsewhere (up to the 30-day cap).
- Disk ceiling: 31 files of 100 MB of events per node. Compressed backups should
  keep actual use well under 1 GB per node; the gzip ratio has **not** been
  measured yet (no rotation had happened at enablement). Check it after the
  first node01 rotation (`ls -l /var/log/kubernetes/audit`).
- The logs stay on the node. Losing a node's disk loses its audit history.
  Shipping events off-node is not set up.

## Reading it

On a node (`ssh -p 2002 james@<node-ip>`, then `sudo -i`):

```sh
# Who read or changed one Secret (current file and compressed backups)
zcat -f /var/log/kubernetes/audit/audit*.log* | jq -c 'select(.objectRef.resource=="secrets"
  and .objectRef.namespace=="bortus-secrets" and .objectRef.name=="NAME")
  | {t: .requestReceivedTimestamp, who: .user.username, verb, code: .responseStatus.code, ip: .sourceIPs}'

# Every exec session
zcat -f /var/log/kubernetes/audit/audit*.log* | jq -c 'select(.objectRef.subresource=="exec")
  | {t: .requestReceivedTimestamp, who: .user.username, pod: .objectRef.name, ns: .objectRef.namespace, uri: .requestURI}'

# RBAC grants (full body)
zcat -f /var/log/kubernetes/audit/audit*.log* | jq -c 'select(.objectRef.apiGroup=="rbac.authorization.k8s.io" and .requestObject)
  | {t: .requestReceivedTimestamp, who: .user.username, verb, kind: .objectRef.resource, name: .objectRef.name}'
```

Read-only summary without printing any event body (counts per level,
credential events, credential bodies, which must be 0):

```sh
sudo python3 scripts/migration/apiserver_audit_log_check.py /var/log/kubernetes/audit/audit.log none
```

## How it was rolled out

`python3 -B scripts/migration/run-apiserver-audit-logging.py <phase> --work-dir <H dir>`

| Phase | Effect |
| --- | --- |
| `preview` | Read-only: reads each live manifest with sudo and runs the transform in memory |
| `node02`, `node03`, `node01` | One API server each via `playbooks/apiserver-audit-logging.yml`; refuses until earlier nodes are enabled |
| `kubeadm-config` | Adds the same flags/volumes to `kube-system/kubeadm-config` (resourceVersion-guarded) once all three run them |
| `status` | Read-only: audit flags, readiness and restarts per API server, plus the kubeadm-config state |

Per node, the play checks that all three API servers answer `readyz` and that
the three nodes and three etcd members are Ready. It then installs the policy
(refusing a drifted copy) and writes an attempt-specific, byte-verified backup
outside the manifest directory. The manifest edit comes from the tested
transform in `scripts/migration/apiserver_audit.py`: it parses the manifest and
appends six flags, two mounts and two volumes, never editing existing fields.
The play then waits for a new Ready API server pod, reads a nonexistent ConfigMap
through that exact server, and requires that probe event at Metadata with no
credential body anywhere in the file. On any failure after the write it
restores this attempt's backup and stops. Re-running against an enabled node
changes nothing and repeats the verification.

node01 holds the API VIP with the highest keepalived priority, so it went
last: the VIP failed over to a verified standby while node01 restarted and
preempted back afterwards.

Result, verified by the agent (receipts under
`/mnt/h/AgentArtifacts/projects/branconet/builds/wsl-artifact-store/files/bortus-operator-recovery/audit-remediation-20261118/`):

| Node | Attempt | New pod Ready | Probe | Credential bodies |
| --- | --- | --- | --- | --- |
| node02 | `20261119T020137Z` | yes, 0 restarts | Metadata, 404 | 0 |
| node03 | `20261119T020414Z` | yes, 0 restarts | Metadata, 404 | 0 |
| node01 | `20261119T020531Z` | yes, 0 restarts | Metadata, 404 | 0 |

Afterwards: 3/3 nodes Ready, 12/12 Kustomizations and 36/36 HelmReleases
Ready, VIP back on node01. The node03 log already held 20 RBAC changes with
full bodies, and all three logs held zero Secret/ConfigMap/token bodies. The
restore path was not exercised live, because every attempt passed.

## Rollback

One node at a time, node01 last:

1. `sudo cp /etc/kubernetes/kube-apiserver.yaml.pre-audit-log.<attempt>
   /etc/kubernetes/manifests/kube-apiserver.yaml` (attempt IDs above; the file
   is the byte-verified original).
2. Wait for `kubectl --server https://<node-ip>:6443 get --raw /readyz` to
   return `ok` and the mirror pod to drop the `--audit-` flags.
3. After all three: remove the six `audit-*` extraArgs and the `audit-policy`
   and `audit-log` extraVolumes from `kube-system/kubeadm-config`, or the next
   `kubeadm upgrade` re-enables logging.

The policy file and log directory can stay; nothing reads them once the flags
are gone.
