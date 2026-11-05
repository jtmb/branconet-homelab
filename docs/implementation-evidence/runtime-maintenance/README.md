# BORTUS dependency and runtime qualification, 2026-10-10

Corrected source: `483ba4f0c82cbaca76646f221c4c497f8c298d70`, based on the app owner's committed `74500af4a9553d98fdf6dd25f71aaba1cddb445a`. Implementation commits are `058d38ada73269c111c849fb1f6e810e25920b72` and `483ba4f0c82cbaca76646f221c4c497f8c298d70`. This is an isolated maintenance qualification. The owner's subsequent UI work and final integrated release require a fresh qualification. No production access, deployment, image preload, chart change, account/Secret/database mutation or credentials were used.

## Qualified changes and checks

The parent-version-scoped npm override `@prisma/config@6.19.3 -> deepmerge-ts 8.0.0` retains Prisma/client 6.19.3 and Next 15.5.27. The lockfile has one resolved DeepmergeTS copy; npm resolution and a complete runtime dependency-directory walk both confirm 8.0.0. The ordinary config regression loads an actual Prisma config through the CLI, validates the schema, deploys all migrations twice and checks zero schema drift. No vulnerability demonstrations were performed.

Clean Linux Node 22.23.3/npm 10.9.9 install, explicit Prisma generation, zero-warning lint, production build, typecheck, all **114 unit tests** (85.52 s) and all **three production HTTP/TLS fixtures** (23.31 s overall) passed from raw Git blob bytes. The native fixture uses a disposable CA-verified HTTPS mock API. None skipped. The clean quality container uses UID/GID 1000, four CPUs with affinity 0–3, four GiB memory and 256 PIDs. Docker builds use ordinary BuildKit defaults with a 900-second wall bound. The Dockerfile's default kubectl was exercised without a version override.

The final runtime removes global npm/npx, Corepack and Yarn, while retaining the local Prisma CLI invoked through Node. Runtime checks proved UID/GID 1000, port 4000, writable `/data`, `/home/shell` and `/app/.next/cache`, the original entrypoint/healthcheck and successful migrations/server restarts. Fresh and legacy-forward disposable containers each applied **all eleven migrations**, reported zero schema drift and passed first/second-boot liveness 200 and expected readiness 503 without native credentials. Legacy checks preserve usernames/password hashes, roles/session versions, exact aliases, quarantined old rows, administrator migration, policies/grants, mount/path/field metadata, operations, rotation intents and audit rows. These checks use the unchanged frozen smoke program, SHA256 `b99ee2e4595500ec991fe9109b2c1765e38a184e18c68476c08f989376870070`. Synthetic fixture values and signing material remain inside disposable containers and are not recorded in evidence.

The image keeps externally supplied stable `BOTRUS_JWT_SECRET`/`BOTRUS_SECRETS_KEY`, provisioning disabled, verified TLS, one-replica/Recreate/PVC requirements, probes and external bootstrap. No schema/protocol/authorization behavior or engine/UI source was changed by this maintenance stage. Final live RBAC/admission/guard/recovery qualification remains external.

## Artifact identities

| Artifact | Exact identity |
|---|---|
| Node base | `node:22.23.3-bookworm-slim@sha256:c3de60bf2f9dd0ac6370e6117950ff62d6e339527e7472301c9c78a017978392` |
| Local runtime image | `bortus-qa:maintenance-483ba4f-raw` |
| Image manifest/index ID | `sha256:497d099b6412e16954e9dd88da9c97656c8cfcc5c9a83db62d3c71765aaec866` |
| Platform manifest | `sha256:e148b6fdf9d7021f5d469e424c0364a69df6c9b6d9b7849142ed12852a8dc2d1` |
| Image archive SHA256 | `d1bfdbe0a132cc9183f9476f795741dacf3b8b02927f53c8b9a7772d1b1b7612` (331,491,840 bytes) |
| Source archive SHA256 | `86f3de99657ea0f0b2ad30d1fb30cf6030461c3a962eeeb94c94c7147870886c` |
| Git package-lock SHA256 | `32b54a6453b70a6438e5a1ed2f0e7a49cc1c971418bdd6eebb29cef4e9c0654c` |
| Git Prisma schema SHA256 | `06abf29e554e101a7b048c7334c9a3eae12c6e78c7f399f709ee2e7b14ecc409` |
| Git Dockerfile SHA256 | `5be26d8ac43ce45dacad4c392a4369aad2ca7eb4adcc0f17ea9442578f692b2a` |
| Runtime Perl | `perl-base 5.36.0-7+deb12u4` |
| kubectl | `v1.37.1`, official checksum verified; Go `go1.26.8` |

