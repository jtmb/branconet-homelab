# Revised delivery objective — user correction October 25

## Existing publication route verified - October 26, 22:47 UTC

Windows Credential Manager holds valid existing Docker Hub credentials for
jtmb92. In-memory authentication confirmed repository pull/push grants for
qbit-monitor, ruckus-bot, ruckus_bot and jtmb-dev. No credential changed or image
was published. This resolves the older route-availability assumption below;
repository-backed local publication implementation and actual deployment
acceptance remain required. Keep Actions off and reuse the existing namespace.


## Scope correction - October 26

WordPress, wordpress-db, wordpress-redis and phpMyAdmin are retired at the user's
request. Their original data, four claims, native Secrets and backups remain.
Database/plugin upgrades for these retired workloads are canceled. Charts and
Flux are updated; [exact acceptance](WORDPRESS-RETIREMENT-20261026.md).
The existing five-milestone goal otherwise remains active and unchanged.


## Additional mandatory goal requirements — October 25

The user's latest AGENTS.md instructions are mandatory execution and acceptance
requirements for every remaining milestone. Their maintained contract is
[Mandatory execution and completion rules](../PLAN.md#mandatory-execution-and-completion-rules--user-instruction-october-25),
with exact owned storage and reconciliation in
[the output inventory](TASK-OUTPUT-INVENTORY.md). This adds the direct-work and
delegation restrictions, single-root storage and capacity guards, protected
source/runtime retention, and verified checkpoint cleanup/reporting requirements.
The existing five-milestone migration/security goal remains active and incomplete.
Current supported goal tools expose status changes but no objective-edit field;
these additional requirements are saved here and in PLAN.md rather than
claiming that the tracker objective was edited or creating a duplicate goal.

**Resolved:** following the user's direct request to set this as the goal,
`create_goal` successfully persisted the revised five-milestone objective in this
same chat. A subsequent `get_goal` readback confirms **active**, thread
`01a12045-bf7e-73b3-8557-752d17c72ffd`, createdAt/updatedAt `1792959856`.
The [exact current saved objective and supported readback](../evidence/revised-goal-readback-20261025.json)
supersede the historical limitation recorded below. No unfinished work was
falsely marked complete and no raw session data was edited. The supported call
succeeded despite the tool description saying an unfinished goal would reject
creation; actual readback is the evidence. The revised scope now governs the
active tracker as well as this plan.

Complete the data-preserving Kubernetes maintenance requested in this chat: preserve every account, credential/permission identity and request/history record in the Overseerr-to-Seerr migration; replace failing MeTube with a working YouTube downloader while preserving existing PVCs/NAS downloads and proving a real download plus restart persistence; audit the whole cluster against current disclosed vulnerabilities and remediate compatible available fixes, reporting unsupported and unfixed findings honestly. Maintain only images and repositories James owns. Do not maintain, patch or rebuild third-party upstream service images as bespoke derivative forks; consume maintained upstream releases through repository-managed version/digest updates and appropriate validation. For owned images, maintained changes, build definitions, dependency changes and update mechanisms must be represented in the owned repository. Ad hoc locally built/saved images or tar archives must not be the maintained deployment source. Every deployment artifact requires reproducible repository-backed provenance and an already approved publication path. Keep GitHub Actions OFF and local testing enabled; local validation does not authorize local-only deployment-image maintenance. Do not invent a registry or publication route. Identify existing deviations and plan a safe repository-backed transition; name any missing build/publication decision without silently substituting a route. Preserve working deployments, repositories, dirty source changes, service data, PVCs, required recovery/rollback artifacts, resource limits and running Strata. This scope correction alone authorizes neither destructive migration nor new external publication. Finish authorized artifact cleanup and verified SMB recovery backup handling before resuming this revised delivery scope. Put repeatable host changes in Ansible and publish reviewed charts through the private branconet-charts local validation -> validated -> Flux path, preserving prior compatible deployment, merge and approval boundaries. Native Kubernetes Secrets managed through BORTUS remain authoritative. Keep BORTUS application development and its unfinished release in its separate owner chat. Finish with exact deployed-image/data/route checks and Codex IAB validation after implementation; update PLAN.md, MIGRATION_STATUS.md and acceptance evidence. A build, prepared script, host patch checkpoint or partial security reduction does not complete this goal.

## Historical goal-control receipt before the successful update

The following is the earlier failed-control observation. It does not describe
the current tracker: the successful update/readback above and the October 28
active-goal readback supersede it. The objective and acceptance scope are intact.

Supported `get_goal` readback identifies thread
`01a12045-bf7e-73b3-8557-752d17c72ffd`, status `paused`,
createdAt `1792798609`, updatedAt `1792955981`.
Its actual persisted objective is still the earlier maintenance objective. The
available `update_goal` schema accepts only `status: complete | blocked | paused`;
it has no objective field and cannot resume a goal. `create_goal` explicitly
rejects an unfinished existing goal. No supported objective-update control was
found in the available tool inventory. This document records the corrected
human-authorized scope, **not** a successful update of the tracked objective.
No raw session data was edited, no replacement goal was created, and the
unfinished goal was not marked complete. Cleanup-first ordering remains.

The exact old objective returned by `get_goal` was:

> Complete the data-preserving Kubernetes maintenance requested in this chat: migrate existing Overseerr to Seerr while preserving every account, credential/permission identity and request/history record; replace failing MeTube with a working YouTube downloader, preserve existing PVCs/NAS downloads and verify a real download plus restart persistence; audit the whole cluster against current disclosed vulnerabilities and remediate compatible available fixes, reporting unsupported/unfixed findings honestly; put repeatable host changes in Ansible and publish reviewed application charts only through private branconet-charts CI → validated → Flux. Preserve existing data, encrypted backups, rollback sources and running Strata. Native Kubernetes Secrets managed through BORTUS remain authoritative. Keep BORTUS application development and its unfinished release in its separate owner chat. Finish with exact deployed-image/data/route checks and Codex IAB validation after implementation, update PLAN.md, MIGRATION_STATUS.md and acceptance evidence. A build, prepared script, host patch checkpoint or partial security reduction does not complete this goal.

## Current deviations and transition

October 28 live main/init-container inspection found no remaining running
`*-security-20261023` references. Those original candidates, source, scans and
failures are historical/recovery evidence, not instructions to rebuild or deploy
them. Current vendor images and both latest official security updates are
represented in private charts and the complete current runtime scan binding.
Preserve original recovery sources and every recorded failed safety exclusion.

The existing Docker Hub publication route is established, with no new registry
or Actions. The three remediation releases have repository-owned definitions,
locks, publication and exact runtime provenance: [qbit-monitor](OWNED-QBIT-MONITOR-20261027.md),
[personal site](OWNED-PERSONAL-SITE-20261027.md) and
[Ruckus](OWNED-RUCKUS-RELEASE-20261027.md). Their live immutable images still match
those receipts. The separately delivered Ingenium image retains its existing
source/installation/data acceptance and published digest; its runtime cycle
changed no application source. BORTUS and its unfinished application release
remain explicitly held with the separate owner. The superseded claim that every
owned-image publication path is unresolved must not block or repeat this work.

Current acceptance is [the October 28 delivery ledger](OFFICIAL-SECURITY-REFRESH-20261028.md).
Seerr's original-account authenticated browser check remains open. Remaining
vendor CVEs, host entitlement exclusions and the BORTUS hold remain explicit;
they are not claims of a vulnerability-free cluster. The full goal stays active.
