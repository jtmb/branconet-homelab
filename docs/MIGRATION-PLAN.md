# Homelab migration plan

The migration chat owns sequencing, integration and rollout review. BORTUS owns application changes and its checkout reconciliation. Run independent preparation in parallel with at most one bounded worker per phase. Keep production actions and publication within their recorded approvals.

## Current deployment

Flux reconciles the separate charts repository after local validation promotes a revision. Ansible owns repeatable host setup and Flux bootstrap. Kubernetes Secrets hold application credentials. Cluster services use Kubernetes Service DNS for internal dependencies.

Public websites use Cloudflare Tunnel. Plex uses a dedicated MetalLB address and the router's Plex forward. The qBittorrent VPN recovery is deployed through Flux, with VPN port forwarding and Radarr and Sonarr connectivity verified. Keep the download stack behind its VPN startup gate.

## Phase 1 — Ingress security

- Keep the corrected SSH Fail2Ban jail and record verification on each node. Traefik access logging is deployed. Existing LAN probes reached Traefik, but kube-proxy masquerade replaced the client address. Public probes have yet to yield a correlated Traefik entry.
- Review the isolated HTTPS test Service against the Flux charts. Use local traffic policy on an unused test port with the existing Traefik selector. Probe each node from a known LAN client. Verify that Traefik records the client address on both nodes with ready endpoints, that the third node behaves as expected without an endpoint, and that existing LAN and public paths still work.
- Verify public attribution at Cloudflare separately. Enable enforcement only after proving genuine client attribution and where enforcement blocks that traffic. Review the exact routing or security change before rollout. API and DNS changes are excluded from this phase.
- Rollback removes the candidate declaration and explicitly removes the test Service after checking its identity, because Flux pruning is disabled. Recheck the existing routes after rollback.

## Phase 2 — Control-plane and LAN resilience

- Verify the live etcd image and align the backup tooling with it. Produce a protected backup and prove an isolated restore using the existing Ansible workflow. Verify recovered membership and datastore health and rehearse recovery with the material required for encrypted resources. Record the restore result separately from snapshot creation.
- Qualify a stable API address and certificate coverage against the existing control plane before changing node identities. Review kubeadm, inventory, storage and scheduling dependencies. Promote and rename one machine at a time under a reviewed runbook, preserving workload and storage access. Finish with three voting control-plane members and verify quorum, API access, scheduling, Flux and storage during a controlled single-node outage. Stop on failed readiness and recover before advancing.
- Stage shared floating HTTPS and DNS addresses alongside the existing LAN paths. Spread ingress and Pi-hole replicas across nodes, synchronize local DNS records and verify an independent secondary resolver can answer the same local names. Give physical nodes, floating services and resolvers distinct names. Verify DHCP client resolution, trusted HTTPS, Plex, and public tunnels before retiring the old paths. Node, API, DNS and router cutovers each retain their approval gates.

## Phase 3 — Private MCP services and handoff

- Start Kubernetes MCP with read-only workload inventory under a dedicated scoped identity. Verify discovery and invocation in Codex and OpenCode and deny Secret access, exec, port forwarding and writes.
- Qualify read-only operations for Pi-hole, Seerr and Plex against the deployed APIs. Use the same local stdio launcher and ignored environment file for both clients. Keep credentials out of Git and tool output. Review upstream candidates before reuse.
- Keep the Netgear adapter read-only while testing the proposed request-only write workflow. Bind each approval to the exact setting, target and change, enforce expiry and replay protection, and verify before and after state for any separately approved live write.
- Record final acceptance, Ansible and chart ownership, and rollback procedures. Keep BORTUS publication and production acceptance separate. Retire redundant checkouts only after current work is integrated, unique work is recoverable, and ownership and inactivity are verified.

This tracked plan uses role-based names. Operational identifiers, local evidence and credentials belong outside the tracked plan.
