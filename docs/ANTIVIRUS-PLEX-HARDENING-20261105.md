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

Full scans explicitly set directory recursion to 256; ClamAV 1.5.4's implicit
default is only 15. For the initial r2 pass, set
`antivirus_scan_supplement_from=full-20261106-r2` with a new finite generation
after the original node pass is terminal. The runner then covers directories
beyond the original depth boundary (with three overlapping levels), newly
mounted local filesystems, and archives that previously hit the time limit.
An original scan root that reported an access warning is retried in full if it
still exists in the current local mount inventory. Disappeared ephemeral mounts
remain explicit original coverage exceptions; no directory or mount is recreated.
The corrective pass keeps the same 1.5-core/3-GiB/4-GiB resource envelope and
24-hour job deadline; only these selected inputs have no per-file timer.
Original limits/results remain intact and later results must be linked before
calling the full coverage requirement accepted. The same procedure derives
its boundary from recorded depth for future scans.

Results are root-only under `/var/lib/branconet-antivirus/<scan-id>/`: updater
log, scanner log and structured status with scope, engine/signatures, limits,
detections and completion state. Collect sanitized results to the existing
`D:\Codex\cluster-threat-scan-20261105` task root. Package/signature files are
retained operational runtime inputs; temporary extraction and controller scratch
must be reconciled after their consumers exit. No antivirus command contains
`--remove`, `--move` or another automatic destructive option.

The runner suppresses ordinary clean-file lines with `--suppress-ok-results`,
retaining access and directory errors. ClamAV's `--infected` output mode also
hides some access-error paths; the original r2 runs and worker2's completed r3
used that older mode, so their raw summary/error totals remain authoritative
and cannot be described as an exhaustive per-path error list. Later queued
corrective runs use the improved logging. Directory recursion starts at one
for each supplied root in ClamAV 1.5.4; the correction's relative three-level
overlap therefore applies to long CSI staging paths as well as `/`.

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

## Observed completion — November 6, 2026

All three full passes and their required deep-directory/archive corrections
finished by 18:26:19 UTC. ClamAV 1.5.4 used verified official databases (initial
daily 28174; later master/worker1 corrections daily 28175).

| Node | Full-pass file visits | Corrective file visits | State |
| --- | ---: | ---: | --- |
| masternode | 426797 | 258944 | Completed |
| workernode1 | 1419931 | 2253193 | Completed |
| workernode2 | 318088 | 99543 | Completed |

These are per-pass visits with deliberate overlap, not counts of unique files.
No confirmed malware was found. The master's one non-limit finding,
`Heuristics.Zip.OverlappingFiles`, was reproduced by scanning the unmodified
public Klauspost ZIP fuzz corpus with the same engine/database. Its SHA-256
`8b2655dc4480530e1a1d682ee27a823bcebddd1c4afb606e202e057419501e14`
also matches the corpus inside the flagged retained build archive. The original
finding remains recorded; no package-cache exclusion or automatic removal was
introduced.

Coverage exceptions remain explicit: files larger than 2 GiB (swap and one
application database), 4 GiB expanded image preloads, a retained archive's
100,000-entry bound, original recursion-limit archives and parser/access errors.
The disappeared `/run/user/1000` mount was not recreated. The original infected-
only output mode does not provide an exhaustive per-path error list. Mounted
plaintext local data was included; NAS shares and detached encrypted volumes
remain outside this node-local scan. This result is not a guarantee against
unknown malware or certification of every unsupported input.

Final mount reconciliation found no new persistent local roots outside recorded
scopes. All r1/r2/r3 scratch mounts, images and loop associations are absent;
the public diagnostic fixture and its temporary mount were also removed. Initial
r1 failures remain labelled incomplete, with minimal evidence preserved.

Live Plex verification at approximately 18:28 UTC retained the original account,
server identity, library keys 1/2/4, paths and all 59 baseline PVC UID/PV bindings.
Plex was Ready with zero restarts; authenticated library access returned 200 and
anonymous access 401. Media remained read-only, config writable; effective Plex
capabilities were zero, NoNewPrivileges and seccomp active, and no API token was
mounted. Its encrypted Longhorn config remained healthy with two replicas. All
three nodes were Ready without memory/disk/PID pressure. Flux source and Plex
release were Ready on charts revision `1fc427b310c11394bd91c4bd2992cd90e091abe6`.

Protected full logs, actual summaries, scope reconciliation, hashes and the
earlier targeted IOC assessment remain in the existing local task root's
`FULL-ANTIVIRUS-REPORT.md` and its referenced observations. Production data,
original rollback material, images, snapshots and models were not deleted.
