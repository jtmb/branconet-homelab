---
name: BORTUS local test
description: Use when testing a managed container locally with Kubernetes-backed settings, adding or changing a BORTUS run profile, or when a local Docker smoke test needs the same configuration production uses.
---

# BORTUS local test

The shared `bortus` MCP delivers approved Kubernetes Secret values into a
reviewed local container and returns only a fixed state. You never receive a
value, a `.env` dump or a handle you can redeem. Follow this order.

## 1. Decide which evidence you need

| Situation | Do |
| --- | --- |
| Code changed in this repo | Build and run it with synthetic fixtures. Do not use cluster values. |
| Need to prove the image starts with production-shaped configuration | Call `bortus_secrets_run` with the operator's profile id. |
| No profile exists yet | Stop. Report that a profile must be added by the operator; do not invent one. |

Never ask for a password, token or `.env` contents, and never read a Secret
with `kubectl` to "just check" something. The point of the profile is that the
value stays out of this session.

## 2. Build without credentials

Reuse the repository's existing build and test commands. Application
credentials must not appear in build args, layers, `--build-arg`, Compose build
secrets or a committed file. If the build itself needs registry auth, that is
the existing registry workflow, not this skill.

## 3. Run the approved profile

```
tools.bortus.secrets_run({"profile": "<operator-provided-id>"})
```

Pass exactly one property. Read the reply:

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

## 4. Report honestly

Say which evidence you have: fixture, cluster-backed local run, or deployed
state. A `passed` run proves the approved image starts and answers its check
with the approved configuration; it does not prove a deployment happened.

Include: profile id, `run_id` when present, image digest if the operator
documented it, and the repository revision you built.

## 5. When something is missing

- Need a new key, namespace or destination: the operator edits the profile.
- Need broader access: that is a policy change, not a test step.
- Runner identity, engine or host problem: report the exact state string and
  stop. Do not create a user, socket, mount, container engine or credential.

## References

- `/home/brajam/repos/veyra-monorepo/mcp-servers/bortus/README.md` — setup,
  runner environment, exact limits.
- `/home/brajam/repos/branconet-homelab/docs/planning/operations/02_DOMAIN_AND_PRODUCT_CONTRACTS.md`
  — tool contract, profile schema, result vocabulary.
- `/home/brajam/repos/branconet-homelab/RULES.md` — agents own routine
  testing; report what you verified.
