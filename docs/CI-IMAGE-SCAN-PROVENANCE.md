# Offline scanning of private CI image artifacts

Current checkpoints and unresolved gates are summarized in [MIGRATION_STATUS.md](../MIGRATION_STATUS.md). This document retains operational contracts and dated attempt history.

The existing worker1 scanner now has two explicit source kinds. Its default
`worker1` path still requires the original local builder seal, successful runtime
receipt and BuildKit metadata. `github-actions` instead validates original private
CI evidence. It never creates or substitutes local builder receipts. Both modes
use the same scanner, immutable databases, limits, OCI verification and reporting.
This document describes source preparation; it does not claim a scan or adoption.

## Operator staging and trust boundary

Root first obtains authenticated GitHub API metadata for the private repository,
workflow, completed successful run/job, and uploaded artifact. Root downloads the
outer ZIP, verifies its complete SHA256/size against the API artifact, checks unique
safe ZIP members, and verifies the original uploaded file bytes before staging.
Keep that original ZIP and API evidence in the protected controller evidence.
No API token, credential, application Secret or raw image Env belongs in the
provenance document, scanner arguments, Git or output.

### Existing-ZIP Windows receiver

Prepared source `scripts/migration/receive-ci-image.py` accepts exactly Seerr,
YTPTube, Jackett, Pi-hole, FlareSolverr and Vaultwarden artifacts from this existing workflow.
The fixed identifiers are `seerr`, `ytptube`, `jackett`, `pihole`, `flaresolverr` and `vaultwarden`.
`--service` defaults to `seerr` for compatibility; select another explicitly.
It does not download
the artifact again. Root supplies the
existing completed ZIP path, reviewed ZIP SHA/bytes, run/artifact IDs and source
head SHA. An explicit `--apply` is required. The receiver first hashes the entire
original ZIP, then obtains the actual repository, workflow, successful run/build
job and artifact API objects. Windows Git Credential Manager supplies its GitHub
credential through an in-memory pipe. GET requests use Bearer authentication
only to `https://api.github.com`, with redirects disabled and no proxy inherited.
No token enters argv, output, provenance or the WSL transfer.

```powershell
python scripts/migration/receive-ci-image.py --apply --service seerr --zip C:/protected/github-artifact.zip --zip-sha256 <reviewed-zip-sha256> --zip-bytes <reviewed-zip-bytes> --run-id <runID> --artifact-id <artifactID> --head-sha <reviewed-40-hex-head>
```

It requires the private charts repository, the exact active image workflow, a
successful manual run on main at the supplied head, and its one successful build
job. Artifact name, run/attempt/head/repository IDs, expiration, API digest and ZIP
size must agree. ZIP members are unique even under case folding, regular files,
unencrypted and in a finite known-file allowlist; unknown paths, links, duplicates
and over-limit files refuse. OCI size is at most four GiB and total expanded ZIP
size at most five GiB. The receiver hashes every original file and inspects only
outer OCI tar metadata, index and layout. It never expands image layers, reads
image configuration for output or executes uploaded code. It validates the actual
uploaded result, frozen lock, runtime-input manifest, host/effective cgroups and
original capacity preflight against the same contracts below.
The selected service must agree in the artifact name, preflight, result and
`<service>.oci.tar` basename. The original uploaded `runtime-metadata.json` is
also required: its actual BuildKit image digest and descriptor must match the
actual OCI index and result, and its config digest must be well formed. Config
blob/layer verification still belongs to the exact-artifact scanner. This
metadata is retained with its original hash rather than executed or rewritten.
Seerr's exact frozen-lock SHA and 561,754-byte size remain mandatory in the
uploaded lock, result and runtime-input manifest. The four non-Seerr services instead
require the original result's `frozen_lock_sha256` to be null and refuse a
Seerr/pnpm lock file or runtime-input lock claim; no fake lock is synthesized.

Original ZIP bytes remain on Windows. Every allowlisted original uploaded file
streams in one-MiB chunks through WSL Python stdin into a new fixed controller
directory:

```text
/home/brajam/.local/share/branconet-migration/ci-image-artifacts-20261024/<runID>-<artifactID>/
```

The controller directory is owner-only 0700, files are new regular 0400 files,
and actual written sizes/hashes are rechecked. A two-GiB free-space reserve and
ten-minute transfer deadline apply. Existing directories/files are never
overwritten. Failure retains the original ZIP and partial new directory for
review; it does not clean or retry automatically. Uploaded scripts/recipe tar
and logs remain opaque retained evidence, not executed source.

