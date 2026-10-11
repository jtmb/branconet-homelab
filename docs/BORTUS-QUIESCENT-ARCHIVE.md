# Deadline-aware quiescent encrypted archive

This standalone callback composes the existing pinned encrypt_source machinery,
not the old capture wrapper that resets its lease. The optional encrypt_source
cleanup callback preserves default behavior for existing callers. When supplied,
age children own separate sessions and all child/pipe/descriptor closures are
independently attempted, including when another closure refuses.

The adapter shares the existing absolute quiescent deadline, at most2100 seconds.
Owned cleanup uses the remaining budget; after expiry it immediately kills only
owned sessions/PIDs and permits one total250ms reap grace. This cleanup margin
never renews the acceptance lease; expiration always refuses acceptance.
No live qualification, application entrypoint or row-preservation proof is granted.

Construct through the adapter's exported quiescent/credentials interfaces to
preserve strict class identity. QuiescentArchive(options,kubeconfig_path,
recipient_path,identity_path) is callable as archive_callback(operation,deadline).
It requires the existing journal's durable sqlite_archive_state=pending, the
same operation deadline and one invocation only. Fresh stopped-source and holder
fences precede launch, follow encryption and NAS copy, and repeat before return.
The ownerless holder must exactly match its qualified read-only proposal,
Running/Ready/unrestarted state and literal spec image/status.imageID. Fresh name,
UID and opaque RV match immediately before exec. Name-based exec remains non-atomic
with Pod UID; post-read source/holder fences remain required.

The existing protected kubeconfig inode is parsed/verified and inherited by the
fixed runtime kubectl; fresh embedded verified mTLS options are also required.
Only fixed NODE_READER bytes enter its bounded stdin pipe. Age recipient/identity
are pinned owned regular single-link600 files in700 directories, with safe pinned
ancestors. Age accesses /proc/<adapterPID>/fd/N while parent descriptors stay alive;
no credential file is exported and no values enter argv/environment/logs/errors.
Encrypted output is exclusive600 in the pinned journal run. Qualified encrypt_source
checks same inode and authenticates the exact ciphertext before any NAS copy.

A fixed strict-host-key SSH invocation streams only ciphertext and bounded public
metadata to james@192.168.0.4:2002. It does not use SCP overwrite semantics. The fixed
NAS directory must be a safe non-writable-group/world directory owned by root or
james. The remote writer creates only bortus-sqlite-<run12hex>.age with O_EXCL600,
checks exact length/hash, fsyncs file and directory, then reopens read-only and
verifies the same inode/size/timestamps/bytes and hash. The local pinned ciphertext
also remains unchanged. Duplicate target, missing response or ambiguity refuses;
partial ciphers remain and are never retried/adopted/deleted. Remote execution is
not atomic with local cancellation, so a lost reply never grants acceptance.
The local absolute deadline bounds transport; a remote remaining-duration budget
is additional protection, never authority to renew the local lease.

The returned exact nine-key result matches capture_quiescent's existing ABI.
It authenticates framed bytes and equal encrypted NAS bytes only. SQLite integrity,
whole rows, fresh restore, schema migration, image/admission and release acceptance
remain separate. The observer/journal belong to the outer coordinator and remain
open for later snapshot/backup/holder deletion. The adapter never resumes controls,
deletes holders or launches an application. All qualification uses disposable
public age keys/SQLite, controlled Python children and mocked transport; no live
operator files, kubectl, Node, SSH, API or production data are accessed.


The combined composition supplies `quiescent_module=observer_module.quiescent`
when constructing QuiescentArchive. Its default graph remains unchanged; the
explicit injection binds the archive's strict operation identity to the observer's
exported source classes without global module reassignment. Construct the operation
from that same module and use the observer's actual trace and ControlJournal.

After captured-zero, `archive_callback.schema_metadata(operation, manifest_path,
manifest_sha256, deadline=operation.deadline)` authenticates the exact newly
captured ciphertext into private tmpfs, checks the pinned actual legacy-image
seven-migration ledger and public topology, independently cleans tmpfs and repeats
zero-writer/source/watch fences before returning a new protected schema receipt.
It does not use or weaken the Ready-writer producer. This source-bound archive
receipt supports stopped-schema qualification while continuous zero writers and
same physical storage remain established. It does not prove original rows,
live Ready status, forward execution or recovery acceptance. The trusted root
phase callback must independently bind image, guards and the actual receipt.


Root independently qualified the integrated shared graph on `1daea8f`: [65 scoped controls passed](../evidence/bortus-quiescent-composition-root-20261011.json) without skips in 14.251 seconds. Frozen working sources remain unchanged, and the test supervisor is absent. Actual local TLS/age/SQLite fixtures use mocked kubectl/SSH; this is local composition acceptance and does not authorize or prove live latest-data capture or forward migration.
