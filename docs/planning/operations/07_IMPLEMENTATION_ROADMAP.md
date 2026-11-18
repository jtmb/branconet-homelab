# BORTUS MCP: roadmap and acceptance

**Authorization:** This is an execution-ready plan, not approval to install, deploy, change RBAC, access production Secrets, register globally, or run Docker with real values.

| Work package | Owner | Do and record | Done when |
| --- | --- | --- | --- |
| W0 · Operating kit and harness | Integrator | Inventory current repo/global registrations and allow/deny rules without printing secrets; rehearse operating kit in isolated OpenCode v2 and record outcomes | G0: explicit/natural skill use, nested guidance, scope ownership and fresh-session continuity demonstrated; actual client capabilities known |
| W1 · Shared rename and inventory | MCP implementer | Preserve pinned upstream behavior and refresh, implement wrapper, keep old path compatibility; migrate global registration and remove duplicate project entries only with rollout authority | G1: before/after inventory schemas and bounded paginated results match; no Secrets access for inventory; shared discovery from two existing repos; alias rollback rehearsed |
| W2 · Scoped runtime with fakes | Runner implementer + reviewer | Implement policy, peer credentials, Docker injection and bounded cleanup with synthetic data; test relevant HTTP/TLS and Docker error paths, concurrency and timeout | G2: named allow path works, denied cases never fetch, revoked-before-launch run never launches, crash/restart reconciles only owned resources, marker not reachable by caller |
| W3 · Activate a real profile | Operator + reviewer | Prove real UID/engine/WSL/Kubernetes boundaries; pin image/probe and exact RBAC; approve one nonmutating profile against test destination first; use existing chart delivery gate if changed | G3: explicit sign-off, real permission denials, exact namespace/name get only for dedicated identity, observed bounded authorized pass, no raw output, clean runtime afterwards |

## Current state (2026-11-18)

W0, W1 and W2 passed; W3 is accepted with residual X1. Evidence:
[implementation record](../evidence/2026-11-18-bortus-mcp-implementation.md).
The implemented paths are `mcp-servers/bortus/` in Veyra (server, policy,
Secret reader, Docker client, runner, launcher, two test modules) and the
`kubernetes-inventory/launch.py` delegator. The global OpenCode registration
is `mcp.servers.bortus`, and the `bortus-local-test` skill is installed at
`.opencode/skills/bortus-local-test/`; the `branconet-homelab` and
`ruckus_bot` projects no longer declare their own MCP copy.

W3's read path is proven live: a ServiceAccount granted `get` on exactly one
Secret name read it over TLS, delivered it into a real container, was denied
every other name and verb, and left nothing behind. Residual X1 records the
one property this host cannot provide: the runner shares the only interactive
account, which is in `docker` and `sudo`. It is accepted, owned and has a
reconsideration trigger, so it is not an open implementation task. Closing it
means reducing that account's access or moving the runner to a host the agent
cannot administer.

### Focused tests, oracles and fixtures

| Case | Requirement | Oracle and fixture |
| --- | --- | --- |
| Rename + isolation | R1/R2 | Two managed repo sessions with same approved identity discover `bortus`; old path fallback works; inventory permissions deny Secrets, broader mutations |
| Authorization + revocation | R3/R6 | Synthetic in-memory fake and controlled clock; wrong UID/unknown/expired/extra fields make **zero** backend requests. A barrier revokes an accepted run between lookup and launch; zero Docker starts |
| Injection + leak checks | R4/R5/R6 | Mock TLS API supplies a random marker and binary file value; private fixture validates correct file/env bytes. Capture marker absent in every caller-visible channel on pass, timeout and error |
| Trust and Docker parity | R4/R5 | Manipulated caller configuration and changed digest refused. Agent not able to inspect actual runner engine or staging; private approved digest starts with expected production-like settings |
| Cleanup and concurrent calls | R6 | Barrier holds first run open; second returns `busy` with no fetch. Inject uncertain start, disconnect and runner termination; assert owned objects gone, legitimate unrelated resources untouched, cleanup failure keeps admission closed |
| Real enablement | R7 | Operator-approved test profile, actual identities and exact read-only policy; safe pass record and preserved inventory rollback. No live prod snapshot or workload changes to make the check pass |

Use independent fixtures; no test-order dependency, repairs to other owners’ resources, or real Secret values in test output. Keep tests only while their contract is supported, and re-review when identity wiring, auth rules, Docker isolation, or external protocol changes. At each checkpoint record exact revision/config, fixture vs real evidence and first remaining task; do not rotate mid-run or archive unfinished work.
