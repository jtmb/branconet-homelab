# Existing-owner Longhorn upgrade preparation

Completed October 27, 19:02 UTC. The new opt-in Ansible preparation role rendered
a pinned candidate and passed server dry-run for **61 resources**, without forced
conflicts. Actual Ansible execution passed: two tasks OK, zero changed/failed.
All **51 existing object UIDs and configurations** matched before and after.
**No production upgrade, image pull, volume attachment or setting change occurred.**
[Exact source, candidate, server result and reconciliation evidence](../evidence/longhorn-upgrade-preparation-20261027.json).

The reviewed official manifest contains 62 resources, 51 already present and 11
new. Fifty existing upgrade resources are owned by server-side `kubectl:Apply`.
The namespace belongs to `before-first-apply`; it is a verified prerequisite and
is excluded from the apply candidate. The dry-run reused field manager `kubectl`,
with no Helm adoption or force-conflict flag. A first read omitted managed fields
and was not ownership proof; its original source/observation remain. The explicit
managed-field second read established ownership before preparation.

The candidate preserves all three current ConfigMap payloads. This includes the
actual storage class's **encryption, two replicas, `Retain`, existing native-key
references and V1 parameters**. Blindly applying the vendor defaults would not
preserve that configuration. Existing workload replica counts, resource settings,
strategies, scheduling, image-pull policies and custom environment additions are
retained; changed commands require explicit review rather than silent replacement.
Existing Service addresses, types and ports are preserved.

Every consumed Longhorn image reference, including driver environment inputs and
manager arguments, is digest-pinned to the reviewed official artifacts. Thirteen
candidate image references are consumed. The separately reviewed `longhorn-cli`
reference is not used by this manifest; its absence is recorded rather than
claiming it was deployed. The vendor's new global manager retains three replicas
and preferred anti-affinity. New resources include three CRDs and the dedicated
CSI service account/roles/bindings. Its official Secret role grants **GET**, with
no Secret writes or value export in this preparation.

The upstream driver passes the shared system-managed node selector to both CSI
controllers and the node plugin. A selector change must therefore account for
node-driver coverage; moving just the driver-deployer Pod does not establish CSI
controller placement. This candidate preserves existing selectors.
[Pinned upstream driver source](https://raw.githubusercontent.com/longhorn/longhorn-manager/v1.13.0/app/driver.go),
[official selector scope](https://longhorn.io/docs/1.13.0/advanced-resources/deploy/node-selector/).

## Capacity correction and next execution gates

The earlier five-image core profile is a lower envelope. The actual manager
DaemonSet also pre-pulls share-manager on every node. Including that container,
the V1-node image projection is **3,882,000,384 bytes** and still lacks
**196,805,633 master bytes** against the dated 18:47 observation and unchanged
floor. The broader 14-image profile still lacks 1,412,084,737 bytes. These reuse
the authenticated layers/old cache inventory; neither is fresh native unpacking
or proof that the full upgrade fits. No threshold or replica count was reduced.

The installed Snapshot/Backup schemas and a representative completed backup
were collected read-only for the next volume-backup implementation. The twelve
previously mapped native-backup gaps remain unresolved; schema discovery is not
a backup or restore. The earlier encrypted control-plane restore remains valid
dated evidence, separate from application-volume recovery.

The native controller filesystem reported 16,885,510,144 bytes available before
the later publisher cleanup. A full native unpack experiment must retain 15 GiB
and account for its compressed/unpacked peak; no such experiment was started.
The existing installed containerd/ctr tools were located read-only. No daemon,
image pull, filesystem growth, unmount, WSL shutdown or alternate output root
was introduced. A rotated-log survey found only 15,675,392 old allocated bytes;
no deletion eligibility was established and no log was removed.

## Output reconciliation

Reused the existing F-backed task root. Removed exactly **12,288 allocated Linux
bytes** of independently verified empty `longhorn-prepare-ansible-scratch`
directories; all candidate/input/source/failure files stayed unchanged. Late
framework module cleanup is unmeasured and not credited. Retain 27 current
source, owner-review, dry-run, diagnostic and cleanup evidence files, 2,917,121
logical bytes excluding their index. This includes the separate publisher
receipts below. No build/dependency/cache payload or restore tree was created.
Previous required recovery-tool and ownership/handle exceptions remain.

The two current Ingenium publisher stages passed the established source/blob,
receipt-chain, lock, Linux-reference, six native Windows exclusive-handle and
final-identity checks. Only their six temporary public binaries and two empty
tool directories were removed: **299,556,864 controller Linux bytes**.
Cumulative publisher recovery is **2,096,898,048 bytes** across fourteen stages.
All source exports, manifests, receipts, primary tools and the complete failed
run remain. Older retained copies were untouched. Exact paths:
[publisher ledger](../evidence/publisher-ingenium-current-release-20261027.json).
No Windows physical or node-space recovery is inferred from controller bytes.

Full goal remains active. Required execution work still includes exact current
application/detached-data backup coverage, fresh actual capacity/cache and
placement qualification, guarded manager/engine upgrade and recovery validation,
honest security exceptions, and final normal Seerr/YTPTube IAB/fleet acceptance.
