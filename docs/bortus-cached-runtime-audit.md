# One-image cached-runtime audit (completed inventory; findings remain open)

This is vulnerability inventory of the currently running cached image only. It is
not BORTUS application development, a new release, a local-build provenance claim,
an application execution, or deployment acceptance. Registry acquisition returned
401; no new registry credentials or downloads are used. No Secrets, application
config, image environment/history, owner source trees or other cached images are
exported into reports. The private OCI archive contains only the existing runtime
image's reachable content and must stay private.

## Verified read-only discovery, 25 October 2026

- Namespace `bortus`, Pod `bortus-5c55f6d5b5-h9z6t`, UID
  `b802cc5f-ca3f-49b2-a3f5-2cd95d2a97bc`, container `bortus`, Ready, on
  `workernode2` / `192.168.0.5`.
- Both actual requested image and imageID are
  `docker.io/library/bortus@sha256:3b076fb9b7fb64fd760691c0120f29d4e363d4ccb9910a596ff211bfc3ea0879`.
  Historical alias is `docker.io/library/bortus:migration-1438b27`.
- Worker2 socket `/run/containerd-k8s/containerd.sock` is root:root 0660 and
  inaccessible to unprivileged James. `/usr/bin/ctr` exists. The exact cached
  reference/content completeness remains **unknown until the root probe**.
- Master retains its old `scan-bortus-export.py`, but its `inputs` is empty and
  both DB metadata files are absent. Its old receipt is for the same digest,
  completed 23 October with an older DB: 5 critical / 98 high / 160 medium /
  154 low / 3 unknown. Those are historical findings, not a fresh result.
- The old helper recorded archive size 1,149,324,800 bytes and SHA256
  `950b2d791f6c7507dbcc9d0fdac03db7229d584f60509df047cb9bb1133fae0c`.
  This is an estimate/reference, **not** the new export's required hash.
- Master free was 20,548,390,912 bytes; worker2 free was 21,764,087,808 bytes.
  The worker1 vendor DB is stale (23 October 19:15 UTC). Staging fresh core+Java
  DBs, the archive and a 2 GiB scratch allowance on master cannot retain the
  required 15 GiB floor. Therefore this path exports on worker2 and scans using
  the already staged fresh WSL scanner. It does not duplicate the DB on master.

## Exact source and bounded phases

`scripts/migration/run-bortus-cached-runtime-audit.py` controls only this digest.
`playbooks/bortus-cached-runtime-audit.yml` runs only on worker2 and stages
`scripts/migration/export-bortus-cached-runtime.py` by its canonical LF SHA256.

The privileged helper performs only `ctr images ls -q name==EXACT_REF` and
`ctr content get EXACT_REACHABLE_SHA256`. It never pulls, imports, unpacks,
executes, removes or relabels an image. Probe verifies every reachable blob
through SHA256, including all reachable manifests/configs, without persisting
config contents. Export repeats verification and writes one OCI archive.
If a root index references missing platform content, the operation refuses and
coverage stays unknown; it does not invent a complete archive from a mounted
container filesystem. Only the single Linux/amd64 runtime is vulnerability-scanned.

Bounds: 512 reachable blobs, 128 layers per manifest, 64 index children, depth8,
4 MiB metadata, 2 GiB maximum archive; actual projected tar bytes must be reviewed
between probe/export. Each node operation uses a separate 900-second systemd
unit, 1 GiB RAM, zero swap, two CPUs, 128 tasks, nice10, no network, no-new-privileges,
read-only system, private devices/tmp and only its evidence directory writable.
The root reader retains only CAP_CHOWN to give James group-read access to its
new root-owned0440 receipts/archive (private root:james0750 directories);
its fixed code issues no containerd mutation calls. The containerd socket is
reachable only by this finite reader, never the vulnerability scanner. No image
process is started.

