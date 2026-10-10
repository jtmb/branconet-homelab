# BORTUS KV administration component

`k8s-rewrite/front-end/src/components/secrets/kv-administration.tsx` exports both `KvAdministration` and a default export. This is a standalone client component for integration by the Secrets-screen owner. It does not change the current page, workbench, shared authentication/query implementation, API, schema, chart or Dockerfile. Local synthetic qualification is recorded in [the administration evidence](implementation-evidence/kv-administration-ui.json). Final integrated-screen, Linux image and live acceptance remain separate.

## Integration contract

```tsx
import { KvAdministration } from "@/components/secrets/kv-administration";

<KvAdministration
  selectedPathId={selectedRegisteredPathId}
  refreshKey={externalMetadataRevision}
  active={secretsScreenActive}
  onMetadataChange={(scope) => refreshOtherMetadataViews(scope)}
/>
```

`selectedPathId` is an optional exact registered path UUID. Changing it remounts all panel state; no alias/native-name inference occurs. Without one, native and legacy grant views accept an explicitly entered UUID. `refreshKey` is an optional string/number: bump it when **external** metadata or permission changes invalidate this component's snapshots. `active` defaults true; setting it false unmounts the workspace and clears sensitive state. Unmount the component on screen close/logout. The shared fresh `useSession` gate and Next 15 `usePathname` also fence session/route changes.

`onMetadataChange(scope)` receives only one of `policies`, `identities`, `legacy`, `paths`, `history`, `rotations`, `recovery`. It runs after a confirmed response and never receives a value, token, body or digest. Refresh other views/capabilities in that callback. The component refreshes its own successful list changes internally; **do not immediately bump its own refreshKey from an identity-issue callback**, because doing so deliberately clears the one-time token before the operator can save it. Closing, changing tabs/paths, navigation, page hiding, logout/session loss and external refresh all discard local state and abort/fence late replies. A cancelled browser request never proves a sent server mutation did not commit.

The broad `secrets/` ignore rule in `k8s-rewrite/.gitignore` also matches this source directory. These two reviewed source files are explicitly tracked; adding new helpers there requires adding the exact source paths, not force-adding a whole Secrets directory.

## Views and request behavior

The default closed panel performs no KV fetch. Opening selects policies for a fresh effective human administrator, otherwise a policy-filtered audit view. Management controls require a fresh authenticated write role plus engineAdmin. This component intentionally offers only audit to readonly/scoped human users; owner-token and scoped native operations supported by the API remain available to the separate workbench/API, rather than implying this panel grants them administration. KV Bearer tokens cannot authenticate the human session gate.

Every explicit operation uses an ephemeral request scope with pre/post fresh session checks, a 45-second total deadline, a one-MiB response ceiling and no-store fetches. There is no automatic mutation retry. Server/transport text is never reflected into errors; only fixed local/status messages and validated operation IDs/outcome names are retained. Controls freeze during a pending action. KV administration responses and one-time tokens never enter shared queries, local/session storage, URLs, callbacks or console logs. Tokens appear in a read-only local textarea once and have an explicit Clear display control; there is no clipboard write or credential download.

Policy, identity, grant, audit and rotation lists render at most 100 rows. Cursor navigation retains at most 100 previous cursors; long audit histories remain forward-reachable. Legacy impact previews retain only the complete bounded alias-name set (up to the existing 10,000 catalog limit), while showing the current 100-row page. Native versions/candidate selections retain the server's 100-item bound. Tables scroll horizontally inside the panel on narrow screens.

