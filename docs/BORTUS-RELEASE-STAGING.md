# Immutable image export and sequential preload

`stage-bortus-release-image.py` consumes the completed receipt from the
[immutable builder](BORTUS-RELEASE-IMAGE.md), pinned by its SHA-256, exact full
source commit and exact `sha256:` config image ID. Pending/failed receipts,
source-label mismatches and any runtime-accepted claim refuse. Export and
preload use separate deterministic, exclusive mode-0700 run directories under
the operator-owned runtime parent, which may be mode 0755 without group/world
write. Their files are exclusive mode 0600. Pinned nofollow directory/file
identities and file/directory/parent fsyncs precede dispatch. Existing runs are
never reopened, overwritten, adopted or replayed.

After manual inspection of a retained failed attempt, the migration owner may
explicitly authorize a fresh preload with `--attempt-id <unique-lowercase-12hex>`.
This optional preload-only ID appends `-attempt-<id>` to both the root run and
each remote stage, and is bound in the closed request, reply and receipts. It
does not change the immutable image/tag or bypass tag absence checks. Reusing
the same attempt, an existing stage or a destination release tag still refuses.
There is no automatic retry; the omitted-ID default paths remain unchanged.

Export first checks the exact Docker tag's config ID and all five source/owner
labels on `james@192.168.0.4:2002`. A durable pending receipt precedes Docker
save of that tag. Received archive chunks are bounded and written directly to
the new protected `image.tar`; export errors, timeouts or lost replies leave
an unaccepted partial and pending/uncertain outcome. The helper verifies the
complete regular-file/directory tar inventory, manifest's sole exact tag,
selected config hash/labels/Linux amd64 platform, and ordered layer diff IDs.
Opaque gzip layer bytes are streamed through bounded decompression to verify
their uncompressed diff IDs; raw blob digests are retained separately. Config
environment fields are never returned or put in metadata logs. It re-inspects
the source Docker identity after save before completing the export receipt.
No source tag creation or Docker image running is performed.

Archive bounds are 4 GiB compressed/plain total and aggregate expanded layers,
4,096 members, 1,024 selected layers, 8 MiB manifest/config metadata and 8 KiB
PAX path extensions. Paths, links, unsupported extensions, duplicate members,
unexpected metadata or nonzero trailing tar payload refuse. Selected-platform
resolution is limited to one Linux/amd64 manifest from at most 64 index
descriptors. Unsupported/ambiguous image formats fail closed. These are image
staging bounds, separate from native Secret request ceilings.

```sh
python3 scripts/migration/stage-bortus-release-image.py export \
  --build-receipt /approved/runtime/bortus-release-<commit>/record.json \
  --receipt-sha256 <pinned-build-receipt-sha256> \
  --source-commit <full-lowercase-40hex> \
  --config-image-id sha256:<exact-64hex-config-id> \
  --runtime-parent /home/brajam/.local/share/branconet-migration
```

For `preload`, additionally supply `--export-receipt` and its independently
pinned `--export-sha256`. The caller supplies only a bounded JSON line with
`sudo_password` through its existing protected stdin pipe; never place that
value in arguments, shell history, files, reports or logs. This tool does not
read operator credential files. The password passes only in memory through
SSH stdin to `sudo -S -p '' -v`; subsequent containerd commands use `sudo -n`.
Authorization and those commands share the remote Python session so sudo's
session-scoped timestamp remains usable. Timeouts kill only the newly owned
command PID; they never signal the shared session/process group. SSH's own
local process ownership remains separate. A successful authorization does not
prove that a later policy/expiry check will permit a command.
No interactive prompt or alternate auth fallback is offered. Python cannot
guarantee zeroization of immutable password objects; no such claim is made.

