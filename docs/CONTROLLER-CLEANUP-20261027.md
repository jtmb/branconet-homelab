# Completed controller cleanup, October 27, 21:47 UTC

Removed **27,804,061,696 allocated Linux bytes** from the existing F-backed
migration filesystem: 9,585,721,344 from 64 completed publisher stages and
18,218,340,352 from six stopped private build caches. This is separate from the
25,709,182,976 bytes already retired on the Kubernetes nodes. No workload,
runtime image, volume, model, NAS media or application data was removed.

The latest user cleanup contract supersedes blanket retention of continuing-task
outputs for another 72 hours. These outputs' final consumers had finished;
their provenance and absence of active references were checked before removal.

| Removed cache, relative to the owned root | Allocated Linux bytes |
| --- | ---: |
| `jackett-9090c0aa2ee9-c1da97fb5e55/state` | 2,847,227,904 |
| `mealie-766e20940e51-251e7197fbb8/state` | 2,413,932,544 |
| `mealie-c692b307681c-540ac3a24c60/state` | 2,439,704,576 |
| `homepage-0946c373ff28-a5d9b4936405/state` | 3,470,241,792 |
| `homepage-2416f68cc1cb-94943ae43cb2/state` | 3,521,310,720 |
| `homepage-aa157513b991-5314aaaa2d8a/state` | 3,525,922,816 |

Owner: migration chat `01a12045-bf7e-73b3-8557-752d17c72ffd`.
Root: `/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025`.
Physical filesystem UUID: `3c792469-ea0e-4a2c-98e8-1185b141607b`, backed by
`F:\branconet-build-storage\native-build-20261025.ext4`.
[Exact cache paths, identities, bytes and source/artifact bindings](../evidence/stopped-controller-cache-retirement-20261027.json).

The maintained opt-in `scripts/migration/retire-stopped-controller-caches.py`
first qualifies at most three explicitly named stages, then requires the same
frozen source and original identities for `--apply`. It verifies original
completion/worker-stop receipts, complete recursive source manifests, retained
OCI archive hashes and every original blob, original reachable Git commits,
locks, filesystem ownership, hardlink containment and full unit/process/FD/map/
mount exclusions. Docker's running-container inventory was empty. No container
or daemon was stopped. Every protected original matched again after removal.
The worker enforced 512 MiB resident memory, zero swap and one CPU.

Two initial implementation refusals occurred before deletion: Go's virtual
address reservation cannot use an address-space cap as a resident-memory limit,
and the original producer's manifest is recursive. The same operator and exact
paths were reconciled using the original producer contract and actual systemd
resident-memory controls. Original refusal receipts, frozen erroneous sources,
cause diagnostics and successful fresh checks remain. No ownership/reference/
policy refusal was bypassed. Regeneration uses the preserved original pinned
builder helper/context; retained exact OCI artifacts do not depend on caches.
This does not authorize new third-party derivative builds.

The publisher operation used its unchanged source/blob/receipt/lock/reference
checks and native Windows exclusive read handles. Removed 192 copied public
tools and 64 empty `.tools` directories; source exports, all original receipts
and primary tools survived unchanged. Publisher cumulative cleanup is now
**11,832,397,824 bytes across 79 stages**.
[Every removed path and measured bytes, original full receipts and six exact retained exceptions](../evidence/publisher-continuing-task-cleanup-20261027.json).
Each exception lists the missing original prepare/check/publish receipt; the
explicitly protected failed `f2085e8a5d0f4098896b6be87e5e3797` stays intact.
Regenerate copied tools from the retained pinned publisher originals in a
future exclusive stage; never replay publication to recreate temporary tools.
No publisher retry or GitHub Actions run occurred.

After removal, the native filesystem reported **44,796,420,096 available bytes**.
Independent Windows readings were C: 61,399,121,920 and F: 46,939,750,400 free
bytes. No Windows recovery is attributed to Linux deletion; no compaction,
filesystem growth or shutdown was performed. Generated paths are only the small
ownership, plan, diagnostic and reconciliation receipts in `operator-control`;
there is no new build, dependency tree, payload copy or cleanup scratch.

Required operational native restore tools remain for the four unresolved data
recovery bindings and fresh pre-upgrade restore gate; reconcile after those
specific consumers finish. The retained original `rollback-custom-kubectl.elf`
fails exact regeneration qualification: the original source archive contains no
compiled member and no byte-identical rebuild has been proven. Preserve that
sole original witness. `operator-control/tmp/system-commandline-sentinel-files`
still lacks creator/regeneration and complete Windows handle proof. Those exact
targets remain protected. The full original failed builds and data backups
remain; other bulk roots require their own ownership/consumer/reference audit.

This completes these bounded removals, not the full migration/security goal.
Current-writer recovery, supported Longhorn upgrade, remaining compatible fixes,
honest unsupported findings and final normal Seerr/YTPTube IAB/fleet acceptance
remain required.
