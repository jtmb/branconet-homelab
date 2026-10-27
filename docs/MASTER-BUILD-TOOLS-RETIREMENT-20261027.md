# Original master builder tools retired

Completed October27. Removed only the six sealed public BuildKit binaries and
two empty `bin` directories under master:

- `/home/james/.local/share/branconet-migration/seerr-build-20261023/bin`
- `/home/james/.local/share/branconet-migration/ytptube-build-20261023/bin`

Recovered **258,555,904 allocated node Linux bytes**. Total qualified node
cleanup is now **24,914,153,472 bytes** across seven operations. Every individual
path, inode, hash and allocated count is in the
[exact ledger](../evidence/master-build-tools-retirement-20261027.json).

Original setup seals, all selected hashes, owner/mode/single-link/filesystem,
72-hour retention, original locks and complete unit/process/FD/map/mount checks
passed. Every unselected context, lock, log, state, source, seal and failure file
retained its identity/hash. The controller's three primary binaries still match
their pins and provide regeneration in a fresh owned stage. Its source receipt
records BuildKit0.34.1's historical archive hash; that archive is absent there,
so no current archive verification is claimed. No old build was replayed.

The inspect-by-default `retired-master-build-tools.yml` playbook passed syntax,
live inventory and opt-in retirement. Its operator uses the existing protected
TTY input and RAM/SSH authentication. The helper source and primary hashes are
verified before invocation. No credential file, environment value or argument
was created. No image, volume, model or application data was removed.

Afterward: **3 Ready nodes**, all **58 claim UIDs/bindings** and **44 Longhorn
volume UIDs** preserved; Deployments/DaemonSets available, unsuspended Flux Ready,
attached volumes healthy. Master native available/free bytes were respectively
**26,827,407,360 / 32,144,044,032** at the post-check. Longhorn reported
32,086,425,600 available. Reusing the earlier image projection leaves
**432,645,121 core-image bytes** or **1,936,372,737 complete-candidate bytes**
missing. This remains a dated projection, not native unpack or fresh cache proof.
The 25% floor, automatic engine-upgrade limit zero and owner hold remain.

Controller reconciliation removed **36,864 allocated Linux bytes** in owned
empty scratch directories. Ansible's late interpreter cleanup removed its
temporary module packaging after the initial operator receipt; those bytes were
not measured or credited. Four remaining empty directories passed independent
reference/inode checks before removal. The initial bookkeeping failures and
their sources remain labeled; no node retirement was repeated. The checkpoint
retains24 minimal source/provenance/footprint/failure/removal/health files,
196,046 logical bytes excluding its final index, inside the existing F root.
No disposable build/dependency/cache/payload tree remains from this feature.
No Windows physical disk recovery or whole-goal completion is claimed.
