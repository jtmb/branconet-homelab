# Serial current-source Veyra Linux build

The source-only compressed transport component is now
`scripts/migration/veyra-linux-streamed-handoff.py`. Its `inspect --revision <sha>`
derives the original Dockerfile stage/RUN programs, all 21 builder exports,
vendor/computer-use closure and exact pinned compiler/runtime bases. It refuses
host Node substitution. Its library transport verifies file bytes, modes,
UID/GID, integer nanosecond mtimes, symlink targets and hardlink topology across
a bounded deterministic compressed archive before any last-consumer retirement;
unrepresented xattrs and inaccessible inputs fail closed. It never deletes the
producer and has no build, install, publish or deploy CLI.

This is an implemented transport/contract component, **not an executable
streamed-rootfs compiler or an admitted smaller build**. Exact isolated rootfs
instruction semantics, signed builder/runtime OS inputs and native ABI, the
complete simultaneous physical peak, and original final runtime/security gates
still require qualification. The current ordinary npm cache was independently
checked as 4,096 allocated bytes with zero of the 1,087 selected integrity
objects present; no dependency-cache reuse or storage saving is assumed. All old
compiled capsules, protected/refused targets and the original full acceptance
scope remain unchanged.

`veyra-linux-streamed-handoff.py qualify-bases --revision <sha> --lease <path>`
is a separately admitted qualification operation. It uses the original registry
reader and layer inventory to verify both compressed digests and uncompressed
diff IDs for the pinned Node/Rust input streams in RAM. It creates zero payload
files and returns logical/rounded-data counts including superseded layers;
those counts are not a measured unpacked filesystem or a complete compiler peak.
It requires a fresh coordinator lease with `purpose=streamed-base-qualification`,
`growthBytes=33554432`, original source/extension identities, measured native
allocation, `nativeStageActive=false`, the original 20 GiB/15 GiB guards, and an
already active cgroup limited to 1.5 CPU cores/4 GiB. It has not been run while
the native lease is held.

