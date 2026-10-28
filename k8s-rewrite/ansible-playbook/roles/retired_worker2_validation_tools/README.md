# Worker2 validation copies

One-time retirement of only the three hash-pinned Linux executables exported for
the 2026-10-23 chart validation. The original binaries on Windows remain the
regeneration source. No build, download, source-tree removal, service changes,
container mutation or Windows recovery is involved.

Run `python3 -B files/controller.py` from WSL using a terminal, inspect its
`inventory.json`, then run the same command with `--apply`. The controller uses
the existing non-echoing privilege-input primitive. It refuses to overwrite
receipts or apply after any inventory refusal. It verifies the original hashes
both before and after the operation. Remote source is base64 encoded so the
process-reference guard does not mistake the controller's command text for an
active consumer of a target executable.

The only output subdirectory is inside the existing F-backed task root:

`/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025/platform-upstream-review-20261027/longhorn-application-batch-20261028/worker2-validation-tools`

Its `ownership.json`, `inventory.json`, and `apply.json` are the minimal durable
ownership and deletion evidence. No generated caches, dependencies or remote
scripts are created. Preserve source, locks, sibling validation receipts and
vendor files. Regeneration is an individually hash-verified copy from
`C:\Users\james\.codex\local-ci\branconet-charts-local-ci\.tools`; do not rerun a
retired validation attempt without a new explicit task.

The pinned existing reference guard checks every process, descriptor, map and
mount namespace plus active systemd units; its unit query is expanded to all
properties. Additional checks cover source ownership, filesystem UUID, single
links, mode, inode attributes, xattrs, 72-hour mtime/ctime age, Git ancestry,
configured commands for root/james, command symlinks, cron, unit and shell
configuration references. Every target is individually refused on failure.
All sibling file identities must remain unchanged. No target refused during
apply is retried.

After successful binary retirement, `--remove-empty-directory` originally qualified
the empty generated `.tools` directory and writes `empty-directory.json` in the
same output root. This incremental receipt is owned by this role and retained
for the coordinator's cleanup review. The follow-up proves ownership from the
original successful validation receipt, source manifest, `.gitignore`, and
actual `scripts/install-tools.py` generator; repeats directory-level consumer
and complete inactivity checks; and uses only `rmdir`. The source export parent
and all sibling files survive. Recreate the directory and copy the same pinned
original binaries only if a future authorized consumer requires them.

The actual directory qualification failed `original_manifest_hash`; its existing
`empty-directory.json` protects that exact directory. Do not retry deletion or
alter the receipt. The three binaries were removed; the 4,096-byte empty directory
and every sibling remain. The current opt-in Ansible entrypoint
`playbooks/retired-worker2-validation-tools.yml` exposes only `inventory|retire`,
never that refused follow-up. Both phases refuse overwriting existing evidence.
The executed-source reconstruction in `execution-source-binding.json` is derived
from recorded patch history, not a hash in the original execution receipt.
