# Two official images, native cache only

The default CLI mode is `observe`; the Ansible entrypoint is disabled by default.
No source/controller preparation runs pulls. The only allowed immutable images
are the reviewed MySQL root `a0225d1e…` and YTPTube root `a5b648c6…`; complete
digests are constants in `files/controller.py` and the receipts.

From the existing WSL controlling terminal, run:

```sh
python3 -B files/controller.py observe --service mysql --node all
python3 -B files/controller.py stage --service mysql --node all
python3 -B files/controller.py observe --service ytptube --node all
python3 -B files/controller.py stage --service ytptube --node all
```

An optional single node is `master`, `worker2` or `worker1`. Every stage still
qualifies all three nodes before the first pull. YTPTube staging additionally
requires fresh proof that MySQL is fully cached on all three nodes. Its budget
uses new actual free-byte/cache observations after MySQL, never ratio credits.

The source binds both exact r2 measurement receipts, the original measurement
source and approved registry metadata. It refreshes only public anonymous HTTPS
root/amd64 manifest/config metadata and verifies their immutable hashes. All 37
layer digest/size/diffID/chain records are tied to the measured crypto-verified
streams. Whole absent-cache upper bounds remain 1,344,196,430 bytes for MySQL and
1,879,576,367 bytes for YTPTube.

Existing compressed content is credited only after no-follow open, exact size,
regular/single-link/root ownership, full SHA-256 and stable before/after inode
checks. A corrupt present blob refuses the operation; it is never overwritten or
deleted. Unpacked credit requires committed native chainID and correct complete
parent linkage. Every other layer retains its full revised measured unpack upper.
The missing peak is those two missing sums plus a fixed 16 MiB metadata allowance.

Actual root/content/image/Longhorn paths must be the same original filesystem.
Both independent guards must pass: privileged free blocks retain the original
25% floor plus one byte plus 512 MiB plus the complete missing peak; nonprivileged
available bytes retain 15 GiB plus that peak. Original root UUIDs, pinned ctr 2.4.2
binary, kernel/runtime, Ready/pressure/cordon state and at least 1 GiB currently
available node memory are checked. Controller C:, F: and F-backed ext4 keep 15 GiB
plus the metadata allowance before each pull. No threshold or scheduling change.

Privilege input uses the existing echo-off TTY helper, stays in RAM and goes only
through SSH stdin to sudo. No passwords in environment/argv/receipts, no remote
script files, no temporary directories, archives, extracted trees or dependencies.
Public registry tokens stay only in RAM. Controller-generated metadata stays in
the existing F-backed `platform-upstream-review-20261027/upstream-security-prestage-20261028` leaf.

Pulls are serial, native `ctr images pull --local --platform linux/amd64
--snapshotter overlayfs --skip-metadata --label io.cri-containerd.image=managed
--max-concurrent-downloads 1 <canonical-repository@digest>` against the original
socket and `k8s.io` namespace. Normal TLS/public authentication remains enabled.
Only the two immutable canonical references can be created. No old tag is moved.
Node output is drained in bounded RAM chunks and only hashes/counts retained.

An exclusive per-service/per-node intent is saved before dispatch. An intent with
no complete accepted result permits observation only, never an automatic pull
replay. Completed nodes are freshly checked and not pulled again. Each result
verifies `ctr images check --quiet`, every blob and committed chain, unchanged
runtime/boot and preservation of every prior image/content/lease/snapshot record.
Actual post-pull allocation and both retained floors are recorded. Failed results
are preserved; no cache/image/filesystem pruning or workload restart is attempted.

The initial master MySQL pull is a preserved failed acceptance: the image,
all content/chains, runtime continuity, measured allocation and floors passed,
but the prior-record subset check failed. That source retained only aggregate
inventory hashes, so it cannot identify which historical record changed.
The original receipt and source are immutable and master must not be repulled.
Subsequent stages retain exact prior-record differences without changing the
acceptance predicate. Fresh complete-cache observations may prove current image
availability independently of that historical failed preservation check.

New native artifacts have the explicitly approved deployments as their remaining
runtime consumer. Their later retirement requires separate retention review.
Pods, configuration, Secrets, PVC/NAS data and BORTUS holds are outside this role.
Use `playbooks/official-vendor-preload.yml` with explicit enabled/mode/service/node
variables to run this identical controller; `raw` avoids remote module files.