Two real attempts reached native transfer but failed before creating the native
CI base directory. One bounded public mock isolated WSL argument handling:
backslashes in the multiline `python3 -c` program were reinterpreted, producing
a SyntaxError before protocol processing. The corrected transport uses WSL
`--exec` and base64-encodes only the trusted receiver program before compilation;
all artifact data still travels through the same bounded binary stdin protocol.
It does not encode credentials into argv or weaken any path/hash/capacity guard.
Native failures now report only a finite operation, exception class, source line
and exit code. Raw child diagnostics/data are suppressed. The observed original
CI base/run directories were absent, so this fix requires no deletion, overwrite
or alternate output directory. No successful real reception is claimed by this
source correction; the original ZIP and failed-attempt evidence remain retained.

The new private `provenance.json` contains actual API objects, complete outer ZIP
identity and exactly the selected scanner inputs under `files`: seven for Seerr,
or six for YTPTube/Jackett/Pi-hole/FlareSolverr/Vaultwarden, which have no pnpm lock.
`retainedFiles` separately binds other original uploaded files without widening
the scanner's input allowlist. Root still must review and stage only the selected
files plus provenance into the root-owned worker1 location below. Reception
returns `received-not-scanned-not-deployed` with the provenance SHA and exact OCI
root descriptor. Neither receiver AST checks nor successful reception establish
image security, native compatibility, account preservation or deployment.

On worker1 the only accepted CI input location is:

```text
/home/james/.local/share/branconet-migration/ci-image-artifacts-20261024/<runID>-<artifactID>/
```

The CI base and selected run/artifact directory must be root-owned mode0700,
with no symlink components. Every staged input is a root-owned mode0400 regular
file with link count1. Neither the scanner nor its Ansible role transfers these
artifacts or generates provenance. The operator stages only:

| File | Source and bound |
|---|---|
| `<service>.oci.tar` | Exact completed uploaded OCI, at most4GiB |
| `result.json` | Original uploaded JSON, at most4MiB |
| `preflight.json` | Original uploaded JSON, at most4MiB |
| `builder-host-limits.json` | Original uploaded JSON, at most4MiB |
| `builder-limits.json` | Original uploaded JSON, at most4MiB |
| `runtime-inputs-sha256.json` | Original uploaded JSON, at most4MiB |
| `pnpm-lock.yaml` | Seerr only; original uploaded frozen lock, at most16MiB |
| `provenance.json` | Operator binding of API metadata and verified files, at most4MiB |

Other ZIP members remain preserved in the original archive but are not staged as
scanner inputs. The provenance `files` map accepts exactly the above uploaded
files, excluding `provenance.json` itself. Each entry contains its actual
`sha256` (64 lowercase hex) and positive integer `bytes`. A separate explicit
command argument binds the complete provenance file SHA256.

## Repeatable controller-to-worker staging

Prepared source `playbooks/ci-image-artifact-stage.yml`, role
`ci_image_artifact_stage`, stages only these already verified controller files to
worker1. Its apply flag defaults false; check mode transfers nothing. It never
downloads, contacts GitHub/Kubernetes, imports an image, runs a scanner, launches
an application or changes existing workload/storage state. No staging execution
is claimed by this source preparation.

The fixed controller location is
`/home/brajam/.local/share/branconet-migration/ci-image-artifacts-20261024/<runID>-<artifactID>`.
Both source directories are owned by `brajam` with mode0700, and selected files
are mode0400 regular files with link count1 and no symlink components. The helper
verifies the complete provenance SHA and each selected original file SHA/size,
bound to the requested private CI service/run/artifact/source head and successful
uploaded result. Only the exact original proof-file allowlist and provenance are
copied; other retained controller evidence is neither copied nor removed.

The destination base/run directories must either be absent or already root-owned
mode0700 with no symlinks. The existing operator parent is inspected and never
changed. Existing selected destination files must already be root-owned0400,
single-link regular files with matching SHA/size; unknown entries or conflicts
refuse before copying. Ansible creates only missing fixed directories and copies
only missing selected files with `force:false`, ownerroot and mode0400. It never
overwrites/chowns a conflicting file, relaxes existing permissions or cleans up
partial/old data. Matching partial copies can be completed without replacing
existing bytes. The worker copy is fully rehashed, and controller hashes/inode/
size/timestamps are checked again after transfer. Output is metadata only.

Before transfer the destination must preserve the existing scanner reserve:
25% filesystem capacity plus8GiB, room for missing copy bytes plus twice the OCI
archive size, and at least max(250,000,10% total) free inodes. This does not
change scanner limits or imply readiness for image unpack/runtime adoption.

