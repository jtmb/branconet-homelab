# Retired native image filesystem caches

This fixed worker2 operation addresses capacity consumed by the unpacked
filesystem caches of six retired derivative images. Every image record, original
OCI blob, native lease/container and workload volume remains protected. It never
runs an image prune or deletes raw snapshot directories.

Use the opt-in `playbooks/retired-native-unpack-cache.yml` with
`retired_native_unpack_cache_apply=true` and an explicit phase:

- `inventory`: resolve all image graphs and exclude every native container,
  lease, foreign-namespace snapshot, current image layer and outside child.
- `physical`: independently map the immutable API identities to exact numeric
  backend directories using two stable read-only metadata reads, transaction
  checksums and native API comparison. No view or mount is created.
- `qualify`: authenticate every retained original OCI blob and uncompressed
  layer diffID; check hardlinks/xattrs and complete process/unit/FD/map/mount
  exclusion, including exact directory roots. Require no unselected orphan.
- `retire`: require the immutable qualification file through
  `retired_native_unpack_cache_qualification`, unchanged executing sources,
  physical identities and original blob identities. Repeat all reference
  checks, remove only those exact cache keys through the native API in child
  before parent order, observe actual directory reclamation, and fully hash
  the preserved original blobs again.

The controller also supports the corresponding direct Python entrypoints from
WSL, with the existing non-echoing TTY privilege primitive. It never puts the
password in argv, environment, files or receipts. Partial native submission is
journaled before and after each key. Any failed or uncertain result requires
inspection; do not replay the retirement or use raw filesystem deletion.

Regeneration uses the unchanged native `ctr snapshots unpack <root-digest>`
with the complete retained OCI graph, without a registry lookup or rebuild.
This is rollback cache regeneration, not a maintained deployment image source.
Current third-party workloads continue using their official upstream images.

Metadata stays under the same F-backed task root at
`platform-upstream-review-20261027/longhorn-application-batch-20261028/native-cache-qualification`.
There are no downloaded dependencies, image archives, extracted copies or
remote scratch directories. Keep unique execution/failure/source receipts and
all original images/content. Node filesystem recovery is separate from Windows
free space; no VHDX recovery is claimed.

The maintained `master_*`, `web_*`, `platform_cache.py` and `cache_outcome.py`
entrypoints use the same qualification and no-retry API protocol for their
explicitly named scopes. The corresponding opt-in Ansible playbooks are
`retired-{master,web,platform}-native-unpack-cache.yml`. They preserve each
cohort's original source, composition, receipts, original OCI graph and failures.
`cache_outcome.py` is observation only and never submits a removal.

`platform_cache.py --node workernode2 --family mysql qualify` considers only
the superseded official MySQL root `76f0358884cb92d9a086d24e5671c38048d3fef40f2588703d73eb55392d6b69`.
It is eligible only after no running/desired workload or native container/lease
uses it. The new official root and every other image remain protected. Explicit
retirement requires `retire --qualification <exact-receipt>`, unchanged fresh
source and the full original physical/reference/payload checks. The separate
`retired-mysql-cache-<node>-20261028` metadata cohort includes every prior platform,
web and original derivative journal in its permanently protected attempted keys.
Ansible uses `retired_platform_native_unpack_cache_family=mysql`; the default
remains platform. This does not authorize deleting image records or blobs.
