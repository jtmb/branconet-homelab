# Existing-cluster maintenance

This directory contains **21 opt-in maintenance playbooks for the existing
Branconet cluster**. It does not contain a cluster installer, reset playbook,
legacy `site.yml`, application variable lookup plugin, or BORTUS application code.
Use this runbook with [the active plan](../../PLAN.md),
[current status](../../MIGRATION_STATUS.md) and
[maintenance evidence](../../evidence/cluster-maintenance-20261023.json).

## Controller prerequisites and fresh-clone closure

Use native WSL as operator `brajam`, with the existing protected runtime at
`/home/brajam/.local/share/branconet-migration/venv/` (Ansible core 2.21.5),
Python, OpenSSH and known host keys. The three Ubuntu nodes are already installed;
`inventory/production.ini` binds James's port-2002 SSH identities at
192.168.0.4 (master), .5 (worker2) and .6 (worker1). The independent Kubernetes
runtime is `containerd-k8s`; do not start retired Docker/Swarm or Gluster.

The source closure is in this repository: role task/default/file/template
inputs, controller launchers, paired qualification observers and the seven public
image recipes. There are no imports from the BORTUS recovery framework and no
required private source files. Source availability does **not** provide operator
credentials, encrypted archives, scan databases, binaries or prior receipts.
Keep those outside Git. A fresh clone must use/recover the independently verified
operator runtime before attempting any live command; these playbooks do not
install or silently replace that runtime.

External execution inputs are intentional and fail closed if missing or changed:

- Native WSL SSH private/public key at `/home/brajam/.ssh/id_ed25519[.pub]`,
  known_hosts, existing cluster credentials and sudo authorization.
- Verified age executable at `.../bin/age`; backup helpers require SHA256
  `eb7dd1b518f0a307c99cd97782623c5321da049154b04acd2d98d21aa7bc9b2c`.
- BuildKit 0.34.1 standalone binaries from the reviewed archive SHA256
  `a59539daf547fe0958efe2d07e41c0a6944e1112a66d7e519ec1cf5b673ef15b`;
  setup tasks verify individual binary hashes. Image builds need the exact public
  context selected in their settings (the reviewed Seerr frozen lock is included
  under `images/seerr/`), sufficient capacity and a
  separately staged attempt; builds are never implied by source publication.
- Trivy 0.76.1 and the frozen October 23 vulnerability/Java databases at the
  exact paths and hashes in `roles/worker1_oci_scan/tasks/setup.yml`.
  The original DB snapshot must be retained/recovered separately; substituting a
  new database requires a reviewed new input seal, never altered old evidence.
- Accepted public OCI/provenance files, authenticated encrypted cold archives,
  receipt hashes and private qualification keys required by the chosen operation.
  Database/plaintext/keys and image archives are not repository dependencies.
- Remote application qualification uses the exact accepted app interpreter and
  bundled libraries. Bazarr's observer needs its existing PyYAML; Seerr's observer
  uses the image's Node/SQLite modules. No pip/npm installation is performed there.

All roles use `ansible.builtin`; no external Ansible collection or custom lookup
plugin is required. `ansible.cfg` preserves host-key checking and declares only
included paths. `group_vars/all.yml` contains the independent runtime pin/socket
and an in-memory sudo environment lookup, with no secret values/bootstrap pins.

From a fresh native WSL clone, perform source-only Ansible syntax validation with
an explicit config path (also required for Windows-mounted/world-writable paths):

```bash
cd k8s-rewrite/ansible-playbook
ANSIBLE_CONFIG="$PWD/ansible.cfg" \
  /home/brajam/.local/share/branconet-migration/venv/bin/ansible-playbook \
  playbooks/security-maintenance.yml --syntax-check
```

Repeat for the selected included playbook. Syntax validation cannot prove a
backup, successful drain, application behavior, recovery or production acceptance.
Do not execute live operations using example/placeholder identities or hashes.

