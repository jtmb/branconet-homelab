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

`.validation/` may already exist as a (gitignored) directory in the
checkout. `ln -s target .validation` then creates a link *inside* it and the
validator writes its report there; check with `ls -la` first and remove only
what the run created.

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
`git ls-remote origin refs/heads/main`) and the full gate passing locally.
Pushing does not publish; run the publisher below, which re-runs the gate on
the exact commit and promotes `validated` for Flux.

## After pushing: publish with the checkout's own publisher

Pushing `main` deploys nothing. Run the checkout's
`scripts/local-publish.py` from WSL with the migration venv (Python 3.12,
PyYAML 6.0.3) and a **fresh** stage for each commit. Verified 2026-11-19 for
charts `0a5cf6f`, `9e6aa2c` and `6f8d1e9`:

```bash
C=/mnt/c/Users/james/AppData/Local/BORTUS/repos/branconet-charts
V=/home/brajam/.local/share/branconet-migration/venv/bin/python
S=/mnt/h/AgentArtifacts/projects/branconet/builds/wsl-artifact-store/files/local-charts-publisher
SHA=<full 40-char sha, equal to local main, origin/main and remote main>
ST=$S/local-charts-publish-$(python3 -c 'import secrets;print(secrets.token_hex(16))')
cd $C
$V -B scripts/local-publish.py prepare --stage-root $S --source-sha $SHA --stage $ST
$V -B scripts/local-publish.py check   --stage-root $S --source-sha $SHA --stage $ST
$V -B scripts/local-publish.py publish --apply --stage-root $S --source-sha $SHA --stage $ST \
  --check-receipt-sha256 $(sha256sum $ST/check.json | cut -d' ' -f1)
```

`check` runs pinned tool versions, all 45 tests and the unchanged validator on
an exact `git archive` export. `publish` atomically moves `validated` and
creates `refs/tags/validated-<sha>`. The earlier `native_wsl_exact_sha_required`
refusal is what the publisher reports when `--source-sha`/`--stage` is missing
or it is not run under Linux; it does not need a separate WSL clone. On a
failed check, read `check.json`'s `checks` array (each entry has an exit code)
before assuming a cause, and do not retry the same stage.

The older Windows local-CI watcher
(`/mnt/f/.../branconet-charts-local-ci-state/status.json`) last ran for
`217f24f` and ended `failed_or_uncertain_no_automatic_same_sha_retry`; do not
rely on it to publish.

Then poll the relevant Flux Kustomization's `lastAppliedRevision` for your
short SHA, force a reconcile annotation if it doesn't show up within ~10
minutes, and if the change touches a pod template, confirm a **new**
ReplicaSet/pod name appeared (not just that Flux applied) — this is the only
proof the change actually reached the running workload.
