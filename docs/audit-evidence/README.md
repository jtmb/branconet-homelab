# BORTUS audit evidence

This bundle accompanies [BORTUS-AUDIT.md](../BORTUS-AUDIT.md), baseline application commit `c2e22caeea096836a8b3992f86c63b11c9eb8dbe`. All resource names/accounts in the evidence are synthetic. No operator credentials or native Secret values are included.

## Files

- `baseline.json`: sanitized original HTTP/subprocess results, local checks, one memory snapshot and UI observations. Timings are Windows/Node 24 with a 50 ms metadata-only fake CLI; not deployed Kubernetes performance.
- `reproduce.mjs`: Windows fixture for the same account races, deleted-account reads, false mutation success, argv injection mechanism, restart attribution, ignored filters, missing routes and healthy/outage cache measurements. It reports observations; it deliberately does not assert the old buggy outcomes as desired acceptance criteria.
- `pods-numeric-sort.jpg`: ascending restarts shows 12, 2, 7.
- `mobile-expanded.jpg`: 390×844 viewport, 224 px expanded sidebar.
- `readonly-actions.jpg`: readonly identity offered operator actions; server permission gates still apply.
- `yaml-view-retains-edit.jpg`: View YAML reopens with retained editor state/Save after an unsaved edit was closed.

## Repeat the local HTTP fixture

Use a credential-free disposable checkout on Windows with Node/npm dependencies already installed and the standard Windows .NET Framework C# compiler at `C:/Windows/Microsoft.NET/Framework64/v4.0.30319/csc.exe`. It compiles a tiny fake executable locally; it downloads nothing. Run from `k8s-rewrite/front-end/`:

```powershell
npm run build
node ../../docs/audit-evidence/reproduce.mjs
```

The fixture refuses occupied loopback ports 4206–4208 before starting. It uses a new temporary SQLite DB, random signing/lookup material held in memory, a synthetic kubeconfig targeting unavailable `https://127.0.0.1:1`, provisioning disabled and a fake kubectl placed first in the child PATH. It passes only basic OS environment inputs plus these fixture overrides to the server. Fake kubectl returns metadata fixtures, records resource names/counts, sleeps 50 ms, and returns exit 1 for all mutations. Account changes affect only the temporary DB.

The fixture writes sanitized observations to ignored `front-end/tmp/audit-reproduction-results.json`, then stops its server and removes its temporary database/config/executable directory. It reads the current Git commit into its result; when reproducing on a changed branch, record the application changes and expect fixed behaviors to differ. Concurrent races may need repeated runs to observe interleavings; latency samples will vary by host.

`baseline.json` records the original run. A separate `reproduction.json` records a final execution of the packaged harness; its timing differences are expected. Unit/native TLS/build/HTTP integration command results are separate from this fixture.

## Repeat the UI observations

```powershell
node ../../docs/audit-evidence/reproduce.mjs --ui
```

After the HTTP cases, the fixture leaves local gateways open at `http://127.0.0.1:4207` (write identity) and `http://127.0.0.1:4208` (readonly identity). They internally inject synthetic cookies and allow GET only, so browser UI mutations are blocked. No credentials need to be entered. The gateways serve the production build's static assets, including decoded dynamic-route paths. Stop with Ctrl+C; the fixture closes its gateways/server and removes temporary state. Result/ready JSON files under ignored `tmp/` contain no tokens/passwords.

1. Open `/pods`; click Restarts until ascending. Observe 12, 2, 7 at the baseline.
2. Set viewport to 390×844 and inspect sidebar/content width. Collapse the sidebar and inspect the accessible names of its 13 links.
3. As readonly, open `/pods/apps/api-worker-rs-0`, then Resource actions. Observe Execute Shell/Edit YAML/Delete.
4. Choose Edit YAML, then Edit; close without saving. Reopen View YAML. Observe editable textarea/Save at the baseline. Do not submit mutations.
5. Open `/secrets` to observe the explicit unavailable native-backend message. Native CRUD/empty-value/delete intent was source-reviewed; no native mutation was performed.

Gateway fixture transport/asset behavior is not production application evidence. The original encoded dynamic-route chunk issue was fixed in the packaged gateway; standalone public-asset setup issues were excluded from findings. No real-cluster or full screen-reader checks are included.
