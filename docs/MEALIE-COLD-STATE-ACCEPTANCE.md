# Mealie original-state preservation

The original baseline and complete cold archive passed, and the October 25
read-only after observation passed for the patched RC1.1 image. Controlled
restart, independent restore and personal-login acceptance remain separate.
The generic cold helper retains all existing application guards, including both
Ruckus writers and the 15 GiB Windows C and projected destination floors.

Metadata-only discovery on October 25 found:

| Resource | Exact identity |
|---|---|
| Deployment `mealie/mealie` | `f0dddcf0-0d07-4b56-a3ec-0cd59d484b93` |
| HelmRelease `flux-system/mealie` | `2d878107-ff9f-46f6-9260-2e8f3a94e38c` |
| PVC `mealie/mealie-data-0` | `d015a16d-5098-4253-ade1-72d80af87f18` |
| PV `pvc-d015a16d-5098-4253-ade1-72d80af87f18` | metadata UID `402d45ec-840b-4a57-9c7e-0cede840539d` |
| Node `workernode1` | `e8d4555f-7cea-445f-b84f-6416964045a9` |
| Native Secret `mealie/mealie-runtime` | `8142b20f-d201-44ff-97b8-f72c93d15557` |
| Service `mealie/mealie` | `33270f41-30e7-4338-a0b6-4a663ae797e7` |

The original image is
`ghcr.io/mealie-recipes/mealie:v1.0.0-RC1.1@sha256:6df1e795f17af43f082146e471113315487b5f0882f2ee7553d469034d929af1`.
The Longhorn RWO ext4 claim is mounted at `/app/data`. Its root is
`1000:65534`, mode `1750`; the discovered descendants are `0:999`, mode `755`.
A Strict `1000:1000` reader can traverse/read this tree without changing any
owner, group or mode. A root reader with all capabilities dropped cannot
traverse that root through DAC. The discovery counted 247 entries and 7,695,731
regular-file bytes; this is sizing metadata, not a state baseline.

## Cold capture

Use the existing playbook
`k8s-rewrite/ansible-playbook/playbooks/cold-application-state-backup.yml`
with these explicit role variables, after the coordinating operator has
reconciled the original Mealie HelmRelease to zero and confirmed no writers:

```yaml
cold_application_state_apply: true
cold_application_state_app: mealie
cold_application_state_node: workernode1
cold_application_state_reader_uid: 1000
cold_application_state_reader_gid: 1000
cold_application_state_output_dir: /home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025/mealie-preservation
```

The helper requires the original image and deployment/release/PVC identities,
the exact PV UID/claim binding/CSI handle, the original node UID, Strict group
support, zero desired/current/Ready writers and no other active PVC consumer.
It mounts the entire claim read-only with no exclusions. The encrypted archive
contains every file, directory, symlink and SQLite sidecar and is fully
authenticated before success. No Secret is mounted in the reader. This helper
never scales or resumes a writer. A fully verified archive is not yet a tested
restore.

## Separate acceptance observer

`scripts/migration/qualify-mealie.py` runs on the WSL controller using the
existing strict SSH identity. It has four explicit modes and no mutation mode:

1. `baseline --image ORIGINAL --runtime sha256:6df1... --receipt BASELINE`:
   observe the original Ready writer before quiescence. Use the full digest
   above, never the abbreviated example. Record native resource/spec/Secret
   HMACs, all-table/file observations and public API routes/version/root page.
2. `cold --cold-receipt RECEIPT --cold-receipt-sha256 SHA256 --receipt COLD`:
   verify the completed generic archive and its exact receipt hash, read every
   encrypted byte, then decrypt only `mealie.db` and its `-wal`/`-shm` sidecars
   to a private verified `/dev/shm` tmpfs directory. Read the SQLite snapshot,
   authenticate the second decrypt stream too, and remove this temporary copy.
   Complete this before starting the replacement writer. This mode has no
   cluster access and does not establish a current zero-writer fence itself.
3. `after --image CANDIDATE@sha256:DIGEST --runtime sha256:ACTUAL_RUNTIME
   --baseline BASELINE --cold COLD --receipt AFTER`: after the separately
   reviewed rollout, compare to the original resource/API baseline and complete
   cold state. The image and observed runtime must match both supplied pins.
