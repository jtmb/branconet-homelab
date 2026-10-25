# System Report qualification

Integration base: public `c53f4c724cf4733e9e58095e7ba6889cc3bd5719` on `codex/bortus-parent-stat-a15-evaluation`. The feature does not modify package.json, the lockfile, owner test runners/planners or frozen controls. That base has no System Report modules or routes; this is an added capability, not a claimed correction to inherited test failures.

## Local checks

| Check | Result and scope |
| --- | --- |
| Focused behavioral tests | 18 pass: 16 inventory/scanner/job/process controls and two database-update controls |
| Production HTTP integration | Passes fresh authentication, operator/scoped-writer authorization, readonly access, session revocation, digest deduplication/cache, concurrent starts, exact-job cancellation and redacted errors |
| Full lint | ESLint passes with zero warnings |
| Types | Full nonincremental TypeScript check passes |
| Production application build | Next 15.5.28 with Node 22.23.3 on Windows passes; the existing portable native fallback applies |
| Linux scanner provisioning | The repository provisioner verifies the official archive, database manifest and layer, then extracts the pinned Linux/amd64 scanner and advisory database |
| Actual CVE matching | Source-linked adapters pass on Windows and Linux/amd64 against the same pinned public Alpine image |
| Database update proposal | Official registry metadata proposal succeeds without changing the repository lock |

The focused controls cover immutable image identity, controller UID/namespace and Service mapping, running init/ephemeral consumers, unknown coverage, advisory-link safety, freshness, database cache invalidation, repeated starts, deadlines, actual child-process cancellation/output limits and environment scrubbing. Database proposals preserve binary pins and refuse alternate repositories, malformed manifests and oversized inputs.

HTTP tests use disposable SQLite, fake kubectl and a fixture scanner. Actual scanner tests separately use only the official public Alpine 3.12.12 manifest `sha256:cb64bbe7fa613666c234e1090e91427314ee18ec6420e9426cf4e7f314056813`. Both platforms analyze 14 packages and report critical CVE-2022-37434 in zlib 1.2.12-r0, fixed in 1.2.12-r2, plus an EOL OS warning. See `scanner-smoke.json` and `scanner-linux-smoke.json`. No private image or live cluster was scanned.

Database and scan timestamps/expiry remain visible. Expired or unknown freshness is stale. The update helper only proposes or edits a reviewed source lock; current running instances change only when a prepared database is supplied or the maintained image is rebuilt. See `SYSTEM-REPORT.md` for the update workflow.

## Rendered QA

Codex IAB inspected the actual production fixture: loading; unscanned/unsupported coverage; findings, advisory, fixed and unfixed versions; namespace/fix filters; no-match search; navigation while scanning and cancellation after return; errors; stale database; empty inventory; missing scanner; 390px mobile; readonly controls; and unavailable inventory.

Final desktop/mobile/readonly/unavailable screenshots are under `screenshots/`. Mobile tables deliberately scroll horizontally. Earlier screenshots before the table correction remain local-only. Unavailable inventory displays unknown coverage and disables scanning; readonly users see no scan/cancel controls. This is visual/browser QA, not a claim of assistive-technology acceptance.

## Failures and remaining limits

The first new test run passed 14/16: a fixture lacked a selector label, and an oversized-results expectation disagreed with the specified unsupported state. Both test-authoring errors were corrected. Moving database-update tests into default TypeScript discovery then exposed a CommonJS/ESM loader failure; asynchronous ESM import corrected it, and the final combined group passes 18/18. None of these was an inherited production defect.

Historical 7,911 tests / 70 failures remain separate owner evidence. The full inherited suite was not replayed or waived; there is no new full-suite baseline-versus-feature result. A complete Linux application image/native-provider build, private registry integration, live cluster coverage, broader BORTUS release/security/recovery and actual assistive-technology acceptance are not claimed.

## Reproduction

Use supported Node 22 from `front-end/`:

    node --import tsx --test tests/system-report.test.ts tests/scanner-database-update.test.ts
    node --import tsx --test tests/system-report.integration.ts
    node node_modules/typescript/bin/tsc --noEmit --incremental false
    node node_modules/eslint/bin/eslint.js . --max-warnings=0
    npm run build
    node --import tsx tests/system-report-qa.ts

The QA harness is loopback-only with disposable public test credentials. Send `stop` on interactive stdin to close its server and remove its temporary fixture. No fixture credential is packaged into the application.

Source integration requires the coordinated current public checkpoint, final conflict review and normal protections. Broader release PR #28, private root docs, existing release gates and production remain separate. No Actions enablement, image publication or production deployment accompanies this feature.
