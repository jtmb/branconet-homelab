# BORTUS MCP — agent guide

Read `README.md` first. This directory is the shared credential-aware MCP
for every managed repository; do not create per-repository variants.

## Rules that matter here

- Never add a tool, argument or return path that hands a Secret value or a
  redeemable handle to the caller. The only successful run result is
  `{state, run_id}`.
- Authorization is the runner's job: Unix peer credentials plus a live
  grant. Repository paths, caller-supplied ids, environment variables and
  OpenCode session metadata are not authentication.
- Policy and grant files are operator-owned. Do not relax a check, widen
  `MAX_*` limits or accept a caller-supplied image, command, environment,
  mount, probe or endpoint to make a test pass.
- The inventory child stays read-only and Secret-free. Keep the pinned
  binary hash check and the memfd execution.
- Keep both protocol eras working: modern requests are stateless and legacy
  clients still open with `initialize`. Never make a tool call depend on
  connection state.
- Every new function or test needs a short comment explaining purpose,
  invariants and failure behaviour. Prefer one focused test per contract
  over broad coverage.

## Working on it

```sh
python3 -B -m unittest discover -s tests -p 'test_*.py'
```

Tests must not require a cluster, real credentials or the network. The
real-Docker cases are optional and skip themselves when the socket or the
test image is absent. When you change a contract, update
`docs/planning/operations/02_DOMAIN_AND_PRODUCT_CONTRACTS.md` in the
homelab repository in the same change.

## Do not

- Start the runner or create a real profile/grant without explicit
  operator approval; activation is W3 in the plan.
- Point the runner at `~/.kube/config`, a rootful Docker socket shared
  with the agent, or a Secret whose other keys are not acceptable to the
  runner.
- Log, print or embed a delivered value anywhere, including test output.
