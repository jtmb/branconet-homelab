# Longhorn production upgrade and final recovery checkpoint

The existing kubectl server-side owner accepted all 61 reviewed official pinned
v1.13.0 resources. Manager, driver deployer, global manager and UI rollouts passed.
All three node managers and all three new global managers are Ready. All original
claim/volume/replica/engine/NAS identities survived the manager rollout, with two
actual healthy RW replicas on every attached volume. Automatic engine upgrade
remains zero; storage availability remains 25%. No forced conflicts, Helm
adoption, data rebind or unsupported downgrade occurred.

The final encrypted checkpoint is
`control-plane-a5da7099e3b94e32a92a7ffe3a7e37f7`, 76,921,380 bytes,
SHA256 `004371fa6145a36c3c6041c57d600c8aa58102f273fb86ff0d3689d44d071555`.
The producer authenticated it and removed only its temporary server snapshot.
An independent full NAS readback and an actual private-network offline restore
passed. All 46 configuration/key files authenticated in memory. Revision
10,644,677, 2,672 keys and logical key-history hash 2,061,052,818 survived the
restore. No configuration/private keys were extracted to plaintext files, no
listener started and no production restoration was performed.

Native configuration-only SystemBackup `preupgrade-20261028-3266035b`, UID
`53024899-193b-406e-939a-aa288e851307`, reached Ready on the existing NAS target.
Two full NAS readbacks, ZIP CRC and all 20 YAML documents passed, including 44
complete volume/PV/PVC binding chains. Bundle SHA256 is
`d42bbb7603f2c390df514ce9a92c9fc7b60cdbd152e8438be44ab75dcfd61592`.
Its volume backup policy is disabled; original unused WordPress was not attached
or initialized. This bundle contains no Secret objects; the encrypted control-
plane checkpoint covers the native keys separately.

The maintained manager and engine maintenance roles/playbooks use the original
deployment owner. The manager's actual worker phases were prepare, apply and
observe. The prepared manifest was unchanged from the prior reviewed candidate,
SHA256 `4e9e85f106dc5cb11a2283956a2278a482b372e0061daccd6af0f0c9d64a8ac5`.
The existing 51 object identities/configurations, recovery proofs, fresh storage
headroom, strict server dry-run and all staged image results passed before apply.
The upgrade is forward-only; the old manifests are not a supported downgrade
after v1.13 schema migration. Qualified original recovery remains retained.

All 43 initialized encrypted V1 block-device engines are now upgraded:
28 attached and 15 retained detached. Original unused WordPress is excluded.
Each serial change tests the original UID/resourceVersion, changes only
`spec.image`, and waits for the original state and replica data-directory paths.
Attached volumes require two healthy actual RW replicas, actual new engine and
replica process images, the same application Pod/image/restart identities and
successful mounted-data read probes before and after. A submitted incomplete
operation is inspected, never blindly replayed or downgraded.
[Supported V1 procedure](https://longhorn.io/docs/1.13.0/deploy/upgrade/upgrade-engine/).

The final 01:56 UTC capture passes all 44 original volume UIDs, 58 Bound claims,
fourteen NAS bindings and 28 healthy attached volumes with two actual RW replicas.
All 43 initialized datasets retain Completed native backups; the backup target is
available. [Exact final acceptance](../evidence/longhorn-engine-upgrade-20261028.json).
The final owner/route inventory has 97 Running Pods, 67 distinct runtime image
IDs and no unavailable desired Deployment or DaemonSet. Private charts main,
validated and live Flux agree at `ba46a95c7eb6b5126aace677780878640240adab`.
BORTUS remains the deliberately suspended application release; the old migration
source also remains suspended. No hold was changed.

Two real interruptions are preserved. HTTP Echo has no `/bin/sh`; its first
read probe failed before any volume change. The bounded replacement verifies the
same container ID/Pod UID/native task PID and exact encrypted mount, reads only
the existing `/data` directory and writes nothing. Before/after checks passed.
Radarr's first atomic patch returned nonzero; its original image, complete spec,
data directories, healthy replicas and application remained unchanged. The
original error diagnostics were not retained, so the first failure's cause is
unestablished. A changed controller resourceVersion is consistent with it.
After explicit actual-state reconciliation, a separately named fresh atomic
intent passed. The launcher now refreshes resourceVersion after read probes and
retains nonzero patch diagnostics. Original failed sources/plans/intents/results
remain; no acceptance threshold or data check was relaxed.

Three original v1.12.1 instance managers still host active upgraded engines.
The vendor documents this V1 live-upgrade lifecycle: normal detach/reattach is
needed before automatic old-manager cleanup. They were not force-deleted.
The original unused WordPress volume also retains its v1.12.1 metadata reference,
and the old EngineImage remains deployed with refcount four. Thus engine upgrade
acceptance does **not** mean every old runtime image is retired. Controlled
workload maintenance and the final exact-image/security/browser gates remain.
[Vendor lifecycle](https://longhorn.io/docs/1.13.0/deploy/upgrade/instance-manager-pods-during-upgrade/).

Current official release API checks at 01:47 UTC returned Calico3.33.0,
Longhorn1.13.0, Kubernetes1.37.1, Flux2.10.0, cert-manager1.21.3, etcd3.7.3 and
FlareSolverr3.5.2 as latest stable releases. These checks fetched public metadata
only, not new images or feeds. Existing exact scans keep their original dated
database fingerprints; no new vulnerability scan or zero-day-clean claim is made.

Windows native default-trust HTTPS requests return200 for Seerr, YTPTube,
Vaultwarden and Homepage. BORTUS still presents a self-signed default certificate:
its chart binding/namespace certificate are prepared but its separate owner keeps
the application release suspended. The matching public root is confirmed in
CurrentUser/Root without a private key. No direct Ingress workaround was applied.
These are TLS/unauthenticated route observations; normal account/browser
acceptance remains open after the remaining implementation.

Disposable offline restore/producer scratch removed: **213,721,088 allocated
Linux bytes**, exact paths in
[the sanitized receipt](../evidence/longhorn-final-checkpoint-manager-20261028.json).
The staging scratch removal separately recovered 8,192 Linux bytes. All minimal
source, failure, cipher and qualification receipts remain. Windows recovery is
not inferred from these Linux measurements.

One exact protected exception remains under the existing F-backed task root:
`platform-upstream-review-20261027/final-control-plane-checkpoint-20261028/restore-ansible-scratch`
and its empty `local`/`remote` children, **12,288 allocated bytes**. Native Windows
exclusive opening returned access denied for this root-owned mode0700 subtree.
It was retained without permission changes or an alternative deletion attempt.
The original cleanup source/failure plan and preservation exception remain.
All other eligible scratch was removed after full Linux references and native
Windows exclusive handles passed. The 16,601,250-byte stock etcdutl and native
Longhorn recovery tools retain the concrete upgrade failure-recovery consumer;
reconcile them after that consumer closes.

The full tracked migration/security goal remains active.
