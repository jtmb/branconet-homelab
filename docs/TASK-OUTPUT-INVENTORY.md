# Maintenance output ownership and reconciliation

The existing authorized generated-output root is retained:

`/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025`

Windows accesses that same filesystem through
`\\wsl.localhost\Ubuntu\home\brajam\.local\share\branconet-migration\local-image-build-offload-20261025`.
It is ext4 UUID `3c792469-ea0e-4a2c-98e8-1185b141607b`, backed by
`F:\branconet-build-storage\native-build-20261025.ext4`. The owner of this
maintenance work is chat `01a12045-bf7e-73b3-8557-752d17c72ffd` and branch
`codex/cluster-maintenance-ansible`. All new operator scratch and receipts use
the existing `operator-control` directory inside this root. No new build,
dependency copy or scanner-cache root is created on C:, D: or another volume.

The earlier `F:\branconet-migration-artifacts\maintenance-storage-20261025`
contains protected execution/source evidence and the already-running local
charts publisher's persistent state. Preserve those existing owners and active
paths; do not migrate or duplicate them. New disposable work uses the declared
ext4 root. Existing application/source repositories, Kubernetes runtime data,
NAS media, encrypted backups and rollback archives remain protected.

The private, current hierarchical inventory is
`operator-control/storage-inventory-current.json`. It enumerates current
top-level paths and retains descendants with an explicit owner/reason or failed
safety check. BORTUS application work belongs to its separate owner. Source and
execution snapshots without an established regeneration manifest, unreadable
builder state, and paths without proved ownership/inactive references remain
retained. Their names alone never authorize deletion. A broad allocation walk
encountered unreadable builder directories; its result is incomplete and is not
a filesystem or Windows recovery claim. The inventory is a reconciliation record,
not a claim that every historical generated artifact has been cleaned.

At October25 22:12 UTC, a root-visible process/FD/map/mount check and exact
empty-directory checks allowed removal of these four owned scratch directories:

| Path relative to the declared root | Allocated bytes removed |
| --- | ---: |
| `operator-control/ansible-local` | 4096 |
| `operator-control/cache` | 4096 |
| `operator-control/home` | 4096 |
| `operator-control/tmp` | 4096 |

Total Linux filesystem recovery was **16,384 allocated bytes**. No Windows disk
recovery is attributed to this operation. Exact checks and per-path regeneration
commands are retained in `operator-control/empty-scratch-cleanup-20261025.json`.
The source and lockfile repositories survive; no tracked files, dependencies,
runtime artifact or unique evidence was removed. This small reconciliation is
separate from the earlier 55,587,958,784-byte verified node cleanup.

No local build or large controller download is part of the current stateless
upstream transition. Before the remote runtime pulls, measured C: free space was
113,524,342,784 bytes, the native output filesystem had 22,173,327,360 bytes
available, and every node could retain 15 GiB after a 2 GiB runtime-stage bound.
The actual measurements remain in `operator-control/stateless-capacity-preflight.json`.
Future build stages must configure compiler/cache/temp paths in the declared
root, and npm must receive process-scoped cache/log/AppData paths before launch.
No npm build was invoked here. Recreate required empty temporary directories
explicitly before a stage; reconcile them again afterward.

## Successful primary compiler-cache cleanup, 22:23 UTC

The three successful primary local builders for http-echo, Whoami and Unpackerr
passed complete OCI archive/blob checks, source/recipe hashes, retained Git
commit checks, live Docker/process/map/mount inspection and exact-path/inode
checks. Six generated cache directories were removed with fd-relative,
symlink-resistant deletion. No older copied cache, failed state or other chat's
builder was included. A final full comparison proved every protected recipe,
source file, log, metadata file and OCI archive unchanged.

| Path relative to the declared root | Allocated bytes removed |
| --- | ---: |
| `http-echo-ff0892f93064-79c5c595f699/state/runc-overlayfs/content/blobs` | 47149056 |
| `http-echo-ff0892f93064-79c5c595f699/state/runc-overlayfs/snapshots/snapshots` | 592498688 |
| `whoami-d3adf8da75b5-b61a99ebb346/state/runc-overlayfs/content/blobs` | 53489664 |
| `whoami-d3adf8da75b5-b61a99ebb346/state/runc-overlayfs/snapshots/snapshots` | 957849600 |
| `unpackerr-e91ac1375ec9-8948f8318133/state/runc-overlayfs/content/blobs` | 72339456 |
| `unpackerr-e91ac1375ec9-8948f8318133/state/runc-overlayfs/snapshots/snapshots` | 1180573696 |

Generated-layer removal totaled **2,903,900,160 allocated Linux bytes**;
including the four empty directories, this checkpoint removed **2,903,916,544
allocated bytes**. Native available space was observed changing from
21,994,999,808 to 24,898,752,512 bytes during the larger operation; concurrent
filesystem activity means that difference is reported separately from the
measured deleted allocations. No Windows recovery or compaction is claimed.

[Exact public deletion receipt](../evidence/controller-generated-cleanup-20261025.json).
The private cleanup plan includes protected-file hashes and exact historical
regeneration commands. Those commands document reproducibility; they do not
authorize new third-party derivative builds. All other existing root paths
remain classified in the current private inventory, with retained evidence or
concrete unfulfilled safety/ownership checks. No data, runtime image, source
repository, encrypted backup or recovery artifact was pruned.

## Media checkpoint scratch reconciliation, 23:27 UTC