The scanner reuses **only** existing helper primitives, exact SHA256
`ee456fd2be0fefcd0108e782771cc54b79ca9692ffaf7c4e57b6f29608094a06`, under
`/home/brajam/.local/share/branconet-migration/local-oci-scan-20261024/helpers/`.
It does not call that helper's builder/receiver provenance logic or main program.
It retains its real cgroup checks, full OCI SHA256 selection, immutable tool/DB
hash checks and the unchanged 8 GiB aggregate audit budget and inode reserve.
All new writable state is on the approved native F mount: controller outputs,
archive transfer, selected OCI layout, analyzer scratch/cache, HOME, TMPDIR,
TEMP, TMP, Ansible local/control directories, unit logs, results and receipts.
The finite audit uses its own exclusive `ROOT/scan.lock`, and retains the refusal
if another Trivy process runs. The coordinator must keep scans serialized;
this helper does not create or acquire a writable CROOT scan lock. Scan is
offline, nonroot, 1 GiB RAM, zero swap, two CPUs, 128 tasks, nice10, 900-second
unit/480-second child/7-minute Trivy timeout, empty credentials/config/ignorefile,
vulnerabilities only. It has no runtime socket, SSH or cluster access. Reports
are Results-only (64 MiB cap); stderr16 MiB; maximum65,536 targets/250,000 findings.

Pinned Trivy0.76.1 SHA256
`d1dfca6ae10a1ad4540bb94e64f0510077c47008920a9b554986b39dca573d83`.
Core DB SHA256 `6a8ba595e91f70580d9badfb6101da1dfeba5c697d28a644244a196034d41540`;
Java DB `9c17cf958a0fc2c74d5457ac33d2eb3ef71b170b49cadf9c465ecb9de7d66924`.
Both metadata files are independently hash-pinned by the existing helper.
Core DB age must remain at most24 hours. Java DB retains its pinned metadata's
own update window (24 October01:07 to27 October01:07 UTC), rather than imposing
the core DB's different cadence. The current core snapshot expires at approximately
25 October19:09 UTC; after that, refuse and review a separately acquired/pinned
fresh DB. Never disable the age check or reuse historical counts as current.

## Root operator4775 invocation

No phase has been executed by the source author. Use the existing hidden Windows
parent / WSL operator workflow. Working directory is the root Ansible checkout.
Use one new 12-character lowercase hex `ATTEMPT`; do not replay completed phases.
The controller-owned output root is the approved F filesystem path:

```
/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025/bortus-cached-runtime-audit-20261025
```

For `probe` and `export`, operator4775 supplies exactly
`{"sudo_password": "<existing RAM-only value>"}` to **stdin**, not argv or a
temporary password file. The controller passes it only through Ansible's existing
process environment contract, clears its copy after spawning and never prints it.
Do not paste a real password into these examples or a shell command.

```sh
python3 -B scripts/migration/run-bortus-cached-runtime-audit.py \
  --phase probe --apply --attempt "$ATTEMPT"
```

Review the private `attempts/$ATTEMPT/probe.json` plus
`probe.controller.json`: exact cache reference, complete closure, source hashes,
same live Pod/image before/after. Then pass its **actual** hash and
`closure.projectedArchiveBytes`:

```sh
python3 -B scripts/migration/run-bortus-cached-runtime-audit.py \
  --phase export --apply --attempt "$ATTEMPT" \
  --probe-sha256 "$PROBE_SHA256" --estimated-bytes "$PROJECTED_ARCHIVE_BYTES"
```

Review `export.json` and `export.controller.json`. They bind actual archive size
and SHA256, node/exporter/playbook/controller hashes and unchanged live image.
The controller streams exactly that archive to private F output, verifies the
transport hash and retains the node copy. No broad fetch, source tree or cache
copy is performed. Then, without any sudo credential:

```sh
python3 -B scripts/migration/run-bortus-cached-runtime-audit.py \
  --phase scan --apply --attempt "$ATTEMPT" \
  --receipt-sha256 "$EXPORT_RECEIPT_SHA256" --archive-sha256 "$ARCHIVE_SHA256"
python3 -B scripts/migration/run-bortus-cached-runtime-audit.py \
  --phase status --attempt "$ATTEMPT"
```

Scan launch is asynchronous. Read the existing unit/status; do not relaunch while
running. Scan results/status now live only under the approved F audit root,
`scan-attempts/bortus-cached-$ATTEMPT/`; the original F `attempts/$ATTEMPT/`
still holds the immutable archive and controller receipts. Existing historical
CROOT attempts/locks remain untouched; this revision never writes them. Status requires the same original live Pod/image again. A restarted or
changed Pod stops the guard and requires a new reviewed identity; no automatic
rebind is attempted.

