# Shared BORTUS MCP: start here

**Decision:** One MCP named `bortus`, shared across managed repositories. Keep the three existing inventory tools. Add one tool that retrieves approved Kubernetes Secret keys and uses them in a local Docker smoke run without handing the values to the agent.

**Status:** Implemented and verified through W2, plus a live scoped read, on
2026-11-18. The shared `bortus` MCP is live in the Veyra checkout, registered
globally, and serves the three inventory tools plus a gated
`bortus_secrets_run`. 29 focused tests pass, including real-Docker delivery,
a real Unix-socket run and a real cluster read through a ServiceAccount
limited to one Secret name. One property remains open: the runner's separate
operating-system identity, because this host has a single interactive account
with `docker` and `sudo` membership, so on-host secrecy cannot be asserted
from this session. Baseline for the plan: homelab `560db763`, Veyra
`3f2c11528`, OpenCode `v2.3.2`.

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

**Where it stopped:** W1 and W2 passed; W0 and W3 are partial. The live
proof read a purpose-made Secret through a ServiceAccount limited to that
one name, delivered it into a real container, and cleaned up; the evidence is
in [the implementation record](../evidence/2026-11-18-bortus-mcp-implementation.md).
The one open property is the runner's separate operating-system identity:
this host has a single interactive account that is in `docker` and `sudo`, so
"the agent cannot inspect the runner" is not assertable until that account's
own access is reduced or the runner moves to a host the agent cannot
administer. Everything else the plan asks for is implemented.
