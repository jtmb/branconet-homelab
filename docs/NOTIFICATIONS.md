# Certificate monitoring and ntfy notifications

## Components

| Piece | Location | Role |
|---|---|---|
| `private-ntfy` Deployment | `bortus-notifications` namespace, node01 | ntfy 2.38.1 (fixed CVE-2026-4738 zlib image), serves `https://notifications.branconet.lan` |
| Monitor | `bortus-certificate-monitor.service` on node02, UID998 | Scans cert-manager Certificates + CSRs (and TLS-endpoint expiry, see below) via scoped kubectl; durable SQLite outbox |
| Sender | Same host, same UID | At-least-once delivery from the outbox to ntfy |
| Watchdog | `bortus-certificate-watchdog.service` on node03, UID997 | Detects monitor outage via its Lease/heartbeat, delivers `missed`/`recovered` events independently |
| CSR controller | node02, SA `bortus-csr-controller` | Unattended approval of kubelet-serving CSRs — **node02 only**, see limitation below |

## ntfy auth model

- `auth-file` backed by `/auth/user.db`, but `/auth` is an **emptyDir**.
  Users are provisioned at container start from `NTFY_AUTH_USERS`
  (and tokens from `NTFY_AUTH_TOKENS`), sourced from the **native Secret**
  `private-ntfy-auth` — never from Git. A password/token change made with
  `ntfy user ...` inside the running pod **vanishes on restart**; it must be
  written into the Secret. Use `scripts/migration/update-ntfy-auth-user.py`
  (see the `native-secret-change` skill) — never hand-edit the Secret.
- Entry format is **`name:hash:role`** — omitting `:role` crash-loops the
  server (`invalid auth-users ... expected format`). The script validates
  this before writing.
- `auth-access` (declarative, in Git) grants:
  - `bortus-monitor-publisher` → write-only `bortus-certificates`
  - `bortus-watchdog-publisher` → write-only `bortus-monitor-health`
  - `bortus-subscriber` → read-only both topics
  - `auth-default-access: deny-all` — nothing is readable without a login,
    including through the public web app shell.
- Web UI is enabled (`web-root: /`, `enable-login: true`,
  `enable-signup: false`). The app shell itself loads for anyone, but every
  topic read still requires authentication (`deny-all` is unaffected by
  serving the UI).

## Publishing a human-visible test notification

The server treats the HTTP **body** as the message text; a title is a
**separate header**, not a JSON field in the body:

```
POST /bortus-certificates
Authorization: Bearer <monitor-token>
Title: Some title
Tags: white_check_mark
Priority: 3

Plain text message body here.
```

Posting a JSON blob as the body (`{"title": ..., "message": ...}`) publishes
correctly (HTTP 200) but renders as a raw, untitled JSON string in every
client — this happened once in production (2026-11-17) and is left visible
in the topic history as a reference example of the failure mode.

## Pod restarts on config change

Flux does **not** restart a pod when only a ConfigMap or Secret changes —
only a change to the pod **template** triggers a new ReplicaSet. The
Deployment carries a `checksum/server-yml` annotation (hash of the
ConfigMap's exact `server.yml` content) specifically so that editing
`server.yml` forces a restart; a test in
`scripts/test_certificate_candidates.py` asserts the annotation always
matches the current ConfigMap content. **Native Secret changes are
out-of-band on purpose** (see above) and are restarted directly by the
rotation script, not by this checksum.

## Monitor coverage

The monitor's `scan()` covers Kubernetes API objects (cert-manager
`Certificates`, `CertificateSigningRequests`). It does **not** have host
filesystem or root access, so kubeadm/kubelet host PKI files are not
directly readable by it. `scan_tls_endpoints()` extends coverage to those
certificates **without** granting host access: it opens a live TLS
handshake to each node's own `:6443` (apiserver) and `:10250` (kubelet) and
reads the certificate currently being served — the same low-privilege
"observe what's actually presented" approach already used for kubelet
CSR verification. Alerts for TLS-endpoint expiry flow through the existing
outbox/sender/ntfy path and share the same `expiryWarningDays` policy
threshold as the API-object scan.

## Notification delay — known contributing factor

A 2026-11-16 delivery took 3972 seconds (66.2 minutes) across six failed
attempts before succeeding. Diagnosis (not reproduced under load) points to
the sender's inner HTTPS timeout (originally 3s) racing its cgroup CPU quota
(`CPUQuotaPerSecUSec=50ms`, i.e. 5%): measured full child runs took
1.8-2.4 seconds against that 3-second budget while the actual network round
trip measured ~55ms — the gap is CPU scheduling delay, not network latency.
The inner timeout was raised to 8 seconds (still inside the sender's fixed
10-second whole-process child deadline). This is a mitigation for the
strongest supported cause, not a confirmed, reproduced fix — if long delays
recur, check `transportKind`/`transportStage` on the failed attempt before
assuming the same cause.

## Known limitation: CSR approval is node02-only

`k8s-rewrite/ansible-playbook/playbooks/csr-controller-host.yml` is
hardcoded to `hosts: workernode1` (node02) with an `enrollment.json` that
only trusts `name: node02, ips: [192.168.0.6]`. **node01 and node03 kubelet
serving-certificate renewals are not covered** — their CSRs will sit pending
until an operator manually approves them. Extending coverage to the other
two nodes is a new privileged-service deployment (its own identity, RBAC,
credential broker, systemd units), not a small fix — treat it as a separate,
explicitly-authorized task (see the `node-host-ops` skill).
