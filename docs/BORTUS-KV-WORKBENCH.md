# BORTUS native KV workbench integration

The isolated workbench adds explicit adoption, current and immutable-version reveal, grouped editing, rollback, restore, soft-delete, external-drift capture and protected transfer forms. It is exported from `k8s-rewrite/front-end/src/components/secrets/kv-workbench.tsx` as both `KvWorkbench` and the default export. The existing Secrets screen is not wired by this component-only change; the integration owner connects selected path metadata and completes combined UI/native qualification.

## Props and lifecycle

```tsx
<KvWorkbench
  path={selectedPath}
  capabilities={freshCapabilities ?? null}
  onClose={() => setSelectedPath(undefined)}
  onMetadataRefresh={refreshPathMetadata}
  returnFocus={() => pathTrigger.current?.focus()}
/>
```

`path` contains `id`, `mountId`, `path`, `namespace`, `name`, `revision` and an explicit `fields: [{field,key}]` array. The structural types `KvSelectedPath` and `KvCapabilities` are exported. Capabilities are the result of `GET /api/kv/paths/[id]/capabilities`, including `pathId`, `revision`, `permissions`, `nativeMutationEnabled` and `initializationAllowed`. Supply the fresh selected-path result or null, never inferred role capabilities. `onMetadataRefresh` receives no values; it invalidates parent metadata only. Mount the dialog only while the path is selected. `returnFocus` restores its selection trigger on close.

The component uses the existing fresh session subscription and independently refreshes path capabilities every ten seconds. Failed or older-than-15-second capabilities pause value controls. Readonly remains metadata-only. Initial browsing reads only capability/status metadata; adoption preview, values, version values and transfer are explicit actions. Explicit history browsing lists metadata. Ordinary grouped editing requires read policy to preserve current siblings. A writer with update but denied read receives a distinct complete-replacement form; it never requests current/history values.

Path/target/mapping changes unmount and fence the prior state. Close, cancellation, clear, session-ended events, role withdrawal and capability changes abort requests and clear revealed values, original edit values, drafts and import bundles. Late responses cannot repopulate those forms. Display/draft clearing cannot undo a sent native mutation; inspect metadata and operation outcome before another mutation. Values never enter shared query/cache stores or browser persistence. Error rendering suppresses arbitrary server body text and retains only status, fixed outcome and validated operation IDs.

Each native action captures `{resourceVersion,expectedHead,pathRevision}` when its form opens. Background metadata refresh never upgrades that capture. Metadata changes pause the open action; conflicts discard its draft and require a new explicit action. Positive `pathRevision` support in strict human native prerequisites is an integration prerequisite assigned to the app owner; this branch deliberately does not edit shared schemas/routes. Existing API-only integration checks therefore do not prove the new component's revision-bearing requests work against its unmodified base.

## User actions

- Adoption preview shows exact native keys and paged legacy aliases. Exact logical-path entry plus explicit acknowledgement commits version 1 while preserving original bytes and unrelated native keys/type/metadata.
- Current/version reveal displays UTF-8 or base64 as returned by native routes. Empty bytes have an explicit label. Values remain only in the transient form.
- Grouped editing loads current fields deliberately and captures their native revision. Unchecked fields are explicit removals. Unchanged documents cannot be saved; introducing/clearing an empty value requires the per-field empty acknowledgement. Switching encoding preserves bytes or fails when binary cannot decode as UTF-8. Existing empty/binary siblings remain intact.
- Write-without-read replacement uses only field mappings and native status, with captured head/resourceVersion/pathRevision. Each mapped field starts included and blank; enter its replacement, explicitly acknowledge empty bytes, or uncheck it to remove it. Exact-path entry and complete-replacement acknowledgement are required. No unknown current managed value is presumed retained; unrelated canonical Secret keys/type/metadata remain preserved by the native engine. Unchanged intent is disabled, stale CAS fails without retry and permission withdrawal discards the form.
- Rollback and restore select a retained immutable version and create a new head. Soft-delete removes managed current fields with an exact-path confirmation while preserving object/history. Drift capture is a separate confirmed reconcile operation. Operation IDs can be inspected explicitly; mutations never retry automatically.
- Import accepts bounded BORTUS v1 JSON in memory. Server preview displays only target/mapping/revision/head metadata, clears the visible JSON input and requires each existing target's overwrite acknowledgement plus batch credential/new-version consent. Ready plans retain their captured identities. Refused previews require a fresh corrected preview. Independent commit outcomes show every document, including partial success/refusal and operation IDs. Original imported objects require separate adoption.
- Export requires export policy, exact path and explicit credential acknowledgement for current or selected historical fields. Its temporary Blob URL is revoked after download; the deliberately downloaded file remains credential-bearing and must be protected by the operator.

The accessible Zinc/Indigo dialog uses the shared Radix focus trap and Escape handling. Inline cancellation returns focus to the stable Refresh metadata button; outer close returns the selection trigger. History, adoption aliases, import plans and outcomes show at most 20 rows per page. Documents retain the API's 64-field limit. Horizontal table overflow remains inside its container at 320/390/768 CSS pixels. Permanent destruction/GC and rotation administration stay with the separately owned administration workflow.

## Qualification and integration boundary

The helper tests are `tests/kv-workbench.test.ts`; the isolated browser harness is `tests/kv-workbench.browser.mjs` with its exclusive `kv-workbench-browser-entry.tsx`. Run the browser harness from `front-end` with the absolute Playwright package path and optionally an installed browser executable. It bundles the real component with esbuild/Tailwind into an owned temporary directory, uses an ephemeral loopback `listen(0)` port, intercepts synthetic API responses, and writes metadata-only evidence/screenshots under `docs/implementation-evidence/kv-workbench-*`. It does not mount any kubeconfig or use a database. No browser dependency/package manifest changes are needed.

Local checks: 120/120 unit tests (seven new workbench tests), production build, zero-warning lint, typecheck and all three production HTTP integration fixtures pass on Windows/Node 24.18.0. HTTP fixtures use temporary SQLite, fake credentials/CLI and CA-verified loopback native APIs with dynamic ports. The new standalone browser results are in [browser evidence](implementation-evidence/kv-workbench-browser.json), including zero-read complete replacement, an RV change after the form captured its revision, and permission withdrawal before submission. Recorded initial failures are in [attempt ledger](implementation-evidence/kv-workbench-attempts.json). Screenshots contain metadata only.

Combined selection/navigation, the owner's human `pathRevision` schema fix, production Node 22/Linux image, actual Kubernetes guard/admission/RBAC and final live acceptance remain with the integration owner. This work adds no runtime environment, schema migration, native verbs, deployment or production changes. It provides BORTUS KV flows, without claiming dynamic issuers, PKI, transit or HashiCorp API compatibility.
