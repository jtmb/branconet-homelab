---
name: feature-handoff
description: Checkpoint a completed BORTUS feature and automatically continue the full goal in a fresh local chat after focused verification and one matching receipt.
---

# Feature checkpoints and fresh chats

The user authorized focused validation, reviewed commit/push checkpoints to the
existing intended remote, fresh local successor chats, handoff messages and
predecessor archive after a verified receipt. On 2026-10-23 the user explicitly
requested the working Veyra handoff pattern without human intervention. Apply
the [current handoff policy](../../../docs/operations/handoffs/2026-10-23-bortus-autonomous-handoff-policy.md).
It supersedes historical relay bookkeeping, not product acceptance or execution
permissions. A checkpoint never completes the full BORTUS goal.

## Checkpoint

- Finish and personally review the current concrete feature. Do not rotate for
  elapsed time, tokens, context, preparation or an active run. Early rotation
  requires an explicit user request. Stop assigning work and reconcile writers.
- Identify the actual feature checkout. Reuse an existing suitable isolated
  checkout when the saved project's default checkout is busy. Give its exact
  path to the successor; creating a chat does not change its command cwd.
  Do not switch, reset, clean, stash or commit unrelated work. Create no new
  worktree unless authorized. Preserve unaccepted worker branches separately.
- Update affected docs with actual changes, finite validation, failures and open
  gates. Keep Source, runtime, visual and performance claims distinct. Run the
  project's existing focused checks/hooks within current authorization; do not
  invent Veyra gate commands, replay frozen workloads or change resource limits.
- Stage only reviewed intended changes. Commit/push normally to the intended
  existing remote and verify its branch SHA with `git ls-remote`. Reconcile an
  uncertain push before transfer. Local-only root docs/skills stay local: retain
  their versioned snapshot/hashes separately, never publish them as app files.
- Write one concise portable handoff plus a private local companion using the
  [checklist](references/handoff-template.md). Give the full objective, accepted
  revision, next feature/owned paths/criteria, first actions, durable restrictions
  and open gates. Link canonical evidence; keep credentials/private data out.
  Preserve historical evidence in place without copying or recursively hashing
  cumulative receipts, ancestor graphs, all Git refs or unrelated repositories.

## Transfer

- Use `list_projects` and `create_thread` for the same saved local project with
  fresh history, `model: "gpt-6.1-sol"`, `thinking: "high"`. Existing chats keep
  their settings. Select one next concrete feature; do not begin it here.
- The successor reads the current policy/skill, portable handoff/private
  companion and relevant domain specs. Newest checkpoint instructions supersede
  old starting SHAs, clean-checkout assertions and receipt/ack sequences. Carry
  forward original product constraints and evidence links without transcript copy.
- The successor calls `get_goal`; if absent, creates the FULL authorized BORTUS
  objective without an invented budget and confirms active with `get_goal`.
  Never mark a milestone complete, fake active status, edit tracker storage or
  overwrite an unfinished goal. A blocked old chat retains its real tracker.
- Before edits, verify the OWNED checkout's branch, HEAD, intended remote SHA
  and relevant dirty state. A material mismatch stops dependent edits. Preserve
  and diagnose the actual mismatch without resetting anything. Unrelated shared
  checkout activity or Codex capture refs do not invalidate this checkpoint.
- Write ONE small receipt at the unique private path supplied by the parent:
  `accepted: true`, `threadId`, `branch`, `commit`, `nextFeature`, `handoffsRead`,
  `goalStatus: "active"`, `goalScope` and `ownershipAccepted: true`. Goal fields
  must reflect the real tool result. Acknowledge the exact owned checkout and
  receipt path. Then continue autonomously; no startup report, parent startupack,
  cumulative closure map or separate owner-release handshake is required.

## Confirm and archive

- The parent checks that the successor exists, its receipt matches the verified
  checkpoint/full active goal, and old writers are stopped. The receipt transfers
  exclusive feature ownership. Archive ONLY the predecessor after this match;
  never archive the successor or unrelated chats. Receipt observation may use
  `wait_threads` and a small file read; avoid repeated unchanged polls.
- If the attempted successor is blocked by superseded handoff bookkeeping and
  tools cannot resume its tracker, the user's 2026-10-23 repair request authorizes
  one fresh replacement transfer of this completed checkpoint. Preserve old
  trackers/evidence as blocked, start the replacement's own full active goal,
  and retire the unused attempt only after replacement acceptance. Do not spawn
  a succession loop for unresolved feature failures or missing authorization.
- On creation/verification failure, retain a recoverable checkpoint and the real
  error; never simulate acceptance, weaken gates or request approval already
  supplied. Ask only for a genuinely new permission or missing decision.
- Emit the created-thread directive and link the checkpoint, skill and successor.
  Carry this workflow into each successor without requiring another user request.
