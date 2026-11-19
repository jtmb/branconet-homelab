# BORTUS MCP

One stdio MCP for every managed repository, launched as
`/usr/bin/python3 -B <this directory>/launch.py`.

It serves two things:

- the three existing read-only inventory tools (`pods_list`,
  `resources_list`, `events_list`) through the already pinned
  `kubernetes-mcp-server` child, under the inventory identity that cannot
  read Secrets; and
- `bortus_secrets_run`, which is only exposed when `BORTUS_RUNNER_SOCKET`
  is configured. It asks the operator-owned local runner to deliver
  approved Kubernetes Secret keys to one reviewed container and reports a
  fixed result. It never returns a value.

## Files

| File | Purpose |
| --- | --- |
| `launch.py` | Validates the private `.env`, then replaces itself with `server.py`. |
| `server.py` | MCP stdio loop, inventory child proxy, scope check and the tools. |
| `policy.py` | Strict schema for profiles and expiring grants (run tool only). |
| `kube.py` | Bounded Secret reads, name listing, exact-name fetch. |
| `engine.py` | Minimal Docker Engine API client for the private socket. |
| `runner.py` | Optional privileged runner: authorize, fetch, deliver, check, clean up. |
| `tests/` | 46 focused tests, including real Docker, a real socket, scope rules, credential refresh and inventory stream recovery. |

## Two ways to use it

**Direct read (default).** `bortus_secret_get` returns the values so an agent
can build a local `.env` or a `docker run` line immediately:

```
bortus_secret_names(namespace)            -> {"namespace","names":[...]}
bortus_secret_get(namespace, name)        -> {"namespace","name","data":{...}}
bortus_secret_get(namespace, name, keys)  -> only the keys you asked for
```

Reads are limited to `BORTUS_SECRET_SCOPE`: a comma list of `*`, `namespace`,
or `namespace/secret`. Anything outside it is refused before a request is
made. Non-UTF-8 values come back in `data` as base64 and are listed in
`base64_keys`.

**Guarded run (optional).** `bortus_secrets_run` delivers an operator-approved
profile into a reviewed container and returns only `{state, run_id}`, for
cases where the value should never appear in the session at all. It needs a
runner socket, a profile and a grant; none of that is required for direct
reads.

## Protocol and connection reuse

The server is dual-era. A request that carries modern per-request metadata
(`io.modelcontextprotocol/protocolVersion`) is served statelessly under
revision **2026-07-28**: `server/discover` advertises the supported versions,
and `tools/list` returns `resultType`, `ttlMs` and `cacheScope` as that schema
requires. A client that opens with `initialize` keeps the legacy handshake and
receives legacy-shaped results.

That makes the entry eligible for one pooled OpenCode connection per server
across project directories: register it with a fixed `cwd`, `"pool": true` and
`"protocol": "2026-07-28"`. Without pooling, each directory starts its own
copy of the pinned inventory child.

A pooled connection can outlive the inventory token. Before any inventory call
the proxy checks the kubeconfig age; past six hours it runs the existing
refresh helper and restarts the child so the new credential is loaded. A failed
refresh leaves the current child in place and the next call retries.
`launch.py` also refreshes a token older than 30 minutes before starting the
server; that takes about 2-3 seconds over ssh.

**Never let the refresh helper inherit stdin.** stdin is the client's MCP
stream, and the helper's `ssh` forwards whatever it can read to the remote
command. Until 2026-11-19 it did exactly that: with a stale token, OpenCode's
first `server/discover` was swallowed, the pool probe timed out after 30
seconds ("server did not offer pinned protocol version 2026-07-28"), and every
directory fell back to its own connection. Both refresh calls now pass
`stdin=DEVNULL`, the helper's ssh uses `-n`, and
`CredentialRefreshStreamTests` fails if any of the three regresses.

**Inventory replies are capped at 64 KiB** (`MAX_LINE`). `pods_list` and
`resources_list` cover every namespace and have no `namespace` argument, so
narrow them with `fieldSelector` (for example `metadata.namespace=vaultwarden`),
`labelSelector`, or `limit` plus `continue`. An oversized reply comes back as
a tool error saying exactly that. Any failed inventory call (oversized, timed
out or unreadable) restarts the stateless child before returning. Until
2026-11-19 the unread tail of an oversized reply, or a timed-out call's late
reply, was handed to the next caller; `InventoryStreamTests` covers both.

The OpenCode service remembers a pool refusal for a given set of server
settings until the service restarts, so a fixed server keeps per-directory
connections until then. Check with `opencode mcp list` plus the log: a pooled
connection logs `mcp connected server=bortus` without a `directory=` field,
and two directories share one `server.py` process.

## Configuration

`launch.py` reads `.env` in this directory. It must be mode 0600 and owned
by you:

```text
MCP_BINARY=/absolute/path/to/kubernetes-mcp-server
MCP_SHA256=<64 lowercase hex characters>
MCP_KUBECONFIG=/absolute/path/to/inventory.kubeconfig
BORTUS_SECRETS_KUBECONFIG=/absolute/path/to/secrets.kubeconfig   # optional
BORTUS_SECRET_SCOPE=*                                            # or ns,ns/secret
BORTUS_RUNNER_SOCKET=/absolute/path/to/bortus-runner.sock        # optional
```

The first three are the existing inventory settings and are required.
`BORTUS_SECRETS_KUBECONFIG` accepts JSON or YAML kubeconfigs with a bearer
token or a client certificate. Set it and `BORTUS_SECRET_SCOPE` to enable the
direct read tools; leave them out and those tools are not offered. Leave
`BORTUS_RUNNER_SOCKET` out to hide the run tool.

## Checking it

```sh
python3 -B -m unittest discover -s tests -p 'test_*.py'
```

The suite runs offline against fakes and additionally exercises a real
local Docker engine when `/var/run/docker.sock` and the `alpine:3.20`
image are present. Those two cases deliver a synthetic marker into a real
container, prove a missing binding makes the check fail, and prove the
container and staging directory are removed afterwards.

## Operator-side runner

The runner is a separate process started by the operator under an identity
the agent session cannot become. It needs its own environment:

```text
BORTUS_PROFILES=/private/path/profiles.json
BORTUS_GRANTS=/private/path/grants.json
BORTUS_KUBECONFIG=/private/path/runner-kubeconfig.json
BORTUS_RUNNER_SOCKET=/private/path/bortus-runner.sock
BORTUS_RUN_ROOT=/private/path/runs
BORTUS_DOCKER_SOCKET=/run/user/<uid>/docker.sock
BORTUS_AUDIT_LOG=/private/path/audit.jsonl      # optional
```

Start it with `python3 -B runner.py`. It recovers its own labelled
containers before opening admission, then serves the socket. A profile
names one pinned image digest, 1-16 Secret-key bindings, a fixed probe
(`running`, `tcp` or `http`) and a timeout. A grant is one uid, one
profile id and an expiry at most 24 hours away.

## Limits

Runs are serialized (one at a time), capped at 512 MiB and one CPU with
`CapDrop: ALL` and `no-new-privileges`, and every key is limited to 64 KiB
with 64 KiB in total per run. Denied, expired or unknown requests fetch
nothing. A failed cleanup keeps admission closed until the runner can
verify its own resources are gone.