Example nonsecret settings for the verified Seerr artifact (keep operational
settings/evidence outside Git):

```json
{"ci_image_artifact_stage_apply":true,"ci_image_artifact_stage_service":"seerr","ci_image_artifact_stage_run_id":40048938336,"ci_image_artifact_stage_artifact_id":12542054969,"ci_image_artifact_stage_provenance_sha256":"a3539e17170a4638c4937d7bf3d4c292f06fa2da21bbc6d75209536e9b31b998"}
```

From a reviewed native WSL stage's Ansible directory:

```bash
/home/brajam/.local/share/branconet-migration/venv/bin/ansible-playbook playbooks/ci-image-artifact-stage.yml --limit workernode1 --extra-vars @/protected/ci-stage-settings.json
```

The playbook uses the existing inventory, strict SSH key/host checks and sudo
credential supplied only through `BRANCONET_MIGRATION_SUDO_PASSWORD` by the
operator's protected stdin wrapper. No credential belongs in extra-vars, argv,
provenance or logs. Service defaults to `seerr`; the fixed allowlist also permits
`ytptube`, `jackett`, `pihole`, `flaresolverr` and `vaultwarden` with their exact verified artifact contracts.
Stage success is separate from fresh scanner setup, exact scan review, preload
and deployment acceptance.

## Provenance JSON contract

Top-level keys are `schemaVersion:1`, `sourceKind:"github-actions"`, `github`,
`outerZip`, and `files`. Additional API fields are allowed inside the original
GitHub objects but are not copied into the scanner's selected receipt.

`github` contains these actual API objects/fields:

| Object | Required fields and relationships |
|---|---|
| `repository` | `full_name:"jtmb/branconet-charts"`, `private:true` |
| `workflow` | `path:".github/workflows/build-security-images.yml"` |
| `run` | Positive `id` and `run_attempt`, 40-hex `head_sha`, `event:"workflow_dispatch"`, `status:"completed"`, `conclusion:"success"` |
| `job` | Positive `id`, matching `run_id`/`head_sha`, `name:"build"`, completed/success |
| `artifact` | Matching positive `id`, `expired:false`, exact API `size_in_bytes` and `digest`, matching `workflow_run.id`/`head_sha` |

Artifact name must equal
`security-<service>-<headSHA>-<runID>-<runAttempt>`. `outerZip` contains verified
integer `bytes` and 64-hex `sha256`, matching artifact `size_in_bytes` and
`digest:"sha256:<hash>"`. Run/artifact IDs are positive integers below2^63 and
select the fixed directory; caller archive paths are not accepted.

The scanner independently SHA-checks each staged original proof file, then binds
uploaded `result.json` state `artifact-built-not-qualified-not-deployed`, service,
`source_commit`, archive hash/bytes, and its single exact OCI root descriptor to
the API/command inputs. Its original runtime input manifest must contain a valid
Dockerfile hash and only bounded relative filename/hash entries. Seerr requires
the actual lock file, runtime-input lock hash and result frozen-lock hash all equal
`9665b245267e7c864210bdf85f1098c0891f30946c64b3781f44077fff0b7811`.
Other services require no frozen-lock claim.

Original host and effective builder evidence must agree on the exact container
`buildx_buildkit_security-<runID>-<runAttempt>0`, 3GiB memory, zero swap, 150% CPU
(quota150000/period100000), CPUs0-1, and512 tasks. The original preflight must bind
the same source/service/run/attempt and preserve the 18GiB initial free-space
requirement, 12GiB build allowance, 4GiB OCI bound, 2GiB reserve and10% free inodes.
These are CI build limits; the subsequent offline scanner retains its separate
1GiB/zero-swap/two-CPU/128-task limits.

The scanner is offline. It cannot independently authenticate GitHub or reread the
remote ZIP; that boundary is explicitly the operator's SHA-bound receipt and
retained authenticated API/download evidence. It does independently verify staged
proof-file bytes and all selected OCI contents. It records `sourceKind` and
`ciProvenance`, with actual CI IDs/head/ZIP/proof-file hashes and build bounds;
it records no local `builder` object for CI input. Archive inode/size/time identity
and all provenance hashes are rechecked before and after scanning.

## Invocation

First stage/review a fresh content-addressed scanner source version. Use
`--phase setup` for initial tool/database installation; that path and its original
large-copy capacity guard are unchanged. Once the exact inputs are installed,
`--phase helper` refreshes only a content-addressed helper/seal. Before any helper
copy it fully hashes the fixed installed Trivy binary, both DBs and metadata,
results template and empty config/ignore files, and verifies their exact sizes,
root ownership/modes, single-link regular-file identity, protected directories
and absence of symlink substitution. It preserves the existing 25% filesystem
plus 8 GiB and inode floor, charging only twice the reviewed helper byte size
plus twice a 64 KiB seal budget; it does not reserve room to recopy existing
large inputs. The reviewed helper must remain at most 256 KiB. No tool, DB, template or config is transferred, replaced or normalized.

