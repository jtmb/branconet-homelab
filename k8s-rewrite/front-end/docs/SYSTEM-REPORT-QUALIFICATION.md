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

## Public owner checkpoint integration

Public checkpoint `15fd0087897d6ce5435b6994be0c3da980846e9b` adds only four Ansible-selection runner/test files. Its changed paths have no intersection with the feature. It was merged into the isolated feature branch without conflicts; those four files match the public owner commit exactly, and application/scanner/build source remains byte-identical to qualified feature commit `17f6feefc4872d4e72963917548fadef79c87f88`.

After integration, runner/planner syntax and default discovery pass, both new TypeScript test files remain selected, and the focused group passes 18/18. Earlier full lint/types/build/production HTTP/rendered/scanner evidence retains its stated scope; no full inherited-suite replay or blanket acceptance claim follows this owner-only test integration. Fresh Actions permissions remain disabled. The draft PR still requires the coordinator's current-head/merge-window protocol and normal protections.

Public checkpoint `194f922b238a50858b507717d96d75a72bc495d0` was subsequently confirmed reviewed by the coordinator. Its four logout runner/test paths also have no overlap with the feature. Integration is conflict-free, preserves those owner files exactly, and leaves all application/scanner/build source unchanged. Runner/planner syntax, default discovery and the 18 focused controls pass after this integration. Broader suite/release limits above remain unchanged.

## Final combined qualification

The public target subsequently advanced through `df4bd0005a15ae68a150f3b2697d0d1a7d6a0649`, `dd955ba5f8fd2a45b0e3951d446800c8719f319f` and `7d1dd4b06aa30ea14f1353207dc0b8ef8f610c0e`. These owner test/planner/runner changes integrated without conflicts or feature-path overlap. Owner files match their public checkpoint, including package metadata, runner mappings, planners and frozen controls.

On Windows with system `core.autocrlf=true`, the first combined run passed 157/161: four unchanged M15 safeguards compare raw runner text to an LF literal. The same four failed on a detached, unchanged `df4bd000` baseline using the same Node 22.23.3 executable, shared tsx loader, dependency path and serial scheduling. No assertions were edited or failures waived. Restoring only `scripts/run-unit-tests.mjs` to its exact LF Git blob (after verifying CRLF normalization equals that blob) made the baseline four pass and the feature's 161 checks pass. No global Git configuration or unrelated checkout bytes changed. Reproduce these exact-text safeguards with the runner's canonical LF Git bytes; a Windows CRLF checkout still exposes this inherited mismatch.

After integrating `7d1dd4b`, the expanded group passes **1,136/1,136**, with no failures, cancellations or skips: all fifteen owner Node22 replacement files, every `*-unit-plan.test.mjs` safeguard, and both feature test files. Full nonincremental types and full lint also pass. This is a combined affected-test result, not a replay of every inherited test. The historical full-suite limitations above remain.

Independent read-only source review found no blocking authorization, privacy, digest identity, coverage, lifecycle or resource-bound issue. Its minor finding was corrected: exhausting the report byte budget now marks the job and remaining unscanned images as errors, rather than classifying the job as user cancellation. The expanded existing budget test proves later images are not scanned, findings are not retained, and coverage remains incomplete. A second independent review approved this correction and the two latest owner test checkpoints.

One further public test-only checkpoint, `5a6a0ca550303dfaa29db70e076be30925a50f14`, added deploy-stream replacement controls. It also integrated without conflict, preserved owner files and passed independent review. The expanded group now passes **1,227/1,227** with all sixteen replacements, planner safeguards and feature tests; no failures, cancellations or skips. Supported default discovery selects both feature files (237 total selected tests). A final local build attempt initially hit sandbox `EPERM` while creating disposable `.next` output; this environment failure is retained separately from source/test results.

The approved local retry completed the final Node 22 production build and both existing packaging steps successfully. Production HTTP integration against that rebuilt output passes 1/1, including authentication, authorization/revocation, caching/coalescing, cancellation and redacted errors. Final source review confirms all 50 owner checkpoint paths match the public target exactly and the feature diff is confined to 29 frontend paths. Private root-document changes remain excluded.

## Reviewed discovery compatibility checkpoint

The next public target, `d0650941cd4715bf1bc9613865be39ab8149c4d5`, introduced four M22 safeguards that compared the live test directory with historical fixed totals. Combined qualification passed 1,591/1,595. An unchanged detached target reproduced three failures; its newest safeguard passed there but failed when the two feature test files were added. Both feature files remained selected. No assertions were edited or tests hidden to obtain a pass.

The owner supplied reviewed checkpoint `6fb76e879062c057bac0a420a6466fda29f430f6`. It preserves historical totals in pinned filename fixtures and checks current discovery with exact mapping/set/partition invariants, including synthetic future TS/MJS inputs. Owner-managed checksum pins were reconciled. Runner batching preserves order and applies the experimental VM flag only to the new 85-control replacement input. Independent review verified these changes, 194 preserved prior controls and 465 checksum entries without finding a blocker.

After conflict-free integration, **1,708/1,708** combined checks pass across the owner's three execution batches (1,564 + 85 + 59), with no failures or skips. All twenty-one Node22 replacements, planner safeguards and both feature test files are included. Supported discovery selects 242 files and retains both CVE test files. Full nonincremental types and zero-warning lint pass. All 67 owner checkpoint paths match the public target exactly. Application, scanner, build and package source remain unchanged from the successful final production build and rebuilt HTTP integration; those checks retain their stated scope without another unrelated test-only rebuild.

The non-required GitGuardian check on the earlier feature head remains failed for eighteen reported occurrences. Independent source review and recomputation identify these as three SHA256 source-integrity assertions repeated across six unchanged owner safeguards, rather than credentials. No incident dismissal, skip, broad exclusion, security-setting change or protection bypass was performed. A separate email naming `eb5b310` supplies a generic detector type and commit but no exact incident value or source location; its GitHub check is neutral because it could not complete scanning. That email alone is not classified by the eighteen-occurrence proof. Final remote check metadata and any additional exact findings must be reviewed separately.
