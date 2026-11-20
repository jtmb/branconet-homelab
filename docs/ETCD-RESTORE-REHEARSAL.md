# Offline etcd restore rehearsal

**State:** design only. This document records a private, offline rehearsal for a future fresh control-plane backup. No backup, credential, restore, or production system was accessed to write it.

## Purpose and result levels

This drill implements only the etcd restore precondition in the [LAN resilience plan](LAN-RESILIENCE-AND-MCP-PLAN.md). It restores the snapshot from the existing control-plane backup format into a disposable, isolated, single-member etcd instance. It proves that the encrypted artifact can be opened with the protected operator identity, that the snapshot restores with the exact etcd tools represented by the backup, and that recovered Kubernetes records can be read without printing object values.

Record two distinct outcomes:

1. **etcd data restore:** snapshot integrity passes, an isolated etcd member starts, its health and revision are readable, and non-secret object records plus Secret record payloads are present. Secret values, keys, object names, certificates, and configuration contents are never printed or saved to the drill receipt.
2. **API decryption check:** if the full recovery gate requires proof that the captured Kubernetes encryption configuration can decrypt stored Secrets, start only an isolated API server against that restored etcd. Read objects through the local API and return counts/booleans only. An etcd-only pass does not prove this API layer.

Neither outcome changes or joins the live cluster.

## Current preflight note

The coordinator's read-only preflight on 2026-11-07 reported the live control-plane API endpoint as `192.168.0.4:6443`, three kubelets at v1.37.2, and the single `etcd-masternode` image as `registry.k8s.io/etcd:3.7.3-0` with digest `sha256:0d27b9478551f431f82d1e0ddb6c87ad07ebae8b904c637f3a99213349523910`. Recheck all of this immediately before any rehearsal.

The current `control_plane_backup` Ansible source asserts etcd `3.7.0-0` and digest `sha256:6ecefbe2510c4a30573a62a4d6dd175acf881ca67003fcd91849a16df7a724d5` [role defaults](../k8s-rewrite/ansible-playbook/roles/control_plane_backup/defaults/main.yml) [role tasks](../k8s-rewrite/ansible-playbook/roles/control_plane_backup/tasks/main.yml). That pin does not match the observed live image. The local backup role now matches the live declared image, runtime digest and both embedded tool versions. A fresh backup and offline restore still need execution and separate receipts. The exact etcd image and embedded `etcdctl`/`etcdutl` used for a future drill must match the freshly captured backup receipt's source identity.

The backup playbook passed Ansible syntax validation after the pin update. The existing controller has the pinned age executable and Ansible runtime. The live backup helper requires its privileged snapshot and recovery-file reads. The restore requires a separately verified offline Linux guest. The current Windows session cannot inspect Hyper-V, and WSL has no QEMU system binary or KVM device.

The existing post-upgrade encrypted backup matches the current etcd image and its receipt SHA-256. The receipt reports successful archive authentication, snapshot status and snapshot footer checks at creation. Its restore flag is false. Preserve it as historical recovery material and obtain a fresh snapshot for the rollout gate.

A fresh encrypted backup completed and its archive SHA-256 matches its receipt. The pinned registry image resolved to the Linux amd64 manifest, every layer matched its digest, and all three etcd executables were present. WSL separately passed the loopback-only network namespace, private no-swap tmpfs, and transient cgroup checks for zero swap and core dumps. The combined restore must enforce those controls before opening the archive.

The first WSL rehearsal restored the fresh archive into a new single-member etcd cluster. The restored snapshot matched its recorded hash, revision, key count and size. The loopback endpoint passed mutual TLS and served the expected namespace record and a nonempty Secret record payload. The isolated process and RAM-backed filesystem exited after verification. This run exercised raw data recovery at the original revision. A second isolated restore applied a rehearsal bump of one billion revisions and verified that a read at the original revision failed as compacted. The pinned Kubernetes API server authenticated over TLS and returned data for a Secret whose matching etcd record carried the encryption marker. No Secret identifiers or values were emitted. The bump used for an actual recovery must still be sized from the age and write activity of the recovery snapshot.

The three-member WSL rehearsal restored the same snapshot into three separate data directories with an isolated cluster identity and rehearsal-only TLS credentials. All three members became healthy. After the elected leader stopped, both survivors served the same recovered namespace record at the snapshot revision. The restarted leader rejoined and all three endpoints became healthy again. The rehearsal processes and their private RAM-backed filesystem exited successfully.