Existing helper-file conflicts refuse before writes. Only a missing selected
root-owned version directory/helper may be added, followed by the new helper's
unchanged `setup` / `inputs()` full-hash self-seal. Existing seals must match,
never be replaced. The ordinary selected-metadata status branch remains in use;
no scanner is launched by the helper phase. Scan admission, resource/deadline
bounds, DB freshness, service/provenance and original-input checks are unchanged.
Prior helper versions, seals, builds and failed scans remain unchanged. Example
(all IDs/hashes must be actual verified values):

```bash
venv/bin/python <stage>/scripts/migration/run-worker1-oci-scan.py --apply --phase setup --output-dir <protected-controller-output>
# For an already fully installed scanner, use helper instead of repeating setup:
venv/bin/python <stage>/scripts/migration/run-worker1-oci-scan.py --apply --phase helper --output-dir <protected-controller-output>
venv/bin/python <stage>/scripts/migration/run-worker1-oci-scan.py --apply --phase scan --source-kind github-actions --service seerr --ci-run-id <runID> --ci-artifact-id <artifactID> --ci-provenance-sha256 <provenanceSHA256> --archive-sha256 <ociSHA256> --root-descriptor sha256:<rootDigest> --output-dir <protected-controller-output>
```

`--build-attempt` remains its default `initial` in CI mode solely for CLI
compatibility; no local build attempt is claimed. A nondefault value refuses CI
mode. Worker mode rejects CI identity arguments. Both retain private stdin-only
sudo transport and fresh scan attempt identities. The CI input directory is
read-only/no-exec within the scanner unit; no image layer is executed, no runtime
import/deployment occurs and `securityAcceptance` remains false.

