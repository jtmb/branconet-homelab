# BORTUS workflow guide

For an unadopted native key on Secrets, select metadata, optionally reveal, then enter a replacement or choose Intentionally save an empty value. Save remains disabled for untouched selection/reveal. Clear display and draft erases the local editor without a native request. Delete selected key opens an exact namespace/Secret/key confirmation; cancelling sends no delete. Stale versions fail and require refresh/reselection before an explicit retry. Adopted keys still require versioned KV mutations. These editor changes passed local TLS/browser qualification; see [editor evidence](implementation-evidence/secret-intent.json).

The application lives at `k8s-rewrite/front-end/`; its documentation lives at repo-root `docs/`. This main-branch publication includes the dashboard and application runtime. Existing Swarm sources remain in place. Kubernetes charts, provisioning roles and Flux source changes are separate deployment work.

## Local setup

1. Enter `k8s-rewrite/front-end` and run `npm ci`.
2. Configure an untracked `.env` from `.env.example` using independently supplied signing/lookup credentials and a SQLite `DATABASE_URL`. Keep signing material stable across restarts.
3. Supply operator `KUBECONFIG` or `~/.kube/config`, `BORTUS_SECRET_NAMESPACES` and optional metadata-only aliases via `BORTUS_SECRET_ALIASES_FILE`.
4. Run `npm run db:deploy`, then `npm run dev`. Open `http://localhost:4000` and register the first user, which receives write role, engine administration and the initial KV grant.
5. Check cluster resources and native Secret metadata. Import native values externally before enabling their consumers. See [deployment contract](BORTUS-DEPLOYMENT.md).

For an existing database, make a consistent backup and assess migration history before deployment. Never reset a production database to make migrations pass.

## Configuration and Secrets

Static rotation APIs passed local qualification; KV UI remains pending. Prepare one exact existing field and a same-namespace Deployment/StatefulSet/DaemonSet; generate once with displayed native head/RV and metadata revision. Changing the stored string does not rotate an external credential or prove a consumer used it. Inspect ambiguous operations before further action. Consumer acknowledgement records an explicit assertion; optional named reload is administrator-only and may reconcile back under Flux. No automatic workload restart occurs.

Use Previous aliases / Next aliases on the Secrets screen to browse all references. Native and alias metadata load independently; refresh failures are shown beside the affected source. Alias page navigation does not reload the native Secret list. This browser behavior passed local readonly/mobile checks with 603 synthetic aliases and an unavailable native endpoint.

Alias metadata bounds passed local unit and production HTTP/TLS qualification. Follow nextCursor to inspect all 100-reference pages; current-namespace metadata excludes history. Register strict four-field mappings through the API for immediate cache invalidation, or update the bounded metadata file and allow up to ten seconds for refresh. Readiness coalesces metadata-only dependency probes and does not establish write/admission acceptance.

History cleanup APIs passed local unit and production HTTP/TLS qualification. Select committed versions and confirm the exact path; first tombstone any active head being destroyed. Inspect reference-commit and per-history cleanup outcomes separately. For orphan GC, an administrator previews one path, reviews candidates older than 24 hours, and submits the current source head/RV/path revision plus candidate UID/RV. Changed ownership/references or unavailable sources retain history; no background sweep runs.

The v1 import/export API workflow passed local unit and production HTTP/TLS qualification. Choose explicit paths/versions and acknowledge that export contains credential values. Review metadata-only import plans, then submit the same bounded bundle with current path revision/head/RV and explicit overwrite choices; inspect every per-path outcome before retrying. New native initialization needs an administrator, while already-imported native objects require explicit adoption first. No group destination is inferred from an alias. Full transfer UI remains pending.

Flux repository removal keeps its native authentication Secret. The progress view reports retained credentials; inspect exact references/consumers before explicit native key or KV version cleanup. Repository names never establish Secret ownership, and cascade removal does not require a canonical Secret delete permission.

Use **Configuration** (`/configuration`) for nonsecret SQLite settings. Use **Secrets** (`/secrets`) for native Secret metadata and, as an effective engine administrator, explicit reveal and key CRUD. Create refuses existing keys; update/delete require the current resourceVersion. Unrelated keys, type and metadata are preserved. Deleting the last Opaque key retains an empty Secret object.

User, configuration and settings screens share metadata/session queries with explicit failed-read states and Retry. User/configuration tables render at most 100 rows per page with typed date/text sorting and keyboard actions. Editors are labelled focus-trapped dialogs; deletion requires an exact username or configuration key. Fresh engine administration, valid/changed input and one pending request gate saves. Mutation requests have a 20-second deadline, abort on unmount and never automatically retry an ambiguous outcome. Passwords retain intentional whitespace and leave the UI when an editor closes or write access ends. Configuration edits preserve the existing key/ID.

