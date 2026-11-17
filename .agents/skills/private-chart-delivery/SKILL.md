---
name: private-chart-delivery
description: Use when editing or publishing the private branconet-charts repository (flux/, scripts/test_certificate_candidates.py, scripts/validate.py). Covers the 44/45-test gate, the Windows git workflow, the local-CI publisher, and the pod-restart gap.
---

# Private chart delivery

The private charts repository lives at
`/mnt/c/Users/james/AppData/Local/BORTUS/repos/branconet-charts` in WSL
(Windows path `C:/Users/james/AppData/Local/BORTUS/repos/branconet-charts`).
It is a separate repository from `branconet-homelab`, with its own git
history, remote, and CI gate. Never edit it through the WSL `git` binary —
use the Windows git binary so credentials and line endings match the
existing workflow (see below).

## Before editing

1. Read the file you're changing in full; most resources carry byte-pinned
   tests (`scripts/test_certificate_candidates.py`) that assert exact
   content, not just shape. A pin existing for good reason (drift
   detection) — update it deliberately and explain why in the pin's own
   comment, never loosen it to a wildcard.
2. Check whether your change touches a Deployment pod template. Flux does
   **not** restart a pod when only a ConfigMap or Secret changes — the
   template itself must change (e.g. a `checksum/<name>` annotation) or
   nothing reaches the running pod until a manual `kubectl rollout restart`.
   Native Secrets (passwords, tokens) are usually rotated out-of-band from
   Git on purpose (see `native-secret-change` skill) and restart themselves
   directly; only Git-managed ConfigMaps need a checksum annotation.

## Running the gate locally

Use the retained H toolchain via symlinks, never install/copy tools:

```python
pub = Path(json.loads((STAGE.parent/'credential-bootstrap-publisher-result.json').read_text())['stage'])
tools = pub / 'source/.tools'
(repo/'.tools').symlink_to(tools, target_is_directory=True)
(repo/'.validation').symlink_to(some_scratch_validation_dir, target_is_directory=True)
# env: PYTHONDONTWRITEBYTECODE=1, TMPDIR/TMP/TEMP=scratch, GOMAXPROCS=2, PATH=tools:$PATH
# run: python3 -B -m unittest discover -s scripts -p test_*.py
# then: python3 -B scripts/validate.py
# always unlink .tools/.validation afterward, even on failure
```

**The test count is pinned twice** — once implicitly (the suite just has N
tests) and once explicitly, in a *separate* repository:
`C:/Users/james/.codex/local-ci/branconet-charts-local-ci/scripts/local-publish.py`
hardcodes `int(match[1]) == N` as a tamper-evidence guard on its own CI
watcher. If you add or remove a test, the local gate will pass but the
real publisher will fail with `check_failed_no_publication_raw_output_withheld`
/ `all_N_existing_..._required`. Update the count in that file too — it is
the *same* `branconet-charts` origin, just a dedicated clean clone that
fast-forwards from `origin/main` before each publish attempt, so pushing
your count-update commit to `main` is sufficient; don't edit files inside
that dedicated clone directly.

## Committing and pushing

Use `git commit --only -m "..." -- <paths>` (via the Windows git binary, with
retries for transient `GCM_INTERACTIVE`/network failures) to commit **only**
the paths you touched. This repository deliberately carries a large body of
unrelated staged/uncommitted work (watch for files showing `MM` — staged
*and* unstaged — meaning someone else's in-progress change already touched
the same file; diff `--cached` vs working tree before editing to avoid
silently reverting it). Never `git add -A` or plain `git commit` here.

Push directly to `main` (`git push origin <sha>:refs/heads/main`) only after
the parent check (`git rev-parse HEAD` must equal
`git ls-remote origin refs/heads/main`) and the full gate passing locally —
pushing triggers the real publisher, which re-runs everything and actually
promotes the `validated` tag and lets Flux apply it.

## After pushing

Poll `status.json` at
`/mnt/f/branconet-migration-artifacts/maintenance-storage-20261025/branconet-charts-local-ci-state/status.json`
for `sourceSHA` matching your commit and `finishedUTC` set. On failure, read
`check.json` in the referenced stage directory for the `checks` array (each
entry has its own exit code) before assuming the cause — don't guess or
retry blindly; the watcher explicitly refuses automatic same-SHA retries.

Then poll the relevant Flux Kustomization's `lastAppliedRevision` for your
short SHA, force a reconcile annotation if it doesn't show up within ~10
minutes, and if the change touches a pod template, confirm a **new**
ReplicaSet/pod name appeared (not just that Flux applied) — this is the only
proof the change actually reached the running workload.
