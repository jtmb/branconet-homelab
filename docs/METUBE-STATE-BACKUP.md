# MeTube cold state backup and legacy reobservation

Current checkpoints and unresolved gates are summarized in [MIGRATION_STATUS.md](../MIGRATION_STATUS.md). This document retains operational contracts and dated attempt history.

Both operations actually completed on October24. The Flux owner stopped the old
writer; this helper archived/authenticated all seven original files (618,241,982
bytes), then reobserved them after replacement/restart with zero differences.
Both owned temporary Pods were deleted normally. NAS media was never mounted or
walked by the helper. The separate BORTUS recovery
framework and its frozen helpers are not imported or changed.

The entry point is `k8s-rewrite/ansible-playbook/playbooks/metube-state-backup.yml`,
role `metube_state_backup`, with the dedicated
`scripts/migration/run-metube-state-backup.py` launcher. It uses the existing
master operator kubeconfig through strict WSL SSH, without sudo or application
credentials. Native Kubernetes Secrets remain untouched.

## Fixed original identities and scope

Read-only discovery on 2026-10-23 found Deployment `plex/ytdl` UID
`b6f10b2b-3350-49f5-9b1c-182f80db4af5` and these original Bound PVCs:

| Claim | PVC UID | Helper access |
|---|---|---|
| ytdl-data-0 | 5411bcf9-4331-43bd-9a8d-7d0fbf0a9324 | Full /state, read-only |
| ytdl-data-1 | dcc218b0-929e-4892-bd72-1a226157af5d | Full /tmp_dir, read-only |
| ytdl-data-2 | 7c3e8710-a79d-408f-b8fb-df3b87bdb0de | UID/status metadata only; never mounted or walked |

The helper image is the original immutable MeTube image
`ghcr.io/alexta69/metube@sha256:afd3fa2b229e3e6d4c8750618fe148af33a1f70b32af4441ecbd2d08f29d8221`.
Read-only execution confirmed Python 3.13.12, `/usr/bin/tar` and stdlib `tarfile`.
The current seven regular files total 618,241,982 bytes, with UID/GID 1000;
those live sizes are discovery metadata, not a cold backup fingerprint.

The temporary Pod runs only sleeping Python and the injected byte reader, as
UID/GID 1000 with all capabilities dropped, read-only root filesystem, no service
account token, 500m CPU and 256 MiB memory limits, and a 30-minute deadline.
Both claim references and mounts are read-only, with no subPath. No fsGroup or
recursive ownership change occurs. No NAS claim, Secret, hostPath, app environment,
application entrypoint, updater or application process is mounted or started.

## Cold backup phase

First qualify the replacement image. Root then stops the old writer through
its existing Flux owner and waits for the observed Deployment generation,
replica/Ready/available counts and all old claim-using Pods to reach zero.
The helper checks that condition before and after capture; it does not scale
anything or alter GitOps. The target worker must be Ready, uncordoned and free
of pressure. The original Deployment and all three PVC UIDs must still match.

Use a protected nonsecret settings file, for example:

```json
{"metube_state_apply":true,"metube_state_phase":"backup","metube_state_output_dir":"/home/brajam/.local/share/branconet-migration/metube-state-20261023","metube_state_backup_node":"workernode2"}
```

From a freshly staged native Linux source tree, invoke the isolated operator
Python with `scripts/migration/run-metube-state-backup.py --settings-file
/protected/settings.json`. No password or other stdin data is needed.
`--syntax-check` creates no Pod and reads no application files. Direct Ansible
check mode likewise skips the operation.

Every original regular file is SHA-256 hashed in one-MiB chunks. Directories,
permissions, ownership and symlink targets are recorded; symlinks are never
followed. Hardlinks and special files refuse rather than being silently omitted.
Limits are 4 GiB file data, 4096 entries and eight MiB manifest metadata. The
complete two-claim tar streams directly from the reader into the existing
SHA-bound age v1.3.2 executable on native WSL, using the existing operator
`id_ed25519.pub` recipient. It is never buffered as one large byte string or
written as plaintext on the controller. The existing `id_ed25519` identity
is used for authenticated stream decryption; no keys are generated or rotated.

Verification traverses the entire decrypted tar in chunks without extraction,
checks every file against the archived manifest SHA/size and metadata, checks
path/type membership, and drains through EOF so age authenticates the final
chunk. The source detects file or tree changes during streaming. The receipt
records ciphertext hash/size, manifest hash, all three claim UIDs and a protected
`cold-legacy-metadata.json` fingerprint baseline compatible with
[YTPTube acceptance](YTPTUBE-ACCEPTANCE.md#cold-preservation-metadata).
File contents, cookies, URLs and credentials are not written into the receipt,
metadata baseline, Git, argv or logs; filenames/hashes stay in private evidence.

Only after all checks pass does cleanup send a normal Pod deletion with the
exact newly created UID as a server-side precondition, then wait for deletion.
No force deletion, PVC deletion or legacy file removal exists. A failure retains
the temporary read-only Pod and all ciphertext/metadata for root review.

## Reobserve after the replacement test and restart

The new YTPTube writer uses the same Deployment and claims. Its config subPath
hides sibling MeTube files, so a separate read-only helper mounts both full claims
on that writer's node. It verifies a single Ready writer owned by the original
Deployment and the exact operator-supplied accepted image identity. It never
reads the authentication Secret or changes the writer.

The cold baseline must contain none of the three new paths. The later reader
excludes only these exact paths and their descendants:

- `data-0/ytptube-config`
- `data-1/ytptube-deno`
- `data-1/ytptube-cache`

No other path or old file is excluded. Every old full-file SHA, size, owner,
mode, directory and symlink target must match; unexpected legacy additions also
refuse. Directory timestamps are allowed to change when the new directories
are created. All original PVC UIDs are rechecked before and after observation.

A reobservation settings file adds the independently checked cold backup receipt
hash and the accepted immutable writer image:

```json
{"metube_state_apply":true,"metube_state_phase":"reobserve","metube_state_output_dir":"/home/brajam/.local/share/branconet-migration/metube-state-20261023","metube_state_baseline_receipt":"/protected/cold-run/receipt.json","metube_state_baseline_sha256":"<independently-checked-64-hex-sha256>","metube_state_expected_writer_image":"<accepted-reference@sha256:digest>"}
```

The helper independently hashes and fully authenticates the retained cold archive
again, compares its manifest with the current full-claim fingerprint, and records
`legacy_reobserved:true` only on equality. It retains protected observed metadata
and mismatch path metadata on failure, without printing file contents. The
YTPTube application acceptance helper's separate `legacy_reobserved:false`
field remains accurate; this receipt is the independent observation it requires.
Run a fresh reobservation after the bounded download and after the restart.

A completed archive/fingerprint receipt is preservation evidence, not proof of
an independent restore, a compatible queue import, playable media, working
provider access or complete migration acceptance. Keep the old files, original
NAS downloads, cold ciphertext and operator key available for rollback.