Settings distinguishes effective registration status from the persisted application switch: ALLOW_REGISTRATION=true can keep it open when the switch is off. PV policy editing applies one explicit Retain/Delete choice after exact-volume confirmation; failures remain visible. The former default-policy Save was a delay without persistence or a consuming creation flow and has been removed. New PV defaults come from StorageClass configuration; no successful save is simulated. Viewport width is a browser preference available to both roles.

Flux cascade deletion now stops on command/discovery errors and retains its DB inventory record until cleanup succeeds. A namespace that remains after 60 seconds requires manual finalizer investigation; the dashboard does not automatically strip finalizers. See [Flux integration](FLUX-GITOPS.md).

Register exact alias/namespace/name/key mappings using `/api/secret-references` or the alias JSON file. Underscores and path-style aliases are not parsed into destinations. Bearer lookup returns mapped native values or nonsecret configuration; legacy sensitive SQLite rows are excluded, including during outages.

See [API usage](API-USAGE.md), [Secrets engine](SECRETS-ENGINE.md) and [permissions](USER-PERMS.md). Protect browser and Bearer traffic with TLS outside loopback development.

## Provisioning integration

Container provisioning is disabled. Provision or recover a cluster from an independent operator environment with independently available credentials. The optional local dashboard runner expects Ansible and a separately supplied sibling tree at `k8s-rewrite/ansible-playbook/`, including `playbooks/` and `inventory/production.ini`. That Kubernetes provisioning tree is not supplied by this application-only merge.

`POST /api/vars/sync` generates lookup expressions and inventory for that optional tree. It never generates Secret values. Local runner inputs are `ANSIBLE_BECOME_PASSWORD`, `ANSIBLE_PRIVATE_KEY_FILE`, `ANSIBLE_REMOTE_USER`, `BOTRUS_API_URL` and `BOTRUS_SECRETS_KEY`. Bootstrap must work while the target cluster is unavailable. Use sensitive task `no_log` handling in the external playbooks. Dashboard runs accept only site.yml and the supported role selection. New job output uses a fixed stdout callback and retains only lifecycle/role status; ordinary stdout/stderr, task labels, module results and exception text are withheld. Missing callback completion fails explicitly, including on a zero process exit. Local producer/production storage/stream qualification passed; full deployed Linux runner/image acceptance remains separate and historical output is unchanged.

## Cluster and Flux operations

Overview counts now distinguish native Secret object metadata from SQLite nonsecret configuration. Failed independent sources show unavailable counts, not zeros. Clearing dashboard inventory requires effective engine administration and exact confirmation, describes the SQLite records removed and refetches live data; it does not describe live resource removal or a cluster being undeployed.

Nodes displays live cluster state and SQLite inventory in separate sections. Inventory remains accessible during cluster outages and is not promoted to live status. Inventory changes validate names/IPs/roles, expose saving/errors and require confirmation for deletion. Editing by record ID avoids creating a second record when its hostname changes.

Pods, Deployments, Namespaces, Services, Ingresses and Storage now use shared metadata queries and paginated tables (100 rows/page). Search/sort/filter changes reset the page. Pod type/namespace/label filters are applied by the server; labels submit explicitly. Storage distinguishes persistent volumes from actual PVCs and offers exact claim detail links. Empty results are shown only for a successful snapshot; failed requests retain and label previous data or show unavailable state.

The dashboard lists nodes, namespaces, pods, deployments, services, ingresses and storage using externally supplied Kubernetes credentials. Database node records describe inventory; creating a record does not provision a machine or join it to Kubernetes.

New Flux repository locations must be credential-free HTTPS/SSH URLs or SSH SCP spelling; enter private authentication separately. Userinfo/passwords, query strings and fragments are rejected before side effects. Existing unsafe locations are withheld from the dashboard without rewriting stored resources. Detail views explain that controller messages and annotations are withheld, preserve structured readiness, and link only safe HTTPS URLs. Inspect raw controller diagnostics in the independent operator environment.

Cluster APIs now expose per-resource availability and labelled retained snapshots, fail unavailable primary reads with 503, and keep node inventory separate from live status. Browser availability presentation is being updated under A06/A11; see the implementation ledger for current acceptance.

The **Flux** view reflects installed Flux resources. The production source is the separate private `jtmb/branconet-charts` repository: main pushes pass validation before CI promotes their exact SHA to validated. The existing migration-releases Kustomization uses source branconet-charts and path ./flux/releases. BORTUS's package is charts/bortus, with release overrides in flux/releases/bortus.yaml. Application source pushes do not rebuild or redeploy the running image. See [Flux guide](FLUX-GITOPS.md), its reviewed image-release procedure and [connection guide](CONNECTING-TO-A-CLUSTER.md).

The engine-administrator terminal executes shell commands with the application's operating-system permissions as well as its Kubernetes permissions. Treat effective engine administrators as trusted operators with application-host access; scoped writers have no terminal/infrastructure authority.