4. `restart` takes the same arguments plus `--previous-after AFTER`. The
   coordinating operator performs the restart separately. Require a changed
   Pod UID or increased container restart count, unchanged candidate image and
   runtime, and repeat every preservation check against both original cold
   state and the prior successful after observation.

For every invocation, feed the same existing 32-byte key encoded as 64 hex
characters on **stdin**, never an argument or environment variable. Keep that
key outside Git under the controller's existing private-secret handling. The
helper does not generate, persist or print it. Receipt paths must be new files
under an existing owner-only directory outside Git; receipts are created 0600.
Keep all generated receipts in the task-owned F-backed directory above. Do not
copy real databases or plaintext manifests into this repository. All receipts
are HMAC-authenticated, source-bound, contain no raw Secret/SQL/API/file values,
and preserve failures instead of overwriting previous evidence.

The controller sends the key over stdin through SSH and `kubectl exec`. Only
resource identities, structural counts and HMACs leave node/container memory.
Execution reads the referenced Native Secret in node RAM to compare its complete
`data`, type and immutable flag; no Secret values are printed or exported. The
observer requires the same deployment, HelmRelease, PVC/PV, Service and Secret
UIDs. Deployment/HelmRelease specs must match
apart from the explicit image replacement and Deployment restart timestamp;
pull policy remains compared. PVC/PV/Service specs are compared in full. The
single Ready Pod must belong to the pinned Deployment and be the only active
consumer of the claim. Resource checks run before and after observation.

The original baseline and cold reader remain bound to workernode1 UID
`e8d4555f-7cea-445f-b84f-6416964045a9`. Longhorn permits the replacement writer to
move nodes without replacing that PVC/PV. After/restart phases therefore allow
only the three discovered name/UID pairs:

| Node | Exact UID |
|---|---|
| masternode | `f2df6169-4592-4544-b62c-74d89f598648` |
| workernode1 | `e8d4555f-7cea-445f-b84f-6416964045a9` |
| workernode2 | `eda66e65-f388-4b97-b64f-a709cda81894` |

The original node identity is still checked; the actual writer node must retain
its listed UID, be Ready, have no pressure condition and remain unchanged during
one observation. Its name/UID is recorded separately in the writer receipt.
This does not modify placement or force a Pod back to its old node.

The only accepted historical observer revision for original baseline/cold
receipts is `07c6af0a223a994dc49abe26fbcfa1f638dc35094e18922e3fbc743efb9fc9a7`;
both archive helper hashes must remain exact. The placement change preserved
`STATE_SOURCE` and all SQL/file/pod/archive/comparison function source bytes.
Only the controller's source allowance and remote placement fence changed.
Current-source after receipts remain required for subsequent restart comparison.

SQLite verification includes integrity and foreign-key checks, full schema,
every table, every column, every row (including duplicate multiplicity), typed
NULL/text/integer/real/blob values and both schema-version pragmas. Required
`users`, `groups` and `recipes` counts are recorded; credential hashes, tokens,
membership and relationship values are HMAC-covered without printing them.
There is no table omission or data migration allowance. Physical B-tree root
pages are excluded from schema comparison. WAL-aware read transactions use
`mode=ro` and `query_only`, never `immutable=1`, checkpoints, VACUUM or journal
changes. SQLite may coordinate read locks/SHM; zero SHM metadata effects are not
claimed. All original physical DB/journal bytes remain in the cold archive.

Every non-database file is compared by complete bytes, owner, group, mode and
kind; names and symlink targets are HMAC-protected. The main database owner/mode
is compared separately, while its logical contents use the all-table proof.
All database/sidecar file fingerprints are retained in the private receipt.
Inodes, timestamps and SQLite page/journal byte layout may naturally change and
are not treated as application data. No log/content path is silently excluded.
The sole append allowance is `/app/data/mealie.log`: the exact old
`mealie/core/root_logger.py` SHA256
`0af03695170c7ae0d03083bbbfd81456bdd63a8402057fc0f822c9e0630831ed`
constructs `logging.FileHandler(LOGGER_FILE)` with its default append mode.
The observer verifies that logger source hash in both old and candidate Pods.
It requires the same regular-file owner/group/mode, every original byte as an
exact HMAC-verified prefix, and at most 16 MiB appended since the cold capture.
The restart check also proves every byte observed in the previous after receipt
remains a prefix. Complete observed log hashes remain in all-file receipts;
the log is not removed from the inventory or cold archive. The implementation
defines no rotating handler or rotated pathname. Therefore truncation, rotation,
replacement by a symlink or an unknown new rotated file fails; original bytes
remain recoverable from the authenticated cold archive, but that is not a claim
of unchanged live log preservation. Concurrent changes to any other non-database
file refuse observation. Full-file backup preservation and live byte immutability
are distinct claims.

