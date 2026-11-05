# Controlled whole-server checkpoint benchmark

This harness measures complete production Next servers from immutable Git blobs. It owns only its temporary fixture containers, its private `~/.cache/bortus-controlled-perf/run-*` directory and the explicitly selected metadata report. It does not build/pull images, contact a cluster, deploy, preload an image, or read an application checkout's env/DB files. See [qualification and limits](../../docs/BORTUS-CONTROLLED-PERFORMANCE.md).

Prerequisites: Linux Docker with cgroup v2, Python with `tarfile` data filters, an already installed Node **22.23.3** Linux x64 image with OpenSSL CLI and Bash, and the reviewed raw-blob exporter from charts commit `a82a6cb9e244b0ec05489bc7251f3e29411c64dc` plus its Gitleaks scanner. The exporter must exactly match that committed file; `git archive`/a mutable source checkout are not substitutes. On Windows worktrees the exporter selects Windows Git from WSL to resolve the worktree's Git directory.

From WSL Ubuntu, this reproduces the measured checkpoint. It creates a fresh protected directory and never overwrites the committed evidence if a new report path is used:

```bash
python3 '/mnt/c/Users/james/.codex/worktrees/8f2c/kubernetes migration/benchmarks/bortus-controlled-perf/run.py' \
  --repository '/mnt/c/Users/james/.codex/worktrees/8f2c/kubernetes migration' \
  --exporter '/mnt/c/Users/james/.codex/worktrees/8cdf/branconet-charts/scripts/export_bortus_source.py' \
  --baseline 51e8cd66379c1f40a95ea02f4da7c8aed848f2a4 \
  --candidate 1e0030a51c7d6cf0b8e161d349813de745c0aa11 \
  --image sha256:f628f5688b3fafb391d8d99c9b16aee4d9162aa5aaa121c3ae340f5bc8c2a678 \
  --runs 3 \
  --report '/home/brajam/.cache/bortus-controlled-perf/checkpoint-rerun.json'
```

`--prepare-only` exports/verifies/builds both sources without measuring. `--resume` accepts only an existing directory inside this harness's protected namespace, verifies source/image provenance, and resumes missing pairs. A changed runtime harness archives all prior observations and starts a complete new measurement set; it never mixes driver versions. A different candidate needs a fresh run directory. Source builds are capped at 900 seconds each; runtime containers at 600 seconds each. A timed-out operation stops only the exact container it created. A failed phase stops qualification and preserves metadata plus protected output; assertions are not bypassed.

The orchestrator accepts three to five pairs and alternates baseline/candidate order. Application source files are checked against their original byte hashes before/after build and before each run. Build artifacts stay private and outside Git. Only original selected source files are covered by that unchanged check; this is not a hash manifest of every generated bundle or dependency file. Source, exporter, lockfile, immutable runtime image and driver provenance are recorded.

Derive a validated summary from a completed report, then run the evidence/provenance tests:

```bash
python3 benchmarks/bortus-controlled-perf/summarize.py \
  docs/implementation-evidence/bortus-controlled-perf.json \
  --output docs/implementation-evidence/bortus-controlled-perf-summary.json
python3 -m unittest discover -s benchmarks/bortus-controlled-perf -p 'test_*.py'
node --check benchmarks/bortus-controlled-perf/whole-server.mjs
```

The summary refuses partial, unpaired, duplicate, mixed-driver, changed-fixture or differently constrained sets. Its latency-comparison flag excludes failed inventory/HTTP error outcomes. The tests protect these exclusions and raw-byte archive extraction against line-ending changes and traversal/link entries. They do not claim an application regression pass.

For final integrated qualification, pass its exact committed SHA with a **new** report path and directory. Keep these checkpoint reports intact. The integration owner must identify the final source and reconcile measured regressions and remaining browser/live/image gates; this harness deliberately labels its source as a checkpoint.
