# Maintained CoreDNS adoption

Accepted operational checkpoint: October26,21:30UTC. The full five-milestone
migration/security goal remains active; WordPress database/plugins, Plex,
remaining platform/fleet updates, owned publication, trusted TLS and final IAB
are still open.

Official upstream CoreDNS1.15.0 replaces the temporary bespoke image:
`docker.io/coredns/coredns:1.15.0@sha256:0a9d8c8ddf34347eb59aad9a8784f0710de88d6d112726d11d271f9bc6daca26`.
The amd64 manifest is
`sha256:3429e3bbffb1e839470c4a3541d4d78aca84a1394c75a539d0200c58c63196ac`.
The deployed binary reports1.15.0 / Go1.27.3 / commit `a6fde3f`.
The [upstream release](https://github.com/coredns/coredns/releases/tag/v1.15.0)
and exact tag bind it to `a6fde3fe339c6ec848447e11cc9796be8c97b4e0`.

CoreDNS remains the existing kubeadm-owned Deployment
`adee85f5-3155-4be2-bc2f-8a602b15c17d`. The opt-in
[Ansible playbook](../k8s-rewrite/ansible-playbook/playbooks/coredns-patch.yml)
and [fixed controller](../scripts/migration/patch-coredns.py) maintain this
platform component; the private application chart publisher is unchanged at
`4fb19f9ec5620b3605a28c126e07c897004a78a9`. GitHub Actions was verified off.
No new publisher, third-party rebuild or registry was introduced.

The actual rollout changed only the Deployment image. Its Corefile, DNS Service
UID/spec, Deployment UID, two-replica count, resource settings, capabilities and
mounts remain. Two fresh replicas passed18 TCP/UDP checks: cluster DNS Service
plus each Pod, queried for Kubernetes, the WordPress database and example.com.
Service answers were parsed and compared against the actual Kubernetes Service
addresses. Pod /health and /ready passed. The actual Ansible playbook then ran
successfully with changed0, unreachable0 and failed0; its independently observed
before/after DNS checks passed again. No synthetic fixtures replace this evidence.

The immutable-image scan retained11High,6Medium and4Unknown rows, with no CISA
KEV match. All11High rows identify the CoreDNS module as the Go pseudo-version
`v0.0.0-20261021021732-a6fde3fe339c`; their fixed ranges end at1.14.7 or earlier.
An isolated no-data Pod proved the official binary's actual1.15.0 version,
Go1.27.3 and matching release commit. The controller permits this exact
module/commit/fixed-range attribution and refuses any other available Critical/
High fix. It preserves every raw row and labels the conclusion as a version
inference. No scanner exclusion, ignore rule, altered database or suppression
was used. This is not a claim that every possible vulnerability or zero-day is absent.

The first version probe dropped every capability and could not execute the
upstream capability-bearing binary (EPERM). The qualified probe used the same
existing NET_BIND_SERVICE-only capability as production, with no new production
permissions. Neither probe mounted data, Secrets or an API token; both had a
Pod-specific deny-all network policy. The original failure's complete Pod spec,
status, log and policy were retained locally and in the authenticated NAS archive
before its exact resources were retired. The successful probe was also retired
by UID. Four older unrelated failed diagnostic Pods remain protected.

The initial Ansible invocation failed before any task: its in-process RPC socket
could not start under the long real temporary path. The retained recovery used
an inherited open-directory descriptor as a short `/proc/self/fd/...` name,
verified to resolve to the same F-backed directory/device. No filesystem alias
or additional output root was created. Executed command modules receive the full
real TMPDIR/TEMP/TMP from the role, preventing an invalid inherited-descriptor
fallback. The retained runner is
`operator-control/run-coredns-ansible-idempotence-r2.py`; its command/extra-vars,
physical-path proof, failed log and successful log remain recovery evidence.
The three empty temporary directories were reconciled after successful exit.

The fixed controller preserves the existing image-only UID/resourceVersion
preconditions. If rollout or DNS verification fails, it restores the old image
only when the live specification still matches its own exact change, then
checks the original DNS behavior. Concurrent operator changes are never overwritten.
Its previous controller source and original deployment/configuration remain intact.

Recovery evidence lives under the single existing F-backed task root:

- `upstream-coredns-20261026`: complete before/current/version/DNS/Ansible evidence,
  original failure, accepted patch receipts and exact temporary-resource retirement.
- `control-source/upstream-coredns-20261026`: executed controller and version probe,
  legacy source, exact role defaults/tasks and playbook.
- `security-review-20261026/apps-coredns-current-r3-0`: raw scan, successful receipt,
  unchanged pinned tool/feed provenance and version-attribution source.
- `operator-control/coredns-upstream-metadata-receipt.json`: every archive member
  and SHA256. The409908-byte age archive has SHA256
  `c28c6c3fd9a2d30260227b0c0ec8ce68d1f44ff6fc9ffa8ba0027c6dc4031b75`.
  Full NAS read-back and age authentication passed using the existing recovery
  destination/key backup. Prior cumulative archives were not duplicated inside it.

Final health:3Ready nodes without pressure,56Bound PVCs,34Ready HelmReleases,
all Kustomizations Ready,91Running Pods and42Longhorn volumes total with every
attached volume healthy. The image/owner inventory covers68distinct images and
306controllers. No application Secret, data claim or NAS media changed.
[Exact cleanup and retained exceptions](TASK-OUTPUT-INVENTORY.md#coredns-reconciliation-october26-2130utc).