Public HTTP checks use only the existing ClusterIP:9000 with no proxy or
redirects: `/`, `/api/app/about` and `/openapi.json`. Compare the original
application version, complete route/method set and root-page bytes. Full
response bodies are HMAC-recorded, not emitted. Old source commit
`3f49e80b9a91e9ec4ebefa36246da5674daca62b` defines these in
`mealie/routes/__init__.py`, `routes/app/app_about.py` and `mealie/app.py`;
`core/config.py` and `core/settings/db_providers.py` define `/app/data/mealie.db`.
The observer checks the existing dotenv/environment-selected SQLite production
path without importing or starting the application. Postgres, another path,
disabled/different OpenAPI routing or a different resource graph fails closed.

No personal login is invented. User-password authentication, browser behavior,
external routing/TLS and an independent restore still require the operator's
separate evidence. The helper never sends credentials to login, creates a user,
changes a password, submits a recipe, writes an API resource or restarts/scales
anything. Public GETs may generate normal application access logs. Passing this
observer is a preservation checkpoint, not automatic whole-application adoption.

Source qualification used one disposable synthetic SQLite fixture on tmpfs.
It detected credential changes, cross-group reassignment, duplicate removal,
schema changes and FK corruption. Focused file checks accepted a bounded log
append and rejected missing prefix proof, unrelated file mutation, mode drift,
truncation, changed prefixes, oversized appends and symlinks. Restart comparison
required an actual Pod/restart-count change. Embedded remote Python and role YAML
parsed successfully. These checks used no production data and ran no baseline,
archive capture, build, rollout or restart.

## October 25 after checkpoint

The one authorized after observation passed on workernode2 for
`docker.io/library/mealie-security-20261023@sha256:a3fc64d6777e22de915a97d3dbb77e1edc5d5998be683b4a1bed8968a26b2bb9`.
It reused the original private `baseline-r3.json` and `cold.json` under
`FBASE/acceptance-mealie-20261025`, with their existing HMAC key supplied only
on stdin. All original SQLite, full-file/log-prefix, native Secret/PVC/spec and
API comparisons passed unchanged.

The new private receipt is
`FBASE/acceptance-mealie-20261025/after-placement-r1.json`, SHA256
`6b8bee4dc1ed839752aa90596bf526b496f0892cfff66ee21b2d1c5acc8d4f0a`.
Observer SHA256 is
`b2ac7534411c14bb9417d317e6ebc1e96bc0ce366c1ea0ecb3c2966370d6c305`.
Here `FBASE` is the existing task-owned mounted filesystem root
`/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025`.
No scaling, restart, state edit, image change or Git operation was performed by
the observer worker. The coordinating operator owns controlled restart and the
next `restart --previous-after` observation.

## October 25 controlled restart accepted

Root published the declared restart annotation through charts commit
`f52c01b678fcd1811ef9ad5a1503abc56b7c6680` and the existing local validator/Flux.
The new `FBASE/acceptance-mealie-20261025/restart.json` passed with the same
observer, original HMAC key and baseline/cold proofs; SHA256
`603eeec945b94246cabde11fabb87057e317c24f8d48c0eddf67814771133ae6`.
All53 SQLite tables/847 rows,3 users,1 group,33 recipes,247 filesystem entries,
234 API routes, native credentials/claims and three HTTP surfaces remained
consistent. Scheduling from workernode1 to workernode2 is allowed only among the
three pinned Node UIDs; PVC/PV and data checks remain exact. This is runtime
preservation and restart evidence, not a personal-login or browser claim.