The separate pod-exec handler runs scripts inside the selected pod/container via structured kubectl argv. Runtime session capabilities expose provisioning/operator-shell/pod-exec gates; Windows has no operator host shell, and both shell modes can be disabled by their documented environment flags. The resource menu hides exec and mutations for unknown/readonly/scoped-writer sessions and offers only implemented operations. Node drain and resource deletion require exact-name confirmation. Drain respects PDB/local-data/unmanaged-pod refusal, and a timeout may leave partial effects that must be inspected. Successful mutations refetch subscribed cluster metadata; YAML/log dialogs load only when opened.

## Validation

Provisioning uses the shared fresh session/runtime capability and metadata-only job history. Container/unsupported runtimes show independent-operator guidance instead of Run controls. Only effective engine administrators can read captured provisioning output; other accounts see job metadata. Authorized job output is loaded explicitly into a bounded text tail, with cursor-based streaming, hidden-page close/resume, explicit error/retry and unmount cleanup. Completed job deletion and provisioning/cancellation use accessible confirmations with failures inside the focused dialog. Cancellation reports a request rather than claiming completion, and refuses an unowned process. Local unit/HTTP/browser completion/unmount/role/mobile checks passed; browser visibility transitions and real runner/image performance remain separately bounded acceptance.

Keyboard focus is visible on interactive controls. Resource menus use keyboard-aware dropdowns; dialogs expose titles/descriptions, trap focus and return it to their trigger. Logs render as a bounded text snapshot, and YAML syntax tooling is removed from initial route imports. Resource keyboard/mobile/browser and observed-script comparisons passed locally; see [evidence and limits](implementation-evidence/README.md). Other screens, actual zoom and screen-reader/performance checks remain pending.

Deployment details now show desired/observed controller state, including paused/reconciling/scaled-down state and generation. Pod membership follows controller UIDs. Desired replicas use an explicit bounded form; runtime edits may be reconciled back by Flux.

Resource detail pages subscribe to the same metadata query lifecycle. A failed read shows unavailable state rather than claiming the resource was deleted; only a fresh 404 is shown as Not Found. Retained/partial/stale responses remain labelled, and menu mutations invalidate active detail/list subscriptions.

Small viewports use a 56-pixel navigation rail with named resource links; desktop navigation can expand/collapse. Comfortable content width applies only on large viewports. Resource screens fit 320/390/768 CSS-width checks, with local table scrolling; remaining-screen and actual zoom acceptance is pending.

YAML, log and resource confirmation dialogs use accessible modal primitives. YAML sessions reset for each resource/mode; readOnly remains authoritative, Save requires an available callback and changed content, and closing a dirty editor requires an explicit discard. Editor drafts are not persisted. Keyboard dirty/discard/read-only reopening and focus trap/return passed in the synthetic browser fixture.

Run `npm test`, `npm run typecheck`, `npm run build`, then `npm run test:integration`. The HTTP integration suite requires the production build and uses temporary SQLite, fake credentials and a loopback unavailable Kubernetes endpoint. It does not access the operator database or live cluster.

Image and live-cluster evidence are separate from those local checks. See [recorded evidence and runtime contract](BORTUS-DEPLOYMENT.md).

The [2026-10-10 performance/correctness/UI audit](BORTUS-AUDIT.md) records the main-source baseline, reproduced account/CLI/UI bugs, local cache measurements and a staged implementation plan. Its [evidence bundle](audit-evidence/README.md) includes a disposable Windows fixture and screenshots. These checks do not establish deployed-image performance. The current lint command uses checked-in flat configuration and direct ESLint with warnings treated as failures; the app-only Node 22 quality workflow runs install/lint/build/type/unit/HTTP checks without deployment credentials. See the implementation ledger for current acceptance rather than treating a workflow definition as a successful CI run.

Follow the [implementation ledger](BORTUS-IMPLEMENTATION.md) for remediation status; the audit remains historical evidence. The account migration is forward-only and needs a consistent DB backup before deployment. Password reset invalidates the user's cookies; self-reset requires signing in again. Flux-owned workload screens will show source/ownership/reconciliation status as implementation progresses. Ad-hoc runtime edits must not be described as persistent Git desired-state changes; charts-repository integration is coordinated separately.

Legacy access changes require fresh engine administration, an exact paginated alias-impact preview and acknowledgement before commit. Re-preview after a changed alias/mapping/grant/policy/principal/path/mount revision or mount namespace scope. Principal disable blocks nonsecret legacy configuration lookup too; bootstrap credentials must stay independent. Exact grant revocation does not change native values or the external lookup key. These APIs passed [local unit and production HTTP/TLS qualification](implementation-evidence/kv-legacy-access.json); the full KV interface/final image/live acceptance is pending.
