# Full node antivirus scanning and Plex hardening

This November 5 follow-up is authorized independently of the earlier targeted
compromise assessment. No detection authorizes automatic removal/quarantine,
deleting a volume, pruning images, replacing credentials or rebuilding the cluster.

## Repeatable node scan

Use the existing inventory and in-memory sudo environment with
`k8s-rewrite/ansible-playbook/playbooks/antivirus-scan.yml`. Supply
`antivirus_scan_launch=true` and a new lowercase `antivirus_scan_id` (8–61
characters, letters/digits/hyphens). The procedure installs the supported Ubuntu
ClamAV/freshclam packages, verifies 15 GiB remains plus a 5 GiB installation/scratch
allowance and launches a finite systemd unit on each of the three nodes.

The unit updates official signed signatures before scanning. An update failure
fails the run instead of accepting stale/missing signatures. Freshclam's normal
update service stays enabled; there is no recurring scan or parallel clamd daemon.
Notifications to absent clamd are disabled. A generation cannot overwrite an
existing result. Units have 150% CPU (at most 1.5 cores), 3 GiB memory, idle I/O priority and a 24-hour
safety deadline. Archive extraction uses an exclusively created, fully reserved
4 GiB ext4 scratch image with loop/nosuid/nodev/noexec, rather than unbounded
node SSD writes. A fresh capacity check preserves 15 GiB plus a 512 MiB margin
after reservation. The runner unmounts and removes only its exact generated
scratch image after the scanner exits and loop-device/identity checks pass.

The full scan covers node-local host files, unpacked container image files,
mounted plaintext local data volumes, boot/snap filesystems and memory-backed
file storage. It does not traverse virtual proc/sys/device trees (except shared
memory), repeat CSI aliases, scan NAS network shares as though node-local, or
interpret encrypted Longhorn raw replica images as application files. Mounted
plaintext Longhorn files are scanned. Detached encrypted volumes remain outside
the scan; do not attach/reformat/decrypt them merely to claim complete coverage.
If a workload moves a volume while a node scan runs, reconcile the original and
current scope. After that node's full scan is terminal, use a new generation and
`antivirus_scan_only_volume=pvc-<uuid>` on the current volume-owning node to scan
the relocated plaintext data. This is a labelled supplemental scan, never a
substitute for the original full node scan or a replay of its result.
ClamAV's explicit per-file/archive/time/recursion limits and every error or limit
alert must be reported; an oversized file is not proof of infection or a clean
scan of that file.

Results are root-only under `/var/lib/branconet-antivirus/<scan-id>/`: updater
log, scanner log and structured status with scope, engine/signatures, limits,
detections and completion state. Collect sanitized results to the existing
`D:\Codex\cluster-threat-scan-20261105` task root. Package/signature files are
retained operational runtime inputs; temporary extraction and controller scratch
must be reconciled after their consumers exit. No antivirus command contains
`--remove`, `--move` or another automatic destructive option.

## Plex

The separately owned private charts repository contains the Plex hardening
profile and its operations runbook. It retains the immutable Plex image, all
four claims and the library paths. It removes authentication exemptions using a
restricted init container, preserves a small protected original preferences
backup inside the encrypted config claim, uses a dedicated token-free account,
mounts media read-only and limits privileges and network access. The preflight
found no configured DVRs or active sessions; recording functionality must have
an explicit writable recording destination if enabled later.

Deploy through the existing local validation -> validated -> Flux route.
`playbooks/plex-hardening-verify.yml` then verifies live rollout, token/principal,
seccomp, read-only media and lack of Secret-read permission. Separately compare
original claim UIDs/PV bindings, Plex image/server/account identity and library
keys, verify authenticated library access and anonymous rejection, and exercise
DNS/Threadfin/media reads and an actual denied network destination. These are
runtime checks; source validation alone is not deployment acceptance.

The controller's D: NTFS path cannot host Unix socket files. The task-local
launcher uses authenticated Linux abstract sockets for this Ansible invocation
only, retaining all filesystem output on D: without changing installed Ansible.
The existing charts publisher retains its separately authorized F:-backed root;
it must not be replaced by a second publisher or moved into this task root.
