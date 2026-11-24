---
{"version":1,"scope":"repo","owner":"opencode-memory","id":"tls-and-workload-scope","title":"TLS naming and workload authentication scope","tags":["tls","mtls","network","scope"],"kind":"decision","updated":"2026-11-15","verified":"2026-11-15","sources":["docs/MIGRATION-PLAN.md","docs/operations/handoffs/opencode-takeover.md"]}
---

James requires free/self-hosted components and direct execution without subagents.
On November 15 he chose to keep current service names rather than introduce
`home.jtmb.cc`, and to secure this Kubernetes cluster for now rather than federate
with another cluster.

Retain the existing private-CA trust for `.lan` services, separate Kubernetes-CA
trust for API access, and existing public-domain routes. Public ACME certificates
cannot cover `.lan`. Workload mTLS is a separate rollout; these naming decisions
do not prove mesh deployment or grant permission to weaken existing controls.
Current implementation and acceptance status belong in the migration plan.