| View | Actual route contract and confirmations |
|---|---|
| Scoped allow/deny policies | Paged GET `/api/kv/policies`; POST `/api/kv/policies/preview` precedes create/update/delete. Captured rule ID/revision for edits/removal; explicit principal, mount/all-mount scope, full-segment prefix and actions. Any legacy-involving rule change requires every preview page, exact fingerprint/aliases and separate config acknowledgment when reported. Input changes or failed requests invalidate confirmations. Deny remains authoritative for native data actions. |
| Automation identities | Paged metadata GET, explicit owner ID, 1–32 mount/prefix/action scopes and expiry within 30 days; local datetime plus explicit 1-hour/1-day/7-day/30-day presets. POST returns a credential once. Pre/post session equality prevents a late token display after role/account loss. DELETE confirms captured exact identity ID, owner and expiry; revoked/expired metadata is shown honestly. Owner role/session/policy intersection remains a server check on every token use. |
| Audit | GET `/api/kv/audit` with the only supported filters: exact pathId, operationId and cursor. Fixed whitelisted metadata cells only. An empty filtered page can still have a next cursor. `authorized` records a decision, not value delivery. |
| Legacy lookup | Principal state, paged exact grants, principal enable/disable, grant/restore and revoke. Preview captures principal/path/mount revisions and complete aliases; commit repeats fingerprint and aliases, with a separate nonsecret-config acknowledgment for principal changes. No lookup key is copied or issued. |
| History and recovery | Captures path, capabilities, native status and version metadata without calling value endpoints. Retention PATCH uses path revision and limit 1–100, with the lower operator-configured maximum enforced by the server. Destroy requires selected committed versions and exact captured path/namespace/name/path revision/head/RV text; active-head selection is disabled until tombstoned. Reference commit and each history deletion are displayed separately, including partial/recovery-required cleanup. GC requires explicit preview, displayed 24-hour minimum age, exact selected candidate names/UIDs/RVs and captured source/path prerequisites. Operation inspection confirms an exact operation ID, renders only its metadata, and leaves absent native proof ambiguous. |
| Static rotation | Declares an exact mapped field and same-namespace Deployment/StatefulSet/DaemonSet, then separately prepares, generates once, resolves/cancels eligible intent, requests optional UID/RV-fenced consumer reload, and records a separate consumer-consumption assertion. Rotation ID/revision/state plus source head/RV are captured. No generated replacement value is returned or stored in the UI. A verified template marker is not pod readiness or evidence of consumption; the acknowledgment is explicitly an operator assertion. |

Native changes require both captured action capabilities and guarded mode; metadata retention and supported outcome inspections use their actual non-native gates. The flag is an operator assertion, not evidence of installed admission/RBAC protections. No administration bypass of KV data denies is implemented.

## API limitations for the integration owner

These are source-confirmed boundaries, not invented request fields:

- Identity DELETE has no revision/CAS body. The UI confirms immutable ID/owner/expiry and uses fresh authorization, but cannot claim identity-revision CAS.
- Native status/version list responses omit canonical/history UIDs. Destroy can confirm the exact path, native target, head and RV; source/history UID verification/deletion preconditions remain server-side. GC and consumer previews do expose UIDs and are confirmed explicitly. Full displayed UID confirmations for destroy require a shared API change.
- The strict destroy schema does not accept `pathRevision`, although the native engine supports an optional path revision internally. The UI captures/displays the revision and capabilities but sends only the currently supported head/RV/path/versions body. Across-request path-revision protection for this route requires the shared API owner to extend its schema/tests; no unsupported field is sent.
- Consumer preview spreads marker metadata after its `rotationId` identity field. If a consumer carries a different valid previous rotation marker, that marker can shadow the response identity. The UI refuses mismatched rotation IDs rather than sending a reload against guessed metadata. The shared API owner should return the marker under a separate name.
- A maximum-length 10,000-alias acknowledgment can exceed the existing 512-KiB KV request-body ceiling. The UI never silently omits aliases or partially changes the principal. The server refuses an over-limit request; scalable acknowledgment beyond that envelope is a shared API concern.

## Reproducing local qualification

Use Node 22 and the normal front-end commands: `npm test`, `npm run lint`, `npm run build`, `npm run typecheck`, `npm run test:integration`. The new unit file covers fresh admin gates, capability deny/guard/revision checks, complete legacy/config acknowledgment, exact GC UID/RV bodies, route-schema compatibility, one-time reply fencing, revoked/stale single-send failures, correct browser fetch receiver and explicit timeout outcomes. The new integration fixture exercises the client against the actual production Next routes, temporary SQLite and a CA-verified native mock, including CAS, all 603 aliases, real token issue/revoke, retained partial cleanup, absent-proof recovery and original-key/metadata preservation.

After a production build, run `node node_modules/tsx/dist/cli.mjs tests/kv-administration-ui-fixture.ts` in a terminal with stdin/TTY retained. It prints only its loopback browser URL and synthetic owner/mount/path/operation IDs. The harness bundles the actual component into a temporary page and proxies its API requests to the production Next server with a synthetic cookie. `/__fixture/status` exposes metadata request/write counts only. POST `/__fixture/control` accepts the documented test actions in the helper: role withdrawal/restore/readonly, delayed token, stale policies, rotate deny/allow and the synthetic reload marker setup. No production connection or credential is permitted.

For a controlled partial cleanup, run `tests/kv-administration-cleanup-fault.ts <owned temporary fixture directory>` under tsx. It refuses non-fixture credentials/directories, preserves CA verification and fails exactly one history DELETE without deleting that object. Sending `stop` on stdin restores the fixture kubeconfig and closes the owned proxy. Send `stop` to the UI fixture to close its production child and clean its own temporary directory. Failure records and browser screenshots are retained in the evidence; synthetic passes do not establish real consumer receipt, external guard installation, zoom/screen-reader acceptance, production latency or final-image acceptance.
