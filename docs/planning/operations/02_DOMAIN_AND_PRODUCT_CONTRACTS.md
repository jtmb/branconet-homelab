# BORTUS MCP: tool and grant contracts

## C-1 · Tool contract

MCP server key `bortus`; preserve the existing inventory tool names, schemas and results. New tool `secrets_run` has one required property, `profile`, an ASCII identifier of 1–64 characters matching `[a-z][a-z0-9-]*`. Reject extra properties. The server passes the call to the private runner over a Unix domain socket; the runner independently checks the request and caller UID using `SO_PEERCRED`, not claimed repo, user ID, or environment. OpenCode confirmation is optional defense in depth, never authorization.

Successful check response: `{"run_id":"<random UUID>","state":"passed","check":"healthy"}`. Fixed failure states are `invalid_request`, `not_authorized` (including unknown, expired, disabled or revoked), `busy`, `credential_unavailable`, `runtime_unavailable`, `check_failed`, `timed_out`, and `cleanup_required`. After acceptance return `run_id` for correlation; do not return internal exceptions, original probe content/status codes, secret references, user-defined strings, file paths, resource IDs, container IDs, stdout or stderr. MCP errors have fixed messages and a reason enum. Report success only after cleanup.

## C-2 · Operator config and Kubernetes

Installed, versioned, operator-owned profile schema: `id`, `image_digest`, `bindings[]`, `probe`, `egress_policy`, `timeout_seconds`, `runtime_mode`, and explicit `live_approved` (false by default; distinct from a scoped dev grant). Each binding contains `namespace`, `secret`, `key`, `delivery` (`file` or `env`) and destination. File destinations are fixed direct children of `/run/secrets/`; env destinations match `[A-Z_][A-Z0-9_]*`. Reject duplicate destinations and allow env only for reviewed env-only workloads. The operator pins image, existing entrypoint, nonsecret config, and a fixed health check (runner-issued TCP/HTTP readiness or reviewed image health check, with fixed pass/fail only). No agent-supplied code, commands, probe text, environment, image, working-directory mount, endpoint or manifest. The profile and grant store are not writable by the calling UID.

A profile may also pin `command`, a list of 1–8 strings of at most 512
characters (4 KiB in total). It exists for an approved image without a
long-running default entrypoint, is part of the operator policy, and is never
supplied by a caller. Probe kinds are
`running` (process must stay up for 1–30 seconds), `tcp` and `http`; the
network probes require `network: "bridge"` because they use the container's
private address, while an isolated run uses `running`.

A grant is `{uid,profile,expires_at}`. Default TTL 60 minutes, maximum 24 hours; no wildcards. Atomic validated config reload, default deny; use trusted host UTC. The runner checks live grants before any fetch and again immediately before launch. Changes revoke queued/not-yet-started runs; the operator kill procedure handles active runs, since revocation cannot undo earlier use. Launch and revocation must serialize at admission; do not treat a cached grant as current.

An illustrative profile maps `testing/example-client:api_token` to a read-only file `/run/secrets/api_token`, or to `EXAMPLE_API_TOKEN` if the app only accepts env. It selects one approved local `linux/amd64` image by digest, `runtime_mode: test`, `live_approved: false`, a fixed `GET /readyz` returning 2xx, and either no network or an allowlisted test dependency. The approval stores identifiers, never values. `runtime_mode` is `test` or `live`; a live run requires `live_approved: true` **and** a valid UID grant. Keep profile approvals distinct from temporary access grants. Only the designated operator can edit either.

Use one dedicated read identity initially, with namespace Roles granting only `get` on exact Secret `resourceNames` used by activated profiles. No list/watch, write, token creation, exec or port-forward. Use validated cluster CA and a dedicated expiring credential, no fallback to admin `KUBECONFIG`. Fetch each named Secret once per run; Kubernetes reads the entire object, so only the runner enforces key restrictions. Choose Secrets whose other keys are acceptable to that runner; split into dedicated narrowly scoped Secrets with operator approval if needed. Cross-object snapshots are not atomic; never promise a coherent rotating multi-Secret bundle. Fail closed on missing, malformed, oversized or unapproved data. Never persist or cache Kubernetes values between runs.

## C-4 · Direct scoped reads

`bortus_secret_get(namespace, name, keys?)` returns the values so an agent can
build a local env file or a `docker run` line in one call. `bortus_secret_names(namespace)`
lists what exists. Both are enabled only when `BORTUS_SECRETS_KUBECONFIG` and
`BORTUS_SECRET_SCOPE` are set; otherwise the tools are not offered at all.

`BORTUS_SECRET_SCOPE` is a comma list of `*`, `namespace`, or
`namespace/secret`. A request outside it is refused before any API call, with
a fixed message. The kubeconfig's own identity (bearer token or client
certificate) is the second limit: a 403 is reported as a permission error.
Values are UTF-8 text in `data`; a value that is not valid UTF-8 is returned
base64-encoded and named in `base64_keys`. Arguments are strict: unknown
fields, invalid names, more than 64 keys and unknown keys are rejected.

This path returns real values to the caller on purpose. It replaces the older
"ask a human to paste it" workflow; the guarded `bortus_secrets_run` path
stays available for values that must not appear in the session at all.

## C-3 · Run, failure and lifetime

Default one active run total; other requests receive `busy` without fetching any Secret. Limit to 16 bindings and 64 KiB total selected decoded data, a bounded Kubernetes response per object (2 MiB), 5 seconds for a Kubernetes read, and 120 seconds total for one run, default 60. No automatic retries. For env, validate UTF-8 with no NUL and apply via the private Docker API, not a shell or `.env`; for files, support bytes via read-only mounts staged on runner-only tmpfs. Never pass inputs through process arguments. Logs disabled, no exposed ports, and no user-supplied bind mounts; only fixed approved network access if the check requires it.

Run state: validate → authorize → reserve → fetch → stage → recheck and launch → probe → remove container and staging → return. No container if fetch/stage fails. On caller disconnect, cancel and clean up; where disconnect detection is delayed, hard timeout still applies. On uncertain create/start, reconcile the owned run label before returning or allowing another run; never rerun blindly. A separate runner cleanup path handles shutdown and startup after crash: remove only containers from its dedicated engine with its exact ownership label, clean only its own staging in the private root, then reopen admission. Cleanup failure leaves admission closed with `cleanup_required`. Docker env values may be visible in private engine metadata until removal; the engine and its files are inside the trusted boundary and excluded from user-accessible logs/backups.
