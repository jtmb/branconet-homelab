---
name: native-secret-change
description: Use when rotating a password, token, or other credential stored directly in a Kubernetes Secret (not Git) for a BORTUS service such as ntfy. Covers format validation, resourceVersion guarding, verified restart, and automatic revert.
---

# Changing a value in a native Kubernetes Secret

Some credentials (ntfy's `bortus-subscriber`/publisher passwords and tokens,
for example) are deliberately stored **only** in a native Kubernetes Secret,
never in Git, because `/auth`-style mount points are `emptyDir` and the
service reads `NTFY_AUTH_USERS`/`NTFY_AUTH_TOKENS` env vars sourced from the
Secret at container start. A CLI-side change (e.g. `ntfy user change-pass`
inside the running pod) vanishes on the next restart — it must go into the
Secret itself.

## The 2026-11-17 incident this skill exists to prevent

A hand-edited `users` value used `name:hash` instead of the required
`name:hash:role`. ntfy crash-looped for ~6 minutes before the format error
was visible in `kubectl logs`. The root cause was assuming a 65-character
field was "hash only" when it was a 60-char bcrypt hash plus `:role`.

## Required steps, in order

1. **Confirm the pod is currently healthy** before touching anything. Refuse
   to proceed if it isn't — you can't tell your change from a pre-existing
   problem otherwise.
2. **Hash the new value inside the running pod**, never locally or in any
   tool that might log the plaintext:
   ```
   kubectl exec -i deploy/<name> -- sh -c '<hash-command>'
   ```
   with the plaintext piped via stdin, confirmation included, output
   captured and the bcrypt (or equivalent) line extracted by pattern, not by
   assuming a fixed field width.
3. **Validate the new secret-value format with a strict regex** before
   writing anything, and validate every *other* existing entry in the same
   field too — don't write a value next to entries you haven't checked.
4. **Back up the old value** (base64, exactly as stored) to a `0600` file
   before patching, named with a timestamp so repeated rotations don't
   collide.
5. **Patch with a `resourceVersion` precondition** (`--type=merge` with
   `metadata.resourceVersion` set from your own `get`), never a blind
   overwrite.
6. **Restart and poll for Ready**, with a bounded timeout (a few minutes).
7. **If the pod does not become Ready, revert immediately**: re-read the
   Secret's current resourceVersion, patch the old value back, restart
   again, and report the failure — don't leave the service down while you
   investigate.
8. Never print the plaintext value in any log, receipt, or chat message that
   isn't the one direct handoff to the credential's owner. Delete any
   temporary plaintext file as soon as the value has been verified to work
   (e.g., via a scoped login check), not before.

`scripts/migration/update-ntfy-auth-user.py` in this repository implements
all eight steps for ntfy specifically and is reusable as a template for the
next native-Secret-backed credential.
