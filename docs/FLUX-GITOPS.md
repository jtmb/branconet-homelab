# BORTUS and the homelab Flux pipeline

The three Flux list calls now use `get <resource> --all-namespaces`. On committed `ab7c6867f20af434aed704d1644e8b08267eda0a` (frontend `da4ed3bd2282424c1f40009678db8374b83ac73d`), a fresh original four-phase Linux build passes342 unit tests and eight HTTP integrations, including the three strengthened assertions in the existing Flux parent. The separate real matching Kubernetes v1.37.1/patched-kubectl fixture passes45 additional finite cases with44 exact app argv records, covering the corrected hierarchy without replaying the earlier44 cases. The existing strengthened unit assertions cover both cascade discovery orderings. All327 public actor records/four source files,384 raw files/5383 compiled objects/40635 installed objects,57 original plus11 observer/query host identities and all five container IDs/names are independently closed/current; own/fresh checks pass. ROOT qualifies the original A04 command boundary by the reviewed43-route/50-method family enumeration plus existing instrumented unit/HTTP coverage and both real-API fixtures; this is not50 new real handler tests or an exhaustive cascade-branch claim. The original validation text and historical failed attempts/false runtime acceptance flags remain unchanged. This qualifies the reviewed source boundary, with delivered/live acceptance, Flux controller reconciliation, positive kubelet services and deployment separate. See [ROOT composite qualification](implementation-evidence/a04-command-boundary-composite-root-20261015.json) and [fresh functional qualification](implementation-evidence/flux-fixed-functional-root-20261015.json).

The current Flux/focus source passed a fresh Node22 production build,170/170 units (23.90s), zero-warning lint, typecheck and four production HTTP suites (34.63s). Nine actual Chrome checks passed, including unchanged physical max-one read ownership, real hidden/deletion monitoring, fresh withdrawal, delayed-reply fencing, complete typed201-row pages and320/390/768 fit. The pinned readonly Flux axe4.14.0 scan returned20 rule passes, zero violations and zero incomplete findings; this is scoped automation, not complete assistive-technology acceptance. Real200% browser zoom passed three separate Chromium checks using tabs.setZoom/getZoom, unchanged1000x900 window geometry and CSS984-to492 reflow. Dialog bounds/keyboard bottom-action reachability/focus return and100-row child-local overflow passed. The saved Playwright zoom screenshots capture only492x374 physical pixels and clip the enlarged surface; they cannot independently establish full visual fit. Actual geometry and keyboard evidence are separate. See [scoped qualification](implementation-evidence/flux-stage-qualification.json). Original focused, five regular-browser and two zoom failures remain retained; no performance, final-image or live gate is passed here.

The hierarchy/child/progress UI uses completion-scheduled public metadata queries with explicit unavailable/Retry and labelled prior data. Focus shares an active fresh read; idle visible focus refreshes, while explicit mutation/refetch invalidation still aborts and fences old generations. Hidden pages abort/pause and discard private forms/owners. Public removal references survive hiding and resume progress without another DELETE; dismissal stops monitoring and fences acknowledgements without claiming server cancellation. Completed progress remains until closed. Add/sync/remove have one explicit bounded20-second client owner and no automatic retry. Exact-name removal disclosures and fresh server administrator gates remain authoritative.

The locally qualified static rotation workflow can explicitly request a named same-namespace Deployment/StatefulSet/DaemonSet template reload for an effective administrator with rotate policy. It patches only the pod-template rotation marker with UID/RV conditions, never edits Git, and reports requested/ambiguous outcomes separately from consumption. Flux may reconcile that marker back; operators must coordinate reload and external credential validity. No automatic restart or cluster-wide reload occurs. This workflow passed local unit and production HTTP/fake-CLI qualification; real Flux/controller acceptance remains pending.

BORTUS K8s Manager displays and manages the Flux resources in the connected
cluster. Application code remains in `jtmb/branconet-homelab`; the private
[branconet-charts repository](https://github.com/jtmb/branconet-charts) owns all 33
live application charts, their values and Flux foundation configuration.

## Production contract

Direct Flux list reads validate complete object arrays (at most 10,000 objects) and absent/empty continuation plus absent/zero remaining-item metadata before redaction. Malformed/partial replies return fixed 502 without truncation or producer text. Normal successful empty discovery remains valid, and general CLI output stays at two MiB; the Pod-only eight-MiB collection exception is not reused. Completeness regressions and actual HTTP cases passed in the scoped combined qualification.

Hierarchy discovery now propagates HelmRelease-list failures instead of replacing them with empty children. A missing/denied/unavailable Flux source read returns a typed failure, allowing the client to label retained metadata rather than present an incomplete successful tree. No synthetic empty child inventory is substituted. Actual HTTP and browser failure/recovery qualification passed locally.

Repository rows bound long URL/branch/path metadata within their flexible description and truncate names; the redundant kind badge is hidden on narrow screens. Child tables keep horizontal overflow in labelled keyboard-focusable local scroll areas. Actual320/390/768 long-metadata fit and real200% geometry/keyboard reflow passed locally; screenshot limits are recorded above.

Hierarchy and child sorting use the existing typed comparator: unknown/invalid dates and missing revisions stay last in both directions, with stable name/identity ties. Actual mixed null/valid/equal timestamps passed both sort directions with unknowns last.

Reconciliation now accepts installed CRD-only roots as well as stored repository IDs. The browser supplies explicit name and namespace query fields; the server requires `flux-system`, validates the name, reads the current GitRepository UID/resourceVersion and matches the `gr-UID` hierarchy identity before invoking structured `kubectl annotate --resource-version=...`. Stale/recreated identity returns 409 and no annotation; failed reads/commands remain typed failures. Stored-ID calls remain compatible and a supplied mismatched name is refused. No resource adoption, child mutation, Git edit or credential change is performed. The resource-version option is documented by [kubectl annotate](https://kubernetes.io/docs/reference/kubectl/generated/kubectl_annotate/). Local regression/HTTP/browser qualification passed; real controller acceptance remains pending.

Public removal IDs/start times survive page hiding and permission changes while private forms and client mutation owners are disposed. On return, fresh progress monitoring resumes and another removal remains disabled. If a delete reply was interrupted before acceptance, the exact server progress-key contract is checked without retaining credentials or replaying a mutation. Missing/expired progress (completed-entry cleanup or server restart) is ambiguous and requires resource/inventory inspection before explicit retry. The server rejects a duplicate removal whose same progress key is still active with 409 before starting another cascade. Five-minute cleanup intervals retain active entries and remove only completed records, so a long cascade cannot lose its admission guard through that timer. Genuine hidden-mid-deletion, active retention and interrupted-reply/dismissal qualification passed locally.

Repository and bundle details now share the same visibility/abort/freshness-aware metadata query. Only HTTP 404 establishes current absence; network/503 errors show unavailable/Retry or a labelled retained snapshot. Route keys isolate navigation state and links disable speculative prefetch. Bundles, inventory, conditions, labels and events use searchable 100-row pages, typed numeric/date sorting, semantic table headers and keyboard links for supported resource destinations. Inventory is bounded across all kinds in one table, with kind search/sort retaining that organization. Messages/annotations remain withheld. Complete child/inventory pages and keyboard navigation passed actual-route qualification alongside the hierarchy.

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
