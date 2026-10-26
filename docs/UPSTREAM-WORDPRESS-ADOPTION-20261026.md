# WordPress upstream adoption

Accepted backend/state/restart checkpoint: October26,21:06UTC. The full
migration/security goal remains active; this does not close WordPress database,
plugin, platform/fleet, owned publication, TLS or final browser work.

Official WordPress7.1.3 / PHP8.3.36 Apache replaces the temporary bespoke image:
`docker.io/library/wordpress:7.1.3-php8.3-apache@sha256:e5a724ec7ad9055f48b2941ac1b674b08e77ed60edb8937a6254fb89ec45ddf7`.
The amd64 manifest is
`sha256:806680ba62232c4c300fb9dcc9f89d08e9e8c2bfc59837a1f58716f8648306d5`.
The current core version is confirmed by the [official release page](https://wordpress.org/download/)
and the image by the [official image source](https://github.com/docker-library/official-images/blob/master/library/wordpress).

The three private commits passed the existing local validation publisher and Flux:

| Operation | Exact revision |
| --- | --- |
| Quiesce the old application | `81f51f1997e5fe08bba1cca3a4892fa3f40c7393` |
| Activate the official image after NAS verification | `b3f388ff3b36e82beb9bece7b4bd8443cc80635c` |
| Independent persistence restart, current main/validated/live | `4fb19f9ec5620b3605a28c126e07c897004a78a9` |

The only lasting workload changes are its image and the explicit restart marker.
The original Deployment `c5b60268-c0d4-43f8-8014-4c04e427a122`, HelmRelease,
Longhorn claim `90b7695b-3cbf-41d9-b6d1-1f9ee3fd5e2f`, backing PV, Services,
requests, native Secret references/UIDs/resourceVersions, ports and routing remain.
The official entrypoint's existing-site copy guard was checked against its pinned
source. Complete comparisons confirm it did not replace persistent site files.

Both production observations passed all5662 file entries /145967967file bytes,
all12 tables and515 stable rows, including the original user's password hash,
permissions, content and settings. Standard scheduling/transient options are
excluded only from equality; the complete encrypted SQL backup retains them too.
The prior `qualify-wordpress.py` defines that finite exclusion; it was unchanged.
The twelve internal/published-node root, login-redirect and REST routes preserve
their original behavior. No personal login or final IAB acceptance is claimed.
The restarted PodUID is `6ce10f67-aea5-4835-a855-a39af3f9dbaf`, distinct from
the first official-image Pod `ec6e8ffd-91ec-449c-a632-5fb31589453d`.
All3338 checked core files matched the [WordPress7.1.3 checksum API](https://api.wordpress.org/core/checksums/1.0/?version=7.1.3&locale=en_US);
wp-content plugins/themes remain a separate audit/update scope.

Recovery uses the existing authorized F-backed task root and authenticated NAS
`\\TRUENAS\plex_smb_share\Branconet-Recovery-Backups\2026-10-25\ciphertexts`:

| Artifact | Cipher bytes | SHA256 |
| --- | ---: | --- |
| Complete cold site files, no exclusions |151998900| `ef19d1a43d1544830669db972d5048da4f9f623aaf762a975ff888275ccd4bf9` |
| Complete visible application SQL, twelve tables |1323346| `8901d8ff270ca50737103a2fcd83da4f85c7a4efea3b08e9d8da8512f0761cfd` |
| Exact source, state, route, restart, scan and cleanup metadata |10058340| `158a0fa57480e3a39650ff89c20ff46b7511a120fb428688800dcfe5580094e3` |

Every ciphertext received full NAS read-back and age authentication. Metadata
also received complete member/hash comparison. Existing recovery-key backup was
reused; no keys were rotated or printed. Cold SQL contains1322814 plaintext bytes
only within encrypted streams; no plaintext backup was written to disk.
This logical application backup does not claim a full physical MySQL/account-store
backup or a database-upgrade restoration drill.

The first file-archive verification refused the new tighter8192-entry/1GiB tuple
before reading the archive. Its failure receipt is retained. The finite verifier
now accepts that tighter profile without changing byte/hash/path/metadata checks.
A guarded resume verified the same ciphertext against the same stopped writer
and original read-only reader, then deleted that reader by exact UID. No duplicate
file archive was captured and no source or failed evidence was deleted.

Rollback is a scoped chart commit restoring only the prior WordPress image with
one replica; never revert the whole private repository and its unrelated accepted
cutovers. Both images use the same qualified core/PHP and database. If actual
state recovery becomes necessary, restore the authenticated copies into a separate
verified destination and compare them before changing the active claim.

Evidence under the task root:
`upstream-wordpress-20261026/{baseline,after,restart,core-integrity,protected-backup,chart-review}.json`;
`control-source/upstream-wordpress-20261026` retains exact executed source and
the original verifier. Operator receipts include the three successful publisher
stages, full image/owner inventory, all NAS proofs and exact cleanup reconciliation.
[Removed paths and retained exceptions](TASK-OUTPUT-INVENTORY.md#wordpress-reconciliation-october26-2106utc).

The exact official-image scan used unchanged pinned public feeds/tool and no
suppression:2Critical,160High,840Medium,1094Low,220Unknown; no matching CISA KEV
entry. One High has a vendor package fix: `CVE-2026-111497`, libbrotli1
`1.1.0-2+b7` → `1.1.0-2+deb13u1`. Findings remain open; no bespoke rebuild or
clean-security claim is made. Core integrity does not rule out unknown zero-days.
MySQL remains5.7.44. Akismet5.3.5 and Redis Object Cache2.5.4 remain installed;
upstream reports5.7.2 and3.0.0 respectively. Their updates require backed-up,
account/content/settings-preserving verification, separately from this exact
image-only comparison.

Final cluster observation:3Ready nodes without pressure,56Bound PVCs,
34Ready HelmReleases and all Kustomizations Ready,42Longhorn volumes total with
all attached volumes healthy. Four previously failed diagnostic Pods remain
preserved as evidence. GitHub Actions was freshly verified disabled.

