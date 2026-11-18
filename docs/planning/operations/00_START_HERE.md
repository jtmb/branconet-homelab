# Shared BORTUS MCP: start here

**Decision:** One MCP named `bortus`, shared across managed repositories. Keep the three existing inventory tools. Add one tool that retrieves approved Kubernetes Secret keys and uses them in a local Docker smoke run without handing the values to the agent.

**Status:** Implemented and verified on 2026-11-18, with one accepted
residual. The shared `bortus` MCP is live, registered globally, and serves the
three inventory tools plus a gated `bortus_secrets_run`. 29 focused tests pass,
including real-Docker delivery, a real Unix-socket run and a real cluster read
through a ServiceAccount limited to one Secret name. The `bortus-local-test`
skill is installed and triggers in a fresh session. Residual **X1**: the runner
shares this host's only interactive account, which is in `docker` and `sudo`,
so the agent can reach it; that one property is accepted, named and given a
reconsideration trigger rather than claimed. Baseline: homelab `560db763`,
Veyra `3f2c11528`, OpenCode `v2.3.2`.

| Read | What it answers |
| --- | --- |
| [Master plan](01_MASTER_PLAN.md) | What ships, what it looks like, and why |
| [Product contracts](02_DOMAIN_AND_PRODUCT_CONTRACTS.md) | Tool inputs, outputs, grants and run behavior |
| [Architecture and path map](03_ARCHITECTURE_AND_REPOSITORY.md) | Where code runs, what each identity can access, and where files belong |
| [Agent operating kit](04_SKILL_AND_AGENT_DESIGNS.md) | Guidance and OpenCode checks before code |
| [Tool experience](05_DESIGN_AND_ACCESSIBILITY.md) | What an agent and operator see |
| [Security and operations](06_SECURITY_AND_OPERATIONS.md) | Activation, threat model, incident handling and rollback |
| [Roadmap and acceptance](07_IMPLEMENTATION_ROADMAP.md) | First task, work packages and release gates |
| [Fresh-chat handoff](../../memory/08_BORTUS_MCP_HANDOFF.txt) | Paste-ready implementation prompt |
| [Canonical records](../bortus-mcp/records.json) and [planning validation](../bortus-mcp/VALIDATION.md) | Scope, traceability and evidence; the workbook is a derived view |

**First implementation task, after authorization:** inventory existing client registrations and test a secret-free `bortus` registration in a clean OpenCode v2 session. Prove discovery and the runner boundary with synthetic data before giving the runner any Kubernetes Secret access.

**Where it stopped:** every work package is delivered. W0–W2 passed, W3 and
requirement R5/R7 are accepted with residual **X1** recorded in
`records.json` and the tracker: the runner shares this host's only interactive
account (`docker` and `sudo` membership), so on-host secrecy is not
assertable. Evidence: [the implementation record](../evidence/2026-11-18-bortus-mcp-implementation.md).
The residual names its owner, acceptance date and the change that would let a
future run close it: reduce that account's access, or run the runner on a host
the agent cannot administer.
