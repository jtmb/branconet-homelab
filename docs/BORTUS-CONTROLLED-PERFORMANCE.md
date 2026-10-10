# Controlled whole-server performance qualification

This is an independent checkpoint comparison for audit A07/A21 server cost. It provides server-side evidence relevant to A11; it does not complete browser polling/lifecycle, UI behavior A08–A20 or optional client-code A22 acceptance. The immutable audit and application remain unchanged by this benchmark. The final integrated source still needs its own rerun.

The [raw record](implementation-evidence/bortus-controlled-perf.json), [validated aggregate](implementation-evidence/bortus-controlled-perf-summary.json) and [reproducible harness](../benchmarks/bortus-controlled-perf/README.md) preserve source provenance, every request's timing/status/size, phase CPU/RSS/process/API counts, assertions and earlier attempts. A successful harness run means the expected successes **and expected negative cases** occurred. It does not mean that every audit performance gate passed.

## Source and environment

| Property | Fixed input |
| --- | --- |
| Audit baseline | `51e8cd66379c1f40a95ea02f4da7c8aed848f2a4` |
| Integrated checkpoint | `1e0030a51c7d6cf0b8e161d349813de745c0aa11`; not final |
| Raw-blob exporter | Charts `a82a6cb9e244b0ec05489bc7251f3e29411c64dc`; reviewed local bytes must match committed bytes |
| Runtime | WSL Ubuntu Docker, Linux x64, Node 22.23.3, existing image `sha256:f628f5688b3fafb391d8d99c9b16aee4d9162aa5aaa121c3ae340f5bc8c2a678` |
| Source build limits | 4 CPU quota/affinity CPUs 0–3, 4 GiB RAM, no swap, 256 PIDs, four Next workers; independent clean `npm ci && npm run build` |
| Runtime limits | 2 CPU quota/affinity CPUs 0–1, 1 GiB RAM, no swap, 256 PIDs, network disabled except container loopback |
| Repetitions | Three fresh containers per source, alternating B/C, C/B, B/C; each includes six identical workload profiles |
| Synthetic dependencies | Fake CLI: 50 ms per command; verified-TLS native API: 12 ms per request; optional Longhorn delay: 1,000 ms |

Raw Git blobs are exported outside the checkouts, checked for credentials and scanned. The selected original file bytes are hashed, checked unchanged before/after both successful builds and before every runtime run. Both sources use their own committed lockfile and application schema; isolated migrations/accounts/configuration are created in each disposable container. No existing DB, native cluster, Secret, credential, chart, storage or production resource is used. Native values/annotation markers and auth material are synthetic, ephemeral and absent from evidence, SQL, argv and Git. No image is built or pulled.

