# BORTUS MCP: master plan

## What James gets

From any managed repo, ask the agent to run an approved Docker test using Kubernetes-backed configuration. The agent calls `bortus.secrets_run` with a named profile. BORTUS fetches the keys at run time, supplies them to the approved container, runs a fixed check, and reports pass/fail. There is no need to copy passwords, hand-edit an `.env`, or write an MCP server for that repo. A new app needs only an operator-approved profile, not new server code. Kubernetes remains the source of truth; this is not a second vault or a new dashboard.

1. **Build normally.** Use the existing repository build and the same nonsecret settings/entrypoint conventions as production. Build without cluster credentials. For Dockerfiles that need registry authentication, keep it in the existing registry workflow; production application credentials are never build args, layers, or BuildKit inputs in this plan.
2. **Test the edited build with disposable fixtures.** This remains ordinary local Docker. Use synthetic values for edited code that can print, copy, or transmit what it receives. This validates image shape, env wiring and app startup without claiming live authentication.
3. **Check real integration with a reviewed image.** James or the designated operator approves a digest and one profile. The agent can request the run from any repo without seeing credential bytes, and can compare the approved artifact with the one intended for deployment. Prefer Kubernetes-stored dev/test credentials against a test destination; live credentials and live endpoints require explicit approval of exactly that profile and proof of a nonmutating check. An agent can build a candidate for review; it cannot approve it by naming it in a tool call.

| Ships first | Deliberately does not ship |
| --- | --- |
| Shared server name `bortus`; preserve inventory behavior | Separate server installations for each repo |
| One named-profile Docker smoke tool; file or existing env interface | `get_secret` plaintext, `.env` export, arbitrary Docker/Compose or shell |
| Time-bound grants and exact namespace/Secret/key mapping | Auto-discovering Secrets or inferring authority from repo manifests |
| Local-only run, result and cleanup; synthetic and narrowly scoped live gates | Remote vault UI, new authentication service, builds with app secrets, generic long-lived sessions |

Keep the existing pinned inventory backend. Add one local runner with a separate identity, one owner-edited policy, and a private Docker context not shared with the agent. A Unix identity plus an expiring grant is the first scoped key; no API token in chat, repo or tool arguments, and no optional UI to mint keys. If agents need independently revocable grants, give their launch contexts different OS identities; two repos using the same identity intentionally have the same grants.

**Tradeoff:** an app with a secret can always disclose it. A mode-0600 file written under the agent’s own identity, secret-bearing environment variables in agent-controlled Docker, or an opaque reference redeemable in the agent’s shell do not meet this requirement. The one extra boundary—a runner the agent cannot administer—is what makes the rest simple. If the host cannot enforce it, keep the live path disabled rather than promise secrecy.
