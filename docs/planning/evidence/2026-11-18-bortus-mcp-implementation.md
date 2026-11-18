# BORTUS MCP: implementation evidence, 2026-11-18

**Scope of this record.** What was actually built and observed in the
shared Veyra checkout (`mcp-servers/bortus/`), the compatibility alias, the
client registrations, and the two project configs. It is not a W3
activation record: no real profile, real grant, cluster Secret read or
operator runner identity exists yet.

| Item | Value |
| --- | --- |
| Veyra source | `mcp-servers/bortus/` (new), `mcp-servers/kubernetes-inventory/launch.py` (now a delegator) |
| OpenCode | `v2.3.2`, global registration `mcp.servers.bortus` |
| Code under test | `policy.py`, `kube.py`, `engine.py`, `runner.py`, `server.py`, `launch.py` |
| Test command | `python3 -B -m unittest discover -s tests -p 'test_*.py'` in `mcp-servers/bortus` |
| Test result | 29 tests, OK, 10.879 s (includes two real-Docker cases and two real-socket cases) |

## What was verified

1. **Inventory parity (R1/R2).** The former `kubernetes-inventory` launcher
   and the new `bortus` launcher were driven with the same MCP handshake.
   Both reported protocol `2025-06-18`, the same three tools
   (`events_list`, `pods_list`, `resources_list`), and an identical live
   `pods_list` table: same header, same three rows, same
   `remainingItemCount: 121`. Only `serverInfo.name` differs (`bortus`).
   The old path now delegates to the shared server and returns the same
   tools and a working live call.
2. **Client discovery (R1).** After adding the single global entry,
   `opencode mcp list` reports `✓ bortus connected`; the homelab session
   listed `bortus` alongside its other servers, and this session's Code
   Mode catalog received `bortus` tools. A live `pods_list` through the new
   registration returned the expected structured inventory result.
3. **One shared entry (R1).** `branconet-homelab/opencode.json` and
   `ruckus_bot/opencode.json` no longer declare `kubernetes-inventory`.
   `ruckus_bot` reports `✓ bortus connected` from the global entry alone.
   An explicitly empty project `mcp.servers` map hides global servers, so
   the whole key was removed rather than left empty.
4. **Run tool gating.** With `BORTUS_RUNNER_SOCKET` unset the tool list is
   exactly the three inventory tools. With it set, `bortus_secrets_run`
   appears; calling it while no runner is listening returns the fixed
   `runtime_unavailable` text and `isError: true`.
5. **Denial, revocation, busy and cleanup (R3/R5/R6).** Synthetic tests
   assert zero cluster fetches and zero container creations for a wrong
   uid, an unknown profile, an expired grant, a malformed request and a
   run that was revoked between fetch and launch. A second concurrent call
   returns `busy` with no additional fetch. A failing `remove` yields
   `cleanup_required` and closes admission for later calls.
6. **Delivery and cleanup in a real container (R4/R5).** Two tests use the
   local Docker engine and `alpine:3.20`: one proves an env value and a
   read-only file both reach the container (the container exits non-zero
   otherwise) and then asserts the container and staging directory are
   gone; the other proves a wrong value fails the check and still cleans
   up. The synthetic marker appears in neither the result nor the audit
   line.
7. **Socket protocol (R3/R6).** The real `runner.serve` loop was started on
   a private socket; `server.RunnerClient` and raw socket frames produced
   `passed`, `not_authorized` and `invalid_request`, with no containers
   left behind.

## Live cluster and container proof (same day, second pass)

A disposable namespace `bortus-mcp-selftest` held one Secret with a random
marker, a ServiceAccount, and a Role granting only `get` on that Secret by
`resourceNames`. A 20-minute token was minted into a 0600 kubeconfig; the
value was never printed. Results:

```
auth can-i get secrets/selftest-secret: yes
auth can-i get secrets/other-secret:   no
auth can-i list secrets:                no
auth can-i get pods:                    no
auth can-i create pods:                 no
auth can-i get configmaps:              no
live Kubernetes read: 1 object, 2 deliveries, value matches
live denial for a non-approved name: CredentialError(unavailable)
runner result: {"state": "passed", "run_id": "19ae14ca488240aa"}
cleanup: no owned containers, staging directory empty
wrong-uid result: {"state": "not_authorized", "run_id": null}
```

That exercised `KubeconfigTransport` against the real API server, delivered
the real cluster value as both an environment variable and a read-only file
into a real `alpine:3.20` container, proved the container compares them, and
proved the value-dependent check fails otherwise. The namespace, its objects
and the temporary kubeconfig were deleted afterwards; no `bortus` container
remains.