## Included entrypoints

| Playbook | Dedicated controller helper / scope |
|---|---|
| `security-maintenance.yml` | `run-security-maintenance.py`: workers first, then single control plane; kernel/package/containerd patching |
| `storage-checkpoint.yml` | `run-security-maintenance.py --playbook storage-checkpoint`: fresh online Longhorn snapshot/off-node backup |
| `control-plane-backup.yml` | `run-control-plane-backup.py`: encrypted configuration/etcd capture and authentication |
| `cold-application-state-backup.yml` | `cold-application-state-backup.py`: one already-quiesced Arr/Tautulli/Vaultwarden app |
| `metube-state-backup.yml` | `run-metube-state-backup.py`: old ytdl PVC archive and legacy-file reobservation |
| `filesystem-growth.yml` | `run-filesystem-growth.py`: pinned worker1 ext4 filesystem growth, no partition/LV changes |
| `retired-build-offload.yml` | `run-retired-build-offload.py`: bounded original artifact archival; explicit reviewed selected-cache clearing only |
| `derived-oci-retirement.yml` | `run-derived-oci-retirement.py`: retire only proven reproducible scan materializations, keeping original artifacts/results |
| `seerr-image-build.yml` | `run-seerr-image-build.py`: retained bounded master-only Seerr build path |
| `ytptube-image-build.yml` | `run-ytptube-image-build.py`: separate retained bounded master-only YTPTube build path |
| `worker1-image-build.yml` | `run-worker1-image-build.py`: isolated public security image source/attempt |
| `worker1-oci-scan.yml` | `run-worker1-oci-scan.py`: offline exact OCI scan, no import or deployment |
| `ci-image-artifact-stage.yml` | Ansible with protected nonsecret settings: provenance-bound CI files to worker1 |
| `application-image-preload.yml` | Ansible with protected nonsecret settings: exact reviewed OCI cache import only |
| `vendor-cert-manager-scan.yml` | `run-vendor-cert-manager-scan.py`: only five fixed official1.21.3 public registry images; no deployment |
| `vendor-core-scan.yml` | `run-vendor-core-scan.py`: exact official etcd3.7.3/CoreDNS1.14.7 scans using the existing verified public inputs; no deployment |
| `etcd-static-patch.yml` | `run-etcd-static-patch.py`: reviewed singleton3.7.0 to3.7.3 image/config patch, fresh authenticated backup and frozen-revision preservation |
| `cold-pihole-state-backup.yml` | Full authenticated encrypted Pi-hole config/query/gravity backup after Flux quiescence |
| `local-oci-scan.yml` | Exact local OCI validation/scanning with explicit legacy or dedicated native F storage |
| `coredns-patch.yml` | Reviewed CoreDNS image only; original deployment, Corefile, Service and live DNS checks |
| `local-build-storage.yml` | Create/mount only the dedicated private F-drive ext4 build file; local root, opt-in |

Controller helpers live at repository `scripts/migration/`. Their `--help` and
corresponding docs define their accepted settings. Sudo is supplied through a
protected JSON stdin pipe and transported in the launcher's child environment,
never argv, Git, logs or shell history. No plaintext password example is provided.
Settings/receipts belong outside the clone. `--apply`/apply variables are explicit;
check mode is not a live-operation acceptance test. Do not weaken a refusal.

## Existing-cluster security maintenance

Read [security scope](../../docs/CLUSTER-SECURITY.md). Fresh authenticated recovery
receipts, healthy original Longhorn identities/replicas, all expected Ready nodes,
normal eviction/PDB enforcement and known emptyDir policy precede each cordon.
No force eviction, PDB bypass, runtime data replacement or automatic rollback is
implemented. A failure stops progression; inspect its preserved recovery receipt.
The single control-plane reboot temporarily interrupts the API. The original
2.4.1-to-2.4.2 path or unchanged 2.4.2 rerun is supported; unrelated runtime changes
refuse. Actual node maintenance already passed independent recovery checks;
source publication does not rerun it.

