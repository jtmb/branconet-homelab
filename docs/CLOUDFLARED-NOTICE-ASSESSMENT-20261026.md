# Cloudflare eMudhra notice: read-only assessment

Assessment time: October26,21:42UTC. James forwarded this notice to the existing
migration chat via the other chat. The forwarded Gmail reference is
`1a17a03455b4f81e`; this assessment did not independently reread the email.
The migration goal was already active. No paused work was resumed and no upgrade,
restart, certificate, credential or TLS-verification setting was changed.

Cloudflare's [official advisory](https://blog.cloudflare.com/emudhra-certificate-compromise/)
reports eight compromised intermediate certificates and no identified active
exploitation on its services. It directs Tunnel users to patched software and
container users to a fixed image deployment. It explicitly cautions against
disabling certificate verification. The forwarded notice specifies2026.10.3 for
Docker/Kubernetes; the [official2026.10.3 release](https://github.com/cloudflare/cloudflared/releases/tag/2026.10.3)
exists. Current public registry metadata resolves its amd64 candidate to:

`docker.io/cloudflare/cloudflared:2026.10.3@sha256:faa8e0a1475f137c910be6025f43c8e4092fdd35461b31e19fd1390657a1ff39`.

That is candidate metadata only. The image was not pulled, executed or deployed.
No existing Tunnel deployment was found to which this change could be applied.
Restarting an old image alone would not establish the fixed version.

| Scope | Authoritative observations | Limit |
| --- | --- | --- |
| Kubernetes |95Pods,54Deployments,7DaemonSets; no StatefulSets/CronJobs/Jobs; main/init/ephemeral container metadata inspected; no cloudflared workload identified|Does not inventory external Cloudflare account connectors|
|192.168.0.4/.5/.6|Strict SSH read-only process, systemd unit/unit-file, dpkg, standard binary/config locations; no connector process/unit/package/binary identified; no process-read permission failures; Docker inactive|Unidentified custom installations outside inspected locations are not proven absent|
|Current Windows host|No matching Cloudflare service, cloudflared process or PATH command; broader cloudflared process-name query also returned none|Not an account-wide inventory or a full disk scan|
|Existing Ubuntu WSL|No matching process/unit/package/binary/config; active Docker was readable and listed no cloudflared container|No other WSL distro or unrelated machine was changed or assumed covered|
|NAS192.168.0.8|Not inspected for Tunnel software|No established NAS administration access in this cluster scope|
|Cloudflare account|No available Tunnel account connector/API session; no local Tunnel configuration/credentials identified|Connected Tunnel versions, hosts, installation methods, image digests and replica counts remain unknown|

The cloudflare-ip-checker application is a separate service; it supplies no
Tunnel connector-version evidence. No unrelated DNS API credential was reused to
claim account/Tunnel access. Native Kubernetes Secret private keys and token
values were not read or returned.

The cluster has48Ingress resources and30distinct declared hostnames. Public
certificate-only reads covered the seven referenced TLS Secrets. Their chains
are Let's Encrypt YR1/YR2 through ISRG; no eMudhra/emSign issuer or subject was
observed. Strict hostname/chain TLS handshakes to all three node IPs produced:

- 21 verified connections covering `jtmb.cc`, `mealie.jtmb.cc`, `media.jtmb.cc`,
  `aplb.jtmb.cc`, `lucinda.jtmb.cc`, `mc.jtmb.cc` and `santos.jtmb.cc`.
- 69 unverified connections for the 23 LAN/local names. Every reported verification
  failure was self-signed-certificate error18; the presented subject was
  `TRAEFIK DEFAULT CERT`. This is the existing trusted-TLS acceptance gap,
  separately from identifying an affected eMudhra chain.

The inspector used `openssl s_client -verify_return_error -verify_hostname ...`.
Verification was never disabled. These observations concern declared cluster
Ingress endpoints; actual Tunnel-origin configuration was not located. A current
valid origin chain does not prove an older client's trust store would reject a
forged certificate. No all-clear for the Cloudflare account or every application
TLS verifier is claimed.

Next step is scoped read-only access to the actual Cloudflare Tunnel connector
inventory and, if applicable, the NAS host. Identify each owning host/runtime,
connector version/digest, replica and origin TLS configuration before proposing
any exact deployment. The notice itself authorizes no upgrade or restart. A later
change must identify its qualified maintained release, rollout/availability plan,
origin trust and applicable host/change authorization; do not guess a deployment
or request approval for an unidentified connector.

Private evidence is under the existing F-backed task root at
`cloudflared-notice-assessment-20261026`: Kubernetes/host/Windows/WSL metadata,
public certificate chain observations, strict live handshakes, exact inspector
sources, candidate registry metadata and `assessment.json`.
`output-reconciliation.json` retains each exact evidence path/hash and its reason.
No build/cache/dependency output was produced, no cleanup target was deleted,
and all earlier protected source/runtime/recovery exceptions remain unchanged.
The full migration goal remains active; GitHub Actions was not enabled or used.