No compiler or dependency caches were created. Backup archives, their distinct
API/SQL observations, frozen sources, keys and encrypted NAS metadata remain
required recovery/acceptance evidence under the declared root. Raw new receipts
are retained there; repository documentation records concise results/pointers.
After the Ansible syntax check and all copy/observation processes finished, the
empty generated scratch tree passed complete process/map/mount and inode checks:

| Removed path relative to declared root | Allocated bytes |
| --- | ---: |
| `operator-control/tmp/ansible-home` | 4096 |
| `operator-control/tmp/ansible-local` | 4096 |
| `operator-control/tmp` | 4096 |

This new lifecycle removed **12,288 allocated Linux bytes**, with no Windows
recovery claim. The original sources, all archives and prior cleanup receipts
remain. Exact proof is `operator-control/media-scratch-reconciliation.json`.
Recreate the configured empty paths explicitly before a future Ansible stage.
The current private inventory includes the new protected media acceptance/
backup subtree; every earlier retained exception keeps its documented reason.

## Unpackerr checkpoint reconciliation, 23:54 UTC

All paths below are relative to the declared F:-backed ext4 root. Exact proof:
`operator-control/unpackerr-scratch-reconciliation.json`. After source/hash,
ownership, inode and complete process/map/mount checks, these current-stage
reproducible binary/payload files and empty scratch directories were removed.
No build or dependency cache was created.

| Removed path | Allocated bytes |
| --- | ---: |
| `upstream-unpackerr-20261025/vendor-unpackerr` | 19034112 |
| `unpackerr-fixture-y0n8j8as/unpackerr` | 19034112 |
| `unpackerr-fixture-y0n8j8as/downloads/Branconet.Unpackerr.Disposable.Fixture/fixture.zip` | 8192 |
| `unpackerr-fixture-y0n8j8as/downloads/Branconet.Unpackerr.Disposable.Fixture/original-download.nfo` | 4096 |
| `unpackerr-fixture-y0n8j8as/outside-sentinel.txt` | 4096 |
| `unpackerr-fixture-y0n8j8as/mock-library/Subs/fixture.srt` | 4096 |
| `unpackerr-fixture-y0n8j8as/mock-library/movie.mkv` | 4096 |
| `unpackerr-fixture-y0n8j8as/mock-library/Subs` | 4096 |
| `operator-control/tmp/ansible-home` | 4096 |
| `unpackerr-fixture-y0n8j8as/downloads/Branconet.Unpackerr.Disposable.Fixture` | 4096 |
| `operator-control/tmp/ansible-local` | 4096 |
| `operator-control/tmp` | 4096 |
| `unpackerr-fixture-y0n8j8as/mock-library` | 4096 |
| `unpackerr-fixture-y0n8j8as/tmp` | 4096 |
| `unpackerr-fixture-y0n8j8as/downloads` | 4096 |

Total: **38,125,568 allocated Linux bytes**. No Windows disk recovery is claimed.
The exact source/command and required failed-fixture binary survive for
regeneration; use the command in the private reconciliation receipt under the
same bounded isolated user scope. Config/source manifests, keys, all encrypted
archives, NAS copies and unique observations/logs remain protected.

Retained current-stage exceptions:

- `unpackerr-fixture-7zb5sjyf`: Preserve the complete failed toolchain-guard fixture and its exact binary input; no failed-state cleanup authorized.
- `unpackerr-fixture-y0n8j8as`: Unique passing result, execution logs and exact runtime fixture config retained; reproducible binary/payload copies removed.
- `upstream-unpackerr-20261025`: Required configuration backup, native verification key, before/after/restart receipts and distinct failure evidence retained.

All previous retained exceptions remain unchanged. No older artifacts, runtime
images/volumes, NAS media, source repositories or other owners were pruned.
Explicitly recreate configured operator scratch before a future Ansible stage.

## phpMyAdmin checkpoint reconciliation, October26 00:20 UTC

No build, dependency install, source-tree dependency copy or local image export
ran. All new controls, private observations and distinct recovery archives are
inside the declared F:-backed ext4 root. The SQL/HTTP checks kept account data,
credentials, cookies and response bodies in memory. Exact current receipt:
`operator-control/phpmyadmin-upstream-adoption.json`.

After every producer and NAS copy completed, the empty scratch directory passed
ownership, inode, process/FD/map/mount and root containment checks:

| Removed path relative to declared root | Allocated bytes |
| --- | ---: |
| `operator-control/tmp` | 4096 |

Exact proof: `operator-control/phpmyadmin-scratch-reconciliation.json`.
This is **4096 allocated Linux bytes**, with no Windows disk recovery claim.
Regenerate by explicitly creating the private operator-control/tmp directory
before the recorded metadata encryption/copy commands.

Retained current-stage exceptions:

- `upstream-phpmyadmin-20261025`: required verification key and unique original,
  after/restart SQL/login observations, including failed verification evidence.
- `control-source/upstream-phpmyadmin-20261025`: exact executed source versions
  needed to reproduce both the failed checks and accepted behavior.
- `operator-control/phpmyadmin-before-recovery-metadata.tar.age` and
  `operator-control/phpmyadmin-final-recovery-metadata.tar.age`: required distinct
  authenticated recovery evidence with verified NAS copies; final archive does
  not duplicate the baseline/key/source ancestor bundle.
- `operator-control/phpmyadmin-existing-vendor-findings.json`: required exact
  package/advisory rows and original prior-scan bindings; current security review
  is incomplete. Original scanner inputs/reports and rollback images survive.

Existing publisher state and every earlier retained ownership, safety-check,
failed-state and runtime exception remain unchanged. No PVC/NAS data, source
repository, model, image, volume, other project or older artifact was pruned.
