# Homelab migration plan

The migration chat owns sequencing, integration and rollout review. BORTUS owns application changes and its checkout reconciliation. Run independent preparation in parallel with at most one bounded worker per phase. Keep production actions and publication within their recorded approvals.

## Current deployment

November 15 OpenCode setup: the four requested infrastructure MCPs and the
official local Agent Browser MCP are connected and exercised in this WSL
checkout. See `docs/LAN-RESILIENCE-AND-MCP-PLAN.md`, “OpenCode WSL registration,”
for checks, token refresh and runtime ownership. Free/self-hosted certificate
and workload-authentication hardening was delivered on 2026-11-16 (below).
James chose to keep current names and secure this cluster only (November 15).
Retain private-CA trust for `.lan`, Kubernetes CA trust for the API, and existing
public-domain routes. Cross-cluster federation is outside this rollout.
The saved TLS/workload-authentication plan below is complete (2026-11-16).

Flux reconciles the separate charts repository after local validation promotes a revision. Ansible owns repeatable host setup and Flux bootstrap. Kubernetes Secrets hold application credentials. Cluster services use Kubernetes Service DNS for internal dependencies.

Public websites use Cloudflare Tunnel. Plex uses a dedicated MetalLB address and the router's Plex forward. The qBittorrent VPN recovery is deployed through Flux, with VPN port forwarding and Radarr and Sonarr connectivity verified. Keep the download stack behind its VPN startup gate. The direct node WebUI shared one NAT source address across browser and automation attempts. The existing desktop account authenticated through the trusted LAN HTTPS hostname. Radarr and Sonarr now use the internal WebUI Service with the verified working account. Their saved connection tests passed, and the scoped Ansible repair reran with no changes.

LAN HTTPS uses a private, name-constrained root CA for the two local DNS suffixes. Flux declares the issuer and certificates, cert-manager renews the server certificates, and Traefik serves them. The Windows user trusts the public root. The private key stays in Kubernetes. Kubernetes API trust uses its separate cluster CA. Pods that call a LAN HTTPS endpoint need the public LAN root through their client-specific trust configuration. Plan a root rollover with overlapping client trust and explicit server certificate reissuance.

## Saved TLS and workload-authentication plan — 2026-11-15

James requested that this plan be saved after MCP setup, then asked for it to
be completed. **Status 2026-11-16: all six steps executed and verified;** see
"Delivered outcome" below for exact scope and residual exceptions.

### Accepted scope

- Use free, self-hosted components and execute directly without subagents.
- Keep current service names, including the existing `.lan` names and public
  Cloudflare-domain routes. Do not introduce `home.jtmb.cc`.
- Secure this existing three-node Kubernetes cluster. Cross-cluster federation
  is deferred until another cluster is explicitly brought into scope.
- Retain private-CA certificates for `.lan` and separate Kubernetes-CA trust
  for kubectl/API access. Public ACME certificates cannot cover `.lan`.
- Preserve production data, credentials, application resource limits, private
  chart delivery, disabled GitHub Actions and the established recovery contracts.
- Reuse the existing checkouts and H artifact roots within their storage limits.

### Completed foundation

The Kubernetes, XR500, Pi-hole, Plex and Agent Browser MCPs are registered and
connected. Actual authenticated reads, Kubernetes Secret-list denial, and
isolated browser navigation/snapshot/close passed. All observed cluster nodes,
HelmReleases and cert-manager Certificates/ClusterIssuers were Ready.
MCP setup details and verification are in `docs/LAN-RESILIENCE-AND-MCP-PLAN.md`.

### Remaining implementation sequence

1. **Verify compatibility and capacity.** Refresh the actual private chart head,
   publisher ownership, node health and resource requests. Inspect Calico's
   effective dataplane, CNI paths, existing NetworkPolicies and application
   communication dependencies. The Metrics API was unavailable at inspection;
   use existing read-only node observations rather than assume spare capacity.
2. **Check existing TLS trust and renewal.** Verify hostname/CA validation,
   expiry and renewal for LAN HTTPS and the API, preserving current names.
   Keep public-domain certificate handling distinct from workload identity.
   Fix demonstrated trust or renewal gaps without replacing working trust roots.
3. **Prepare a bounded workload-mTLS pilot.** Upstream Istio ambient is the
   candidate, not a deployed decision. Istio 1.32 lists Kubernetes 1.37 as
   supported; pin and verify the selected release and images before use.
   Review Calico interaction, resource overhead, service-account identities,
   certificate issuance/rotation and explicit authorization rules. Use a
   separate workload trust domain/CA rather than the LAN or Kubernetes CA.
4. **Validate and deploy the isolated pilot.** Use the existing private
   exact-source validation → validated revision → Flux path, with Ansible for
   any required host configuration. Use disposable workloads without production
   claims. Prove allowed identities succeed, unauthorized identities and
   plaintext fail under strict mTLS, and certificate rotation and pod replacement
   preserve expected access. Verify recovery/rollback before wider enrollment.
5. **Enroll production incrementally.** Map required callers before enforcing
   policy, then roll out one bounded application group at a time. Verify
   ingress, Cloudflare Tunnel, health probes and application integrations.
   Treat DNS/UDP, host-network workloads, storage/control-plane components,
   direct LAN clients and VPN-sidecar traffic explicitly; an ambient TCP mesh
   does not automatically secure those paths. Preserve existing VPN leak
   protection and record every exception and its actual protection.
6. **Verify and document the delivered scope.** Record the exact chart/image
   revisions, actual authenticated/encrypted paths, denied paths, renewal
   behavior, resource impact and rollback procedure. Recheck existing LAN/public
   endpoints and retained data. Clean only verified obsolete task-owned output.
   Keep unmet coverage visible rather than claim cluster-wide mTLS from a pilot.

### Delivered outcome — 2026-11-16

1. **Compatibility/capacity (done).** Charts head `e511f1c`; Calico 3.33 manifest
   install, IPIP, iptables-nft, kube-proxy iptables; all Istio kernel modules
   present on the three nodes; no prior mesh CRDs. node02 (4 CPU) had 3.63 CPU
   requested, so DaemonSet requests were set to 50m each. Istio 1.31.4 chosen
   (supports Kubernetes 1.37, no known CVEs; 1.32.0 was six days old).
2. **TLS trust/renewal (done).** LAN HTTPS: 22 hostnames pass private-CA +
   hostname validation; a forced cert-manager renewal reissued and Traefik
   served the new serial. Gaps found and fixed: (a) nothing renewed kubeadm
   certificates — added a read-only expiry check and runbook (earliest
   2027-10-09); (b) API servers did not verify kubelets — kubelets now use
   cluster-CA serving certificates and all API servers verify them. Details:
   [CLUSTER-TLS.md](CLUSTER-TLS.md).
3. **Pilot prepared (done).** Upstream charts vendored unchanged into the
   private charts repo with provenance; digest-pinned distroless images;
   istiod ×2 (self-signed mesh CA to 2036, separate from LAN and cluster CAs).
4. **Pilot validated (done).** Through the private publisher and Flux
   (`d2a9aaa`): allowed identity 200, unapproved identity and plaintext refused,
   preserved across istiod loss, pod replacement and ztunnel restart (new leaf
   serial); live enroll/unenroll without restart.
5. **Production enrolled (done, bounded).** Traefik (ingress mode: inbound
   uncaptured, so Fail2Ban client addresses are unchanged), cloudflared (own
   ServiceAccount) and eight app namespaces: homepage, http-echo, mealie, ruckus,
   vaultwarden, web-apps, website-stack, whoami. Callers were mapped from
   ztunnel records before ALLOW policies were enforced (`142ec25`); STRICT where
   no plaintext LAN path exists; direct node-IP ports remain plaintext only from
   node/tunnel addresses. **Not enrolled, by design:** plex (VPN sidecar
   firewall, MetalLB/SSDP discovery), pihole (LAN DNS/UDP), bortus (admission
   guards need separate qualification), ingenium (separate owner) and all
   infrastructure namespaces. Ambient L4 does not cover UDP or host-network pods.
6. **Verified and documented (done).** 55 routes matched baseline after each
   phase; unauthorized pods refused by every enrolled app; footprint ztunnel
   5–7 MiB, istio-cni 15–18 MiB per node, istiod 53–61 MiB per replica. Istio
   releases use `reconcileStrategy: ChartVersion` so unrelated charts commits do
   not roll ztunnel (proven: generations unchanged across a later commit). Final
   charts revision `c57a3a5`, all six Flux Kustomizations Ready. Private charts
   `docs/WORKLOAD-MESH.md` holds the enrollment rules, policy table and
   rollback. Disposable namespace and 327,560,709 bytes of reproducible
   downloads/copies were removed; scripts, evidence and `istioctl` remain under
   the H `branconet-history/workload-mesh-20261116` directory.

Future, outside this plan's accepted scope: enroll plex/pihole/bortus only
after their own qualification; run the certificate expiry check before
2027-07-11; approve kubelet-serving CSRs at rotation.

## Saved follow-up plan — BORTUS Certificates & Trust and network hardening

James requested this feature and follow-up roadmap, then asked to save the
discussed plan. **Status: implementation in progress; see execution state below.**
Saving the plan did not enable automation, approve CSRs, retire resources,
commit existing changes or enroll additional workloads. The earlier TLS rollout
remains completed; this is its next delivery scope.

### Scope and boundaries

**Execution clarification, 2026-11-16:** James instructed: “stop asking for
approval. The plan is in stone. Deliver.” Proceed through this accepted plan,
including existing private immutable delivery and bounded integration/staged
rollout, without repeated approval prompts. Earlier preparation-only approval
holds are historical. This does not waive actual validation/acceptance,
preservation, resource ceilings, private-only transport, disabled Actions or
the requirement to reconcile uncertain outcomes. Ask only for a genuinely
missing external input; never substitute a local pass for live acceptance.

- Free/self-hosted components, this cluster only, current service names and
  trust roots retained; execute directly without subagents.
- Preserve production data, credentials, existing resource limits, admission
  protections, private chart validation/promotion/Flux delivery, disabled GitHub
  Actions and recovery contracts.
- Reuse the existing authoritative WSL checkout, private charts checkout,
  compatible dependencies and H output roots within the combined repository
  allowance. Do not create another checkout or blanket-stage existing work.
- BORTUS provides management and visibility. Certificate authorities and their
  controllers retain issuance ownership; no CA keys enter the dashboard.

### Feature: Certificates & Trust

Add a sidebar page using BORTUS's existing dark styling, accessible controls,
tables, detail views and permission model.

| Area | Information and controls |
| --- | --- |
| Overview | Expiring certificates, failed renewals, pending requests, automation health and stale monitoring |
| Certificates | Hostname/node, issuer, expiry, renewal owner, consumers and last verified time |
| Certificate requests | Requesting node, requested identities, validation results, approval and issuance status |
| Automation | Enable/pause policies, maintenance windows, thresholds and notifications |
| History | Actor, policy changes, job steps, outcomes and recovery actions |

Distinguish **approved → issued → installed → verified**; approval alone is not
successful renewal. Show desired policy separately from effective state, and
unknown/stale data separately from healthy data. Include loading, empty,
failure, disabled and recovery states, keyboard focus and screen-reader
announcements.

Authenticated readers inspect metadata. Mutations require fresh operator
authorization (`requireOperator`, not write role alone), with backend enforcement
and an audit trail. Private keys and credentials never enter UI responses,
SQLite, Git, command arguments or logs. Store only necessary policy, operation
and observation metadata.

### Certificate lifecycle automation

**Kubelet serving certificates**

Automatically approve legitimate serving-certificate renewals for enrolled
nodes, replacing recurring manual invocation of
`scripts/migration/approve-kubelet-serving-csr.py`.

Before enabling unattended approval, replace that helper's text-based parsing
and subject substring comparison with strict certificate-request validation:

- Exact requester, subject, signer and permitted usages.
- Valid request signature and acceptable cryptography.
- Requested DNS/IP identities matched against enrolled node identity and
  trusted inventory; reject unexpected identities, extensions and
  client-certificate requests.
- Recheck the current CSR and node before approval, including object identity
  and concurrent changes; make retries idempotent.
- A recreated node or unexpected address change requires attention rather
  than silently inheriting approval.
- Verify issuance and that the node actually presents the new certificate.
  Leave invalid/ambiguous requests unapproved with actionable reasons.

Use a dedicated narrowly permissioned CSR controller, scoped to the intended
signer and approval operations; never grant blanket certificate approval or CA
signing access. Begin in observation mode and enable automated approval only
after positive and negative validation.

**LAN and mesh certificates**

Keep cert-manager and Istio responsible for issuance and normal renewal.
BORTUS monitors renewal health, reports failures, provides supported renewal
actions where appropriate, verifies the certificate actually served, and
tracks CA expiry separately. Use certificate-type-aware thresholds: 24-hour
mesh leaves cannot share annual control-plane expiry rules.

**Control-plane certificates**

Schedule expiry checks and provide a UI-managed renewal workflow:

1. Check expiry, node health and etcd quorum.
2. Verify a fresh recovery checkpoint.
3. Renew within the configured maintenance window.
4. Process one control-plane node at a time.
5. Verify API readiness, certificate trust and node operations before advancing.
6. Refresh managed kubeconfig consumers.
7. Stop and report any uncertain outcome; reconcile actual state before retry.

Unattended renewal is enabled only after recovery and interruption testing.
Retain the existing independent bootstrap/recovery path.

BORTUS deliberately disables in-cluster Ansible provisioning. Host maintenance
therefore uses an independent Ansible-managed runner, not privileged web-request
execution or a provisioning bypass. Closing the browser or restarting BORTUS
must not interrupt automation. The host runner requires an always-on deployment;
a sleeping Windows/WSL session is not an availability guarantee. Qualify its
placement, scoped credentials, durable jobs, concurrency control and heartbeat
before claiming unattended operation.

Provide notifications for failed jobs, approaching expiry and missed monitoring
runs. Select and verify a free/self-hosted notification destination during
implementation; in-app status alone cannot notify an absent operator.

### Phase D — Mesh coverage: BORTUS read-only baseline (started)

No mesh change was made. The control plane is healthy: two `istiod`, three
`ztunnel` and three `istio-cni` pods run in `istio-system`, and nine namespaces
carry `istio.io/dataplane-mode=ambient` (homepage, http-echo, mealie,
mesh-pilot, ruckus, vaultwarden, web-apps, website-stack, whoami). The `bortus`
namespace is **not** enrolled: no dataplane label, no `PeerAuthentication`, no
`AuthorizationPolicy` and no `NetworkPolicy`, and the running pod has a single
`bortus` container with no sidecar.

BORTUS baseline: image `…e7539b9e`, serviceAccount `bortus-kv` with
`automountServiceAccountToken: true`, `Recreate` strategy, 1Gi memory limit with
100m/256Mi requests, liveness/readiness/startup probes, env from
`secret/bortus-runtime` (keys `jwt-secret`, `lookup-token`), a `data` PVC plus a
`configMap` aliases volume. RBAC: a cluster binding to `bortus-dashboard-view`
and namespace RoleBindings for `bortus-dashboard-manage`, `bortus-secrets` and
the two certificate-reader Roles. Persistence: `bortus-data` (1Gi, Longhorn,
reclaim `Retain`) is attached and healthy with two started replicas on node02 and
node03, and the pod itself runs on node03. Ingress: four Traefik objects for
`bortus.branconet.lan` (http redirect plus TLS with
`branconet-local-ingress-tls`).

Recorded implications for enrollment: with no policy objects, enabling ambient
would not by itself enforce strict mTLS; enrolling changes the pod's dataplane,
so the three probes, the Traefik ingress path, DNS and API egress all need
re-qualification; and the retained claim with two healthy replicas must survive
the change. Evidence: `phase-d-baseline/{bortus-baseline,bortus-workload,
bortus-access-storage,bortus-runtime-baseline,phase-d-baseline-acceptance}.json`.
BORTUS is now ambient-enrolled with strict mTLS. Two private checkpoints did
this through the validated path (44 tests, full validator, singleton promotion,
exact Flux): `7ae7c95…` labelled the namespace `istio.io/dataplane-mode=ambient`
and added a PERMISSIVE `PeerAuthentication`; `1c5ebf0…` switched it to STRICT
after the permissive window was qualified. The existing pod was recreated
(`780bb378…` → `a8ded156…`) because enrollment happens at pod creation; the
running pod carries the `ambient.istio.io/redirection=enabled` annotation (it is
an annotation, not a label).

Qualification, PERMISSIVE and then STRICT: all three kubelet probes pass with
0 restarts; `bortus.branconet.lan` resolves to 192.168.0.252 and returns
HTTP 307 → `/welcome` through Traefik with the LAN CA trusted; the pod reaches
the Kubernetes API (`https://192.168.0.251:6443/healthz` → 200 `ok`) so API
egress survives ztunnel; and a non-enrolled pod's plaintext request to the
BORTUS service is now **rejected**, which is the enforcement evidence that
PERMISSIVE could not give. Storage is unchanged: the same `bortus-data` PVC UID
and PV, with both Longhorn replicas still started on node02 and node03.

Limits: Traefik→BORTUS mTLS is inferred from the working ingress path rather
than an explicit SPIFFE identity assertion; the PERMISSIVE window was minutes,
not a soak; and no attended browser acceptance was performed. Rollback is to
revert `bortus-mesh.yaml` to PERMISSIVE (or remove the namespace label).
Phase D then enrolled a single Plex application without touching the shared
namespace. Bazarr's dependency check first: it has three claims (`/config`,
`/tv`, `/movies`), no probes, ClusterIP 6767 plus a published 6767, no
`gluetun` container in its pod, and at runtime only `lo`/`tunl0`/`eth0` with a
`eth0` default route — so despite carrying `VPN_*` keys from its runtime secret
it is **not** tunnelled and cannot inherit the VPN pod's netns. Peer reachability
was 200 for sonarr, radarr and Plex.
Because the `plex` namespace also holds the VPN and host-network workloads, the
namespace was **not** enrolled; the bazarr pod template alone received
`istio.io/dataplane-mode: ambient` (checkpoint `3fc2cba…`, HelmRelease
`0.1.3+3fc2cba15695` Ready). After the rollout the new pod carries
`ambient.istio.io/redirection=enabled` with 0 restarts; sonarr, radarr and Plex
still answer 200 from inside the pod; sonarr reaches `bazarr:6767` with 200
(plaintext peer allowed because the namespace has no strict policy);
`bazarr.branconet.lan` serves HTTP 200 through Traefik with the LAN CA trusted;
and all three claims remain Bound with their original PVs.
Evidence: `phase-d-bazarr/{bazarr-dependencies,bazarr-network-baseline,
enrollment-qualification,phase-d-bazarr-acceptance}.json`. Rollback is removing
the pod label. Playback with a real client and SSDP discovery (xteve) were not
exercised.
Phase D repeated the pod-level pattern for sonarr. Baseline: a single
`linuxserver/sonarr` container, no VPN interface, `eth0` default route, no
`hostNetwork`, three claims (`/config`, `/media/tv`, `/downloads`), no probes,
ClusterIP/published `8989`; radarr/bazarr/Plex/qBittorrent all answered before
the change. Only the pod template label was added (checkpoint `c381f2b…`,
HelmRelease `0.1.2+c381f2b5c180` Ready); the `plex` namespace stayed unenrolled.
After rollout the pod carries `ambient.istio.io/redirection=enabled` with 0
restarts; outbound sonarr→radarr 302, →bazarr 200, →Plex 200; inbound
radarr→sonarr and bazarr→sonarr both 302; `sonarr.branconet.lan` serves 302
through Traefik with the LAN CA trusted; and all three claims are unchanged and
Bound. Rollback is removing the pod label. No real indexer/playback run and no
attended UI check were performed.
Phase D then enrolled radarr the same way. Baseline: single `linuxserver/radarr`
container, no VPN interface, `eth0` default route, no `hostNetwork`, no probes,
claims for `/config`, `/media/movies` and `/downloads`, ClusterIP/published
`7878`; sonarr/bazarr/Plex/qBittorrent all answered beforehand. Only the pod
template label changed (checkpoint `426b198…`, HelmRelease
`0.1.2+426b19890da7` Ready), leaving `plex` unenrolled. After rollout the pod
carries `ambient.istio.io/redirection=enabled` with 0 restarts; outbound
radarr→sonarr 302, →bazarr 200, →Plex 200; inbound sonarr→radarr and
bazarr→radarr both 302; `radarr.branconet.lan` serves 302 through Traefik with
the LAN CA trusted; and all three claims are unchanged and Bound. Rollback is
removing the pod label. No real indexer fetch, playback or attended UI check was
performed.
Phase D then enrolled tautulli. Baseline: single `ghcr.io/linuxserver/tautulli`
container, no VPN interface, `eth0` default route, no `hostNetwork`, no probes,
one `/config` claim, ClusterIP `8181` plus published `9119`; Plex 200 and
sonarr/radarr 302 answered before the change. Only the pod template label
changed (checkpoint `c96e062…`, HelmRelease `0.1.0+c96e062ba0d7` Ready), with
`plex` still unenrolled. After rollout the pod carries
`ambient.istio.io/redirection=enabled`, 0 restarts; outbound Plex 200,
sonarr/radarr 302; inbound sonarr→tautulli and bazarr→tautulli both **303**;
`tautulli.branconet.lan` serves 303 through Traefik with the LAN CA trusted; and
the claim is unchanged and Bound. A first predicate accepted only 200/302 and
wrongly failed this step; Tautulli's 303 is a served redirect and the check was
corrected and recorded. Rollback removes the pod label. No real Plex activity
ingestion and no attended UI check were performed.
Phase D then enrolled jackett. Baseline: single `linuxserver/jackett` container
with readiness and startup probes, no VPN interface, `eth0` default route, one
`/config` claim, ClusterIP `9117` plus a published `9117`; flaresolverr 200,
sonarr/radarr 302 and Plex 200 answered beforehand. Only the pod template label
changed (checkpoint `f4f1dc4…`, HelmRelease `0.1.0+f4f1dc4c3993` Ready), keeping
`plex` unenrolled. After rollout the pod carries
`ambient.istio.io/redirection=enabled` with 0 restarts; outbound flaresolverr
200, sonarr/radarr 302, Plex 200; inbound sonarr→jackett and radarr→jackett both
**301**; `jackett.branconet.lan` serves 301 through Traefik with the LAN CA
trusted; the claim is unchanged and Bound. Rollback removes the pod label. No
real indexer search and no attended UI check were performed.
Phase D next attempted flaresolverr and **rolled it back**. Baseline was fine
(single FlareSolverr 3.5.2 container, no VPN interface, `eth0` default route,
`/config` mount with no claim, ClusterIP plus published `8191`, local GET 200).
After adding only the pod label (checkpoint `5c8376a…`, HelmRelease
`0.1.3+5c8376a50d1c` Ready) the pod was Ready and listening on `0.0.0.0:8191`
inside the container, yet unreachable from jackett, sonarr and bazarr, and even
from a non-mesh pod to the pod IP. Rollback to `e0305ae…` restored in-cluster
access (jackett and sonarr both 200 to `flaresolverr:8191`).
Two honest findings: 17 pods had been **Evicted by node03 DiskPressure** around
this window (node03 now reports DiskPressure=False with 21 GB free), so mesh
causality is **not** established for the outage; and the published node-IP path
`8192`… i.e. `8191` on 192.168.0.4/.5/.6 timed out both before and after the
rollback while the Service lists those externalIPs and an endpoint exists —
kube-proxy rules could not be read without sudo, so this is recorded as an open,
likely pre-existing gap rather than a mesh effect. Flaresolverr remains
unenrolled; the app needs a cleaner pass after node03 hygiene is reviewed.
The flaresolverr re-attempt was **deferred pending diagnosis**, not retried. Two
investigations ran read-only. Node03 did evict 17 pods and kubelet logged 29
eviction/DiskPressure lines in 12 hours, but the node now reports
DiskPressure=False, root has 21 GB free (82 GB used, 80%), and the `du` "10T" on
`/var/lib/kubelet` is a mounted volume being followed, not host consumption.
For the published path: `flaresolverr-published` is a ClusterIP Service with
externalIPs `.4/.5/.6`, `etp=Cluster`, `8191→8191` — the same shape as working
`sonarr` 8989 and `jackett` 9117 — and node01's iptables already contains
KUBE-SVC/KUBE-SEP/KUBE-EXT rules DNATing 8191 to `10.244.186.239:8191`. Yet TCP
to `.4/.5/.6:8191` times out from the operator host while `.4:8989` is open, the
in-cluster Service path from jackett returns 200, and a direct pod-IP connect
from an enrolled peer did not succeed. UFW is active with default **deny
routed** and only `8079:8098/tcp` explicitly allowed, which is a plausible
contributor for forwarded service traffic to a pod on another node.
No mesh label, Service, firewall or node change was made. Re-attempt is blocked
on: testing forwarded published traffic to a pod that is not on the queried
node, inspecting UFW forward/before chains, and confirming whether any published
port to a node03 pod works.
Both findings were then resolved and the enrollment completed. The published
`8191` timeout is explained by the pod's own pre-existing NetworkPolicy
`plex/flaresolverr-ingress`, which allows ingress only from `podSelector {}`
(same namespace) on TCP 8191: `externalIPs` traffic is masqueraded by kube-proxy
so its source is a node IP and the policy denies it. That policy is why
`sonarr`/`jackett` serve on the node IPs while `flaresolverr` never did — it is
pre-existing and unchanged in scope. The 17 node03 evictions were a historical
DiskPressure spike; the node now reports `DiskPressure=False` with 21 GB free,
and the brief `000FAIL` blips were pod churn, not connectivity loss.

Re-attempting with the label (checkpoint `44b1aaf…`) reproduced the failure
deterministically, which isolated the real defect: an **enrolled** pod whose only
ingress allowlist omits the ambient HBONE inbound port `15008`. Enrolled→enrolled
traffic is HBONE to 15008, so every same-namespace caller failed, while
enrolled→non-enrolled plaintext on 8191 still worked. An additive test policy
allowing 15008 from same-namespace pods restored jackett/sonarr to 200
immediately; the test policy was then deleted. The chart fix
(`785dae7…`, HelmRelease `0.1.3+785dae7cb361` Ready) adds TCP 15008 to the same
`from: podSelector {}` rule — no `namespaceSelector` was added, so isolation is
unchanged.

Qualified after the fix: pod `flaresolverr-6c7b958567-5nrcc` enrolled with
`ambient.istio.io/redirection=enabled`, 0 restarts; jackett, sonarr and radarr
all reach both `flaresolverr:8191` and the pod IP with 200; the published
node-IP path stays blocked exactly as before (policy, not a regression); and the
platform control (`192.168.0.4:8989` → 302) is unaffected. `/config` is an
`emptyDir`, so there was no claim to preserve. Evidence:
`phase-d-flaresolverr/{phase-d-flaresolverr-acceptance,hbone-flux-result,
retry-flux-result}.json` and `node03-hygiene/{findings-resolution,
networkpolicy-cause,firewall-chains}.json`.
Phase D then enrolled xteve. Baseline: two binaries in one pod
(`ghcr.io/volschin/threadfin` plus a `legacy-guide-routes` nginx sidecar), no VPN
interface (`lo`/`tunl0`/`eth0`), `eth0` default route, no probes, three claims
(`xteve-data-0/1/3`), ClusterIP `xteve` (`1900`, `34400→34401`) plus
`xteve-published` (`1901→1900`, `34400→34401`), and **no Ingress object**. No
NetworkPolicy selects `app=xteve`, so the flaresolverr `15008` defect could not
apply — and the published node-IP path worked from the operator host *before*
the change (200 on `:34400`), unlike flaresolverr.
The chart also defines a separate **`xteve-ssdp` Deployment with
`hostNetwork: true`** for SSDP discovery. Only the `app: xteve` pod template
received the ambient label (checkpoint `c3b3bbd…`, HelmRelease
`0.1.2+c3b3bbd990be` Ready; the render contains exactly one ambient label), so
the host-network SSDP gateway remains outside the mesh — verified by its pod
having no ambient annotation.
Qualification: pod `xteve-85fb58cdc9-qcsz6` enrolled with
`ambient.istio.io/redirection=enabled`, 0 restarts; sonarr, radarr and jackett
each reach `xteve:34400` and the pod IP with 200; xteve→Plex 200; the SSDP
gateway (non-enrolled, plaintext) still reaches `xteve:34400` with 200; the
operator's published path stays 200; and all three claims are unchanged.
`xteve:1900` resets, but it failed the same way **before** enrollment, so that is
pre-existing and not caused by this change.
**qBittorrent was deliberately not enrolled**: its pod carries `tun0` and the
`checksum/proton-wireguard` annotation, so it terminates Proton WireGuard inside
the pod. Proxying its egress through ambient ztunnel risks traffic leaving
outside the tunnel, which is a leak boundary rather than a mesh-coverage gap.
Evidence: `phase-d-xteve/{xteve-baseline,flux-result,source-result,
phase-d-xteve-acceptance}.json`.
Phase D then assessed **Pi-hole and deliberately did not enroll it**. Its pods are
ordinary (no `hostNetwork`, no in-pod VPN) and no NetworkPolicy selects them, so
the flaresolverr `15008` defect does not apply — but the transport evidence
disqualifies it anyway: ztunnel listens on TCP only (`15000/15008/15020/15021`,
**no UDP listener**), and in an enrolled pod netns `ISTIO_PRERT` redirects **TCP
only** to `15006` while `ISTIO_OUTPUT` sends **all outbound UDP** to `15053`,
which is a DNS *client* interception proxy. Pi-hole is a DNS *server*: inbound
UDP 53 would gain no mesh protection (it bypasses ztunnel) while its outbound
UDP — including replies to LAN clients — would be captured by a DNS-client
proxy. With the advertised LAN VIP (`pihole-lan-dns`, `etp=Local`) and the node03
standalone DNS/DHCP path sharing that role, that is an availability risk with
LAN-wide blast radius for zero coverage gain. It therefore stays out of the
mesh. (CoreDNS forwards to 1.1.1.1/8.8.8.8, not to Pi-hole, so the cluster
itself is independent of it.) Evidence: `phase-d-pihole/pihole-deferral.json`.

