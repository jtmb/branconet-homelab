# Plaintext port restriction and mesh enrollment

Two related but separate hardening layers exist on this cluster:
**nftables restriction** of plaintext ports to known consumers, and
**ambient mesh (Istio) enrollment** of individual workloads.

## nftables plaintext restriction

### Why node-level, not just NetworkPolicy

Several plaintext ports are either host listeners (not Kubernetes Services)
or published via `externalIPs`, which NetworkPolicy does not cover.
`scripts/migration/plaintext_restriction.py` installs one nftables table per
profile on all three nodes via
`k8s-rewrite/ansible-playbook/playbooks/plaintext-restriction.yml`.

### Two hook types

- **`input` hook at priority -10** — for ports the node itself listens on
  directly (Cockpit 9090, MetalLB speaker metrics 9120/32158/32359-style
  health-check ports). The packet is delivered locally, never rewritten, so
  `tcp dport` sees the real port.
- **`prerouting` hook at priority -110** — required for any port reached via
  a Kubernetes Service `externalIPs` publication. kube-proxy rewrites the
  destination to the pod address/port in the NAT hook at priority -100, so
  **any** rule placed at `input` or `forward` only ever sees the *translated*
  pod port. Two lessons, both learned the hard way:
  - At the `input` hook this traffic is invisible entirely (discovered on
    `pihole-exporter`).
  - At the `forward` hook it is visible but carries the **pod's** port, not
    the published one. Every profile whose published port differs from its
    pod target port was therefore a silent no-op (2026-11-18 finding:
    vaultwarden 8096→80, mealie 8089→9000, aplb 8082→80,
    minecraft-website 8083→80, web-apps 8080/8081→80, ruckus-bot
    8088→8080 — operator traffic passed with every rule counter at zero,
    so the restriction had never engaged). The fix is not a smarter selector
    at `forward` — the nodes' nftables 1.0.2 predates `ct original proto-dst`
    — but matching **before the rewrite**, in `prerouting` at -110, where
    `tcp dport` is still the port the client originally contacted.
  - Prerouting sees every entering packet, so those rules are additionally
    scoped to the three node IP destinations (`ip daddr`); pod or node
    egress to any other address on the same port is untouched.

### NetworkPolicy on an `externalIPs` pod sees two different sources

The node nftables profile and a pod's NetworkPolicy do not see the same
source address. If a client enters at the node hosting the pod, Calico checks
policy before kube-proxy's SNAT and sees the real client, for example the
operator host `192.168.0.13`. If it enters at another node, the pod receives it
SNATed to that node's Calico tunnel address. ztunnel sees the post-SNAT
address in both cases. A NetworkPolicy for a published port must therefore
list the clients this profile admits as well as the node and tunnel
addresses. Found on 2026-11-19 when vaultwarden's `:8096` failed only through
node01; see the charts repository's `docs/NAMESPACE-NETWORK-POLICIES.md`.

### The pod-CIDR trap

A prerouting profile that only allows LAN/operator addresses will reject
**in-cluster callers**, because Service traffic from pods arrives with a
**pod-network source address** (`10.244.0.0/16`). Every prerouting profile
must allow `10.244.0.0/16` in addition to loopback, the three node IPs, and
the operator host, or it silently breaks pod-to-Service traffic through
that port while looking like it only restricted external access.

### Current inventory (identical on all three nodes)

| Profile | Ports | Hook | Notes |
|---|---|---|---|
| `core` | 32158, 32359, 9090 | input | MetalLB health-check ports, Cockpit |
| `pihole-exporter` | 9617 | prerouting | No in-cluster scraper existed; pods use the ClusterIP |
| `ruckus-db` | 3306 | prerouting | |
| `ruckus-bot` | 3003, 8088 | prerouting | Both published ports of one Service must be covered together |
| `mealie` | 8089 | prerouting | |
| `minecraft-website` | 8083 | prerouting | |
| `aplb` | 8082 | prerouting | |
| `web-apps-local` | 8080, 8081 | prerouting | Only node-self traffic observed; pod CIDR still included for safety |
| `vaultwarden` | 8096 | prerouting | Deferred pending owner decision (sporadic external sync clients), then approved and applied |

Deliberately **not** restricted: Plex (32400, real external/LAN clients),
LAN DNS (53, real LAN+pod clients), Traefik ingress ports, kubelet/API
server ports (already TLS).

### Measurement method before restricting a port

Use `conntrack -L --dport <port>` (not `ss`) for any `externalIPs`-published
port — `ss` only sees locally-terminated sockets and cannot see NAT'd
forwarded traffic. A 60-120 second window is the historical sampling
duration; it cannot rule out an infrequent client, so a restriction is a
judgment call on measured absence, not proof of absence.

