# Swarm storage migration handoff

## Subsequent narrow cleanup

James subsequently authorized deletion of identified generated outputs outside
H:, without resuming the migration queues or running new full comparisons.
Three previously observed candidate Webpack compiler caches were removed under
`/home/brajam/.cache/bortus-controlled-perf`: runs `run-96a01c508f66`,
`run-a369b09dcf31`, and `run-511a80059038`, each at
`candidate/.next/cache/webpack`. Their total measured allocation was 591,175,680
bytes. Source/package/lock separation, physical containment and focused live
reference checks passed. No source, fixtures, databases, node_modules, runtime
bundles, run records or H: payloads were deleted. Exact paths and per-target
bytes are in `SWARM-narrow-generated-cleanup-20261113.json` in the existing run.
No Windows free-space recovery is claimed. The retained H: performance copy
predates this intentional compiler-cache cleanup; the old verifier must not be
resumed against an assumed unchanged source tree.

The subsequent bounded existing-record search found 20 additional documented
run/branch compiler-cache paths; all were absent, so no further data was removed.
All 16 physical b8 originals remain retained: saved records do not establish
source-free disposable child targets within those mixed/source/runtime trees.
See `SWARM-b8-generated-cleanup-decision.json` and
`SWARM-narrow-cleanup-final-20261113.json`. This bounded cleanup lane is finished;
no migration or additional cleanup continuation is queued.

**STOPPED by James on November 13, 2026.** The storage-coordinator goal was
paused and cleared. Do not resume queues, scans, copies, cleanup or retirement
without a new user instruction. All owned Swarm storage jobs and their Windows
wrappers have exited. `SWARM-storage-stop-20261113.json` records exact final
identities and source states; no unrelated workload was stopped.

Updated November 13, 2026. Swarm Migration owns Branconet storage decisions;
the storage coordinator maintains the combined register and exclusive executor
assignments. This handoff grants no additional deletion or production authority.

## Current work

- The existing `bortus-controlled-perf` preservation transaction has finished
  rsync; its content and metadata verifier was cancelled at the user's stop.
  Its source directory remains physical, with no source-path cutover or backup;
  only the subsequent explicitly recorded compiler caches were removed.
  Its last pre-stop durable
  receipt still says `copying`; successful cutover and original retirement have
  **not** been established. There is no surviving process to resume automatically.
- Swarm's saved eligible Branconet batch queue finished: 72 moves completed and
  12,465,696,768 allocated Linux original bytes retired, with equivalent H:
  copies and original-path symlinks verified. Its receipt is
  `SWARM-known-queue-results.json`. One captured row contains a literal ellipsis
  and failed source-path qualification before copying. A bounded name listing
  subsequently resolved its one actual child, and a separately authorized batch
  moved `root-private600-independent-a02ecfb8f720`, retiring 24,576 allocated
  Linux bytes. See `SWARM-resolved-name-migration.json`; the original malformed
  row and failure receipt remain unchanged.
  Further scoped batches moved the exact loose `bortus-migration-1438b27.tar`
  archive (1,149,362,176 allocated Linux bytes) and 32 historical test directories
  (171,311,104 allocated Linux bytes, no exceptions). See
  `SWARM-loose-archive-migration.json` and `SWARM-history32-results.json`.
  History batches through b17 completed 516 moves in total. One source,
  `native-master-retained-c29-controls-7ba42fe8b069`, failed the special-entry
  guard at `source/public-owned-0954022f89c7/public.sock`; its original and H:
  copy remain, with no cutover or retirement. Preserve this exact failure and
  do not retry it through another batch. See `SWARM-history32-b12-results.json`.
  Swarm's last recorded attempt on the ordinary
  `F:\branconet-migration-artifacts\maintenance-storage-20261025` preservation
  folder was a separate preservation move that stopped before
  source cutover: Robocopy reported access denied copying NTFS security to the
  assigned H: destination, followed by a missing-file timestamp-restore error.
  The original is intact and the partial destination is retained. Preserve this
  failed check; do not infer successful copying from the conflicting zero exit
  code in the receipt. The coordinator has the exact log and receipt.
  A coordinator-directed same-path continuation then applied source-equivalent
  root access rules and copied payloads with a reliable Robocopy exit code of 1.
  It stopped when Windows rejected restoring the Administrators owner on
  `ubuntu-compaction-result.json`. Both copies remain; source retirement is false.
  See `SWARM-F-maintenance-same-path-continuation.json` and
  `SWARM-F-maintenance-owner-failure.json` in the existing run. Do not bypass the
  owner-preservation failure.
- The storage coordinator owns the next-security and historical-image scopes.
  Its latest reported queues finished. Respect those exclusive assignments;
  this handoff authorizes no restart or further cleanup.

## Records and preserved work

The existing run root is
`H:\AgentArtifacts\projects\branconet\runs\branconet-wsl-stage-20261113T215208Z`.
Use `SWARM-performance-cache-migration.json`,
`SWARM-remaining-known-batch-queue.json`, `phase1-owner-swarm.json`, and
`SWARM-native-image-reconciliation.json` there for exact assignments and results.
Do not repeat the whole-tree inventory.

Ten earlier directory moves completed with original-path compatibility and
6,230,016 allocated bytes of verified duplicate originals retired inside Linux.
These are separate from the unfinished performance transaction. No Windows
free-space recovery is claimed from Linux retirement.

Preserve the exact prior retirement-rejected roots, the failed coredns special
entry target, protected runtime/database paths, active copies, all unique source
and recovery data, and the existing CI-zips junction. No alternate-owner retry
of a refused target is authorized.

## Remaining outcomes

These are historical unfinished outcomes, not authorization to continue after
the stop above. Final completed receipts account for 814 directory moves plus
one archive and 36,738,080,768 allocated Linux original bytes retired. No Windows
free-space recovery is claimed. General batch 8 was active at cancellation:
16 entries had completed their old-path symlinks and 16 originals remained
physical. No interrupted rename needed repair, no backup was retired by the stop
operation, and batch 9 did not start. Preserve all originals, remaining backups,
partial H: payloads and failure receipts.

1. Finish and verify the existing performance transaction and independent queued
   preservation moves without overlapping other executors.
2. Move the ordinary F: maintenance folder with complete content, streams,
   timestamps and effective permissions, preserving its original access path.
3. Reconcile the shared native-build image using existing member records first.
   Whole-image integrity does not prove member obsolescence. No image remount,
   truncation or retirement during the WSL responsiveness issue.
4. Reconcile legacy excess against the shared 50,000,000,000-byte repository
   allowance. Existing approved preservation transfers continue; they grant no
   permanent exception or new build allowance. Physical quota enforcement is a
   separate outcome and has not been established by this handoff.

The intended future source location is `/home/brajam/repos/<project>`. Source
relocation and shared filesystem enforcement are separate phases; this work has
not moved the authoritative checkout or changed the production cluster.
