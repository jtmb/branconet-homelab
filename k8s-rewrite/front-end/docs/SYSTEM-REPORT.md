# System Report runtime and API

System Report is part of BORTUS, using its Next.js backend, existing cluster resource cache and activeJobs cancellation registry. It reports vulnerability matches, never demonstrated exploitability, and does not patch clusters or rebuild images.

## API and authority

- GET /api/system-report requires a fresh authenticated account and returns private/no-store inventory and in-memory results.
- POST /api/system-report uses existing requireOperator authorization, coalesces repeated starts into one active job and requires current Pod inventory. Returns202 with the current job.
- DELETE /api/system-report?jobId=... requires the existing operator gate and exact active job. Cancellation holds the scanner slot until process/pipes close.
- /system-report is visible to authenticated users. Only operators see scan/cancel controls; server authorization is authoritative.

No new database schema, Secret API access, RBAC, credentials, daemon socket, standalone scanner service or runtime container is added.

## Repository-backed scanner provisioning

Both existing Dockerfile and Dockerfile.release invoke scripts/provision-scanner.mjs in their existing builder and copy its output to /opt/bortus-scanner. scripts/scanner-inputs.json pins official Trivy 0.76.1 and a specific official advisory OCI manifest/layer by SHA256. Builds never follow latest. Archive/manifest/layer identities, byte ceilings and database schema/freshness metadata are checked. The provisioner preserves the upstream license and writes provenance.json.

Docker runtime defaults:

- BORTUS_TRIVY_PATH=/opt/bortus-scanner/trivy
- BORTUS_TRIVY_CACHE_DIR=/opt/bortus-scanner/cache

The existing owned build supports Linux/amd64. Optional development overrides must be absolute paths to an explicit local binary and prepared database. Missing/invalid inputs render unavailable; they do not produce clean results. The initial pinned DB expands to 1,637,195,776bytes (compressed136,007,730). Expanded database ceiling is 3 GiB; the first 1.5 GiB provisioning attempt refused this database, and the reviewed finite bound was increased after inspecting its size. Provisioning is a build step, not a service or a startup database download.

The pinned database is a reproducible snapshot, not an automatically refreshed service. Refresh reviewed DB manifest/layer pins in the owned repository and rebuild the maintained BORTUS image, or explicitly supply an operator-prepared current DB directory. Do not overwrite a database during a scan. The report exposes UpdatedAt/NextUpdate and marks expired/unknown freshness stale. It never silently reports an old database as current.

Official inputs: https://github.com/aquasecurity/trivy/releases/tag/v0.76.1 and ghcr.io/aquasecurity/trivy-db. Upstream CLI contract: https://trivy.dev/docs/latest/references/configuration/cli/trivy_image/. No GitHub Actions invocation or image publication is part of provisioning.

## Finite runtime limits and disclosure

One process-local job scans sequentially: maximum 256 images, ten-minute job deadline, 90 seconds per image, 1 GB image ceiling, 8 MiB stdout/64KiB stderr, 16 MiB normalized report results, 32 MiB/512-entry cache and six-hour TTL. Cache identity includes runtime digest and DB/binary metadata; stale or changed inputs miss cache. GOMAXPROCS=1, parallel1 and GOMEMLIMIT=256MiB constrain scanner work; these are not an OS memory sandbox. Existing deployment resource limits remain authoritative.

Image analysis uses remote image sources by runtime registry digest, offline vulnerability matching, no DB/Java/check updates, no version checks/telemetry, no shell and a scrubbed environment. Filesystem analysis caches are disabled; each scan's temporary directory is removed after process closure, including cancellation. Raw scanner output/errors never reach clients or logs. The upstream Java identification DB is not separately bundled; images requiring unavailable language identification or credentials fail explicitly, rather than being assumed clean.

No Kubernetes/signing credentials or inherited Trivy/Docker configuration reaches the scanner. Operators may supply existing registry authentication explicitly under the cache's registry-auth directory; BORTUS does not create, extract, expand or persist credentials. It downloads image contents only from the image's registry and never uploads private contents/inventory to an advisory service.

## Coverage and update decisions

Inventory covers all visible statuses reported running, including regular, running init and ephemeral containers. Digest deduplication preserves all consumers/aliases. Controller UID and namespace resolve ReplicaSet-to-Deployment ownership; direct controllers remain visible otherwise. Services require a nonempty matching selector in the same namespace; missing mapping remains unknown. Visibility is limited by the existing Kubernetes identity and one connected cluster.

Only pullable runtime SHA256 digests establish scan identity. Mutable tags, opaque CRI/config IDs, absent digest, absent package targets, failed/truncated results and cancellation retain incomplete coverage. EOL OS and stale results are explicit. Zero matches means only no known matches in detected packages. Results/inventory disappear on process restart.

For third-party images, review the advisory and maintained upstream release, then change version/digest in authoritative jtmb/branconet-charts where appropriate. A package fix does not prove an upstream image includes it. Maintain/rebuild only owned repository-backed images. This screen performs neither operation; merging source does not deploy anything.

See SYSTEM-REPORT-PLAN.md and qualification receipts for current test results and remaining acceptance limits.

### Updating advisory pins through reviewed source

From front-end with the supported Node 22 runtime:

1. Run `node scripts/update-scanner-database.mjs` to print a candidate from the official public DB registry. This is a bounded metadata-only read with no cluster/image inventory. It does not write source or change runtime data.
2. Run `node scripts/update-scanner-database.mjs --write` when ready to edit the repository lock, then review `git diff -- scripts/scanner-inputs.json`. Binary/version pins stay unchanged. No update runs automatically during application use or builds.
3. Run `node scripts/provision-scanner.mjs <owned-validation-directory> --binary-source <absolute-qualified-scanner-directory>` on Linux/amd64 to verify the pinned manifest/layer checksums, expanded DB schema/timestamps and archive limits. Review provenance and scan a pinned public fixture.
4. Commit the reviewed lock change and rebuild the owned BORTUS image using its existing build definition. Normal deployment approval and chart ownership still apply. This command never publishes images, enables Actions, patches workloads or deploys anything.

Refreshing pins does not immediately change already-running instances. The screen retains their actual scan/database timestamps and stale warnings until a current snapshot is supplied and images are rescanned.

## Qualified scanner build input

The provisioner requires an explicit absolute provider directory containing `trivy` and its upstream `LICENSE`. `scripts/scanner-inputs.json` binds both exact byte counts and SHA256 values. The maintained scanner is `0.76.1-bortus.1`, built with Go 1.27.3 from upstream commit `e713f67f7d54decdcd9b3132c9751833dcced698` and six pinned module updates recorded in the same lock. The helper copies these two regular files through exclusive new outputs, verifies their identities and digests, and rejects missing, aliased, changed or mismatched inputs. It never falls back to downloading the upstream release binary. `BORTUS_SCANNER_BUNDLE` may supply the same absolute directory when the command-line option is omitted.

`Dockerfile.release` takes the scanner and license from its existing required `BORTUS_RUNTIME_IMAGE` provider. The regular `Dockerfile` takes `/scanner/trivy` and `/scanner/LICENSE` from its existing `bortus_kubectl` build context; that context continues to supply `/kubectl` separately. Operators must supply bytes matching the reviewed lock. This source change introduces no image publishing or deployment command.

The advisory database still follows the original immutable manifest/layer verification, schema and timestamp checks, size limits and staging cleanup. The reviewed database snapshot is dated 2026-10-25; its age remains visible and it requires a separately reviewed pin update for freshness. `--database-only` retains the portable database qualification path. Whole-image security qualification uses its independently current official advisory database and remains a separate acceptance gate.
