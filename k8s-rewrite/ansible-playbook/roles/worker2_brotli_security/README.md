# Worker2-only Brotli library security patch

October 28 outcome: the host's native unattended updater installed the fixed
package at 06:44 local time. This controller did not install it: its original
preinstall refusal and reviewed retry's changed-state refusal remain intact.
All three nodes now have the fixed version. Do not replay either apply attempt.
Use observation for this completed host requirement; the entrypoint below retains
the reviewed repeatable procedure and original failure evidence.

Prepared for [USN-8956-1](https://ubuntu.com/security/notices/USN-8956-1), published
26 October 2026: Jammy `libbrotli1=1.0.9-2ubuntu0.1` fixes CVE-2026-111497.
This role is not applied by the default playbook. It never runs Ubuntu Pro account
commands, a general upgrade, reboot, drain, service restart or cache prune.

The sole target is `james@192.168.0.5:2002`, hostname `workernode2`, root filesystem
UUID `960bc2c7-2a7e-4bc2-b2c5-dbb6d71207f4`. It requires three original Ready,
uncordoned nodes, no pressure, the unchanged Longhorn 25% floor plus 512 MiB, and
a bounded additional 64 MiB transaction peak on worker2.

Run `python3 -B files/controller.py candidate` for an unprivileged signed-candidate
and exact transaction-plan observation. It is explicitly not full qualification.
Run `python3 -B files/controller.py qualify --privileged-read` from a WSL terminal
to include root-readable kubelet configuration hashes (the source remains in the
repository). Review the resulting `qualify-*.json`, then explicitly
run `python3 -B files/controller.py apply --qualification <absolute-receipt>`.
The Ansible entrypoint `playbooks/worker2-brotli-security.yml` invokes that same
controller, uses `raw` on localhost to avoid remote module files, and is disabled
unless `worker2_brotli_security_enabled=true`. Its mode defaults to `qualify`;
application additionally requires `worker2_brotli_security_mode=apply` and the
exact `worker2_brotli_security_qualification` path. Set
`worker2_brotli_security_privileged_read=true` for qualification or observation
requiring protected hashes. Application always requests terminal-only privilege.
Run from a controlling TTY.

Privilege input reuses the existing `legacy_plex_preservation` terminal helper.
The password is read with terminal echo disabled, retained only in RAM and sent
on SSH stdin to `sudo -S`; never put it in Ansible variables, environment, argv,
files or receipts. Remote Python is source in `-c`; no remote scripts or tempdirs.

Qualification checks the signed/trusted Ubuntu `jammy-security` candidate and
an exact simulation with one `Inst` and one `Conf`, no extra packages/removals.
Application rechecks the whole installed-package/runtime snapshot, downloads only
the pinned package, verifies the archive against signed APT SHA-256/size and
refuses unexpected maintainer scripts (only the normal ldconfig trigger allowed).
Installation uses forced authenticated/no-insecure/only-upgrade/no-remove
options, `NEEDRESTART_MODE=l`, noninteractive mode and preserved conffiles.
Acceptance requires the complete installed-package diff to be solely libbrotli1,
unchanged boot/kernel/service PIDs and starts/runtime configuration hashes,
clean dpkg and unchanged node identity/runtime state.

Metadata stays in the existing F-backed root at
`platform-upstream-review-20261027/worker2-brotli-host-20261028`. Ownership and peak
budget are recorded before operations. Native APT/dpkg state is the required
runtime consumer. A preexisting package archive is protected. A newly created
exact signed archive is removed only after the final consumer, with dpkg/APT
locks, resolved ancestry, single-link inode/hash ownership and no extended
attributes. The pinned existing cleanup reference is transferred only in a RAM
packet and checks process arguments, cwd/root/executable, file descriptors
(including SFTP), memory maps, every observed mount namespace and every active
systemd unit property. Logical and allocated removed bytes are separate. This is
a native Linux APT path, not a Windows-mapped path; no Windows deletion proof or
space recovery is claimed. Failed safety checks retain that exact path without
retry. Partial archives are retained with
an explicit failed-authentication reason. No blanket cache cleanup is permitted.

`apply-intent.json` is exclusive and written before SSH dispatch. An interrupted,
failed or uncertain installer is never automatically replayed. Use `observe` for
read-only follow-up and review the immutable failure receipt. An acceptance
receipt records concrete package/continuity/cache facts, not merely an exit code.

One narrowly reviewed exception exists for the complete original
`apply-0313dea68b364a2b89bb97b75d2af501.json` refusal, pinned by SHA-256. Installation
never started; package, host, cluster and the preexisting signed archive stayed
unchanged. Its only error was the trigger parser rejecting this exact normal
72-byte package file:

```text
# Triggers added by dh_makeshlibs/13.6ubuntu1
activate-noawait ldconfig
```

The parser now requires those exact bytes, the reviewed trigger SHA-256 and the
reviewed complete control-tar SHA-256. It does not accept arbitrary comments or
other triggers. After a **new current-source privileged qualification**, explicit
`apply --qualification <new-receipt> --reviewed-preinstall-refusal <original-receipt>`
may create the exclusive `apply-intent-r2.json`. The original intent remains
unchanged. Both the original refusal and fresh state must prove no installer
started, no package/host/node change, no cleanup refusal, and the identical signed
archive inode/hash. The new intent binds the original receipt and reviewed control
hashes. Any started, uncertain, changed-state or additional attempt is refused.
The Ansible equivalent additionally sets
`worker2_brotli_security_reviewed_preinstall_refusal` to that exact original receipt.
