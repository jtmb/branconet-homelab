# Unpackerr 1.0 and delivery acceptance

Official Unpackerr1.0.0 is deployed and accepted through the existing private
local validator → validated → Flux pipeline. Production and a distinct controlled
restart preserve the original configuration, native credential and both storage
bindings. Main/validated/live is `5b894f2491d0ca080d8e63cdb2a73050eb551878`.
The full cluster goal remains active; node capacity cleanup is now in progress.

## Actual release and data proof

Image:
`ghcr.io/unpackerr/unpackerr:1.0.0@sha256:21c6bfa4f4c86ab2dd0232da0dfb3ed4c5d929e42e09894e7b4d2154d0c144f6`.
The reviewed amd64 child is
`sha256:4a3bba3267fd83da7ff8871c73feddcc6ec00ee4de303043ed63c2d38f8b0a4c`.
Both runtime imageIDs match the reviewed index. The official binary extracted
from its hash-verified registry layer is23,220,384bytes, SHA256
`3c46b9afff7885f47bcb5d3c411f4d7d13e5695aaf61c221ad1e8670ce53fbdf`,
version1.0.0/Go1.27.1. No derivative build or new publication route was used.

The complete original17,148-byte config was quiesced through Flux and cold
archived. Its20,692-byte ciphertext, SHA256
`456cefa62e7203da7b966b4ab19b18980b4a3414ae68341ccdca41e2e1b36834`,
passed full authentication and NAS read-back before adoption. The exact temporary
reader was UID-deleted. Original Longhorn claim `unpackerr-data-1` and SMB claim
`unpackerr-data-0`, their PV identities/specifications, Deployment/HelmRelease
UIDs and native Secret UID/resourceVersion/content fingerprints all match the
baseline after adoption and restart. The full original file bytes/owner/group/
mode match. No NAS corpus was walked or copied, and no native Secret was changed.

Baseline Pod:`de1a79fc-6e48-4a1a-a84a-820b2b5f3f2f`;
adoption Pod:`a3a0f36d-1220-4173-9dcb-3ef73f3adf3c`;
restart Pod:`45f8cffb-bdb0-420b-a475-851283c7e20e`.
Both new observations report Sonarr/Radarr queue retrieval with no observed
authentication/error/fatal lines. Their normalized Deployment specifications
match the baseline apart from the reviewed image, empty listen-address override
and controlled restart annotation. There is no port5656 listener. No Service,
ingress, resource-policy, native environment binding or other app setting changed.

The explicit nonsecret chart override `UN_WEBSERVER_LISTEN_ADDR: ''` keeps the
new web interface disabled. Kubernetes omits the empty `value` field in API JSON;
the observer accepts that exact empty-literal shape, rejects valueFrom/extra
fields and verifies the actual listener state. The first stricter-shape failure
and its frozen source remain. It was an observer serialization mismatch, not an
application or credential failure.

## Bounded compatibility and security

A real ZIP was extracted by this exact official binary in isolated user/network
namespaces, with loopback-only mock Radarr,512MiB memory/no swap/oneCPU/64tasks
and180s outer deadline. Content, mapped ownership and0644 permissions matched.
After simulated import, only extracted payloads were cleaned; original/archive/
library sentinels survived. The config was not rewritten and the HTTP server
stayed off despite a nonempty file setting overridden by the empty environment
value. This does not prove a real Arr import, every archive type or NAS ACLs.
The original positive fixture source/result/logs and stricter current failure
status handling remain separately identifiable; no failed result was relabelled.

