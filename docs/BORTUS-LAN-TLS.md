# BORTUS LAN TLS while application delivery is held

The charts foundation owns `bortus/bortus-lan-tls`, a separate Ingress for
`bortus.branconet.lan` on Traefik `websecure`. It references the existing
cert-manager Secret `branconet-local-ingress-tls` and routes `/` to `bortus:4000`.
Priority 1000 wins over the existing identical Helm HTTPS route's implicit
rule-length priority. The Helm-owned HTTP route remains on `web`; the separate
redirect described below is pending publication and runtime acceptance.

Publish through the existing charts main -> local full validation -> validated
-> `migration-releases` pipeline. Do not resume the BORTUS HelmRelease to apply
this infrastructure repair. Its chart already references the same TLS Secret
for future authorized reconciliation. Do not patch or adopt either Helm-owned
Ingress. No application, image, principal, storage or Secret value changes are
part of this repair.

After Flux observes the validated revision, run the existing
`k8s-rewrite/ansible-playbook/playbooks/lan-tls.yml` with
`lan_tls_verify_bortus_https=true` and the existing task-owned
`lan_tls_output_dir`. Keep `lan_tls_apply=false` and
`lan_tls_install_windows_trust=false` for verification only. This opt-in checks
the foundation ownership, exact route, held release, cert-manager leaf and
verified TLS/SNI on node addresses 192.168.0.4, .5 and .6. It verifies a public
HTTP response without authentication or following redirects; this is transport
acceptance, not authenticated application or KV delivery acceptance.

The verifier uses the public native root certificate in memory; it never reads
private keys or disables TLS validation. Existing normal client trust remains a
separate client-side acceptance check. Repeated verification is read-only;
configuration reconciliation stays with the existing publisher and Flux.

With `prune:false`, removing the foundation file alone does not delete a live
Ingress. Any later route retirement requires an explicit reviewed ownership and
deletion plan after the held application release's separate acceptance gates.

The strict shared verifier found Ingenium's leaf had no explicit serverAuth EKU. Its chart now requests that usage. Opt-in `lan_tls_renew_missing_leaf_usage=true` requests normal cert-manager status renewal only for this exact reviewed existing leaf when the extension is absent; it preserves the Certificate spec and TLS Secret UID, then verifies the renewed signature and usage. The CA/root trust stays unchanged. The follow-up launcher enables this bounded repair. After renewal, repeated calls make no change.

## HTTP redirect enforcement — deployed and verified

The foundation resource `flux/releases/foundation/bortus-lan-http-redirect.yaml`
retains a separate Ingress, `bortus/bortus-lan-http-redirect`, matching
`bortus.branconet.lan` and `/` on entrypoint `web`, priority 1000. It now references
`bortus-lan-https-redirect@file` and the existing backend `bortus:4000`.
The original Kubernetes Middleware candidate was unsupported by the installed
provider setup; its failed reconciliation receipts remain preserved. This repair
does not add a CRD/provider or change the Traefik Deployment.

The existing watched `/etc/traefik/dynamic` directory mounts the entire native
`traefik/traefik-dashboard-config` Secret. Separate opt-in helper
`reconcile-bortus-http-redirect.py --apply` inserts only the public data key
`bortus-https-redirect.yaml`: HTTP middleware `bortus-lan-https-redirect`,
redirectScheme `https`, permanent true. Existing private values are read only in
RAM, never logged, persisted or passed as command arguments. UID/resourceVersion
tests protect the single-key JSON patch; readback preserves all other values,
type, labels and owners. A conflicting key is refused, while an identical key
returns changed false. Exact file-watch flags/mount and held BORTUS are checked.

`lan_tls_apply_bortus_http_redirect` defaults false and is separate from CA/trust
operations. The final hardening launcher explicitly enables it and the public
HTTP verifier. The verifier reads only the public key using a go-template,
checks the foundation Ingress and held release, and never follows redirects.
Secret values/resources remain outside Git. The existing Helm routes and
`websecure` TLS Ingress remain unchanged.

The original observation of HTTP 200 at 07:07:52 UTC remains a pre-repair
failure. The first Middleware-CRD publication at `8111a20b6819ef7d9ef9aa3e45858e65f14f3512`
was rejected by Flux because that CRD is absent; it did not establish enforcement.
The file-provider repair at `1d2ab6fed53a90b1cef497907b707dcd1d137085`
passed the unchanged local validation/promotion flow and actual Flux reconciliation.
`H/tls-file-provider-redirect-final.log` records exit 0 and changed 0 after repair:
all twelve certificate leaves and strict HTTPS/SNI on .4, .5 and .6 pass;
HTTP redirects permanently to HTTPS with the original path and query preserved.
`H/bortus-redirect-chart-and-flux-acceptance.json` binds both publications and
retains the original CRD failure. The application HelmRelease stays suspended;
its image, accounts, Deployment and PVC identities/specifications remain held.
These are transport and redirect results, not authenticated BORTUS feature acceptance.
