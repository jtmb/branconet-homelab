# Ruckus same-image HA recovery candidate

The initial candidate was prepared without executing a phase, reader, archive,
SQL query, restore, rollout or restart. Execution checkpoints are recorded below. Root owns review, freeze, Flux changes,
reader creation/deletion, and execution. The existing qualification scripts are
unchanged.

The intended result is the current MySQL **5.7.44** application and data on the
original Longhorn volume's existing two replicas. This is a storage relocation,
not an application or database-version upgrade. The exact image remains
`docker.io/library/ruckusdb-security-20261023@sha256:2f0c391e6c04501862598bbc5446165f8ebba08025168451f6f6447352316349`.

## Preservation contract and observed starting point

This deliberately changes the earlier **untouched original PVC** contract. It
adds one directory and allocates new data blocks on that filesystem. The original
filesystem root's directory mtime/ctime/size will change. Its inode, owner and mode
must remain unchanged. Every pre-existing descendant's bytes, inode, size, mtime,
ctime, owner, mode and symlink target remain strict. Device numbers may change
across CSI attachment and are not used as persistent identities.

The old MySQL files are directly at the original filesystem root. The retained
inspection calls that root `data-0`; it is not an existing `data-0` subdirectory.
The proposed new application directory is:

```
original PVC filesystem /
  [all original files and directories retained]
  security-data-20261025/       # exclusively new sibling
    [complete current claim root copied here]
    data-0/                    # current MySQL application directory
```

The fresh archive contains the **whole current claim**, not just its application
subPath. The restore strips only the archive's logical root alias. Outer claim
directories and metadata are reproduced inside the new sibling, while the live
database mount becomes `security-data-20261025/data-0`.

The original claim is `ruckus-db-data-0`, UID
`2f604004-b45f-4061-bdc4-43f5ca2f7fd8`; its PV UID is
`ac9b38c6-ee0c-4e2b-bfc0-03a188e889d1`. The current claim is
`ruckus-db-data-0-security-20261025`, UID
`0bf707c8-628e-4284-9aa0-35b711c8749b`; its PV UID is
`d6706cd4-91a7-449f-a41f-8434108f047e`. Both remain Bound with Retain policies.

The original inspection at
`FBASE/ruckus-original-ro-inspection-20261025/560ef15e180b` recorded 786,726,912
guest-free bytes, two attached RW healthy replicas, and 216,491,611 original file
bytes. It failed its historical comparison only for the filesystem-root mtime:
1792938130383078658 → 1792950954781991637. The candidate authenticates the original
encrypted archive and pins that inspection. Only that exact historical difference
is accepted when establishing the fresh original inventory. It does not turn the
failed historical receipt into a pass or permit arbitrary old-directory drift.

## New source and inherited primitives

* `scripts/migration/ruckus-ha-recovery.py`: F-only controller, plans, authenticated
  receipt chain, full cold archive, exclusive restore and old-tree comparison.
* `scripts/migration/ruckus-ha-recovery-remote.py`: RAM-only master identity guards
  and normal-application-account SQL observations. Sent through `python3 -B -c`;
  requests including the HMAC key travel on SSH stdin, not argv or disk.
* `scripts/migration/ruckus-ha-recovery-manifest.json`: exact source/dependency
  hashes for freezing. Include the listed existing dependency files at their
  original relative paths in the frozen checkout; `ROOT` is derived from that
  layout.

The pinned SQL observer is `copy-observer-3284b56f3d7e.py`, full SHA256
`3284b56f3d7e7f0a570d84823a3a5b3a1c8067249156450bc061af2dadda3751`, already installed
on master. Its `native`, `SQL`, and `snapshot(administrative=False)` APIs are reused
without alteration. Credentials remain in RAM and the existing Bash pipe FD;
no root SQL, login mutation, grant bypass, or grant escalation is introduced.

The exact existing archive verifier and reader are reused. The pinned restore
program from `qualify-ruckusdb-copies.py` is adapted in memory by checked,
single-occurrence source replacements: fixed `/restore` root, removal of the tar
logical root alias, acceptance of the already-created empty mount root, exact
nested socket-link path, target inode binding and a per-file free-space guard.
O_EXCL, O_NOFOLLOW, path confinement, file hashes, metadata restoration, full
manifest membership, trailing-byte limits and age authentication remain mandatory.

The normal account sees the schemas/grants it is authorized to read. SQL receipts
do not pretend to enumerate inaccessible system accounts. The complete physical
archive and byte-identical full restore cover those files; normal-auth after and
restart observations cover all visible rows, DDL, objects, settings and account
identity using the unchanged observer. The expected counts come from the **fresh
5.7.44 baseline**, not the original historical 3,962-row snapshot.

## Phase flow and exact CLI shape