Live testing found and fixed three defects the fakes could not: staged files
had to be `0444` (dropping all capabilities removes `CAP_DAC_OVERRIDE`, so a
`0400` file owned by the runner is unreadable in the container), container
removal needed a bounded retry, and the operator `command` limit was raised
from 128 to 512 characters per part (4 KiB total). The test suite now also
asserts that env and file delivery agree, and no longer removes containers
belonging to a concurrent runner.

## W0/R8: the operating skill is installed and triggers

The designed `bortus-local-test` skill is installed in this repository at
`.opencode/skills/bortus-local-test/SKILL.md`. Repository-specific skills stay
in the repository, not in the global config, so the skill is scoped to the
project that owns the plan. It was exercised three ways on OpenCode `v2.3.2`:

- **Explicit load:** a `skill` call with id `bortus-local-test` returned the
  full workflow body with the project path as its base directory, and the
  harness advertised the skill in its available-skill list with the intended
  description.
- **Natural triggering inside the repository:** `opencode run --archived
  --format json` in this repository, prompted only with “I want to smoke-test
  my container locally using the same cluster-backed settings as production
  before I deploy. What is the safe sequence, and which tool do I call?”
  recorded:

  ```
  skill {"id": "bortus-local-test"}
  execute {"code": "return search({namespace:\"bortus\",query:\"secrets_run\"})"}
  ```

  and answered with the fixture-first sequence and
  `tools.bortus.secrets_run({ profile: "<operator-provided-id>" })`, i.e. it
  took the intended branch without being told the skill existed.
- **Negative scope check:** the same prompt in an empty directory outside the
  repository produced no tool calls, no mention of the skill id and no
  `secrets_run` reference, confirming the skill is project-scoped rather than
  globally installed.

Nested guidance resolves (the skill points at the MCP README, the contract
document and `RULES.md`, all present), and fresh-session continuity works
because the probe sessions started with no prior context.

## Accepted residual X1

The only unmet clause in the whole plan is recorded as residual **X1** in
`docs/planning/bortus-mcp/records.json` and in the tracker: the runner shares
the single interactive account on this host, which is in `docker` and `sudo`,
so the agent session can reach the runner, its engine and its memory. The
consequence is stated plainly: “the agent cannot recover a delivered value”
is not enforceable here until that account's access is reduced or the runner
moves to a host the agent cannot administer. Everything else — peer uid
checks, expiring grants, exact-name RBAC, no value in any frame, bounded
runs, verified cleanup — is implemented and tested. The residual names the
owner, the acceptance date, the authority for accepting it, and the
reconsideration trigger.

## Direct reads (added after owner feedback, 2026-11-18)

The first design only offered the guarded runner, which needed a profile, a
grant, a socket and a separate identity before an agent could get anything.
That was more work than pasting the value by hand, so the direct path was
added and is now the default:

```
tools: ['bortus_secret_get', 'bortus_secret_names', 'events_list', 'pods_list', 'resources_list']
names: {"namespace": "bortus-mcp-selftest", "names": ["demo"]}
returned keys: ['token', 'user']
token matches the cluster value: True
value shown to the agent: demo-3521d5e3103a96ca
```

Scope enforcement, same build:

```
out-of-scope read: That Secret is outside this machine's configured scope.  isError: True
```

Enabling it is two lines in the private `.env` (`BORTUS_SECRETS_KUBECONFIG`,
`BORTUS_SECRET_SCOPE`); there is no per-repo, per-session or per-run setup.
The transport reads the existing operator kubeconfig as YAML with its client
certificate, so no token refresh is needed. 35 tests cover scope denial before
any request, key filtering, binary values and name listing. The test namespace
and Secret were deleted after the check.

## Limits and what is still unproven

- No production Secret was read. The live read used a purpose-made test
  Secret, deleted at the end; `kube.KubeconfigTransport` is now proven
  against the real API server with a scoped identity.
- **The runner's own operating-system identity is not established.** There
  is one interactive account (`brajam`), it is in the `docker` group, and it
  is in `sudo`. Creating a second Unix user needs root; more importantly,
  while the agent session holds root-equivalent access on this machine, any
  on-host process separation can be undone from that session, so the
  "agent cannot inspect the runner" property cannot be honestly claimed
  here. This is a property of the host's access model, not a missing code
  path: `runner.py` already checks `SO_PEERCRED`, refuses unexpected uids,
  and owns its socket and Docker socket by path.
- Container-level resistance to a malicious approved image is out of scope:
  a reviewed image that prints its inputs is a boundary compromise by
  definition.
- The global registration is a live client-configuration change. Rollback is
  the backup at `~/.config/opencode/backups/opencode.jsonc.before-bortus-20261118-054242`
  plus restoring `kubernetes-inventory/launch.py` from Git.
