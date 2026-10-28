# Preserve legacy Plex state before node-space recovery

**Completed October27,13:04UTC.** All 126,757 entries were independently restored
and verified from the complete authenticated NAS ciphertext. Exact retirement
through Ansible then removed **10,936,221,696 allocated node Linux bytes** from
only `/var/plex-stack/plex2/config` and `/var/plex-stack/plex2/config.old`.
Every outside-tree identity and retained parent owner/mode/inode survived.
The verified NAS ciphertext remained protected by deny-write/delete handles
throughout the operation. No image, model, volume or live application data prune.

Worker2 available filesystem bytes rose from 19,341,955,072 to 30,223,949,824
during retirement; concurrent filesystem writes make that change distinct from
the selected files/directories' measured allocation. Longhorn separately reports
35,546,726,400 bytes available and Schedulable=True. Its 25% minimum is unchanged.
All three nodes/disks are Ready/schedulable, all 58 claims Bound, all 44 Longhorn
volume UIDs preserved, and all attached engines have two RW replicas. Deployments,
daemonsets, HelmReleases and Kustomizations are Ready, including the separately
owned Ingenium deployment. This does not establish upgrade headroom or complete
the broader goal. [Sanitized receipt](../evidence/legacy-plex-preservation-20261027.json).

The 47,474,196-byte incremental recovery metadata packet contains 61 explicitly
selected, individually verified members, with no payload/archive ancestry copy.
Complete NAS readback and age authentication passed; SHA-256
`0ea7be14812c9a03f4631834fe91c4623901d1074173a13a888cc67fe4982a96`.
The original profile, sources, failures, receipts and required encrypted metadata
mirror remain. All restore and Ansible scratch is reconciled.

Owner: migration chat `01a12045-bf7e-73b3-8557-752d17c72ffd`.
This operation archives inactive legacy configuration, not running Plex data or
an expendable-cache assumption. No local original may be retired before complete
authenticated NAS backup and independent restoration of every archived entry.

The metadata-only worker2 survey found 65,880 regular file inodes and 60,877
directories beneath `/var/plex-stack`, with 10,682,728,448 allocated file bytes.
The largest file is 271,163,392 bytes. There are two symlink files, no unreadable
entries, and no mounts in the survey process's mount namespace. These observations
are not full inactivity, archive or retirement proof.

Exact candidate roots are `/var/plex-stack/plex2/config` and
`/var/plex-stack/plex2/config.old` on original worker2 ext4 UUID
`960bc2c7-2a7e-4bc2-b2c5-dbb6d71207f4`. All other node data, original Gluster/MySQL,
Docker state, images, volumes, models, current app state and rollback sources
remain outside this selection. Preserve original paths, contents, numeric owners,
modes, nanosecond timestamps, extended attributes and symlink targets in the
encrypted archive and its manifest. Refuse special files or external hard links.

Use exactly `node-cleanup-20261027/worker2-legacy-plex-preservation` under the
existing F-backed task root, ext4 UUID `3c792469-ea0e-4a2c-98e8-1185b141607b`.
Controller profile/receipts and frozen operator sources remain there or in the
existing `operator-control` directory. Regenerate metadata from the maintained
Ansible helper with the fixed host/filesystem/root guards and existing SSH key.
No new build, dependencies, image pull or local archive staging is required.

Archive transport is strict existing SSH -> pinned age -> the already approved
NAS recovery ciphertext store. The Windows operator uses the established NAS
access and the existing independently verified recovery-key backup. No secret
values may enter argv, environment, Git or logs. Privilege input uses the existing
non-echoing terminal/RAM/SSH stdin path. Complete process, mapped-file, descriptor,
unit and mount-namespace checks precede inventory and any later retirement.

Independent restoration uses the exact owned `restore-batch` directory, with
at most one 512 MiB file and a bounded batch of files present at once. Directory
structure and every file/symlink's bytes and metadata must be independently
verified. Set TMP/TEMP/TMPDIR inside that directory; hold the 15 GiB controller
space floor, with a 1 GiB memory/no-swap/one-CPU private-network job. All restore
scratch must be reconciled after its checks; failed qualification retains exact
scratch and diagnostics. Keep original source trees until all recovery checks
pass and a live read-only NAS handle denies write/delete access during retirement.
No driver, live volume, global floor, replica count or Ingenium change is allowed.

## Inventory and recovery execution

The full privileged inventory passed complete process, descriptor, mapping,
active-unit and mount-namespace checks before and after hashing. The exact roots
contain 65,880 files, 60,875 directories and two symlinks: 10,537,887,785 file
bytes and 10,682,728,448 allocated file bytes. No extended attributes were present.
The complete source was stable before and after streaming every file into age.
The encrypted NAS archive is 10,806,237,156 bytes, SHA-256
`69f759e6a7cf9311cb850ce31d71412433169f8ee9e144570f418c0ba7fd952d`.
Archive publication alone does not qualify local retirement.

The first independent restoration verified 56,883 files and both symlinks, then
stopped at the unchanged per-member free-space guard. It retained completed
directories until EOF. All original source trees survived. The failed operator,
restore receipt and source remain under the owned root. The retained generated
scratch was separately inventoried, fully hashed against the source profile,
checked for references and reconciled: 58,810 exact entries / 473,235,456
allocated controller Linux bytes removed. No node or Windows recovery follows
from that controller measurement.

The revised verifier closes completed subtrees during the depth-first stream,
removing verified files and empty completed directories in batches of at most
500 objects plus the active ancestor chain. It keeps complete path, numeric
owner, mode, nanosecond timestamp, extended-attribute, symlink, full-file-readback
and whole-age-stream authentication checks. The same 512 MiB per-file ceiling,
15 GiB free-space floor and private-network resource limits apply. It reads the
existing NAS ciphertext; it does not archive original trees again. The original
producer helper and failed receipts stay distinct from the resumed verifier.

`playbooks/legacy-plex-retirement.yml` uses a controller action plugin to pass the
bounded profile over the existing SSH stdin channel. No large profile or password
enters argv, environment, Git or node temporary files. The privilege password
comes from the existing non-echoing terminal and remains in RAM. The Windows NAS
guard must hold and prove deny-write/delete read handles for the complete archive
throughout retirement. The node helper repeats every original hash, identity,
retention and full-reference check before individually unlinking exact selected
entries. It preserves all outside-tree identities and parent owner/mode/inodes.
The retirement playbook passed syntax checking; execution is permitted only after
the completed all-entry restoration receipt exists.

Execution passed: `ok=2 changed=1 unreachable=0 failed=0`. The first controller
teardown closed its short-path descriptor before Python finalized an Ansible
listener. The node operation had already succeeded. Its original controller and
retained-IPC receipt survive. Complete process/mapping/mount checks and every
network namespace proved the one socket inactive; individual removal of it and
two empty directories recovered 8,192 allocated controller Linux bytes. The
maintained controller now finalizes its owned workers before closing the
descriptor. One real nonmutating Ansible worker check passed and left no scratch.
No retirement was replayed. No Windows disk recovery is claimed.