See the [unchanged scanner execution contract](../k8s-rewrite/ansible-playbook/README.md#exact-offline-worker1-oci-vulnerability-scans)
and [cluster maintenance scope](CLUSTER-SECURITY.md).

The first actual staging preflight refused before transfers because the existing
shared migration parent is James-owned0775. Live metadata verifies its group is
James's own primary group with no other members; it is not world-writable.
The parent check now permits read/traversal modes and group write only when the
group's complete member set is exactly that same operator. It does not chmod or
chown the shared parent. New CI base/run directories remain root-owned0700 and
all eight files root-owned0400, with the original digest/no-overwrite checks.

## Exact official cert-manager 1.21.3 registry scans

A separate `vendor-cert-manager-scan.yml` and
`scripts/migration/run-vendor-cert-manager-scan.py` cover **only** controller,
cainjector, webhook, acmesolver and startupapicheck at the five fixed official
1.21.3 index/amd64 digest pairs in `vendor_cert_manager_scan/files/scan_vendor.py`.
`sourceKind` is always `upstream-registry`. This is source preparation, not five
completed scans, verified signatures, CI provenance, image adoption or deployment.
It does not extend or weaken the existing CI/worker OCI scanner's input contract.

The primary chart index is
`sha256:e482675aec32862d323a9218293ff7de81192337998615e4378c56498473f240` at
`oci://quay.io/jetstack/charts/cert-manager`. Official
[1.21.3 release notes](https://github.com/cert-manager/cert-manager/releases/tag/v1.21.3)
identify Go1.26.10/CVE-2026-111943, x/net0.60.0, compromised eMudhra trust removal
and the unowned next-private-key Secret copying fix. This is an in-train patch
from the current1.21.2, not a major migration. Its sole CRD delta is the optional
Certificate `status.acme.ari.certID` string. All five other CRDs and values.yaml
are byte-identical in the primary old/new chart comparison. The existing
Flux HelmRelease/OCIRepository retain ownership; application/Secret/CRD mutation
is outside the scanner.

### Setup and execution boundary

Only worker1 (192.168.0.6) is supported. Explicit setup verifies the already
staged W1 Trivy0.76.1, the frozen main vulnerability database and Results-only
template, then makes
an exclusive verified public snapshot under
`/home/james/.local/share/branconet-migration/vendor-cert-manager-scan-20261024/inputs`.
Existing tool/DB/config bytes and all old audit/scanner attempts remain unchanged.
Approximately1.80GB of public input copies are required so the networked scanner
can run unprivileged without granting access to the original root-only inputs.
The copied immutable files are root-owned and readable only by root and James's
verified private primary group. Interrupted/different copies refuse; no automatic
replacement, cleanup or fallback download occurs.

A fresh12-hex attempt is prepared exclusively. Its batch runs as James with no
capabilities, a tmpfs-hidden home, a read-only bind of only the new public scanner
root, and a writable/no-exec bind of only its own attempt. Actual SSH/kubeconfig,
Kubernetes/CRI paths and production storage are hidden/inaccessible. A clean
`env -i` entry and allowlisted scanner environment prevent credential inheritance.
Its fresh HOME, `{"auths":{}}` Docker config, empty Trivy config and empty ignore
file never read/change existing user configuration. Each index and selected
amd64 manifest is SHA-verified directly over verified HTTPS at Quay, with no
metadata redirects/proxy/authentication; those primary documents are retained.
Trivy remote mode acquires only the allowlisted public Quay image references,
including registry/CDN blob redirects. Network is enabled for this acquisition;
this is not a claim of kernel-level domain filtering. Offline dependency analysis,
both DB-update skips and version-check skip prevent auxiliary update lookups.
The1.56GB Java database is not copied or linked: these five fixed images contain
Go tools. Java analysis is not disabled. Any Java result type, Java language,
Maven/Gradle package identity or JAR/WAR/EAR/POM evidence refuses the batch; a
scanner error from an unavailable Java database also fails rather than implying
a clean result. An unexpected language needs separate reviewed inputs, not a
weaker retry.
No Kubernetes, CRI, image import, application execution or Secret access runs.

The entire sequential five-image batch retains the prior hard bounds:1GiB RAM,
zero swap,200% CPU,128 tasks and900seconds (a stricter shared batch deadline,
not900seconds per image). Actual systemd and cgroup limits are recorded and must
match before network acquisition. Each image also has the existing7-minute
Trivy timeout/480-second watcher; the batch's own840-second watcher stops its
child before the unit ceiling. A shared public-input flock and `/proc/comm`
checks refuse overlap with another scanner without stopping anyone else's work.
The global disk reserve remains25% of filesystem capacity plus8GiB and the inode
floor remains the greater of250,000 or10%. A fresh attempt is bounded to2GiB,
100,000 files,64MiB per Results report and16MiB stderr, sampled every2seconds;
LimitFSIZE is256MiB. Sampling does not promise zero overshoot.

The pinned vulnerability DB must still be younger than24hours. Fresh setup does
not refresh it. `--scanners vuln`, `--image-src remote`, `--platform linux/amd64`,
`--offline-scan`, `--skip-db-update` and `--skip-java-db-update` are fixed.
`--format template` receives only Results using the existing `{{ toJson . }}`
template; ImageConfig/Env/history/labels are never serialized in the report.
Package lists remain for actual dependency/version attribution. Native Go-binary
coverage, complete input rehash, Results hashes/counts and terminal state are
required; scanner exit alone cannot mean clean. Failures preserve every attempt,
partial output and diagnostics. Status observation can finalize an interrupted
unit as failed without rerunning it. Every receipt keeps `securityAcceptance:false`.

### Operator calls after source review

Supply the same protected JSON sudo stdin transport as the other launchers;
never put a credential in argv, files in Git, logs or shell history. Examples show
only nonsecret flags; `<protected-password-json-pipe>` is an operator-owned RAM
pipe, not a literal shell command or password:

```text
python scripts/migration/run-vendor-cert-manager-scan.py --syntax-check
<protected-password-json-pipe> | python scripts/migration/run-vendor-cert-manager-scan.py --apply --phase setup --output-dir /home/brajam/.local/share/branconet-migration/vendor-cm-controller-20261024
<protected-password-json-pipe> | python scripts/migration/run-vendor-cert-manager-scan.py --apply --phase scan --output-dir /home/brajam/.local/share/branconet-migration/vendor-cm-controller-20261024
<protected-password-json-pipe> | python scripts/migration/run-vendor-cert-manager-scan.py --apply --phase status --attempt <returned12hex> --output-dir /home/brajam/.local/share/branconet-migration/vendor-cm-controller-20261024
```

The launch receipt is not scan completion. Review the remote terminal receipt,
all five Results files and residuals before the separately reviewed existing
private charts CI/validated/Flux patch. Keep original chart/CRDs, resource values,
certificate/issuer identities and Secret references. Require three Ready
Deployments, webhook admission, existing Certificate/ClusterIssuer readiness and
verified application TLS routes after any actual upgrade. Do not force renewals,
delete/recreate CRDs or grant the scanner deployment authority.