### Boot persistence

nftables rules are **runtime-only by default** and do **not** survive a
reboot. `branconet-plaintext-restriction.service` (installed by
`playbooks/plaintext-restriction-persist.yml`, a `oneshot`,
`RemainAfterExit=yes` unit on `multi-user.target`) re-applies every profile
via `scripts/migration/apply-all-plaintext-restrictions.py` on every boot.
Verified across a real node02 reboot: all 9 tables returned with no manual
intervention.

### Operator-host dependency

Every profile allowlists one operator host IP, `192.168.0.13`
(`scripts/migration/plaintext_restriction.py:ALLOWED`). Verified 2026-11-18:
the LAN DHCP server actually in use is `branconet-lan-dhcp.service` on node03
(not the router), and its `/etc/branconet-lan-dhcp.conf` reserves it with
`dhcp-host=04:7c:16:bb:21:5c,192.168.0.13,24h` (source:
`playbooks/lan-dhcp-handoff.yml`). The Windows operator adapter has that
hardware address, holds `192.168.0.13` from DHCP server `192.168.0.5`, and
reaches the restricted port 8096 on all three nodes. If that adapter is ever
replaced, update the reservation and the allowlist together.

### Traefik dashboard certificate (`proxy.branconet.lan`)

The dashboard route lives in the native Secret `traefik/traefik-dashboard-config`
(file provider) with `tls: {}`, meaning "use any certificate in Traefik's
store that matches the name". Until 2026-11-18 none matched, so browsers got
Traefik's self-signed "TRAEFIK DEFAULT CERT". Private charts
`flux/releases/foundation/proxy-dashboard-tls.yaml` now issues
`proxy.branconet.lan` from `branconet-local-ca` (Secret
`traefik/proxy-dashboard-tls`) and loads it into Traefik's store through a
TLS-only anchor Ingress whose rule is a `.invalid` host on the internal
`health` entrypoint, so it can never receive traffic. The route, its sign-in,
and the Traefik Deployment are untouched; cert-manager renewals reload
automatically. Verified: chain to the home-network root, Windows trust store,
`401` sign-in prompt still enforced, other `.lan` sites unchanged, anchor
host `404`.

### Rollback

`k8s-rewrite/ansible-playbook/playbooks/plaintext-restriction.yml` with
`--extra-vars "restriction_profile=<name> restriction_action=remove"`, or
disable `branconet-plaintext-restriction.service` to stop reapplication on
reboot.

## Ambient mesh enrollment

Enrollment is per-pod-template label (`istio.io/dataplane-mode: ambient`),
not always per-namespace — a shared namespace with non-mesh-safe workloads
(host network, in-pod VPN) is enrolled at the individual Deployment level
instead.

| Workload | Enrolled | Reason |
|---|---|---|
| `bortus` | Yes, STRICT mTLS | Own namespace, qualified PERMISSIVE→STRICT |
| `bazarr`, `sonarr`, `radarr`, `tautulli`, `jackett`, `flaresolverr`, `xteve` | Yes, pod-level | `plex` namespace also hosts VPN/host-network workloads |
| Previously-ambient set (`homepage`, `http-echo`, `mesh-pilot`, `website-stack`, `whoami`, `mealie`, `ruckus`, `vaultwarden`, `web-apps`) | Yes | Default-deny via `AuthorizationPolicy action: ALLOW` entries |
| `qbittorrent` | **No** | Terminates Proton WireGuard inside the pod (`tun0`); routing its egress through ztunnel risks a VPN leak |
| `xteve-ssdp` | **No** | `hostNetwork: true` Deployment for SSDP discovery; ambient redirection does not apply cleanly to host-network pods |
| Pi-hole | **No** | ztunnel has no UDP listener; an enrolled pod's `ISTIO_OUTPUT` captures **all outbound UDP** (a DNS-client interception pattern), which would break a DNS **server**'s replies to LAN clients with zero coverage gain. The advertised LAN VIP makes this a LAN-wide availability risk for no benefit. |

### The ambient HBONE port 15008 trap

An **enrolled** pod's ingress NetworkPolicy must allow TCP **15008** (the
ambient HBONE port) from any peer expected to reach it, in addition to the
application port. Enrolled→enrolled traffic goes over HBONE to 15008, not
directly to the application port; a NetworkPolicy written before enrollment
(allowing only the app port) will silently break every same-namespace caller
once the target pod is enrolled. (Found via `flaresolverr`'s pre-existing
`podSelector {}`-only policy.)

### Verifying enrollment actually worked

Check the **pod** (not the Deployment) for the
`ambient.istio.io/redirection=enabled` **annotation** — it is not a label,
and it only appears after the pod is recreated post-enrollment (existing
pods don't retroactively redirect).
