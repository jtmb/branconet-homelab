# Tautulli maintained vendor transition

Owner: cluster maintenance chat `01a12045-bf7e-73b3-8557-752d17c72ffd`.
Status: preparation; production still uses the prior derivative. No vendor
adoption or final security/browser acceptance is claimed here.

The [official 2.18.2 release](https://github.com/Tautulli/Tautulli/releases/tag/v2.18.2)
is the latest stable release at inspection. It matches the currently running
application commit `9484667bc1f2d159368a999320b8f495bbfbd00a`. Select the explicit
version tag rather than inferring that `latest` is identical: their image
manifests differ despite the same application source revision.

The original publisher's explicit 2.18.2 digest was evaluated and scanned, not
deployed: it still contains 4 Critical / 113 High findings against the current
feed. The [maintained LinuxServer distribution](https://docs.linuxserver.io/images/docker-tautulli/)
ships the same application release with a newer base. Its selected image is
`ghcr.io/linuxserver/tautulli:v2.18.2-ls249@sha256:c6a48416d16b26f254b000133d2d844c1905ee58ed0f44aad9bda66598d39988`;
amd64 manifest
`sha256:88cb2fd7ab5b356e58b73a07b2ed1e44819e933e4982b7de4096e52406853823`.
The October 23 build reports no Critical, 7 High, 4 Medium, 45 Low and 2 Unknown
finding rows; seven High rows have package fixes absent from this artifact.
Both reports use the same pinned current advisory feed, no suppression and
complete before/after input hash checks. Neither has a CISA KEV intersection.
No third-party image is built, patched or republished.

Keep the original `plex/tautulli` Deployment UID
`9db52ebb-23c8-47c6-82c8-ebde3b0a2775`, release UID
`e5aa088f-22a3-4f47-b7c4-094be5354bf4`, Longhorn claim UID
`97eb095e-37ec-4185-80ed-4d8f3c19f486`, native Secret, resource requests and routes.
Before image adoption, pause only Tautulli through the private charts publisher
and Flux, take a complete authenticated encrypted cold backup, verify its NAS
read-back and bind its SQL state to the observed baseline. Preserve every
account, history record, configuration value and original file metadata. Check
native API authentication, Plex identity/libraries and notifier configuration
without sending notifications. Repeat data/API/routes on a distinct restart Pod.
Any data-changing rollback must preserve the new state before restoring the
authenticated original; an image rollback alone is not data recovery.

The existing F:-backed output root and ext4 UUID remain authoritative. New
protected observations, key and cold archive use `upstream-tautulli-20261026`;
frozen executed source uses `control-source/upstream-tautulli-20261026`; metadata,
scan reports and control receipts use the existing `operator-control` and
`security-review-20261026`. All output belongs to this chat on the same physical
volume. Preserve current source repositories, native secrets, all failed
evidence, the complete original archive and existing rollback image. Public
scan caches and empty scratch are reproducible only from the exact pinned
image/tool/feed commands and require normal ownership/reference checks before
removal. Capacity guards apply before downloads or archive stages.

The original live baseline passed 802 filesystem entries, all 24 tables / 11365
rows, 16 users and 2878 history records, authenticated API/Plex/configuration
reads and 27 status/login/redirect route checks. It verifies every original
entry has UID/GID 1000 before allowing the maintained image's ownership setup.
These are pre-cutover results, not vendor deployment acceptance.

The complete original claim is now authenticated and verified on NAS:
159475924 encrypted bytes, SHA-256
`a5b76de5260cbab8a7b5a592bb61cc023d6c19e6895c8db72ab8daea8cfcd0de`.
All 23 non-session tables match the earlier live snapshot exactly. One existing
active-session row advanced while the original app was still running; the cold
SQL copy is the authoritative pre-adoption state. Every column of that row is
fingerprinted. Only `stopped`, `state` and `view_offset` may subsequently advance,
as implemented by the exact vendor `ActivityHandler.set_session_state` source.
Require all other cells and session identity to match, and verify those three
runtime values against the actual authenticated activity API and a fresh
heartbeat. Do not omit the whole sessions table or relax account/history checks.
Both the initial strict online-to-cold mismatch and the corrected cold-reference
receipt remain. The original archive, verification key and protected sources
stay intact. No account, credential or history record has been changed by the
controller.

The versioned cold-backup profile is exposed by the existing Ansible role and
controller, with the complete four-GiB/4096-entry bound and UID/GID 1000 reader
on workernode1. It never scales the application itself. The reviewed LinuxServer
init script applies the configured `abc` ownership to `/config`; its service
runs the published Python program at `/app/tautulli/Tautulli.py` as that user.
Preserve the actual entire claim's ownership/modes against the existing native
PUID/PGID and repeat every state/API check after launch and restart.

Final fleet security and Codex IAB acceptance remain separate goal gates.
