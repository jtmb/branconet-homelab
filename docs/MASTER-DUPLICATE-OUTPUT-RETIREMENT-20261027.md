# Four old master build duplicates retired

Completed October 27, 20:24 UTC through the new opt-in
`retired-master-duplicate-outputs.yml` Ansible playbook. Its inventory and
retirement phases passed: 11 tasks OK, three changed, zero failed. Removed
**233,078,784 allocated master Linux bytes**; cumulative qualified node cleanup
is **25,709,182,976 bytes**. [Exact paths, original identities, hashes and health](../evidence/master-duplicate-output-retirement-20261027.json).

Only these four files were removed below
`/home/james/.local/share/branconet-migration/root-custom-kubectl-build-20261012-f73dc0/kubectl-security-53c90b1e408a/`:

| Relative path | Allocated bytes |
| --- | ---: |
| `kubernetes/_output/local/go/bin/kubectl` | 61,968,384 |
| `kubernetes/_output/local/bin/linux/amd64/kubectl` | 61,968,384 |
| `go1.26.9.tar.gz` | 66,940,928 |
| `kubernetes-src.tar.gz` | 42,201,088 |

The original completed compile-only record pins all four hashes. That build
exited zero and injected no image or cluster change. Both compiled files have
the same original hash; read-only export and independent full readback preserved
that artifact at the existing F root's
`node-cleanup-20261027/master-generated-cleanup/rollback-custom-kubectl.elf`.
It remains unexecuted, mode0600, **61,968,384 allocated bytes**. Original file
metadata and pinned historical build commands remain in the preservation proof.

The two archive copies exactly match their original pins and retained primaries
in `root-custom-kubectl-build-20261012-b5d6d1/kubectl-security-a4cc69125f81`.
That complete failed build tree remains. All **77,887 unselected source, report,
failure and primary-archive entries** retained original identities and complete
hashes. Only direct parents' expected unlink timestamps were normalized.

Qualification checked the original filesystem UUID, canonical/non-Git paths,
owner/mode/single-link identity, full hashes, no extended attributes, 72-hour
retention, original locks and complete systemd/process/FD/map/mount references.
Deletion uses checked parent directory descriptors and exact inode identities.
The default operation inspects; explicit apply adds retirement after qualification.
The maintained launcher freezes source bindings and collects existing sudo input
through the protected terminal before Ansible workers, retaining it only in RAM.

Fresh health at 20:25 UTC: three Ready nodes, all **58 original claim UID/bindings**
and **44 volume UIDs** preserved, all Deployments/DaemonSets available and all
unsuspended Flux resources Ready. Master available/free bytes were
**27,600,588,800 / 32,917,225,472**. Storage minimum remains25%; automatic engine
upgrade remains zero. No runtime, image, volume or application data was pruned.

Reusing the earlier authenticated image/cache projection with the new disk
observation, the mandatory V1-node image profile clears the unchanged floor and
512MiB operating margin by **12,909,567 bytes**. The complete image candidate
still lacks **1,202,369,537 bytes** on master. Actual component placement, fresh
cache/unpack and recovery capacity remain separate gates; no upgrade was executed.

Controller reconciliation removed **20,480 allocated Linux bytes** in five empty
Ansible scratch directories after full reference/inode checks. Sixteen minimal
source/provenance/removal/health files and the original artifact total62,076,432
logical bytes, excluding their final index. No compiler/dependency/cache/raw
restore scratch remains from this operation. Older recorded ownership/retention
exceptions and required native recovery tools remain. No Windows disk recovery
is inferred. The full goal stays active with recovery, upgrade and final
security/fleet/Seerr/YTPTube IAB acceptance still required.