`veyra-linux-oci-chunks.py` implements the final archive transport as a library.
It writes each bounded gzip layer directly into the one seekable OCI TAR,
backfills the content-addressed member header, and independently reads that
closed byte range to verify file contents, ownership/modes, nanosecond timestamps,
hardlink topology and Linux xattrs (including the original restore-node file
capabilities). It creates no separate whole-layer scratch copy and never deletes
producer files. GNU tar provides PAX/xattr encoding; [OCI requires file attributes
and xattrs to survive](https://specs.opencontainers.org/image-spec/layer/).
This authored component still needs the actual full executor, admitted runtime
observations and last-consumer/reference checks; syntax/source inspection is not
an executed roundtrip or a completed image.

The authored producer components are now `veyra-linux-rootfs-producer.py`,
`veyra-linux-copy-handoffs.py`, `veyra-linux-oci-sandbox.py` and
`veyra-linux-source-context.py`. They remain **unrun and unqualified for a full
compiler/image**. Source COPY is gated on an export made by the same original
pinned BuildKit frontend with canonical `.dockerignore` and any original
Dockerfile-specific ignore file. No independent glob approximation or raw APP
working tree becomes an exact source context. Image RUN requires the original
pinned OCI runtime and an actual isolation/ownership/capability qualification;
the original BuildKit-pinned Moby seccomp v0.2.4 source and Apache license are
retained next to the operator. Trusted base extraction has a fixed command,
read-only host tools, cleared environment and a restricted capability set; that
mount is unavailable to image/install RUN instructions.

The separately admitted base qualification actually finished successfully at
**2026-11-06 07:40:26 UTC**. All compressed layer hashes and uncompressed diff
IDs matched the exact current locks. Payloads were streamed in RAM under
256 MiB/1.5 CPU/no-swap limits, with no payload file, extraction, installation or
compiler created. The transient unit was collected and its lease released.

| Exact input | Compressed bytes streamed | Logical regular-file bytes, including superseded layers | 4 KiB rounded file-data bytes | Entries |
| --- | ---: | ---: | ---: | ---: |
| Node 22.23.4 locked base | 79,849,595 | 227,038,720 | 242,036,736 | 7,370 |
| Rust 1.99.0 locked base | 320,632,778 | 910,196,045 | 924,749,824 | 7,285 |

Both locked bases have zero whiteouts and zero unresolved hardlinks. Rust has
three extended-metadata entries, retained as an explicit extraction/parity
requirement. These are authenticated archive counts, **not** an observed unpacked
physical allocation, restored SDK acceptance, native ABI acceptance or complete
compiler peak. The old 8,216,641,536-byte plan is a planning estimate, not an
irreducible lower bound. Npm install/cache coexistence, native post-install work,
compiler working sets, direct handoffs and all final OS/runtime/security inputs
still need complete admission and actual qualification.

Minimal actual lease/log/result records live under the original task root at
`real-gmail-ui/veyra-phase-1/coordination/integration/streamed-base-qualification-20261106*`.
The successful probe used native budget **13,576,361,886**, fresh Linux allocated
**5,757,792,256** and bounded summary growth **33,554,432** bytes, totaling
**19,367,708,574** against the unchanged **21,474,836,480** ceiling. No bulk
derivative needs cleanup from that RAM-only probe; zero payload bytes were
retained or removed. Protected/refused paths and original runtime consumers were
untouched.

Coordinator: `01a188fc-d3ed-7dc2-ab95-e0eed8a793ec`. Executor:
`scripts/migration/veyra-linux-build.py`, maintained in this existing migration
checkout. Root owns application/native source, contracts, prior local cleanup,
merge, publication, charts/Flux and final product acceptance.

This command builds one complete candidate from the final clean reviewed source.
It runs serial compiler stages and emits one final OCI image. Source preparation
has not acquired binaries, installed dependencies or started a builder.

## Storage and ownership

Every generated file stays below the existing approved WSL task root:

`/home/brajam/.local/state/ingenium-release/skill-zen-fix-1792810845`

It is the Ubuntu ext4 VHDX on Windows C: `EE22980A`, paired with the existing
approved native NTFS root. The combined ceiling is **21,474,836,480 bytes**;
Windows C: and destination retain **16,106,127,360 free bytes**. Platforms run
serially. The Windows-stage 4 GiB growth estimate is not reserved again during
an inactive Windows stage.

Only these new subtrees are written:

| Path relative to existing root | Consumer and retirement |
| --- | --- |
| `b/current/context`, `b/current/browser-extension` | Exact committed first-party sources and eight canonical browser files; retire after final image |
| `real-gmail-ui/veyra-phase-1/linux-image/tools` | Pinned BuildKit tools; retire after final compiler/image consumer |
| `b/current/store`, `b/current/runc`, scoped HOME/XDG/TEMP/cache directories | Current compiler phase; verify stopped identities and retire before the next phase |
| `b/current/handoffs/{budget,swarm,rust,node}` | Actual current successful producer exports; byte/metadata fingerprint before every consumer; retire after last consumer |
| `b/current/veyra-linux.oci.tar` | Root exact-image qualification and existing publisher; retire after verified immutable registry reconstruction |
| `b/current/*-build.log`, `*-daemon.log`, `*-metadata.json`, `owner.json`, `result.json` | Minimal original observations and provenance; retain unique records |

The old private `b` directory is preserved and counted. Only a previously absent
`b/current` child is created. Existing current outputs or tools cause reconciliation
rather than replacement or a new attempt root. The current complete storage
measurement uses the existing approved guard's root-owned
`du -x -s -B1 -- <task-root>` authority. It does not open private recovery or old
builder contents. Actual root identity and destination filesystem are checked.

Regeneration is the exact committed source/locks, canonical browser source,
recorded command and pinned tools. Original source, credentials, models, recovery,
unique failures and all refused targets are protected. Native/prior-root deletion
remains exclusively Root-owned. No generated disposable files were created during
preparation; removed bytes are zero.

## Exact producer graph

The export-target-only proposal is
`scripts/migration/veyra-linux-stage-exports.patch`. Root independently matched
all 21 runtime builder COPY source paths, preserved vendor/computer-use and
Swarm/Rust closures, integrated the 37-line patch and updated the existing build
lock. `compatibility` remains the default final Dockerfile target. Root also
corrected the observed license collector's API/Swarm workspace selection while
preserving exact local-manifest completeness, registry, checksum and license checks.
Root will provide the final source identity after reconciliation.

One executor invocation performs these phases:

1. **Budget:** real `veyra-budget-artifact`, using the current locked npm graph
   and canonical bundle command. Export the actual plugin/provenance.
2. **Swarm:** real `veyra-swarm-artifact`, with the previous budget export supplied
   as `swarm-budget-builder`. `node-dependencies` is overridden by the exact
   locked Node base image solely to supply its unchanged Node binary. Compile
   the canonical Rust exporter/worker and actual contract/declarations/notices.
3. **Rust API:** real `veyra-rust-artifact`; `builder` supplies only the same
   immutable locked Node base binary. The current Rust API source/lock is compiled
   with actual notices. This avoids triggering the Node application stage early.
4. **Node/frontend:** real `veyra-node-artifact`, using the actual generated Swarm
   stage root. Original Core/API/extension/frontend builders, vendor and pinned
   computer-use producers run. Export precisely the current runtime closure.
5. **Image:** original requested final Dockerfile target, supplied with those real
   successful stage exports as named contexts. Build current runtime OS/tools,
   browser, speech sources, startup validation and final OCI export.

At each boundary the original client and daemon PID/start identities must be
stopped. The actual output is fingerprinted and checked against its source
identity before compiler/cache retirement. The Swarm worker, contract, TypeScript,
plugin and notice hashes are checked against the actual release. Rust binary,
lock and notices are checked against its actual compiler receipt. Node's source
receipt and generated public contract must match the original source and actual
Swarm output. No old compiled capsules or old successful application images enter
these handoffs.

The required browser named context is the canonical eight-file directory under
`real-gmail-ui/veyra-phase-1/windows-source/integrations/browser-extension`.
The existing source verifier determines its hash at invocation. BuildKit receives
`--local veyra-browser-extension=...`,
`--opt context:veyra-browser-extension=local:veyra-browser-extension` and the
matching `VEYRA_BROWSER_EXTENSION_SHA256` argument.

## Phase peak and admission

`scripts/migration/veyra-linux-serial-budget.json` contains the reviewable planning
components, uncertainties and input facts. It is a proposal, not execution
permission or a measured successful build. All 1,087 selected Linux/x64/glibc npm
registry identities matched the lock; reported unpacked content is 1,039,887,981
bytes/61,784 files. Eighty legacy packages omit size metadata and remain covered
by allowance. Browser inputs are 685,019,718 logical bytes; the locked Rust base
records 320,632,778 compressed bytes. Tools are 92,218,962 archive bytes plus
129,254,995 selected binary bytes at acquisition. No package/image payload was
acquired for these source/metadata checks.

| Phase | Planned simultaneous growth bytes |
| --- | ---: |
| Tool acquisition/extraction | 264,241,152 |
| Budget | 3,184,525,312 |
| Swarm compiler/export | 3,855,613,952 |
| Rust API compiler/export | 3,653,238,784 |
| Node/frontend/export | 6,606,028,800 |
| Runtime/complete OCI export | 8,216,641,536 |

The whole candidate admits the **maximum phase**, 8,216,641,536 bytes (7.6523 GiB),
including retained prior exports, active store/snapshots, downloads/compiler work,
output coexistence and margin. Expired compiler stores are not summed. GC is not
assumed capable of deleting active references. Root must review the estimate and
freshly measure a retained paired baseline of at most **13,258,194,944 bytes**
before admission. Unpacked base allocation, legacy npm sizes, compiler scratch,
compression and actual exports remain planning uncertainties until observed.

Before every actual phase, the executor remeasures the entire WSL allocation,
checks actual retained-export sizes against the phase allowance and verifies the
upcoming live working/output peak against the unchanged ceiling and both floors.
A watchdog checks actual allocation/floors during compilation and cancels only
its owned client on failure. No unrelated process is stopped.

## Commands and fresh lease

Source-only inspection:

```powershell
$builder = wsl.exe -d Ubuntu --exec wslpath -a (Join-Path (Get-Location) 'scripts/migration/veyra-linux-build.py')
wsl.exe -d Ubuntu --exec python3 -B $builder inspect --revision <final-clean-reviewed-commit>
```

Root supplies a fresh UTF-8 JSON admission inside the same existing task root:
`owner` (coordinator ID), `at` (UTC, under 180 seconds old), `platform: "linux"`,
`exclusive: true`, `nativeStageActive: false`, final `sourceRevision`, canonical
`sourceSha256`, `extensionSha256`, measured positive `nativeBudgetBytes`, reviewed
`growthBytes`, and `growthPhases` from the proposal. `growthBytes` equals the
maximum complete phase sum. These are measured execution inputs under the existing
platform lease, not a new human approval workflow.

After Root releases that lease and fresh capacity fits:

```powershell
wsl.exe -d Ubuntu -u root --exec python3 -B $builder run --revision <final-reviewed-commit> --lease <fresh-Root-admission> --target compatibility
```

This uses the previously qualified isolated BuildKit v0.34.1 route, private Unix
socket, private overlayfs/runc state and task-scoped HOME/XDG/TEMP/npm paths. The
pinned archive SHA-256 is
`a59539daf547fe0958efe2d07e41c0a6944e1112a66d7e519ec1cf5b673ef15b`.
Only its three independently pinned tools are extracted. Max parallelism is one;
RUN operations have a 4 GiB memory/swap ceiling and 150% CPU quota. The per-phase
3 GiB private GC target is a cache preference, not an active-working-set bound.
No new Docker/containerd global state, host service or cluster resources are used.

## Completion and cleanup

The existing complete `ops/oci_image.py` parser verifies the final archive and
source/repository/role/browser labels. Root then owns actual workflow qualification,
existing `ops/publish-image.py`, immutable registry readback, reviewed charts,
singleton local validation and Flux. Actions remains disabled. Packaging creates
no worker enrollment, speech/model activation, writable database cutover or R14
replacement.

Cleanup checks original source/locks, exact output ownership, filesystem identity,
all observed process handles/maps/mount namespaces, outside hard links and pinned
regeneration. It recognizes zero-device whiteouts only in its new OverlayFS
snapshot subtree. Every removed path/allocated byte count and retained failure
is recorded; a failed safety check stops advancement and protects that exact target.
The final OCI archive and minimal provenance/logs survive for Root's concrete next
consumer. Linux allocation recovery is reported separately from Windows free space;
no VHDX recovery or compaction is implied.

Producer, export-validation and acquisition failures enter a separate stopped-
invocation cleanup path. It verifies the original PID/start identities are
terminal, original source/locks and failure log/metadata hashes survive, and
successful handoffs remain unchanged. It then applies the same reference,
filesystem and hard-link checks to this invocation's reproducible scratch/store
and any authenticated tool archive. An earlier refused pass/target is excluded
from retry. Stop failures retain referenced targets with their exact PID/reason.

Potential core/minidumps, traces, heap/profiling files, compiler crash reports,
npm debug logs and Cargo build diagnostics are preserved outside the disposable
store. Closed regular files move on the same filesystem into
`b/current/diagnostics`, with original identity, hashes, bytes and preservation
reason recorded; their retained blocks are never counted as recovered. An
unproven preservation check retains the exact target. Successful exports retain
their concrete remaining consumers; unqualified partial OCI/exports/downloads
retain exact paths/bytes and the missing regeneration or diagnostic proof.
An ordinary stopped compiler store is not retained solely because its build failed.

Primary references: [BuildKit v0.34.1](https://github.com/moby/buildkit/releases/tag/v0.34.1),
[buildctl local/OCI exports](https://github.com/moby/buildkit/blob/v0.34.1/docs/reference/buildctl.md),
[named contexts](https://github.com/moby/buildkit/blob/v0.34.1/frontend/dockerui/namedcontext.go),
[worker/GC configuration](https://github.com/moby/buildkit/blob/v0.34.1/docs/buildkitd.toml.md),
[Dockerfile resource controls](https://github.com/moby/buildkit/blob/v0.34.1/frontend/dockerui/config.go).

## Observed streamed-input and isolation qualification (November 6)

These observations qualify inputs and the closed executor controls; they do not
admit the full compiler or accept a runtime image. The original six-phase
capacity, source, lease, cleanup and resource requirements still apply. Root owns
the complete streamed orchestrator and its final review.

The authenticated locked npm input pass verified all 1,087 unique SHA-512/SRI
objects selected by the unchanged lock (1,243 installation paths), streaming
them without caching, extracting or installing package payloads. Unique inputs
were 262,651,928 compressed bytes, 1,041,915,673 logical file bytes and
1,216,532,480 bytes rounded to 4 KiB per data file. Installation-path weighting
was 1,240,391,680 rounded data bytes, before directory inodes, workspaces,
postinstall outputs, npm state, compiler work and export coexistence. This is
an input measurement, not an installed dependency-tree or peak measurement.
The corrected bounded pass used 47.1 MiB peak memory; the original 256 MiB
failed attempt and kernel evidence remain preserved.

The closed source-context/OCI control passed at 2026-11-06T10:05:42Z under a
512 MiB memory and 1.5 CPU envelope, with a distinct 768 MiB closed-probe growth
reservation. The original pinned Dockerfile frontend projected 4,092 included
canonical files and excluded the generated index. Actual pinned Node 22.23.4
on glibc 2.36 ran in the qualified OCI namespace with seccomp filtering,
NoNewPrivileges, original bounded capabilities, protected host mounts and no
host tools, GPU, container socket or secret environment. Actual ownership and
UID/GID 1108 controls passed. The original restore helper retained UID 0,
GID 1108, mode 0750 and cap_chown/cap_fowner. The actual transport preserved
root metadata, nanosecond times, bytes, symlinks and hardlinks.

A separate actual OCI layer preserved security.capability, ownership, modes,
nanoseconds and hardlink topology. The first verifier correctly refused a
header-only xattr comparison: GNU tar writes inode xattrs on the data-bearing
member rather than repeating them on the hardlink header. The narrow correction
resolves the preceding archived inode and still rejects conflicting hardlink
metadata. The same original compressed layer then passed independently, without
changing its bytes (SHA-256
`301fdfc8ce1e530224221bc6b85b8780ba4802a33624db3b7bd1d9b05fd59e9a`).
The original 876-byte incomplete outer archive remains unique failure evidence.

The original parent-gzip/bootstrap failure and all minimal logs, source proofs
and closed-control results remain under the existing task root. After their
last consumers, the original ownership/reference/artifact checks retired
850,767,872 Linux allocated bytes of tool copies, compressed inputs, frontend
scratch, the closed probe root filesystem and fixtures. Filtered canonical
context and pinned OCI runtime remain for the reviewed full-build consumer.
No Windows disk recovery, VHDX compaction, full compiler execution, registry
publication or workload deployment is claimed by these controls.

The current prepared source is `45b1278d826e9c1e44cededf15d33c0fd75618cf`,
canonical SHA-256
`332da4ac2f32b2f2015139c762f1743afd523f5e44decefdb263333cef7d5fb8`.
Four bounded source transitions preserved the original frontend/OCI observations,
reconstructed the old canonical Git authority and verified every current included
byte/mode. The same 4,092 included paths and one omitted `.gitkeep` remain; no
frontend or OCI probe was replayed. The final readable coordination receipt is
`coordination/integration/source-context-delta-45b1278d826e-result.json` under
the existing phase root. Original browser pins and base/APT/npm/Rust/Swarm/voice
inputs remain unchanged; the declared runtime selects full Chromium and ffmpeg.

The [current streamed proposal](../scripts/migration/veyra-linux-streamed-budget.json)
targets Root's driver `766b0a668e8a0a3256a5b56d78f9aeaa7424508db15d58dbdb49abb442dc9ced`.
It accounts for split locked extraction/native hooks, actual validated compressed
COPY transport, the archive's last consumer before browser installation, complete
Node export/file bounds and selected-browser per-layer retirement. Its maximum
is **4,385,898,953 bytes**, requiring a retained paired baseline no larger than
17,088,937,527 bytes under the unchanged 20 GiB ceiling. This is a conservative
proposal with explicit unmeasured allowances, not an irreducible minimum or an
accepted compiler run. Fresh complete admission, actual output/runtime qualification
and Root's go/no-go remain outstanding.

## Temporary task ceiling amendment (November 6)

The human explicitly authorized: "I approve the temporary 23 GiB ceiling. Keep
the 15 GiB reserve, resume the goal, and finish the entire plan."
This amendment applies only to the existing paired Veyra Native/WSL roots for
the current plan. It does not amend another task, move outputs, authorize a
compiler launch, stop Ubuntu or relax any preservation requirement.

The original Linux admission and live guards now use 24,696,061,952 bytes
(23 GiB), retaining both 16,106,127,360-byte free-space reserves. Each fresh
full lease must explicitly bind `combinedTaskCeilingBytes=24696061952` and
`minimumFreeBytes=16106127360`. Native/Linux serialization, freshness, source
and extension checks, all six phase estimates, 4 GiB/1.5 CPU controls and cleanup
requirements remain unchanged. The 4,385,898,953-byte maximum growth therefore
requires a freshly measured retained paired baseline of at most
20,310,162,999 bytes. Original 20 GiB observations above remain historical
evidence. Source `45b1278d826e9c1e44cededf15d33c0fd75618cf` and driver
`766b0a668e8a0a3256a5b56d78f9aeaa7424508db15d58dbdb49abb442dc9ced`
remain frozen; actual full admission and Root's compile go are still required.