The other Phase D remainder — the previously ambient namespaces — was then
qualified read-only: **10 namespaces, 15 of 15 pods enrolled**, with six STRICT
(`bortus`, `homepage`, `http-echo`, `mesh-pilot`, `website-stack`, `whoami`) and
four with no `PeerAuthentication` (`mealie`, `ruckus`, `vaultwarden`,
`web-apps`). The important finding is that **nine `AuthorizationPolicy` objects
with `action: ALLOW` provide default-deny**: only `traefik/traefik`,
`cloudflare-tunnel/public-web-tunnel` and a few namespace-scoped principals are
allowed. That explains the east-west refusals — e.g. `ruckus-bot` is refused
(`ConnectionReset`) by whoami, http-echo, website-stack, homepage and web-apps,
while same-namespace `ruckus-bot → ruckus-db:3306` is open. They are policy, not
breakage. The intended path was verified instead: eight ingress hostnames answer
200 through Traefik with the LAN CA (`homepage`, `http-echo`, `mealie`, `ruckus`,
`vault`, `aplb`, `lucinda`, `whoami`); `jtmb-dev` and `mesh-pilot` have no DNS
record here so their ingress path was not exercised. Evidence:
`phase-d-ambient-set/{ambient-inventory,ambient-traffic,ingress-path,
phase-d-ambient-set-acceptance}.json`.
**Unattended kubelet-serving approval is now enabled and proven end to end.** The
prerequisite chain was completed first: the controller's ClusterRole gained
signer-scoped approval (`approve` on `signers/kubernetes.io/kubelet-serving`
plus `get, patch, update` on `certificatesigningrequests/approval`), delivered
through the unchanged 44-test/validator/Flux path in three revisions
(`255c187…`, `1508c97…`, `28d5552…`) because each verb requirement only surfaced
from the API server's own refusal. Signing, create/delete, other signers,
Secrets and node writes remain denied.
The managed unit was switched from observe to approve with a reversible drop-in
(`/etc/systemd/system/bortus-csr-controller.service.d/10-approval.conf`,
`playbooks/csr-approval-toggle.yml`; rollback is
`--extra-vars csr_approval_action=disable`).
Proof: a genuine rotation was forced on node02 by moving kubelet's serving file
aside. The **service** approved the resulting CSR with **0 operator commands**
(durable row `csr-s7q4l` / `9b3a50c5…`), the signer issued it, and kubelet now
serves it — `80a9e9fe…` → `846e474a…`, issued equals served, TLS1.3, issuer
`CN=kubernetes`, NotAfter 2027-11-17. Node02 stayed Ready.
Three real defects were found and fixed on the way: the RBAC verb set
(`update` alone was insufficient — `get` and `patch` were also required); the
credential broker quarantined the runtime token because its expected permission
matrix went stale after the widening (so approve mode silently lost its
credential); and the controller wrote its exactly-once approval row **before**
the PATCH and never released it on a definite failure, wedging that CSR forever
(`release_approval` now clears the row only when the API server confirms the
object is not approved, preserving exactly-once for genuinely uncertain
outcomes). Attempts 1-3 each wedged a CSR; all were retired under
UID/resourceVersion guards. Evidence:
`csr-unattended-approval/{unattended-acceptance,unattended.result,rbac3-flux-result,
enable-result,upgrade4.log,pre-retry-reconciliation}.json`.
The Phase C remainder was then closed with measured evidence. A 120-second
conntrack window per node showed **zero** node-IP clients on 8082 and 8083,
node-self traffic only on 8080 (2024/2112 flows from the node's own IP) and 8081
(92), and zero on 8096. Three further forward-hook profiles were added and
applied through `playbooks/plaintext-restriction.yml`: `minecraft-website`
(8083), `aplb` (8082) and `web-apps-local` (8080 + 8081 — safe because their only
observed clients are node IPs, which stay in the allowlist). Verification after
apply: the operator host gets HTTP 200 on all four ports from all three node IPs,
an in-cluster pod gets 200 on all four, node-to-own-IP stays 200 on both nodes
that polled themselves, and every reject counter stayed at 0 during the allowed
probes. Rollback is `--extra-vars "restriction_profile=<name>
restriction_action=remove"`. Two probe mistakes were caught and corrected in the
process: a loopback probe (nothing listens on 127.0.0.1) and a mangled SSH
argument list. Only `vaultwarden` 8096 remains unrestricted by decision, because
its clients sync sporadically and a bounded window cannot prove absence.
The inventory is now eight tables per node, identical on all three:
`core` (32158/32359/9090), `pihole-exporter` (9617), `ruckus-db` (3306),
`ruckus-bot` (3003/8088), `mealie` (8089), `minecraft-website` (8083),
`aplb` (8082) and `web-apps-local` (8080/8081). Evidence:
`plaintext-inventory/{phase-c-remainder-sampling,minecraft-verification,
phase-c-remainder-acceptance}.json`.
The 66.2-minute node02 notification latency was then diagnosed read-only. The
figure is not one slow send: the event was created at 23:30:14Z and acknowledged
at 00:36:26Z (**3972.3 s**) across **six** failed attempts with the last failure
at 00:35:57Z, so the delay is the retry/backoff schedule, with codes
`notification_transport_unavailable` (phase transport) and `process_failed`
(phase child). Four alternatives were eliminated with measurements: the ntfy pod
started 22:29:27Z with **0 restarts** and was never replaced during the window
(not server availability); `PinnedHTTPSConnection` connects to the configured
address and uses the hostname only for SNI, so there is **no DNS lookup**
(not resolution); six fresh connect+TLS+request round trips from node02 to the
VIP total **48-56 ms** (not network latency); and the egress rule's accept
counter is 55 with the exact destination permitted (not a blocked path).
The strongest remaining cause is **CPU-budget saturation against the sender's own
3-second timeout**: `publish_ntfy` sets `timeout=3` for connect and TLS, the unit
is capped at `CPUQuotaPerSecUSec=50ms` (`cpu.max "5000 100000"`) and reports
`nr_throttled 423 of 586` periods with 40.0 s cumulative throttled time, while
measured full-child runs took 1.806 s and 2.399 s — 60-80% of that 3 s budget —
with only ~55 ms of it being network. Honest limits: the original failures
predate the `transportStage`/`transportKind` annotation, so no run has captured
`kind=timeout`, and the diagnosis is therefore **strongly supported but not
reproduced**. The egress table's 15 rejected packets are historical residue
(unchanged over 75 s with no pending events), not an ongoing block, but remain
unattributed. **No code or resource change was made**, because the cause is not
proven; the proposed reviewed fix is to raise the inner timeout from 3 s to ≤8 s
(still inside the existing 10 s per-child budget, at no cost on a 55 ms path)
and/or raise the CPU quota, ideally paired with capturing `transportKind` on the
next real failure. Evidence:
`notification-latency-diagnosis/latency-diagnosis.json`.
The `wordpress/jtmb-cc` certificate was then retired after a dependency check.
Six reference classes were enumerated and all were empty: no apex
`jtmb.cc`/`www.jtmb.cc` Ingress or IngressRoute rule anywhere (28 ingress hosts,
none apex), no Ingress TLS `secretName: jtmb-cc-tls`, no other Certificate
sharing that Secret, no pod volume and no pod `envFrom` reference. The
`wordpress` namespace held only the Certificate (UID `591745ea…`, Ready=True,
dnsName `jtmb.cc`, ClusterIssuer `letsencrypt-production-http01`), its
CertificateRequest/Order, and the Secret (UID `6e544d1c…`, `tls.crt`/`tls.key`,
**no ownerReferences**). The domain itself resolves to Cloudflare
(`172.64.80.1`), whose edge certificate serves TLS, so the cluster Secret was
never on that path.
The declaration was removed from the private charts
(`flux/releases/foundation/public-certificates.yaml` deleted plus its
kustomization entry, checkpoint `886d93c…`, unchanged 44-test/validator gate and
a render confirming absence). Because `migration-releases` has **prune=false**,
Flux applied the source change without deleting the object — verified by the
unchanged UID and resourceVersion — so both objects were then deleted with
`uid` + `resourceVersion` preconditions. Post-state: no residual Certificate or
Secret, no leftover CertificateRequest/Order/Challenge, `jtmb.cc` and
`mealie.jtmb.cc` still resolve to Cloudflare, and certificates went from 15 to
**14 healthy of 14**. Rollback is `git revert 886d93c…`, after which cert-manager
re-issues and recreates the Secret. Left for a separate decision, and
deliberately untouched: the namespace still holds retired-chart Helm release
Secrets, their `-runtime` Secrets, and `source-acme-0..5` copies that no
`wordpress` Ingress references. Evidence:
`certificate-retirement/{wp-retirement-pre-state,flux-result,delete-result,
retirement-verification,retirement-acceptance}.json`.
UDP payload verification was then performed read-only, with real payloads rather
than assumptions. Listener inventory: node01 holds UDP 53 (systemd-resolve), 68,
111 (rpcbind), **1900 (python3)**, 7946 (speaker) and NFS rpc ephemeral ports;
node03 holds 53, **67 (dnsmasq — the standalone DHCP)**, 111, 7946 and 10554
(pihole-FTL). Plaintext was confirmed by capturing actual traffic:
DNS answers on three resolution paths (floating `192.168.0.253`, standalone
`192.168.0.5` and the node-IP externalIP `192.168.0.4`) with
`bortus.branconet.lan → 192.168.0.252` and a two-record CNAME chain for
`notifications.branconet.lan`; **Plex GDM** replied on node01 UDP 32410 and 32414
with a readable `HTTP/1.0 200 OK / Content-Type: plex/medi…` payload; and **mDNS
5353** produced six cleartext PTR/AAAA records from `172.25.192.1`. No responder
appeared for SSDP 1900 (a python3 process holds the port but answered no
M-SEARCH for three ST types and emitted no NOTIFY during a 12 s passive
capture), for Plex GDM on node03, or for an unsolicited memberlist probe on
7946, whose framing is plaintext UDP with an opaque/keyed payload. Not verified,
deliberately: a DHCP 67 lease exchange (taking a lease would disturb the LAN),
memberlist payload contents, and payloads for rpcbind/NFS ephemeral ports. The
12 s windows cannot exclude infrequent announcements, and the mDNS/SSDP samples
came from the operator network path rather than from cluster pods. Evidence:
`udp-payload-verification/udp-verification.json`.

The Certificates UI release gate was then assessed and is **definitively
unreleased**: the deployed image `…e7539b9e` contains no `certificates` route
under `.next/server/app/(dashboard)` and no `api/certificates`, while both exist
in source, so the screen cannot be served from the running build. The "static
delivery label" is a hardcoded string literal at
`src/app/(dashboard)/certificates/monitor-controls.tsx:51` (`"· delivery not
configured"` inside a `<span>`), not derived from monitor state. Closing this
gate requires a real image release: rebuild under the H qualification path,
publish the immutable reference, update the private chart pin, roll the
single-replica `Recreate` deployment, re-run the API/UI and LAN-CA ingress
checks, and replace that literal with state derived from the monitor snapshot.
That is a production restart and was therefore not performed as part of a
read-only assessment. Evidence: `ui-release-assessment/ui-release-assessment.json`.
The Certificates UI delivery label was then converted from a hardcoded literal to
derived state, and the release was **stopped at a real blocker**. The monitor now
derives `notificationDelivery` from the outbox instead of returning a constant
(`CertificateMonitor.delivery_state()` → `not-configured` / `no-delivery-yet` /
`pending-delivery` / `delivered`, exercised against an in-memory database for
three of the four transitions); `MonitorView` gained a validated union, the
snapshot parser rejects unknown values, and
`monitor-controls.tsx` renders `deliveryLabel()`/`deliveryTone()` from monitor
state instead of the `"· delivery not configured"` literal. Verification:
project-wide `tsc --noEmit` exit 0 and `eslint --max-warnings=0` exit 0 on both
changed files, using the retained H dependency tree through a temporary symlink
(no install or copy made; the symlink was removed afterwards).
Release is blocked by a concrete contract, not by effort:
`prepare-bortus-release-context.py` builds the Docker context from a **git
commit** (`--source-commit`, `git ls-tree`/`cat-file`), so an image can only be
produced from a committed revision. Every certificate-UI change in this session
is uncommitted, in a root repository that has deliberately preserved a large body
of unrelated staged/uncommitted work and a fixed index SHA-256 `778cf730…`
throughout. Committing the root repository is therefore an owner scope decision,
and the release itself restarts BORTUS (`Recreate`, 1 replica). The three options
are recorded: a scoped certificate-UI commit, a full-tree commit (not recommended
unreviewed), or leaving the UI unreleased with the code staged. Evidence:
`ui-release-assessment/ui-label-implementation.json`.
The authorized scoped commit was then made and the release context built, but the
**image build was refused by the builder environment**. Commit
`d43f05b2d227f8b7613098e081db812c7e9797cc` ("Add the Certificates screen with
derived delivery state") contains 13 files: the three `certificates` dashboard
components, both `api/certificates` routes, `certificate-control.ts`,
`certificate-inventory.ts`, `sidebar.tsx` (the nav entry), four certificate test
fixtures and `scripts/migration/certificate_monitor.py`. Staged work went from 971
to 970 paths, so the unrelated staged body was preserved; the one consumed path,
`sidebar.tsx`, already carried 93 insertions/92 deletions of its own, which is
disclosed rather than folded in silently.
`prepare-bortus-release-context.py` then succeeded against the exact lowercase
commit: **164 included files, 9 excluded, 296,403 bytes, context SHA-256
`06bb3750…`, manifest SHA-256 `44889e99…`, application tree `df6a71b2…`**, with
the producer recording `image_built=false` and `cluster_mutations=0`. The first
invocation failed because the contract compares against the full 40-character
SHA and I passed an abbreviated one.
`build-bortus-release-image.py` was then dispatched and refused at `tag_query`
with `Cannot connect to the Docker daemon at unix:///var/run/docker.sock`: the
fixed build host **node01 has no Docker daemon** (`systemctl is-active docker` →
`inactive`, no socket), while the operator WSL daemon is healthy (29.6.2,
overlayfs) but is not the pipeline's destination. The refused run
`bortus-release-d43f05b2…/record.json` is retained with `deployed=false` and
`runtime_accepted=false`, and the helper refuses to replay or adopt an existing
run, so it must be reconciled before another attempt for this commit. Enabling
dockerd on a live control-plane node would add the DOCKER iptables chains beside
kube-proxy, which is a node-level service change rather than a routine repair, so
the build was not forced. Evidence: `ui-release/{context-evidence.json,
build-blocked.json}` and the retained `record.json`.
The Certificates UI image was then built, verified and published, but the rollout
was stopped by a delivery requirement and rolled back. Option B was completed
first: the certificates page and both `api/certificates` routes were adapted to
the **deployed** lib surface (`getCurrentRole`, `getSession`, `requireWrite`) and
to the deployed `kubectlJSON(cmd: string)` signature via `args.join(" ")` after
confirming every argument token is space-free (commits `ea041f1d`, `82580115`).
The release tree reverts `auth.ts`/`permissions.ts` to the deployed versions
through a temporary `GIT_INDEX_FILE` plus `read-tree`/`update-index`/
`commit-tree`/`update-ref`, so the working tree keeps the in-progress auth
refactor untouched and the shared index was not modified.
`build-bortus-release-image.py` then completed after the builder was repaired
(node01 `docker` was inactive with no socket; started it, verified
`FORWARD` policy stayed `DROP` and the cluster was unaffected: 3/3 nodes Ready,
65/65 pods on node01 ready, cross-node probes 200 both ways). The artifact is
`sha256:1688194a…`, 1,114,174,137 bytes, revision `82580115…`, source tree
`cc0f292f…`, and **provably contains the feature**: `.next/server/app/(dashboard)`
lists `certificates` and `.next/server/app/api/certificates` exists. It was
pushed to Docker Hub as `jtmb92/bortus@sha256:44a163a9…` (exit 0).
Pinning exposed one more gate requirement: the validator refuses an image that is
not listed in all three Flux-owned admission Deny policies, so the digest was
added to `approvedImages` in the three `bortus-kv-guard-*` policies and the full
44-test/validator gate passed (checkpoint `34b5890…`). Flux applied it and the
deployment switched to the new digest — then failed with **`ErrImageNeverPull`**:
the deployment uses `imagePullPolicy: Never`, so a new digest must be preloaded
into the worker node image stores, and node03 did not have it. BORTUS was
unavailable for roughly 13 minutes before the pin was rolled back
(`a5165a0…`) to the preloaded `e7539b9e` digest; the pod is Running and Ready
again. The new digest stays in `approvedImages`, so completing the release now
only needs the node preload (`bortus-release-preload-node.py`) followed by a
re-pin and the API/UI plus LAN-CA acceptance. Evidence:
`ui-release/{release-outcome.json, pin-commit-intent.json, pin-flux-result.json,
rollback-result.json}`.
**The Certificates UI is released and live.** The delivery failure was diagnosed
precisely: `docker save` of the unqualified local tag stores the image as
`docker.io/library/bortus:release-82580115…`, so neither the `jtmb92` repository
path nor any digest reference existed on the nodes — which is why both the
ad-hoc import and the first pin produced `ErrImageNeverPull`. The supported path
(`stage-bortus-release-image.py export` then `preload` with build and export
receipts, `{"sudo_password":…}` on stdin) exported the archive
(1,149,636,096 bytes, sha256 `d6518eed…`) and imported it on **all three nodes**
with `import_exit_code 0` and per-node archive identity verified, reporting the
platform manifest digest `858ddb5c…`. Two references were then added on each
node with `ctr images tag`: `docker.io/jtmb92/bortus@sha256:858ddb5c…` and the
registry index digest `@sha256:44a163a9…`, and verified by listing.
Re-pinning (`4293bd5…`) passed the validator unchanged because the digest was
already in all three Flux-owned Deny policies, Flux rolled the single-replica
`Recreate` deployment, and pod `bortus-6b77c798cf-m2cc9` is Running and Ready
with 0 restarts. Live acceptance (`verify-certificates-ui-release.py`) passes
**every** check: the deployment uses the new digest; the running pod's
`(dashboard)` route set contains `certificates` and
`/app/.next/server/app/api/certificates` exists **inside the running image**;
`/api/certificates` answers **401** (auth-gated, not 404) and `/certificates`
answers **307 → /welcome** through `bortus.branconet.lan` with the LAN CA
trusted. Cluster: 12/12 Kustomizations healthy, 3/3 nodes Ready. The earlier
13-minute outage, the refused/failed/interrupted build runs and the rolled-back
pins (`a5165a0…`) all remain recorded. Remaining gates are unchanged: node03
reboot survival, attended subscriber/reader receipt, the vaultwarden 8096
decision, real playback/discovery exercise, and DHCP 67 / memberlist /
rpcbind-NFS payload verification. Evidence:
`ui-release/{release-acceptance.json, release-acceptance-final.json,
rollout-result.json, pin3-result.json}`.
**node03 reboot survival is now accepted.** The reboot was performed
(`systemctl reboot`), boot ID changing `5a456fc3…` → `f9246c77…`. Recovery was
verified rather than assumed, and one detail mattered: DHCP 67 is **not**
`dnsmasq.service` (inactive) but `branconet-lan-dhcp.service`
(`/system.slice/branconet-lan-dhcp.service`), which is what the post-check
asserted. After the reboot `kubelet.service`, `branconet-lan-dhcp.service` and
all three BORTUS watchdog units (`bortus-certificate-watchdog.service`,
`-notifications.service`, `-credential.timer`) are active/enabled, UDP 67 is
listening again on `0.0.0.0%enp3s0`, and DNS 53 answers with rcode 0 on both the
standalone `192.168.0.5` and the floating `192.168.0.253` — the floating resolver
kept answering, so LAN resolution never depended on the rebooting node.
node02's monitor, sender, CSR controller and credential timer were unaffected.
Workloads: 27 of 27 live pods on node03 are fully ready; the 34 non-running
objects there are pre-existing Failed/Evicted pods from Nov 8/15 and 03:23, older
than this reboot, not reboot casualties. Longhorn settled to **0 degraded** with
30 healthy volumes; the 17 stopped replicas belong to detached volumes reporting
robustness `unknown`, which is normal for retained-but-unattached claims.
Importantly the **newly released Certificates UI survived the reboot** — the
BORTUS pod came back ready on digest `44a163a9…`. Cluster is 3/3 nodes Ready.
Evidence: `node03-reboot-survival/{pre-reboot.json, reboot-issued.json,
post-reboot.json, node03-reboot-acceptance.json}`.
A real media exercise and two payload checks were then completed. **Tuner
discovery is genuine**: xteve's `/discover.json` returns an HDHomeRun-style
DeviceID and BaseURL, `/lineup_status.json` answers, and `/lineup.json` lists
**29 channels** (e.g. "PT (VF) Dazn 5"). **Playback is proven as far as the tuner
hand-off**: requesting a channel stream returned **302** to the upstream
provider; following it returned **401**, because real media bytes require the
provider's own client context (auth/headers) that a bare curl does not carry — so
decoded playback is *not* claimed. The **authenticated Plex API** works
(`/library/sections` 200 with a 3-section MediaContainer, `/status/sessions`
200), with the token supplied on stdin only. Chain liveness: sonarr 200, radarr
200, bazarr 200, tautulli 303, jackett 302.
Payload verification: **rpcbind UDP 111 verified** (portmap v2 NULL call answered
with matching xid, msgType=reply, acceptState=0, 24 bytes); **memberlist UDP 7946
verified as opaque/encrypted** (real node01→node03 gossip captured, ciphertext
after the UDP header, so framing is plaintext-UDP but contents are keyed).
**DHCP 67 lease exchange remains NOT verified**: a synthetic DISCOVER from node01
received no OFFER within 6 s even though `branconet-lan-dhcp.service` is active
and UDP 67 is listening — recorded rather than assumed, and needing its own
diagnosis (interface scope, relay requirement, or authoritativeness). Evidence:
`media-exercise/{media-exercise.json, media-and-payload-acceptance.json}`.
**The DHCP 67 no-OFFER was then diagnosed and the exchange is now verified.** The
server was never at fault: `branconet-lan-dhcp.service` (main PID 995,
`/system.slice/branconet-lan-dhcp.service`) runs
`dnsmasq --keep-in-foreground --conf-file=/etc/branconet-lan-dhcp.conf` with
`port=0`, `interface=enp3s0`, `bind-interfaces`, `dhcp-authoritative`, ranges
`192.168.0.200-245` and `192.168.0.247-250` (deliberately leaving `.246` free),
a 24 h lease, router `192.168.0.1` and DNS advertised as `192.168.0.253` then
`192.168.0.5`. My first probe sent **no DHCP broadcast flag**, so dnsmasq
unicast the offer to a random MAC that does not exist and the client socket never
saw it — and the server journal proves it answered even then
(`DHCPDISCOVER(enp3s0) 02:00:00:84:af:6f` → `DHCPOFFER(enp3s0) 192.168.0.230`
with matching transaction id 3384024176). Re-running with the broadcast flag set
produced a real exchange: the client received `OFFER` from `192.168.0.5` for
`192.168.0.236`, mask `255.255.255.0`, lease `86400 s`, and the server log shows
the matching `DHCPDISCOVER(enp3s0) 02:00:00:76:29:6d` →
`DHCPOFFER(enp3s0) 192.168.0.236 02:00:00:76:29:6d`. Scope is stated honestly:
DISCOVER/OFFER only — no REQUEST/ACK was sent, so no lease binding is claimed.
Evidence: `media-exercise/dhcp67-acceptance.json`.
Both owner decisions were then taken and acted on. **Vaultwarden 8096 is
restricted** (`vaultwarden` profile, forward hook: loopback, the three node IPs,
the operator host and the pod CIDR allowed; everything else rejected). Verified
after apply: the operator host gets HTTP 200 on `:8096` from all three node IPs,
a cluster node gets 200, an in-cluster pod gets 200, and the reject counter did
not move during any allowed probe. Sporadic external client sync was the original
reason for deferral and the owner accepted that trade-off explicitly.
Applying it exposed a **real gap the reboot had hidden**: nftables restrictions
are runtime-only and did **not** survive the node03 reboot — the post-apply
inventory read 9 tables on node01/node02 but only **1** on node03. Every profile
was re-applied and the inventory is now **9 identical tables on all three nodes**
(`core` 32158/32359/9090, `pihole-exporter` 9617, `ruckus-db` 3306, `ruckus-bot`
3003/8088, `mealie` 8089, `minecraft-website` 8083, `aplb` 8082,
`web-apps-local` 8080/8081, `vaultwarden` 8096). A second defect surfaced during
that repair: the `core` table on node01/node02 still carried the pre-refactor
owner comment, so the helper correctly refused with
`firewall_table_ownership_unknown`; those tables were deleted by exact name and
recreated under the current owner comment. **The restrictions are still not
boot-persistent** and need a persistence unit so a reboot cannot silently drop
them — recorded explicitly rather than left implied. The **attended
subscriber/reader receipt was explicitly deferred by the owner**, so it remains
open and no completion is claimed for it. Evidence:
`plaintext-inventory/{vaultwarden-verification.json, restore-all-profiles.json,
core-reapply.log, restored-inventory.json,
vaultwarden-and-persistence-acceptance.json}`.
**Boot persistence for the nine restriction tables is now implemented and proven.**
The gap recorded above (runtime-only tables lost on reboot) is closed by
`branconet-plaintext-restriction.service` — a `oneshot`,
`RemainAfterExit=yes`, `WantedBy=multi-user.target` unit installed by
`playbooks/plaintext-restriction-persist.yml` on all three nodes. Its runner
`/usr/local/libexec/branconet-plaintext-restriction-all`
(`scripts/migration/apply-all-plaintext-restrictions.py`) shells out to the
**existing helper once per profile**, so the helper's ownership and table checks
remain the only authority and no bypass was introduced. Install result:
`ok=9 changed=0` (node01, already current), `ok=9 changed=3` (node02, node03),
`failed=0` everywhere; the unit is `active`/`enabled` with `Result=success` and a
9-table inventory identical on all three nodes.
Proof across a real reboot on **node02**: boot ID `f6d82213…` → `e6b87bf0…`, and
all **nine tables returned with no manual re-apply**, unit `Result=success` under
a fresh invocation `e8583035…` — the exact scenario that previously dropped eight
tables on node03. Rule content after reboot is byte-identical between the
rebooted node02 and the untouched node01 (`vaultwarden` 8096 profile compared
directly), allowed sources still reach the restricted ports (HTTP 200 from all
three node IPs), and node02's monitor, sender, CSR controller and credential
timer all returned `active`/`enabled`. Cluster 3/3 nodes Ready, BORTUS running
the released `44a163a9` digest. Four of my own defects surfaced and are retained:
the play's assert tested a `from_json` dict for truthiness (now a computed length
comparison), two wrong `stat` attribute names before the correct `stat.pw_name`,
and — twice — a probe/assert that used a non-existent
`branconet_plaintext_restriction_core` table when `core` actually maps to the base
table name with no suffix. Evidence:
`plaintext-persistence/{node02-pre-reboot.json, node02-post-reboot.json,
persistence-acceptance.json, post-reboot-verification.json,
persistence-final-acceptance.json}`.
Phase C was then **re-recorded against the persistent mechanism**, superseding the
runtime-only framing of the earlier record: all nine profiles are documented with
their ports and hook type (`core` uses the `input` hook for host listeners
32158/32359/9090; the other eight use a `forward` hook at priority −10 for
published Service ports), together with the allowlist model (loopback, the three
node IPs, the operator host and the `10.244.0.0/16` pod CIDR, everything else
rejected), the enforcement evidence, and durability as part of acceptance rather
than an open caveat. Rollback is per profile plus disabling the persistence unit.
`plaintext-inventory/phase-c-persistent-acceptance.json`.

The media gate was then advanced from the tuner hand-off to real searches and real
media bytes. **Real indexer search works**: sonarr returned **186 live releases**
from 1337x, The Pirate Bay, eztv and nyaasi, and radarr returned **221** from
1337x, IP Torrents, YTS and thepiratebay, with all nine indexer validations
passing (`isValid: true`). **Authenticated Plex playback produced real media**:
fetching a library part with Plex's own token returned HTTP **206**,
`contentType video/x-matroska`, **4,194,304 bytes** starting with the EBML
signature `1a 45 df a3`; inspecting those bytes found the `matroska` DocType, a
**`V_MPEGH` HEVC video track**, an **`A_AAC` audio track** and the `Lavf58.41.100`
muxer string. The token came from the `plex-api-access` Secret and travelled on
stdin only.
The first search attempt returned **zero** results and that was diagnosed rather
than explained away: **jackett was not running** (`unavailableReplicas=1`, pod
`ContainerCreating` waiting for a Longhorn volume to detach), because the node02
reboot I performed had detached that volume; every sonarr/radarr indexer is a
Torznab entry pointing at `jackett:9117`, so all indexer tests returned HTTP 400
"Unable to connect to indexer". Once jackett started, all validations passed.
Three probe mistakes are retained: `strings` does not exist in the Plex image (so
the first codec probe found nothing; `grep -a` was used), Plex emits
`<Part id=… key="/library/parts/…">` rather than `Part key="…"`, and a grep loop
printed cosmetic stray `0` lines. Not claimed: decoded video frames or a live
player session, any download/grab/import run, or attended UI. Evidence:
`media-exercise/{indexer-search3.json, plex-playback.json,
plex-playback-tokens.json, media-gate-acceptance.json}`.
A **self-audit was then run after the owner reported the notification page returning
`{"code":40401,"http":404,"error":"page not found"}`**, and it found five issues, two
of them defects I had shipped or left half-delivered.
**D1 (open):** the ntfy web UI is disabled — `server.yml` sets `web-root: disable`,
so `/` correctly 404s. The attended-browser receipt path I described does not
exist; I published a URL without ever requesting it. Closing that gate needs
either the ntfy mobile app with the subscriber token, or a reviewed config change
enabling `web-root` (a private-chart + Flux rollout and restart).
**D2 (fixed):** the host monitor hardcoded `notificationDelivery` to
`"not-configured"` while its own database held six delivered events, so the
released UI label was wrong in production. A hash-guarded play
(`playbooks/certificate-monitor-delivery-state.yml`) updated only
`certificate_monitor.py` on node02 (`ok=9 changed=2 failed=0`), and the published
snapshot now reports `delivered` with `notificationsPending: 0`, consistent with
`outboxTotal 6 / delivered 6 / pending 0`.
**D3 (fixed in source, not yet in the deployed image):** my UI change made
`notificationDelivery` a **required** snapshot field, so any snapshot lacking it
was rejected wholesale and the screen would show `offline` rather than a wrong
label. The existing fixture tests caught this only now: the field is optional with
a `not-configured` default, unknown values are still refused, explicit coverage
was added, and **7/7 control tests and 13/13 across both suites pass**.
**D4 (recorded):** working-tree `tsc` fails because `api/certificates` passes a
string while the preserved, unshipped working-tree `k8s.ts` expects
`readonly string[]`. The released tree (`82580115`) carries the deployed string
signature and built successfully, so this is divergence with the in-progress
refactor, not a release defect — but I had reported a clean typecheck earlier and
did not re-run it after adapting the routes.
**D5 (false alarm):** I reported 12/12 Kustomizations healthy and a later sample
read 10/12; re-querying showed `migration-releases` and `plex-vip-controller` both
`Ready=True`/`Healthy=True`, so the earlier sample caught reconciliation.
Re-verified good: 3/3 nodes Ready with no pressure, BORTUS ready on
`sha256:44a163a9…`, 14/14 certificates healthy, zero CSRs, all monitor/sender/CSR/
watchdog units `active`/`enabled` on their own hosts. My earlier wording that
"every non-owner gate is closed" was too strong. Evidence:
`self-audit/self-audit.json`, `monitor-delivery-state/`.
The owner then chose **option 2 — enable the notification web UI** (D1). The private
config now serves the web app (`web-root: /`, `enable-login: true`) while
`enable-signup` stays `false` and `auth-default-access` stays `deny-all`, so the
app shell is public but **every topic read still requires a login** (verified:
anonymous `GET /bortus-certificates/json?poll=1` → **403**, authenticated → 200).
Because `/` previously returned `{"code":40401,...,"error":"page not found"}`,
`/auth` is an `emptyDir` and users are provisioned from `NTFY_AUTH_USERS`, the
`bortus-subscriber` password hash was replaced **in the native Secret** (a CLI
change would vanish on restart), preserving both publisher identities and all
three tokens. The private gate moved with the change: the normalized-config byte
pin became `914d375c…`, with the reviewed delta documented and the two changed
keys asserted individually; **44 tests + validator passed**, published as
`f5f9af8…` and applied by Flux.
**Incident, recorded rather than hidden:** my first Secret write used
`name:hash` without the required `:role`, so ntfy **crash-looped for about six
minutes**; the rollout watcher caught `CrashLoopBackOff` and the log read
`invalid auth-users ... expected format: 'name:hash:role'`. The root cause of my
error was reading the old 65-character field as hash-only when it was a 60-char
bcrypt hash plus `:user`. Rewriting the entry and restarting returned the pod to
`Running 1/1`; the monitor outbox was empty (`pending 0`) so no event was lost,
and delivery still reads `delivered` with `lastRun: complete`. A human-visible
test message ("Attended receipt test") was published to `bortus-certificates`
(HTTP 200) and confirmed readable through the subscriber credentials, so the
attended receipt is now waiting only on the owner's confirmation.
Evidence: `ntfy-web-ui/{web-ui-acceptance.json, push-result.json,
users-before.b64, unit-tests2.log, validation2/}`.




With this, every non-owner gate in the plan is closed. Both owner decisions were
subsequently taken: the **vaultwarden 8096 restriction was approved and applied**,
and the **attended subscriber/reader receipt was explicitly deferred**, so it
remains open and unverified. The only outstanding plan item is therefore that
deferred attended receipt; no completion claim is made for it.
























### Phase C — Plaintext reduction: read-only node-IP inventory (started)

Inventory only; no firewall, Service, port, Secret or certificate change was
made. Cluster side: 22 services publish through `externalIPs` on all node IPs
(plex stack, mealie, vaultwarden, ruckus, web-apps, pihole public/exporter,
traefik 80/443), one NodePort service (traefik 30080/30443) and three MetalLB
VIPs (192.168.0.252 traefik, .253 DNS, .254 Plex).
Host side, 17 listening surfaces exist on node IPs: 2002 SSH, 6443 apiserver
(TLS, SANs include each node IP), 2379/2380 etcd (TLS), 10250 kubelet (TLS),
10256 kube-proxy healthz (plaintext), 32158/32359 kube-proxy
`healthCheckNodePort` (plaintext JSON naming `traefik-lan` and `pihole-lan-dns`),
7946 MetalLB gossip (plaintext), 9120 MetalLB metrics (self-signed localhost
certificate), 9090 Cockpit (self-signed per-node certificate), 179 BIRD, 111
rpcbind, node01-only 2049 NFS and 29644 SMB-CSI, and node03-only 10554 pihole-FTL
backing the advertised LAN DNS path.
Recorded candidates for later, separately reviewed tightening: restrict the two
`healthCheckNodePort` listeners and Cockpit to cluster/admin sources, restrict
rpcbind/NFS/SMB-CSI to media clients, restrict MetalLB gossip/metrics to node and
monitoring sources, and restrict each published `externalIPs` service to its real
client range. Limitations: UDP payloads were not verified, per-port client
populations are unmeasured, and the node03 DNS/DHCP path was inventoried but not
exercised. Evidence: `plaintext-inventory/phase-c-findings.json` and its six
supporting JSON files (cluster exposure, attributed listeners, node-IP probes,
TLS identities, healthCheckNodePort probes).
Phase C then moved from inventory to one reviewed restriction. Bounded sampling
(60 s per node, `ss` live sockets with a validated parser; `conntrack` returned
no rows) measured **zero** clients on 32158, 32359 and 9090 on all three nodes,
while the control port 2002 showed the operator source and kubelet 10250 showed
the node01 apiserver. With no measured consumers, a fixed nftables input table
(`branconet_plaintext_restriction`) now rejects those three ports except from
loopback, the three node IPs and the operator host, applied serially across
nodes by `playbooks/plaintext-restriction.yml` with a `check` mode and a
documented `remove` rollback. Verification: all three ports remain reachable
from the operator host on every node, a pod-network source was rejected (Reject
counter incremented on node01), UFW itself was neither reordered nor disabled,
and the cluster/kubelet control path is untouched. Sampling limitations are
recorded: a 60-second window cannot see occasional clients, and the 22
`externalIPs` publications are still unrestricted.
Phase C then measured the published `externalIPs` services properly. Host `ss`
cannot see DNAT'ed service traffic, so sampling moved to `conntrack -L
--dport <port>` (75 s per node, validated by a generated control flow). Measured
real clients include Plex 32400 from internet peers (34.202.97.122,
174.91.168.36), LAN DNS clients .243/.244/.245 plus in-cluster pods on 53, and
in-cluster pods reaching the arr/web ports through node IPs. The
pihole-exporter publication (9617) had **no** in-cluster scraper — pods scrape
the ClusterIP — so it was restricted next, in a second fixed profile of the
same helper. That attempt exposed a real design error: an `input` hook cannot
restrict published Service traffic because it is DNAT'ed and forwarded; the
profile was corrected to a `forward` hook at priority −10. Verification after
correction: operator and cluster-node access to node01:9617 returns 200, a pod
on node01 reaching node02:9617 is blocked, and the reject counter stayed zero
for the operator probes. Node02/node03:9617 refuse at the endpoint layer
because the exporter pod runs only on node01; that was untested before this
step and is not caused by the rule. Rollback remains
`--extra-vars "restriction_profile=pihole-exporter restriction_action=remove"`.
A third restriction followed the same measured pattern. A 120-second
conntrack window showed **no** clients on 3306 (ruckus-db), 8088, 8089, 8096,
8082 or 8083; only 8080/8081 saw traffic, and solely from the node's own IP.
The database port was therefore restricted first via a `ruckus-db` forward-hook
profile. That step exposed a second real design fault: cross-node Service
traffic reaches the target node with a **pod-network source**, so a LAN-only
allowlist silently rejected in-cluster consumers (reject counter rose and the
connection was refused). Both forward profiles now also allow `10.244.0.0/16`,
after which the operator gets the MySQL 8.4.13 greeting from all three node IPs,
a cluster node connects, and the earlier pihole-exporter "endpoint layer"
note was corrected — all three node IPs return 200 once the pod CIDR is
allowed. A spoofed-source probe was attempted but proved inconclusive: an
unlisted source is dropped by reverse-path filtering before the rule, so
rejection evidence rests on the real pre-fix cross-node refusal, not spoofing.
A fourth restriction covered the ruckus-bot publication. A 60-second conntrack
window showed no clients on either published port, and both `3003` and `8088`
were restricted together (a service profile must cover every published port, not
just the one under discussion). Verification after apply, with the pod CIDR in
the allowlist: the operator host receives HTTP 200 on `:8088` and HTTP 404 on
`:3003` from **all three** node IPs (the 404 is the application's own response,
so both are reachable), a cluster node gets the same codes, an in-cluster pod
reaches both ports through a node IP, and the reject counter did not move during
any allowed probe. An initial operator probe helper reported AttributeError;
direct HTTP probes proved the service reachable, and the helper defect is
recorded rather than the network. Remaining published services (8089, 8096,
8082, 8083, 8080, 8081, 8089 and the Plex/DNS/traefik set) are untouched.
A fifth restriction covered mealie (8089). A 90-second window measured no
node-IP clients for either 8089 or 8096, but only mealie was restricted:
vaultwarden is a credential-vault path whose clients (phones, extensions) sync
sporadically, and a 90-second silence cannot prove absence, so it is deferred
pending an owner decision or long observation. After apply, the operator
receives HTTP 200 for mealie from **all three** node IPs, a cluster node and an
in-cluster pod also get 200, and the reject counter did not move during any
allowed probe. Remaining published services are 8080/8081 (node-self traffic
only), 8082/8083, 8096 (deferred) and the Plex/DNS/traefik set that has real
external or LAN clients.






### Retire unused certificates safely

Add a **Retire certificate** workflow. `wordpress/jtmb-cc` is the first candidate,
not a deletion already performed:

1. Recheck workloads, routes, Secret references and external consumers.
2. Preview the exact resource and proposed retirement with dependencies.
3. Remove the declaration through the existing private charts validation and
   Flux path; do not make a live-only change that reconciliation will undo.
4. After reconciliation, remove the exact live Certificate explicitly because
   pruning is disabled.
5. Preserve the TLS Secret and application data, inspecting ownership rules
   first to prevent cascading deletion.
6. Verify Flux does not recreate it and active endpoints still work.

Discovery of an apparently unused certificate flags it for review, never
automatic deletion. The historical December 8 renewal date is a reason to
prioritize review, not proof that the resource remains unused now.

### Delivery sequence

**Phase A — Checkpoint existing work**

- Reconcile the working frontend with the deployed source and current refs.
- Review the TLS scripts, playbooks and documentation.
- Commit only owned files/hunks and verify unrelated staged and unstaged work
  remains intact. Extensive mixed changes require a scoped checkpoint, not
  `git add .`, index clearing or a blanket root commit/push.

**Phase B — Deliver Certificates & Trust**

- Implement inventory, UI, durable job history and scheduled monitoring first.
- Qualify and enable safe kubelet renewal approval.
- Deliver dependency-checked certificate retirement.
- Qualify scheduled control-plane renewal and its maintenance/recovery controls.
- Verify notification delivery, missed-run detection and worker availability.
- Update all affected API, permission, deployment, TLS and workflow docs with
  behavior changes. Release only after existing application security,
  accessibility, resource, recovery/data and private delivery gates pass.

**Phase C — Reduce plaintext exceptions**

- Inventory direct node-IP ports and actual consumers; do not infer disuse
  merely from a short quiet observation window.
- Migrate HTTP callers to trusted HTTPS. Protect database and other non-HTTP
  connections with protocol-appropriate controls.
- Remove unused exposure through private charts, then tighten mTLS policies
  incrementally while preserving required routes.
- Test access through node-IP ports as well as direct pod/Service paths:
  source-address translation can obscure the original caller, so a node-source
  allow rule is not proof of original-client authentication.

**Phase D — Extend mesh coverage**

1. BORTUS first: qualify admission protections, native Secrets, Kubernetes API
   access, streaming, probes, authentication and persistence.
2. Selected Plex applications individually after dependency checks; preserve
   VPN isolation/leak protection, media playback and discovery. Do not
   blanket-enroll the shared namespace containing VPN and host-network traffic.
3. Pi-hole: qualify DNS access restrictions and encrypted upstream transport
   separately. Client-to-Pi-hole encryption depends on client support; ambient
   mTLS does not protect UDP DNS. Keep coverage exceptions explicit.

### Acceptance and stopping criteria

- Valid kubelet renewal completes unattended; invalid requests remain unapproved
  with clear reasons. Verify the new certificate at the actual node endpoint.
- Automation survives worker/BORTUS restarts without repeating completed
  mutations; unknown outcomes are reconciled, not blindly replayed.
- Retired certificates stay retired while retained Secrets/data survive.
- Control-plane renewal preserves quorum and demonstrates recovery and
  managed-consumer refresh before unattended activation.
- Required application routes continue working; removed plaintext paths and
  unauthorized identities fail, including node-IP exposure tests.
- UI workflows pass keyboard, screen-reader and permission checks; observers
  cannot mutate infrastructure.
- Effective RBAC/admission, resource impact, backup/recovery, persistence,
  notifications, rollback and exact deployed revisions have actual evidence.
- Keep incomplete coverage visible. A feature milestone does not complete the
  entire follow-up roadmap.

### Follow-up execution state

- Phase A completed: local checkpoint `5f643ac22597d0422a5be8d22b16b3b4b11814c7`
  at `refs/heads/checkpoint/bortus-tls-foundation` contains only nine owned TLS
  paths (including the existing saved-credential dependency and scoped doc
  sections). Active HEAD and the original index were not changed. All 1,002
  frontend files reconcile to deployed source `34b8fa18`: 25 byte-identical,
  977 differing only in CRLF/LF, no content differences. Live BORTUS was Ready
  on immutable image `e7539b9e…`. Nothing was pushed.
- Phase B in progress: initial read-only `/certificates` UI and
  `/api/certificates` inventory added to working source. It distinguishes
  approval/issuance from installed verification and unavailable data from
  empty inventory. Monitoring-policy controls and durable observations are now
  integrated in working source; host/mesh checks, approval and maintenance
  automation remain explicitly unavailable.
- Initial verification: six inventory tests passed, including Kubernetes
  typed-list `items:null` normalization without accepting malformed data. The inventory function
  read the real operator API and returned 14 cert-manager Certificates and
  three issued CSRs, with both sources available and endpoint/host/consumer
  gaps explicit. This is an operator-backend read, not proof of production
  BORTUS RBAC or rendered UI acceptance.
- Strict CSR validation now uses Python `cryptography` with signed-request
  tests, exact subject/SAN/group/usages checks, node UID/address enrollment,
  request-age limits and CAS approval. A new check-only mode has no mutations.
  No live CSR was approved. Existing historical rollout evidence is not
  retroactively claimed as testing these new checks.
- Durable monitoring foundation added: an explicit once-only runner, private
  H state directory, scoped KUBECONFIG requirement, exclusive lock, SQLite
  observation/run history and deduplicated notification outbox. Four in-memory
  persistence/failure tests passed in the first slice. The UI is now connected
  through fixed policy/observations ConfigMaps. No scheduler or notification
  delivery is installed.
- Additional verification: six strict CSR tests passed, including a
  cryptographically tampered request. The monitor also completed an operator
  API scan into in-memory SQLite (no on-disk state or scheduling enabled).
  All four new TypeScript/TSX files passed syntax/transpile checks with the
  existing read-only dependency image. A selected UI typecheck could not
  resolve `lucide-react` in that reused image; application dependency
  typechecking, build and rendered UI acceptance remain unrun, not passed.
- Storage preflight: the initial broad logical-size scan was unsuitable
  (sparse disk plus permissions). A filesystem-scoped allocated-byte scan
  measured 15,812,886,528 readable bytes in the mounted store, but excluded
  private directories and shared runtime contents. The backing sparse store
  itself has 279,457,562,624 allocated bytes and is not an additive measure of
  repository payload. Existing preserved-corpus/producer attribution must be
  reconciled before admitting new dependency/build bulk. No unknown data,
  shared images, volumes or caches were deleted, and no new dependency tree
  or image was built. Read-only checks reused an existing image and removed
  their exact ephemeral containers.
- Monitoring control integration (source complete, not deployed):
  `PATCH /api/certificates/policy` enforces fresh operator access, same origin,
  a 4 KiB body, exact schema and UID/resourceVersion CAS; the last 50 changes
  retain operator/time metadata. Only paused/monitor mode is supported.
  Runner `--control-plane` publishes durable observations and a 60-second
  heartbeat; `--loop` honors scan interval and warning threshold, records
  acknowledged policy UID/revision, and refuses policy drift during a scan.
  A failed publish does not repeat a recent scan. Missing/stale heartbeats,
  unacknowledged policy and degraded sources are distinct UI states.
- Latest focused checks: 12 app/control tests and nine monitor/control tests
  passed, including an actual Python snapshot consumed by TypeScript.
  Selected control/UI types passed using existing dependency-image types.
  An isolated browser component/API fixture verified save → pending,
  acknowledgement → paused, stale-write feedback, readonly controls/direct
  PATCH 403, historical observations and offline heartbeat. This is not a full
  Next build, production styling, actual screen-reader, deployed RBAC or
  production-runner acceptance. The first fixture launch failed on an unset
  diagnostic module filename; that fixture-only error was corrected before
  the successful run. The private browser session and exact task containers
  were closed/removed; no dependency tree, bundle files or image was created.
- Private charts now contain an inactive `flux/certificate-monitoring` candidate
  with paused seeds and separate fixed-resource UI/monitor grants. All nine
  objects passed Kubernetes server-side dry-run. It is absent from active
  release composition and remains uncommitted/unpublished. Neither role grants
  Secret access, CSR approval, token minting or host operations. Flux
  `IfNotPresent` preserves operator/runner data after initial bootstrap.
- First unfinished action: complete attended screen-reader acceptance and
  qualify host-monitor service resource/restart/persistence behavior and
  notification delivery before its rollout. Installed external credential
  execution/resource/periodic checks now passed (see latest section).
  Complete the remaining certificate
  approval/retirement/host-renewal work. No feature deployment, automated
  approval, renewal or retirement has occurred; Phases C and D have not started.

Restart continuation: the interrupted takeover-handoff update is restored.
HEAD remains `9d53d7c0` and the original index hash is unchanged. The broad
historical dependency search was cancelled by another server restart before
returning results; no dependency discovery or completed accounting is claimed
from that attempt. A bounded check of five known historical dependency
locations found none present; this does not establish that all reusable
dependencies are absent. No full build or new dependency bulk was started.

Independent-runner readiness then fixed two concrete issues: subprocess output
limits now apply during concurrent stdin/stdout/stderr draining, and a restart
immediately retries an interrupted read-only scan instead of waiting for its
configured interval. Five new focused checks passed (pipe-pressure input/output,
stdout/stderr overflow, sanitized failure, deadline with pipe-holding descendants,
and interrupted-scan recovery); unchanged UI/browser checks were not repeated.
The new bounded transport also read the real Certificate and CSR endpoints:
14 Certificates, zero current CSRs, 33,105/132 response bytes. These were
read-only operator checks, not scoped-runner acceptance or live approval.
Current mounted-store used space is 58,392,096,768 bytes with 440,562 free
inodes; that filesystem-wide observation includes other projects and is not
repository admission. Backing allocation was 279,605,608,448 bytes; it remains
distinct from payload accounting. Storage attribution, full application build
and real durable/always-on runner qualification remain open.

Dependency reuse follow-up: retained security-qualification v1–v8 trees were
located in the existing H packaged-app corpus. The v8 tree has TypeScript 5.9.3,
React 18.3.1 and lucide-react 0.460.0. Reusing its type files read-only, the
complete certificate screen, monitoring controls, inventory and control types
passed with zero diagnostics and no emitted files. This closes the selected
UI check's missing-icon limitation, not application-build acceptance. V8's full
lock/schema differ: 263 installed package manifests were read, with numerous
version mismatches, 317 missing lock entries (including development packages),
and Windows rather than Linux SWC/Prisma binaries. Do not build or install over
that preserved tree, or call it the qualified current application environment.

Storage cleanup admission: the 2,900,746,240-byte staging-only
`application-artifacts-20261023.tar` in the existing coordinator run duplicates
the retained H `files/application-artifacts-20261023` payload. GNU tar comparison
of data/ACLs/xattrs/numeric ownership passed (exit 0, 77.35 seconds). An earlier
180-second attempt timed out without a comparison result; the bounded
continuation completed. All 19 members and the original compatibility alias
remain; the archive's original verification/hash receipt remains. Regeneration:
GNU tar with PAX/ACL/xattr/numeric-owner/sparse preservation from the retained
directory; no byte-identical outer tar encoding is required for this completed
transfer. No script references the outer archive as an input.

Reference admission: no visible Linux open-file or mount match; 170 process FD
tables were unreadable, so that scan alone did not establish inactivity. Windows
exclusive read access passed, and a controlled reader of the same file in WSL
made that exclusive access fail until the reader closed. This establishes the
cross-boundary exclusion check rather than waiving the Linux visibility gap.
The exact archive is admitted for ordinary literal deletion only; retained
application OCI payloads, source and unique records are not cleanup targets.

Completed: ordinary Windows literal deletion removed that exact outer archive;
post-check verified it absent, all 18 retained payload files still total
2,900,715,620 bytes, and the source alias plus original verification receipt
remain. **Removed: 2,900,746,240 logical and allocated bytes.** No application
OCI file was removed and no Windows C-space recovery is claimed.

Native Windows enumeration corrected the slow DrvFS whole-tree measurement:
`H:\AgentArtifacts\projects\bortus` contains 88,017,201,245 logical file bytes
in 569,313 files, with no enumeration errors and two reparse entries skipped.
This is not allocation or hardlink deduplication. The prior DrvFS `du` attempt
timed out after 540 seconds and produced no complete root measurement.
The coordinator runs contain 7,145,003,381 logical bytes after the first archive
retirement (before any second retirement). Separately, non-following Linux
`du` found 48,362,647,552 allocated bytes under the legacy runtime, with eight
permission gaps; aliases are excluded and their H targets remain separately
chargeable. These measurements do not establish a compliant combined total.
New dependency/build bulk remains unadmitted.

The second staging archive `ci-image-artifacts-20261024.tar` is 2,079,170,560
bytes. Its new payload/metadata comparison was cancelled by another server
restart before a result; it remains retained and no comparison/deletion pass
is claimed. V2–v8 dependency trees are also retained: the v9 cleanup receipt
explicitly preserves their immutable failed-run inputs/evidence, so discovering
old installed modules does not make those trees eligible for deletion.

The interrupted second-carrier comparison was subsequently completed: exact
membership matched 100 retained entries and GNU tar data/ACL/xattr comparison
passed (exit 0, 59.13 seconds), with 2,078,997,328 retained payload bytes.
There are no visible open-file/mount references or script inputs for the outer
tar. Windows exclusive file access passed; Linux FD visibility has 44 PID gaps,
covered by the previously calibrated cross-boundary exclusive-file check,
not by claiming a complete Linux scan. The exact 2,079,170,560-byte outer tar
is admitted for ordinary literal deletion. Its verified receipt and retained
payload/source alias remain outside the deletion scope. Regeneration uses GNU
PAX tar with ACL/xattr/numeric-owner/sparse preservation from the retained
`files/ci-image-artifacts-20261024` directory; byte-identical outer encoding is
not required for this completed transfer container.

Second retirement completed: ordinary exact Windows literal deletion removed
`ci-image-artifacts-20261024.tar`. The post-check confirms the outer tar absent,
all 92 retained files still total 2,078,997,328 bytes, and the original alias and
verification receipt remain. **Both redundant carriers removed:
4,979,916,800 logical/allocated bytes.** The coordinator-run logical total after
the second retirement is 5,065,832,821 bytes by subtracting its exact measured
size from the preceding complete enumeration; this is not a new whole-tree
measurement or a claim of a compliant repository total. No active services,
protected old failed runs, application images, credentials or data were removed.

Next admission action: reconcile producer attribution and exact retained
consumers across the 88,017,201,245-byte H BORTUS root, legacy runtime and
mounted shared store. Do not add those location totals blindly (aliases,
hardlinks, distinct producers and private measurement gaps remain), or treat
this cleanup as permission for a dependency install. Full Linux application
build and scoped durable/always-on runner qualification remain unfinished;
the historical Windows type tree is a read-only source-check input only.

### Current dependency/build admission decision

New dependency/build bulk is **not admitted** under the normal 100 GB rule.
The producer/alias/retention ledger is recorded in
`operations/DOCKER-H-STORAGE.md` ("Certificates & Trust build admission").
The largest held recovery capsule alone is 53,920,129,364 bytes, included in the
88,017,201,245-byte H location total; it preserves mixed homelab members until
replacement/regeneration is established. Legacy BORTUS security and delivery
roots separately have 12,233,007,104 and 4,350,091,264 readable allocated bytes.
These are different measures, not a certified additive repository total.
Private gaps, H aliases and other producers must not be hidden or charged
twice. Completed eligible cleanup remains 4,979,916,800 bytes; no newly screened
protected corpus or shared runtime object was cleared for retirement.

Current-lock sizing is now concrete: 504 conservative Linux/x64/glibc install
locations, 495 distinct public manifests, 834,617,149 logical unpacked bytes.
All version/integrity checks matched; missing sizes for 23 old packages were
measured from small bounded in-memory tarballs, not saved or installed.
The pinned Linux build input check passed all 10 Node/compiler/header hashes.
The omitted `--pull=never` on its first attempt triggered an unexpected Node
fetch; subsequent checks pinned the existing image ID with pull disabled.
That event and its unmeasured incremental storage are explicitly accounted in
the storage ledger; no full build, dependency tree or production rollout ran.

Proposed next-stage ceiling: 4,000,000,000 incremental H bytes for one current
dependency tree, install cache/temporaries, build output and synthetic
runner/UI checks, with reserve-specific refusal before an over-budget
substage. This is not admitted and does not reuse the former review-only
exception. The remaining decision is fresh explicit authorization for that
bounded stage while protected legacy attribution is reconciled, or continued
legacy reconciliation until ordinary admission is established. No global
allowance increase, new disk/root or deployment authority is implied.

### H retry result — shared transport/store needs coordinated recovery

James requested retrying H in response to the bounded-stage question. The
retry kept the 4,000,000,000-byte stage ceiling and performed read-only admission
checks only. Windows H has 390,930,190,336 free bytes and sees the existing
backing file/temp directory. WSL's `/mnt/h` still lists H: as its 9p mount, but
those paths return ENODEV; the nested loop0 ext4 directories return EIO.
Kernel observations show loop read/write failures and an aborted ext4 journal,
including failed superblock writes. Cached filesystem free-space figures are
not proof of writeability. No dependency install, new stage directory, output
symlink or application build was started.

This is now an availability/recovery boundary, not a request to recheck free
space or rerun completed tests. The existing Docker/containerd services share
the affected store. No service, mount, device or workload was stopped, reset or
repaired. The required next decision is a coordinated local maintenance window:
verify consumers are idle, recover the existing H transport and inspect the
existing store offline before selecting a preservation-safe repair. No live
cluster mutation, WSL shutdown, new mount/root or automatic fsck is authorized
by this observation. Details and exact errors are in `operations/DOCKER-H-STORAGE.md`.

The subsequent externally initiated restart also restarted WSL. In current boot
`e72801ac-8c43-458f-86b4-5e74f9c4a756`, H reads are restored; loop0 reports zero
errors with active journal commits. A 65,536-byte H fsync/readback/unlink probe
passed and was removed. This supersedes the immediate shared-recovery hold;
this agent did not stop services or repair/remount the filesystem. The earlier
maintenance question was interrupted, not answered or used as authority.

Continuing James's directed H retry within the 4 GB stage described above:
`scripts/migration/qualify-certificate-frontend.py` prepares an in-place,
read-only-source Linux qualification with one H dependency tree, fixed H
output binds, pinned existing Node image/pull-never, substage/total size guards,
source/lock/index binding and retained started/result records. No new checkout
or source snapshot is created. Empty ignored source directories are mountpoints
only; native/worker source inputs remain read-only mounts. Containers retain
2 CPUs, 1 GiB/no swap and PID256. This is preparation, not a passed build or
runner acceptance, and does not change global storage/deployment boundaries.

### Current Linux qualification execution

- Current-lock install passed in 65.68 seconds: 1,190,854,656 stage bytes,
  source/lock/index unchanged. Source-maintained dependency preparation and
  Prisma generation passed; the stage then measured 1,304,059,904 bytes.
  These completed steps must not be replayed after a restart.
- First build stopped in native prebuild because GCC deliberately sanitizes
  TMPDIR. The driver now mounts the same H temp at `/tmp`; pinned native
  compilation then passed two identical compiles, ELF hash
  `8dde4ce66cf7045bfa7d5c0c0fb8ad3ff3d98809fbe24b76487b520ea664f6c2`.
  Its failed log is retained.
- The next build found a real page defect: `CertificatesPage` awaited operator
  authorization without an async declaration. The page is now async. The
  following build compiled but failed required React-hook lint; monitoring
  policy synchronization now declares its dependency and guards UID/revision
  so ordinary heartbeat responses preserve unsaved edits.
- Unfiltered `npm run lint` passed for the checkout bound to 993
  source/config/test files. Source fingerprint
  `85876117c63b70ed7470dce53ebeffa354f46cf190a1a20c7b8c2a87b4fd635b`.
  The combined Next worker hit its default 512-MB heap; a serial attempt also
  exhausted 768 MB while exposing the whole test corpus. No memory/cgroup limit
  or check was relaxed. Existing `.dockerignore` excludes `tests` from the
  actual release context; `build-context` now mirrors that exact rule with a
  read-only empty mount, keeping all application/generated-route type checks.
  The matching full lint pass is mandatory. Whole-checkout test typechecking
  is not passed, and default `npm run build` has not passed.
- `build-context` passed in 72.42 seconds, including application/generated-route
  type checks and native/worker packaging, with the matching full lint pass.
  Observed stage peak: 1,699,647,488 bytes; retained output at completion:
  1,680,080,896 bytes. Source/lock/index stayed unchanged. This is the existing
  release context, not a passed whole-checkout test typecheck or default combined
  `npm run build`. No publication or production connection occurred.
- A real H SQLite persistence check passed across two separate processes:
  identical run ID, one observation/notification and no replay within interval.
  A competing process was denied the lock, then acquired it after release.
  The four finished synthetic DB/snapshot/lock files were removed (61,440
  allocated bytes), preserving the small result/cleanup records. This is
  durable-core evidence only; scoped identity/always-on service and notification
  delivery remain unfinished.
- A focused real-application fixture is prepared at
  `tests/certificate-application-fixture.mjs`: current Prisma schema, actual
  login/role authorization and built Next assets with local synthetic kubectl
  responses/state. Syntax passed in the pinned read-only Node container.
  The `fixture` step completed with clean exit after 719.7 seconds, no bounded
  failure, and unchanged source/lock/index. Do not reinstall/rebuild or replay
  its passed desktop/API checks.
- `application-browser-result.json` records 18 checks against real built
  Next/Prisma/auth: operator login/inventory, keyboard policy save, pending →
  acknowledged pause, same-revision unsaved-edit preservation, readonly disabled
  controls, offline/historical observations and production CSS. API denials:
  readonly/non-admin writer/cross-origin 403, stale revision 409, oversized body
  413, invalid policy 400; denied writes preserved the policy. Revoking operator
  access in SQLite made the same session's write return 403. Desktop screenshot
  retained (141,357 bytes); build ID `mVyRgO-5RneuqgCW4GHLa`.
- At the first fixture checkpoint phone responsiveness was unverified: the
  requested 390px popup remained 800px. Later actual viewport results follow. Keyboard/accessibility-tree
  checks are not attended screen-reader acceptance. Production RBAC,
  notification delivery and always-on runner acceptance remain unfinished.
- The exact fixture container and isolated browser closed. Finished synthetic
  SQLite/kubeconfig/fake CLI removal reclaimed 319,488 allocated bytes; four
  small public synthetic metadata JSON records remain. Empty source routing
  directories and the owned build-info link were removed.
- The admitted exact `npm` (234,057,728 bytes) and `next/cache` (227,749,888
  bytes) were revalidated and removed: **461,807,616 allocated bytes**. Retained
  stage measured **1,218,887,680 bytes before its small cleanup receipt**.
  `cache-cleanup-result.json` preserves the result. Dependencies, built runtime,
  unique logs/results and screenshot remain for outstanding acceptance.
- The qualification driver now supports fresh attempt-specific application
  fixture directories (`fixture --attempt <label>`), retaining earlier metadata.
  This changes no frontend/build input, so remaining viewport qualification can
  reuse the matching successful build. Never relaunch into the old fixed
  `application-fixture` directory or replay a completed attempt.
- Real viewport qualification is now possible using the installed browser CLI's
  supported `set viewport` on the same isolated MCP session. Before correction,
  390px and 320px views both had 404px page width: long Kubernetes resource names
  escaped the monitoring panel. `responsive-before-result.json` and phone
  screenshot preserve that defect. The monitor panel now uses wrapping for
  unbroken text, with no data clipping or behavior change. Fresh lint/build and
  rendered phone verification are required for this changed source. The driver
  selects explicit named `--lint-attempt`/`--build-attempt` receipts to retain
  earlier results without accepting a different source fingerprint.
- Phone-wrap full lint/build passed (77.39 seconds; stage peak 1,426,976,768
  bytes). Real 320px/390px page widths now equal the viewport; panel and expanded
  observations have no horizontal overflow. The 390px table's last column is
  reachable by local scrolling. `responsive-phone-wrap-result.json` preserves
  evidence. Axe 4.12.1 then found two genuine accessibility defects: CSR
  timestamp contrast 4.11:1 (<4.5) and a non-focusable scroll container.
  Timestamps now use zinc-400; the table wrapper has a named region, tab stop
  and visible focus. Fresh lint/build/audit and keyboard-scroll checks are
  required for these changes; no actual-reader acceptance is claimed.

### Current responsive/accessibility result — 2026-11-16

The subsequent `phone-a11y` full lint and release-context build both passed on
fingerprint `561826437128d627d2b59fff280749902700db4d40c1673caf77da8a04f87dea`
(993 files); build ID `1Z4OrQk6ue0Sv4szH1jFe`. Build took 70.82 seconds, with
1,446,993,920 observed stage bytes and unchanged source/lock/index. The named
fixture closed normally (exit 0, 117.89 seconds); all three new phone fixture
attempts have clean exit results. No dependency install or production access.

`responsive-a11y-result.json` records:

- Actual 320px/390px viewport and page widths match exactly. Monitoring panel
  client/scroll widths match (230/230 and 300/300). Long metadata wraps.
- Tab from search reaches **Certificate metadata table**; its 2px solid focus
  outline is visible. Real ArrowRight input changed its scrollLeft to 48px.
- Axe 4.12.1 at 320px: zero violations; one incomplete contrast rule covering
  five offscreen cells. At 1280px with those cells visible: zero violations and
  zero incomplete rules. This resolves the automatic audit only, not every
  accessibility requirement.
- Actual phone rendering was inspected and screenshots retained. Unchanged
  auth/policy/API acceptance is explicitly reused from the prior application
  result; those checks were not repeated for presentation-only changes.

All owned browser sessions and fixture containers are closed. Exact regenerated
Next cache and nine finished synthetic DB/kubeconfig/CLI files were admitted
then removed: **228,614,144 allocated bytes**. Retained stage is
**1,219,219,456 bytes before its small receipt**, under the same 4 GB cap.
Source mountpoint directories/build-info link are gone; current dependencies,
built runtime, unique results/logs/screenshots and public synthetic metadata
remain for attended-reader/release checks. Earlier cache cleanup is completed,
not a new deletion target; neither cleanup establishes normal global admission.

**Still required:** attended screen-reader announcements (not inferred from
axe/DOM/keyboard), scoped real runner identity and durable always-on service,
notifications and all remaining certificate lifecycle/plaintext/mesh phases.
The inactive chart candidate remains unpublished/unapplied. No feature release,
approval, retirement, renewal or network rollout occurred.

### Independent runner host candidate — source qualified, not installed

Read-only SSH preflight reached all three nodes without become or mutations.
Each has Python 3.10.12, systemd 249 and `/usr/local/bin/kubectl`; the monitor
service is absent. Selected candidate placement: node02 (`workernode1`,
192.168.0.6), with 11,985,149,952 available RAM bytes and 90,013,511,680 free
bytes under `/var/lib` at observation. This is a placement choice within the
existing cluster, not a claimed deployed or highly available runner.

The local runner remains H-only. The new managed-host profile requires exact
root-managed code, fixed private state, an unprivileged process, fixed
CA-verified VIP-only kubeconfig/token-file paths and fixed kubectl. It refuses
exec plugins, insecure TLS, extra identities and ambient admin fallback; it
does not provision/mint credentials. Signal shutdown wakes the interval wait,
duplicate owners return a fixed outcome, and public/symlinked state is refused.

The inactive systemd candidate confines the runner to 256 MiB/no swap, 10% CPU,
64 tasks, no capabilities, read-only protected paths and cluster API VIP-only
network access. An initial Ansible candidate defaults to preflight, has only
explicit stage (never activate), refuses existing install/state targets and
stages no credentials or enabled service. No stage tasks were run.
The database has a verified 16 MiB page ceiling, keeps 1,000 recent runs and
delivered notifications, and never discards pending notifications to free space.
The unit's separate 20 MiB individual-file ceiling is not a whole-filesystem
quota; a SQLite rollback journal can temporarily add up to another database.

Verification recorded in `runner-host-candidate-result.json`:

- **18 tests passed**: modified monitor/control integration plus six actual
  entrypoint/profile tests. Separate processes reopened private SQLite without
  duplicate scans/outbox; the loop refused a contender, exited its wait on
  SIGTERM and released ownership. Malformed control state stayed sanitized and
  did not publish a fresh heartbeat. Growth-limit failure preserved existing
  metadata; bounded history retained undelivered alerts.
- Ansible syntax check passed. Local `systemd-analyze verify` returned 0; it
  also reported an existing unrelated Ingenium unit-symlink permission warning,
  which was left untouched. This is definition validation, not runtime policy.
- Node02 Python 3.10 parsed all five runner modules from stdin, with no source
  installed or executed on that host.
- The seven source/unit/playbook hashes and logs are retained. Synthetic test
  payloads were automatically removed; two empty temporary directories were
  then removed (8,192 allocated bytes). Stage usage before the small receipt
  was 1,219,244,032 bytes, under the existing 4 GB qualification cap.

Remaining before enabling this candidate: independently provision/refresh a
short-lived narrowly scoped identity; verify actual allowed/denied Kubernetes
operations; qualify the installed service's real resource limits, restart,
persistence and missed-heartbeat behavior; deliver notifications to a verified
free/self-hosted destination. Attended-reader and later lifecycle/network
phases remain open. No Kubernetes grants/ConfigMaps, tokens, node services or
production files changed. The private chart candidate remains inactive.

The new Ansible **read-only preflight** also completed on node02 with become
explicitly disabled: `ok=3 changed=0 unreachable=0 failed=0 skipped=9`.
All account/code/state/unit/reload tasks were skipped. Its first controller
attempt failed before tasks because the local RPC server did not start under
the long H temp path (exit 250); that failed log remains. The corrected attempt
used the repository's existing abstract multiprocessing Unix-address pattern
and passed without changing temp storage, permissions or infrastructure.
`runner-host-preflight-result.json` binds the playbook and exact result. The
empty controller temp directory was removed (4,096 allocated bytes); logs and
minimal evidence remain. This is live preflight wiring, not live runner/RBAC
or service acceptance.

### Scoped credential refresh and live RBAC — 2026-11-16

Implemented the root-only external credential broker and inactive twenty-minute
timer, with one-hour audience-bound tokens, pinned ServiceAccount UID,
root-managed fixed paths/CLI hash, bounded subprocesses, API-authenticated
SelfSubjectReview, representative effective allow/deny reviews and actual
metadata reads before atomic publication. Known UID/scope changes quarantine
the active local token file; transient failures leave the existing credential
unchanged until expiry. Values never enter arguments, Git, SQLite or logs.
The shared `ApiQualification` adapter is used by the root candidate and the
operator's live proof. Node02 Python 3.10 parsed both new modules; eight focused
tests passed for rejected identity/scope/expiry, transient errors and atomic
publication/cleanup. Service/timer definitions and updated Ansible syntax passed.

Private charts now separate **identity qualification only** from activating the
feature. Reviewed seven-path commit
`7e1c6c9eab42ead78f77c374a5a1cc555196bfd3` contains the five-object monitor
identity/RBAC child, its release reference, docs and the still-inactive six-object
UI/control candidate. No workload, static token Secret, UI grant or control
ConfigMap was enabled. The existing H-compatible singleton watcher was already
running; it was not restarted. Its exact-source CI passed **35 tests plus the
full unchanged chart validator**, promoted validated and Flux reconciled both
`migration-releases` and `certificate-monitor-identity` Ready at that SHA.
Seven Flux Kustomizations and 36 HelmReleases were inventoried, with no
unsuspended resource reported not Ready.
Unrelated private memory/config files were not staged. Actions stayed off.

Live ServiceAccount UID: `687ff70b-39a4-4555-9b17-cb02d83b4ec6`; automount is
false. The first real-token qualification authenticated and passed its reviews,
then failed safely on a diagnostic kind assertion because generic kubectl get
rewrites lists to `kind: List`. No token was published; candidate files were
removed. That failure is preserved. The adapter now uses exact typed raw API
endpoints rather than accepting arbitrary list shapes.

The distinct corrected attempt passed **7 allowed / 19 denied** effective
SelfSubjectAccessReviews and actual reads of **14 Certificates / 0 CSRs**.
A further deliberate two-cycle proof verified real refresh, not just initial
issuance: both cycles reauthenticated and rechecked all 26 permissions; the
second atomic replacement gave new readers a different complete token while
a held old reader retained the old complete file. Both token lifetimes were one
hour. These are representative boundary checks, not an exhaustive proof against
all possible future RBAC changes.

Records: `credential-bootstrap-publisher-result.json`,
`credential-live-qualification/{failure,cleanup}.json`,
`credential-live-raw-api/{result,cleanup}.json` and
`credential-live-rotation/{result,cleanup}.json` in the existing H qualification
stage. All four diagnostic issued tokens' files, pending kubeconfigs and
temporary public CA files were removed. No server-side token revocation is
claimed; issued tokens expire normally. Only metadata evidence remains.

**Still unqualified:** installed root broker/timer enrollment, real host
service/cgroup/restart/reboot behavior and periodic renewal, independent
missed-heartbeat/notification delivery, attended-reader acceptance and all
later certificate lifecycle/plaintext/mesh phases. Node02 confirms all three
candidate units still not-found/inactive. Both control ConfigMaps remain absent.
Only the reviewed identity/RBAC bootstrap changed the cluster; no host service,
app image, certificate lifecycle action or network/mesh policy was activated.
`credential-refresh-acceptance.json` binds the final six source paths and all
test/live results. `host-credential-enrollment-candidate.json` contains only the
pinned public UID/audience and node02's observed kubectl hash; it has not been
installed. Diagnostic/syntax payloads are gone; two empty directories reclaimed
8,192 allocated bytes. Current frontend qualification and publisher stages
measured 1,399,451,648 bytes combined, within the same 4 GB ceiling without any
normal-global-accounting or deployment-budget claim.

### Installed node02 credential broker — periodic refresh qualified

The user's next-step authorization covers staging public enrollment and
qualifying the actual broker/timer, **without starting or enabling the monitor**.
Initial staging completed once: `ok=20 changed=10 unreachable=0 failed=0`.
It installed the fresh unprivileged account/group, seven root-owned modules,
public CA/config/UID enrollment, private metadata directory and three inactive
unit definitions. Do not rerun the initial-stage play over this installation.
The bootstrap admin kubeconfig remains in its existing root-only location.

The first broker execution returned success, but the collector rejected its
pre-exec process-security sample. A read-only inspector then missed the success
record because journalctl's JSON output replaces fields over 4096 bytes with
null. Both collector failures remain in their original receipts. Corrected
`inspect --attempt journal-all` recovered the original successful invocation
`96552fd9952042ec9d77f5d409861fbb`, all 7 allow/19 deny checks and 14 Certificate/
0 CSR reads, with a root-owned 0640 runtime token and no pending files.

A separately recorded `once --attempt exec-sampling` passed **323 live cgroup
samples**. Kernel limits: memory 268,435,456 bytes, swap 0, tasks 64,
`cpu.max = 10000 100000` (10%). Maximum observed memory was 70,258,688 bytes
and tasks 5; memory events reported no OOM or OOM kill. CPU throttling counters
advanced under the real broker. The Python process had NoNewPrivs=1 and
effective/bounding capability mask `9` (CHOWN/FOWNER only). The retained first
sample shows systemd's pre-exec `(python3)` executor before applying those
restrictions, confirming why the original observation failed. No limit or
security property was relaxed; these observations are not a stress/OOM test.

Real UID998 access checks additionally passed: it can read the published token
and fixed public config, cannot read the bootstrap admin kubeconfig or broker
lock, and cannot write broker code, enrollment or token. Token group matches
the monitor account. Fixed kubeconfig validation and the existing public CA
hash match. No token bytes were printed or copied into evidence.

Only the credential timer is now enabled/active. Its initial invocation passed;
the recorded baseline is `27e371f4cddd47e1a2a2009e8244fda5`, and its next
monotonic due time is `1601308837483` microseconds on boot
`137455a5-2921-4691-ab8f-06bc53ad0c23`. The bounded, read-only `observe` phase
completed without resetting the timer or starting a service. **Actual periodic
refresh passed after 1,200.109143 seconds**, with new invocation
`6dec32e9716e4f07a03c93c1a0c13ed1` at/after that due time. Its journal confirms
7 allow/19 deny checks and 14 Certificate/0 CSR reads. The token inode and
mtime changed, ownership remained root:998/0640, and new expiry was
2026-11-16T17:34:14Z. Observer exit was 0; the monitor remained disabled/inactive.
Do not repeat the passed periodic check, `timer`, staging or manual execution.

Evidence in the existing qualification stage:
`node02-credential-stage-{started,result}.json`,
`node02-credential-journal-reconciliation.json`,
`node02-credential-inspect-journal-all.result.json`,
`node02-credential-once-exec-sampling.result.json`,
`node02-credential-installed-boundaries.json`,
`node02-credential-timer.result.json`,
`node02-credential-observe.{started,result}.json` and the hash-bound summary
`node02-credential-installed-acceptance.json`.
Monitor remains disabled/inactive. Installed monitor persistence/restart/reboot,
notification delivery, attended-reader, lifecycle/plaintext/mesh acceptance
remain open; no application or mesh rollout occurred.
The completed staging controller's exact empty `node02-staging-temp` directory
was separately checked then removed (4,096 allocated bytes). Unique logs and
failure/success receipts remain; H stage measured 1,219,440,640 bytes before
the cleanup receipt. The installed runtime token remains owned by the active
credential timer; it is not a diagnostic cleanup target.
This completes the authorized installed broker execution/resource/periodic
qualification, not the full follow-up. The observer is finished; only the
credential timer remains enabled. Node-reboot survival was not exercised.
Next dependency is scoped monitor-service and notification qualification;
the current step did not authorize starting the monitor or rebooting a node.

### Monitor qualification and notification path — preparation only

The next user direction explicitly requires preparation while the monitor stays
disabled/stopped. The new read-only `monitor-preflight` phase passed on node02:
installed checkpoint hashes match, UID998 owns the private 0700 state directory,
no monitor database exists, and the monitor is disabled/inactive. Both fixed
control ConfigMaps remain absent. Proposed source differences are recorded
separately from installed hashes; nothing was upgraded or provisioned.

The monitor unit source proposes a separate private volatile cache directory,
fixed HOME/XDG paths, unset proxies and accounting. This addresses the same
ProtectHome/read-only discovery-cache risk already corrected for the broker,
without changing any installed file. Do not rerun initial staging as an upgrade.
`CLUSTER-TLS.md` now defines the future paused-first qualification: bind policy/
observation UIDs and revisions, sample the actual unprivileged limits, test
durable completed/interrupted runs across stop/start, preserve pending outbox
events through controlled outages, and review results before enabling startup.
Those live steps still require activation authority.

No operational notification destination was found in repository configuration.
Selected **self-hosted ntfy** for the prepared delivery path; this is not the
public relay, a new server deployment, or a configured subscriber. An explicit
HTTPS topic/private-IP/CA/publisher-token-file profile has no default endpoint.
The separate dispatcher preserves the monitor's API-VIP-only network policy;
it cannot read Kubernetes bootstrap/runtime credentials. The candidate
notification unit defaults to deny-all egress and requires a reviewed exact
destination drop-in before any use. No credentials, ntfy server, client
subscription, DNS/TLS name or live message were created.

The new module/executable use the existing metadata-only outbox and a separate
sender lock. Pending events survive failures and unknown outcomes, with durable
60-second to one-hour backoff and no more than three attempts per batch.
HTTP runs outside SQLite write locks and each sender child is bounded to ten
seconds/1 KiB stdout and stderr. Only a valid matching ntfy server acknowledgement
marks a row delivered. This is at-least-once: a send accepted just before a local
crash may duplicate the same stable event ID. No exactly-once or attended
delivery claim is made. The dispatcher does not construct CertificateMonitor,
so it cannot mark another process's active scan interrupted.

**Preparation verification:** eight focused tests passed using synthetic H
SQLite/credentials and actual loopback TLS. They cover durable retry/restart,
unknown outcome/stable ID, sender exclusion, no active-scan interference,
trusted TLS/hostname, rejection of plaintext/public-address/credentialed URLs,
redirect/auth/backend failures, mismatched and oversized acknowledgements,
and actual separate CLI restarts without replaying acknowledged rows. This is
an ntfy-compatible fixture, not an actual ntfy server or subscriber acceptance.
Both new modules parse on node02 Python 3.10; local unit verification exits 0.
It retains the pre-existing unrelated Ingenium symlink warning and the newer
controller's ignored CPUAccounting warning; node02 systemd249 supports that
option. No dependency install, app build, broker/timer replay or rollout ran.

`monitor-notification-preparation-result.json` binds six source paths and the
checks. Logs, read-only node02 preflight and source-only unit differences remain
in the existing qualification stage. Synthetic DB/token/TLS-key payloads were
removed by test teardown; its exact empty directory was removed separately
(4,096 allocated bytes). Qualification plus current publisher stages measured
1,399,603,200 bytes before the small result receipt, within the same 4 GB cap.

**Next unaccepted gates:** reviewed unit/module upgrade and explicit monitor/
notifier activation authority; private ntfy deployment with bounded storage,
deny-anonymous ACLs, publisher/subscriber identities and actual operator receipt;
independent off-host missed-run/node-loss detection (a node02 dispatcher cannot
detect node02 dying); real monitor restart/persistence/resources; future
lifecycle-job notification producers; attended-reader and remaining
lifecycle/plaintext/mesh work. UI notification status remains explicitly
unconfigured. The credential timer remains untouched, enabled and owns its
runtime token. Monitor remains disabled/stopped and notifier not installed.

### Private ntfy and independent watchdog — inactive candidates prepared

The next direction authorized preparing private deployment/ACLs and an off-host
detector, not publication, provisioning or activation. The private checkout
now has **unreferenced** `flux/private-ntfy` (nine objects) and
`flux/certificate-watchdog` (five identity/grant objects), plus four candidate
contract tests and operations documentation. The ntfy Deployment also has
zero replicas. Private HEAD remains `7e1c6c9e…`; no commit/push, watcher change,
Actions, Flux apply, native credential, DNS/route or workload change occurred.
Unrelated private memory/config files remain untracked and intact.

ntfy v2.38.1 is pinned to registry index
`sha256:038da2be5e668fee6d36a62884eea48975e1b71c29a56964e5298c1b9165a573`
(linux/amd64 child `sha256:6ceb27333175e3ce7d021bb883658858f2b8b883db316a73d0755dfa0b306fc4`).
Only registry/source metadata was fetched; no image/binary was downloaded,
scanned or run. Proposed ntfy placement is node01, independent of node02.
The candidate uses nonroot/read-only/no-capabilities execution, bounded
resources, private-CA HTTPS for proposed `notifications.lan`, Traefik TCP SNI
passthrough with no plaintext leg, no pod egress/external push/relay and one
retained 1 GiB cache claim. Cache/auth startup SQL proposes bounded SQLite
pages; effective page size/storage/runtime enforcement still needs proof.
No new public route, LoadBalancer allocation, mesh enrollment or existing
service rename is included.

Native `private-ntfy-auth` Secret references supply three ordinary users and
distinct publisher/subscriber material; no values are in Git. Fixed grants:
monitor publisher writes only `bortus-certificates`; watchdog publisher writes
only `bortus-monitor-health`; subscriber reads both. Anonymous/other topics/
admin/wildcard access is denied by the prepared contract. Runtime auth is
ephemeral and reconstructed from the external native Secret; cache metadata
persists on its retained claim. Material generation, native Secret creation,
rotation/revocation and actual effective-ACL/subscriber tests remain unrun.
`ntfy_acl_contract.py` only validates input syntax in memory and emits booleans/
counts, not credentials. Pinned upstream code corrected an initial longer
token-length assumption: this version requires `tk_` plus 29 URL-safe characters.
The affected validator/fixtures were corrected and both ACL tests rerun; the
original test log remains, not claimed as upstream authentication evidence.

Node03 read-only preflight found 12,874,715,136 bytes available RAM,
17,674,792,960 free under `/var/lib`, and no watchdog service. It is the proposed
off-node02 witness, not an installed service. The separate identity candidate
can **only get** the exact observations ConfigMap and node02 Lease; no list,
mutation, Secret, TokenRequest, node-proxy or approval grant. It requires its
own externally refreshed short-lived credential, never node02's monitor/admin
credential. Actual identity/allow-deny/refresh acceptance remains open.

`certificate_watchdog.py` and `run-certificate-watchdog.py` prepare an explicit
arming/enrollment path with trusted observation/policy/Lease UIDs. They compare
monitor heartbeat age (180s) and node02 Lease renewal (90s), rejecting >5s future
clock skew; paused mode must still heartbeat. API denial/outage/malformed or
recreated resources mean **coverage unavailable/unknown**, not proof of node
death and not silent resolution of an existing incident. The independent
private state/outbox persists incident and recovery transitions, deduplicates
unchanged incidents across process restarts, bounds delivered history and
preserves pending events under the 16-MiB main DB page cap.

The source-only node03 detector unit is unprivileged/API-VIP-only; its separate
notification unit is deny-all until an exact destination drop-in is reviewed.
The existing sender now has an explicit separate watchdog state/credential
profile and fixed recovery events. No node02 DB/service is touched. A single
node03 witness is not resilience against node03 or whole-cluster failure.

**Verification:** 15 focused watchdog/notification tests passed, including
actual separate-process persistence, unarmed no-state/no-network behavior,
coverage/recovery/threshold/UID semantics, separate sender state and actual
loopback TLS. Two affected ACL cases additionally passed after the version
correction. Four private candidate tests passed. The unchanged full private
validator passed all 30 charts/31 HelmReleases and credential scanning; both
candidate Kustomizations rendered and passed object checks. Reused the existing
checksum-matched H tools without copying them; temporary source output/tool
links were removed. No full-application build or completed broker check repeated.

Both new watchdog units passed local definition verification (only the retained
unrelated Ingenium symlink warning). Node03 Python3.10 parsed the three new
modules before the ACL regex-only correction. Read-only host checks confirm
watchdog units absent, node02 monitor disabled/inactive and accepted credential
timer enabled/active. Source-bound
`ntfy-watchdog-preparation-result.json` binds 14 paths. H test keys/tokens/DBs
were removed; six exact empty temp/cache directories reclaimed 24,576 allocated
bytes. Combined current qualification/publisher stages measured 1,399,656,448
bytes before the small result receipt, under the same 4 GB stage boundary.

**Next gates:** explicit activation/reviewed host and private-release changes;
approved/qualified private endpoint, native auth and separate watchdog credential
refresh; actual ntfy image security/TLS/ACL/storage/restart/resource checks;
live off-host monitor/worker/API-outage/recovery tests and real subscriber
receipt. Attended-reader, lifecycle automation and plaintext/mesh phases remain
open. Preparation is complete in its scope; no monitor/notifier/watchdog/ntfy
activation is authorized or claimed by it.

### Actual pinned ntfy server — isolated TLS and effective ACL acceptance

The next user direction authorized qualification of the real server in an
isolated fixture, with production services inactive. `qualify-private-ntfy.py`
binds the candidate's unchanged server.yml, sender/material helper and its own
source. Registry raw bytes verify the index → amd64 manifest → config chain.
The exact child was acquired once into the existing H-backed daemon; later
correction attempts reused it with pull-never. No build, new dependency tree,
checkout, production credential or real notification recipient was involved.

Two interrupted collector/environment attempts remain:

- `tls-acl` pulled the image, then stopped before server start: this daemon
  exposes the manifest, not config, as image ID. Corrected checks preserve
  exact descriptor and raw manifest/config identity rather than accepting tags.
- `manifest-id` passed that identity check and started the server, but stopped
  before TLS/ACL tests because this daemon does not publish host ports from an
  internal network. A credential-free diagnostic confirmed null host bindings.
  A host loopback byte forwarder corrected access without terminating TLS,
  exposing a LAN listener or relaxing the owned internal network.

The separately recorded **`loopback-proxy`** attempt passed actual ntfy
v2.38.1 under nonroot/read-only/no-capabilities, configured 256 MiB/no-swap,
250m CPU/64-task Docker limits. Those are fixture launch controls, not
production kernel/resource/stress acceptance. The same source config and
ordinary-user Bearer-token ACLs were used; only synthetic TLS/users/tokens and
H-local state were supplied.

- Two publishers successfully published to their own exact topics.
- All **26 forbidden operations** failed: publisher reads, other/unrelated
  topic access, subscriber writes, anonymous and invalid-token operations.
  Observed statuses were **20 HTTP403 and six HTTP401**.
- The authenticated machine poll subscriber received both exact metadata
  messages once. No denied write appeared as a message.
- Trusted hostname TLS 1.2-or-newer passed. Untrusted CA, wrong hostname and
  plaintext access were rejected.
- After isolated stop/recreation with a fresh auth store and the same cache,
  subscriber reads returned the identical server message IDs. No permission
  or storage ceiling was relaxed for the passing run.

This establishes real server/Bearer ACL and **machine subscriber receipt**,
not attended phone/PWA/operator receipt, production private-CA/Traefik/DNS
integration, image vulnerability status, packet-policy/volume enforcement or
live monitor/watchdog availability. The remaining gates are not waived.

All task containers, internal networks and byte forwarders closed. Fourteen
exact synthetic key/token/config/auth/cache targets were admitted and removed:
**643,072 allocated bytes**. The passing and two interrupted attempts' metadata/
sanitized logs remain, together with `ntfy-internal-port-reconciliation.json`,
`ntfy-server-cleanup-result.json`, `ntfy-server-production-inactive.json` and
the hash-bound `ntfy-server-isolated-acceptance.json`.

Retain one exact image reference
`docker.io/binwiederhier/ntfy@sha256:6ceb27333175e3ce7d021bb883658858f2b8b883db316a73d0755dfa0b306fc4`
for its outstanding security qualification before any rollout. Reported image
content size is 36,988,086 bytes, **not physical/unpacked allocation**; a
conservative 1,000,000,000-byte image/runtime reserve stays charged inside the
existing combined 4 GB stage (baseline 1,399,672,832 bytes before this step).
The H source stage measured 1,219,633,152 bytes before its cleanup receipt.
Host H had 382,681,219,072 free bytes and loop0 reported zero errors at admission.
The initial private-runtime stat permission error remains recorded; public
daemon/containerd configuration and Docker API were used without weakening
permissions or claiming inspection of protected runtime content. Global legacy
attribution and physical quota enforcement remain separate/unresolved.

Read-only post-checks confirm node02 monitor disabled/inactive, node03 watchdog
units absent/inactive and no production `bortus-notifications` namespace.
Private candidates remain unreferenced/zero-replica; no commit/push/apply,
credential/timer/host change, new DNS record or certificate lifecycle/mesh
operation occurred. Next: exact-image security and remaining production-like
qualification, explicit live activation authority, subscriber attended receipt,
watchdog credential/real outages, monitor persistence and all later phases.

### Retained ntfy image security — secret scan complete; CVE admission pending

The next direction authorizes exact-image security qualification using existing
approved tools, with production off. The existing worker Trivy0.76.1 executable
was reused directly from its H-backed preservation alias and verified against
approved SHA-256 `d1dfca6ae10a1ad4540bb94e64f0510077c47008920a9b554986b39dca573d83`.
It is not the separately maintained BORTUS `.3` scanner. The immutable
October23 advisory snapshot remains unchanged and is stale; it was **not used**
to claim current CVE acceptance.

The dependency-independent step now passed once:
`scripts/migration/qualify-private-ntfy-secrets.py` saved the retained exact
child to a 36,996,608-byte H archive and verified its original manifest,
config digest and every compressed layer SHA-256/size before scanning.
Expanded layer tar bytes were 8,713,728 + 925,184 + 77,475,840; this measures
content, not protected Docker physical allocation. No image execution, pull,
runtime fixture replay, dependency install or production credential occurred.
The original 1 GB image/runtime reserve stays charged, without reduction.

**Actual scanner exit 0; zero secret findings.** Logs show 105 built-in rules,
OS Alpine3.24.4 and Go-binary inventory targets and image-config secret checking.
This is the scanner's default secret-analysis coverage, not an exhaustive
search of compiled binaries or proof that no possible secret exists.
All severities were enabled and no ignore/status suppression was added.
Three cgroup samples verify 1 GiB memory, zero swap, two CPUs and 64 tasks;
the finished service log reports about 110.2 MiB memory peak.
A real scanner-template conversion using synthetic sentinels proved the
metadata-only report excludes image Env, secret Match and Code while retaining
finding metadata. The report does not serialize complete image configuration.

The log also records **anonymous telemetry sent** despite skip-version-check.
Do not call this run network-isolated. The source now explicitly adds
`--disable-telemetry` for any future authorized invocation; it is a post-run
driver correction, not a repeated scan or retrospective change to evidence.
The executed source hash is `e152a33a…`; retain it separately from the corrected
current driver hash. No credentials or production data were supplied to Trivy.

Fresh public DB manifest bytes were pinned/verified as
`sha256:b046135279316e1119730eacf73cb3d1ff1ca86bbedbb96ddd133ef11684ca8e`,
created 2026-11-16T13:13:16Z. Layer
`sha256:25ad50ee557465816b386a58125db6d5f8294ab3c5da334983e8d97dbdba473b`
is 140,815,146 compressed bytes. The earlier 10,240-byte header-only probe
reported 1,773,903,872 logical DB bytes. No full layer/database was downloaded,
extracted or cryptographically accepted as complete. A future streamed
download must hash the **entire** layer, validate exact tar members and DB/
metadata bytes/freshness before running the unfiltered vulnerability scan.

Eligible cleanup is complete: six exact scanner-cache/temp/synthetic and prior
node-compile-cache targets removed **16,052,224 allocated bytes**. No active
qualification/container consumer remained; other-UID `/proc` visibility gaps
are explicitly retained, not claimed as full process visibility. Current app
dependencies/build and publisher checkpoint inputs remain needed. The exact
image and verified export remain consumers for the pending CVE step; do not
rerun the passing secret/TLS/ACL checks or export again.

After cleanup, conservative stage accounting was **1,420,963,840 retained +
1,000,000,000 carried image/runtime reserve + 1,773,903,872 fresh DB =
4,194,867,712 bytes**, already **194,867,712 over** the authorized 4 GB ceiling
before further small receipts. This deliberately retains the entire reserve
even though retained bytes also include the export. It is not a precise
physical-root allocation claim. Current app dependencies/build, current
publisher input and immutable snapshots are not eligible deletion targets.
**Fresh-DB admission is not granted.** A proposed one-stage ceiling of
4,250,000,000 bytes, with streaming/no retained compressed layer and the same
1 GB reserve, requires James's explicit exception; it has not been applied.
No global quota increase, new root, checkout, mount or tool/dependency copy is
implied. Preserve the existing stage and wait for that genuine budget decision.

Evidence remains under `ntfy-security-secrets/`: `result.json`,
`image-input.json`, `resources.json`, `redaction-result.json`, metadata-only
`results.json`, scanner/export logs, `fresh-db-manifest.json`,
`fresh-db-admission.json`, cleanup receipts and `production-off.json`.
Read-only checks confirm monitor disabled/inactive, node03 watchdogs absent,
production ntfy namespace absent, and the accepted credential timer still
enabled/active. Root Git index is preserved. Overall image-security/CVE and all
live monitor/watchdog/notification/reader/lifecycle/plaintext/mesh gates remain
open; zero secret findings is not deployment approval.

James then explicitly selected **Approve 4.25 GB stage**. The existing
qualification stage alone may now peak at 4,250,000,000 bytes, keeping the full
1 GB image/runtime reserve and existing production boundaries. This is not a
global allowance change. `ntfy-security-vuln-approval.json` records authority.
The former not-admitted calculation remains historical; next is the full
pinned-layer streamed download/integrity/freshness verification and unfiltered
exact-export vulnerability scan. Neither has yet run at this checkpoint.

The first DB phase then exceeded the foreground tool's120s limit with both
expected-size pending files retained, but no completed integrity receipt.
It remains interrupted/unaccepted. A distinct background `verify-database`
phase now compares the SAME files byte-for-byte against the complete pinned
layer, with full compressed/member hashing and freshness checks, before
publishing them. No duplicate DB or retained compressed carrier is written.
Its completion is pending; do not replay either started phase or scan before
`database-result.json` proves successful verification.

Recovery then passed in17.82s without a second DB copy: all140,815,146
compressed bytes match layer25ad50ee…, and both pending files matched the
full original tar members byte-for-byte. DB SHA-256 is
`e7587cc3528c2d401dfae2bb327d6d7e2943cb04d714ae7d413c6dbe64a38db3`;
metadata SHA-256 is
`5d20f2276ed7dbaa4c68fa1af8f53c8fed669a9981cef77628b591ad51e2881e`.
UpdatedAt2026-11-16T13:03:44.830426244Z and NextUpdate2026-11-17T13:03:44.830426014Z
passed freshness checks. The verified directory is now published under the
same attempt's `cache/db`; retained qualification/publisher usage was
3,194,920,960 bytes. Original timeout remains historical.
The distinct vulnerability scan is now running against the existing export
with no image execution/pull/export or completed-check replay. Await its
automatic completion and result; no clean-security result is claimed yet.

### Exact pinned ntfy vulnerability assessment — complete, candidate on HOLD

The fresh, unfiltered exact-export scan completed with scanner exit0:
**one MEDIUM finding, zero HIGH/CRITICAL scanner findings**. Coverage is
17 Alpine3.24.4 packages and86 Go packages (including Go stdlib1.27.4).
Go package findings are zero. The prior independent secret scan stays zero;
it was not rerun. The complete raw Results-only report and compact findings
remain, with no ignore, severity/status, unfixed or VEX suppression.

The finding is **CVE-2026-4738**, installed `zlib 1.3.2-r1`, vendor-fixed
`1.4-r0`. The official Alpine v3.24 secdb confirms that mapping. The primary
CNA record describes GDAL's bundled `frmts/zlib/contrib/infback9/inftree9.c`
before GDAL3.11.0, with a Critical9.4 score for that affected GDAL code.
This is a severity/applicability distinction, not permission to dismiss the
finding or silently reassign a score to ntfy. The Alpine HTML page failed500;
the official JSON secdb, primary CVE API and merged GDAL patch record were read.

Read-only inspection of the SAME exact archive confirms zlib1.3.2-r1 and its
shared library are installed, no GDAL/infback9-named payloads appear, and ntfy's
ELF has no dynamic section. No image was executed or persistently extracted.
These observations reduce the obvious dynamic-library path but do **not**
independently prove absence of every statically incorporated vulnerable path.
**Disposition: HOLD.** No false-positive exemption, accepted residual risk,
zero-vulnerability claim, suppression or deployment approval was made.
The next dependency-ready action is a candidate with vendor-fixed zlib1.4-r0
or later (or materially stronger code-not-present evidence), followed by its
own exact-image qualification. Do not change the private pin merely to hide
the recorded finding, and do not infer publication/production authority.

The scanner's log confirms **version checks and telemetry disabled**; no
second anonymous telemetry call was made by this vulnerability execution.
The `--list-all-pkgs` warning only says template output already contains all
packages; both package inventories are present. Its sole kernel sample matches
1 GiB/no-swap/two CPUs/64 tasks with no OOM counters; the finished service log
reports117.2MiB peak. The observed allocated qualification/publisher peak was
3,195,072,512 bytes. With the conservative500MB retained-image allowance,
charged observed peak was3,695,072,512; the complete original1GB-reserved plan
was4,194,884,096, within James's4.25GB stage exception. These are sampled stage
and conservative reservation figures, not protected-Docker physical accounting.
DB/member hashes and source/index remained unchanged after the scan.

Evidence under `ntfy-security-vuln/`: `database-{started,interrupted,result}.json`,
`database-verification-started.json`, original public `db-manifest.json`,
`scan-started.json`, `results.json`, `findings.json`, `resources.json`,
`scanner.stderr`, `component-review.json`, `advisory-review.json`,
`production-off.json`, cleanup records and final `security-assessment.json`.
The original timeout is not rewritten as an uninterrupted successful download.
No tool/dependency copy, new checkout, secret/TLS/ACL/browser replay, image pull/
export/execution or private push/apply occurred during vulnerability scanning.

Required local scan/assessment consumers have now ended. Five admitted DB/
analysis/temp/export targets were removed, reclaiming **1,811,103,744 allocated
file bytes**. The exact task-acquired local ntfy image reference was removed
normally without force/prune; Docker confirmed it deleted and subsequent
inspection confirms absence. Runtime physical reclamation is unmeasured.
The full1GB runtime-reserve consumer has ended; do not report1GB as measured
freed disk. Current stage retained1,204,023,296 bytes and publisher180,113,408
before the small cleanup receipt. Old immutable DB/scanner, app dependencies/
build, source/lock/index, all unique reports/logs/provenance and interrupted
evidence remain. A preliminary retirement check stopped on an unexpected
RepoTags representation; it was the identical owned digest string, not an
additional alias. That failed check and exact-identity correction are preserved.

Read-only proof confirms monitor disabled/inactive, node03 watchdog units
absent, ntfy namespace absent and accepted credential timer enabled/active.
Private HEAD remains7e1c6c9e…; the candidate is still unreferenced/zero-replica.
**This completes assessment of the old digest, not security approval or the
full goal.** Prepare the fixed candidate next; live monitor persistence,
independent watchdog/notification receipt, attended reader, lifecycle automation
and plaintext/mesh phases all remain active/unaccepted.

### Vendor-fixed ntfy candidate — active local qualification

James's next direction explicitly authorizes preparing/qualifying fixed zlib
1.4-r0 or later, keeping production inactive. Upstream latest2.38.1 still has
the held digest. New source under `images/private-ntfy-zlib/` pins that base
and the vendor-signed Alpine3.24 x86_64 package1.4-r0 (56,761 bytes, SHA-256
7b05bc778b8b25cd880835b40114182bd4d1581717504d0129c810c0a14291cb).
The package is fetched once to the existing stage's `ntfy-zlib-fixed/`.
Current retained baseline1,384,148,992 plus fresh DB, full1GB reserve and50MB
export/report margin admits4,208,052,864 under the same approved4.25GB cap.
No new root/checkout, dependency copy or global budget increase.

The source Dockerfile documents an offline package-only derivative and
nonroot1000:1000 default. The shared BuildKit driver lacks per-build CPU/memory
flags, so the actual local candidate uses a two-CPU/1GiB/no-swap/64-task install
container plus commit, without a new builder/tool. APK signature checks use
the base's vendor keys; no untrusted flag, production mount or credential.
The base is reacquired only as a required NEW fixed-candidate input; old-digest
scans/fixtures are not replayed and their HOLD remains literal.

First install succeeded but its CLI-format check was wrong: `apk info -v`
prints description/URL/size, not version. Its removed writable layer/loss and
failure log remain. The separate `apk-db-check` install succeeded with empty
repositories and no lookup warnings, but finished before the kernel sampler
captured a live process. That observer remains failed; its stopped install
layer is retained, not reinstalled.

The first retained-layer finalizer stopped before commit because the APK DB
path is `scripts.tar.gz`, not the assumed `scripts.tar`. Its failure/delta
remain. The named `apk-db-path` continuation now checks every APK hook payload/
mode/owner against the base, package-only delta and unchanged ntfy executable,
then uses a separate read-only candidate audit with an explicit stdin barrier
to capture actual kernel limits/nonroot default. This is not a retroactive
install sample. Reconcile its existing automatic completion and records before
resuming; no candidate build/security/runtime pass is yet claimed here.

The existing runtime/security drivers accept only the exact owned verified
build record for a NEW subject and use separate attempts/directories. They
cannot pull a missing local candidate. Candidate security is combined unfiltered
vulnerability/secret scanning with safe metadata-only secret output and fixed
zlib inventory checks; candidate TLS/ACL/cache checks use the image's own
nonroot default. Private image pin, HEAD, release composition and production
remain unchanged. All later monitor/watchdog/attended/lifecycle/network gates
remain active.

### Vendor-fixed ntfy — locally qualified, not published or activated

New candidate manifest:
`sha256:e26ace78ff6edc73a78e68ef96d8282b4ac80415623671dcee5c9edd764a525e`;
config:`sha256:c7054886cc52c7bd54bb1bb4d41d31b0c4c6648228fc28f9d160b1bd4662316b`.
Vendor-signed Alpine zlib1.4-r0 is the only changed package version.
ntfy2.38.1's executable is unchanged (SHA-256
`2c09c500b0fc624c0294f613640c9b1d3800f1d6957014176e8d1e0659b70265`).
All APK hook contents/modes/owners match the base; only zlib and normal package
state/log paths changed. Default runtime user1000:1000 was actually exercised.

**New-image security passed:** current pinned DB/approved scanner,
17 Alpine/86 Go packages, **zero reported vulnerabilities and zero secrets**.
Fixed zlib is inventoried; no suppression, VEX waiver or risk acceptance.
The real template-conversion sentinel check preserves finding/package metadata
while omitting image Env and secret Match/Code. Telemetry/version checks are
disabled. This is snapshot qualification, not a claim about unknown future CVEs.

**New-image real-server fixture passed:** unchanged server.yml, internal network,
loopback byte forwarding and end-to-end synthetic CA/hostname-verified TLS.
Bad CA/hostname/plaintext rejected; two intended topic publish/receipts and
all26 denials (20x403/six401) passed. Fresh auth-state recreation preserves
identical cached message IDs. This is machine receipt, **not attended phone/
PWA receipt**, production CA/Traefik/DNS/policy/storage or live runner proof.

The earlier collector failures remain literal: APK-info format, missed fast
installer sample, scripts.tar.gz path, omitted Cmd after commit and initial
runtime hash-helper creation timeout. Passed installed/committed state was
reused; no reinstallation/recommit for finalizer corrections. The timed-out
helper was proven never started and removed exactly; named bounded helper
create/start fixed that fresh fixture. All task containers/networks/proxies/
helpers have ended. No old-digest checks were replayed.

The fast install has configured2CPU/1GiB/no-swap/64-task evidence, **not a live
sample**. Separate deterministic read-only candidate kernel/default-user audit
passed; it is not retrospective install sampling. Scanner also sampled actual
matching limits. Full reserved plan4,195,260,928 and charged sampled peak
3,695,736,064 stayed within approved4.25GB with the full1GB reserve.
No protected-runtime physical allocation or stress qualification is claimed.

`ntfy-zlib-fixed/fixed-candidate-acceptance.json` binds complete results.
Retain the unique local image and37,076,480-byte export (SHA-256
`f2e9d0893435b9e45f6f9f992b4fde3bf7415204da2b2f5590f83d45a1a910a5`)
for **immutable private-delivery handoff and remaining production-like
route/policy/storage qualification**. Retire after verified publication/
consumer transfer or explicit rejection. The source Dockerfile is an offline
recipe; actual production of this artifact was bounded install/commit, not a
BuildKit run or claim of bit-for-bit image regeneration.

Cleanup removed18 exact DB/analysis/temp/synthetic targets:
**1,774,649,344 allocated file bytes**. Original base reference retired normally;
candidate/shared required layers and export hash remain verified. Physical
image reclamation is unmeasured. Stage retained1,241,448,448 plus publisher
180,113,408 before small receipt. Vendor package, source/index, app build/
dependencies, old immutable inputs and all unique failure/pass evidence remain.

Private pin remains the original held digest, unreferenced/zero-replica; this
local derivative has no authorized published registry reference. No private
push/apply, image publication, host/credential/DNS change or activation occurred.
Read-only proof: monitor disabled/inactive, watchdog absent, ntfy namespace
absent, accepted credential timer active; root index/private HEAD preserved.
**Requested local fixed-candidate qualification is complete, not full delivery.**
Next: authorized immutable delivery/registry verification and production-like
CA/route/policy/storage/resources, then explicit activation. Monitor persistence,
watchdog identity/refresh/outages, attended subscriber/reader, lifecycle and
plaintext/mesh gates stay active. Do not replay completed candidate checks.

### Production-like ntfy integration — preparation verified, execution not approved

James next requested preparation of TLS/route, policy, storage and resource
qualification for the **retained fixed digest**, keeping production inactive.
No new candidate build/export, image/DB pull, dependency tree or direct-image
security/ACL fixture replay was needed.

The completed metadata-only preflight used ten fixed GET endpoints (no Secret
read, exec, dry-run POST or mutation). It found Traefik2.11.60 with file and
Kubernetes-Ingress providers but **no TCP CRD or Kubernetes-CRD provider**.
The previously inactive IngressRouteTCP would not work. Source now replaces
only that object with public `traefik/private-ntfy-tcp-route` ConfigMap,
key `bortus-private-ntfy-tcp.yaml`: exact HostSNI `notifications.lan`,
file-provider TLS passthrough to the existing proposed HTTPS Service.
The ConfigMap is **not mounted live**; active edge deployment/composition/RBAC
is unchanged. Qualified server.yml SHA-256 remains
`dca96ae9b0bf87c0b0dfb7ee0fe9e32179a8eb17c32c7346364a5ddbe8352898`;
the unreferenced/zero-replica private candidate still pins the held original
upstream digest, not an unpublished local reference.

Private `qualification/private-ntfy/{contract.json,edge-volume-proposal.json,README.md}`
defines an inactive, bounded qualification profile and runbook, **not resources
or an apply/patch path**. Registry reference is null; execution/publication
approvals false; edge/workload replicas zero. Isolated namespaces, `.invalid`
synthetic hostname/trust and a new retained1Gi Longhorn claim cannot adopt
production objects/data. Native dashboard Secret/items/modes and read-only
directory mount must survive any later projected-volume change. That proposal
requires private key-name/router/service-identifier collision review, fresh
UID/resourceVersion and exact-volume/mount tests plus separate rollout approval.
No native Secret was inspected or changed during preparation.

Pinned ntfy source loads serving TLS at startup. The runbook separates
**issued, projected, restarted and endpoint-fingerprint-verified** states; a
reviewed exact-identity/revision-guarded restart controller is proposed, **not
implemented/installed**. It bounds real route trust/plaintext checks, ordinary
pod versus host/kubelet/ambient paths, DNS/egress controls, actual two healthy
encrypted Longhorn replicas, DB cap/refusal and retained-ID recreation,
actual kernel/mount/resource observations and machine receipt. It neither
enrolls mesh namespaces nor authorizes node reboot/drain or attended receipt.
PVC/Secret/namespace cleanup is not automatic; retained data has a separate
reviewed retirement condition.

Preflight observations: Traefik2/2Ready; CA issuer Ready; Calico3/3Ready.
Longhorn class encrypted/two-replica/ext4/Retain/Immediate/no fromBackup.
Node01 allocatable8CPU/16,165,220Ki, Ready/no pressure/taints; conservative
declared requests3825m/3,655,335,936 bytes, **not usage or scheduler-fit proof**.
Reported Longhorn disk available29,884,416,000 bytes is not replica-placement/
quota/persistence acceptance. Original preflight bytes/source hashes remain;
its unsupported-route blocker describes the pre-correction source. The
collector now treats missing CRD support as capability metadata, not a
dependency of the replacement file route; mount/registry/live gates stay shut.
Only affected synthetic tests were repeated after that small source correction.

Verification passed: **seven public-projection/preflight tests and seven
private candidate/approval/mount/server-byte tests**. Actual Kustomize renders
and existing object checks passed for ntfy(nine objects) and watchdog(five).
The unchanged full private validator passed30 charts,31 HelmReleases,108
composed resources, effective rendering and credential scan. Checksum-verified
tools were reused from the retained publisher, not installed/copied. Temporary
private routing links were removed. The finished empty H validator-temp
directory was removed (4,096 allocated bytes); logs, hashes and small results
remain under `ntfy-integration-preparation/`, bound by `preparation-result.json`.
Combined retained stage/publisher measured1,421,742,080 bytes before the small
cleanup receipt; carried1GB image/runtime reserve plus10MB preparation peak
remained within the existing4.25GB exception. No global attribution/quota claim.

Read-only closing checks: monitor disabled/inactive, node03 watchdogs absent,
ntfy namespace absent, accepted credential timer enabled/active and untouched.
Retained fixed image/export verify; root index/private HEAD7e1c6c9e… preserved,
no active release/Actions change, commit/push, registry publication or apply.
**Preparation is complete; live integration/full delivery are not.**
Next requires separate immutable private-delivery/registry verification
authority and fixture execution/material approval. Native edge collision
audit/mount rollout and real rotation/policy/storage/resources remain unrun.
Keep monitor persistence, watchdog identity/refresh/outages, attended subscriber/
reader, certificate lifecycle and remaining plaintext/mesh work active.

### Delivery execution resumed — 2026-11-16

James's explicit delivery clarification above supersedes repeated
preparation-only approval holds; do not ask him to reconfirm settled steps.
Technical/preservation/acceptance gates remain unchanged.

Private transport PASSED for unchanged fixed digeste26ace78…:
`docker.io/jtmb92/bortus:ntfy-2.38.1-zlib-1.4-r0-e26ace78ff6e`.
Repository privacy, remote manifest/config and all four full layer bytes
verified. Existing release tags unchanged; no rebuild/export, persisted
credentials or production deployment. Temporary helper client removed.
The same unique export then passed sealed-memory node01/node02 preload:
all stored blob bytes and downloaded/unpacked state, no node disk carrier
or registry credentials in pods. Results are in
`ntfy-zlib-fixed/{publication-result,preload-node01,preload-node02,preload-result}.json`.

Node01 needed Longhorn scheduling margin at the unchanged25% floor.
Six eligible closed system journals (>72h, stable/root-owned/no open FDs)
were encrypted on H and recovered/compared before exact retirement:
536,895,488 allocated bytes removed;89,137,747 encrypted bytes retained in
`ntfy-node01-journal-preservation/`. No active log, plaintext carrier,
rotation/retention setting, workload stop, volume or threshold changed.
Peak admitted650MB plus the carried1GB reserve within4.25GB.

Actual isolated cluster staging PASSED using three owned namespaces,
synthetic native auth and real cert-manager synthetic CA/leaf, published
preloaded image, file-provider edge and four source-control Pods. The new
retained1Gi PVCUIDfe0dad4e… binds PVUID96123b20…/LonghornUID8632b30f…,
encrypted and healthy/two replicas. No production data/keys/claims/route.
The first stage rejected unsupported activeDeadlineSeconds in ReplicaSet
templates before workload creation. It remains failed; completed creates/
credentials/PKI/claim/config were reused by exact UID. Corrected diagnostics
are standalone Pods with native<=900s deadlines, not production edits or
weakened bounds. Three fixture boundary tests passed.

`ntfy-cluster-qualification/stage-result.json` is terminal successful.
The active `qualify-ntfy-cluster-path.py` follows that same fixture for routed
trust/fingerprint/HTTP controls, ordinary/ambient/host policy distinctions,
DNS/LAN egress, actual cgroups and cert-manager reissue/projection followed by
guarded Pod recreation/served fingerprint/cache ID on the same PVC.
Reconcile its automatic completion before continuing. No unattended rotation
controller, complete DB-cap/load, attended or production acceptance is claimed.

### Completed isolated integration and guarded rotation implementation

The path check then PASSED: real routed leaf/trust/plaintext rejection and
unrelated HTTP301 before/after; selected edge source connects cross-node to
Service+pod endpoints while unselected, ordinary same-namespace and denied
sources fail (eight observed paths). DNS UDP/TCP and owned LAN-node TCP egress
fail with contemporaneous positive controls; no unsolicited public scan.
Ambient-labelled ingress-mode edge traffic succeeded; host/kubelet probe
exception is documented separately, not original-client authentication.

Real cert-manager revision2 issued a new synthetic leaf. Projection changed
while ntfy still served the old fingerprint, then UID/resourceVersion-guarded
owned Pod recreation served the new fingerprint. Same PVCUID/cache message ID
survived, auth tmpfs recreated. Both actual Longhorn replica UIDs run on
node01/node02 and the encrypted retained volume remains healthy. This is
real renewal-path/restart evidence, not installed unattended-controller proof.

Bounded20 publishes/three poll subscribers PASSED with zero errors, observed
p50~66.73ms/p95~76.97ms (not stress/soak/capacity acceptance).
Synthetic DB snapshots passed integrity/page-count checks and independent
memory-only copies refused writes at16384/1024 pages, total generated payload
under80MiB. This **does not query ntfy's connection-local max_page_count** or
turn PRAGMA targets into filesystem quotas. Hard claim/tmpfs/memory bounds
remain separate. Actual UID1000, no capabilities, NoNewPrivs/seccomp2,
read-only root,256MiB/no swap/250m and bounded tmpfs were observed, no OOM.
Kubelet PID ceiling18847 is not the Docker64 cap; memory.peak is not exposed.
The initial peak-field collector failure remains; only missing observations
were completed, with no repeat messages/cap fills.

All six exact diagnostic Pods were removed with UID/resourceVersion
preconditions; forwards closed. Local synthetic client token/empty temp removed
(8,192 allocated bytes), plus the new finished empty validator temp4,096 bytes.
Retain fixture PKI/native auth/config/claim for the next scoped controller live
qualification, then review exact retirement; no blanket namespace/PVC deletion.
Private source pin now uses published fixed digeste26ace78…, still
unreferenced/zero-replica. Seven updated private tests, rendered nine objects
and the full30-chart/31-HelmRelease/108-object validator/credential scan passed.
The old preparation tests/results remain historical. No private commit/push,
active composition change or production activation was performed.

After an OpenCode server restart, all terminal records were reconciled:
no active driver/local client token; same boot/store/index, no completed
publication/preload/cluster check replay. Then implemented
`automation/certificate-rotation/{policy,controller}.mjs`: fail-closed pinned
Certificate/Secret/Deployment/consumer/image identity, current signed public
CertificateRequest+revision, private-CA/SAN/time validation, projected leaf,
trusted actual endpoint, observation mode, single-writer Recreate and fresh
CAS. It re-collects before one annotation patch and reconciles ambiguous
responses without duplicate rollout. Full Secret payload fallback is rejected;
only public mounted certificates and metadata are used, never native keys.
Eight policy tests and seven current adapter tests passed, using real fresh
synthetic signatures. Ephemeral H keys were removed. No new dependencies.

**Next dependency-ready action:** package and qualify the narrow live
identity/Job or scheduled executor for this controller against the retained
fixture, starting in observation mode. Actual transport/RBAC, controller-driven
reissue/restart, job interruption and installed unattended availability remain
unrun; unit tests cannot close them. Do not repeat completed cluster checks.
Continue without approval prompts through existing private validation/Flux,
monitor persistence, watchdog identity/refresh/outages, attended subscriber/
reader, certificate lifecycle, retirement and plaintext/mesh phases.
Full delivery is still active, not complete.

Closing boundary record: zero diagnostic Pods; production ntfy namespace
absent; monitor disabled/inactive; watchdogs absent; accepted credential timer
enabled/active, untouched. Root index/private HEAD7e1c6c9e… preserved.
Retained stage/publisher1,511,256,064 plus full carried1GB reserve remain within
4.25GB before small closing receipts. Evidence:
`ntfy-cluster-qualification/{path-result,state-result,cleanup-result,source-validation-result,closing-boundary-result}.json`
and rotation policy/adapter test results; the encrypted node01 history remains.
Read-only live cert-manager inspection then corrected request lookup before
controller execution: certificate-name is an annotation, not a label. The
adapter GETs the exact current `<certificate>-<revision>` request and verifies
annotation/owner/revision, eliminating LIST permission. The affected seven
adapter tests passed again on this source; eight unchanged policy tests were
not rerun. Use `rotation-controller-request-binding-result.json`, not the
earlier consumer-pins source hash, for the current adapter binding. No live
controller Job or completed cluster test was repeated.

### Rotation controller — live qualification passed; production inactive

Retained fixture/current source hashes and H budget reconciled; no completed
publication, preload, image, direct or prior cluster-path checks replayed.
New namespace-only identity `ntfy-rotation-qualification` UID494d15ff… is
qualified by a real projected600s API-audience token. Authenticated subject/
UID and enrolled Certificate/leaf Secret-metadata GET passed. Eight actual
403 denials passed: Secret LIST, CA-key Secret GET, Pod LIST, public request
LIST, unrelated Deployment PATCH, token minting, CSR LIST and other namespace.
The role permits exact `private-ntfy` Deployment get/patch, exact leaf Secret/
Certificate get and public CertificateRequest get-only in the fixture namespace.
Secret GET is not restricted to metadata by RBAC; only the implementation
rejects a full Secret response. No claim of CA-key/blanket approval privileges.
Job/deadline/token/public-mount/schedule boundary tests passed three cases.

Evidence is under `ntfy-controller-qualification/identity-result.json`.
The real observation phase created an owned Recreate diagnostic
Deployment and bounded edge reuse the existing synthetic PKI/auth/config and
retained claim. The controller source/actual UID/CA/image enrollment is
projected read-only, starting in observe mode. It uses the already cached
qualified BORTUS Node image, no new dependency/tool/image. No production route/
controller/service activation occurred.

Subsequent exclusive phases qualify observation without mutation on a new
issued/projected leaf, one guarded controller rollout and trusted endpoint,
then a real post-acknowledged-patch/pre-completion interruption wrapper using
the same transport/runOnce. Actual Job suspension stops that worker; recovery
must not increase Deployment generation again. This is not a claimed lost-
TCP-response test. Two native CronJob-owned scheduled executions (not manual
Jobs) must follow; Forbid overlap/60s deadline/30s catchup/bounded history and
explicit qualification suspension/owned cleanup remain required.

Guarded renewal has now PASSED (`renewal-result.json`): observe mode did not
mutate the Deployment or Pod, then auto mode issued exactly one CAS rollout
(Deployment generation1→2). Revision3 fingerprint
`1bdb2ef5b2c0c7704afbd4baa7b4e13a5e4a84ae945453248b41a4f5bb4decd8`
was verified at the actual trusted endpoint after Pod replacement. The first
helper-arity failure was before any renewal request; its unchanged-state
receipt is retained. The corrected resume did not replay identity or initial
observation. Interruption qualification is active against the same fixture;
native scheduled execution and owned teardown are not yet accepted.
Interruption then PASSED (`interruption-result.json`): the real worker was
stopped after the acknowledged PATCH and before wrapper completion. Recovery
observed the durable annotation and actual trusted endpoint; generation
remained3 with no duplicate rollout. The barrier is not a claimed lost-TCP-
response test. Two native CronJob-owned executions are now being observed;
the scheduler must be suspended and exact owned diagnostics removed afterward.
Native scheduling now PASSED (`schedule-result.json`): two successful Jobs
owned by CronJobUID98b15c0b… ran at21:39 and21:40 UTC and verified revision4's
fingerprint080f9bf5… with patch:null. No manual start counted; the native cluster
scheduler does not depend on Windows/WSL to execute. Suspension and exact
UID/resourceVersion cleanup both PASSED. Sixteen new owned objects were
explicitly removed; the two recorded scheduled Jobs were already absent after
foreground CronJob deletion. Zero diagnostic Pods remain. Temporary role,
binding, identity, scheduler and controller source/policy were removed;
pre-existing fixture PKI/native auth/config/claim/namespaces remain outside
this cleanup's scope. No server-side immediate token-revocation claim.
This closes fixture rotation qualification, not production enrollment,
host-runner reboot survival, human receipt or the full follow-up.

`ntfy-controller-qualification/live-qualification-acceptance.json` binds the
executed source, seven phase/cleanup receipts and closing boundaries. Current
read-back confirms no temporary controller grants/scheduler or diagnostic Pods,
production ntfy absent, monitor disabled/inactive, watchdogs absent and accepted
credential timer active/enabled and untouched. Root index and private
HEAD7e1c6c9e…/release composition remain unchanged. Retained stage/publisher
1,511,534,592 bytes plus the full1GB reserve are within4.25GB before the small
acceptance receipt.

The synthetic PVC/PKI/auth/config were deliberately not part of controller
teardown. The exact original claim/volume UIDs remain; after the last Pod
exited, Longhorn reports detached/robustness unknown, not a new attached-health
pass. Their controller consumer has ended: next perform the separate exact
fixture retirement review (references, ownership/cascade, snapshot/volume
identity and synthetic-only data) rather than silently carrying a new runtime
consumer or blanket-deleting namespaces/claims. Retain unique evidence and
encrypted historical journals. Then package/enroll the production controller
through the private validation/Flux path with real native trust/credentials and
guarded Traefik volume preservation. No new approval prompt is needed for
settled execution; technical acceptance still applies.

### Exact fixture retirement and production rotation staging

The separate retirement review found no fixture workload/endpoints, volume
attachments, snapshots/backups or remaining consumer, and matched all original
resource/claim/PV/Longhorn UIDs. Synthetic CA/leaf Secrets had no cascading
owners. Fifteen exact synthetic objects, including retained PVC/PV/Longhorn
volume, were retired with fresh UID/resourceVersion preconditions. Normal
controllers completed finalization; both replicas and generated public requests
are absent. No forced finalizers, production-data deletion, namespace sweep or
physical reclaimed-byte claim. Three original namespace objects with only
injected trust/default metadata remain. Unique evidence/encrypted journals
survive. `ntfy-fixture-retirement/{review,intent,result}.json` binds this.

Production rotation is now packaged in the existing private checkout:
byte-identical qualified controller/policy only, hash-suffixed source ConfigMap,
separate IfNotPresent observe enrollment with deliberately empty UID/CA/endpoint,
namespace-only exact-consumer grants, public-only mounts,600s projected token,
100m/128Mi/60s Job cap and a suspended five-minute CronJob. The unchanged
transport targets Kubernetes-CA-verified192.168.0.4:6443, the existing
control-plane address, not the API VIP. No diagnostic wrapper is packaged.
Two new release children stage zero-replica ntfy/real private-CA leaf/retained
claim first, then suspended rotation. No native ntfy auth, live edge mount,
serving Pod, populated enrollment or automatic rollout is enabled by staging.

Local source checks are running before scoped commit/push. The nine
certificate/watchdog/rotation contracts join the existing35; publisher and
publication-verifier gates both require44. All prior validation/credential/
exact-source/atomic-publication checks remain. The publisher reuses existing
H tool inodes by checksum-verified hard links instead of copying another
tool/dependency tree. Existing singleton watcher/process is reused, not restarted;
all new qualification/publication output stays under the admitted H roots.
Local checks PASSED44 source tests, full validator (30 charts,31 HelmReleases,
110 parent resources, credential scan), and9/7/5-object ntfy/rotation/inert-
watchdog renders. Hash-suffixed source references resolve and packaged JS is
byte-identical to live qualification. Nineteen owned paths were committed/pushed
privately as `fcdabd2107ad0ed7709d646d81f7d1259959ff50`; unrelated private memory/
config files and root Git index were preserved. Actions was verified disabled.
The existing singleton watcher owns exact-source revalidation/promotion; a
read-only observer is waiting for its terminal receipt and normal Flux
reconciliation. Do not rerun the publisher, restart the watcher or manually
apply staged manifests.

A separate native edge audit PASSED: existing dashboard Secret file keys and
parsed router/service identifiers do not collide with the public TCP route.
Only UID/resourceVersion/public volume/mount references were saved; no native
values. Live Traefik still mounts the original Secret unchanged. Any later
mount integration must recheck the fresh object/Secret revision and exact
original volume/mount before publication, preserve the full native projection,
then verify unrelated endpoints. The audit itself dispatched no rollout.

Ended local ntfy image refs were retired normally after verified private
delivery and node transfer; registry/node images remain. The37,076,992-allocated-
byte unique export is retained on an explicit incomplete process-FD visibility
safety check, not deleted or retried through another route. Physical image/
cluster reclamation remains unmeasured.

Production staging is now terminal PASSED. The singleton revalidated44 tests,
advanced `main`/`validated`/immutable tag to exactfcdabd21…, and Flux parent/
both children are Ready on that revision. The new namespace has a Ready real
private-CA Certificate, a retained claim, zero ntfy replicas/Pods and suspended
rotation with unchanged empty observe enrollment. Generated source ConfigMap
matches the qualified JS bytes. Existing H tool inodes are shared by both
publisher exports, not copied. No Actions, watcher restart or manual apply.

The actual production ServiceAccount subsequently passed a fresh projected-token
identity/UID check, enrolled Certificate/leaf-metadata/Deployment/public-request
GETs, exact Deployment metadata-only PATCH server dry run, and eight actual403
denials including the real CA-key Secret. Generation1/replicas0 remained
unchanged. Two exact diagnostic objects/Pods were removed; no token values
persisted or immediate server-revocation claim. Evidence:
`ntfy-production-staging/{staged-flux-result,production-identity-result,production-identity-cleanup}.json`.
This is staged identity/package acceptance, **not** verified serving renewal.

Next dependency-ready step: provision native ntfy auth and the independent
publisher/subscriber delivery path; integrate the public TCP file through the
preserved native Traefik projection using fresh UID/RV/original-field guards;
bring up the one ntfy writer through validated Flux; verify actual private-CA
route, identities and retained state. Only then populate the enrolled UID/CA/
endpoint ConfigMap under CAS, observe the actual endpoint and enable scheduled
rotation through source. DNS/attended receipt and all monitor/watchdog/
lifecycle/retirement/plaintext/mesh gates remain open. Do not rerun passed
fixture/image/security/transport or staging publication checks.

### Native authentication and serving activation — active

Reconciled the staged resource UIDs/zero replicas/suspended schedule and H peak.
Native `private-ntfy-auth` UID29ce9801… was created once with three ordinary
identities, server users/tokens and distinct monitor/watchdog/subscriber token
keys. Values remained in memory/native Secret only; unhashed passwords were
discarded. No client/human delivery or effective ACL acceptance is implied yet.

Public-chain inspection caught a staging defect before serving: the root
permits branconet.lan/branconet.local, not the draft notifications.lan.
The new endpoint is corrected to notifications.branconet.lan without renaming
an existing service, changing issuer or weakening trust. Only server.yml's
base-url changes; its remaining bytes match the qualified configuration.
This new-name/actual-route boundary needs live verification, not a replayed
image/build/security fixture.

Source now proposes one writer, selected-Traefik-only ingress and the preserved
full native dashboard Secret projected alongside one optional public TCP file,
explicit0644/read-only/no subPath. Fresh Deployment/Secret UID/RV, collision
audit, exact original fields and server-side dry run passed with all container
fields unchanged. Actual update remains Flux SSA, not falsely claimed atomic
live JSONPatch CAS. The first guard failed on omitted API defaultMode420
before Secret/endpoint checks; correction explicitly preserves that default.
The second guard discovered pre-existing self-signed TLS at proxy.branconet.lan
(verification code18), preserved as an open trust gap, not waived or described
healthy. Trusted BORTUS/whoami controls both returned200. No edge mutation
occurred in preflight; rotation remains suspended/unenrolled.
The unpublished one-writer source passed44 tests/full validator. For actual
execution, split the dependency: first publish the corrected Certificate and
edge projection with replicas0, verify real issuance and controls, then publish
replicas1. This prevents ntfy loading an old certificate before cert-manager's
new leaf reaches the Secret while rotation is deliberately paused. The first
checkpoint therefore changes only issuance/route, not serving activation.
Checkpoint0024a70… then passed singleton44-test publication and exact Flux
readiness. Corrected leaf revision2 fingerprint8f301d72… passed actual root/
name-constraints/hostname/server-purpose verification before startup. Native
dashboard Secret UID/RV/full0644 projection preserved, two edge replicas Ready,
trusted BORTUS/whoami controls200. The dependent one-writer source is now
prepared; rotation remains suspended and actual serving/ACL/state acceptance
must follow. System DNS does not yet resolve the new name; pinned SNI/address
verification is not general DNS/phone availability.
Writer source946c1f84… subsequently passed singleton44-test publication/Flux
and real serving qualification. The route serves the exact issued fingerprint
8f301d72… over TLS1.3 with private-CA/hostname/constraints enforced; untrusted
CA, wrong SNI and plaintext are rejected. Both native publishers and the native
subscriber exchanged exact machine message IDs on their respective topics;
six anonymous/read/write/cross-topic operations returned403. This is not human
receipt or a notification from a running monitor/watchdog.

The original production claim/PV/Longhorn IDs remain, encrypted with two actual
running healthy replicas. Actual UID1000/capabilities0/NoNewPrivs/seccomp2,
256MiB/no swap/250m, PID ceiling18847 and no OOM were observed. It is not a
backup/restore or production-restart persistence pass. Trusted unrelated
controls still200. A diagnostic NameError occurred after the passed TLS checks
and before the first publish; it remains preserved. Only the unstarted ACL/
state portion resumed, not the completed TLS or old fixture suites.

Fresh CAS enrollment is now being executed in observe mode using actual
Certificate/leaf Secret/Deployment IDs, pinned CA/image/name and the Traefik
Service address. The delivered controller runs in a bounded diagnostic Job;
it must verify the actual endpoint with no patch/generation change before
auto mode and source-based schedule enablement. Rotation remains suspended
until that result. The source IfNotPresent seed will not reset the enrolled data.
The actual delivered-controller observe Job PASSED: expected served
fingerprint8f301d72…, patch:null, no Deployment generation change. Its exact
diagnostic Job/Pods were removed. Fresh UID/RV/full-data CAS then changed only
mode observe→auto, preserving all pins while the schedule stayed suspended.
The next source increment enables the bounded five-minute CronJob; actual
native execution and preservation of operator enrollment are still to verify.
Schedule source5de2c45d… passed singleton44-test publication and exact Flux
readiness. Flux preserved the operator-owned auto enrollment/pins. The first
real CronJob-owned production run was scheduled22:40:00Z, ran22:40:04–11Z and
returned verified/patch:null for8f301d72…. It used the normal five-minute
schedule, not a manual start or shortened test interval; writer generation2
and original PodUID0fb3c861… remained unchanged. Normal bounded native Job
history is retained (2 successful/2 failed), not deleted as fixture output.
This enables guarded future serving-leaf rollout; it is not a claim of a
forced production renewal, host/node-reboot survival or full notification
availability. Evidence is `ntfy-production-activation/native-schedule-result.json`.

Next: serial DNS delivery for notifications.branconet.lan while preserving both
resolvers, independent monitor/watchdog client-token delivery and actual durable
service/alert/outage qualification. The pre-existing dashboard self-signed trust
gap, attended subscriber/reader, safe kubelet/control-plane lifecycle,
dependency-checked retirement and remaining plaintext/mesh gates stay active.
No previous completed image, fixture, staged identity or serving checks need
replaying. The full goal is not complete.

### Notification DNS delivery — completed; full follow-up active

Completed serving/enrollment/native-schedule receipts reconciled, with no
replay or production ntfy change. Both advertised resolvers `.253`/`.5` and
both cluster backends passed40 baseline TCP/UDP local/upstream/filter checks.
The current record source is immutable v3. New v4 preserves its entire data
and adds only notifications.branconet.lan as a CNAME to ingress.branconet.lan.
Publish secondary first with primary untouched, qualify, then publish primary;
finally apply the existing records-only Ansible policy to standalone node03,
refresh loopback/LAN serially and verify both DHCP-advertised paths from LAN.
Do not equate cluster-backend parity with independent-resolver acceptance.
No router/DHCP, credential, image, CA or ntfy schedule change. Existing records,
claims, gravity/filter state and query history remain protected.

H preflight measured2,232,963,072 conservative retained bytes; two256MB
publisher peaks plus the full1GB reserve fit the approved4.25GB stage. Tools
remain same-inode shared inputs; no new checkout/dependency/image copy.
Evidence is under `ntfy-dns-delivery/`; no general DNS pass is claimed yet.
The scoped observer binds each private source/44-test singleton/Flux result,
claim identities and direct TCP/UDP answers before advancing. The independent
refresh driver wraps only the existing records-only Ansible play plus two
separate named service phases; no launcher upgrade/filtering DB copy/DHCP
change. It refuses existing started phases and rechecks unchanged private
filter data/launchers, source-derived public config and qualified floating
DNS before/after each service restart. The original loopback-only launcher
is retained rather than silently replaced with the newer LAN-capable source.
Secondary checkpoint4a352444… is terminal PASSED:44-test singleton publication,
Flux Ready,402 direct TCP/UDP checks across four paths (48 existing names plus
filter/upstream/new secondary answer). Primary generation stayed unchanged;
all PVC UIDs/volume bindings match. The next source checkpoint changes only the
primary record reference. Independent new-name coverage remains unclaimed.
Primary checkpoint8ecc9f87… then passed44-test singleton/Flux and406 direct
TCP/UDP checks; both cluster backends/floatingDNS now publish the new name
with all claims/legacy names preserved. Independent records-only staging first
stopped at controller RPC startup, before any task/remote change. Its corrected
named recovery uses the repository's existing abstract AF_UNIX bootstrap and
keeps scratch on H; initial failure remains literal. No completed DNS suite
or publication is repeated by this recovery.
The first abstract-RPC attempt next stopped before the first delegated read
on unsupported SSH ControlPath percent formatting (ok0/changed0). No host
configuration task ran. A separate no-multiplex recovery now follows the exact
existing DHCP-driver transport pattern, preserving both failed logs.
That transport passed the ten read-only Ansible tasks but exposed a missing
sudo-variable binding in this older play (changed0, before rendering or staging).
The existing saved credential is available; the play now explicitly reads the
same migration environment variable as other host plays. No password is added
to argv/source/logs and no authentication/permission boundary is bypassed.
The named become-binding continuation must recheck live inputs before the
first actual records-only file change; all failures are retained.
The corrected records-only Ansible stage PASSED(ok16/changed1/failed0), changing
only public pihole.toml; no service/helper/filter DB change. Loopback refresh
PASSED with hashes/DHCP/floatingDNS unchanged. The exact LAN service restart
also completed, but its collector incorrectly queried same-host53 instead of
the process's10554 listener; local OUTPUT does not traverse inbound DNAT.
Separate node01 TCP/UDP queries to advertised5:53 already return the new
record. Finish the remaining read-only validation after that restart, never
restart again merely to correct the collector. The diagnostic failure remains.
Read-only completion then PASSED: same LAN invocation002eaa4a… (no repeated
restart), actual10554 listener/new-name TCP+UDP/filter/API controls, unchanged
config/gravity/launchers/DHCP and qualified floating DNS. The standalone
advertised port53 additionally passed all49 v4 names over both transports
(98 exact checks) from node01.

Actual Windows LAN checks PASSED with the existing lease: both advertised
resolvers `.253` and `.5` return192.168.0.252 over real UDP and explicit TCP;
ordinary Windows DNS also resolves the new name. Ordinary WSL resolution and
HTTPS, with root/hostname verification and no hosts/address override, returned
200 and the unchanged served fingerprint8f301d72…. This closes DNS delivery,
not attended phone/PWA/subscriber receipt or actual monitoring alerts.

Closing readback:9 Flux Kustomizations/36 HelmReleases unsuspended Ready,
three Ready nodes. ntfy's generation2/original PodUID and enabled five-minute
rotation remain unchanged. Private main/validated/immutable tag match
8ecc9f876f1363ad42017a048afb9563599f18d7; Actions remains off, original root
index preserved. `ntfy-dns-delivery/closing-boundary.json` binds the outcome.
Retained trees measured2,593,718,272 conservative bytes plus full1GB reserve,
inside4.25GB; no image/dependency copy. Six exact empty temps total24,576 bytes
remain on a failed consumer-visibility check: finished task PIDs are zombies
and `/proc/1746577/fd` returnedEACCES. No alternate-route/elevation/deletion or
process stop; preserve until normal reaping and later authorized review.
The prior candidate export retention is untouched.

Next dependency-ready action: deliver the distinct native publisher credentials
to fixed independent host profiles and perform the reviewed paused-first
monitor upgrade, real durable state/resource/restart/notification qualification.
Do not replay DNS/publication/serving/schedule checks or the completed Ansible
stage/restarts. Monitor/watchdog availability, actual alert/outage delivery,
attended subscriber/reader, dashboard trust, certificate lifecycle/retirement
and remaining plaintext/mesh gates remain unfinished.

### Independent monitor/notification activation — active

Current installed node02 hashes match the accepted initial checkpoint; monitor
remains disabled/inactive with no DB, credential timer active. Both host
notification profiles are absent and node03 watchdog account is absent.
Preflight admits the bounded host/publication step inside existing4.25GB,
with2,593,726,464 retained plus256MB publisher/20MB evidence peak/full1GB reserve.
The create-only credential driver delivers only each host's distinct native
publisher token plus public CA/fixed pinned destination; no subscriber/server
credentials, logged values, H payload or service activation. Node03 gets only
its required non-login account/private profile, not a running watchdog.
Actual paused-first upgrade/persistence/resources/notifications remain unaccepted.
Both publisher deliveries are terminal PASSED(node02 UID998/node03 UID997):
native matching/create-only root0640 files, consumer read/no-write and unrelated
user denial. No service activation or subscriber token delivery.
Next source increment uses a distinct reviewed upgrade play, binding ten
installed hashes and preserving broker/timer, adding only notifier modules
and the reviewed cache/sender units/drop-in. A new private control-only child
seeds paused/empty ConfigMaps; inactive BORTUS UI grants remain separate.
The first upgrade attempt stopped after two read-only tasks/changed0: YAML
flow-list commas had split a systemctl property argument. The argument is now
quoted; the installed timer/monitor state was not changed. Resume the unstarted
upgrade in a separately named attempt, preserving that failure. A separate
control-render collector also assumed object order and stopped before validation;
selection by exact name corrected it, with no live mutation.
The corrected upgrade is terminal PASSED(ok13/changed4/failed0); no services
enabled/started, original broker/timer modules and definitions preserved.
Private control checkpoint7911a030… passed publication; the initial read-only
observer raced child creation and is finishing only Flux/readback, not
republishing. Qualification will prove paused acknowledgement/no scans, real
service/DB restart, then an actual pending diagnostic CSR driving one real
runner outbox/host publish/machine receipt. No CSR approval/key persistence,
production expiry/CA manipulation or existing credential-timer restart.
Control child is now Ready on exact7911a030… with44-test publication; read-only
creation-race collector was finished without replay. Actual paused monitor
qualification passed: same SQLite inode/policy after systemd restart, zero
scans/events while paused, duplicate owner denied, enabled service and matched
kernel256MiB/no swap/10%/64 tasks/UID998/no capabilities/NoNewPrivs/no OOM.
Custom-signer pending CSR41826f46… was then created solely for real alert-path
qualification (no approval/key persistence), followed by audited fresh CAS
paused→monitor at unchanged300-second/7-day policy. Pending outbox persistence
and actual sender receipt are the next running phase, not yet accepted.
Real native CSR inventory now produced one pending event2621e9b0… for
CSRUID41826f46…. A second actual monitor restart preserved the same SQLite
inode, complete scan ID and undelivered event without duplicate scan/outbox.
This is real durable state, not an inserted synthetic DB row or fixture API.
The independent sender phase is now running against that existing DB; actual
server ACK, subscriber receipt and exact diagnostic retirement remain pending.
Initial sender qualification failed safely: no ACK, event remains pending with
durable backoff. No-token/no-publish probes isolated systemd's post-DNAT
cgroup-SKB filtering: VIP-only timed out, current exact edge IPs worked.
No pod-IP/subnet workaround was adopted. Root-managed nft original-destination
filtering is now prepared for the one sender cgroup, fixed252/TCP443 allow and
deny-all-other IP egress, atomic owned replacement on each service start.
This avoids pod churn and adds no proxy/relay. Actual live allow/deny and
outbox completion are still open; do not reset/re-enable/replay accepted work
or manually mark the pending event delivered.
Live nft qualification now passed in the actual sender cgroup: trusted
HTTPS200, forbidden API6443/VIP80 blocked; exact table counters8 allow/2 reject.
The first probe failed at its bounded observation/network stage and remains.
A distinct no-token/no-publish counter probe passed; normal owned-table
stop cleanup and exact runtime probe/override removal completed. The sender
resumed normally, preserving event2621e9b0… and four-failure backoff due
23:46:39Z. Its acknowledgement/restart observer is running, not a manual send
or reset. Current fresh upgrade source installs the nft helper directly;
do not replay the completed original upgrade or the targeted repair play.
Continuation driver `finish-monitor-notification.py` is prepared for the
original ACK/restart result, exact authenticated subscriber message matching,
then UID/resourceVersion-guarded retirement of only the diagnostic CSR.
It records observed duplicate copies honestly, persists no subscriber token,
and requests a fresh scan through audited same-policy CAS. Its started
records prohibit blind replay after uncertainty; live receipt/cleanup/fresh
inventory are not claimed by source preparation.
Read-only continuation found a fifth real failure, event still undelivered,
next due00:03:22Z. Actual installed profile/event/bounded-child offline checks
passed; no network/publish. Sender source now prepares fixed-allowlist
child/transport journal diagnostics because captured child failures previously
hid their cause. Existing backoff/DB semantics and bounds are unchanged;
local tests must prove private errors cannot enter logs and journal loss is
nonfatal. No live source replacement or delivery success is claimed yet.
The initial recovery observer is now terminal FAILED(unacknowledged600s);
no post-ACK restart ran. Two new diagnostics tests passed. The separately
scoped one-script Ansible correction checks the original installed hash,
preserves retry/DB and every service except its necessary sender stop/start.
Native subscriber and CSR cleanup remain gated on actual ACK.
The diagnostics play stopped only sender, then refused its temporary-file
validation because sibling imports were unavailable from Ansible's temp
directory. No script replacement occurred. Validation now uses the exact
installed module path; continuation must verify sender stopped/source hash
and resume only the unstarted copy/start tasks, not replay the completed stop.
That guarded continuation passed(ok2/changed2); sender resumed unchanged
five-failure backoff. A separate actual sandbox/5%-CPU offline child-entrypoint
check passed (network function replaced in memory, no DB/network), ruling out
basic profile/child-launch failure in those bounds. The next normal due retry
now has a read-only fixed-code/ACK observer; no manual publish/reset/restart.
Subscriber and diagnostic retirement remain unrun until real delivery proof.
The sixth normal attempt failed transport-unavailable/child-failed; unchanged
backoff is due00:35:57Z, no OOM. A separate exact-class/sandbox OPTIONS probe
completed TLS and HTTP401 without a native token or publish, with normal
diagnostic-table teardown. Read-only subscriber uncertainty reconciliation is
now prepared to distinguish possible remote acceptance from local ACK failure;
it does not satisfy the guarded CSR-cleanup gate by itself.
Native subscriber uncertainty poll found zero copies of the original stable
event (trusted/authenticated read; not proof of permanent non-delivery).
No publish/reset/CSR retirement followed. A distinct full-child/implicit-HTTP
diagnostic is active with POST replaced by OPTIONS and its credential header
replaced; it tests the failing child transport shape under unchanged bounds,
not replaying prior successful health/ACL checks.

Independent read-only retirement discovery also confirmed wordpress/jtmb-cc
still Ready (UID591745ea…), no certificate owner, and no matching references
in the seven ordinary same-namespace workload/Ingress kinds. Its declaration
still exists in private public-certificates.yaml. This is not an external/
controller/Secret-cascade dependency proof and no retirement was performed.
Full-child transport diagnostic then completed trusted HTTP401 in2.399s,
with OPTIONS/fake header replacing publication and normal nft cleanup.
Production failure is still unisolated. Transport source now adds fixed
stage/kind annotations to the unchanged public error, with independent
journal allowlisting; no backend/credential data, timeout relaxation or retry
reset. Actual next normal retry, not a manual send, must establish the cause.
Six focused diagnostics/real-loopback transport checks passed on the changed
source, including trust/hostname/redirect/auth/mismatch/size rejection. The
scoped play now guards both old source hashes and updates only transport/
sender annotations. Earlier one-file install records remain distinct.
All synthetic test material and its empty4096-byte directory were removed.
The guarded annotation install passed(ok7/changed3/failed0), updating only
transport/sender modules; all bounds and retry state preserved. Its read-only
native observer is active until ACK or fixed-stage diagnosis on the unchanged
00:35:57Z due retry. Do not repeat probes/installs or force publication.
Retirement Secret metadata found no owners/finalizers, values not emitted;
no dependency-complete retirement or delivery acceptance is claimed.
The original pending event was ACKed at00:36:26Z by its normal retry; its retry
row cleared without reset/manual publication. Intermittent transport cause
remains unknown, not claimed repaired by diagnostic changes. Post-ACK restart
qualification is active, then exact subscriber/CSR cleanup and same-policy
fresh-inventory parity/zero-CSR qualification. All earlier failed attempts
and their literal timing/resource evidence remain.
Bounded host-delivery/persistence checkpoint is now PASSED. Native subscriber
received exactly one cached message matching the original event/CSR UID;
actual sender restart preserved delivered row/inode3415914 and first loop
accepted0/failed0/pending0, with unchanged bounds/UID/no capabilities/noOOM.
Monitor and accepted credential timer invocations and broker bytes remained.
Only the diagnostic CSR was retired by fresh UID/RV, with no lifecycle state.
Audit-only same-policy refresh then passed two fresh sources/complete scan
and operator UID/state parity:15 healthy Certificates,0 CSRs,0 pending events.
Closing cluster:10 Kustomizations/36 HelmReleases unsuspended Ready,3 Ready
nodes, ntfy writer/rotation unchanged, root index/private HEAD7911a030… preserved.
`monitor-notification-delivery-acceptance.json` binds finite results.

Acceptance limit:3972.298674s creation→ACK (~66.2min), not an immediate-alert
or general transport reliability pass. Earlier failures remain and later
intermittent cause is unknown; diagnostics stay. No attended receipt/reboot/
watchdog/UI-release acceptance follows. Next dependency-ready work is separate
node03 API identity/short-lived refresh plus durable watchdog/outage delivery;
preserve current monitor/sender/timer/outbox/native auth/data and all later
lifecycle/retirement/plaintext/mesh gates.
Separate node03 watchdog preflight is now PASSED read-only: UID997 publisher
profile unchanged, existing root-private bootstrap/public CA/tool present,
all watchdog code/state/enrollment/services/API identity absent. Fresh monitor
and node02 Lease pins captured; no root credential copy, host mutation or mint.
New source profile narrows watchdog to two exact GETs and denies monitor
inventory/PATCH privilege, with separate fixed node03 broker/UID quarantine.
Shared default monitor semantics need regression qualification; accepted
installed node02 sources remain unchanged. Watchdog live identity, staging,
rotation, persistence/outage/subscriber acceptance still unrun.
Inactive watchdog credential unit/timer sources and focused scope tests are
now prepared; token1h/refresh20min,256MiB/no swap/10%/64tasks/API-VIP-only.
Enrollment/private-bootstrap guards fail before mint. This does not install
anything or reuse the monitor's identity, runtime token or installed modules.
Thirteen credential checks passed, including all eight changed-source default
monitor regressions and five watchdog-scope/refusal cases. Both inactive units
verify locally; node03 Python parsed both modules from stdin without executing/
installing. Local controller warnings (existing Ingenium symlink and ignored
CPUAccounting on controller) remain; target systemd249 support is distinct.
Private source now references only the five-object exact-reader identity,
depending on controls; the existing contract test adds activation/identity-only
assertions without changing the44-test gate. No publication/mint/install yet.
External qualifier source now uses only a sealed private RAM candidate for
actual subject/scope/read/Forbidden checks after exact identity Flux. It
creates no credential payload on H/host disk, performs only a denied dry-run
metadata PATCH, and makes no token-revocation/installed-refresh claim.
Initial synthetic memfd smoke found missing Python fcntl constant names,
before any network/mint; FD closed, no disk payload. Compatibility correction
uses stable Linux UAPI values with mandatory kernel seal readback, never an
unsealed fallback. Corrected smoke and actual effective identity remain next.
Corrected sealed-config smoke PASSED real kubectl parse/kernel seal15/write
EPERM, with FD closed/no network/mint/disk payload. Private identity-only
commit7970fc1… is pushed after two affected candidate tests/five server dry
runs/full validator30 charts/31 releases/113 resources/credential scan.
Its read-only44-test singleton/Flux observer is active; do not repeat push or
restart watcher. Preflight-by-default host play is prepared for broker-only
staging after actual identity proof, preserving publisher inodes/node02.
Identity-only7970fc1… is terminal PASSED:44-test/full-validator singleton
promotion, exact parent/child Flux Ready, five live identity objects/source
match, main/validated/immutable tag equal. Pin watchdog SAUID34e95231….
Actual sealed-RAM credential proof PASSED its authenticated independent
subject,2 allow/30 deny reviews,2 exact reads/7 actual Forbidden checks.
Candidate FD closed/no disk/host credential payload; no server revocation
claim. No watchdog host install/enable or node02 mutation occurred.
Actual Ansible node03 preflight passed(ok6/changed0/failed0/skipped9); broker-
only staging is now running under its own source-bound receipt. Reconcile its
result before any start. Fixed node03 collector wrapper reuses the accepted
resource/journal/timer observer, with staged hash/enrollment/first-token guards
and2/30 effective-scope expectations; detector/sender activation is not part
of credential phases. No original node02 phase is rerun.
Broker-only staging is terminal PASSED(ok15/changed6/failed0): five code files,
public CA/identity/runtime-token-reference config and two inactive credential
unit definitions. Existing publisher files were not targeted. Actual node03
`once` broker/kernel/identity qualification is running; reconcile its terminal
receipt before normal timer arming/periodic observation. Never repeat staging
or an uncertain root broker start. Detector/notifier/state remain absent;
any successfully created runtime token now has the broker as its owner/consumer.
Actual root broker `once` PASSED:295 samples, observed max69,402,624 bytes/
4tasks, actual Python NoNewPrivs1/CapEff+CapBnd9, all256MiB/no swap/10%/
64task limits matched; first pre-exec context is separately retained.
Own2/30 scope/exact reads and root:997/0640 token passed. Only normal credential
timer is enabled; initial scheduled invocation passed and read-only periodic
observer is active against its recorded next20min due. Do not reset/re-arm/
rerun broker or claim periodic acceptance yet. Detector/notifier remain absent.
Their next source prepares a separate volatile cache and fixed node03/UID997
original-VIP notifier wrapper, not an installed rollout or change to node02.
Real periodic credential refresh is now PASSED:1200.312130s observed interval,
new invocation8346afa4…, token inode/mtime replaced root:997/0640 on unchanged
boot5a456fc3…, timer active. Runtime install then passed after that proof
(ok13/changed3): seven new root sources/public armed enrollment/two inactive
units; accepted broker/timer unchanged by the play.
Detector healthy qualification is PASSED: enabled actual UID997/CapEff0/
NoNewPrivs1,128MiB/no swap/5%/32tasks/no OOM, private0700/0600 state, healthy
coverage/heartbeat/lease and zero pending. Initial failure was only the
read-only SQLite inspection during a write; venv/source now retries read-only
opens and the phase was completed without restart/re-enable. A separate bounded
node02 monitor outage/recovery delivery test is running; no outage result/attended
receipt is claimed. The first outage attempt failed before mutation on an
undefined read-only property constant; monitor was rechecked active and a
distinctly named baseline-retry attempt is active, not an unreviewed replay.
That retry is now terminal PASSED. A real bounded node02 monitor stop produced
durable outbox event768e7671… (`missed`) after181.125671s while the Lease stayed
healthy; the node03 sender ACKed it, the monitor was restarted into a new
invocation, and recovery event471333aa… was ACKed at01:48:36Z. Authenticated
subscriber contained exactly one copy of each. Monitor DB inode3415914/policy
and its credential timer persisted; detector/notifier/credential timer are
enabled, only the owned sender table remains in nft, and no runtime overrides
or diagnostic tables survive. A read-only verifier defect (tuple compared to
dict) was corrected before acceptance; the first poll did not mutate anything.
Machine receipt is not attended delivery, and full-cluster/node03-failure
resilience is not claimed.

### Kubelet-serving CSR approval — observation delivered, approval gated

The strict validator existed already; this increment adds the controller and
its scoped identity. `kubelet_csr_controller.py` keeps one durable verdict per
CSR UID, refuses a changed request under the same UID, permits at most one
approval per UID across restarts, and verifies an issued certificate's
SANs/serving usage/validity as a separate step from installation. Fifteen
focused checks passed: observation-never-approves, trusted-enrollment shape,
diagnostic-object refusal, unknown mode, single-approval/recreation, issuance
without approval, ineligible nodes, issued SAN/usage/expiry mismatches, runner
defaults, plus the six existing policy regressions.
`run-kubelet-csr-controller.py` is observe-by-default, requires an explicit
operator enrollment file (never derived from a CSR), refuses approve mode unless
the approval flag is supplied, and re-reads the exact CSR and node before each
verdict. Live run for node02 was read-only: zero pending CSRs, no mutation.
Private checkpointb81ba44… passed the unchanged44-test/validator gate and
exact Flux; it adds `<code>bortus-csr-controller</code>` (SA UID244f185e…, no
automount) with get/list on CSRs and nodes only, plus a one-per-UID approval
audit table that has no live writer yet. Effective scope was proven with a
sealed RAM token: two reads allowed, seven reviews denied, two actual403.
Open: a real pending-CSR positive/negative qualification, managed-host install,
installed-certificate endpoint verification, and enabling approval only after
those pass. No CSR was approved, signed or recreated by this increment.

That positive/negative qualification is now PASSED with approval disabled. Two
genuine pending CSRs were submitted from node02's own kubelet credential
(`system:node:node02`, groups `system:nodes`): the enrolled identity and a
variant with an extra `node03` SAN. Observation recorded `eligible` (no
reasons) and `sans_invalid` respectively, durably and per CSR UID, with
`approved_at`/`issued_verified_at` empty; cluster truth stayed pending with no
certificate or condition. Both diagnostics were then deleted with fresh
UID/resourceVersion preconditions, leaving zero CSRs. Fixture private keys were
generated in-process and never persisted or returned.
Served-endpoint verification is now implemented as a pure check requiring the
presented certificate to chain to the enrolled issuer, carry exactly the
enrolled DNS/IP identities, be currently valid and be server-auth capable.
Against node02's live kubelet endpoint it passed (TLS1.3,
`CN=system:node:node02,O=system:nodes`, issuer `CN=kubernetes`), pinning
fingerprint `80a9e9fe…` with NotAfter 2027-11-16; eleven controller tests pass.
Remaining before approval enablement: an actual renewal window that issues a
certificate for a validated CSR (so issued and served fingerprints can be
matched), plus a managed-host controller installation and restart persistence.

A real issuance flow has now run through the validated path. A genuine
`system:node:node02` kubelet-serving CSR was validated eligible and approved
exactly once by the operator-driven controller (approval rows = 1); the managed
service stayed in observe mode. The Kubernetes signer issued the certificate,
`verify_issued` accepted it, and its fingerprint `71374174…` matched the
fingerprint served by a bounded TLS1.3 listener holding that issued
certificate/key pair. Kubelet's own serving certificate was deliberately left
untouched (`80a9e9fe…`), so kubelet `serverTLSBootstrap` adoption is still a
separate gate.
Kubelet `serverTLSBootstrap` adoption is now demonstrated on node02. The setting
was already true; rotation was forced by moving kubelet's current serving file
aside under a root-only backup. Kubelet itself requested `csr-ds7tz` as
`system:node:node02`; the controller validated and approved that single CSR for
the enrolled node only, the signer issued it, and kubelet wrote and served it:
pre-rotation fingerprint `80a9e9fe…` became `b2d1694e…`, equal to the issued
certificate, SANs `node02`/192.168.0.6, issuer `CN=kubernetes`, NotAfter
2027-11-17. Node02 stayed Ready; monitor, sender, both credential timers and the
CSR controller stayed active. Unattended approval for *future* rotations remains
disabled, so the next rotation will queue a pending CSR for operator action.
Four defects surfaced and were fixed: controller failure reporting after a
successful approval (now reconciles cluster truth), a probe that rejected
kubelet's interim self-signed certificate, cross-attempt receipt overwrites
(now attempt-scoped), and use of `not_valid_after_utc` absent from the host's
cryptography 3.4.8. Every aborted attempt, restore and retired CSR is retained.
Node-reboot survival is now qualified on node02 (the cluster worker hosting the
monitor, sender, CSR controller and both credential timers; node03 was
deliberately deferred because it also hosts the standalone LAN DNS/DHCP).
A genuine pending outbox event was held by stopping the sender, then node02 was
rebooted: boot ID changed `137455a5…` → `f6d82213…`, every BORTUS unit came back
active/enabled without intervention, both runtime tokens were re-minted by their
20-minute timers (`root:998/0640`, `root:997/0640`), the monitor kept the same
SQLite inode `3415914`, the held event was delivered at 03:12:18Z with exactly
one authenticated subscriber copy, a fresh complete scan ran at 03:13:25Z, and
pending notifications returned to zero. The diagnostic CSR was retired under
UID/resourceVersion guards, leaving only kubelet's real issued serving CSR
(`csr-ds7tz`); inventory is 15 healthy certificates and one issued CSR. All
twelve Flux Kustomizations, 36 HelmReleases and three nodes remain Ready.

 The CSR was then deleted with UID/resourceVersion guards and the
qualification key/certificate removed, leaving zero CSRs. Two failures are
retained honestly: an approve invocation whose nonzero exit was reconciled from
durable state without re-approving, and an initial write of the base64-encoded
certificate without decoding. Approval remains disabled for the service.

The observation controller is now installed as a managed host service on node02
with approval still disabled. Preflight changed nothing; installation added
nine root-managed sources, public enrollment/identity/config/CA and three
inactive units (`ok15/changed8`). Only the controller's own one-hour credential
timer was enabled: 4 allowed and 23 denied effective checks, token `root:997/0640`,
consumer read-but-not-write, root bootstrap/lock unreadable, code/profile not
writable. The service runs as UID997 with no capabilities and `NoNewPrivs=1`
under 128 MiB/no swap/5% CPU/32 tasks. Persistence was proven with a genuine
pending node02 CSR observed by the managed service, then an actual restart:
same SQLite inode, identical durable row, zero approvals, fixture retired and
zero cluster CSRs afterwards. Preserved node02 monitor/sender/timer and the
monitor DB inode remained intact. Approval enablement still requires a real
renewal window; node reboot, attended receipt, UI release, retirement review
and plaintext/mesh remain open.
Four changed-helper refusal/profile cases and both local runtime units passed.
Actual UID997 managed-token API reads/OS read-no-write/root-bootstrap+lock
denials passed; publisher inodes unchanged. Separate runtime play now prepares
only new detector/sender files/public arming/inactive units, preserving the
seven accepted broker hashes/timer and refusing old state. Install depends on
actual periodic acceptance; source/preflight does not activate services.

## qBittorrent VPN replacement

Replace only the VPN sidecar. Keep the qBittorrent image, profile claim, download mounts, WebUI Service and qBit Monitor. Use the standard WireGuard client and Proton’s documented NAT-PMP workflow. The selected tools must run on the existing Kubernetes nodes without host networking or host firewall changes. Keep the endpoint-specific WireGuard profile in a native Secret.

Install a default-drop firewall inside the pod before qBittorrent starts. Permit the Proton UDP endpoint, the tunnel, loopback and the existing WebUI clients on their required port. Verify DNS goes through the tunnel. Keep the firewall enforced when the tunnel is missing or the VPN process restarts.

Request both TCP and UDP mappings and confirm their ports match before publishing the existing forwarded-port file. Renew early enough to retry within the 60-second lease. Withdraw the reported port and close its firewall rule when the lease expires. Proton can still reassign a port. The tunnel should stay up when that happens, and qBit Monitor should update qBittorrent to the new lease. Keep the existing shared claim and `/tmp/gluetun/forwarded_port` compatibility path. The pinned monitor reads only that file and qBittorrent’s Web API. The deployed code accepted a synthetic valid port, verified the API write, generated one notification through a stub, and rejected an invalid or missing file without another write or notification. A separate two-container pod then verified that the candidate WireGuard tool image could publish the file atomically on a shared volume and the pinned monitor image could consume it read-only, update the stubbed API once, and verify the result. The disposable pod was removed. Repeat the check with the replacement’s live Proton lease during the serial handoff. A monitor PR is needed only if the live replacement cannot preserve this contract. Live qBit Monitor also authenticated after the Gluetun image rollback, matched the active lease and read the existing 230-item queue. qBittorrent’s built-in UPnP/NAT-PMP was enabled. It was disabled through its Web API and read back so only the VPN sidecar manages the forwarding lease.

Use a disposable pod without production claims for firewall and tunnel failure checks. Test live Proton forwarding with a separate authorized profile or a serial handoff to avoid two clients using the same WireGuard key. Require repeated lease renewals, outside inbound TCP, tunneled HTTPS egress, a forced tunnel-down leak check and a match between the forwarded and listening ports. Cut over only the qBittorrent release through the existing validated Flux pipeline, with its prior revision available for rollback.

Flux deployed charts revision `ff36a12b0f67` with the pinned Hotio base image
running the chart's WireGuard and NAT-PMP lease script. The pod uses Proton's
in-tunnel DNS. The isolated kernel WireGuard trial published a matching
TCP/UDP lease, replaced it on reassignment, and denied traffic outside the
tunnel with and without the interface present. The trial resources were removed.

Live qBit Monitor read the replacement lease and updated qBittorrent through
its existing authenticated API. The 230-item queue and all four application and
monitor claim bindings matched the baseline. The LAN WebUI and the Radarr and
Sonarr Service paths answered. qBittorrent's public HTTPS egress differed from
the node's, and the Proton forwarded TCP port accepted an inbound connection.
Disable `protonWireGuard.enabled` in the qBittorrent HelmRelease and publish
through validated Flux to roll back. The new sidecar keeps the old container
name for Helm field ownership. The chart documentation records the native
profile and rollback procedure. A server-side dry run against the live
Deployment accepted the prior VPN image, Secret, shared mounts and
loopback DNS without the replacement profile or script mounted.

During five minutes of observation, all 49 lease samples had an active port.
There were 12 observed timer refreshes and three distinct ports. Proton
reassigned the port twice with zero container restarts. qBit Monitor applied
each observed port through the authenticated API. Both inbound TCP and UDP
were verified. The new sidecar handles reassignment, while the cause of
Proton's recurring reassignment remains open.

A follow-up passive check found one WireGuard handshake that left the
forwarded port unchanged. A later handshake was followed by a port change
about five seconds later. This is a timing association. It does not establish
that WireGuard key rotation causes the Proton gateway to reassign the lease.
The live tunnel and qBit Monitor remained available during the observation.

A filtered passive packet capture then observed eight matching TCP and UDP
reply pairs from the Proton gateway. The gateway returned a different port
on both protocols 33 seconds after the preceding successful 60-second
renewal, with its reported epoch still increasing. The new requests used the
same suggested-port value as the previous ones. Both WireGuard handshakes
near the change received responses. This proves the new port originated in
the gateway replies before the previous advertised expiry. It does not
explain why the provider reassigned it.

A live follow-up on November 8 found four further port updates between
06:50 and 06:57 Toronto time. qBit Monitor applied all four. The WireGuard
sidecar, qBittorrent and qBit Monitor each reported zero restarts, and Flux
still reported the deployed chart revision ready. Port stability remains
open even though qBittorrent and its monitor remain available.

The installed NAT-PMP tool is from libnatpmp 20230423, the first
version Proton documents as having the response-parser fix. The sidecar
uses the documented TCP and UDP mapping requests and 60-second lifetime.
It retries sooner than Proton's 45-second example. The first 27
intervals between published port changes averaged about 125 seconds
(range 74–153 seconds). A passive follow-up saw port changes within
19 seconds of completed WireGuard handshakes, as well as a completed
handshake that did not change the port. An alternate renewal interval
remains an untested hypothesis. Do not describe a normal WireGuard
handshake or a healthy pod as evidence of stable forwarding.

The local charts candidate renews a normal lease after about 44 seconds,
using the earlier of the confirmed TCP and UDP deadlines. Short leases
still renew early, failed renewals retry in three seconds, and expiry
handling is unchanged. Bash checks covered all four cases. The pinned
Helm renderer verified the candidate script and checksum under the
effective qBittorrent values. The retained Gluetun credential uses the
same WireGuard key as the live sidecar, so it is not an independent
trial identity. The qBittorrent-only trial used a serial Flux rollout
at charts revision `eb35ed30ae86`. The preflight confirmed 230 torrents,
zero downloading and five seeding. After rollout the queue and claims
were intact, seeding resumed, the monitor matched the forwarded port
through the authenticated API and an external TCP connection reached it.
The slower cadence still saw four Proton reassignments, with
inter-change intervals of about 90, 130 and 61 seconds. The observer
recorded no unavailable lease before the rollback replaced the trial Pod.
The exact baseline chart tree was republished as `007791756df0` to
restore the earlier retry margin. Flux applied it and the replacement Pod
matched the baseline script checksum with both containers ready and zero
restarts. The same four claims were attached, qBit Monitor's authenticated
API matched the forwarded port, and all 230 torrents and active seeding
were verified. Slower renewal did not resolve the churn. A comparison on
another qualified Proton endpoint remains open.

The live peer address and public key matched the catalog bundled with
the prior Gluetun image. Two alternate Montreal peers still resolve to
their catalog addresses. The trial candidate selects the P2P peer on a
different network from the current endpoint. Its catalog entry is older
than the live DNS check, so the actual handshake and forwarding still
require verification. A server-side dry run accepted a native Secret
derived in memory from the existing profile, changing only its public
peer and endpoint. Helm rendering changed only the qBittorrent Secret
reference and preserved Recreate, images, volumes, firewall and routes.
The live trial then created an immutable native trial Secret and used
a serial qBittorrent-only rollout at `a80cf0b68e4d`. CA#181 handshook,
accepted an external TCP connection and kept all 230 torrents and four
claims. qBit Monitor applied the port. The alternate peer reassigned it
twice, with 70 seconds between those changes and no missing lease in
the sample. Both changes followed successful WireGuard handshakes.
Flux restored the original profile at `82a95c5bc766`. Both containers
had zero restarts, all four claims matched, seeding resumed, the monitor
matched the current port and an external TCP connection reached it.
The API reported the trial Secret absent after the UID-checked cleanup.
The original profile remains. The alternate endpoint did not stabilize
port forwarding with this WireGuard identity.

A later November 8 live check found the last reported port transition at
07:46 Toronto time. In a later 35-minute sample, qBit Monitor authenticated
on all 202 polls. All 200 logged listen-port comparisons matched. The
WireGuard sidecar, qBittorrent and qBit Monitor were ready with zero restarts.
Earlier reassignments remain unexplained. No chart or monitor change was made
for this check.

Later on November 8, the live monitor showed frequent Proton port changes
again while both qBittorrent containers and the monitor had zero restarts.
Charts revision `c2e65f6d5b34` tried suggesting the previously assigned
public port on TCP and UDP renewal. Proton still reassigned it and the
observer saw a missing lease. The chart rollback `7863f68` restores
Proton's documented renewal requests. Both revisions mute only Discord
port-change notices, with automatic port sync and other alerts preserved.
A fresh dedicated Proton profile used a different key and peer from the
former production profile. An isolated four-minute test recorded 49 stable
port samples, 12 renewals and successful DNS lookups. Both disposable test
Pods were removed before qBittorrent switched through charts revision
`a8fa6c7caa7a`. The first production window saw a brief lease gap, then
the same port returned. A subsequent four-minute window saw the same port
across 49 samples and 13 renewals, with no missing lease or reassignment.
External TCP worked at both ends of the follow-up, both DNS names resolved
at every checkpoint, and qBitMonitor applied the port and logged 24
successful polls. All 230 torrents and four claim identities were preserved.
The first disposable Proton profile was revoked after the browser exposed
its key. Both browser downloads were removed after native Secret verification.

## Phase 1 — Ingress security

- Keep the corrected SSH Fail2Ban jail and record verification on each node. Traefik access logging is deployed. The legacy ingress path masqueraded the client address. The production floating HTTPS path now preserves the client address on both Traefik replicas. Public probes have yet to yield a correlated Traefik entry.
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

## Live rollout checkpoint

- The isolated Traefik HTTPS test recorded the original LAN client on both nodes with a local backend. The third node rejected the test connection as expected. The existing routes passed and the test Service was removed. All six public hosts reported the expected egress address at Cloudflare's diagnostic endpoint with and without a forged forwarding header. A public application 401 carried a Cloudflare Ray ID and produced no matching Traefik entry. The same LAN application request produced a Traefik 401. Cloudflare security-event attribution and enforcement are still open. The available tunnel credential belongs to the connector. No separate Analytics read credential was found in the existing local or cluster configuration. The read-only event qualifier checks the exact Ray, independently observed client address, host, path and a narrow timestamp window. A local fixture verified exact matching, rejection of unrelated and spoofed-address events, and handling of missing schema or sampled results. Live qualification requires a zone-scoped Analytics read token and an event captured for the exact probe. An origin response alone does not qualify as a Cloudflare Security Event. Keep public enforcement gated on the exact correlated event and reviewed edge rule.
- Production floating HTTPS logged the real LAN source on each live replica for both plain and forged-forwarding-header requests. A controlled Traefik Pod eviction moved the announcement to its peer in 2.48 seconds. Two of 11 sampled homepage HTTPS requests timed out during the handoff, then trusted HTTPS recovered and both replicas were Ready. A candidate Fail2Ban filter matched a current Traefik JSON row framed as a container-runtime log line and the intended 403 variant. It rejected the four negative controls. The installed Fail2Ban parser also matched an actual privileged read of the surviving worker's container log. A timed, source-port-specific nftables test on the production announcer dropped two synthetic TCP packets before destination NAT while the concurrent HTTPS control returned HTTP 200. The test table was removed and the same source port then returned HTTP 200. The Seerr LAN login router is now deployed through charts revision `4673f51446ee`. Synthetic invalid sign-ins on the canonical, mixed-case, trailing-slash, encoded-letter and repeated-slash paths returned 403 on the same login router, with the genuine LAN peer. The generic API 401 used a separate router. The candidate filter now uses only the login router's 403 and ignores infrastructure and non-LAN sources. A direct-port test showed Seerr application logs accept a forged forwarding address on that path, so the app logs cannot be used as the ban authority. No chart references the direct Seerr port and no connections were tracked in the bounded preflight on the three hosts. Charts revision `995a9bf523a5` explicitly cleared the external addresses after an omitted field left the legacy manager's values in place. Direct TCP connections to the port now fail on all three nodes. The internal Service, trusted LAN HTTPS and uncached public tunnel returned HTTP 200, with the same Seerr Pod and claim. The local nftables action and atomic ban snapshot consumer passed packet tests in isolated network namespaces on both edge hosts. The tests verified the protected addresses, exact destination and port, unban, expiry, rejection of malformed snapshots without disturbing current state and cleanup. Flux applied the shared state definition at charts revision `3ec0b8e3a66b`. The live API accepted a versioned write from the dedicated publisher and let the dedicated reader retrieve it. Both identities were denied unrelated reads, object creation and deletion. The reader was denied updates, the publisher was denied patches, and a stale publisher update returned HTTP 409. Forced Flux reconciliation preserved the test data, and the test entry was then removed and verified absent. The local shared-journal candidate now uses the client address and Fail2Ban ticket time as the event identity. Focused worker checks covered duplicate publication, delayed revocation, expiry, concurrent updates and an unavailable API. Its TLS client published and read an expiring test event using the live dedicated identities, retried without advancing the resource version, then confirmed a revoked event could not be reinstated. The test journal was removed and verified empty. The next step is to wire the Fail2Ban action and both firewall readers to rotating credentials, then test a timed ban across a handoff and demonstrate rollback before enabling persistent enforcement. Legacy ingress still produces node or cluster addresses, which must be excluded from any jail.
- The protected etcd backup passed isolated datastore restore, API decryption, stale-watch compaction and three-member leader-loss checks. The shared API endpoint passed authenticated TLS verification and is the kubeadm discovery endpoint. Both workers joined as voting members using their existing Kubernetes Node and Longhorn disk identities. The second worker joined with its existing kubelet and preview containers running. The shared API failed over to a worker while the original control-plane etcd was stopped. The surviving control plane committed and scheduled a test Pod and Flux stayed Ready. The original kubelet needed the shared API to recover. The serial Ansible endpoint play now sets that address on all three kubelets. The repeat test verified automatic recovery and address handback.
- The first worker drain completed using normal eviction. The node was uncordoned when Longhorn replicas went degraded and BORTUS could not start on a node without its pinned image. BORTUS recovered on its original node using the existing claim and image. All 28 attached volumes recovered to Healthy, and all Flux Kustomizations returned Ready.
- Longhorn uses two replicas on distinct nodes. The repeatable Ansible rename preflight rejected all three nodes using the current 46-volume placement. A fresh Longhorn 1.13.0 preflight showed 84 GiB of logical allocations, 50.82 GiB of estimated replica data per full copy, and 46 volumes with two distinct placements. Retiring either worker would leave the original control-plane disk 44.75 GiB below the physical rebuild floor and 8.57 GiB below scheduled capacity. It also lacks the required application state node tag. Retiring the original control-plane node would leave one worker 5.30 GiB below the physical floor after two replicas arrive. The other worker would need to schedule 84 GiB against its 75.43 GiB cap, although its estimated physical margin is positive by 1.94 GiB. The Ansible preflight now reports scheduled use, incoming replica estimates and both capacity limits. Filesystem usage was available for 29 live claims. A preliminary screen found at most 13 GiB of logical reduction from smaller replacement claims under its headroom assumption, which would require verified copies and retirement of the current claims. Seventeen detached claims remain bound. A recorded backup is absent for two of them, and a backup record alone does not qualify the others for retirement. The largest snapshot chains contain protected checkpoints. No capacity settings or storage objects were changed. Keep the existing node identities until both capacity and placement can be qualified without weakening replica protection. The deployed BORTUS image was restored from the checksum-verified archive to a second worker. Containerd verified all image objects on each worker and the original control-plane node. BORTUS then recovered on the original control-plane node using its existing claim during the live promotion. Preserve the other worker's unmanaged preview state and resolve its node-bound workloads before draining it.
- The live rename preflight now reports hostname-bound workload templates, unmanaged Pods with local state and PersistentVolume node affinity before evaluating the existing Longhorn gate. qBittorrent still selects the original control-plane hostname. Ingenium selects Worker 1, where three unmanaged preview Pods also have local state. Worker 2 has no matches in these categories, and no PV hardcodes any of the three hostnames. The Ansible preflight reported the dependencies and rejected the original control-plane candidate without changes. Fresh estimates for that candidate put Worker 1 5.39 GiB below the physical floor and Worker 2 8.57 GiB below the scheduled requirement. All 29 mounted encrypted volume mappings report zero discard capacity, so the existing mappings cannot reclaim Longhorn headroom through filesystem trim. Resolve the capacity and application identity dependencies before any drain or rename.
- After the resumed storage cleanup, Worker 1 reclaimed 6,143,455,232 allocated bytes across five closed, inactive scanner and image-audit duplicates. Two had identical copies in the other scanner directory before cleanup, both scanner databases have SHA-256-verified off-node copies, and the completed BORTUS audit tar was reproduced byte for byte from its retained containerd image using the local streaming exporter. The transfer exporter failed to complete and the original was kept until regeneration succeeded. Scan reports, the audit receipt, the active container image, and the failed YTPTube export were preserved. No NAS copy was needed. The fresh Longhorn projection passed Worker 1's physical gate by 0.37 GiB for the original control-plane rename. Worker 2 still needs 8.57 GiB of scheduled capacity and has a separate 1.75 GiB physical margin. No volume, replica, or node setting changed.
- The approved Worker 2 headroom change is live through Ansible. Its default Longhorn disk reservation fell from 34,710,622,617 to 25,507,762,176 bytes, the minimum adjustment that schedules the current 84 GiB on the surviving disk. The existing 100 percent provisioning cap, 25 percent physical floor, hard node separation, and two copies of every volume were preserved. The fresh post-change projection passed for the original control-plane rename, with 0.37 GiB physical margin on Worker 1 and 1.75 GiB on Worker 2. The playbook can restore the original reservation only after current scheduled use fits under it. No volume or replica was moved by this change.
- The three role-neutral Ansible node labels are live. The exact qBittorrent chart revision `673893822a10` passed local validation and reconciled through Flux. Only the selector changed. Its replacement Pod remained on the original physical node, both containers reached Ready, and both PVC UIDs and PV bindings matched the baseline. The authenticated queue retained 230 torrents and the configured listen port matched Gluetun's actual forwarded port. Radarr and Sonarr passed their saved Service-path tests with zero changes. The original control-plane node now passes the capacity and identity preflight without changes. Before renaming it, verify a fresh recovery point and actual replica evacuation and rejoin. Reapply the stable node label after rejoin. Ingenium and its preview Pods retain their separate owner and preservation sequence.
- Both workers now run Keepalived in readiness-gated standby. The current control plane retained the address, authenticated readiness passed, and a standby received the current announcer's VRRP traffic. Both workers needed a non-recursive correction to the root directory ownership and mode before Keepalived would accept its health check. The first candidate worker has the byte-identical, root-only encryption provider. The shared API failover and return to the original announcer passed after all three members were healthy.
- Pinned control-plane images were cached and ran their version commands on the first candidate worker. The kubeadm manifest rehearsal verified the advertised address, stacked etcd endpoint and read-only encryption provider mount. The current signing key pairs and etcd health passed. Both workers now have the verified image set and byte-identical protected encryption provider. The three unmanaged preview Pods were backed up without eviction. The encrypted archive and original Pod definitions were recovered in isolated memory, all 14 SQLite databases passed quick checks, and the reconstructed Pod definitions passed API admission dry runs. Both worker kubelet configurations were separately backed up and authenticated. An isolated Kubernetes memory-volume reseed passed for all three archives, including file bytes, ownership, modes, timestamps and extended attributes. The restore Pod and its deny policy were removed. Both workers passed live CA-pinned kubeadm join preflight and the temporary bootstrap token was revoked. Preflight permitted the two expected checks for a running kubelet and reported swap, which is allowed by the live kubelet configuration. A replacement startup gate was then exercised in Kubernetes. It prevented the main container from starting until the restored files and metadata passed verification. Direct CRI access on the master also verified etcd health and one voting member without routing through the Kubernetes API. Use that independent check during the cutover, and keep the two-voter interval bounded.
- The additive LAN HTTPS chart passed server-side admission and was published to private charts main. It places the Traefik replicas on separate MetalLB-eligible nodes and leaves existing LAN routes available during the trial. The local validator promoted the exact commit and Flux applied it. The two workers each hosted one ready endpoint. Trusted HTTPS for the cluster dashboard and homepage matched the old route. The floating address moved to the peer worker after eviction of the announcing Traefik Pod, and the homepage returned HTTP 200 during the handoff. Both replicas recovered and all six public routes responded.
- Private DNS standby is deployed on a different node and has a healthy encrypted Longhorn claim with two replicas. The approved seed path transferred local configuration and the gravity database without copying query history. Both backends matched 42 local DNS names over UDP and TCP, upstream resolution and a filtering probe. The standby keeps seven days of its own history. Flux applied the edge-announcer pin and Plex and floating HTTPS passed afterward. The original control-plane node is now eligible for DNS without changing those existing announcer pools. Flux applied the floating DNS address for the verified standby and a LAN client verified it over TCP and UDP. The existing DNS addresses still answer. The gateway forwards local queries to the primary, and the NAS did not answer a DNS probe. Both Pi-hole backends now serve the floating DNS address from different nodes. Flux applied charts revision `e8148c2255ae`. After the primary restart, both backends returned the same 42 local answers over TCP and UDP and passed filtering and upstream resolution. The primary pod replacement preserved all bound claims and sampled legacy DNS. A separate controlled endpoint withdrawal moved the floating announcement to the standby in under a second. All 76 Windows TCP and UDP probes passed across the move and return. The two temporary legacy DNS EndpointSlices were removed by verified UID, and the gateway, three old DNS addresses and the floating address answered again afterward. The 22 LAN ingress hostnames returned the same trusted HTTPS status on the floating and legacy addresses. Both Pi-hole instances now use the same immutable, chart-managed address and alias records. Flux applied charts revision `60e296434c28` after a standby-first rollout. Both effective configurations match the published list and returned all 42 local answers over both transports. Filtering and upstream probes passed and claim identities were preserved. A rollout monitor observed no failures in 1,050 queries through the gateway, three legacy DNS addresses and the floating DNS address. The temporary DNS endpoints were removed. The six previously unused role-neutral host and floating service names are live on both resolvers through charts revision `2d1286371b5a`. Both transports returned the expected addresses through the floating resolver and router from Windows. All 42 existing answers matched between the backends, and 360 sampled existing DNS queries passed during rollout. Temporary legacy endpoints were removed and all claims were preserved. The physical host aliases are in place and the Linux and Kubernetes identities still require the guarded rename. The NAS management API requires authentication and the NAS does not currently provide DNS. The desktop uses NAT-mode WSL, has a Windows SharedAccess listener on UDP 53 and did not answer LAN DNS probes. The active Windows DHCP lease lists the XR500 as its only resolver, which matches the Netgear XR500 manual. Directly advertising two resolvers requires a DHCP service that supports custom DNS options. A rootless host resolver on an existing worker ran outside Kubernetes using dnsmasq and the immutable chart records. It matched all 48 local names against the live Pi-hole address over UDP and TCP, resolved public names directly through the same configured upstreams, and returned NXDOMAIN for unknown private names. The listener was stopped and its configuration never touched host disk. This proves the standalone local-record path. The same worker also ran the exact pinned Pi-hole FTL image as a standalone container in an isolated network namespace. A read-only SQLite backup of the standby gravity database passed integrity checks and was opened only in RAM. The database contained 1,342,288 entries, one enabled group and no client-specific assignments. The isolated instance matched all 48 local records and the active blocking probe over both transports. The test container, namespace and RAM state were removed. The Ansible renderer can reproduce the qualified loopback settings without the production admin configuration or query history. The repeatable Ansible refresh resolves the standby claim by identity, reads its encrypted CSI staging mount in read-only SQLite mode, and stages a verified policy and generated loopback configuration in a private host directory. A repeat run left identical gravity data in place. Failure fixtures kept the last good data when the source was absent or client grouping drifted. A separate cold start used only the staged files and pinned image, with no Kubernetes API reads, and passed 98 DNS and filtering checks. The isolated runtime and RAM copies were removed. Refresh is currently on demand. Ansible installed and enabled the standalone FTL service on Worker 2 after verifying that it bound only to loopback on port 10554 and blocked the test domain over both transports. After a controlled systemd restart it answered all 48 local names identically to the floating Pi-hole resolver over TCP and UDP and passed the filtering and public-resolution probes, for 100 checks total. The Windows LAN probe could not reach the staging port. The gateway, all three legacy DNS addresses, and the floating DNS address still answered, and the three legacy admin endpoints returned their expected redirects. LAN activation requires a port-specific handoff. Keep the existing Pi-hole selector and ports for the other legacy addresses, retain the Worker 2 admin route on TCP 8079, and transfer only Worker 2's TCP and UDP port 53 to the standalone resolver. Verify both protocols and the admin route from the LAN, and retain the previous Service configuration as rollback before any separately gated client/DHCP cutover. The local Pi-hole chart candidate preserves the original Service and its internal port list on the other legacy addresses. It gives Worker 2 its own admin-only Service on TCP 8079 with the same backend selector. The exact Helm render passed cluster admission in server dry run. A direct isolated port 53 bind failed because the non-root container did not receive an effective bind capability. A separate two-namespace trial kept FTL non-root with zero effective capabilities and bound only the intended IPv4 address on the unprivileged port. A LAN-interface and subnet-scoped nftables translation accepted TCP and UDP port 53 from the isolated peer. All 48 local names and the blocking probe passed on both transports. Direct high-port requests and requests to the other interface address failed as expected. The trial removed the two network namespaces, container, and RAM-backed data. The chart is local and the real host still listens only on loopback. The Ansible staging playbook installed the dedicated LAN unit, non-root launcher and scoped nftables transaction on Worker 2. The LAN unit is inactive and disabled. The exact staged rules were rehearsed in isolated network namespaces. Both transports passed 98 name and filtering checks, the direct high port was rejected, and removing the owned table closed port 53 for a fresh connection. Repeated removal was harmless and an unrelated table with the same name was preserved. The staged launcher stops its owned container before removing the firewall guard, including after a failed service startup. The isolated trial state was removed. After staging, the loopback unit remained active and enabled, and a LAN client verified the existing Worker 2 DNS and admin responses. The live handoff is still gated. Activate the staged service, verify the host listener and its firewall, then publish the exact Pi-hole Service split through Flux and verify fresh TCP and UDP connections hit the host rule and the admin redirect still works. For rollback, restore and verify the original Flux Service mapping first, then stop and disable the standalone LAN service and verify fresh flows on both transports. Existing tracked connections may age out separately. The cutover playbook defaults to read-only preflight, which passed against the live routing. Once the exact DNS handoff is authorized, run it with `dns_lan_action=start`, publish the reviewed Pi-hole chart split through the existing Flux pipeline, then run `dns_lan_action=confirm`. Confirmation checks the actual split admin Service and requires both independent host forwarding counters to increase during probes before enabling boot persistence. The isolated test advanced both counters and passed rollback with no residual test state. Confirmation against the old mapping refused before making any change. If a live rollout fails, restore the original chart mapping, then run `dns_lan_action=rollback` only after the original TCP, UDP, and admin paths respond. Repeat checks from a LAN client using fresh connections. The application hostname cutover is prepared as a separate local chart patch. It creates a new immutable record set and moves 22 verified application names to the floating HTTPS address. Windows certificate and application probes matched the old route for those names, including the Pi-hole admin path and an authenticated qBittorrent session. The apex, node names, NAS, Plex, and unqualified aliases are among the 26 answers preserved. Both chart slices apply cleanly and the new ConfigMap passed strict Kubernetes admission dry run. An isolated FTL instance rendered from the exact candidate passed all 98 DNS and filtering checks and the trial state was removed. The standalone Ansible refresh now discovers the immutable version from both ready deployments and refuses to replace its cached policy while the versions differ. It ran against the live deployments with zero changes. After the separately authorized standby-first rollout, refresh the standalone policy only after both deployments converge. Retain the prior ConfigMap and restore its references in reverse rollout order if validation fails.
- The original control-plane host rejoined as Node One in Linux and Kubernetes after normal eviction and Longhorn replica evacuation. Etcd retained the same three member IDs and the shared API stayed available. The other two node names are unchanged. qBittorrent came back on Node One with its existing claims and queue. Worker 2 briefly reported disk pressure after workload relocation. It cleared, and the Vaultwarden volume recovered to healthy.

- After the rename, Node One's rollback directory was moved intact to a root-only recovery directory outside the active Kubernetes configuration. A fresh encrypted control-plane backup passed using the new name.
- The fresh admission playbook rejected both remaining renames. Either move would require Node One to receive an estimated 50.77 GiB of replica data, leaving it 44.60 GiB below the current physical floor and 8.57 GiB below the scheduled requirement. Its Longhorn node tags also exclude the Ingenium claim. Worker 1 still has one hostname-bound deployment and three unmanaged previews with local state. Worker 2 has no identity-bound Kubernetes workload in the report. The approved NAS is a candidate for encrypted temporary backups of verified inactive files. Keep two live Longhorn copies, and rerun admission after any space recovery.
- With the approved brief reduction in live copies, Worker 2 drained normally and rejoined as Node Three with the same etcd member ID and the same Longhorn disk UUID. Longhorn adopted 45 replica records on that disk. The one pre-existing failed copy was replaced by a healthy copy elsewhere. The free-space threshold was briefly set to 20 percent to let existing copies resync and restored to 25 percent. All 29 attached volumes returned to healthy. DNS and Pi-hole admin remained reachable, and Plex responded through its floating address after rescheduling. Worker 1 remains under its original name.

- Worker 1 is now Node Two. Its first attempt rolled back after the kubelet rejected a malformed etcd manifest. The corrected manifest passed a dry run before the retry. The retry preserved all three etcd member IDs and the original Longhorn disk and replica identities. Ingenium uses its stable placement label and is Ready on the same machine. Each of the three preview Pods restored its verified checkpoint before startup and returned Ready with its existing image. The old Calico tunnel addresses briefly blocked Plex across nodes. Flux deployed the three current source addresses, and a LAN client decoded 239 video frames through the floating Plex address. The Ansible Plex verifier also passed its runtime, policy, and retained claim checks.
- Worker 2 LAN DNS is live and enabled at boot. The exact cached Pi-hole image was restored from Node One after a missing-image startup failure, then pinned against kubelet image cleanup. The standalone unit passed a restart before the chart split. The local publisher promoted the split, Flux applied it, and Ansible confirmed that fresh TCP and UDP queries incremented the host counters before enabling the service at boot. Pi-hole admin still responds on the original port. Local DNS, upstream recursion and filtering passed. The router read-back showed the approved DHCP pool end. This handoff changed no router settings.
- The three renamed control-plane nodes are Ready. A fresh encrypted post-rename checkpoint passed. Longhorn restored all 29 attached volumes to healthy, returned to its normal free-space threshold, and retired the two empty old-name node records. Plex kept the same server identity in a controlled LAN announcer handoff between the workers. Direct public HTTPS playback also passed from a Proton VPN exit distinct from the home WAN, with Plex Relay disabled. The same server served a library video and FFmpeg decoded 119 frames both before and after the floating address moved to the other worker. The temporary announcement exclusion was removed. qBittorrent retained its queue and its VPN port matched the configured listening port. All six public sites returned HTTP 200 through Cloudflare.
- The standby and then primary deployed local record set v3. Each passed all 48 local names over both TCP and UDP, filtering and upstream recursion. Ansible then refreshed the independent resolver's records without changing its filtering database. Both standalone profiles passed after restart. The independent resolver, floating DNS address and router resolver all returned the expected local addresses from the desktop. Pi-hole admin retained its original direct port. LAN HTTPS works through the shared floating address.
- An isolated DHCP rehearsal on the existing Worker 2 used an imported synthetic lease. The actual DHCP ACK preserved the client address and subnet, advertised the router as the default gateway, and returned the floating and independent DNS addresses in order as option 6. A normal Linux client lookup used the second advertised resolver when the first stopped, and failed after both stopped. The trial used two disconnected network namespaces and removed both, including all RAM-backed test state. The live Windows lease still uses the XR500 as its only resolver. Its observed lease duration is 24 hours. This proves the duration of that client lease only. A staged pool handoff must use a verified lease bound for the entire relinquished range and account for reservations and static assignments. The protected router LAN page exposes five reservation rows but does not provide the active lease expirations or client identifiers required to qualify a no-conflict lease transfer. Production DHCP handoff still requires a verified lease and reservation migration or a proven nonoverlapping pool, the live standalone resolver, a rollback that prevents both DHCP servers from answering at once, and separately authorized router and client changes. Verify actual Windows renewal and resolver use after that cutover.
- The Kubernetes MCP ServiceAccount and list-only RBAC passed strict server-side dry-run. The existing shared launcher passed a syntax check. The private charts validator promoted the inventory identity, and Flux applied that revision. The dedicated short-lived token successfully listed workloads over verified TLS and was denied Secret reads, ConfigMaps, mutations, exec, port forwarding and token creation. The pinned executable returned live workload data through the shared stdio launcher. Both client entries are present. A native Codex app-server call in an ephemeral chat discovered exactly the three intended tools and listed the live Flux source-controller. A native Secret-list call was denied by Kubernetes. OpenCode v2.2.5's own CLI wrote the same supported configuration and reported reading it in an isolated runtime, but its native MCP listing still returned no entries. Its runtime registration endpoint accepted the same entry in a disposable instance, and the native registry transitioned from pending to connected before cleanup. An authenticated disposable OpenCode v2.2.5 server resolved the cold registry behavior. The MCP list was empty before agent initialization, even after location lookup. An agent inventory request activated the location, and all five persisted MCP entries became connected without runtime registration. The native CLI listed all five. Native OpenCode Code Mode then called all five saved adapters in an authenticated disposable v2.2.5 server. A local deterministic model selected the actual tools. The Kubernetes MCP returned the live Flux source-controller and denied listing Secrets. The remaining identities and tools retain their previously verified scopes.

- The Pi-hole MCP is installed in the shared WSL MCP directory and registered in both client configurations. Codex invoked the live health tool and verified trusted HTTPS plus UDP and TCP local and blocking probes. OpenCode connected after explicit runtime registration. The protected filtering and record API contracts passed using transient operator sessions, but the adapter's local application password is still needed for routine authenticated calls. The existing application password was preserved and no administrative credential was written locally.

- Private Plex and Seerr MCP adapters are registered in both clients. The reviewed upstream candidates remain pinned. Each adapter exposes fixed read tools over verified LAN HTTPS and keeps its existing service credential in a private local environment file. Native Codex listed live Plex libraries and Seerr requests. Direct stdio also verified both searches. OpenCode connected to both adapters after explicit registration. OpenCode also connected to both adapters from saved configuration after the agent runtime initialized. Native OpenCode Code Mode read live Plex libraries and Seerr requests from saved registrations. Both clients returned the exact live Seerr proposal for an available-to-request test title. An operator-only executor requires a separate reviewed digest and a narrowly scoped session instead of the admin API key. A loopback API fixture verified pending submission and readback, exact TV seasons, privilege and replay refusal, and a hold on retry after an unconfirmed response. No live request was submitted. A read-only live permission check found six existing accounts and no request-only match. Live acceptance requires a dedicated request-only account and an exact title the operator authorizes for submission.

- The Netgear MCP authenticated against the protected LAN page and read back the intended DHCP bounds in a fresh stdio session. Native OpenCode Code Mode authenticated to that same protected path, and Pi-hole reported live API health with its blocking probe passing over both UDP and TCP. A fresh Codex app-server and native OpenCode both returned a request-only DHCP proposal with the exact pinned router, before and after bounds, a digest and a five-minute expiry. The isolated local approval gate rejected a mismatched digest, target and router state, as well as expired and replayed approvals. Concurrent attempts admitted exactly one request, and reopening the ledger did not permit replay. The router read back the same DHCP bounds afterward. The MCP exposes no live write operation and a live executor would still require a separately authorized exact change and verified readback.

### LAN ban state and handoff

- Publish only decisions from the verified Seerr login jail. Give each decision a stable event ID and use the observed event time to set an absolute expiry. A retry keeps the same ID and expiry. Expired events are ignored, and an unban must name the ban it revokes so a delayed unban cannot clear a newer decision.
- Make changes with the ConfigMap resource version. On conflict, reread and reevaluate the event against the current record. Store a bounded set of event IDs and revocation records through the permitted event lifetime so delayed duplicates cannot reinstate a revoked ban. Treat unavailable or malformed state as a read failure. Worker rules retain their last accepted absolute expiry and expire locally.
- Ansible staged the root-owned client and inactive reader timer on both ingress workers. The installed digests match the source. The Linux peer credential check rejected a mismatched broker and the reader rejected publisher requests. Charts revision `084e259814d8` adds role-separated socket brokers with rotating projected credentials and pins the staged script digest. The first DaemonSet rollout exposed a missing daemon startup import. The timers remained disabled. A filesystem socket test exercised actual daemon startup, a successful request from host root and rejection of a non-root peer. Ansible staged the correction on both workers, and charts revision `a9e28e800752` pins the corrected source. Flux applied the corrected revision and both publisher Pods and both reader Pods became Ready. Both host-root clients reached their dedicated reader sockets. The actual systemd reader units synchronized the journal on both workers. Two publisher sockets accepted the same synthetic ticket without a second resource version change. A one-minute ban dropped the same synthetic source before and after MetalLB handed the floating HTTPS address to the peer in 1.47 seconds. Unrelated trusted HTTPS returned 200. The entries expired on both workers and a later synthetic packet left both counters unchanged. Both test tables were removed, the shared journal was empty, and both Traefik replicas were Ready. Ansible activated the dedicated Seerr LAN jail and reader timer serially on both ingress workers while verifying the existing SSH jail. Fail2Ban 0.11 required the scoped reload to allow initial creation. The watcher attached a replacement Traefik Pod log after eviction. Five real invalid login requests from an isolated LAN client returned HTTP 403 and produced an automatic shared ban. Both firewalls applied it. That client timed out before TLS, unrelated trusted HTTPS returned 200, and revoking the precise ticket restored the client. The temporary network and test ticket were removed and both Traefik replicas recovered. The reader timers and dedicated jail remain enabled. The jail uses five failures in 60 seconds and a 300-second ban. The rule targets only floating LAN HTTPS. Cloudflare security-event attribution and public enforcement remain separate.
- Exercise duplicates, stale revocations, API loss and expiry, then publish one timed test ban and verify both workers enforce it before moving the floating address. Confirm the same test source is blocked after handoff, an unrelated HTTPS client remains reachable, and withdrawing the candidate removes the owned rules from both hosts.

## Checkout consolidation

BORTUS integrated the current application work in its retained checkout. Recovery refs and metadata preserve six historical BORTUS checkouts. The original registered owner used the supported reattachment control to bind its chat to the retained BORTUS checkout. A fresh turn verified the valid path. The archive error then changed from an unverifiable primary checkout to another active task using each of five individually checked candidates. This migration chat also listed all five as attachments. The initial archive response did not identify the tasks holding the references. The documented App Server API identified the shared attachments and let the migration chat unlink them without changing checkout files. Unarchiving the registered owner also unarchived seven inactive audit children that had inherited the same links. All 28 inherited link payloads are recoverable from a local Git ref. Once only the registered owner remained attached, Codex archived all four historical BORTUS checkouts. The archive records and original recovery refs were verified, and Git no longer lists any of those paths. Together with the archived cluster headroom checkout, this reduced the count from eight to three. The only extra checkout is the separately protected antivirus source.

The separate antivirus checkout is clean and its HEAD and all eight Git metadata files match the existing recovery refs. The cluster malware assessment owns this checkout. Its completion receipt explicitly retains the checkout and published refs for review and ongoing maintenance. The retained homelab repo can recover the exact deployed runner and its maintenance runbook directly from the preserved Git ref. All three installed runner hashes match that source. Retiring the physical checkout requires the owner to release its retention and verify inactivity, including the 72-hour minimum for older agent-owned copies. The observed age was under 40 hours. The migration chat continues to use its authoritative homelab path explicitly.

The historical BORTUS account-worker evaluation checkout was clean, inactive, and had no Codex owner marker. BORTUS confirmed its commit is already in the retained application history. The recovery archive matched all nine metadata files. Standard Git worktree removal retired that exact checkout and preserved its branch and recovery archive. The live count dropped from nine to eight, with two designated destinations.

The former cluster headroom checkout has 28 modified or untracked files. The source recovery ref matches all 28 files byte for byte. A separate local recovery ref preserves all nine ordinary Git metadata files, including its index and HEAD reflog. The migration chat is the registered owner. The Veyra runbook and 19 supporting files now live in the retained homelab checkout. Only the runbook command changed to resolve the script from the current repo, and that command launched the runner help successfully. No Windows process or WSL process or mount referenced the former checkout in the preflight. Codex initially refused the archive because two completed read-only audit tasks still held attachments. The documented App Server attachment API identified and unlinked those references. Codex then archived the exact checkout, and Git no longer lists it. The independent source and metadata recovery refs are still present.

The latest check found the retained BORTUS path empty and absent from Git
worktree registration. Archiving the original registered chat triggered
automatic cleanup of its primary BORTUS checkout. BORTUS verified the exact
Codex snapshot, its parent, all 42 expected changed paths and the qualified
application changes. The original owner is unarchived and found the exact
archive attachment. Codex refused its restore because removal was
interrupted, despite the old directory being empty. The verified snapshot
now also has an independent local Git ref.

The BORTUS chat used Codex's managed worktree creation control to recover
the exact verified snapshot at a fresh path. The recovered checkout is
clean, and the chat's attachment and working directory both point to it.
All 42 snapshot paths were verified, including the 29 original protected
files and the 13 integrated receipts. Original file hashes remain
recoverable where Git applied Windows line endings. The interrupted
archive is intact. Three physical checkouts remain: the homelab, the
recovered BORTUS checkout and the separately protected antivirus source.

The original checkout creation record places the antivirus assessment and
its manually created Git worktree in the Swarm Migration chat. There is no
separate registered Codex worktree owner to contact. A fresh check verified
the clean source and all eight per-worktree metadata files byte for byte
against the retained refs. The latest observed write was November 6 at
18:38:40 UTC, placing the earliest 72-hour review on November 9 at
18:38:40 UTC. Recheck active references and the recorded retention before
retiring the exact checkout.

The pre-retirement check found 1,077 tracked paths and no modified,
untracked or ignored files. The checkout HEAD still matches the retained
source and published ref. The check found no references in Windows process
arguments or scheduled tasks, or in the inspected WSL user processes,
working directories and open files. These observations precede the
retention deadline and must be refreshed at retirement.

## Current checks for remaining work

- The router read back the approved DHCP bounds. Windows still receives a
  24-hour lease with the router as its only DNS server. Three read-only
  DHCP Leasequery probes for that same client returned no matching response.
  The connected-device list and the single observed lease cannot establish
  an allocation-safe range for offline clients. No DHCP settings changed.
- The authenticated XR500 dashboard reported firmware 2.3.3.136. The
  vendor's source archive for that build returned 404. Read-only extraction
  of the matching official firmware image showed that its LAN udhcpd
  configuration reads the lease duration from the router's `lan_lease`
  setting and records active leases in a runtime file. Neither the protected
  LAN page nor the vendor manual exposed that lease table.
- A one-packet DHCPDISCOVER requested the maximum lease duration. The live
  router offered 86,400 seconds and only its own DNS address. No DHCPREQUEST
  was sent. This corroborates a 24-hour current duration for ordinary
  clients. The setting is configurable in firmware, so the offer does not
  establish past lease settings or prove that offline addresses are free.
- NETGEAR identifies XR500 firmware 2.3.5.152 as the fix for CVE-2026-9215.
  The vendor image is reachable. The Codex browser rejected the installed
  router certificate with a key-usage error. The pinned read-only MCP
  transport remained available. No firmware or settings were changed.
- Live systemd-networkd leases on all three Kubernetes hosts were issued
  by the router for 86,400 seconds. Each node's LAN interface matched its
  current router reservation. This includes the host of the independent DNS
  resolver. A live DHCP handoff must preserve the node addresses and all
  five router reservations. Prove that the replacement DHCP host can start
  and serve on its expected address with the router's DHCP disabled before
  relying on it to renew its own node lease. These four sampled leases
  (three nodes and Windows) still do not establish the lease history of
  offline clients.
- The independent resolver is enabled and waits for network-online and
  containerd at boot. Its LAN IPv4 address originally came from DHCP. An
  isolated Netplan generation check rendered a static candidate preserving
  the current interface, address, subnet, gateway, route metric and DNS.
  The generated networkd file had no IPv4 DHCP enabled. This was an offline
  syntax and render check. A follow-up copied all existing Netplan
  layers into a temporary RAM-backed directory on the resolver node and
  rendered both the existing config and the merged candidate with the
  node's Netplan. The candidate retained the current address, DNS, gateway,
  route metric, link-local setting and IPv6 router-advertisement setting.
  It removed IPv4 DHCP from the generated networkd file. The copied
  configuration and generated files were removed after the check.
  The repeatable Ansible host-address playbook staged the overlay outside
  active Netplan configuration. The resolver host then accepted the overlay
  through Netplan's timed trial after independent SSH, TCP and UDP DNS,
  and the shared Kubernetes API all passed. The static address and default
  route match the previous DHCP assignment. Netplan persisted the overlay
  alongside the unchanged installer file. The staged input was removed.
  Both resolvers passed direct TCP and UDP queries and recursion afterward.
  The Pi-hole admin route returned its expected redirect and all three nodes
  stayed Ready. The follow-up reboot retained the address, route and new
  boot ID on Node Three. Before reboot, a temporary DNS-only EndpointSlice
  let the standby serve the legacy router path while the primary Pi-hole
  moved to Node Two. That move recorded no failed DNS checks. Across 51
  reboot monitor samples, router DNS, floating DNS and the shared API had
  no failures. The standalone resolver reached its static address and
  passed UDP, TCP, upstream DNS and the admin redirect after startup.
  The first start raced the creation of the containerd socket and the
  unit's own retry recovered. The Ansible unit now waits for the runtime
  API before starting. The installed unit passed a controlled restart
  with zero retries. The exact temporary EndpointSlice was removed and
  Node Three was uncordoned. The primary and standby DNS Pods remain
  spread across two nodes. All 29 attached Longhorn volumes returned to
  healthy after the reboot. The router's DHCP handoff is still separate.
- From the Windows LAN client, the floating and standalone resolvers each
  matched all 48 records in the immutable, shared chart record map over both
  UDP and TCP. This qualifies the live record sets on both DNS paths. It
  does not establish what the router will advertise after a DHCP cutover.

- The read-only `lan-dhcp-preflight.yml` passed against production with
  five tasks and zero changes. The replacement host has the expected static
  address and no IPv4 DHCP listener. Its installed dnsmasq parsed both DNS
  addresses as DHCP option 6 with a documentation-only range, and a second
  node got the expected local record from each resolver over UDP and TCP.
  The XR500 still advertises its own address. Its current event log had
  no DHCP entries and did not resolve the lease or nonoverlap requirement.

- The XR500 diagnostics page has no lease-table export control. Its built-in
  Save Debug Log operation returned a two-member archive with no separately
  named DHCP or lease file. The archive was inspected in memory and was
  not written to disk. Both capture switches were off before and after
  the export, and the DHCP pool read-back matched the approved range.
  A bounded follow-up checked both members for DHCP and lease fields
  without printing the contents. One member was binary and the other
  was text-like. Neither exposed recognizable DHCP records or usable
  address, client identifier and expiration tuples. The export therefore
  does not qualify lease migration.

- The XR500 Device Manager returned 43 device records and 19 online
  interfaces through its authenticated inventory calls. It supplied no
  lease expirations or DHCP client identifiers. Eight distinct current LAN
  IPv4 addresses were visible. None fell in the proposed upper allocation
  block, and none of the five router reservations used that block.
  The candidate stages a lower router pool end, then holds the upper block
  unused until a verified maximum duration for existing leases has elapsed.
  This inventory helps select the candidate but cannot clear offline leases
  or prove that an address was never assigned statically. The router has
  the previously approved pool end during the first save attempts. The
  authorized change was subsequently made through LAN Setup in the Codex
  browser over HTTP. Two independent reads confirmed the new pool end and
  the router's LAN page confirmed DHCP was still enabled. Use November 9
  at 10:46:46 a.m. Toronto time as the conservative start of lease drainage.
  Ordinary leases are 24 hours. November 10 at 10:46:46 a.m. is the earliest
  review, pending verification of historical leases and static addresses in
  the candidate block. The replacement host has no DHCP listener. Both
  replacement DNS resolvers answered on UDP and TCP from Windows.
  A same-day check found one stale neighbor entry in the candidate block.
  Probes from two nodes did not receive an answer or resolve its address
  again. The router event log did not provide a corresponding lease record.
  This leaves the address unverified for reuse while old leases can persist.

- For the candidate handoff, compared all five reservations against the
  three live Kubernetes interfaces, the Windows LAN adapter and the NAS
  neighbor entry. All matched and lie outside the candidate range. The
  replacement host's installed dnsmasq accepted the full candidate in
  test mode, including the five fixed reservations and both DNS resolvers.
  The reservation data was passed in memory. The initial router change
  would lower its pool end from .250 to .199 and leave it serving DHCP.
  Keep the replacement DHCP listener off until the upper range is cleared
  of existing leases and static assignments. Restoring the prior pool end
  is the rollback for this initial step.
- The Ansible standalone DNS cutover playbook now has a read-only
  `dns_lan_action=verify` mode for the live split. It checks the DNS and
  admin Service routes, answers on TCP and UDP, and the active and enabled
  state of the host resolver. The production verification reported nine
  tasks passed, zero changed, and zero failed.

- The signed-in Cloudflare dashboard provided live Security Events for the
  public zone. A controlled request to the path blocked by an existing
  custom rule returned HTTP 403. The event matched the exact Ray ID,
  independently observed client IP, host, path and timestamp. The event
  recorded the custom rule and Block action. No new public rule was enabled.
  The stored API credentials did not provide a working Analytics API path.
  The live zone is on Cloudflare Free. The signed-in rate-limit editor
  offered URI path and verified-bot fields, with IP as its counting key.
  It did not offer hostname or origin response status. A path-only rule
  would count successful and failed requests for that path zone-wide.
  The existing public rule remains in place. The Web Assets inventory
  accepted the exact Seerr POST operation. Its host returned Seerr 3.5.1
  through Cloudflare. The rate-limit editor accepted the operation ID as
  input, but server-side validation rejected the field as requiring
  Advanced Rate Limiting. The successful Free-plan configuration uses
  a custom rule scoped to the two case-normalized login paths to exclude
  other hostnames and methods from only the rate-limit phase. The zone had
  no other rate limits. Its single active rate rule counts all matching
  public Seerr POST requests by IP. It blocks after 10 requests in 10
  seconds for 10 seconds. Both the canonical and trailing-slash paths match,
  regardless of case. Existing WAF custom and managed rules are outside
  the exclusion. This burst guard counts successful requests as well as
  failures. It is separate from the failed-login-only LAN jail.
  An unauthenticated burst returned 11 HTTP 400 responses and five HTTP 429
  responses. A same-path POST burst on another public host and same-path
  GETs on Seerr retained their baseline responses. Seerr status remained
  HTTP 200 during mitigation. After 12 seconds an empty canonical login
  returned HTTP 400 again. The first sampled Security Events lookup did
  not show the exact rate-limit Ray. The earlier public-attribution check
  remains verified against a separate existing Cloudflare block.
  To roll back, disable the rate rule first, then disable its scope rule.
  Revisit the scope rule before adding other rate limiting for those paths.
- Both Pi-hole replicas had the same prior app-password hash and no active
  app sessions at preflight. The app password was rotated on both replicas.
  The new credential and rollback hashes are in native Kubernetes Secrets.
  The private MCP credential file was updated. The live MCP read blocking
  state and local records, and each replica refused an administrative
  update from the app session. The normal stdio launcher passed health,
  blocking and record calls. App sudo stays disabled. This rotation
  replaced the previous app password.
- The dedicated Seerr local account now exists. Its native Kubernetes
  credential was verified, normal sign-in returned only the request
  permission, and the same session received HTTP 403 for administrator
  settings. All six original account records matched their preflight
  metadata. No welcome email or media request was sent. The live submission
  gate now requires the exact operator-authorized title and proposal digest.
  The operator-only executor can read the dedicated native credential through
  a separate pipe, after validating the approval digest. The live pipe and
  request-only session worked. The MCP registration remains read-only.
- The antivirus source worktree remains protected by its owner and retention
  policy. Its recovery source is accessible from the migration checkout.
  The complete scan campaign and its limits are recorded in the security
  notes. No checkout was removed in these checks.

## Rollout checklist

- [x] **Phase 1, LAN.** The isolated test Service verified real client IPs on both nodes with endpoints, expected behavior on the third node and continuity of the existing routes. The Service was removed. The live Seerr LAN ban and recovery checks passed.
- [x] **Phase 1, public attribution.** Correlated the exact Cloudflare event to the controlled request and verified the existing edge rule blocked it.
- [x] **Phase 1, additional public enforcement.** Deployed and verified the public Seerr login burst limit, scope controls and recovery.
- [x] **Phase 2, recovery.** The isolated encrypted snapshot restore passed API decryption and stale-watch relisting. Two restored etcd members kept serving after the third stopped.
- [x] **Phase 2, cluster rollout.** All three renamed control-plane nodes are Ready. The shared API passed TLS and failover checks, Longhorn restored all attached volumes to healthy, and floating HTTPS, DNS and Plex passed their handoff checks. The standalone DNS resolver is live.
- [x] **Phase 2, DHCP.** Completed the operator-approved split-range handoff with the unresolved address excluded. A fresh Windows lease from the replacement preserved its reservation/gateway and advertised both resolvers; direct client queries to both and normal DNS succeeded.
- [x] **Phase 3, read-only tools.** Live Kubernetes inventory and the required permission denials passed. Both Codex and OpenCode exercised the private MCP adapters.
- [x] **Phase 3, Pi-hole.** Verified authenticated blocking and record reads plus administrative write denial on both replicas.
- [x] **Phase 3, Seerr acceptance.** The operator chose the movie under delegated authority, submitted one standard request through the dedicated request-only account, and verified its pending status and ownership. A separate read-only query confirmed the same request in the live queue.
- [x] **Phase 3, checkout retirement.** Retired the clean antivirus checkout after the retention period and fresh inactivity checks. Its source and all eight Git metadata files match retained recovery refs. Two Git worktrees remain: Swarm and BORTUS.

This tracked plan uses role-based names. Operational identifiers, local evidence and credentials belong outside the tracked plan.

### Scheduled DHCP recheck, November 13, 2026

- The Windows client has a current 24-hour lease from the router and still
  receives only the router as its DNS server. The router remains the DHCP
  server; no replacement listener was started.
- Both planned LAN resolvers answered the expected API name over UDP and TCP
  from another cluster node. The replacement host retains its static address,
  both independent resolver services are active and enabled, and no IPv4 DHCP
  listener was present. Queries originating on the resolver host itself do
  not exercise its inbound-only DNS redirect; cross-node checks passed.
- The router connector and Pi-hole connector returned `Transport closed`.
  Opening the router over HTTP in the Codex in-app browser failed with
  `ERR_INVALID_AUTH_CREDENTIALS`. The saved pool end, current reservations,
  complete lease history and static assignments could not be reverified.
  The previously noted stale neighbor remained unresolved, which does not
  establish that an offline device has released its address.
- No cutover was performed: the candidate range remains unqualified. Router
  settings, DHCP service and client leases were left unchanged. The one-time
  scheduled recheck has concluded with the handoff incomplete; automatic
  retries were removed. Resume from authenticated router and allocation
  evidence rather than treating elapsed time or silent probes as clearance.

### Resumed rollout checkpoint

- The router connector authenticated again and read back the approved reduced
  pool. The Codex browser also opened LAN Setup over HTTP, confirming the pool,
  enabled router DHCP and all five existing reservations outside the candidate
  range. This resolves the earlier access failure without changing DHCP service.
  A fresh bounded probe received no ICMP or resolved neighbor replies from the
  51 candidate addresses. That does not clear offline static devices. The router's
  offline-device view did not supply an address or lease expiry for the sampled
  offline device, so it cannot qualify the allocation history. The replacement
  host still has no DHCP listener.
- The final antivirus checkout passed a fresh clean/untracked/ignored check,
  source comparison, comparison of all eight metadata files, and Windows and
  WSL process-reference checks. Its last source write was more than seven days
  old. Normal Git worktree removal succeeded without force. The two retained
  source and metadata refs remain available; scan reports and operational data
  were outside the removed checkout. Git now lists exactly two worktrees.
- Initialized the missing portable repository-memory starter files through the
  shared coordinator helper. Existing source and notes were preserved; the local
  OpenCode configuration now includes the repository memory index.
- DHCP remains the unfinished rollout item. Retain the router until historical
  allocations and static assignments in the candidate range are qualified and
  a normal replacement lease has demonstrated both DNS resolvers.
- The follow-up inspected Device Manager's table view, which lists current
  addresses but has no lease-expiry or static-assignment column; visible offline
  entries report no address. The original unresolved-neighbor observation was
  also reviewed: its retained output redacts the hardware address and records
  no lease identity. It therefore cannot identify that device or qualify reuse.
  The router view was restored and no network settings were changed. This is an
  allocation-evidence limitation, not a missing approval or router-login issue.
- The same missing allocation evidence remained across three consecutive goal
  turns. The rollout goal is blocked with only DHCP handoff unchecked. Resuming
  requires a verified lease/static-address record or the network owner's factual
  confirmation resolving the candidate range and the formerly observed device.
  Existing rollout approval remains valid. Keep router DHCP enabled and the
  replacement listener off until that evidence is available.

### DHCP handoff completed — November 14, 2026

The operator explicitly approved excluding `.246` and using the remaining
freed addresses. This supersedes the earlier allocation-evidence blocker for
that address. The live DHCP-only service uses `.200–.245` and `.247–.250`;
neither range nor any fixed reservation allocates `.246`.

- The router's DHCP service was disabled before the replacement was started.
  Its name, LAN address, subnet, saved pool and five reservations matched the
  pre-change snapshot. The replacement copied those five reservations and
  retained the router as the default gateway. No DNS listener or chart was
  changed.
- The initial replacement start exposed a PID file outside its systemd writable
  paths. It was stopped and disabled, the absence of a DHCP listener was checked,
  and router DHCP was restored and read back. Ansible now keeps the PID file
  beside the protected lease file and stops failed activations automatically.
  After correction, the serial handoff was repeated successfully. The final
  replacement is enabled at boot, running and has zero restarts.
- A real Windows client released and reacquired its lease. It reports the
  replacement DHCP server, the original reservation and gateway, and both LAN
  DNS resolvers. Direct UDP exchanges reached each resolver, TCP queries returned
  the expected API address, and normal Windows DNS resolved the LAN ingress.
  Trusted Homepage HTTPS and internet HTTPS both returned HTTP 200.
- The router browser's blocking save notice stalled the browser tool. The scoped
  operator helper used the existing authenticated firmware form, preserving its
  dynamically generated device-name field, then waited for the apply job before
  reading back the result. It exposes no MCP write tool. Both activation and
  rollback wrappers check that the other DHCP server is stopped first.
- Repeatable source is in `playbooks/lan-dhcp-handoff.yml` under the Ansible
  directory, its template and unit, and the three scoped scripts under
  `scripts/migration/`. The Ansible README documents operation and rollback.
  The existing DNS chart already advertises the same service addresses; no chart
  change is needed for this host-level DHCP handoff.
- Final cluster checks found three Ready nodes, all 29 attached Longhorn volumes
  healthy, and all three deployed Flux Kustomizations Ready. Two source worktrees
  remain. All rollout checklist items are complete. These local source and plan
  edits have not been committed or pushed; unrelated work remains untouched.

The old blocked observations above remain as history. The current rollout state
is complete. The router DHCP configuration remains available for rollback.


## BORTUS release checkpoint, 2026-11-14

Saved node credentials are resolved and validated on all three nodes. The qualified image is privately published and preloaded; 42 live guard cases, fresh separate-volume recovery with whole-row equality, and candidate schema/account-row preservation passed. Temporary rehearsal Pods are absent. Production remains the original Ready image; actual attended screen-reader acceptance is still unverified before the final controlled application rollout. See [current BORTUS evidence and remaining sequence](BORTUS-INDEPENDENT-RESTORE.md#current-bortus-release-progress-2026-11-14). No further deployment approval is needed.


## Final release preparation, 2026-11-15

James reported the attended NVDA announcement Configuration saved. on November15; actual-reader-acceptance-20261115.json records the direct human observation against the unchanged qualified image. Final BORTUS-only production execution is authorized. Veyra acknowledged a quiet shared chart-publication window while retaining independent Ingenium ownership. The previous screen-reader requirement is satisfied; production promotion and final acceptance are in progress, followed by exact local review container/image cleanup.

## BORTUS delivery completed, 2026-11-15

The authorized release is deployed and verified: source `34b8fa18…`, private image `e7539b9e…`, charts/Flux revision `1580091e…`. Real authentication, RBAC, native history/access/CAS/rollback, database preservation, restart persistence and trusted LAN HTTPS passed. Native values were verified absent from SQLite; test data and all four local review containers/images were removed. Scoped generated-file cleanup removed 12,826,632,192 allocated Linux bytes while preserving original source capsules, unique failure evidence, small lossless regeneration recipes and encrypted recovery points. Existing unrelated source and the protected older CI stage remain intact. The inherited BORTUS delivery goal is complete; see [the completed release record](operations/handoffs/current-bortus.md#completed-production-release-2026-11-15) for exact identities and retained exceptions. No subagents or desktop Computer Use were used.