The pinned Node image inherited Perl `deb12u3`; `apt-get upgrade` refreshes installed security packages, and the Docker build enforces the [Debian fixed version](https://security-tracker.debian.org/tracker/DSA-5902-1). The runtime inventory includes OpenSSL `3.0.22-1~deb12u1`, curl `7.88.1-10+deb12u15` and glibc `2.36-9+deb12u14`. kubectl binary SHA256 is `65691ff77eb6fa44c908b77a1082c9f092c3b9733b5cefabec0d1104890e21a8`; Node binary SHA256 is `fde6a4bf8d0562f7751d1a2d6cb9b417c4cfe107bbcb0aa3e9a24e125e348f48`. APT resolution remains time-dependent; rebuilding later can change the resulting image. Pin the accepted resulting artifact separately from its source/base.

[Source provenance](source-provenance.json) records every eligible tracked file's raw Git blob and final qualified archive bytes. The final export uses `git -c core.autocrlf=false archive`: **all 280 files match their committed blob bytes exactly**, with no line-ending or content differences. Environment examples were excluded from both test and Docker source exports; committed `.dockerignore` excludes tests/env/DB/kubeconfig/build output from the runtime context. OCI revision/scope labels and BuildKit provenance are retained. The earlier [CRLF export comparison](source-provenance-attempt-2.json) and its passing functional run remain historical candidate evidence; final source, image and scan identities above belong to the fresh raw-blob qualification.

## Raw package findings and separate applicability note

[Full npm report](npm-audit-all.json): **nine affected tooling entries** (seven high, two moderate), including the Braces/glob chain and PostCSS selector parser chain. [Production npm report](npm-audit-production.json): **zero entries**. Counts include dependency chains, not independent defects. ESLint 9.39.5 retirement and xterm deprecation warnings remain explicit. No forced major upgrade or peer bypass was used.

One vulnerability-only offline image scan used `aquasec/trivy@sha256:af6acf9a6b85dfe389a1941505c0ce9efef52a4719635e1a962f022a3d855daa` (Trivy **0.75.0**), without host installation, Docker socket, credentials or network. Database schema version **2**, updated `2026-10-10T18:59:50.889010923Z`, downloaded `2026-10-10T22:31:43.939383155Z`, DB SHA256 `03cacb40452ceb74afdfca072cb82f79ee884dfac006ef24a4dfdad133b0f917`. The exact image archive above was scanned. Scanner exit zero means reporting completed; **the vulnerability gate is not clean**.

The [unaltered raw Trivy report](trivy-image-vulnerabilities.json) retains **346 rows / 160 distinct IDs**:

| Target | Rows | Severity/status |
|---|---:|---|
| Debian 12.15 packages | 327 | 1 critical, 63 high, 135 medium, 124 low, 4 unknown; 242 affected, 68 fix-deferred, 17 will-not-fix |
| Node packages | 0 | No reported package findings; this does not certify all runtime code |
| kubectl compiled dependencies | 19 | 4 high, 7 medium, 1 low, 7 unknown |
| Total | 346 | 1 critical, 67 high, 142 medium, 125 low, 11 unknown |

All Debian rows other than the precise vendor note below remain unqualified and explicit; the available APT security refresh supplies no recorded fixed version for these remaining rows. All 19 kubectl rows remain: the distributed binary contains `golang.org/x/net v0.57.0`, `golang.org/x/text v0.40.0` and Go `v1.26.8`; the report lists fixes `0.60.0`, `0.41.0` and `1.26.9/1.27.2` respectively. Trivy's `fixed` status means an upstream fix exists, not that this image is patched. The official [current release list](https://kubernetes.io/releases/) lists v1.37.1 as the latest 1.37 patch; the default respects the [one-minor kubectl skew rule](https://kubernetes.io/releases/version-skew-policy/#kubectl). No custom build, prerelease, guessed patch or cluster upgrade was substituted.

**Vendor applicability, CVE-2023-45853 only:** The original critical `zlib1g 1:1.2.13.dfsg-1` row is retained. [Debian's tracker](https://security-tracker.debian.org/tracker/CVE-2023-45853) explains that bookworm's zlib package does not build/provide the affected `contrib/minizip` code. This note applies only to that Debian binary/package finding. It neither removes the raw row nor dismisses other zlib CVEs, independent MiniZip packages or any other image findings.

For context, the earlier `ea849ee` scan against this same scanner/database reported 381 rows (340 Debian, 22 Node, 19 kubectl). The new report has 35 fewer rows: the 13 fix-available Debian rows and 22 Node-package rows no longer appear. This is a package-report comparison between two exact local QA images, not a claim of complete remediation or runtime exploitability.

## Failed attempts and integration

The first source `058d38a` passed clean install/generation/lint/build, then typecheck found TS2339 on the new config fixture's inferred `env.RUST_LOG`. The corrected fixture uses an explicit `NodeJS.ProcessEnv` annotation and a separate database string; assertions are unchanged. [Attempt 1](quality-attempt-1.log), [passing CRLF candidate attempt 2](quality-attempt-2.log) and [passing final raw-blob attempt 3](quality-attempt-3-raw.log) are retained. The earlier CRLF candidate image/scan remains in the protected local artifacts; one scan of the final raw-blob image supersedes it, using the same pinned database and yielding the same package counts. An initial Linux Git export failed on the Windows worktree's absolute Git pointer; disabling native Windows Git's archive line-ending conversion and verifying every file resolved final provenance. An initial npm 10 lock regeneration dropped libc metadata; it was discarded and regenerated using disposable npm 11.16.0 under Node 22.23.3, retaining all original package metadata except the scoped DeepmergeTS resolution. One final fresh-runtime WSL connection attempt failed before the Linux fixture started (`Wsl/Service/0x8007274c`); the unchanged retry passed. The legacy-forward and runtime contract checks also passed. No test assertion or resource boundary was weakened.

Integration owner: cherry-pick the two source commits in order, then the evidence/documentation commit that adds this directory. Reconcile documentation with your newer UI ledger; preserve these residual package findings. No engine/auth/UI files are owned by this maintenance change. Run the established install/generate/lint/build/types/unit/HTTP gates on the final combined source, build its exact clean Docker context with a recorded source revision label, and qualify that final image's migration/restart/recovery contract. This isolated QA image is not a deployment artifact or a rollback approval. Retain old images/backups; never reset existing databases or infer native Secret ownership during integration.

[Machine-readable qualification](qualification.json), [dependency resolution](dependency-resolution.json), [Debian inventory](debian-packages.tsv), [image build](image-build.log), [base update](base-build.log), [scanner log](trivy-scan.log), [unchanged runtime fixture](runtime-smoke.cjs) and [runtime contract check](runtime-contract.cjs) support this handoff. Committed log transcripts normalize terminal carriage returns and trailing whitespace; the raw Trivy JSON is unaltered. Original logs, image archives/database and complete local artifacts remain at `/home/brajam/.local/share/branconet-migration/bortus-delivery/runtime-maintenance-058d38a` in Ubuntu WSL.