Preload copies and independently re-verifies the pinned export, then handles
only `james@192.168.0.4`, `.5`, `.6`, port 2002, strictly in that order. All SSH
uses BatchMode=yes, StrictHostKeyChecking=yes and ForwardAgent=no. Each node
creates a fresh `.bortus-release-preload-<fullcommit>` stage directly under its
verified owned home, mode 0700, with parent/anchor checks. Either exact tag
spelling (`bortus:release-<commit>` or `docker.io/library/…`) already present
refuses; unrelated images do not block it. The inventory is bounded and must
have the actual expected ctr header. It rechecks tag absence after receiving
the exclusive mode-0600 archive, verifies size/SHA, flushes the file/directory,
and saves a durable remote pending record before import. An existing remote
stage also refuses. No adoption or automatic retry is performed.

The fixed runtime command is `/opt/containerd-k8s/bin/ctr`, address
`/run/containerd-k8s/containerd.sock`, namespace `k8s.io`. After import, the
helper verifies actual root index/manifest content hashes, unique platform
selection, selected manifest's config and ordered raw layer digests, then the
config ID, labels and ordered diff IDs. Metadata captures are bounded in memory;
whole image config/Env objects are not saved as logs. Complete import stdout
and stderr remain separately protected on the node. Fixed reasons are returned
on failure. All three root runtime digests must agree; the config ID is retained
as a **different identity**, never substituted for a runtime/manifest digest.

Local intent precedes each SSH call; remote intent precedes import. Lost reply,
invalid/partial metadata, import error or a durability failure stops the
remaining nodes and retains pending/uncertain receipts. The coordinator must
inspect those outcomes explicitly; rerunning this tool cannot resolve them.
Successful earlier node imports are retained and are not undone. Each owned
SSH/import child is waited/reaped; query timeouts are 30 seconds and save/import
operations are limited to 1,200 seconds. A remote operation may outlive a lost
SSH reply. No remote cancellation or cleanup is attempted.

Docker and containerd tags provide no atomic compare-and-set. The coordinator
must hold exclusive source/tag and destination import ownership, exclude
concurrent writes to protected stages and inputs, and recheck source/controller
requirements at release. Checks around dispatch detect drift but do not make
these operations atomic. This tooling never runs an image, deploys a workload,
qualifies a holder, grants admission/RBAC, or proves application/data/migration
recovery. It records `runtime_qualified=false` and `deployed=false`. Historical
fixed-image distribution/recovery receipts remain historical.

Local fixtures exercise public archives and actual POSIX persistence with
mocked Docker, SSH, sudo and ctr responses. They establish tooling behavior,
not a real export/import, power-loss durability or runtime acceptance.

The first actual immutable holder preload stopped before transfer/import when
the old remote commands created new sessions after sudo authorization. Its
protected root/node refused or uncertain records remain retained. Local Python
child tests reproduce the session mismatch and qualify shared-session handling;
they do not execute sudo, SSH, ctr or an operator password. Actual new preload
and holder/runtime acceptance remain with the migration owner.

Root independently verifies selected native commit `15fb94ba`: seven exact raw
files/modes, 86 original artifacts, both unchanged dependencies and the final
26 focused/64 combined release cases. After integration, all 249 current
`test_bortus*.py` migration-helper cases pass under WSL without skips. Source
and test inputs remain unchanged through execution. The [integration receipt](../evidence/bortus-release-staging-integration-20261011.json)
records the exact scope; it grants no actual export, preload or runtime acceptance.

The actual `7e30b9b4` holder export completed at 09:19:37 UTC on 2026-10-11.
The protected 1,150,322,688-byte archive has verified config/source/layer bindings;
its [receipt](../evidence/bortus-holder-source-image-7e30-20261011.json) records
export separately from still-pending three-node preload/runtime/admission.
A pinned Trivy 0.75.0 default image and image-config scan completed with zero
Secret findings and 346 vulnerability entries (67 High, one Critical). Scanner
exit 1 represents findings, not an accepted clean image. Four fixable High entries
are in bundled kubectl's Go/x/net dependencies. Its production remediation and
the inert Node-only holder reachability review remain open; no app entrypoint ran.
