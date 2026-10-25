# CoreDNS security patch — October 25

Both existing CoreDNS replicas now run the reviewed image
`docker.io/library/coredns-security-20261023@sha256:014e9ae348d5dcf3ed5451a5490a29bb6e51477f5b3291e31804c74fe6b557d9`.
The original deployment UID, replica count, pod configuration, Corefile and DNS
Service are preserved. Only the deployment's container image was patched.

The application source is official CoreDNS 1.14.7, commit
`427fc80ed9ca47f354585eb30a3f1332950856c4`; all Go/config source files and plugins
are checked unchanged. The image uses Go 1.26.10 and patched compatible modules.
The final image retains the upstream numeric identity and file capability.

Fresh exact OCI scan: zero Critical, High, Medium or Low rows; three Unknown
rows remain. Two are tzdata advisory metadata, and one is the unmaintained
OpenPGP module warning. No ignore file, analyzer exclusion or suppression was used.
This is not proof that undisclosed vulnerabilities do not exist.

| Evidence | SHA-256 |
|---|---|
| Original OCI archive | `c499e924e0f59a95ef79326bb8014e1a143f25fad8db25684342d115e77500bf` |
| Sealed local provenance | `4e54bfb4ca8527fdd530d5fe3712194f145a59ff0d780962fd9d50ca0b89dc0d` |
| Fresh scan status | `a15ed053ec7b5b02ceda42de1c23d4d1f432bcacdf2f1a7ad76ed6589befc740` |
| Full Results-only scan | `9f986bf38857a6efb59d1dfd0891dd6fd369ca23b5b4e863b45625cc284448d4` |
| Final live qualification | `94f2fbfa3b29175b3bafbf5228b54fb496f1c3db0d3779d146a377c614014abd` |

The image was imported and verified on all three nodes through the existing
cache-only Ansible role. `playbooks/coredns-patch.yml` then applied the image to
the original kubeadm-owned deployment; it is not a Flux HelmRelease. Final
checks passed 18 real UDP/TCP lookups through the Service and both Pod addresses,
covering cluster Services and external forwarding, plus four health/readiness
HTTP checks. Both new Pods are Ready with zero restarts.

The first post-rollout observer saw terminating old Pods and refused its
two-Pod-count assertion. That failed receipt is retained, SHA
`769dabb61ee9ca6c26c713cbc3144a1f7c5f56b36d42196a946f4d38eabef59a`.
The idempotent observer then passed after termination finished. Comparing the
retained original and final deployment specifications independently confirmed
that only the image changed, and the original Corefile bytes/UID matched.
The current controller waits briefly for terminating Pods before that assertion.

Defaults/check mode perform no mutation. Explicit execution requires the exact
completed private scan receipt and SHA, fresh database, full original artifact
hash and original deployment UID. Receipts and backups remain in the protected
operator runtime, outside Git. The old image and original configuration remain
available for an identity-checked image rollback.