Set `FBASE` to
`/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025`.
`H` below denotes the frozen `scripts/migration/ruckus-ha-recovery.py`; `KEY`
denotes the existing private hex HMAC key. Do not echo the key or use shell tracing.
Every command reads it only from stdin. Each phase creates a unique private F
directory and prints only receipt path, SHA256 and status. Every receipt contains
a keyed authentication value; every subsequent phase requires its exact SHA256.
Do not modify a frozen source after taking a baseline: the entire chain binds both
new Python source hashes.

1. Root pauses **the bot** through Flux, leaves current DB Ready1, and confirms
   no other clients can write during the recovery window. Capture a fresh stable
   normal-auth baseline:

   ```sh
   python3 -B "$H" baseline < "$KEY"
   ```

2. Root pauses the DB through Flux too. Generate the cold-reader plan using that
   baseline. Review and apply the plan through the established owner workflow;
   record exact Pod and NetworkPolicy UIDs. This mounts both claims read-only,
   on workernode2, with no fsGroup and deny-all ingress/egress.

   ```sh
   python3 -B "$H" plan-cold --baseline "$B" --baseline-sha256 "$BS" < "$KEY"
   python3 -B "$H" cold --baseline "$B" --baseline-sha256 "$BS" \
     --reader-run-id "$RID" --reader-pod-uid "$PUID" --reader-policy-uid "$NPUID" < "$KEY"
   ```

   The cold phase requires both Flux and Deployment replica counts/status0,
   native identities unchanged, no foreign claim users, and the original two
   replicas already healthy/RW. It authenticates the old archive, fingerprints
   the old root with the new sibling absent, and writes/authenticates/reobserves
   the full current claim. Remove only the recorded cold-reader resources using
   UID preconditions; retain their plan and receipts.

3. Generate the restore plan, binding fresh baseline and completed cold receipt:

   ```sh
   python3 -B "$H" plan-restore --baseline "$B" --baseline-sha256 "$BS" \
     --cold "$C" --cold-sha256 "$CS" < "$KEY"
   ```

   **Applying this plan is the first original-filesystem metadata mutation.**
   Kubelet's safe subPath setup creates the absent sibling directory. The PVC
   volume source is RW to permit that one bind; `/original-ro` is independently
   read-only and `/restore` binds only `security-data-20261025` RW. Neither the
   Pod nor its process receives a writable whole-original-filesystem mount.
   There is no fsGroup, ownership init container or recursive chown. The reader
   runs the pinned cached Python image with networking denied and no SQL server.

   After recording exact new reader/policy UIDs:

   ```sh
   python3 -B "$H" restore --execute-new-sibling-restore \
     --baseline "$B" --baseline-sha256 "$BS" --cold "$C" --cold-sha256 "$CS" \
     --reader-run-id "$RID" --reader-pod-uid "$PUID" --reader-policy-uid "$NPUID" < "$KEY"
   ```

   This requires the sibling to be a real, empty directory, the RO and RW views
   to refer to the same inode, guest free space to exceed full file bytes plus
   256MiB, and at least8,192 free guest inodes. It fully reauthenticates the cold
   source before writing. Each file allocation retains256MiB. It verifies every
   restored byte/metadata entry and every pre-existing old entry afterward.
   A partial destination is retained and refuses reuse; no recursive cleanup,
   resume-overwrite or automatic retry exists.

4. Remove the restore reader/policy by recorded UIDs. Root changes only the DB
   volume claim to the original claim and subPath to
   `security-data-20261025/data-0` through the existing Flux owner, and sets DB1
   while keeping bot0. Keep image, native Secret, resources, command and all other
   Pod-template fields unchanged. The helper normalizes only those exact two
   mount fields when comparing its template HMAC. It does not emit/apply a chart
   patch. Both old current PVC and all archives remain retained.

5. Generate/apply the read-only after-reader plan on the same node, bind its UIDs,
   then compare live state. `$R/$RS` identify the successful restore receipt.

   ```sh
   python3 -B "$H" plan-after --baseline "$B" --baseline-sha256 "$BS" \
     --cold "$C" --cold-sha256 "$CS" --restored "$R" --restored-sha256 "$RS" < "$KEY"
   python3 -B "$H" after --baseline "$B" --baseline-sha256 "$BS" \
     --cold "$C" --cold-sha256 "$CS" --restored "$R" --restored-sha256 "$RS" \
     --reader-run-id "$RID" --reader-pod-uid "$PUID" --reader-policy-uid "$NPUID" < "$KEY"
   ```

6. Root performs the controlled DB restart. With the after reader still within
   its30-minute deadline (or a new exact plan/UID pair), run `restart` with all
   `after` arguments plus `--previous "$A" --previous-sha256 "$AS"`. It requires
   a different DB Pod UID created after the prior receipt, exact fresh SQL state,
   preserved native identities and old filesystem, and both original replica
   UIDs in the running engine's RW map. Only then may root restore the bot and
   perform its separate normal service acceptance. Delete only owned reader
   resources by UID; the helper intentionally has no deletion API.

