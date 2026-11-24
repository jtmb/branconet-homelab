# Seerr inventory MCP

Run `/usr/bin/python3 -B server.py` over stdio. It imports
`mcp-servers/_shared/read_only_media.py` (bounded GET-only transport) and
`dual_era.py`, and is registered in this repository's `opencode.json`,
disabled by default. The ignored `.env` contains the existing
`SEERR_API_KEY` and must be mode 0600. The adapter sends it only through
trusted private HTTPS to Seerr. Seerr grants administrator authority to API
keys, so protect the local file. This adapter issues fixed GET operations.

Tools read Seerr health, search movies and shows, and list recent request
statuses. The returned fields omit requester identity, tokens, paths and
service configuration. A fourth read-only tool, `seerr_propose_request`,
checks a movie or specific TV seasons against live availability and produces
an exact proposal with a five-minute expiry and an approval digest.

## Operator submission

Keep the MCP read-only. To submit one separately approved proposal, pass its
`proposal` object on standard input to `operator_request.py`, with
`--approval-sha256` set to the exact reviewed digest and `--ledger`
pointing to the persistent SQLite file inside a private operator directory.
It prompts for a request-only Seerr account on the terminal. The session
must have the standard request permission or the corresponding movie or TV
permission. Administrator and auto-approval privileges are refused.

An operator with permission to read the dedicated native Kubernetes Secret can
instead pass it through a separate pipe. Set `APPROVED_DIGEST` to the digest
reviewed for `proposal.json`, and `LEDGER_PATH` to the ledger in the private
operator directory. Run this from the MCP directory in Bash.

```bash
python3 -B operator_request.py --approval-sha256 "$APPROVED_DIGEST" \
  --ledger "$LEDGER_PATH" --credential-fd 3 < proposal.json \
  3< <(timeout 15s ssh -o BatchMode=yes -p 2002 james@192.168.0.4 \
       kubectl -n plex get secret seerr-mcp-requester -o json)
```

The operator command reads the Secret from the pipe and uses the same
request-only session checks. Its approval digest is checked before login.

The command rereads the title, reserves the approval in the ledger before
sending, and reads back the saved request by ID. The result must match the
approved media, seasons, request owner and pending status. If submission is
uncertain, the ledger holds the title for operator reconciliation in Seerr.
The live MCP proposal passed in Codex and OpenCode. Submission and readback
were exercised against an isolated API fixture with a fake account.

The reviewed [upstream Seerr MCP](https://github.com/cyanheads/seerr-mcp-server)
was pinned at `ebf32a13302272fa6aced6decca3765ce1b0b14c`. Its guarded write
flow is a reference for later review. This adapter does not load the upstream
runtime.

## Location, protocol and pooling (2026-11-19)

This server moved from Veyra into `branconet-homelab/mcp-servers/` and is
registered only in this repository's `opencode.json`, with a fixed `cwd`,
`"pool": true`, `"protocol": "2026-07-28"` and `"disabled": true`. It is
dual-era through `mcp-servers/_shared/dual_era.py`: `server/discover` and
modern per-request `_meta` are served statelessly, and a client that opens with
`initialize` gets the previous legacy replies unchanged. Credentials are
re-read from `.env` on every call, so one pooled process serves every directory
in this repository; connect it for a task and disconnect it after.

The committed `lan-root-ca.pem` is the public private-LAN root certificate,
identical to the one in `mcp-servers/pihole-dns/`. Tests:
`python3 -B -m unittest discover -s mcp-servers/_shared/tests -p 'test_*.py'`.

The operator example above still addresses the current masternode
(`192.168.0.4`, SSH port 2002) as documented in `docs/CONNECTING-TO-A-CLUSTER.md`.
