# Four static website runtime cycles

The fixed cohort is APLB, Lucinda Art Gallery, Minecraft **website**, and Santos
Web in `web-apps`. No game server is included. Each uses its original single
Longhorn claim and the same official Nginx digest. The supported normal
detach/reattach moves its upgraded engine off the old instance manager.

The opt-in Ansible entrypoint is
`k8s-rewrite/ansible-playbook/playbooks/longhorn-static-runtime.yml`, with
`longhorn_static_runtime_apply=true` and an explicit
`longhorn_static_runtime_phase=prepare|stop|observe|detached|resume|verify`.
Its maintained worker invokes the existing private Windows Git publisher;
it makes no direct cluster writes. Stop and restore change only each original
HelmRelease's `values.replicaCount`, through local validation, `validated` and
Flux. It never suspends controllers or changes application images, Pod templates,
resource limits, native Secret references or storage bindings.

Before submission, every existing file is read and SHA-256 hashed; sorted file
hashes and symlink targets are reduced to a manifest hash. Original Deployment,
release, claim, PV and volume UIDs/specs plus both replica data directories are
bound into the plan. The four baseline manifests contain 172, 198, 61 and 49
lines respectively. After normal detach and restore, the same identities,
content hashes and runtime images must pass, along with two actual healthy RW
replicas and a new ready Pod with zero restarts on the pinned v1.13.0 instance
manager. Failure is retained rather than marked successful or blindly retried.

The original F-backed task root and physical filesystem UUID remain authoritative.
This cohort's metadata is under
`platform-upstream-review-20261027/longhorn-static-runtime-20261028`.
Its exclusive ownership/peak/regeneration record preceded the plan and stop.
The two publisher exports are reconciled only after terminal validation and
actual Flux consumption; source Git blobs, lockfiles, reports and all failed
evidence remain. No new output root, image build, data copy or NAS change occurs.

All four runtime cycles passed. Stop commit
`936e2aa590c29251bf5a7a6c8d8dec83728bb60c` and restore commit
`70fcccc5c452222bb64f203dc5a225c94bdf0bc5` both passed the unchanged local
publisher and were consumed by Flux. All original file manifest hashes, images,
templates, claim/PV/volume identities and replica directories survived. Each
new Pod has zero restarts and two actual healthy RW replicas on the new
instance manager. All58claims remain Bound, all14NASbindings survive, all three
nodes are Ready and no desired Deployment/DaemonSet is unavailable.
[Exact acceptance and source receipts](../evidence/longhorn-static-runtime-20261028.json).

The first normal Windows route check failed with resolver error11002; its
original source/failure are preserved. Follow-up DNS reads identified a missing
`mc.branconet.lan` CNAME in Pi-hole, while its ingress already existed. The
opt-in `pihole-website-alias.yml` Ansible entrypoint now carries the exact native
CLI operation. It appended only `mc.branconet.lan,branconet.lan`, retaining every
previous alias and the same ready DNS Pod/container/image/restart identity.
The native setting survives readback, and direct DNS returns the original three
node addresses. No Windows DNS settings, native Secret or chart template changed.
This uses [Pi-hole's documented CNAME configuration](https://docs.pi-hole.net/ftldns/configfile/#cnamerecords).
All four LAN HTTPS routes then returned200 with normal Windows certificate
trust and no TLS override. HTTP/TLS acceptance is separate from the final IAB gate.

Cleanup removed **355,721,216 allocated Linux bytes /1,612paths** from the two
consumed terminal publisher exports. All1,612exclusive Windows handles and full
Linux reference checks passed; ten protected report/lock/publication files and
original Git blobs/tools remain unchanged. The exact per-path ledger is
`longhorn-runtime-retirement-20261028/publisher-cleanup-d1be6b9e1e35c57c/receipt.json`
under the existing platform review root. Retain16unique current metadata/source/
failure records,435,939logical bytes excluding the inventory index; no build,
dependency cache or recovered payload was generated. Required tracked charts
source and operational recovery tools still serve the remaining stateful cycles.
All earlier failed-safety-check/rollback exceptions remain protected. Independently
observed Windows free space is C:58,135,957,504 and F:193,663,725,568bytes; no
Windows/VHDX recovery is inferred from Linux deletion.

Twenty-three live engines still use the three old instance managers. Remaining
runtime cycles, final exact-image/security reconciliation, normal Seerr/YTPTube
IAB acceptance and final cleanup remain open. BORTUS's held release stays with
its separate owner. The full migration/security goal remains active.
