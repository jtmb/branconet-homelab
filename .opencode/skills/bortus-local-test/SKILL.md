---
name: BORTUS local test
description: Use when testing a managed container locally with Kubernetes-backed settings, adding or changing a BORTUS run profile, or when a local Docker smoke test needs the same configuration production uses.
---

# BORTUS local test

Two ways to get Kubernetes configuration into a local container. Pick the
first unless you have a reason.

## A. Read the values and use them (default)

```
tools.bortus_secret_get({"namespace": "bortus", "name": "some-secret"})
tools.bortus_secret_get({"namespace": "bortus", "name": "some-secret", "keys": ["TOKEN"]})
tools.bortus_secret_names({"namespace": "bortus"})
```

The reply is `{"namespace", "name", "data": {"KEY": "value"}}`; non-UTF-8
keys are listed in `base64_keys`. Use the values for `docker run -e`,
`--env-file`, or a local `.env` that is git-ignored. Never commit them, never
paste them into a tracked file, and delete any temporary copy when done.

Only namespaces and names in this machine's `BORTUS_SECRET_SCOPE` can be read
(`*`, `namespace`, or `namespace/secret` entries). A denial means the scope
line in the MCP `.env` needs that entry — one line, once.

## B. Let the runner use the values without showing them

For a value you do not want in the session at all, an operator can register a
profile and the run tool reports only pass/fail:

```
tools.bortus_secrets_run({"profile": "<operator-provided-id>"})
```

| State | Meaning | What you do |
| --- | --- | --- |
| `passed` | The approved check ran and passed; `run_id` is for correlation only | Report the artifact and state |
| `invalid_request` | Wrong argument shape | Fix the call; do not add fields |
| `not_authorized` | No live grant for this caller/profile | Report it; do not retry or guess ids |
| `busy` | Another run is active | Report it once; do not loop |
| `credential_unavailable` | An approved key could not be read | Report it with the profile id |
| `runtime_unavailable` | Runner or engine not reachable | Report it; do not start Docker yourself to compensate |
| `check_failed` | The container's check failed | Treat as a real failure of the artifact |
| `timed_out` | Budget exhausted | Report elapsed expectation, do not rerun blindly |
| `cleanup_required` | The runner could not verify cleanup | Stop all further runs and report immediately |

## Building

Reuse the repository's existing build and test commands. Application
credentials must not appear in build args, layers, `--build-arg`, Compose build
secrets or a committed file. If the build itself needs registry auth, that is
the existing registry workflow, not this skill.

Test changed code with synthetic fixtures first; use cluster values to prove
the image starts with production-shaped configuration, not to replace a test.

## Reporting

Say which evidence you have: fixture, cluster-backed local run, or deployed
state. A value read through `bortus_secret_get` or a `passed` run does not mean
a deployment happened.

## References

- `/home/brajam/repos/branconet-homelab/mcp-servers/bortus/README.md` — setup,
  runner environment, exact limits.
- `/home/brajam/repos/branconet-homelab/docs/planning/operations/02_DOMAIN_AND_PRODUCT_CONTRACTS.md`
  — tool contract, profile schema, result vocabulary.
- `/home/brajam/repos/branconet-homelab/RULES.md` — agents own routine
  testing; report what you verified.
