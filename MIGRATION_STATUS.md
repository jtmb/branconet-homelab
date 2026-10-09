# Migration acceptance evidence

Contract: [PLAN.md](PLAN.md). Goal active since 2026-10-09 14:30 UTC; execution target before 20:30 UTC. Cluster migration is owned by this chat; BORTUS application development is owned by the separate BORTUS Kubernetes Secrets development chat.

## Current progress

- Approved plan saved with architecture graphs, acceptance contract, migration sequence and report template.
- Migration goal active; source checked out from the inspected k8s-rewrite baseline on codex/kubernetes-migration.
- BORTUS application-development chat requested with an isolated worktree and scoped integration contract.
- Vault unsealed and HTTP-healthy; authenticated metadata inventory completed: 40 current records, 43 values.
- Three hosts inspected; sudo verified; Gluster bricks online, no reported split-brain, pending Plex log healing.
- No application cutovers, data imports or Kubernetes deployment acceptance tests completed yet.

## Acceptance ledger

| Criterion | Status | Evidence / remaining work |
|---|---|---|
| AC1 Three-node Kubernetes | Pending | Hosts inspected; provision and verify all nodes |
| AC2 One CI/CD pipeline | Pending | Repair Flux setup and add repository validation |
| AC3 Complete service coverage | Prepared | Live/source scope in PLAN; create per-service register |
| AC4 Individual charts/values | Pending | Existing resources inventoried; packaging and validation required |
| AC5 Longhorn persistence/recovery | Pending | Prerequisites inspected; storage proof required |
| AC6 SMB preservation/integration | Pending | Existing share/mounts verified; demonstrate target wiring |
| AC7 Native Secrets/BORTUS | In progress | App development delegated; import and live integration pending |
| AC8 Data preservation | Pending | Source locations inventoried; backups/restores/copies required |
| AC9 One Plex service | Prepared | All three configs/libraries inspected; consolidate after backup |
| AC10 Reproducibility/docs | In progress | Plan and report saved; update implementation alongside changes |
| AC11 Retirement approval | Pending | Requires completed evidence and user confirmation |

## Service evidence template

- Service/source container:
- Target chart/release and values:
- Image digest and dependencies:
- Source dataset / destination PVC / media mounts / ownership:
- Secret namespace/name/key references (never values):
- Backup and restoration evidence:
- Consistent final-copy or database verification:
- Functional endpoint/application tests:
- Restart, relocation and rollback tests:
- Status and remaining work:

## Ownership and dependencies

BORTUS changes: native Secrets provider, APIs/UI/lookup/auth, startup synchronization removal, deployable image/runtime, integration documentation and development tests. Migration changes: Ansible, charts/values, Flux, Longhorn, backups/import/cutover and live acceptance. Track BORTUS implementation here by delivery evidence without copying its development transcript.
