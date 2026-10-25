# Dedicated local build storage

The existing cluster disks and C-drive build guards remain unchanged. A separate
96 GiB native ext4 filesystem was created in
`F:\branconet-build-storage\native-build-20261025.ext4`, UUID
`3c792469-ea0e-4a2c-98e8-1185b141607b`, and mounted at the operator runtime's
`local-image-build-offload-20261025`. Strata and other projects were left running.
Only this new, explicitly verified regular file was formatted; no host partition
or existing filesystem was changed. Its Windows directory has a private ACL.

`playbooks/local-build-storage.yml` is opt-in and must run as local WSL root.
Default/check mode do not create or mount anything. Repeated execution verifies
the existing file, filesystem UUID and mount rather than reformatting it. No
formatting is performed at startup. The successful creation receipt SHA is
`8a68474285391cffe386c69973da0aee21e6dabfb4df74a4d0ff74b09bcf2c37`.
An initial format attempt timed out before creating a filesystem; its original
file identity and zero header were checked before the explicit guarded resume
with `mkfs.ext4 -E nodiscard`. Both attempts are retained.

The private charts repository's separate offloaded builder admits CoreDNS,
Jackett, Plex, Unpackerr, Homepage and http-echo only. It keeps the existing 3 GiB memory, no-swap, 1.5 CPU,
512-task, 8 GiB cache, 12 GiB fresh allocation and 4 GiB OCI bounds. The original
global build lock prevents overlapping builders. It checks both the dedicated
F filesystem/physical drive and the shared Docker bootstrap on C; Docker's new
mutable layer is bounded to 64 MiB, logs to two 16 MiB files, and C retains 2 GiB.
It never clears shared caches or changes the default builder.

The offloaded scanner is opt-in. Its original memory/CPU/deadline, complete OCI
and source proof, 24-hour database age and full database hashes remain enforced.
It retains 25% plus 8 GiB free in the native filesystem, 8 GiB physically on F,
and an 8 GiB private scanner allocation ceiling. Old C-drive scanner guards and
frozen helpers remain unchanged. New helper setup rehashes existing complete
immutable inputs once, avoiding redundant reads of both original and copy.
No credential, database, image archive or private receipt is committed to Git.

The existing local charts publisher now stages on the same native F filesystem.
Its 29 controls and unchanged chart validator passed for source
`03aa16e785a7c74779bb72799056af0683311c04`; publication receipt SHA256 is
`54a197827798d9f88fe1d2971d821f8f037f35c78ee4bc9ffb2d27f66dd1942e`.
There is still one serial publisher and no GitHub Actions execution.

The opt-in `local_build_storage_configure_ci` Ansible setting installs an
owner-root existing-only mount helper and updates the existing idle Windows
scheduled task with `--offloaded-storage`. At startup, the watcher invokes this
helper before watching; a missing backing file refuses instead of creating or
formatting one. Configuration receipt SHA256 is
`a7fc81364984c7b66f001ac344fb487f8b416e422f999141e93de2c2821e4e0c`.
The mount helper verifies the original file, filesystem and owner identities.

During maintenance, C: exhaustion caused the Ubuntu controller filesystem to go
read-only. The cluster nodes were unaffected. Transparent NTFS compression of
identified archival artifacts recovered capacity; full hashes, lengths and last
write times were verified unchanged. No artifacts were deleted, no unrelated
checkout was reset and no Strata process was stopped. Only the failed Ubuntu
instance was restarted; its existing Docker workload recovered healthy. The
original backing file was then remounted through Ansible, with receipt SHA256
`7ccdc24e2e904ec9afaaaa57bf5a0bf46266458cacabd93bb19206fc7a871720`.
Private recovery evidence remains under
`F:\branconet-migration-artifacts\maintenance-storage-20261025`.
