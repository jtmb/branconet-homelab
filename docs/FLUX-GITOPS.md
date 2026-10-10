# BORTUS and the homelab Flux pipeline

The locally qualified static rotation workflow can explicitly request a named same-namespace Deployment/StatefulSet/DaemonSet template reload for an effective administrator with rotate policy. It patches only the pod-template rotation marker with UID/RV conditions, never edits Git, and reports requested/ambiguous outcomes separately from consumption. Flux may reconcile that marker back; operators must coordinate reload and external credential validity. No automatic restart or cluster-wide reload occurs. This workflow passed local unit and production HTTP/fake-CLI qualification; real Flux/controller acceptance remains pending.

BORTUS K8s Manager displays and manages the Flux resources in the connected
cluster. Application code remains in `jtmb/branconet-homelab`; the private
[branconet-charts repository](https://github.com/jtmb/branconet-charts) owns all 33
live application charts, their values and Flux foundation configuration.

## Production contract

| Item | Configuration |
|---|---|
| Authoring branch | charts repository `main` |
| CI-promoted branch | `validated`, pointing to the exact successful current-main SHA |
| Successful revision tag | `validated-<full-sha>`; never move it |
| GitRepository | `flux-system/branconet-charts` |
| Source URL | `ssh://git@github.com/jtmb/branconet-charts.git` |
| Native source credential | `flux-system/branconet-charts-readonly`; repository-specific read-only SSH key |
| Kustomization | Existing `flux-system/migration-releases` |
| Composition path | `./flux/releases` |
| App package/values | `charts/<name>/`, `charts/<name>/values.yaml` |
| Effective app overrides | `flux/releases/<name>.yaml` |
| Chart source | `GitRepository/branconet-charts`, namespace `flux-system` |
| Chart path | `./charts/<name>` |
| Strategy | `Revision`; content updates reconcile without a Chart.yaml version bump |
| Infrastructure | Same foundation resources; cert-manager keeps its OCI digest |
| Removal/recreation policy | `prune:false`, `force:false`, retained claim keep annotations |

CI checks all packages, activation/staging gates, effective rendered releases,
resource uniqueness, credential scanning and complete foundation composition.
Only a successful run for current main promotes its exact SHA. PR validation
never promotes. CI has no Kubernetes credentials; the promotion job alone gets
repository contents write permission. Flux polls the source and chart artifacts
at one minute; normal release intervals are five minutes.

The existing Kustomization and all 34 release identities are retained. The old
`migration-validated` source is retained suspended and pinned to checkpoint
`373a1e513e1bfb8b13ed5212ccc1b0f57a5ff301`. Its old CI publisher is removed;
archived chart validation does not deploy. There is one active Kustomization.

## Edit, inspect and reconcile

Change the relevant chart values/templates or effective release overrides in the
charts repository, commit and push to main, then inspect successful CI and live
observed revisions. Raw copied manifests in package folders are historical
reference material; Helm uses templates and values.

```bash
kubectl get gitrepositories,kustomizations -n flux-system
kubectl get helmreleases -n flux-system
kubectl describe gitrepository branconet-charts -n flux-system
kubectl describe kustomization migration-releases -n flux-system
flux reconcile kustomization migration-releases -n flux-system --with-source
```

A chart content change does not require a version bump for this Git source.
Meaningful chart API/version changes should still be versioned for maintainers.
The setup canary changed only an HTTP echo Pod annotation, left version 0.1.0
unchanged, and proved CI/source/Helm revision updates, real rollout and rollback.
See [setup acceptance](CHARTS-SEPARATION.md) and the
[charts acceptance record](https://github.com/jtmb/branconet-charts/blob/main/docs/ACCEPTANCE.md).

## BORTUS image releases

The production chart remains `bortus:migration-1438b27`, `imagePullPolicy: Never`,
with that exact image preloaded on all three nodes. Source pushes in the app
repository can validate/build independently but do not publish or deploy an
image. For a new approved application release, build from a clean verified source
context, exclude environment/database/build artifacts, publish or preload an
immutable image version on all nodes, checkpoint the native SQLite volume and
migration/recovery requirements, then change only the reviewed image/chart
contract in the charts repository. Push through this pipeline and verify health,
readiness and native Secrets behavior. Never change registries or image versions
as a repository-separation side effect. Application rollout remains coordinated
with the BORTUS development owner.

## Dashboard, credentials and recovery

Malformed condition types become Other rather than being string-coerced into public output. Conditions are capped at 32; malformed event timestamps are withheld instead of echoed. The repository detail view labels a withheld URL, links only validated HTTPS locations, and explains the withheld messages/annotations. All 89 unit tests, lint, fresh production build/typecheck and both production HTTP fixtures passed; see [confidentiality evidence](implementation-evidence/flux-confidentiality.json). Fresh Flux browser acceptance remains pending.

The projection withholds invalid/credential-bearing existing repository URLs from API metadata without rewriting their DB/native records. Flux JSON reads pass the shared annotation/managed-field/value/message filter. Readiness remains structured Ready/Not Ready/Unknown; condition types/status are allowlisted, and raw controller condition/event messages are withheld. Detailed raw controller output must be inspected through the independent operator environment. Repository names, branches and paths remain nonsecret operator metadata; arbitrary opaque values deliberately placed in those locations cannot be identified as credentials.

Repository URLs are public/persisted metadata. New submissions accept credential-free HTTPS/SSH URLs and SSH SCP spelling, reject HTTP/other schemes, HTTPS userinfo, SSH passwords, query strings, fragments and control characters before any DB/native/CLI change. Authentication must use the separate private credential field, which is written only through the verified native Secret API. Existing URL records require operator review; no automatic database rewrite is performed.

Repository cascade removal retains native credentials and reports that fact in its Flux-resource progress step. It never infers credential ownership from `<repository>-auth` or deletes a whole Secret. Credentials may be shared, imported or adopted by the KV engine; clean them up only through explicit native key/version operations after checking their exact references and consumers. Current-namespace RBAC remains get/list/create/update without Secret delete. Namespace deletion can still remove resources in the selected application namespace; `flux-system`, where repository credentials live, is protected from this cascade.

Application command contract: kubectl operations use argv arrays and validated Kubernetes names. Subprocess failures are fixed typed errors, without raw stderr. Cascade deletion stops on failed discovery/child deletion, ignores only confirmed missing resources when suspending Flux, records the active failed step and retains the DB record when it fails. Conversion and regression evidence are tracked in [BORTUS-IMPLEMENTATION.md](BORTUS-IMPLEMENTATION.md).

JSON source reads also throw fixed failures rather than synthesizing empty success. Flux commands share the app's bounded kubectl process pool and deadlines.

Namespace deletion is polled for up to 60 seconds. Only a confirmed 404 proves absence. Timeout ends with an error and retains the inventory record; investigate finalizers manually before retrying. The dashboard no longer attempts the unsupported shell-pipeline finalizer removal or silently force-deletes remaining pods. Bound PV cleanup runs only after namespace absence is confirmed.

GitRepository/Kustomization YAML uses the Kubernetes client's serializer (including proper string quoting), a disposable OS temporary file, and the same bounded structured command wrapper. Zero exit establishes apply success; stdout phrases do not. These generated files contain public repository metadata, never private credential values.

See [API usage](API-USAGE.md) for the full application interface. Dashboard writes require fresh write plus engineAdmin and operate on the connected cluster using the application's credentials. Scoped KV writers have metadata views but no Flux mutation controls.
The `/flux` hierarchy joins source names with Kustomization sourceRef and
HelmRelease chart sourceRef; the active root is branconet-charts and its existing
bundle is migration-releases. Repository/bundle detail and Sync show actual
readiness, events, resources and revisions. Native credentials live in flux-system;
BORTUS's namespace Secret role remains the existing get/list/create/update Role,
separate from dashboard Flux RBAC. No cluster-admin role is added. No DB credential
replay, SOPS or value-bearing Secret resource enters Git.

Use the dashboard Sync operation or the CLI to request reconciliation. Normal
rollback is a chart revert through CI. For source failure, suspend the existing
Kustomization, pin the source to a recorded successful commit, then reconcile and
resume. To undo the repository switch, restore the retained old source and
original path without recreating releases or storage. Exact commands, source
pinning, ownership and bootstrap prerequisites are in the
[charts operations guide](https://github.com/jtmb/branconet-charts/blob/main/docs/OPERATIONS.md).
Host/CNI/storage disaster bootstrap remains independent; recover data and native
credentials before Flux activation. Final Swarm/Gluster retirement is separate.

New private-repository credentials are created as native Secrets in `flux-system` using verified API request bodies. Configure the namespace allowlist and RBAC accordingly. `GitRepo.authData` stays empty; old SQLite credentials are never replayed. Existing native Secret collisions fail instead of overwriting imported credentials.

Keep value-bearing native Secret resources out of Git. Manifests should reference credentials created independently. Bootstrap and recovery credentials must remain available outside the cluster being created. See [deployment contract](BORTUS-DEPLOYMENT.md).
API endpoint/auth contracts remain documented in [API usage](API-USAGE.md);
private credential behavior is in [deployment](BORTUS-DEPLOYMENT.md).
