# Completed Seerr transfer retirement

The accepted Seerr deployment retained its six accounts, full history and real
restart checks. On October25 one redundant public transfer archive was removed
from masternode after its full controller copy and all13 referenced cached image
blobs were independently rehashed. No process, mount or loop referenced the file.

- Removed path: `/home/james/.local/share/branconet-migration/application-artifacts-20261023/seerr-security-20261023-ci40048938336.oci.tar`.
- Archive SHA256: `d3fa13eee47afd2a6c83e5fc49796a02143c441513c36fd06aa9b21dff64b174`.
- Logical bytes removed:319,832,064; allocated bytes recovered:319,836,160.
- Node free bytes:21,137,657,856 before,21,457,494,016 after.
- Retained controller archive: the same basename under `/home/brajam/.local/share/branconet-migration/application-artifacts-20261023/`.
- Retained image: `docker.io/library/seerr-security-20261023@sha256:7bf03e8c4433460c0d93f789da56db457e3484412c448997102885af185db93c`.

This is a completed deployment's duplicate transfer file. Runtime images,
volumes, encrypted data backups, source, lockfiles and compiler caches remain.
It is not retirement of the source artifact or a blanket cache-pruning rule.
Windows free-space recovery is zero for this remote-node operation.

The opt-in Ansible playbook is `playbooks/completed-seerr-transfer.yml` with
`completed_seerr_transfer_apply=true`. It verifies the controller before and
after, inventories the exact file, revalidates cached content and ownership,
checks active references, then unlinks only that filename. The original archive
can be restaged with `application_image_preload`, service`seerr`, generation
`ci40048938336`, after its normal capacity checks. No build is needed to restage.

Private receipt log: `FBASE/control-logs/completed-seerr-transfer-master-20261025-r2.log`.
`FBASE` is the mounted task root documented in [local build storage](LOCAL-BUILD-STORAGE.md).

## October25 additional finite completed transfers

Master YTPTube's completed duplicate was removed after the same controller and
active-reference checks: basename`ytptube-security-20261023-ci40052586445.oci.tar`,
SHA`c1d4130b64aa71629e5ead6ac0c37d17194dff2cf644ae5e4f8115f5559de5c3`,
461,156,352 logical/461,160,448 allocated bytes;34 cached blobs were rehashed.
Its full controller archive remains.

Workernode2's kubelet had already garbage-collected unused Seerr/YTPTube aliases.
The initial strict cached-alias attempts refused and removed nothing. The finite
role now permits an absent alias while retaining the full controller archive
before AND after, exact archive SHA/size/owner/mode/inode, no process/mount/loop
reference and single-file unlink checks. Existing aliases still require their
entire original content graph to pass hashes. No runtime image is recreated or
pruned to remove a transfer duplicate. Regeneration copies the exact retained
controller archive; source recipes/lockfiles and deployment images remain.

The explicit worker plan removed these basenames only under the same node
`application-artifacts-20261023` directory (allocated bytes):

| Exact basename | Allocated bytes |
| --- | ---: |
| seerr-security-20261023-ci40048938336.oci.tar |319836160|
| ytptube-security-20261023-ci40052586445.oci.tar |461160448|
| flaresolverr-security-20261023-ci40058492329.oci.tar |478855168|
| wordpress-security-20261023.oci.tar |278257664|
| phpmyadmin-security-20261023.oci.tar |198549504|
| tautulli-security-20261023-ci40068021890.oci.tar |108433408|
| vaultwarden-security-20261023-ci40060033423.oci.tar |92905472|
| coredns-security-20261023.oci.tar |70000640|
| nginx-security-20261023.oci.tar |65982464|

Total worker recovery2,073,980,928 allocated bytes. Exact hashes, before/after
free space and per-file checks are in retained private log
`FBASE/control-logs/retire-worker2-completed-transfers-20261025.log`, which passed
72 tasks/9 exact unlinks. This restored room for normal guarded Ruckus image
preload on all three nodes. No compiler cache, backup, volume, media, source,
lockfile or image was deleted. Windows recovery remains zero.


## Four accepted media services, October25 18:10 UTC

Radarr, Sonarr, Bazarr and Whoami passed their data/resource and controlled
restart checks before this finite cleanup. The same Ansible role removed exactly
these12 transfer files, retaining full SHA256-verified controller archives
before and after, source/locks and all runtime images/volumes. No prune occurred.

| Node | Exact removed basename | Allocated bytes |
| --- | --- | ---: |
| masternode | `radarr-security-20261023-r1.oci.tar` | 141434880 |
| workernode2 | `radarr-security-20261023-r1.oci.tar` | 141434880 |
| workernode1 | `radarr-security-20261023-r1.oci.tar` | 141430784 |
| masternode | `sonarr-security-20261023-r1.oci.tar` | 134139904 |
| workernode2 | `sonarr-security-20261023-r1.oci.tar` | 134139904 |
| workernode1 | `sonarr-security-20261023-r1.oci.tar` | 134139904 |
| masternode | `bazarr-security-20261023-r2.oci.tar` | 154902528 |
| workernode2 | `bazarr-security-20261023-r2.oci.tar` | 154902528 |
| workernode1 | `bazarr-security-20261023-r2.oci.tar` | 154902528 |
| masternode | `whoami-security-20261023-r1.oci.tar` | 10252288 |
| workernode2 | `whoami-security-20261023-r1.oci.tar` | 10252288 |
| workernode1 | `whoami-security-20261023-r1.oci.tar` | 10252288 |

All paths are under `/home/james/.local/share/branconet-migration/application-artifacts-20261023/`.
Total allocated bytes: 1322184704. These are remote Linux recoveries; Windows recovery is zero.
Exact per-file hashes, active-reference/content checks and live before/after free
bytes are retained in `FBASE/control-logs/retired-accepted-media-transfer-summary-20261025.json`
and the source operator log. Each node passed32 tasks/four changes/zero failures.
This partial recovery does not clear the recorded Longhorn disk pressure.
