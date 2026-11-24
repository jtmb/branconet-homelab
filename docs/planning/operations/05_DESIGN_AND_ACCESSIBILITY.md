# BORTUS MCP: what the user sees

No dashboard, public page, accounts, billing or mockups are needed: the interface is an agent tool and short operator instructions. Status uses plain text and a stable enum, never relies on color and works in text-only clients. While an accepted call runs, say which profile is being checked, not which Secret objects it is reading. Do not invent progress or report deployment.

| Situation | What to say | Next action |
| --- | --- | --- |
| User testing edited code | “Local fixture passed; no cluster credentials used.” | For real integration, offer to submit the digest for review |
| Approved live-compatible profile succeeds | “Docker smoke passed; BORTUS used the approved Kubernetes-backed settings.” | State image/profile and run ID from nonsecret operator records; do not suggest deployment occurred |
| Profile missing, disabled or expired | “This run is not authorized.” | Confirm the intended profile with the operator; do not list hidden profiles |
| Another run active | “Runner is busy. No Secrets were fetched for this attempt.” | Ask the operator or retry once later if appropriate |
| Cluster unavailable or missing a key | “Approved configuration could not be loaded.” | Operator uses run ID to identify configuration issue, not raw response |
| Timeout or cleanup failure | “The check did not complete” or “Runner needs cleanup before another run.” | Distinguish `timed_out` from `cleanup_required`; never assume success |

Example request from any managed repo, using a fictitious profile:

```json
{"profile":"local-api-smoke"}
```

The assistant can pair this with its ordinary build/test workflow. No arbitrary interactive terminal, container logs or inspection API is exposed by this tool. The architecture diagram is factual, not a UI concept; see [architecture](03_ARCHITECTURE_AND_REPOSITORY.md).
