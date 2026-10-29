# Pipelined native configuration writes

The remote static-pod JSON patch and `upgrade.yaml` tasks now use
`ansible.builtin.command` with the memory-only `native_artifacts.py write` helper
and explicit JSON stdin. Their rendered content is unchanged. They no longer
use the copy action's SFTP transfer or a controller F path as remote scratch.
All existing controller receipt copies remain delegated to localhost.

Immediately after a new native tempfile directory is allocated, the read-only
`allocation` mode requires it to be empty, root-owned, mode0700, and at its exact
non-symlink `/etc/kubernetes/tmp/kubernetes1372-*` path. Its host, inode/device,
UID/GID/mode, unique allocation name and observed creation ctime are saved in a
controller `.allocation.json` receipt **before** the patch directory or files
are created. The receipt binds the host, upgrade authority and recovery receipt.

The write helper checks that original allocation identity and root-owned parent
before each write. It permits only `upgrade.yaml` and the three named control
plane patch files on the master. Files use O_EXCL/O_NOFOLLOW, root ownership,
mode0600, a 2 MiB content bound, file/directory fsync and post-write size/hash
verification. Existing files are never overwritten. The JSON patches retain
their exact `/spec` and `/metadata` replacement structure. No installed binary,
static manifest, certificate or service is changed by the writer itself.

The native inventory carries the original allocation proof, and cleanup requires
that proof plus its existing exact content and active-reference checks. The
earlier failed native directory has no such pre-write controller allocation
proof. It must remain an explicit retained exception; a matching name prefix
does not confer ownership and must not be used to adopt or delete it.

This source change was parsed only. It does not replay the failed upgrade, repair
its allocation, authorize another drain, or change native binary resume rules.