## Fresh online storage checkpoint and dedicated launcher

Select `run-security-maintenance.py --playbook storage-checkpoint`. Require the
explicit settings and a protected receipt path. Online snapshots/backups are not
cold application consistency or independent restoration. Keep original volumes,
healthy replicas, backup credentials and NAS target unchanged.

## Separate control-plane backup before master maintenance

Use `run-control-plane-backup.py`; it captures a separate encrypted configuration
and etcd backup, streams full authentication and preserves receipts outside Git.
Authentication does not prove an independent restore. Existing signing materials,
encryption config, SSH identity and original etcd image/digest remain bound.

## Separate MeTube cold state preservation

Read [MeTube state contract](../../docs/METUBE-STATE-BACKUP.md) and
[YTPTube acceptance](../../docs/YTPTUBE-ACCEPTANCE.md). Quiesce the existing writer
through the charts owner first. The helper never stops it automatically. Original
PVCs/NAS/downloads stay intact. Reobservation excludes only the three documented
new YTPTube directories and verifies every legacy file/metadata fingerprint.

## Cold application state and qualification

Read [cold state and SQLite contracts](../../docs/COLD-APPLICATION-STATE-BACKUP.md).
The source includes Radarr/Sonarr/Bazarr, Seerr and YTPTube before/after/restart
observers and Radarr/Sonarr SQLite Users-table verification. Pair files stay
adjacent; imports use included role-local archive primitives. Application writes
are quiesced externally before cold capture. SQLite read-only observations may
coordinate SHM locks; do not substitute immutable-mode shortcuts that omit WAL.
Private HMAC keys and authenticated originals remain outside Git. Stored-account
fingerprints do not prove interactive login or authorization behavior.

## Bounded master-only Seerr image builder

`run-seerr-image-build.py` operates only a fresh explicit retained attempt under
the documented resource/capacity fences. Prefer the already authorized separate
private charts artifact workflow for new off-cluster image builds. No local build
starts merely because these retained operational paths are published.

## Prepared retired master public artifact offload

Read [offload contract](../../docs/RETIRED-BUILD-OFFLOAD.md). Only the fixed retired
public build trees and reviewed cache IDs are eligible. Full ciphertext/stream
verification precedes any explicitly selected cache clear. Never sweep original
failure evidence, private application data, current builders or unrelated Strata.

## Prepared worker1-only security image builder

`run-worker1-image-build.py` stages public source/tools into a distinct sealed
attempt. Reviewed capacity, cgroup and no-secret/no-runtime-import guards remain.
Old seals/attempts are never overwritten. Check its service allowlist before use;
not every public recipe implies a supported local-build service.

## Separate bounded YTPTube image builder

`run-ytptube-image-build.py` retains its own source, units, input seal and logs.
Do not reuse or overwrite a Seerr attempt. Actual accepted CI artifacts and their
immutable runtime/scan receipts take precedence over older failed local attempts.

## Exact offline worker1 OCI vulnerability scans

Read [CI/image provenance](../../docs/CI-IMAGE-SCAN-PROVENANCE.md). The scanner
uses only the SHA-bound public OCI/recipe/provenance and frozen DB files, with
read-only/no-exec source mounts and bounded resource/time/capacity guards.
It does not run an image, import it, suppress findings, modify charts or deploy.
Fresh scan attempts and content-addressed helpers preserve prior results.

## Pinned worker1 existing-LV filesystem growth

`run-filesystem-growth.py` accepts only the reviewed .6 ext4 filesystem UUID,
preflight hash and exact device/mount guards. It grows the filesystem only;
partition, LV, other filesystems and production mounts are outside its scope.
Do not rerun based solely on the historical need for more space.

## CI artifact staging

