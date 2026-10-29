# Fixed xteve three-copy headroom operation

Source preparation only; no xteve storage mutation or runtime acceptance is claimed.
The completed qbit helper and evidence are immutable. This separate profile uses
only `H/qbit-three-copy-headroom/xteve-*` records, with a separate source-bound
ownership receipt. H remains the existing F-backed autonomous-hardening-20261028
root. No additional output root, generated cache, or temporary dependency is needed.

The fixed volume is `pvc-d40f1490-7254-4599-be82-2fad35abb88b`, UID
`bc2fc045-62a2-4266-a237-c9d37642acb2`. Retain worker1 replica r-27d468d0
(UID a5bfe7c3-9f81-471d-a4d0-7b378eae6f62); retire worker2 r-10300ab4 only
through native healthy surplus cleanup (UID c1f392d6-a55e-494b-8b8f-7b8b061d13d8).
The sole additional-copy destination is master. Read-only discovery observed engine
UID 2a23f930-0bf2-4221-87d7-7458c079f10e on worker2; qualification freezes its actual
node and image rather than assuming a control-plane engine.

Every phase requires the SHA-bound native authority and terminal successful apply
receipt, three completed native host records bound to that authority, live API and
all kubelets 1.37.2, unchanged containerd 2.4.2, original node UIDs and no concurrent
upgrade process. It binds the completed qbit receipt and frozen qbit source hash.
The unchanged current58 checkpoint verifier retains the full projected identity,
backup, offline-volume and ephemeral-source guards, normalizing only the approved
proxy image and this volume's two temporary spec fields. All other volume specs,
settings, Longhorn node specs, identities and original data remain protected.

Sequence: qualify, add-third, observe-third (one snapshot per invocation), reduce,
observe-two, restore. The default playbook phase is qualify. Count goes 2 to 3 to 2;
per-volume auto-balance goes ignored to best-effort to ignored. No global setting,
node flag, replica deletion, workload restart or raw directory deletion exists.
Fresh running RW replicas, instance managers, Ready times, anti-affinity, linked
clone/eviction/data-locality precedence and strict raw space ordering are checked.
Unknown health or ordering refuses reduction and leaves three copies intact.

Before copying, conservative max(2 GiB, logical size, actual size) must preserve
15 GiB usable and the hard 25% + 512 MiB filesystem floor, plus native scheduler
capacity. After the third copy exists, reduction requires master and worker1 to
actually exceed that floor by 2 GiB. Only worker2 may use projected recovery, capped
at the minimum original/current identity-bound directory allocated bytes. After
native removal, all three nodes must actually retain the full 2 GiB margin; the
original full volume spec must be restored before completion is recorded.
Allocated bytes are a projection until native cleanup and fresh filesystem readings
confirm recovery; no Windows free-space claim is made.

Use `scripts/migration/xteve-three-copy-headroom.py PHASE --authority ABSOLUTE_H_PATH
--authority-sha256 SHA --kubernetes-success ABSOLUTE_H_RESULT --kubernetes-success-sha256
SHA`. Feed one protected password line on standard input before any SSH child starts;
never put credentials in arguments, files, transcripts or receipts. The playbook
`playbooks/xteve-three-copy-headroom.yml` uses the existing launcher RAM-only
BRANCONET_MIGRATION_SUDO_PASSWORD carrier, no_log and command stdin. Its variables are
xteve_headroom_phase, xteve_headroom_authority, xteve_headroom_authority_sha256,
xteve_headroom_kubernetes_success and xteve_headroom_kubernetes_success_sha256.
Do not supply a password through extra-var files. Use the established controller
scratch and RAM launcher, not a new disk credential carrier.

Each mutation writes exclusive before/intent/after records immediately before the
UID/resourceVersion/full-spec tested patch. An existing intent is never replayed.
Read-only observation can qualify a completed action after a lost reply. Original
receipts, raw data, failure witnesses and all qbit records are excluded from cleanup.
These compact xteve records are required unique recovery evidence until this exact
operation completes and its accepted successor recovery generation is captured.
The source and existing pinned Longhorn 1.13 controller behavior are the regeneration
recipe; no generated executable or bulk artifact is created by source preparation.
