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
