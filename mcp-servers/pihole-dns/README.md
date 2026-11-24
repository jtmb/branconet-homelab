# Pi-hole DNS MCP

Run the stdio server with
`/usr/bin/python3 -B /home/brajam/repos/branconet-homelab/mcp-servers/pihole-dns/server.py`.
The server uses the floating DNS and HTTPS addresses. It verifies the HTTPS
hostname with the Branconet public root certificate copied from the trusted
Windows certificate store.

- `pihole_health` checks the private API plus a local DNS answer and a blocking
  probe over UDP and TCP.
- `pihole_blocking` reads the current blocking state.
- `pihole_local_records` reads local address and CNAME records.

The last two tools require the existing Pi-hole app password in the ignored
mode-0600 `.env` file. Leave Pi-hole app sudo disabled. The server creates a
short-lived session for each protected read, signs out afterward and never
returns session credentials. DNS record edits go through the charts repo.

`lan-root-ca.pem` beside `server.py` is required and is committed (it holds no
private key). It is the public "Branconet Homelab Local Root 2026" certificate (valid to 2031-10-25), SHA-256 fingerprint
`79:B3:CF:11:AE:D6:C4:04:88:5E:55:5C:EF:F3:38:19:FF:A4:CA:53:49:59:F0:0F:80:B1:6E:09:92:7E:2F:AB`.
Check a replacement with `openssl x509 -in lan-root-ca.pem -noout -fingerprint -sha256`.

## Location, protocol and pooling (2026-11-19)

This server moved from Veyra into `branconet-homelab/mcp-servers/` and is
registered only in this repository's `opencode.json`, with a fixed `cwd`,
`"pool": true` and `"protocol": "2026-07-28"`. It is dual-era through
`mcp-servers/_shared/dual_era.py`: `server/discover` and modern per-request
`_meta` are served statelessly, and a client that opens with `initialize` gets
the previous legacy replies unchanged. Credentials are re-read from `.env` on
every call, so one pooled process serves every directory in this repository.
Tests: `python3 -B -m unittest discover -s mcp-servers/_shared/tests -p 'test_*.py'`.
