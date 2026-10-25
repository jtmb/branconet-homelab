# Revised delivery objective — user correction October 25

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

## Goal-control receipt and limitation

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

The currently deployed `*-security-20261023` derivative images and undeployed
third-party rebuild candidates belong to the earlier approach. Their full
archives, source, scans and failed attempts remain historical/recovery evidence.
Do not rebuild or promote those candidates under the corrected scope. Working
deployments stay running until each compatible upstream release is selected,
represented by version/digest in the charts repository, and qualified against
existing data and integrations. Rollback artifacts are retained through that
transition. Source recipes are preserved, not deleted or portrayed as current
approved maintenance policy.

For first-party owned images, repository source/build definitions and provenance
are required. A replacement approved build-to-publication route has not been
established here: GitHub Actions is disabled, local-only saved deployment images
are rejected by the correction, and no new registry/publication is authorized.
That exact owned-image publication decision remains open. Third-party maintained
upstream image references can use their established publication paths; they do
not require us to operate derivative builds. Evaluate registry access and the
actual compatible upstream release before changing any running image.
