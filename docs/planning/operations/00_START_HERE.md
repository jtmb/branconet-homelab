# Shared BORTUS MCP: start here

**Decision:** One MCP named `bortus`, shared across managed repositories. Keep the three existing inventory tools. Add one tool that retrieves approved Kubernetes Secret keys and uses them in a local Docker smoke run without handing the values to the agent.

**Status:** Implemented and verified through W2 on 2026-11-18. The shared
`bortus` MCP is live in the Veyra checkout, registered globally, and serves
the three inventory tools plus a gated `bortus_secrets_run`. 29 focused
tests pass, including real-Docker delivery and a real Unix-socket run. W3 —
a real operator-owned runner identity, real profile/grant and one
nonmutating cluster-backed smoke — is not started. Baseline for the plan:
homelab `560db763`, Veyra `3f2c11528`, OpenCode `v2.3.2`. Existing
repository rules and James’s current direction govern the remaining work.

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

**Where it stopped:** W0 is partial (discovery and registration verified, skill and nested-guidance rehearsal not), W1 and W2 passed, and the evidence is in
[the implementation record](../evidence/2026-11-18-bortus-mcp-implementation.md).
The next task is the W3 operator set-up: a separate runner Unix identity,
a private rootless Docker socket, an approved image digest and probe, exact
`resourceNames` RBAC and one time-limited grant. Until those exist, the run
tool stays hidden and no real Secret is read.