## Artifact and tool contract

Use only a **fresh, completed** output from `playbooks/control-plane-backup.yml`: its `control-plane.tar.age` and metadata-only `receipt.json`. The existing archive contains `manifest.json`, `snapshot.db`, and the captured `/etc/kubernetes` recovery files. Keep the source archive and its original receipt unchanged. The backup helper currently sets `restore_verified: false`; add any rehearsal result to a separate metadata-only drill receipt rather than editing the backup receipt. See the [Ansible control-plane backup notes](../k8s-rewrite/ansible-playbook/README.md#separate-control-plane-backup-before-master-maintenance) and [backup helper](../k8s-rewrite/ansible-playbook/roles/control_plane_backup/files/control_plane_backup.py).

Before decrypting, require `status=completed`, successful authenticated-archive, snapshot-status, and snapshot-footer checks, and matching archive SHA-256 and source image digest in the receipt. Confirm the snapshot status values and snapshot hash later match the receipt. Use the already-qualified age v1.3.2 executable and its recorded SHA-256, plus the existing protected operator identity. Do not copy the identity into this repository, put it in the receipt, or show it in command output.

The source helper verifies an artifact when it creates it; it is not an offline restore command and invokes the live master. Do not invoke the backup runner for this rehearsal. The restore procedure below uses the existing artifact and pinned age, `etcdutl`, `etcd`, and `etcdctl` tools, plus an ephemeral Python standard-library verifier in the private VM.

## Isolation and handling

Run the drill in a disposable Linux VM with no route to the LAN, production nodes, NAS, internet, or cluster DNS. Disable all non-loopback network interfaces at the hypervisor boundary; do not rely only on a guest firewall. Do not mount a production share, production container socket, kubeconfig directory, or host `/etc/kubernetes`. Do not run kubelet, kubeadm, controller-manager, scheduler, Flux, or application workloads for the etcd-only level.

Use a private, mode-0700 RAM-backed work directory with swap and core dumps disabled. Copy in the archive and metadata receipt read-only. Make the exact etcd image by the digest in the fresh receipt available inside the VM before disconnecting it; do not pull an unpinned image during the drill. If that exact image/tool digest is unavailable, stop. Disable shell tracing and history. Keep decrypted files, etcd data, private keys, and all response bodies inside the VM's private work directory; never send them to a terminal, CI log, Windows host, or persistent share.

Before extraction, stream-decrypt through EOF so age authenticates the complete ciphertext. Verify archive member names, types, sizes, and hashes against `manifest.json` in memory. Accept only the exact expected regular files: `snapshot.db`, `manifest.json`, and the declared `etc/kubernetes/` recovery files. Reject absolute paths, `..` components, links, devices, duplicates, undeclared members, and any hash mismatch. Write the accepted files with restrictive permissions into the private work directory; do not use an unchecked bulk `tar -xf` against the decrypted stream.

## Single-member etcd restore

The recovery image must provide the same `etcdutl` and `etcd` build recorded for the fresh snapshot. Recheck `etcdutl snapshot status` on the staged snapshot and compare its hash, revision, key count, and size with the backup receipt. Stop on any mismatch. Do not pass `--skip-hash-check`; the backup is made with `etcdctl snapshot save` and is expected to carry its integrity hash.

Because Kubernetes watches can retain informer state from a newer revision, use `--bump-revision` and `--mark-compacted` for the rehearsal, following the [official etcd v3.7 recovery guidance](https://etcd.io/docs/v3.7/op-guide/recovery/). Before starting, select and record a bump value that exceeds the conservative upper bound on writes since the snapshot. Derive that bound from the snapshot age and measured peak write rate. If the needed bound cannot be established, the drill may demonstrate raw etcd restore but must not be called a Kubernetes-ready recovery rehearsal.

Restore to a new directory and new logical cluster identity. For the single-member drill, use a unique name and token and loopback-only peer URL:

```sh
RESTORE_NAME=drill-1
RESTORE_TOKEN=<unique-per-drill-token>
RESTORE_CLUSTER="${RESTORE_NAME}=https://127.0.0.1:2380"

etcdutl snapshot restore "$PRIVATE_ROOT/snapshot.db" \
  --name "$RESTORE_NAME" \
  --data-dir "$PRIVATE_ROOT/etcd-data" \
  --initial-cluster "$RESTORE_CLUSTER" \
  --initial-cluster-token "$RESTORE_TOKEN" \
  --initial-advertise-peer-urls https://127.0.0.1:2380 \
  --bump-revision "$REVIEWED_REVISION_BUMP" \
  --mark-compacted
```

Start only that etcd member, with its client and peer listeners bound to `127.0.0.1`. Use the archived etcd CA, server/peer certificates, and healthcheck client certificate from the private extracted tree. The etcd launch configuration must use the same restore name, data directory, initial cluster, and token as the restore command, with `--initial-cluster-state=new`. Require normal certificate verification. If a certificate does not validate for the loopback endpoint, stop and record the TLS check as failed; do not disable verification or expose a listener on the source node's LAN address. The API endpoint and peer URLs used here are local drill values, not production identities.

The listener contract is:

```text
client listen/advertise: https://127.0.0.1:2379
peer listen/advertise:   https://127.0.0.1:2380
client TLS: server.crt/server.key, etcd CA, client-certificate auth enabled
peer TLS:   peer.crt/peer.key, etcd CA, peer-client-certificate auth enabled
```

Start `etcd` from the same pinned image with those settings and the archived file paths. A launch has this shape:

```sh
etcd \
  --name "$RESTORE_NAME" \
  --data-dir "$PRIVATE_ROOT/etcd-data" \
  --listen-client-urls https://127.0.0.1:2379 \
  --advertise-client-urls https://127.0.0.1:2379 \
  --listen-peer-urls https://127.0.0.1:2380 \
  --initial-advertise-peer-urls https://127.0.0.1:2380 \
  --initial-cluster "$RESTORE_CLUSTER" \
  --initial-cluster-token "$RESTORE_TOKEN" \
  --initial-cluster-state new \
  --cert-file "$ETCD_PKI/server.crt" --key-file "$ETCD_PKI/server.key" \
  --trusted-ca-file "$ETCD_PKI/ca.crt" --client-cert-auth \
  --peer-cert-file "$ETCD_PKI/peer.crt" --peer-key-file "$ETCD_PKI/peer.key" \
  --peer-trusted-ca-file "$ETCD_PKI/ca.crt" --peer-client-cert-auth
```

Do not mount the host's original `/var/lib/etcd`, use its systemd unit, or modify any captured manifest in place. Use the archived `healthcheck-client.crt` and key plus the etcd CA for client probes. Both client and peer certificate names must validate for their loopback URLs; otherwise stop rather than weakening TLS.

Run `etcdctl --endpoints=https://127.0.0.1:2379 --cacert="$ETCD_PKI/ca.crt" --cert="$ETCD_PKI/healthcheck-client.crt" --key="$ETCD_PKI/healthcheck-client.key" endpoint health` and the corresponding `endpoint status --write-out=json` against the loopback endpoint. Keep probe output inside the private VM; record only success/failure and numeric status fields. Require the restored revision to equal the source snapshot revision plus the reviewed bump, and require the endpoint to report one healthy member.

Prove data without disclosing it:

- Query the known non-secret `/registry/namespaces/default` record. A local in-memory verifier must assert exactly one matching key with a non-empty value and emit only `default_namespace_record=present`.
- Query `/registry/secrets/` in memory. Assert the response contains Secret records and at least one non-empty value payload. Emit only record counts and `secret_payloads_present=true`; do not emit keys, names, values, hashes of values, or serialized JSON. Do not persist the response. A non-empty raw etcd Secret payload proves the data was recovered, not that Kubernetes successfully decrypted it.
- Keep all `etcdctl` output piped directly to the verifier, with no `tee`, shell tracing, debug logging, or saved response files. Record command exit status and sanitized counts only.

## API-level decryption sub-gate

For a full Kubernetes recovery result, perform an additional read-only API check in the same isolated VM. Start only the API server using private copies of the captured manifest and configuration, an image available by a verified digest, the restored loopback etcd endpoint, and the captured `encryption-config.json`. Bind the API listener to loopback only. Do not start controllers, scheduler, kubelet, or any reconciler. Use a private copy of the admin kubeconfig with a loopback/localhost URL and require its CA and server certificate to validate normally; if the existing certificate cannot validate the local alias, stop this sub-gate rather than use insecure TLS.

Issue only read-only GET/list requests. Pipe the Secret list response directly into a local in-memory verifier that checks that at least one Secret object has metadata and decrypted non-empty `data`, then prints only aggregate counts. Never print names, keys, or values, and never write response bodies to disk. Configure any API audit output to metadata-only, or leave payload logging disabled. If the API process cannot be safely started from the archived state without adding unqualified images or weakening TLS, mark this sub-gate unrun; do not claim encryption-key/API recovery from the etcd-only result.

This sub-gate tests one API server reading one restored etcd member with the captured encryption configuration. It is not BORTUS recovery acceptance, workload restore, application health, or a live cluster recovery.

## Separate three-member and production acceptance

This drill restores a **new logical etcd cluster** from a snapshot. Snapshot restore replaces member and cluster identity. It does not add a voter to the currently running cluster, rehearse kubeadm control-plane join, or prove a hostname migration. Do not use `etcdutl snapshot restore` as a substitute for the approved in-place stacked-etcd membership transition, and never run it against a production data directory. The plan's per-node identity, storage, workload, Flux, and rollback checks remain separate.

A later offline three-member disaster-recovery test can restore the **same snapshot** separately into three private data directories, each with a distinct member name and peer URL, while using one shared new initial-cluster definition and a unique shared cluster token. Use an isolated test network and test-only peer certificates. Confirm all three members become healthy, then stop exactly one member and verify the remaining two retain quorum and serve the same keyspace; restart it and confirm all three recover. This proves only that a new three-member cluster can be formed from one backup and tolerate one member loss.

It does not prove the future 1-to-2-to-3 membership transition on the existing nodes. During a live two-voter stage, quorum is two, so that intermediate cluster has no voter-loss tolerance. Do not remove or rename another member until the actual cluster reports all three intended voters healthy and the stable API works. Verify the observed member list and quorum after each staged join before proceeding.

The current API endpoint is still observed as `192.168.0.4:6443`. Before promoting either worker, separately stage `k8s-api.branconet.lan` outside cluster DNS, include it in kubeadm's `controlPlaneEndpoint`, API certificate SANs, and client kubeconfigs, then prove that this stable name reaches the current single API server with normal CA/SAN verification. That pre-promotion check proves name/TLS/reachability to the current backend only; a single voter cannot demonstrate failover. After all three intended control-plane voters are healthy, prove API access and etcd quorum while one control-plane node is unavailable, then restore it and recheck health before the next node operation. A loopback restore proves nothing about the LAN endpoint, DNS independence, API load balancing, API-server certificate SANs, or endpoint failover. A successful local restore cannot waive those gates.

## Receipt and cleanup

Write a separate metadata-only drill receipt containing the source archive SHA-256, source etcd image digest, snapshot hash/revision/key count/size, exact tool digests, selected revision bump, isolation identifier, timestamps, exit statuses, aggregate non-secret object counts, and whether the etcd and API sub-gates passed. Do not copy any backup content, keys, certificates, object names, or response values into the receipt. Never change the original archive or backup receipt.

After capturing sanitized evidence, stop the local API server/etcd if running and destroy the disposable VM and its private work area. Keep only the original encrypted backup and the small metadata-only drill receipt. On failure, record the exact failing step and sanitized error first, then destroy the secret-bearing VM; do not retain a plaintext disk image as generic evidence. Recheck that no mounted disk or running process still references the VM before removing it.

## Acceptance checklist

- [ ] Fresh completed backup artifact and receipt match the current live etcd image digest.
- [ ] Pinned age authentication, member/path allowlist, file hashes, and etcd snapshot status checks pass.
- [ ] Snapshot restores into a new private etcd data directory with a reviewed revision bump and compaction marker.
- [ ] Loopback-only etcd health/status pass with normal certificate validation.
- [ ] Non-secret namespace presence and Secret payload presence are verified in memory; output contains counts/booleans only.
- [ ] API decryption sub-gate passes, or is explicitly recorded as unrun with no claim of API-level recovery.
- [ ] Separate three-member restore and live membership/quorum transition remain open until independently rehearsed and accepted.
- [ ] Before promoting workers, the stable API name reaches the current API server and validates TLS without a bypass.
- [ ] Only after all three intended voters are healthy, API failover and quorum are verified with one control-plane node unavailable.
- [ ] Hostname migration, storage, workloads, and Flux remain separate rollout gates.
- [ ] Disposable plaintext workspace is destroyed and only the encrypted backup plus sanitized metadata receipts remain.
