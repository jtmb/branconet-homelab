# Native staging authentication carrier repair

`scripts/migration/native-stage-repair.py` is a separate, explicit one-shot
carrier repair. It does not modify the frozen original controller, remote stage
helper, original ownership, original failed intent, backups or failure evidence.
It has not been executed during source preparation.

The original controller SHA256 is
`9ef6a287adadc82852b633a9ff282a065c80c01b9c4b60686a62dc9458a73c41`;
the immutable remote helper is
`c124d58ae18b02ceb02ca835dab8aa283a4a52b840c8426168c6de290e9d1378`.
The original Ubuntu sudo authentication call combined `-k` with `-v`, which does
not update its cached credentials. Its following `sudo -n` payload was denied
before Python execution. The host uses Python3.10.12; its syntax check succeeded.
No upstream Kubernetes binary or remote staging algorithm changes are needed.

The repair hard-binds the actual public evidence already captured by the
coordinator:

- `kubernetes1372-stage-sudo-journal-projection.json`, SHA256
  `f6f53d9395b839175abb6894e85b8c0edcc3e1b2c77c3d990cfd866b8e3014e5`:
  the original payload denial at microsecond timestamp `1793251564835373`,
  without a session-open event.
- `kubernetes1372-native-stage-after-transport-failure.json`, SHA256
  `7b25f7b4d1a6fd7dfb3a27412de41dfd47df8fc93a32c228a8794c2a95a618b2`:
  all nine authored paths absent.
- `kubernetes1372-native-auth-carrier-comparison.json`, SHA256
  `a21f3b32760c62877b2c651febe694009c8cbcac64f7d8b9843e973b540c5e27`:
  original auth succeeded but payload was denied; the corrected carrier returned
  root UID and exactly the harmless public stream marker.

`stage` consumes the protected password line before SSH. It loads the unchanged
original functions in memory, verifies original source/ownership/checkpoint and
raw backup hashes, and repeats all three original identity observations. All
nine paths must still be absent and all three conservative staging/replacement
budgets must pass before any write. An existing partial path refuses the repair.

Before mutation, it exclusively creates
`H/kubernetes1372-native-stage/transport-repair`, declares ownership, preserves
the exact original controller as `original-staging.py`, and writes a separate
`original-intent-disposition.json` marked `closed-auth-before-exec`. This is a new
evidence record, not an alteration of the failed intent. Each new write then
gets its own repair before/intent/after record. The original remote code still
enforces exclusive path creation, stream size/SHA256, original metadata, fsync,
data/identity preservation and unchanged capacity floors.

The corrected memory-only carrier consumes the password, performs separate
`sudo -k`, authenticates using `sudo -S -p '' -v` with only the password pipe,
and invokes `sudo -n` with only the binary stream. Password handling cannot
depend on whether sudo consumes a line. Stderr is drained in bounded chunks and
only its byte count/hash and exit status enter evidence; raw stderr and password
bytes are never persisted. No process is terminated after an uncertain outcome.

Invoke the existing venv Python with `-B` and this script's `stage` mode using the
coordinator's existing protected stdin transport. `observe` is read-only on
nodes and can qualify completed repair-authored files after a lost completion
reply. It never submits writes. A second `stage` invocation is refused once the
repair root exists; any new uncertain partial requires preservation, not another
carrier retry.

On all-nine completion, the helper exports new actual per-node receipts and
`transport-repair/binary-evidence.json`. Original raw backup and vendor signature/
scan references remain intact; `reviewedVulnerabilityIDs` remain unchanged for
the coordinator's explicit review. The exact `.new` paths are consumed later by
the native role's atomic replacement, after full authority preflight. Original
failure/source evidence remains protected. Parsing/whitespace checks are the
only validation performed for this source addition; no repair was executed.
