# BORTUS implementation evidence

The audit-evidence directory is the immutable pre-fix record. This directory records post-change acceptance; synthetic Windows timings do not establish Linux image or real cluster performance.

The production HTTP suite uses disposable SQLite, fake signing/lookup material, an unavailable loopback native API, and a metadata-only fake kubectl executable with a fixed 50-ms delay. It records actual HTTP contracts and command counts. On Windows it compiles the .NET fixture; Linux uses the equivalent Node fixture, whose process startup cost differs.

Run from k8s-rewrite/front-end after npm run build. npm run test:integration emits metadata-only timing diagnostics. Setting BORTUS_TEST_EVIDENCE_PATH saves that diagnostic JSON explicitly; no native value export is performed. BORTUS_EVIDENCE_SOURCE labels the source revision/working tree. Twelve warm and twelve unavailable requests yield p50/p95; twenty concurrent cold/warm requests verify coalescing. Exact timestamps, runtime and limitations accompany the saved result. Tests assert contracts/counts, not latency thresholds on an uncontrolled host.

Pre-fix Windows audit: a cold pod route fetched ten types in 184.86 ms; 12 warm samples p50/p95 15.24/16.23 ms; 20 concurrent cold calls shared ten CLI operations; two sequential unavailable pod reads started 20 CLI operations and returned false-empty 200. The new fixture shares the 50-ms CLI delay but adds fresh SQLite account checks and different owner-rich metadata. Compare command cost and response correctness directly; treat latency comparisons as observational. No container peak RSS, real kubectl/RBAC, live latency or screen-reader acceptance is inferred from this fixture.