Every launch remeasures C≥15GiB without allocating scan scratch there. Export
still requires both F physical/native≥15GiB plus actual projected archive bytes.
This finite scan requires **both native F and physical F≥23GiB** before launch:
15GiB retained plus the complete unchanged 8GiB aggregate scratch cap. During
writes both must retain≥15GiB; the existing inode reserve remains unchanged.
The 8GiB cap accounts for every allocated regular file below the one audit root,
including retained failures, archives, layout, helper snapshots, controller
scratch, caches, reports and receipts. Only the two exact read-only DB directory
links are permitted; they are not copied or counted as new scratch.

This is an explicit, authorized policy replacement **only for this F-only audit**:
the former C-root proportional25%-plus8GiB reserve is not transplanted onto the
144GiB external filesystem. `storagePolicy` in launch/worker receipts records
both the new fixed policy and the old policy it replaces. The immutable `ee456`
primitives, general scanners and publisher configuration are not modified.
Read-only preparation measured native F43,062,050,816B and physical F31,230,808,064B,
both above23GiB; these are preparation observations, never launch authorization.
The wrapper remeasures immediately before every actual launch.

The systemd scanner makes the complete CROOT input tree read-only, permits writes
only to F scan-attempts, its F lock and F unit log, and makes fallback `/tmp` and
`/var/tmp` inaccessible. Explicit HOME/TMPDIR/TEMP/TMP/XDG_CACHE_HOME point at F;
all analyzer cache writes stay there. The inherited Ansible config has an explicit
`/tmp/ansible-*` ControlPath, so this finite wrapper disables SSH multiplexing
with `ControlMaster=no`/`ControlPath=none` (including direct SSH calls). It keeps
all host-key/identity guards; no control socket is created on C or `/tmp`. Existing Trivy/DB/config/template and
content-addressed `ee456` code remain read-only C inputs. No DB/dependency copy,
new acquisition, installation or fallback to C is introduced. The node requires15GiB plus projected
archive bytes and the existing inode floor. The source-only author did not launch
any export, transfer, download, scanner, new Pod or application process. All failed
receipts, source, archives and runtime cache remain; no automatic deletion/prune.

## Public attribution evidence copied byte-for-byte

- `imagesharp-per-advisory-attribution.json`:
  `f120e84b7f07f7e5b46f3c842392e7661ef7d2b51b82f6bf66842a236143a0c2`
- `imagesharp-per-advisory-attribution.md`:
  `994b53fdd39376557323d779ba35286bb125be69aecd68c55fd868fa135bd5c2`
- `selected-runtime-attribution.json`:
  `9fc721fcc9fc39babaed58a56acfc23b259d418e2fa5bb608fccceb8aaeefed0`

These are evidence copies, not scanner suppressions. They retain each ImageSharp
advisory's primary fix/ancestry and actual selected DLL hashes, nonselecting PKCS
metadata distinctions, Sonarr.NET6 EOL and unresolved findings.


## F-only source revision validation

Before editing this revision, read-only process/unit inspection found no active
Trivy, cached-audit controller or cached-audit systemd unit. No scanner or runtime
was launched during this revision. Validation is in-memory Python AST parsing,
source inspection of exact immutable dependency functions and SHA256 comparison
of the unchanged exporter/playbook/other bound evidence. No pycache, test suite,
container, image build, download or cluster operation was created.

The CLI remains unchanged. Use the frozen helper under the F source bundle with
`--phase scan --apply --attempt "$ATTEMPT" --receipt-sha256 "$EXPORT_RECEIPT_SHA256"`
and `--archive-sha256 "$ARCHIVE_SHA256"`; then use `--phase status --attempt
"$ATTEMPT"`. Probe/export continue to use the repository controller so its original
relative Ansible path resolves correctly. Existing immutable probe/export
receipts are not regenerated or overwritten by changing the scan storage profile.
A future source freeze and its manifest stay on F; no new controller-C source
snapshot or receipt is required.


## Missing-bundle preflight diagnostic

The frozen `bortus-cached-complete-ebe2dbe02bff` snapshot was incomplete: it lacked
both `scripts/migration/export-bortus-cached-runtime.py` and
`k8s-rewrite/ansible-playbook/playbooks/bortus-cached-runtime-audit.yml`. The
controller hashes these required files before opening the inner operator log. The new attempt
had already created `controller-probe`, proving that its main stdin JSON parse
and first capacity check had passed; the earlier JSONDecodeError was a separate
failure. Pure SSH JSON transport and local metadata PowerShell passed without
running kubectl, sudo, any cached-image phase, export or scanner.