Live inventory found no watched folders, Whisparr, webhooks or command hooks, and
metrics is disabled. Existing numeric Sonarr/Radarr config/env keys continue to
work. The new extractor has vendor behavior changes, including a default Starr
expansion ratio7.5:1 versus5:1; unchanged config keys do not imply identical old
extraction limits. No new web credentials or UI configuration write was enabled.
The optional v1 history sidefile is separately bounded/recorded if created;
original file preservation is not waived.
[Official migration notes](https://unpackerr.zip/docs/install/upgrading/).

Same-feed unsuppressed comparison:5→4High and16→10Medium, with1Low/3Unknown
unchanged,0Critical/no CISA KEV match. The x/net High row is removed. Four Go
stdlib rows remain in vendor Go1.27.1 despite listed later toolchain fixes.
No clean-image claim or bespoke vendor patch is substituted.

At06:55UTC all63running-Pod image digests have complete same-feed reports:
89Critical/2828High/3613Medium/2103Low/1427Unknown package rows;2363unique CVEs.
The known FlareSolverr Chromium/CISA match remains. Counts are distinct-artifact
inventory, not exploitable-path totals or an assurance against unknown zero days.
Newer Jackett remains unadopted because its exact candidate has the same High
curl/libcurl findings. [Earlier snapshot/client checkpoint](SNAPSHOT-AND-CLIENT-TRUST-20261027.md).

## Delivery repair and preserved failures

The charts remote had advanced to Ingenium preparation while the shared checkout
still pointed at3a8de93. The first guard refused without writing. This operation
used an isolated Git source worktree; the shared HEAD/dirt and Ingenium's
zero-writer/no-PVC preparation remain. Pause:`3a15a8e3…`; adoption:`252a7527…`;
reviewed restart:`32c61656…`; accepted final source/transport fix:`5b894f24…`.
Every accepted publication passed all33existing/Ingenium tests and the normal
30-chart/31-release credential/effective-rendering validator. Actions stayed off.

Windows-to-WSL connection failures interrupted validation/observation. The final
maintained watcher launches via WSL root, then `/usr/sbin/runuser -u brajam`
before any validation/publication. The Linux publisher still enforces its
unprivileged ownership, exact source/ref/tool, size, validation and atomic
promotion guards. These were not weakened. The existing
[Ansible CI configuration](../k8s-rewrite/ansible-playbook/roles/local_build_storage/files/configure-local-ci.ps1)
applies the same account drop to the controller keeper. That configuration source
was applied and the regular existing scheduled publisher is running. No WSL,
Strata or application shutdown, new publisher, credential transfer or global
Windows security/execution-policy change occurred.

The cold verifier initially rejected the newly tightened64MiB profile before
reading its archive. That bounded tuple was added without changing old profiles;
the exact failed archive/reader then passed all original recovery checks. Old
failed receipt/source remain, with a separate successful recovery receipt.
Other retained failures include the optional master-side Arr read, the first
API empty-field observer, unsuccessful publisher/relay attempts and the first
Windows-Git interop cleanup check. None is an automatic approval rejection.

## Cleanup and recovery record

All generated work stayed in the existing F-backed root and source worktree
listed in [the output inventory](TASK-OUTPUT-INVENTORY.md). Completed cleanup
removed579,760,128allocated Linux bytes:

- 46,493,696B: the two reproducible binary copies under
  `platform-upstream-review-20261027/unpackerr-v1-qualification/vendor-unpackerr`
  and `unpackerr-fixture-__8d22ik/unpackerr`, generated ZIP/sentinel/library
  payloads and their five empty directories. Unique result/logs/config remain.
- 533,266,432B /2397paths: exact generated source/tool copies and empty scratch
  in successful publisher stages `c988683559884952a4f6422a3f521aa9`,
  `92a38cbe31b74c41b88d24bcf9d16409`, `cf1f3d7be92848ff9b5d530816c77a81`.
  Primary Git objects, source/locks, manifests and validation/publication receipts
  remain. The second full proof used read-only Linux Git as the actual owner
  after Windows interop failed; no deletion preceded the complete proof.

Exact absolute paths/bytes, creator/source/regenerator, hashes/inodes, locks and
full process/FD/maps/mount checks are in
`operator-control/unpackerr-v1-{fixture,publisher}-scratch-{plan,reconciliation}.json`.
Retain the source worktree, frozen source/failures, raw scans/recovery and all
runtime/data/originals. Failed publisher stages
`060844f1d0244cd684c31394bcecfb6b` and `f20435bfaa7d4f0688a8180c16ff2860`
remain in full for failure-source preservation. Earlier managed-command sentinels
and their `operator-control/tmp` parent remain for the missing creator/
regeneration/Windows-handle proof. This is controller Linux recovery, not node
or Windows filesystem recovery; no image or volume was pruned.

New evidence-only ciphertext:4,220,116bytes, SHA256
`374a1b84a7978c9c55251d544d227742aa5fbdcfbeb4410a8fa853ab964d8914`.
Every member and full authentication passed locally and by NAS read-back.
Prior metadata packets, scanner DBs and cold ciphertexts were referenced rather
than copied into it. Exact local/NAS receipts:
`operator-control/unpackerr-v1-metadata-receipt.json` and
`smb-unpackerr-v1-metadata-copy-status.json`. Originals and recovery-key backup
remain; independent whole-cluster restore and final IAB are not implied.

At06:57UTC all3nodes are Ready/no pressure,57claims Bound,31HelmReleases and all
Kustomizations Ready; no unavailable desired Deployment/DaemonSet. All27attached
Longhorn volumes are healthy with two RW replicas;16remain detached. Four old
failed diagnostic Pods remain preserved. BORTUS's separate-owner hold is unchanged.
Master/worker2 still fail Longhorn's unchanged25%floor by4,493,698,049B and
1,662,542,849B before additional pull/rebuild/payload space. Node cleanup is now
the priority; Longhorn recovery/upgrade, vendor/host exceptions and final IAB/
whole-goal acceptance remain open. [Upgrade design review](LONGHORN-UPGRADE-DESIGN-20261027.md).
