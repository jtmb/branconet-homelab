# October 28 delivered security updates and remaining acceptance

MySQL and YTPTube security updates are deployed and their data checks pass.
The goal remains active because the authenticated Seerr browser check needs
an original account login. The trusted Seerr sign-in page itself renders normally;
no original account was reset or replaced. The user was asked for that login
during the work, while cleanup continued.

| Contract | Current evidence |
| --- | --- |
| One existing CI/CD path | Private charts main → unchanged local validation → validated → Flux; Actions remained off. |
| MySQL official security patch | Chart 0.1.7, commit `7a296bdf3828e61ae69a9c96c851afa26c8e7e03`; official root `a0225d1ea6631c8bc2385dc4c2faba17bbf1834ecf369e1659a9a382bd8d5dd7`. |
| MySQL data/identity | New Pod `4f4c7dea-f136-43b4-bcfb-91958b6e6263`; all 3,983 before rows, schema, native Secret, server identity, settings, template and storage bindings preserved. Version remains 8.4.13. |
| YTPTube official update | Chart 0.1.1, main/validated/live `21bd3bf517199e45591ae44e13bd251ee8a04ffe`; official 2.7.6 root `a5b648c6c20d877cf90715415b1b31565dda9399020d80f186000fdd76474f86`. |
| YTPTube data/identity | New Pod `3a4bda71-9f6b-4148-998f-76ea32329788`, zero restarts; original account, nine presets, history/stable tables, three claims and native Secret pass the unchanged preservation predicate. All seven original files match, 618,241,982 bytes. |
| Actual mounted runtime | Imported Brotli 1.2.1, brotlicffi 1.2.1.0 and OS libbrotli1 1.1.0-2+deb13u1 are fixed, including the original mounted Python package path. Existing pinned yt-dlp 2026.10.21, JavaScript provider, Deno and ffmpeg checks pass. |
| Normal YTPTube browser | Existing account login over trusted HTTPS; both original completed history entries visible; original H264/AAC sample plays to 00:05 / 00:05. No injected cookies or new authentication identity. |
| Seerr preservation | All six original users and credential/permission fields match; original request/media/season IDs and counts remain. Ordinary lifecycle changes and four original Sonarr link limitations are explicitly assessed in the media ledger. Authenticated browser view remains pending. |
| Cluster/storage | Three Ready nodes, all desired controllers available, 58 Bound claims, 14 SMB volumes; native Secrets and the unchanged Longhorn floor/resources remain. BORTUS release suspension and its one old runtime remain with its separate owner. |
| Matching recovery | Post-upgrade 76,921,380-byte encrypted archive, independent NAS full readback, all 46 configuration/key members verified and actual offline etcd restore. Revision 10,941,451 / 2,906 keys and complete logical-history hash match after restoration. No production restore or plaintext secret-configuration extraction. |

[Exact receipts, hashes and cleanup](../evidence/official-security-refresh-20261028.json)
bind each claim above to its actual source. The first master MySQL preload's
historical prior-record subset check remains failed, as documented in the
[preparation checkpoint](UPSTREAM-MAINTENANCE-CHECKPOINT-20261028.md). Its original
aggregate-only inventory cannot establish which historical record changed.
There was no repull. Fresh image/content/runtime/budget observations and both
worker stages passed; the actual deployed MySQL data acceptance is separate.

The first functional observer tried the cluster-only service address from WSL
and timed out without logging in. The maintained observer now uses the normal
LAN HTTPS route with the exact pinned public CA and certificate verification.
Its actual native login, runtime and retained-media checks pass. The initial
MySQL post-check also ran while Helm was still progressing; it passed after the
actual release became Ready. Neither intermediate observation is deployment
acceptance. The original first refusal/failure receipts remain intact.

## Security result and limits

All 64 distinct current runtime digests bind to complete, hash-verified October
28 r5 image reports, including both new vendor candidates. No new digest lacks
a report. The earlier 65-image inventory also included a different CSI provisioner
runtime identity; the new actual identity was already covered in the fleet scan.
Current controller/image identities are recorded explicitly rather than copied
from the old Pod inventory.

The current image reports retain 102 Critical and 2,788 High package rows, 2,403
distinct CVEs, and three KEV identifiers across other images. Counts are scanner
package rows, not 2,890 independently established reachable exploits. Vendor
image availability differs from a package's listed fixed version. The compatible
new official MySQL and YTPTube updates remove their Brotli KEV findings; host
Brotli is fixed on all three nodes. Other reviewed vendors still ship affected
packages, and the unmerged BORTUS application release remains its separate owner's
responsibility. No bespoke vendor rebuild, CVE suppression, zero-CVE result or
absence of undisclosed zero-days is claimed. Current feed validity ends October
29 at 07:10 UTC. Full residual detail stays in the bound reports.

## Exact checkpoint cleanup and retained exceptions

After the preceding 4,732,964,864-byte native cache checkpoint, removed another
864,673,792 allocated worker2 Linux bytes from ten qualified superseded MySQL
unpack-cache paths. Every original image/blob remains. The new image caches on
all three nodes now have the concrete production scheduling/restart consumer.

Removed another 586,055,680 allocated controller Linux bytes: two consumed
publisher exports (177,860,608 each), post-restore disposable scratch
(213,725,184), four inactive zero-byte serialization locks and the regenerated
etcdutl tool/empty parent (16,609,280). Full Linux reference checks and independent
exclusive Windows handle checks passed. Etcdutl regeneration was proven by a new
complete 16,601,250-byte in-memory export from the unchanged pinned live etcd
container; the exact SHA-256 matches. No bulk re-export was saved. All original
source, lockfiles, ciphertexts, keys, failures and minimal receipts remain.

Retain the exact new `post-upgrade-control-plane-checkpoint-20261028/restore-ansible-scratch`
after its native Windows exclusive-read check returned access denied (5).
It was not deleted, chmodded, chowned or retried. Earlier protected empty tool
directory and root-owned packaging exceptions remain unchanged. Retain the
65,241,088-byte original volume restore kit: its exact recorded old engine
producer path has been removed by the supported engine retirement, so current
hash-identical regeneration has not been proven. It remains the matching kit for
the 74 retained Completed original native backups, until an exact regeneration
source or independently qualified replacement exists. This specific preservation
exception did not stop cleanup of the independently regenerable etcdutl copy.

Unique current before/after/hash reports, three small browser screenshots and
authenticated recovery ciphertexts remain under the same F-backed task root.
There are no new dependency trees, local image archives or extracted build
payloads. Linux recovery is not Windows free-space recovery; no WSL shutdown,
VHDX compaction or disruption of Strata occurred.
