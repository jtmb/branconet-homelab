# BORTUS MCP: architecture and ownership

## Data flow

[Standalone data-flow diagram](../bortus-mcp/flow.svg) · [visual provenance](../bortus-mcp/records.json)

```text
Agent in any managed repo → OpenCode stdio → bortus MCP (agent identity)
                                              │
             existing inventory tools ────────┴─→ pinned inventory process
                                                   └─→ Kubernetes list only

             secrets_run(profile) ─→ Unix socket (peer UID checked)
                                          │ privilege boundary
                                          ▼
             owner-edited profiles → private runner → exact-name Kubernetes GET
                                          │
                      approved keys in memory / private tmpfs
                                          ▼
                       private rootless Docker → approved image and probe
                                          │
             only fixed result enum + opaque run ID back to agent
```

Extend the shared Python stdio integration rather than forking the Go inventory server. The wrapper owns the client handshake, forwards only the three approved inventory tools and multiplexes one new typed tool to the runner. Preserve tool schemas and pagination; separate inventory timeouts from the run request. Reuse an existing small JSON-RPC adapter only after checking it supports concurrency, id routing, cancellation and stable capabilities; keep the inventory executable/pin and refresh workflow. Use existing Python 3 stdlib for Unix peer credentials, bounded I/O and TLS; use a fixed private Docker Engine API version negotiated at startup. No runtime dependency downloaded at launch. Validate against the installed Python, Engine API and OpenCode `v2.3.2` before code freeze.

Keep the existing classic stdio handshake during migration, with no connection pooling requirement. OpenCode Code Mode uses `tools.bortus.secrets_run(...)`; a direct tool is named `bortus_secrets_run`. The configured server can start without a runner for read-only migration; the new tool remains withheld until operator-enabled. Reconcile any action-name permissions that refer to `kubernetes-inventory` before removing the old registration. Never treat OpenCode session metadata as authority.

Run the broker and its private rootless Docker engine as a dedicated non-agent Linux user. Reuse a suitable existing Linux execution domain; the boundary applies to the real caller, including shell, Docker, sudo, WSL/Windows interop and management sockets. If Windows/WSL ownership can cross the boundary, those agent sessions are ineligible for live runs until moved into a verified restricted execution context. Rootless mode is not a boundary when the agent can use its socket or become the owner. Never add infrastructure automatically to work around this gate.

| Path | Owner and purpose |
| --- | --- |
| Homelab `README.md`, `docs/README.md`, `docs/planning/operations/` | Plan entrypoints and primary decisions; homelab integrator |
| Homelab `docs/planning/bortus-mcp/` | Canonical `records.json`, validation and reproducible workbook/export source; homelab integrator |
| Homelab `docs/memory/08_BORTUS_MCP_HANDOFF.txt` | One active paste-ready handoff for this work; homelab integrator |
| Veyra `mcp-servers/kubernetes-inventory/` → `mcp-servers/bortus/` | Proposed canonical shared code; retain old launcher path as a compatibility delegator during transition |
| Veyra `mcp-servers/bortus/{launch.py,server.py,runner.py,policy.py,tests/,README.md,AGENTS.md}` | Proposed implementation; launch/wire transport, privileged run, policy validation, focused fixtures and local guides |
| OpenCode user config `mcp.servers.bortus`; existing project/Codex registrations | Global launch with existing client-specific syntax, no per-repo code; migrate existing registrations only after verification |
| Private charts, after approval | Exact-name RBAC and bindings under existing Flux change review; no credential values in Git |
| Runner-owned config, credential, runtime socket and tmpfs outside checkout | Installed by operator; no repo access or sharing with agent; excluded from deliverables |
| Workbook, ZIP, diagram | Derived on demand from versioned planning sources; no generated copies kept in Git; local HTTPS exact routes |

Owner records and usage docs stay with the actual feature. Other repos need no MCP source or profile grants based on path. Local repo settings cannot widen runner policy.
