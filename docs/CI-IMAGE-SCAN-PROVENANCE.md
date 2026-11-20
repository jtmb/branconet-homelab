# Offline scanning of private CI image artifacts

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
YTPTube, Jackett, Pi-hole and FlareSolverr artifacts from this existing workflow.
The fixed identifiers are `seerr`, `ytptube`, `jackett`, `pihole` and `flaresolverr`.
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
or six for YTPTube/Jackett/Pi-hole/FlareSolverr, which have no pnpm lock.
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
`ytptube`, `jackett`, `pihole` and `flaresolverr` with their exact verified artifact contracts.
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

First stage/review a fresh content-addressed scanner source version and complete
its normal explicit setup. Prior helper versions, seals, builds and failed scans
remain unchanged. Example (all IDs/hashes must be actual verified values):

```bash
venv/bin/python <stage>/scripts/migration/run-worker1-oci-scan.py --apply --phase setup --output-dir <protected-controller-output>
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
