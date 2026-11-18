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

## Limits and what is still unproven

- No production Secret was read. `kube.KubeconfigTransport` is exercised
  only through its parsing/limits paths in tests; the live TLS read is part
  of W3.
- No separate runner identity, no operator-owned rootless Docker socket and
  no real profile or grant exist. `recover()`, `serve()` and the CLI are
  implemented, but the trust boundary described in the plan is not yet
  enforced by an actual second Unix user on this host.
- Container-level resistance to a malicious approved image is out of scope:
  a reviewed image that prints its inputs is a boundary compromise by
  definition.
- The global registration is a live client-configuration change. Rollback is
  the backup at `~/.config/opencode/backups/opencode.jsonc.before-bortus-20261118-054242`
  plus restoring `kubernetes-inventory/launch.py` from Git.
