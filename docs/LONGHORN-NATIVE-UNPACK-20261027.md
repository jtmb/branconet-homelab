# Exact native controller unpack qualification

October 27: all thirteen consumed official Longhorn 1.13 candidate images were
pulled by immutable digest and unpacked with **the production node's exact
containerd 2.4.2 binaries** in an isolated controller instance. Every compressed
layer hash and complete committed overlay snapshot chain matched the earlier
fully authenticated public manifests. No containers started; no production
runtime, driver, setting, replica or application changed.
[Exact image/digest results, binary hashes and cleanup](../evidence/longhorn-native-controller-unpack-20261027.json).

This is an actual native unpack measurement on the existing controller ext4
filesystem. It is **not** a production-node cache refresh, placement proof,
supported upgrade execution or application recovery acceptance. The separately
reviewed unused `longhorn-cli` image was excluded from this consumed set.

The public binaries were exported read-only from the master with full source
hashes before and after, and complete destination hashes:

| Binary | Bytes | SHA256 |
| --- | ---: | --- |
| `containerd` | 40,710,352 | `4c8ea02ec7b01b1763910c82343e7b5fc39da4f356eb97645ec1baf3367a7fe2` |
| `ctr` | 23,597,216 | `bcf0357ed9f17b8851ccde2486321c8fa2d0bcfb0ea71c267da6a1155c7f4743` |

The actual binary emits configuration version 4; its own default configuration
is retained as source evidence. The private configuration redirected root,
state, sockets and temporary paths inside the declared F-backed scratch. CRI,
NRI, TCP, debug and metrics listeners were disabled. No container runtime was
registered with Kubernetes. Registry TLS verification stayed enabled; there
were no registry credentials, insecure flags or image publications.

The private systemd unit enforced 512 MiB resident memory, zero swap, one CPU
and 96 tasks. Sequential pulls used a single layer download at a time. Before
starting, both measured C: and destination capacity passed the 15 GiB floor
with an 8 GiB complete disposable peak budget. All thirteen unpacks consumed
**4,402,479,104 allocated Linux bytes including the temporary tool copies and
private runtime metadata**. This aggregate is not a per-node incremental budget.

The private daemon exited normally with code zero. After the unit ended, the
unchanged full unit/process/FD/map/mount guard and original-source hashes passed.
Removed the complete exact generated directory:

`/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025/platform-upstream-review-20261027/longhorn-capacity-budget/native-unpack-20261027/scratch`

Removed **4,402,479,104 allocated Linux bytes**; native available bytes afterward
were **44,795,273,216**. No Windows recovery is claimed. No tool, layer, snapshot,
dependency tree or private daemon remains. Only small unique source/default-
configuration, ownership, image logs, hash/chain results and removal receipts
remain under the same operation root: 22 files, 1,088,139 logical bytes excluding
their hash-bound final inventory. Regeneration uses the frozen maintained
`scripts/migration/measure-longhorn-native-unpack.py`, exact original node binary
hashes and original pinned public manifests. Do not reuse this temporary runtime
as a deployment source.

Full migration/security goal remains active. Required work includes remaining
data recovery bindings, fresh actual node capacity/cache and placement, guarded
manager/engine upgrade, honest security exceptions and final fleet/IAB acceptance.