`receive-ci-image.py` validates the private repository/workflow/run/attempt/job/
artifact/head and original outer ZIP before protected native WSL reception.
`ci-image-artifact-stage.yml` then checks provenance and every selected file before
and after worker transfer, with no overwrite or image execution. GitHub/GCM
credentials stay in memory. The private charts workflow/CI helper are maintained
in that separate repository and are intentionally not duplicated here.

## Maintenance application cache-only OCI preload

`application-image-preload.yml` imports only exact reviewed public images into
`containerd-k8s`'s Kubernetes cache namespace. Optional controller-to-node staging
retains file ownership/hash/capacity/no-overwrite fences. It does not change a
Deployment or pull policy. Deployment still requires the separate reviewed charts
main -> validation -> validated -> Flux path, followed by real app acceptance.


## Exact five-image official cert-manager scanner

The separate vendor registry path uses the existing frozen W1 public inputs and
Results-only template, with explicit verified private copies for an unprivileged
networked unit whose real operator home is hidden. It preserves1GiB/noSwap/200%
CPU/128-task/900-second hard bounds for the whole five-image batch. New setup
requires space for approximately1.80GB public input copies plus the unchanged
filesystem reserve. Existing private configs, old scanners and all production
objects remain unchanged. See the exact source/provenance/limits and operator
calls in [CI/image provenance](../../docs/CI-IMAGE-SCAN-PROVENANCE.md#exact-official-cert-manager-1213-registry-scans).
This fixed Go-only path does not copy/link the Java database; Java analysis stays
enabled and unexpected Java package evidence refuses. Both database-update skips,
offline analysis and all capacity/resource floors remain unchanged. No actual
scan follows from this source checkpoint.


## Refresh an installed offline scanner helper

After initial setup, opt-in `run-worker1-oci-scan.py --phase helper` fully verifies
the exact installed tool, vulnerability/Java databases, metadata, Results template
and empty configuration/ignore files before copying only the missing new
content-addressed helper and seal. Hashes, sizes, root ownership/modes, single-link
identities and protected directories are checked. The filesystem reserve remains
25% plus8GiB, with the existing inode floor; only twice the helper size plus twice
a64KiB seal allowance is charged for this small transfer. Initial setup and its
large-copy capacity check remain unchanged. No scan or large-input replacement
runs. Conflicting existing sources/seals refuse.

## Retire reproducible successful scan materializations

`derived-oci-retirement.yml` and `run-derived-oci-retirement.py` are opt-in and
limited to seven fixed successful scan attempts on worker1. Every original OCI
archive and its original CI/build proof, completed scan report and vulnerability
projection must authenticate before any removal. The projection exactly matches
the original scanner's `get()` behavior for absent optional fields. Every selected
blob and layout/index byte must be reproducible from the original archive.

Only the redundant `selected-runtime.oci` directories may be moved into the
owned receipt directory and unlinked, using fresh inode/path/mount/open-handle
checks and durable per-file receipts. All originals, failed attempts, databases,
reports/diagnostics, source trees, application data, PVCs and NAS media remain.
The exclusive scan lock prevents overlap. Review/retire/status never scan or
deploy; interruption preserves receipts and any incomplete quarantine.

`qualify-flaresolverr.py` separately observes the exact deployed derivative,
owner/digest/native-reference/resource contracts and matched browser/driver, then
performs one actual public-page browser request. It retains only hashes and
metadata, not cookies/content. This does not replace final Codex IAB acceptance.


The [Vaultwarden acceptance helper](../../docs/VAULTWARDEN-ACCEPTANCE.md) pairs
with its existing whole-application cold-backup role. Run its cold-only schema
preflight before publishing the new writer, then its full comparison after the
exact reviewed rollout. It does not scale or deploy workloads.


Owned maintenance scripts, image recipes and Ansible inputs use LF through
root `.gitattributes`, preserving executable shell input and reproducible
content-addressed helper/lock bytes across Windows and WSL checkouts. The policy
does not alter unrelated application or legacy paths.
