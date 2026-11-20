---
name: kubernetes-repo-audit
description: Use when asked to audit this cluster and repository for security, reliability, drift, or supply-chain problems, or to prepare an implementation-ready remediation plan. Read-only by default.
---

# Kubernetes and repository audit

Produce an evidence-based audit of the repository and the live cluster it
deploys, without changing either. This skill encodes the review contract; the
scope and target are given by the current request.

## Non-negotiable rules

1. **Read-only.** No deploys, restarts, drains, deletes, upgrades, reconciles,
   credential rotations, firewall changes, CI changes, commits or pushes.
   Proposed patches are written to `docs/audits/<date>/proposed/` and left
   unapplied.
2. **No secret payloads.** Never read Secret `data`/`stringData` values,
   tokens, keys, kubeconfigs or credentials in source. Report location and
   exposure, not the value.
3. **Bounded checks.** No scanners deployed into the cluster, no debug
   containers, no `exec` into workloads under audit, no exploitation or stress
   testing. Small log and event samples with an explicit time window only.
4. **Explicit context.** Select the kubeconfig/context per command and record
   it. If the intended cluster is ambiguous, ask one focused question.
5. **Evidence over narrative.** Documentation is a claim to verify, not proof.
   Separate confirmed, likely, unverified and not-applicable.

## Phases

1. **Establish reality.** Record repo URL, default branch, exact commit,
   working-tree state, and the cluster identity/context. Note access limits and
   observation timestamps. Discover versions, nodes, runtimes, control-plane
   and etcd topology, CNI, ingress, DNS, storage, certificates, monitoring and
   backup components from the cluster itself.
2. **Map source to runtime.** For each significant workload: namespace, kind,
   name, owning controller, image reference and digest, source file or chart,
   GitOps/Helm revision, and desired vs observed revision. Flag unexplained
   drift, mutable tags, resources with no source, and suspended reconciliation.
3. **Security review.** API server, kubelet and etcd exposure; RBAC breadth and
   escalation paths; service accounts and token mounts; workload isolation and
   Pod Security; ingress/TLS/authentication boundaries; NetworkPolicy presence
   versus enforcement evidence; secret flow and encryption at rest; application
   auth, input handling and logging; build/deploy supply chain.
4. **Vulnerability review.** Compare observed versions and digests against
   authoritative advisories (Kubernetes CVE feed, upstream projects, vendor
   packaging). State whether the vulnerable feature is present. Never equate a
   scanner alert with exploitability, and never dismiss a finding because a
   service is internal. Record scanner version and database age when used.
5. **Reliability and performance.** Quorum and failure domains, replica
   placement, probes, restarts/OOM/evictions, requests and limits, storage
   capacity and reclaim, certificate renewal, DNS and registry dependencies,
   backup scope and restore evidence, upgrade and rollback paths, and circular
   recovery dependencies.

## Finding format

Every material finding records: ID and title; severity, priority and
confidence with justification; affected resources and repo paths (file:line at
the reviewed commit); sanitized evidence with timestamp and command; impact and
prerequisites; concrete remediation naming the authoritative source file;
validation checks with expected outcomes; and change risk with rollback.
Deduplicate related alerts into root causes while still listing affected
resources.

## Deliverable order

A. Executive assessment (security, availability, performance separated).
B. Environment and deployment map, with ownership gaps and drift marked.
C. Prioritized findings table, then detailed findings.
D. Ordered remediation plan with dependencies, validation, rollback and
   maintenance-window need, plus reviewable proposed diffs kept separate.
E. Coverage and unresolved checks, including what access would close each gap.
F. Executor handoff for a separate agent working through the repository flow.

Write sanitized reports and patches under `docs/audits/<YYYY-MM-DD>/`. Follow
the repository's existing documentation conventions and never overwrite prior
audits.