Quota and affinity constrain scheduling; they do not reserve physical cores or remove host contention. Equal `--memory`/`--memory-swap` disables swap, verified here through actual cgroup `memory.swap.max=0`. See [Docker resource constraints](https://docs.docker.com/engine/containers/resource_constraints/). Cgroup CPU/peak memory cover the entire fixture container: driver, TLS producer, Next, Prisma/CLI children and file cache. Actual Next child PID RSS/high-water/CPU are reported separately using `/proc`; see [Linux cgroup v2 counters](https://docs.kernel.org/admin-guide/cgroup-v2.html). These measurements do not establish production resource requests/limits.

## Fixed workload and definitions

Every profile configures 18 native namespaces and 603 exact metadata aliases. The two large-record profiles concentrate native objects in one namespace while still checking all 18 allowed scopes. The same lists, aliases, key spellings, immutable source and assertions apply to both versions.

| Profile | Pods | Native objects | Decoded payload/object | Config rows |
| --- | ---: | ---: | ---: | ---: |
| Audit-small | 3 | 334 | 64 B | 200 |
| Metadata-200 | 200 | 200 | 64 B | 200 |
| Metadata-1,000 | 1,000 | 1,000 | 64 B | 1,000 |
| Metadata-10,000 | 10,000 | 10,000 | 64 B | 10,000 |
| KV-sized native | 3 | 25 | 256 KiB | 200 |
| Maximum flat native | 3 | 3 | 1 MiB | 200 |

Cold means a fresh Next production process with authenticated session initialized and no earlier cluster resource request. OS/file caches are not flushed. Warm means the same process immediately after its first identical successful read: 12 sequential samples and a burst of 20 concurrent requests. A second fresh process tests 20 concurrent cold requests. Additional phases load empty Services after Pods, complete configuration and native metadata, every alias page, and five readiness requests. Audit-small also tests delayed optional Longhorn, two sequential CLI outages and forbidden access to the eighteenth native scope. Only read requests occur.

Equivalence checks cover every Pod name/namespace/count; every native Secret name/namespace/type/resourceVersion/exact key map/count with payload/annotation exclusion; all 603 exact aliases across up to seven pages; configuration row counts; and the expected empty Service list. They do not assert byte-identical JSON, every Pod presentation field, or configuration row values. Availability metadata and pagination envelopes legitimately change public response sizes.

HTTP timing stops after the whole body is received; validation is outside that timing. Workflow elapsed includes all requests, body validation and phase observer work, which is the useful comparison for one versus seven alias pages. CPU counters cover the phase. RSS is sampled every 50 ms with kernel high-water at phase boundaries; short-lived process peaks may be missed. Historical `steady_rss_kib` names the last 20 samples of an active workload, **not an idle steady-state measurement**. The summary calls it end-window RSS. Requests have a 20-second deadline clipped to the 540-second run deadline; startup probes have a 30-second wall deadline. A 600-second outer container bound also applies. The 32-MiB observer response-size assertion is checked after full body receipt; it is not a streaming memory ceiling.

Native `produced_response_body_bytes` records serialized response bodies **attempted by the fixture producer**, including rejected-page retries; it is not actual socket bytes, client-received bytes or transport overhead. Browser transfer/render/LCP/DOM/visibility/polling, real ingress/API/CLI latency, idle RSS, long-lived leaks and manual zoom are unmeasured.

## Measured checkpoint results

The final repeated set and summarized figures are recorded below after validation. All figures are medians across three runs. For warm/concurrent p50/p95, each percentile is first computed per run using nearest rank, then those three values are summarized. A 12-request nearest-rank p95 is its maximum sample; it is a small fixed-workload observation, not a population tail estimate. Raw run ranges are retained, with no statistical-significance or SLA claim.

| Equivalent Pod workload | Baseline | Checkpoint | CLI calls B/C |
| --- | ---: | ---: | ---: |
| 3 Pods, cold HTTP latency | 187.0 ms | 97.4 ms | 10 / 1 |
| 200 Pods, cold HTTP latency | 192.7 ms | 100.7 ms | 10 / 1 |
| 1,000 Pods, cold HTTP latency | 198.6 ms | 114.4 ms | 10 / 1 |
| 3 Pods, 20 concurrent cold p95 | 249.9 ms | 116.6 ms | 10 / 1 |
| 1,000 Pods, 20 concurrent cold p95 | 302.8 ms | 325.7 ms | 10 / 1 |
| 3 Pods, 12 warm p50 / p95 | 5.6 / 16.9 ms | 5.9 / 19.3 ms | 0 / 0 |
| 200 Pods, 12 warm p50 / p95 | 4.5 / 7.5 ms | 6.7 / 11.5 ms | 0 / 0 |
| 1,000 Pods, 12 warm p50 / p95 | 6.1 / 9.1 ms | 10.5 / 16.2 ms | 0 / 0 |
| 1,000 Pods, 20 concurrent warm p95 | 73.9 ms | 142.3 ms | 0 / 0 |
| 3 Pods, delayed optional Longhorn cold read | 1,091.9 ms | 93.5 ms | 10 / 1 |
| Empty Services immediately after 3-Pod read | 4.9 ms | 84.6 ms | 0 / 1 |

Cold independent Pods reads avoid nine unrelated processes and the optional-resource delay. Healthy in-flight coalescing remains: 20 cold requests share one fanout/read, while warm requests issue no CLI commands. Independent caching also stops prewarming Services during the Pods request, so the next Service screen pays its own cold-read cost. Response metadata grows the 3-Pod body from 653 to about 1,007 bytes and the 1,000-Pod body from 216,468 to about 268,666 bytes. These are actual HTTP body bytes, without transport headers/compression.

**The no-warm-regression requirement is not satisfied.** In all three current pairs, 1,000-Pod warm p50/p95 are slower: baseline p50 range 5.9–6.3 ms versus checkpoint 8.0–19.7 ms; the raw/aggregate evidence retains precise ranges. The 1,000-Pod warm workflow CPU rises from a 124.6 to 205.4 ms median, and concurrent warm CPU from 134.2 to 239.8 ms for the whole phase. This benchmark does not isolate whether response mapping/authorization/serialization or another change causes it. A blanket A07 performance pass would be inaccurate.

The 10,000-Pod fixture produces **5,914,546 CLI JSON bytes**, beyond both sources' 2-MiB CLI output ceiling. The baseline returns `200` with an empty list; the checkpoint returns explicit `503` unavailable. Neither returns the intended 10,000 objects. Single/concurrent results are marked **invalid for speedup comparison**, and warm samples are skipped. This proves more truthful failure behavior and bounded process cost, not successful large-Pod capacity.

| Complete native metadata inventory | HTTP latency B/C | Native calls B/C | Producer-attempted body bytes B/C |
| --- | ---: | ---: | ---: |
| 334 small objects / 18 namespaces | 94.3 / 306.7 ms | 18 / 18 | 151,310 / 151,310 |
| 200 small objects | 73.1 / 303.5 ms | 18 / 18 | 91,172 / 91,172 |
| 1,000 small objects | 72.4 / 926.1 ms | 18 / 54 | 450,196 / 453,832 |
| 10,000 small objects | 246.0 / 7,876.6 ms | 54 / 504 | 4,501,868 / 4,547,696 |
| 25 × 256-KiB objects / one active namespace | 184.5 / 512.3 ms | 18 / 21 | 8,748,637 / 15,746,610 |
| 3 × 1-MiB objects / one active namespace | 117.4 / 574.3 ms | 18 / 22 | 4,196,924 / 16,783,410 |

Every intended native object and exact key map is returned in both sources; public body sizes match. The audit baseline has 200-object pages and concurrent scope listing. The guarded checkpoint uses sequential scope processing and adaptive 20-object pages with bounded response/retry/aggregate budgets. The safety implementation therefore costs latency and more calls against this **audit baseline**, even where earlier intermediate one-object paging benchmarks improved. Large-page rejection produces repeated bodies in the large-record fixtures. The attempted-byte counts must not be presented as actual client transfer or as byte-budget violations. This server benchmark does not attribute every difference to a single implementation change or change the native safety limits.

| Server metadata/probe workflow | Baseline | Checkpoint |
| --- | ---: | ---: |
| All 603 audit-small aliases, complete workflow | 12.4 ms / 1 HTTP request | 49.0 ms / 7 HTTP requests |
| 10,000 configuration rows, HTTP latency/body | 141.9 ms / 2,218,891 B | 162.9 ms / 2,218,891 B |
| Five audit-small readiness requests | 295.2 ms / 90 native calls | 115.0 ms / 18 metadata-only calls |
| Five 10,000-object readiness requests | 1,002.9 ms / 270 native calls | 112.8 ms / 18 metadata-only calls |
| Five KV-sized readiness requests | 732.7 ms / 90 native calls | 114.3 ms / 18 metadata-only calls |

Bounded 100-alias pages preserve all 603 references while adding HTTP envelopes/round trips: audit-small total body 61,921 → 62,227 bytes. Comparing one checkpoint page to the entire baseline would lose equivalence. Readiness checks all 18 scopes with metadata-only responses, then reuses its bounded probe cache for the remaining four calls. In the 10,000-object case, producer-attempted bodies fall from 22,509,340 to 5,836 bytes; in the KV-sized case, 43,743,185 to 2,241 bytes. Both versions reject the inaccessible eighteenth scope with `503` after a fresh process (18 calls); checkpoint median rejection latency is 125.9 ms versus 56.2 ms. No value-body fallback/cache is introduced.

Two sequential CLI outages consume 20 baseline commands versus one checkpoint command, with checkpoint cooldown reuse. Their response contracts differ: old `200` empty versus current `503` unavailable. Request duration and CPU are retained as negative-case observations, **not a latency speedup**.

| Whole six-profile container run | Baseline median (range) | Checkpoint median (range) |
| --- | ---: | ---: |
| Cgroup peak memory | 364.6 MiB (357.5–381.3) | 284.8 MiB (271.8–285.2) |
| Cgroup total CPU | 34.98 s (34.87–40.23) | 34.57 s (32.61–37.54) |

No OOM/kill is observed; throttling is zero or below 1 ms across these final whole runs. The checkpoint's lower **combined fixture peak** does not promise lower application idle RSS or general CPU improvement: CPU ranges overlap and include startup, migration/seed, driver and producer work. Audit-small Next end-window RSS increases from 191.7 to 199.2 MiB, 1,000-object from 200.2 to 214.0 MiB, and maximum-flat from 209.6 to 226.9 MiB; KV-sized falls from 253.1 to 231.7 MiB. The 10,000-object window is about 248 MiB for both. Phase PID high-water/CPU, samples and whole-container peaks are separate fields in the evidence, not interchangeable memory limits.

## Attempts, acceptance and next step

The integration owner is separately profiling warm Pods. One diagnostic run used exact 1e0030a source bytes and this Node22/image/resource constraint, changed the driver only to select the 1k profile, execute 200 warm reads and enable Node CPU sampling, and completed its success/negative-case assertions. This altered diagnostic is not one of the frozen acceptance pairs. Recursive metadata projection, Pod summaries and JSON serialization appeared in samples; a metadata-only weak-snapshot projection/JSON cache is now being qualified. Account/session verification, current availability/warnings and filter validation remain required. Keep these checkpoint figures intact; the unchanged full workload must still run on a new exact committed candidate.

Preparation exported and built both immutable sources; builds took 92.886/101.425 seconds under identical build limits. An initial runtime candidate attempt failed in the observer's availability-field lookup, not the application assertion. The corrected lookup retained the expected old-empty/current-unavailable outage outcomes. That partial attempt and its baseline are archived separately and excluded from comparisons. A subsequent complete six-run set is also retained separately: review found that a retry-count startup loop could exceed its stated wall deadline. The current driver clips each startup probe to the real deadline and repeats every pair. No source, fixture, equivalence check or acceptance condition was weakened to pass.

The actual measurement runner is preserved in commit `cefc52b125138aea2662bf200902a1bd31e16754`, with its original byte hash in the raw record. A later archival-only correction prevents reading an earlier failed phase's recycled result filename after a successful set. The passed duplicate copied under the second archive's `failed_measurements` was moved, intact, to `reclassified_passed_duplicate_snapshots`; the real initial failure remains in the first archive. No final observation, driver, source, assertion or percentile changed. The current runner archives only a current failed result created after that phase started. Both runner versions remain reviewable in Git.

Seven evidence integrity/provenance tests check guarded extraction, EOL/source changes, completed pairs, fixture/driver consistency, exclusion of failed 10k/outage results from speedups, and refusal of stale/passed failure snapshots. Both exact application builds and the runtime success/negative-case assertions passed. Full application unit/browser/integration acceptance belongs to the integration ledger; this benchmark does not substitute for those suites.

The harness scan found no credentials. Scanning the owned documentation/evidence produced 25 generic-key findings; each was verified to be a 64-character SHA256 of a selected committed source file in `source_manifest`, triggered by credential-related filenames. They are public source provenance, not native Secret-value or credential digests. No untriaged finding or broad scanner-rule suppression remains; redacted scanner output stays in the protected workspace.

A07's warm-cache latency requirement and successful >2-MiB Pod capacity remain open. Server metadata/readiness capacity and explicit error semantics have bounded synthetic evidence, with the costs described above. The integration owner must resolve or explicitly disposition the regressions and repeat this unchanged workload against the final committed source. Hidden-tab request rates, lifecycle cancellation, UI render/DOM/LCP/interaction, final compatible image/recovery and live migration remain separate gates.