Probe/export now check these two exact public source paths and their already
reviewed SHA256 values locally, before reading the credential request or launching
any subprocess. A missing, unreadable or changed file leaves a new private F
`source-preflight-refusal.json` containing only a fixed code and the allowlisted
relative filename. The outer no-log wrapper can continue censoring all credential
handling; this separate diagnostic contains no values from the request or image.
Existing failed snapshots/receipts stay untouched. The coordinator must build a
new complete snapshot containing the unchanged exporter/playbook plus original
config, inventory and group variables; the preflight does not supply missing
files or bypass a guard.


## Installed Ansible RPC path correction

The next complete snapshot reached the unchanged Ansible CLI but its internal
LocalManager reported `TimeoutError: Local RPC server did not start`. The retained
operator log for attempt `60d8e851aadd` has SHA256
`502cc4e320d8cf9b42a2abf5ec8c5aee35d8fa045716451697de29c1d0cf89e0`.
Read-only inspection of installed `ansible/_internal/_rpc_host.py` (SHA256
`dbec8b6a29b05111911cfbf97a953415f71645514f042ed7f4308c17e41eee08`)
shows its server thread waits five seconds for `serve_forever`. Installed CPython
3.12 `multiprocessing/connection.py:70` chooses an AF_UNIX address under
`multiprocessing/util.py:144`'s `TMPDIR/pymp-XXXXXXXX/listener-XXXXXXXX`.
The configured TMPDIR is 160 bytes, making that socket path 192 bytes, beyond
Linux's 107 usable pathname bytes. Even using the 80-byte FBASE directly as
TMPDIR still produces 112 bytes, so that alone is insufficient.

The controller now launches the **same installed Ansible CLI, version and full
argument list** with the existing venv Python and a small process-local bootstrap.
It pre-seeds `multiprocessing.current_process()._config['tempdir']` to a fresh
exclusive `FBASE/r<seven hex characters>` directory. This omits only the extra
`pymp-*` component; the normal listener address is exactly 107 bytes. The bootstrap
and caller both verify the actual mounted FBASE, same native device, owner1000,
mode0700, no symlink alias, empty fresh directory and socket-length bound.
No Ansible/stdlib file, role, inventory, credential flow or audit limit is changed.
All ordinary HOME/TMPDIR/TEMP/TMP/cache/Ansible temporary files retain the existing
deep F paths; no C or `/tmp` fallback is introduced.

A public `controller-<phase>/rpc-path.json` binds the short socket directory to its
attempt. The aggregate reserve walk validates every such registered directory:
only up to16 owner-owned zero-byte `listener-*` Unix sockets are permitted and
their allocated blocks count toward the same 8GiB cap. No regular scratch file or
nested directory is permitted there. Empty directories and failed attempts are
retained; no broad cleanup is performed. Scanner sandbox writes remain unchanged;
this short socket path serves only the local Ansible controller before scanning.
The bootstrap and main helper were AST-parsed in memory, with no pycache and no
actual Ansible/node phase, socket/server startup or application execution.

## Actual execution, October25 2026

The final frozen source `control-source/bortus-cached-complete-60ef83299913`
(manifest `60ef8329991372763f537d24e6664dd4ff3f6bdb2c271cd96019cad4e32ee167`)
completed the privileged read-only cache probe and export, then the offline
F-only scan. All17 reachable blobs passed complete hashes. The retained private
OCI archive is1,149,327,360 bytes, SHA256
`fa7df63ec2a22c2eedff17a16e5d1e7b555d6b93802b5c470aafdccad90731d4`.
The original live Pod/image remained Ready and unchanged; no image was executed
by the audit. The new archive hash differs from the historical tar hash because
the export envelope is newly generated; its exact root image remains3b076fb9….

Actual fresh findings: **5 critical,99 high,160 medium,154 low,3 unknown**.
Results SHA256 `a1801bae5afa75f326bb3084e2f9e5684339262eecac56c036c053ad7c85f51e`.
This closes missing exact-image coverage; it does not fix these findings.
The private evidence root is `FBASE/bortus-cached-runtime-audit-20261025`,
attempt `3da0b68becea`, scan `bortus-cached-3da0b68becea`. Root sent this evidence
to the existing separate BORTUS owner chat. Application remediation stays there;
no unfinished BORTUS release was merged by this maintenance chat.
