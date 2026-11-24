# Kubernetes read-only MCP candidate

## Review scope and result

Read the official `containers/kubernetes-mcp-server` Git object at the pin recorded in [LAN resilience and homelab MCP plan](LAN-RESILIENCE-AND-MCP-PLAN.md): `19e48a6d11b274b462f7edfad61553b5ff88bda7`. The local clone reports that exact `HEAD` and the official GitHub origin. It is a deliberate `--no-checkout` source snapshot; review used Git objects without restoring its absent worktree. No code was built or run, and no credentials or client/cluster configuration were accessed.

The upstream is a plausible base for the planned Kubernetes MCP. Its repository license is Apache-2.0; keep the upstream license and attribution in any derived distribution. This is a repository-license check only; no third-party dependency license audit was done. It supports MCP stdio directly, so a shared WSL launcher can technically serve Codex and OpenCode. It is a substantial Go server with many toolsets, so its permissive license and transport fit do not make its defaults safe for this use.

## Minimal useful tool surface

The upstream `core` toolset exposes the relevant generic read operations:

- `pods_list` for a bounded summary of pods across namespaces;
- `resources_list` for namespaced Kubernetes objects, including Deployments, StatefulSets, DaemonSets, Jobs, and CronJobs by API version and kind; and
- `events_list` for cluster events.

The default `list_output = "table"` asks Kubernetes for tabular list output. That is a better initial surface for status summaries than `resources_get`, which returns a full object as YAML. Table columns vary by resource and API; verify the actual fields before acceptance. `events_list` returns event messages, which are workload-originated data and should be treated as untrusted. Upstream documents only best-effort redaction for known credential patterns in MCP log notifications; it does not promise sanitization of tool results.

Flux health can later use `resources_list` for exact Flux API versions and kinds, with RBAC restricted to the required Flux resources. There is no need to enable other upstream toolsets for that. Detailed `resources_get` should stay out of the first slice unless its full-object output has an explicitly accepted data scope.

## Controls required before use

The upstream defaults are too broad: `read_only` defaults to false, the default toolsets include `core` and `config`, and core includes write-capable tools. `read_only = true` only hides tools by their MCP annotations; upstream explicitly states it does not alter Kubernetes permissions. Read-only tools can still read any object the identity may get, including Secrets. The generic `resources_list` can request any API kind that the identity may list.

For the first local configuration, use the equivalent of:

```toml
read_only = true
toolsets = ["core"]
enabled_tools = ["pods_list", "resources_list", "events_list"]
list_output = "table"
```

The explicit tool allowlist, toolset selection, and read-only filter are useful exposure controls, not an authorization boundary. Back them with a dedicated identity and a custom RBAC role limited to `list` on the required workload resources, pods, and events. Exclude Secrets, ConfigMaps, and all write verbs; do not grant pod exec or port-forward permissions. Add `get` only if a later approved feature needs it. Add Flux resources separately for the Flux slice. The upstream getting-started guide offers the built-in `view` ClusterRole as a convenient example; it is broader than this plan’s explicit resource allowlist and should not be copied unchanged.

`denied_resources` can add an application-level deny for Secret kinds, but upstream marks it as a best-effort guardrail. It must not substitute for RBAC. Keep non-core toolsets disabled because some use separate backend clients and do not consult the Kubernetes resource-deny list.

## Credential and client fit

Upstream accepts an explicit `kubeconfig` path. If none is configured, client-go can fall back to `$KUBECONFIG` or `~/.kube/config`; the later launcher must select a dedicated read-only kubeconfig explicitly so an administrator context cannot be chosen by accident. The server does not load the project’s ignored `.env` convention itself. A common WSL launcher can read that file and select the protected kubeconfig path; keep the credential material in the separate mode-0600 kubeconfig rather than in client arguments, TOML, logs, or MCP output.

The binary speaks stdio when `port` is empty and reserves stdout for MCP frames. OAuth is HTTP-only, which is compatible with the plan’s local spawned-process model. The upstream Python wrapper downloads a release binary into `~/.kubernetes-mcp-server/bin/<version>`; its quick-start examples also use `@latest`. That path is not pinned to this reviewed commit and is outside the task-owned output-root convention. Do not use those convenience launch paths for the pinned integration. A later implementation must provide one locally controlled, commit-traceable executable and have both clients invoke the same WSL launcher. Source review establishes protocol fit only; actual Codex and OpenCode discovery remains unverified.

## Smallest next implementation slice and focused checks

Implement only the shared WSL stdio launcher, the three-tool allowlist above, and the matching custom read-only RBAC for workload/pod/event listing. Keep the work separate from deployment or production configuration. Use existing upstream tool-filter coverage rather than adding a new test framework.

When implementation is authorized, the smallest meaningful checks are: (1) process-level MCP `initialize` and `tools/list` show exactly the three intended tools with clean stdout; (2) `kubectl auth can-i` as the dedicated identity confirms list access only for the selected resources and denies Secret reads, writes, exec, and port-forward; (3) one targeted read smoke confirms the returned table fields and event output are suitable; and (4) each client independently discovers and calls the same tools through the WSL launcher. These checks were not run in this source-only review.

## Pinned upstream references

All links below address the reviewed commit, not the moving default branch:

- [Apache-2.0 license](https://github.com/containers/kubernetes-mcp-server/blob/19e48a6d11b274b462f7edfad61553b5ff88bda7/LICENSE)
- [Configuration and cluster authorization](https://github.com/containers/kubernetes-mcp-server/blob/19e48a6d11b274b462f7edfad61553b5ff88bda7/docs/configuration.md)
- [Read-only ServiceAccount example](https://github.com/containers/kubernetes-mcp-server/blob/19e48a6d11b274b462f7edfad61553b5ff88bda7/docs/getting-started-kubernetes.md)
- [`resources_list` and `resources_get`](https://github.com/containers/kubernetes-mcp-server/blob/19e48a6d11b274b462f7edfad61553b5ff88bda7/pkg/toolsets/core/resources.go)
- [`pods_list`](https://github.com/containers/kubernetes-mcp-server/blob/19e48a6d11b274b462f7edfad61553b5ff88bda7/pkg/toolsets/core/pods.go)
- [`events_list`](https://github.com/containers/kubernetes-mcp-server/blob/19e48a6d11b274b462f7edfad61553b5ff88bda7/pkg/toolsets/core/events.go)
- [stdio entry point](https://github.com/containers/kubernetes-mcp-server/blob/19e48a6d11b274b462f7edfad61553b5ff88bda7/pkg/kubernetes-mcp-server/cmd/root.go)
- [Python release downloader](https://github.com/containers/kubernetes-mcp-server/blob/19e48a6d11b274b462f7edfad61553b5ff88bda7/python/kubernetes_mcp_server/kubernetes_mcp_server.py)
- [Tool filtering tests](https://github.com/containers/kubernetes-mcp-server/blob/19e48a6d11b274b462f7edfad61553b5ff88bda7/pkg/mcp/mcp_tools_test.go)