## Bounds, residual assumptions and refusal behavior

All new outputs live under `FBASE/ruckus-ha-recovery-20261025`,0700, exclusive
filenames. HOME/TMPDIR/TEMP/TMP/XDG_CACHE_HOME are explicitly there before any
subprocess. The native ext4 mount must resolve to the existing144GiB backing file
and inode115123265474727363. Launch requires C≥15GiB and native/physical F≥16GiB;
archive writes retain15GiB. Archive/plain-file scope remains384MiB/4,096 entries;
the reader budget is500m CPU/512MiB, deadline1,800s. Cipher streaming is bounded
to600s and its own SSH/age children are closed on failure; no service or Pod is
killed. Failures, partial encrypted outputs and partial destination files remain.

Root must check these concrete assumptions before execution:

* The three-way timeline remains fresh: bot paused, SQL baseline stable, both
  writers paused, then current full cold. The tool guards Kubernetes writers;
  unknown external database clients cannot be proven absent from Pod metadata.
* Workernode2 remains the reviewed RWO attachment node. Mobility is not silently
  accepted by this finite plan; no forced scheduling or host operations occur.
* Both **existing** original replicas attach RW healthy before any restore. The
  helper pins their two names/UIDs, rejects any extra original-volume replica,
  and requires both in the engine RW map. It changes no replica count, Longhorn
  scheduling threshold, disk reservation or auto-balance setting. Longhorn may
  itself perform normal recovery work when attaching; this is not a proof of
  zero block allocation. The new sibling consumes blocks on each existing copy.
* Fresh original guest capacity must still satisfy actual full current bytes
  plus256MiB. The earlier786,726,912-byte observation is evidence, not a current
  free-space promise. Required node-level Longhorn disk headroom remains root's
  separate live gate; this helper does not create free space.
* The inspected historical root mtime and original file inventory still match.
  Unexpected changes fail closed. No old account/provider/credential file is
  exempted; only the newly owned sibling is excluded from the old-tree walk.
* App-visible full SQL equality is assessed while bot0. This does not claim that
  a restored running MySQL datadir remains byte-identical after startup. Exact
  full-file equality is proved before startup; the old root stays strict through
  after/restart. The fresh encrypted source and old current claim remain rollback
  material, not automatic rollback authorization.

Source qualification performed: AST parsing of both new files, AST parsing of
the exact adapted restore program, all single-occurrence restore preimage checks,
and exact inherited source hashes. No synthetic DB, new test suite, Kubernetes
operation, archive decryption, SQL observation or recovery command was run.


## October25 execution corrections

The original baseline63ced125… was captured with bot0/current DB1 and normal
authentication; it contains3,966 current rows across two tables. Both writers
then reached Flux0. Cold receipte105666f… fully authenticated the current
213,330,203-byte/298-entry claim and rechecked its complete contents.

Kubernetes omits empty NetworkPolicy rule slices and default-false Pod/PVC
booleans. The guards now normalize only those specific false/empty defaults;
automountServiceAccountToken/enableServiceLinks remain explicitly required.
The second RO attachment changed only the original root's mtime/ctime again;
its exact independent inventory is SHAe3d7f0b1369a7c91694ef0e8142509a1aa892d78be977e50415183acb571559b.
Every other root field and every original descendant remain exact. The cause
of the root timestamp change is not claimed. All failed receipts remain.

The revised protocol permits only the exact authenticated historical baseline
SHA63ced125ab7f5e61c88f9df3d1d2cbf3af8244c48a5a19a6d662640e9bc1f345
with its original two source hashes. That branch had no reader or historical
filesystem guard; its SQL/identity implementation remains unchanged. Other
proofs must match the new frozen protocol. Frozen old source was not edited.

The first complete restore matched every byte/owner/mtime/path but its final
check correctly rejected two missing SGID mode bits. No content overwrite or
restore replay is allowed. The separately source-pinned
[metadata completion](RUCKUS-HA-RESTORE-METADATA-COMPLETION.md) authenticates the
failed lineage, adds only FSETID to a new owned reader, and permits exactly two
fd-based directory chmods before a full comparison. Its result is explicitly
labelled as completion by that helper, not execution of the original restore.

Repeatable normal phases are available in the disabled-default Ansible
`playbooks/ruckus-ha-recovery.yml` role. It reads the fixed private HMAC key into
RAM in the wrapper; the key never enters Ansible variables/module arguments.
Prepare private0700 uid1000 FBASE/ruckus-ha-recovery-controller/{home,tmp,cache}
and use the existing short-F-RPC Ansible bootstrap. Check mode does no work.
Only public proof paths/SHA values and UID arguments are role parameters.
