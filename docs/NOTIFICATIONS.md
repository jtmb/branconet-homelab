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

The exposed subscriber password was rotated again. The replacement is
stored under `BrancoNet/ntfy/bortus-subscriber` in the owner's Windows
Credential Manager. The agent verified the replacement on the new Ready
ntfy pod and read the exact private test notification over trusted HTTPS.
This was not a personal receipt by the owner. The previous bcrypt verifier
was replaced; the exposed plaintext was not reused in a live negative test.

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
threshold as the API-object scan. (Fixed 2026-11-18: the sender's event
validator rejected the `tls-endpoint` resource, so every such alert stayed
pending forever behind its retry backoff and never reached the topic.
Verified end to end with a clearly-labeled synthetic warning: monitor row →
sender → ntfy → subscriber, delivered within one 60s loop.)

The monitor includes TLS endpoint rows in the published snapshot. The
first D3 dashboard image rejected those rows and could show “Offline”
despite a fresh heartbeat. The deployed follow-up accepts the fixed
node01–node03 API server and kubelet records separately from the required
Kubernetes inventory sources. The signed-in agent browser verified
“Monitoring” and “delivery confirmed by the sender” against the production
snapshot. This is sender confirmation, not personal receipt.

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

## Unattended kubelet certificate renewal — all three machines (2026-11-18)

One approver, `bortus-csr-controller.service` on node02, renews kubelet
serving certificates for **node01, node02 and node03**. It approves a request
only when the requesting machine (as recorded by the API server) is on its
list, the request names exactly that machine's own name and address, and that
machine's own switch is on.

```text
request → which machine sent it? → on the list? ──no──→ recorded, never approved
                                        │ yes
                    exactly its own name + address? ──no──→ recorded, refused
                                        │ yes
                          its switch: watch-only → recorded only
                                      approve    → approved once
```

- List and switches: `/etc/bortus-csr-controller/enrollment.json` on node02
  (version 2), written only by
  `k8s-rewrite/ansible-playbook/playbooks/csr-controller-multinode.yml`
  (`-e '{"csr_approve_nodes": [...]}'`). The previous file is kept at
  `/var/backups/bortus-csr-controller-enrollment.previous.json`.
- Per-machine test: `scripts/migration/qualify-node-csr-rollout.py`
  `watch|renew|verify node01|node03`.
- Proof on 2026-11-18: node01 and node03 each passed watch-only (own request
  eligible but not approved; a request also claiming another machine's
  address refused as `sans_invalid`), then a real renewal approved by the
  service with no operator command and served by the machine (node01
  `csr-rrqth`, node03 `csr-xlskq`). node03's DHCP and DNS were checked after.
  node02 kept serving its existing certificate.
- Two approver bugs fixed at the same time: the host's cryptography 3.4.8
  made the "issued certificate is correct" check always fail (now passes:
  `issuedVerified` 0 → 3), and a definite approval failure crashed on an
  undefined name instead of releasing the request for retry.
- The controlled-rotation tool (`qualify-kubelet-rotation.py`) takes a
  **per-attempt** backup under `/root/bortus-kubelet-pki-backup/<attempt>/`
  and restores only if *that attempt* actually changed the serving files:
  a pre-flight refusal leaves the host untouched (verified live: refusal
  with zero kubelet restarts and no backup directory), and a failure after
  the files change restores exactly that attempt's own certificate,
  including the `kubelet-server-current.pem` symlink (verified live with
  an aside→restore round trip returning the identical fingerprint). A
  failed rollback is recorded loudly, never swallowed.
- Rollback for one machine: re-run the play without it in
  `csr_approve_nodes` (it returns to watch-only); `[]` returns all three to
  manual approval.
