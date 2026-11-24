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

## Independent LAN DNS on Worker 2

Preload the exact Pi-hole image declared by the standalone resolver playbooks.
If the registry is unavailable, use a trusted node that already holds that
digest. Stream its linux/amd64 OCI image with containerd's local exporter into
Worker 2's local importer, using the Kubernetes containerd socket and namespace
on both ends. Apply the `io.cri-containerd.pinned=pinned` image label on import.
The standalone playbooks verify that CRI reports the image as pinned before
starting it. This keeps kubelet image cleanup from removing it after Pi-hole
pods move to another node.

Use `independent-dns-lan-cutover.yml` with `dns_lan_action=start` while the
original Kubernetes DNS route still answers. Verify the standalone service
can restart, then publish the chart split through the existing Flux workflow.
Run `dns_lan_action=confirm` after the split appears. It checks both DNS
transports and the retained admin route before enabling the service at boot.
For rollback, restore the original chart route first, then run
`dns_lan_action=rollback` once that route answers again.

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
procedure. See the [recovery record](../../docs/LAN-RESILIENCE-AND-MCP-PLAN.md#xr500-diagnostic-adapter)
for the tunnel, port forwarding and downloader checks.

## Full read-only ClamAV scan

`playbooks/antivirus-scan.yml` scans the existing three nodes one at a time. It
requires the installed ClamAV engine, a running `clamav-freshclam` updater, and
signature files updated within 72 hours. The scan runs at low CPU and I/O
priority and never deletes or quarantines findings. Exact per-node results,
including any detected paths, are written with restricted access outside Git.

Coverage includes each node's root filesystem with `--cross-fs=no`, the separate
local ext4 `/boot` filesystem (scanned by `playbooks/antivirus-boot-scan.yml`),
each active containerd overlay root, and the complete currently mounted Plex
Longhorn config volume. The latter's pre-change PVC/PV UIDs, PV name, retention
policy, Pod UID, container image and Plex version are recorded for post-rollout
comparison.
NAS/SMB media, NFS mounts, and other application PVCs are intentionally excluded
to avoid recursively scanning shared media and application data on every node.
This is a host/container/Plex-config scan, not a claim that those excluded
storage datasets were scanned.

Scans alert on files larger than 4 GiB, nested content larger than 16 GiB, more
than 2,000,000 files, or recursion beyond 32 levels. A limit alert or scanner
error is an incomplete result and must be reported; it is never called clean.
These limits are raised from ClamAV's defaults, and the scan uses its
`--alert-exceeds-max=yes` mode because the [ClamAV scanning guide](https://docs.clamav.net/manual/Usage/Scanning.html)
documents that oversized files are otherwise skipped and assumed clean.
For execution, use the protected stdin credential path of
`scripts/migration/run-security-maintenance.py` with `--playbook antivirus-scan`,
a settings file containing only `{"antivirus_scan_apply":true}`, and a protected
output directory under the declared task root. Do not pass sudo in argv, a
settings file, or shell history. This scan does not install packages, reboot,
patch hosts, or change cluster resources.
Run the same protected runner with `--playbook antivirus-boot-scan` and the same
settings/output directory to scan each node's separate `/boot` device serially.

After Flux reconciles the Plex hardening chart, run
`playbooks/plex-hardening-verify.yml` with
`plex_hardening_baseline_receipt` set to the exact `-plex-baseline.json` file
created alongside the node scan results.
It checks live container security, the constrained NetworkPolicy, Plex's
account-backed library endpoint, and unchanged Longhorn claim/volume UIDs. The
release is derived from the digest-pinned image tag; /identity is checked
only for API reachability because its version field is a schema version.
All three playbooks are read-only with respect to node contents, cluster
resources and application storage.

## Existing-cluster security maintenance

`playbooks/security-maintenance.yml` is a dedicated workers-first, `serial: 1`
maintenance entry point. The configured containerd pin is 2.4.2, but live 2.4.1
has not been patched by writing these files. Bootstrap refuses a different
already-installed runtime version and directs operators to this maintenance
entry point. CNI and crictl bootstrap extraction markers bind the archive SHA,
so a changed configured archive is not silently skipped. Docker coexistence
checks require `migration_require_docker_coexistence: true`; its default is false
after the approved Docker/Swarm retirement. No task starts Docker or glusterd.

Before execution, review fresh encrypted configuration/etcd/application recovery
evidence and current Longhorn replica placement, free capacity, PDBs, workload
placement and tolerated downtime. Supply the sudo credential through a protected
stdin-to-child-environment launcher, using the existing runner's in-memory
`BRANCONET_MIGRATION_SUDO_PASSWORD` transport; never put it in a command line.
The existing `scripts/migration/run-ansible.py` is hardcoded to `site.yml` and
does not select this new playbook. Use the dedicated
`scripts/migration/run-security-maintenance.py` launcher described below; it uses
the same isolated runtime, inventory and configuration, accepts only documented
nonsecret settings, and checks the independently supplied backup receipt SHA.
The security role additionally
requires all of the following nonsecret extra vars:

```yaml
security_maintenance_apply: true
security_maintenance_backup_verified: true
security_maintenance_backup_reference: /protected/path/to/reviewed-backup-receipt.json
security_maintenance_reboot: true
security_maintenance_expected_kernel: 5.15.0-198-generic
```

The reference records the operator's reviewed evidence; the role does not verify
the backup artifact itself. Pass these nonsecret settings using `-e @path.yml`.
Syntax-check with the same isolated Ansible and explicit `ANSIBLE_CONFIG` shown
above, substituting `playbooks/security-maintenance.yml`. Check mode runs
read-only preflight and skips the mutation block; it is not drain/patch testing.

Each node must start Ready and uncordoned, with all three expected nodes present,
and no `MemoryPressure`, `DiskPressure`, `PIDPressure` or `NetworkUnavailable`
condition True on any node. Every one of the original thirty volume names/UIDs
from the reviewed checkpoint receipt must still exist attached and healthy;
detached originals cannot disappear from the pre-node gate. A pressure incident
or failed volume recovery stops further node maintenance until corrected.
The preflight also requires
attached Longhorn volumes healthy, the `block-if-contains-last-replica` drain
policy intact, independent containerd running, and Docker/glusterd stopped. The
service-facts guard accepts the explicit `stopped` and `inactive` representations
of those retired units before and after maintenance; running and failed states
still refuse. Ansible core 2.21.5 reports the verified inactive/dead systemd units
as `inactive` on these hosts.
The role inventories predictable drain blockers before cordoning, then rechecks
after cordoning. Normal eviction and all PDBs remain enforced; `--force` and
`--disable-eviction` are never used. By default emptyDir loss refuses. Explicit
`security_maintenance_allow_reviewed_emptydir: true` permits
`--delete-emptydir-data` only after every relevant emptyDir matches the reviewed
namespace/controller/volume/mount-path allowlist. It covers Flux rebuildable
caches/temp, CSI socket storage, Longhorn UI runtime storage, xTeve `/tmp/xteve`
and FlareSolverr `/config`. The user explicitly classified the latter as
disposable runtime/browser-session state; normal restart/session loss is accepted.
xTeve configuration remains on its PVCs. Changed/unlisted mounts and unmanaged
pods refuse before patching. Keep other writers of pod specifications excluded
during this maintenance window. Longhorn/PDB constraints may still stop a drain. Investigate
the preserved failure; do not bypass the data gate. A failure stops the rollout
and does not automatically uncordon or roll back partially applied maintenance.

Ubuntu upgrades are limited to `security_maintenance_ubuntu_packages` (kernel
meta packages, OpenSSH, OpenSSL, libc, sudo and systemd by default), with
`default_release: jammy-security`, no autoremove and service starts/restarts
suppressed during package installation. This is not a whole-machine package
audit or an unrestricted distribution upgrade. Add other reviewed Ubuntu package
names explicitly, and simulate dependency resolution first. Third-party packages
are accepted only as exact `package=version` pairs in
`security_maintenance_extra_packages`; use host-specific inventory variables for
packages present only on one node. Docker/containerd distribution packages, runc
and Gluster package mutations are rejected. Do not use this role to reactivate
the retired runtime. Installed NVIDIA toolkit 1.16.0 on masternode needs a
separately reviewed exact upgrade (current candidate 1.20.1-1 for toolkit,
toolkit-base, libnvidia-container-tools and libnvidia-container1), without running
`nvidia-ctk runtime configure` or introducing GPU integration.

The runtime patch stages the verified official archive in a version directory,
checks its version, atomically copies containerd/shim/ctr with backups, preserves
the existing configuration bytes, and restarts only `containerd-k8s`. The role
accepts only the reviewed 2.4.1 to 2.4.2 path or an unchanged 2.4.2 rerun; it
does not patch runc, regenerate runtime configuration or touch either runtime's
data. Optional reboot runs only when the reboot-required marker exists or the
running kernel differs from the configured target, and requires that target to
be actually running afterward. The live daemon version is checked through the independent CRI socket,
the node must become Ready, retired services must remain stopped, and attached
Longhorn volumes must recover before the next node. Review workload rollouts and
application health/data after the run. The single control-plane reboot causes a
temporary API outage even when applications remain on workers.
The read-only Ready command now uses ten-second watch/request timeouts and up to
40 retries separated by five seconds, so transient API connection or authorization
initialization errors after that reboot do not immediately fail maintenance.
Persistent errors still exhaust the bounded wait and stop before uncordoning;
no authorization changes, drain replay or error bypass is performed.

Before each cordon, a unique mode-0600 controller JSON receipt durably records
the frozen original volume/controller identities under the launcher's private
per-run recovery directory. The final run record identifies that directory;
receipts survive drain, reboot or later assertion failures. Direct Ansible use
must supply an absolute `security_maintenance_recovery_receipt_dir` outside Git.
Use the preserved snapshot during reviewed recovery; do not substitute a newly
reduced resource set. The live CRI version guard accepts exactly `2.4.2` or
`v2.4.2`, matching the runtime's actual optional version prefix.

The final gate freezes the exact names/UIDs of all initially attached volumes
and the UIDs, desired counts and initial Ready counts of all active Deployments,
StatefulSets and DaemonSets before cordoning each node. Every original volume must return
to **attached and healthy**; disappearance, replacement or remaining detached
does not pass. Every original active controller must retain its desired replica
count, observe its current generation and regain all Ready replicas; Deployments
also require all desired replicas updated and available. DaemonSets must retain
their original scheduling count and regain Ready, available and updated Pods;
this covers the CNI and storage node agents. Missing controllers or
scaled-down replacements cannot evade the gate. The next node is not touched
until these checks pass. This is controller readiness, not application/data AT.

If reboot is false, updated libraries may remain loaded in existing processes
and the old kernel remains exposed. The 2026-10-23 installed kernel image
5.15.0-198.208 and meta-package version 5.15.0.198.171 are distinct. A reboot to
5.15.0-198 addresses the older Dirty Frag fix boundary; it does **not** resolve
unpatched CVE-2026-98260. Supported Jammy HWE 6.8 is also vulnerable with only a
work-in-progress fix recorded. See [the dated findings and primary sources](../../docs/TECH-STACK.md#2026-10-23-host-security-maintenance-preparation).
No kubeadm upgrade is included: upstream 1.37.1 remains current at this audit;
future patches require separately reviewed `kubeadm upgrade plan`, control-plane
upgrade, kubelet sequencing and official skew/Longhorn checks, rather than
rerunning `site.yml` to overwrite binaries.

## Fresh online storage checkpoint and dedicated launcher

`playbooks/storage-checkpoint.yml` inventories the existing attached volumes,
requires each healthy with configured replica count at least two, verifies the
available existing NAS target against the configured URL without logging it,
then snapshots and incrementally backs up **one volume at a time**. It does not
attach detached retained volumes, stop application writers, delete old snapshots
or backups, or claim restoration. Consistency is explicitly
`crash-consistent-online`; this is not an application cold backup. The official
[Snapshot](https://raw.githubusercontent.com/longhorn/longhorn-manager/v1.12.1/k8s/pkg/apis/longhorn/v1beta2/snapshot.go)
and [Backup](https://raw.githubusercontent.com/longhorn/longhorn-manager/v1.12.1/k8s/pkg/apis/longhorn/v1beta2/backup.go)
contracts supply `createSnapshot`, `volume`, `snapshotName` and
`backupMode: incremental`. Existing live Backup labels are `backup-volume` and
`backup-target`. Each snapshot must be ready without error; each backup must
complete with the exact volume/snapshot/target identity. A terminal error stops
the serial run and preserves all partial resources. Use a fresh unique prefix;
reusing a prefix with existing resources is refused, not replayed.

Create a protected nonsecret JSON settings file, for example:

```json
{"storage_checkpoint_apply":true,"storage_checkpoint_prefix":"security-20261023-unique","storage_checkpoint_receipt_path":"/protected/operator/storage-checkpoint-unique.json"}
```

Its receipt contains only names, UIDs, completion times and consistency metadata,
with excluded unattached volume names. It contains no backup URL or Secret value.
The controller receipt directory must already exist. Controller-reported
completion is not an independently restored/off-node readback proof. Retain the
existing independent recovery evidence as well. Current October 9/11 backups
were 12–14 days old at the October 23 audit, so a new checkpoint is required.

From a Linux source tree with this repository layout, run the dedicated launcher
with the isolated Python runtime:

```bash
~/.local/share/branconet-migration/venv/bin/python \
  scripts/migration/run-security-maintenance.py \
  --playbook storage-checkpoint --settings-file /protected/checkpoint-settings.json \
  --output-dir /protected/operator/maintenance-logs
```

Checkpoint mode uses the existing master operator kubeconfig and needs no sudo
credential. For maintenance mode, supply the reviewed fresh checkpoint receipt
path in `security_maintenance_backup_reference`, its independently checked SHA
using `--backup-sha256`, and the maintenance settings file. The launcher requires
a completed online checkpoint less than 24 hours old; this freshness gate does
not replace configuration/etcd backup and recovery review. Stdin must contain
only `{"sudo_password":"..."}` via a protected pipe. The password is passed only
in the child environment, never argv, settings, logs or a credential file.
Logs/launcher receipts use unique names and modes 0700/0600 outside Git.
`--syntax-check` takes no password or settings; `--check` runs preflight only.
Optional `--limit workernode2|workernode1|masternode` permits an explicitly reviewed
single-node step. To upgrade NVIDIA packages only on master, set
`security_maintenance_extra_packages_by_host.masternode` to the four exact
`=1.20.1-1` package selections; the actual
read-only apt simulation selected exactly four upgrades, zero installs/removals
and no Docker dependencies. The static containerd 2.4.2 archive was also streamed
and hashed independently: 34,415,353 bytes matching the configured SHA-256.

The default `security_maintenance_retire_unused_containerd: true` separately
checks the stock `/run/containerd/containerd.sock` namespaces/tasks and distinct
systemd MainPIDs before cordoning and immediately before retirement. Any running
task refuses retirement. Only after zero-task verification does it stop/disable
`containerd.service`; it never removes its packages/config/data or stops
`containerd-k8s.service`. This guarded execution-time inventory requires sudo;
an unprivileged read or absence of Docker is not proof the socket is unused.

## Separate control-plane backup before master maintenance

`playbooks/control-plane-backup.yml`, role `control_plane_backup` and
`scripts/migration/run-control-plane-backup.py` prepare a distinct maintenance
checkpoint. They do not execute, modify or reuse the frozen BORTUS qualification
helpers `backup-etcd.py` and `capture-kubernetes-recovery-config.py`.
This source is prepared only; no new backup has been taken by writing it.

Read-only discovery found the existing `etcd-masternode` static Pod Ready with
`registry.k8s.io/etcd:3.7.0-0`, runtime digest
`6ecefbe2510c4a30573a62a4d6dd175acf881ca67003fcd91849a16df7a724d5`.
Both embedded tools report 3.7.0; no host installation/download is needed.
The [official etcd 3.7 recovery instructions](https://etcd.io/docs/v3.7/op-guide/recovery/)
use `etcdctl snapshot save` and `etcdutl snapshot status`. This path uses the
existing TLS healthcheck-client certificate against `https://127.0.0.1:2379`,
creates a unique root-0700 staging directory beneath `/var/lib/etcd`, saves a
fresh snapshot and validates its database structure with embedded `etcdutl`.
It never copies the live `member/snap/db`, alters cluster membership or restores
over the live database.

The helper streams the complete regular-file `/etc/kubernetes` recovery tree
(including PKI, kubeconfigs, manifests, `encryption-config.json` and
`longhorn-crypto-key`) and the snapshot through strict SSH directly into the
existing native WSL age executable. The existing age v1.3.2 executable is bound
to its read-only observed SHA-256
`eb7dd1b518f0a307c99cd97782623c5321da049154b04acd2d98d21aa7bc9b2c`.
No plaintext configuration/archive is saved on the controller or emitted to
Ansible output. It refuses symlinks, unprotected
or unexpectedly large inputs. Limits are 512 MiB snapshot, 64 MiB configuration,
256 configuration files and one MiB per configuration file. All 32 standard
recovery files must be present and nonempty, including every kubeadm PKI pair.
Source Pod identity,
image identity and captured-file stability are checked.

The existing operator SSH age recipient/identity are required explicitly;
no key generation or rotation occurs. For example, use a protected nonsecret
JSON settings file containing:

```json
{"control_plane_backup_apply":true,"control_plane_backup_output_dir":"/home/brajam/.local/share/branconet-migration/control-plane-backups-20261023","control_plane_backup_recipient_file":"/home/brajam/.ssh/id_ed25519.pub","control_plane_backup_identity_file":"/home/brajam/.ssh/id_ed25519"}
```

From a freshly staged native Linux source tree, run
`scripts/migration/run-control-plane-backup.py --settings-file /protected/settings.json`
with the isolated operator Python. Supply only `{"sudo_password":"..."}` through
the existing protected stdin dispatcher. The launcher uses inherited child
environment transport and the remote sudo stdin channel; credentials are never
rendered into Ansible environment shell assignments, argv, settings or files.
`--syntax-check` requires neither settings nor credentials and takes no backup.
Direct Ansible check mode likewise takes no backup.

Each run has an exclusive private directory containing ciphertext and a
metadata-only `receipt.json`. Verification decrypts through EOF to authenticate
the age stream, parses the tar without extracting plaintext, checks all required
files and exact file hashes, validates encryption-config/PEM structure, and
checks the snapshot's whole-file hash and appended SHA-256 footer against the
exact database already inspected by `etcdutl`. It records snapshot revision,
key count, size and hash, plus ciphertext SHA-256 and source identities.
Only after verification does it remove its own inode-bound temporary snapshot
and empty staging directory; failures retain ciphertext and any protected remote
snapshot for review. No existing backup/configuration/data is deleted.

A completed receipt is an authenticated off-node operator copy, not a NAS copy,
application cold backup, independent restore, API decryption or BORTUS recovery
acceptance. Keep the operator key independently recoverable. Review the fresh
receipt together with Longhorn checkpoint and workload recovery evidence before
the master-last maintenance step; no existing maintenance gates are bypassed.

## Separate MeTube cold state preservation

`playbooks/metube-state-backup.yml`, role `metube_state_backup`, and
`scripts/migration/run-metube-state-backup.py` prepare separate `backup` and
`reobserve` phases. Root stops the writer through Flux; the helper never scales
it. A bounded temporary UID-1000 Pod reads the full original state/temporary
claims read-only, never mounts or walks the NAS claim, and records all three
original PVC UIDs. Complete tar/file hashing and age authentication stream in
chunks, preserving the roughly 618 MB current state without whole-archive RAM
buffering. A later full-claim reader compares every old file, excluding only
the three exact new YTPTube config/cache paths. Only the verified temporary Pod
is normally deleted with a UID precondition; originals and failed evidence stay.
See [the preservation runbook](../../docs/METUBE-STATE-BACKUP.md) for settings,
limits, receipt semantics and the required cold-writer/restart sequence.
Source preparation and syntax checks create no Pod, backup or application change.

## Bounded master-only Seerr image builder

**Retired build execution after the October 23 disk-pressure incident:** this
role now allows only `status` and `stop`. The historical setup/phase details
below document the retained sealed attempt, not an available dispatch path.
Neither this builder nor the YTPTube builder may execute builds on production
storage. An isolated off-cluster CI build requires its separately reviewed
capacity limits and the pending private charts Actions approval.

`playbooks/seerr-image-build.yml` and the dedicated
`scripts/migration/run-seerr-image-build.py` launcher offload the reviewed public
Seerr derivative build to the master without starting Docker or connecting to
either containerd socket. They do not deploy an image, access PVCs or read native
Secrets. The existing verified BuildKit 0.34.1 binaries come from controller
`~/.local/share/branconet-migration/seerr-image-20261023/bin`; official archive
SHA-256 is `a59539daf547fe0958efe2d07e41c0a6944e1112a66d7e519ec1cf5b673ef15b`.
The parent stages only the reviewed Dockerfile, apply-overrides.cjs and
security-overrides.json through the controller context. Setup hashes each tool
and source, copies only those exact inputs into protected root-owned
`/home/james/.local/share/branconet-migration/seerr-build-20261023`, seals their
identities and verifies the remote bytes. Existing differing/unsealed attempts
refuse replacement; artifacts and failures are retained.

The launcher accepts phases `setup`, `lock`, `runtime`, `status` and `stop`, plus
`--context-dir <absolute-controller-context>` for setup and
`--output-dir <protected-controller-evidence-directory>`. Use the isolated venv
Python. Every operational call receives only `{"sudo_password":"..."}` through
a protected stdin pipe; it never puts the credential in argv or a file. Syntax
checking takes no credential. Setup does not run BuildKit. Lock/runtime dispatch
asynchronously; launcher exit zero means dispatch, not build completion.

Each build phase runs its supervisor, daemon, client and OCI executions beneath
one exact transient systemd service with **3 GiB RAM, no swap, 150% CPU, allowed
CPUs 0–1 and 512 tasks**, a four-hour bound and native snapshotter/max parallelism two. The
supervisor verifies the actual cgroup limits before building. BuildKit 0.34.1
has no `--oci-worker-cgroup-parent` flag: the supported Dockerfile frontend
`--opt cgroup-parent=<actual-service-cgroup>` is used instead. Reviewed upstream
[frontend configuration](https://github.com/moby/buildkit/blob/v0.34.1/frontend/dockerui/config.go),
[Dockerfile conversion](https://github.com/moby/buildkit/blob/v0.34.1/frontend/dockerfile/dockerfile2llb/convert.go)
and [OCI specification generation](https://github.com/moby/buildkit/blob/v0.34.1/executor/oci/spec.go)
pass that parent into `<service>/buildkit/<execution-id>`. A delegated child
cgroup holds supervisor/daemon/client so domain controllers can be enabled
without the cgroup-v2 internal-process conflict. The same service ancestor
therefore bounds the aggregate build. Empty private HOME/DOCKER_CONFIG exclude
operator registry credentials; no SSH/secret mounts or insecure entitlements
are passed. BuildKit garbage collection is disabled for retained build state.

Run `setup`, then `lock`, inspect its terminal receipt and generated frozen lock,
then `runtime`. Each phase has unique fixed unit/socket names and exclusive
ownership; replay of an existing phase is refused. Lock writes the exported
`context/pnpm-lock.yaml` with exclusive creation. Runtime verifies that exact
successful lock identity before creating a retained OCI archive. `status` emits
only unit/resource/result metadata; detailed builder output remains in protected
remote log files. `stop` affects only the two exact owned units and leaves all
files/cache/artifacts intact. Verify both units stopped and coordinate bounded
builder completion **before the master's maintenance reboot**. A failed or OOM
build is retained and does not qualify the image; do not increase these limits
or alter the reviewed recipe silently.

## Prepared retired master public artifact offload

`playbooks/retired-build-offload.yml`, role `retired_build_offload`, and
`scripts/migration/run-retired-build-offload.py` prepare a separate explicit
inspect -> whole-tree encrypted offload -> reviewed exact-cache-clear sequence.
Only the two fixed October 12 custom kubectl build roots and their fixed cache
directories are in scope. It defaults apply false, never executes an old helper,
and never removes source/output/log/failure trees. Read the complete
[offload and review contract](../../docs/RETIRED-BUILD-OFFLOAD.md) before selecting
any phase. No archival/cleanup or storage health result is established by this
source proposal.

## Prepared worker1-only security image builder

`playbooks/worker1-image-build.yml`, role `worker1_image_build`, and
`scripts/migration/run-worker1-image-build.py` are a separate source-only
alternative after worker1's existing root filesystem has been safely expanded.
They target only `workernode1` (`192.168.0.6`, james, SSH 2002). Apply defaults
false. The retired master builders, seals, logs, lock and outputs remain untouched.
No SSH setup/build or application rollout is established by this preparation.

The launcher takes `--service seerr|ytptube|jackett|pihole`, `--phase
setup|runtime|status|stop`, and an absolute protected `--output-dir`. Setup also
requires an absolute staged `--context-dir`; Seerr additionally requires
`--seerr-lock-path` pointing to the separately exported frozen pnpm lock with
The initial/r2 attempts used SHA256 `3ba907e7d00dc76e636b79ed14c45e4ea2bf0a202104461ad8c335097f4f333b`.
The new ip-address 10.7.4 lock for a separately sealed r3 attempt is SHA256
`9665b245267e7c864210bdf85f1098c0891f30946c64b3781f44077fff0b7811`. Current setup/helper source binds only this new lock;
original frozen stages, setup seals, logs and locks remain untouched.
The operator stages that exact file in the new controller context; the builder
does not fetch or modify the retained master attempt. All recipes need a named
`runtime` stage. This builder only builds runtime; it does not regenerate locks.
The existing protected stdin sudo credential contract applies, with no credential
value in argv, settings, source, logs or receipts. Private charts CI was approved
and published separately; its first image runner refused insufficient disk space.

Each service gets a new root-owned 0700 directory under
`/home/james/.local/share/branconet-migration/worker1-image-build-20261023/<service>`
and unit `bortus-worker1-<service>-build-20261023-runtime.service`. Setup seals
only its own helper, exact selected recipe files, the required lock, and the
previously checksum-verified standalone BuildKit 0.34.1 tools from controller
`/home/brajam/.local/share/branconet-migration/seerr-image-20261023/bin`.
Release archive SHA256 remains
`a59539daf547fe0958efe2d07e41c0a6944e1112a66d7e519ec1cf5b673ef15b`.
It refuses every existing complete or incomplete service setup. A host-wide
exclusive lock sequences all four service builds, and each runtime attempt is
recorded with exclusive creation before preflight. Replay, overwrite, automatic
cache cleanup after failure and restoration of an older attempt are unsupported.

The default `--attempt initial` preserves those historical identities. An explicit
`--attempt r2` (or another `r1`–`r999` identifier) creates a distinct `<service>-r2`
directory and `bortus-worker1-<service>-build-20261023-r2-runtime.service` with a
separate seal and receipts. The identifier accepts no path or unit punctuation.
All attempts share the same exclusive host build lock and unchanged resource/
filesystem bounds. Existing attempts cannot be replayed or overwritten. The first
Seerr worker attempt failed during upstream Husky's production-prune lifecycle;
the correction skips scripts only during pruning and uses a fresh attempt with
the same frozen lock. Retain the original source, failure, logs and cache.

BuildKit can explicitly export mode 0666 despite the service umask. Successful
builds now tighten only their public OCI archive and build-metadata file to 0600
before hashing. The status/stop play also normalizes those two regular root-owned
files after a successful retained receipt, covering earlier completed attempts.
The protected 0700 build directory remains unchanged; no source or receipt bytes
are modified. A scanner permission refusal is retained and never called a pass.

Before starting the daemon, measured free bytes must be at least
`max(ceil(30% of filesystem total), 32 GiB) + 20 GiB`, with at least 15% free
inodes. The helper checks actual hostname `workernode1`; setup seals the actual
root ext4 UUID/source/type and every operational phase verifies that pin.
The root/device/filesystem identity is recorded. Every two seconds,
through readiness, build and archive hashing, the helper checks unchanged device,
filesystem ID and total size; available bytes must remain above
`max(ceil(30% of total), 32 GiB)`, and free inodes at least 10%. A violated floor
records an abort when possible and signals only the exact owned build unit,
including OCI sibling cgroups; cgroup.kill is the fallback if systemd refuses.
Sampling permits small overshoot.
The same monitor stops for an OCI above 4 GiB or any runtime log above 64 MiB;
completed OCI size is also checked before recording success.
No API credential or optional Kubernetes node
pressure input is used; root must independently require healthy nodes/volumes
before dispatch, and stop the exact unit if cluster pressure develops.

The aggregate delegated systemd ancestor is verified at 3 GiB RAM, zero swap,
150% CPU, CPUs 0-1, 512 tasks and a two-hour RuntimeMaxSec, with maximum parallelism
two. The proven control-child/OCI-sibling cgroup-parent layout bounds supervisor,
standalone daemon/client and Dockerfile executions together. BuildKit uses its
native snapshotter, only an independent Unix socket, no containerd worker/socket,
empty private HOME/DOCKER_CONFIG and no credentials/hooks/production mounts.
Its own active cache enables GC with a 20 GiB soft target, 1 GiB reserved cache
and the measured free-space floor; active cache can exceed that target, so the
independent filesystem monitor remains mandatory. Failed source, logs, lock and
partial/complete OCI outputs remain for review. GC affects only this new cache.

`runtime` dispatch is asynchronous; only its successful `runtime-finished.json`
with archive size/SHA establishes build completion. Output is
`<service>-security-20261023.oci.tar` in that service root. `status` reports public
metadata only; `stop` checks command ownership and stops only its exact runtime
unit. Build completion does not qualify a scan, native runtime, migration or
actual service functionality and does not preload, publish or deploy anything.

## Separate bounded YTPTube image builder

This role also permits only `status`/`stop`; setup/runtime dispatch is refused
before any setup or service mutation. Historical inputs and receipts remain.

`playbooks/ytptube-image-build.yml`, role `ytptube_image_build`, and
`scripts/migration/run-ytptube-image-build.py` prepare the independent YTPTube
derivative using the same reviewed BuildKit binaries and aggregate cgroup
limits described above. They do not modify Seerr's source/helper/seal or use
its remote state. YTPTube has only `setup`, `runtime`, `status` and `stop`
phases because its Dockerfile has a single final stage named `runtime`.

Setup takes the absolute staged `images/ytptube` controller directory and copies
only Dockerfile, patch-provider.py, verify-python.py, the verified standalone
tools and its own helper. Its protected remote identity is
`/home/james/.local/share/branconet-migration/ytptube-build-20261023`; its sole
build unit is `bortus-ytptube-build-20261023-runtime.service`. Setup seals the
copied bytes and refuses changed/incomplete prior inputs. The launcher uses
the same protected stdin credential contract and asynchronous completion
semantics as Seerr. Output is the retained `ytptube-security-20261023.oci.tar`;
inspect the successful runtime receipt and scan the exact image before rollout.
See [the image runbook](../../images/ytptube/README.md) for exact staging,
dispatch, isolation, dependency and pending runtime acceptance details. No
YTPTube build or deployment is established by source preparation.

## Exact offline worker1 OCI vulnerability scans

`playbooks/worker1-oci-scan.yml`, role `worker1_oci_scan`, and
`scripts/migration/run-worker1-oci-scan.py` are a separate, disabled-by-default
scanner path. They neither edit nor dispatch the worker1 builder. The only target
is james@192.168.0.6:2002; setup uses the existing controller Trivy 0.76.1 binary
and the four exact database/metadata files retained in native WSL at
`/home/brajam/.local/share/branconet-migration/audit-db-offload-20261023T215011Z`.
The binary SHA256 is `d1dfca6ae10a1ad4540bb94e64f0510077c47008920a9b554986b39dca573d83`.
All input hashes and both database timestamps are sealed; existing differing
remote files are preserved and refused. No database or tool download occurs.
The master audit reports, original exports and controller DB evidence stay intact.

The source kind defaults to `worker1`, preserving the local builder contract
below. Explicit `--source-kind github-actions` accepts only separately staged
root-owned original private-CI proof files and an operator SHA-bound provenance
receipt. It never fabricates local builder seals/finished receipts. CI inputs use
the fixed `ci-image-artifacts-20261024/<runID>-<artifactID>` directory and retain
the same offline scanner/DB/resource/redaction/OCI checks. See the exact
[CI provenance and staging contract](../../docs/CI-IMAGE-SCAN-PROVENANCE.md).
The fixed scanner, CI-stage and preload allowlists are `seerr`, `ytptube`,
`jackett`, `pihole` and `flaresolverr`. The Windows receiver includes prepared
Pi-hole and FlareSolverr support. Each non-Seerr original result must explicitly
claim a null frozen lock and contain no Seerr/pnpm-lock input; Seerr's exact lock
checks remain unchanged. This extends artifact handling, not the local builder's
execution allowlist, and proves no build, scan, native behavior or rollout.

The standalone `playbooks/ci-image-artifact-stage.yml` and
`ci_image_artifact_stage` role perform that controller-to-worker copy only.
Apply defaults false, check mode transfers nothing, IDs/service/SHA select fixed
paths, and complete SHA/owner/mode/link checks precede and follow force-false
copies of missing selected files. Existing matching files are preserved; conflicts
and unknown destination entries refuse. It retains the scanner's filesystem/inode
reserve plus copy/scan space, rechecks unchanged controller bytes, and never
scans, imports, deploys, overwrites conflicting files or cleans old data. Exact
settings/invocation are in the same CI provenance document.
The separate Windows `scripts/migration/receive-ci-image.py` receiver can prepare
the protected native WSL controller copy from an existing verified private Seerr,
YTPTube or Jackett
ZIP and authenticated API metadata. It never substitutes local build receipts,
downloads again, imports an image or stages directly on a cluster node. Root
reviews its exact selected proof files/provenance before worker1 staging: seven
for Seerr including its fixed lock, six for the four non-Seerr services with an
explicit original null lock claim.

Setup reuses those exact verified inputs/template in the private root
`/home/james/.local/share/branconet-migration/worker1-oci-scan-20261023`.
The helper is staged separately at `helpers/<full-local-source-SHA256>/scan_oci.py`
with mode 0500 under root-owned mode-0700 parents. Its `inputs.json` seal lives
beside that exact helper, and scan requires its own matching setup seal. Ansible
derives the helper path from reviewed local source bytes, with no caller path
override. Copies use force false and then verify exact hashes; existing DB/tool/
template files are reused without overwrite or download. The original root-level
helper, seal and all failed attempts remain untouched. Explicit setup is required
once for the new helper version before scan/status; setup itself scans nothing.
It checks a reserve of 25% filesystem capacity plus 8 GiB, with additional room
for staging copies, before copying large inputs. Scan requires the existing
fixed builder archive for one of `seerr`, `ytptube`, `jackett`, `pihole`, its
reviewed whole-archive SHA256 and its original root descriptor digest. Archives
use `--build-attempt initial` by default or exactly `r1` through `r999`, selecting
only the fixed `<service>` or `<service>-rN` builder directory; the artifact
basename remains `<service>-security-20261023.oci.tar`. Matching builder seal,
successful runtime-finished receipt and BuildKit root digest metadata are required
and bound by SHA256 in the scanner receipt. Failed/prior builds stay intact.
Archives
must be private regular files, at most 4 GiB. The helper checks every reachable
OCI manifest/config/layer digest and size beneath the single exact root. It
requires exactly one linux/amd64 runtime manifest and materializes a private OCI
layout directory containing only that manifest's unchanged blobs and a single
runtime index. Every copied blob is checked again by size and SHA256. The report
binds the original archive hash/root, selected runtime manifest/config digest,
and materialized index/layout hashes. Layers remain opaque blobs: there is no
image filesystem extraction by this helper.
Other platforms and attestations receive identity verification only, not a CVE
scan. No image is imported, unpacked into production storage or executed.

Each fresh 12-hex attempt uses a separate
`bortus-worker1-oci-scan-<service>-<attempt>.service`. Aggregate bounds are 1 GiB,
no swap, 200% CPU, 128 tasks, Nice 10, GOMAXPROCS=2 and GOMEMLIMIT=512MiB. A
global lock and process check permit only one scanner. PrivateNetwork disables
network access; Kubernetes/runtime/Longhorn/SSH paths are inaccessible, databases
are mounted read-only, and writable paths are confined to the scanner root.
The 7-minute scanner timeout, 480-second child observation ceiling, 900-second
unit ceiling and live filesystem/inode reserve checks bound the attempt.
Insufficient reserve, stale DB (over 24 hours from UpdatedAt), missing coverage,
scanner error or OOM is failure, never a clean result. There is no retry loop.

Trivy receives only the derived layout directory with `--input`, `--scanners vuln`, offline mode,
both DB updates disabled, explicit empty config/ignore files, all severities,
and no ignore-unfixed or suppression. The
[0.76.1 template implementation](https://github.com/aquasecurity/trivy/blob/v0.76.1/pkg/report/template.go)
passes only Results to the template, so persisted `results.json` excludes full
image config, Env, command/history and arbitrary labels. No Kubernetes Secret
API or Secret scanner is used. Raw package/CVE results and private stderr remain
under the attempt directory; `vulnerabilities.json` contains package/current/
fixed/severity/status/source rows, and `status.json` retains input/OCI identities,
DB age, cgroup evidence, coverage and fixed/unfixed critical/high counts. No raw
stderr is printed into Ansible output. All findings and failed partial attempts
remain; `securityAcceptance` stays false pending review and runtime acceptance.

The launcher defaults to no action and uses the existing operator venv. With
`--apply`, its stdin is exactly the protected `{"sudo_password":"..."}` object;
the value travels only to the child environment and never argv, settings or
receipts. Syntax checking needs no credential or host contact:

```text
venv/bin/python <stage>/scripts/migration/run-worker1-oci-scan.py --syntax-check
venv/bin/python <stage>/scripts/migration/run-worker1-oci-scan.py --apply --phase setup --output-dir <private-controller-output>
venv/bin/python <stage>/scripts/migration/run-worker1-oci-scan.py --apply --phase scan --service <service> --build-attempt <initial-or-rN> --archive-sha256 <reviewed-sha256> --root-descriptor sha256:<reviewed-root> --output-dir <private-controller-output>
venv/bin/python <stage>/scripts/migration/run-worker1-oci-scan.py --apply --phase status --service <service> --attempt <returned-attempt> --output-dir <private-controller-output>
```

Setup can take longer than the launcher's 360-second observation window while
copying the retained DB. A timeout preserves that process: observe its exact PID
and private log rather than replaying setup. A successful scan launch is
asynchronous and proves neither scan completion nor application acceptance.
This source preparation does not itself perform a transfer or scan.

The original frozen source `1eab515ca7f7` failed because Trivy 0.76.1 interpreted
the OCI tar input as a Docker archive and then as an OCI directory. Its
[OCI reader](https://github.com/aquasecurity/trivy/blob/v0.76.1/pkg/fanal/image/oci.go)
opens `index.json` from a layout directory. The prepared correction supplies
that directory and uses a new content-addressed helper/seal without changing the
scanner flags, findings policy, resource bounds or frozen failure evidence.
Only AST and Ansible syntax checks qualify this source preparation; staging,
setup and actual scanning remain Root-owned operations.

The correction retains the original nonempty Results-array
guard and per-target Type metadata; it does not retain every installed package
or prove exhaustive package/OS coverage. Existing findings can qualify an exact
artifact vulnerability report, but blank/unrecognized analysis cannot establish a
clean image. The optional `61d8bc5f9a0a` inventory/terminal-status refinement is
preserved in a separate controller stage and is not adopted. No installed-package
inventory or terminal-status refinement is bundled with this input-format fix.

## Pinned worker1 existing-LV filesystem growth

`playbooks/filesystem-growth.yml`, role `filesystem_growth`, and
`scripts/migration/run-filesystem-growth.py` provide a separate, inspect-by-default
capacity recovery path. It targets only `workernode1` (`192.168.0.6`): root and
`/var/lib/longhorn` must be the same mounted read-write ext4 filesystem, UUID
`5f1fd363-f7b7-44db-ace5-ad81a25a2926`, on the existing
`/dev/mapper/ubuntu--vg-ubuntu--lv` with exactly **253,906,386,944 device bytes**.
The independently read original superblock has **26,214,400 blocks of 4,096 bytes**
(107,374,182,400 bytes); `df` reports a smaller usable capacity because of
filesystem metadata. Existing LV space, rather than unallocated VG space, is
the recovery opportunity. No filesystem growth has been established by source
preparation or syntax checking.

The role stages an actual SHA-256-pinned `guard.py` under the fixed private
`/home/james/.local/share/branconet-migration/fs-growth-worker1-20261023`
directory. An existing differing helper is preserved and causes refusal.
`filesystem_growth_apply` defaults to `false`: normal execution only inspects
mount/device identity, clean superblock state, exact original features/geometry
and writes a private receipt. Generic Ansible `--check` is refused; use this
explicit inspection mode. Sudo is required to read the superblock, even during
inspection. It reaches the dedicated launcher only as JSON
`{"sudo_password":"..."}` on protected stdin, then the Ansible child's private
environment; never in settings, argv, source, receipts or diagnostics.

Run the launcher from the staged native WSL source with the existing migration
venv, a nonsecret settings file and a private controller output directory:

```text
venv/bin/python <stage>/scripts/migration/run-filesystem-growth.py --syntax-check
venv/bin/python <stage>/scripts/migration/run-filesystem-growth.py --settings-file <inspect.json> --output-dir <private-controller-output>
```

Inspection settings are `{}` or `{"filesystem_growth_apply":false}`. Review the
remote metadata receipt and independently record its SHA-256. Only a subsequent
explicit apply may set `filesystem_growth_apply:true`,
`filesystem_growth_reviewed_preflight:<remote-receipt-path>` and
`filesystem_growth_reviewed_preflight_sha256:<exact-sha256>`. The helper also
requires unchanged source hash, boot ID, UUID, device bytes and original geometry;
a reboot requires fresh inspection. Do not inspect before a planned reboot and
reuse that receipt afterward.

The sole filesystem mutation is `resize2fs /dev/mapper/ubuntu--vg-ubuntu--lv`,
without a size or force option: grow online to the already existing device.
There is no partition/LV operation, shrink, offline fsck, filesystem feature
change request, Longhorn threshold/metadata mutation or data deletion. The
[upstream 1.46.5 manual](https://raw.githubusercontent.com/tytso/e2fsprogs/v1.46.5/resize/resize2fs.8.in)
documents mounted ext4 online enlargement and the default existing-device size.

The guard serializes attempts and refuses another live `resize2fs`. It records
the process identity and before/after superblock, UUID, mounts and `df` evidence;
receipt bytes and their parent directory are fsynced. At a 300-second observation
timeout it preserves the running resize and its PID; the launcher similarly
returns an observation state after 360 seconds without killing its child.
Observe the existing process and receipt rather than replaying. An already
fully grown filesystem is reported without another resize. Growth does not
qualify application data integrity or Longhorn recovery; verify the original
30 checkpoint volume UIDs, healthy replicas, disk scheduling and applications
before continuing maintenance or image work.

<a id="seerrytptube-cache-only-oci-preload"></a>

## Maintenance application cache-only OCI preload

`playbooks/application-image-preload.yml` and role `application_image_preload`
prepare a separate serial cache import after the coordinator transfers an
accepted public OCI archive to each node. Optional verified controller staging
can perform that public archive transfer as described below. They do not build,
deploy, start an application, read a Secret/PVC, or change runtime configuration.
The existing BORTUS preload/recovery mechanisms are not reused or modified.

The root credential dispatcher invokes the playbook with nonsecret settings:

```yaml
application_image_preload_apply: true
application_image_preload_artifacts:
  - service: seerr # or ytptube, jackett, pihole, flaresolverr
    archive_path: /home/james/.local/share/branconet-migration/<protected-stage>/image.oci.tar
    archive_sha256: <independently-verified-64-hex-archive-sha256>
    manifest_digest: sha256:<expected-64-hex-root-image-or-index-descriptor>
```

Use per-host settings/inventory if transferred paths differ. The archive and
containing directory must be owner-only, owned by root or UID 1000, under the
operator directory, without symlink resolution. Only the independent
`/opt/containerd-k8s/bin/ctr`, `/run/containerd-k8s/containerd.sock` and `k8s.io`
namespace are allowed. After checking archive SHA-256, OCI layout, the unique
expected root descriptor and its exact content bytes, the helper imports with
`--local --all-platforms --no-unpack --digests --base-name` and the managed CRI
image label. The fixed canonical image names are
`docker.io/library/seerr-security-20261023@sha256:<digest>` and
`docker.io/library/ytptube-security-20261023@sha256:<digest>`, with equivalent
`jackett-security-20261023`, `pihole-security-20261023` and
`flaresolverr-security-20261023` aliases for same-application derivatives.
No arbitrary application or BORTUS alias is accepted.

The explicit base-name filters unrelated named references. Conflicting
prospective aliases refuse import; every existing image identity must remain
unchanged afterward. The helper verifies the exact canonical alias and cached
manifest/index SHA, and reports metadata only. It never removes images, forces
tags, accesses the stock socket or runs a container. All platform content is
cached; unpacking, actual CRI launch and application acceptance remain later
gates. No live import is established by preparing or syntax-checking this role.

### Optional protected controller-to-node artifact staging

`application_image_preload_stage_from_controller` defaults **false**, preserving
the already-transferred archive contract above. With explicit `true`, the role
copies only Seerr, YTPTube, Jackett, Pi-hole or FlareSolverr public OCI archives, from the fixed
controller directory
`/home/brajam/.local/share/branconet-migration/application-artifacts-20261023/`
to the fixed node directory
`/home/james/.local/share/branconet-migration/application-artifacts-20261023/`.
Per-artifact `generation` defaults to `initial`, preserving the exact basename
`<service>-security-20261023.oci.tar`. The only other accepted generations are
`r1`–`r999` and `ci1`–`ci999999999999999`, without leading zeroes. These use
`<service>-security-20261023-<generation>.oci.tar` under the same fixed directories;
`archive_path` must equal the exact computed node destination. For example:

```yaml
application_image_preload_apply: true
application_image_preload_stage_from_controller: true
application_image_preload_artifacts:
  - service: ytptube
    generation: r2
    archive_path: /home/james/.local/share/branconet-migration/application-artifacts-20261023/ytptube-security-20261023-r2.oci.tar
    archive_sha256: <independently-verified-64-hex-archive-sha256>
    manifest_digest: sha256:<expected-64-hex-root-image-or-index-descriptor>
    uncompressed_layer_bytes: <reviewed-positive-expanded-layer-bound>
```

The matching controller source in this example is
`/home/brajam/.local/share/branconet-migration/application-artifacts-20261023/ytptube-security-20261023-r2.oci.tar`.
An omitted/explicit `initial` generation remains compatible with the original
path; a retry or CI artifact gets a separate name rather than replacing it.
Generation affects only protected transfer paths and recorded staging metadata.
It does not alter the immutable service/digest cache alias or import checks.
Each artifact must additionally supply positive
`uncompressed_layer_bytes` no greater than 16 GiB, independently measured or
conservatively bounded from all archive layers; it is not a claim about the
deduplicated final root filesystem. Archive size is measured and capped at 4 GiB.

Controller pre/post checks require a regular single-link, non-symlink file,
current-owner-only permissions, protected 0700 parent, exact supplied SHA-256,
and unchanged descriptor identity. As `james` without become, node preflight
checks its protected parent. When that child is absent, the existing operator
ancestor must be owned by the operator and not world-writable; group-write is
accepted only when both explicit and primary group membership resolve solely
to that same operator. Its existing mode is never changed. The new child remains
0700. Preflight also checks
any existing exact archive hash/size, and current `statvfs.f_bavail`. Before each
copy it requires available bytes at least:

`ceil(15% * filesystem total bytes) + 1 GiB + 2 * archive bytes + uncompressed_layer_bytes`

The 15% threshold and 1 GiB reserve are fixed. The role records the exact total,
available, reserve, required bytes, file identities and post-copy SHA metadata
in operator output. It creates only the missing fixed 0700 directory, copies
with mode 0600 and `force: false`, and hashes the complete node copy before
calling the unchanged importer. A matching existing owner-only archive is
preserved, including mode 0400; a differing archive refuses rather than being
replaced. The existing import helper independently repeats its SHA/OCI checks.
Copies remain after import for review; no automatic staging cleanup is added,
and the native WSL archive is always retained. Check mode skips staging/import.
Source/syntax preparation is not an actual transfer, capacity or runtime receipt.

Kubernetes native Secrets are encrypted at rest. Longhorn uses two replicas, retained PVs, LUKS and a native longhorn-crypto Secret; recovery copies must preserve both API and volume encryption keys. Flux retains helm-controller and does not activate the source branch until charts/values validate. Application imports, migration cutovers and final Gluster/Vault retirement follow [PLAN.md](../../PLAN.md) and [MIGRATION_STATUS.md](../../MIGRATION_STATUS.md). Full instructions: [MIGRATION-OPERATIONS.md](../../docs/MIGRATION-OPERATIONS.md).

## Standalone LAN DHCP handoff

`playbooks/lan-dhcp-handoff.yml` stages a DHCP-only dnsmasq service on the
existing standalone resolver host. Its two allocation ranges exclude `.246`.
It preserves the five existing router reservations and gateway, and advertises
both LAN resolvers. DNS port 53 and the Kubernetes charts are unchanged.

Run `scripts/migration/run-lan-dhcp.py` from WSL with `syntax`, then `stage`.
The runner reads the existing sudo credential through a hidden prompt and puts
controller scratch and logs under the declared H artifact run. Staging leaves
the new service stopped and disabled. In the Codex browser over HTTP, disable
router DHCP and read back the saved setting before running
`activate --router-disabled`. Verify a real Windows DHCP renewal reports the
new server, original reservation/gateway and both DNS addresses, then query each
resolver from that client. `verify` checks the active service and listener.

For rollback, run `rollback` first and verify the replacement listener has
stopped, then re-enable router DHCP and renew the client. Never run both DHCP
servers together. Existing lease state lives in `/var/lib/branconet-lan-dhcp`;
do not erase it during service maintenance.

The operator-only `scripts/migration/xr500-dhcp-setting.py` uses the same
firmware LAN form if the browser stalls on its blocking save notice. It reads
the private MCP `.env`, verifies the configured router HTTPS certificate before
using the operator-requested HTTP LAN form, checks the fixed LAN/pool baseline
and verifies unchanged reservations. It is not exposed as an MCP
write tool. A router apply response is asynchronous: reconcile its completion
marker and saved DHCP state before activating or restoring another server.
The Windows acceptance command is `scripts/migration/verify-lan-dhcp-client.ps1`.
It checks the actual lease, exchanges DNS packets directly with both resolvers,
and checks TCP and normal Windows DNS. The staged service keeps both leases and
its PID file inside the unit's writable private state directory.

## Node rename storage admission

Run the read-only admission play before any planned node retirement or rename.
From the Ansible directory, set the candidate to its current Kubernetes name.

```sh
ANSIBLE_CONFIG="$PWD/ansible.cfg" ansible-playbook -i inventory/production.ini   playbooks/node-rename-admission.yml -e 'rename_candidate_node=REPLACE_WITH_CURRENT_NODE'
```

The play projects incoming Longhorn replicas onto the two survivors and checks
disk capacity, existing replica separation and node and disk tags. A negative
margin or placement mismatch stops the preflight. A pass is a capacity estimate.
Verify actual eviction, backups, workload readiness and etcd quorum separately
before changing a node identity.
