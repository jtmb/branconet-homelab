# Maintained Plex adoption - October 26, 22:54 UTC

Plex now consumes LinuxServer's maintained image directly:

`docker.io/linuxserver/plex:1.43.5.11079-b3b13e506-ls330@sha256:01a53d9c7adcbb3701fbb0a4230c0a37c85453759b6b05a67356c3c7a09de08d`

The vendor image contains the same Plex1.43.5.11079-b3b13e506 already running.
`VERSION=docker` remains explicit, so startup uses that packaged version.
The existing launch command, environment Secrets, resource settings, Service,
13Gi config claim and three SMB media claims are unchanged. There is one
Kubernetes-managed writer. No media files were migrated or traversed recursively.

Private charts main, validated and live Flux source are
`929f182b15a7889ea21ae2382ca1caf2a9f28297`. The existing local pipeline validated
each revision; GitHub Actions was not used. The sequence was Flux quiescence,
fresh complete cold backup, image adoption, then a separate Flux-driven restart.

Both production and the distinct restart passed the complete comparison against
the original running server: all21 checked library/account/watch-state tables,
all3 library sections and their identity/paths, original server/account identity,
native Secret versions, original PVC/PV identities and native authenticated
library API access. No table fields were excluded or rewritten. UID1000 could
read the existing NAS media prefix. All6 node-facing identity/web checks passed,
with response hashes identical to the previously accepted routes. These are
actual API/data/route checks; no browser or real playback acceptance is claimed.

The old Pod was replaced by `20a53a8d-2054-448c-b693-8e2ea795fc9b`, then by
`f06ea94e-ea9a-4dfc-953e-90f448ac1f9b` for the independent restart. Both report
the selected immutable vendor image ID. The old derivative remains recovery
evidence and is no longer the running Plex image.

The fresh backup contains38987 files /6482079115 file bytes. Its complete
6623548404-byte encrypted archive has SHA256
`a4a61df2dd6128b6d61209e0eca1b932e28df5d2f4101ffd2aef65666175918d`.
Ciphertext streamed directly to the existing NAS recovery folder without a
second local6.6GB archive. Complete NAS read-back, SHA256, age authentication and
every decrypted archive member matched the cold source manifest. Original
backups and the existing recovery key backup remain intact. The read-only,
UID1000 reader mounted only the config claim and was retired by exact UID after
verification. Neither writer scaling nor data restoration is hidden in the helper.

The optional `upstream-plex-20261026` Ansible backup profile now supports this
bounded Windows NAS ciphertext transport. It preserves the15GiB local and NAS
free-space floors, permits only the existing recovery destination, refuses
overwrites, retains failed partials, never stores plaintext archive contents,
and authenticates the entire read-back. Existing profiles still default to local
transport. The exact frozen helper was executed directly; this is not a claim
that the whole Ansible playbook was executed during this checkpoint.

The unsuppressed vendor scan retains4High,70Medium and8Low rows, with no CISA
KEV match. The4High rows are Go stdlib findings in the vendor's `pebble` binary
(Go1.27.1): CVE-2026-111943, CVE-2026-78667, CVE-2026-78669 and
CVE-2026-97031. The selected current vendor release still carries these rows;
they remain security exceptions. No third-party fork, replacement binary,
scanner exclusion or zero-day-clean claim is introduced.

Evidence under the single F-backed task root:

- `upstream-plex-20261026`: source/version discovery, preflight, complete cold
  backup receipt, original/production/restart observations and adoption/routes.
- `control-source/upstream-plex-20261026`: exact executed controllers, reader,
  transport and Ansible profile, bound by the eight-file SHA256 manifest.
- `security-review-20261026/apps-plex-current-r3-0`: raw unsuppressed scan,
  verified immutable-image/tool/feed provenance and terminal successful receipt.
- `operator-control/plex-upstream-*`: whole-cluster inventories, exact cleanup
  receipts and authenticated recovery metadata. The3841140-byte metadata
  ciphertext SHA256 is
  `0925b99df280215fd3bcaf867e85532194207e3a1894e0d1911d617d33c376a1`.
  Every metadata member and full NAS read-back/authentication passed.

Final health:3Ready nodes without pressure,57Bound PVCs,30Ready HelmReleases,
all Kustomizations Ready,87Running Pods,64distinct runtime images,289controllers
including historical ReplicaSets,43Longhorn volumes with every attached volume
healthy. Four older failed diagnostic Pods remain protected failure evidence.
No third-party application derivative transition remains in the current matrix;
owned application images and platform/security work are separate open work.

Cleanup removed534413312 allocated Linux bytes /2362 generated paths. Exact
paths, per-path bytes, original Git/tool/protected-file proofs, regeneration and
inactive process/FD/map/mount checks are in the publisher and review scratch
reconciliation receipts. Sources, locks, unique evidence, required backups and
prior exceptions remain. No Windows disk recovery is claimed.

Existing Docker Hub Credential Manager authentication was also verified in RAM:
the established `jtmb92` route grants pull/push for qbit-monitor, ruckus-bot,
ruckus_bot and jtmb-dev. No credential changed or value was printed, no image
was published, and no registry was invented. Repository-backed owned source/
publication implementation and actual rollout acceptance remain to finish.
