# Optional FlareSolverr least-privilege acceptance

The existing cluster verifier retains its baseline checks and defaults. Add
`--flare-least-privilege` to require the deployed, Ready Flux chart version
`0.1.3+REVISION_PREFIX` (the exact first 12 characters of the supplied full charts
commit), its Deployment and owned ReplicaSet/Pod security contexts, and actual
process security state. The verifier requires UID/GID 1000, `runAsNonRoot`,
`RuntimeDefault`, no privilege escalation, no added capabilities and drop ALL.
It rejects container overrides of the Pod settings.

The optional mode executes only a read-only Python probe inside the existing
Flare container. It returns selected `/proc/1/status` fields: all four UIDs/GIDs
must be 1000, `CapEff` zero, `NoNewPrivs` 1 and `Seccomp` 2. It verifies the
service-account token path is absent without reading a token. Existing checks
also require automount disabled and no service-account token projection. Pod
UID, container ID, restart count and readiness must remain unchanged across the
observation. No environment, command line, Secret or private config is emitted.

Direct invocation uses the existing controller Python:

```text
python -B scripts/migration/verify-cluster-hardening.py --revision CHARTS_COMMIT --receipt ABSOLUTE_H_RECEIPT.json --flare-least-privilege
```

The TLS runner also accepts `--flare-least-privilege --revision CHARTS_COMMIT
--receipt ABSOLUTE_H_RECEIPT.json`; it runs its existing TLS checks first, then
the full cluster verifier with the optional checks. With no new arguments its
behavior remains unchanged. Receipts must be new files directly under the
existing H output leaf. An optional check failure does not emit a passing
cluster receipt.

This verifies configured and effective process restrictions. It does not prove
browser compatibility or patch vendor CVEs. Browser request acceptance remains
a separate post-rollout check owned by the coordinator. Implementation was
checked by parsing only; no live probe or rollout was performed for this change.
