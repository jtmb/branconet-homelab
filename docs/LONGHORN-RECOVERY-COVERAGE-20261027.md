# Current Longhorn recovery coverage

**22:05 UTC update:** original cancellation/retirement lineage, unchanged claim
spec/UID chain, unstarted engine/never-healthy replicas, no consumers/tickets and
read-only physical absence of both configured replica directories establish
that the unused WordPress destination has no initialized payload. Its preserved
metadata is covered by control-plane recovery. No artificial initialization or
native backup was performed. **Two current-writer recovery gates remain**:
Ruckus and Ingenium. Three missing native Backup CRs include this unused claim;
these are distinct counts. [Exact physical/source proof](UNUSED-WORDPRESS-VOLUME-LINEAGE-20261027.md).

**22:03 UTC update:** retained old Ruckus now has a completed native NAS backup,
independent all-block encrypted raw restore and normal detach. The original
replica survived; normal manager reconciliation restored its existing desired
two-replica configuration before the backup. Nine datasets total 542 verified
blocks. Three native-backup gaps remain: current Ruckus and Ingenium writers,
and the unused WordPress claim. [Exact newer proof and capacity caveat](DETACHED-VOLUME-NATIVE-RECOVERY-20261027.md).

**21:24 UTC update:** retained `pihole/pihole-data-1` also passed completed native
NAS backup, normal detach and independent raw restore: 73 additional blocks.
Eight retained datasets now total 376 verified blocks. Four native-backup gaps
remain: retained old Ruckus, current Ruckus and Ingenium writers, and the unused
WordPress claim. The original 58 claim bindings and 44 volume UIDs survive.
[Eighth dataset and exact limitations](DETACHED-VOLUME-NATIVE-RECOVERY-20261027.md).

**20:08 UTC update:** seven datasets from the historical gap table below now
have completed full native NAS backups and independently verified encrypted raw
restores, with scratch reconciled. All 303 blocks passed. The five remaining
native-backup gaps are the two current writers, old Ruckus, old Pi-hole claim 1
and the unused WordPress claim. [Exact newer evidence and limitations](DETACHED-VOLUME-NATIVE-RECOVERY-20261027.md).
The table below remains the original 18:32 discovery record.

Read-only observation at October 27, 18:32 UTC. All three nodes are Ready without
pressure. All 58 original claim UID/binding pairs and 44 Longhorn volume
UID/name pairs match the morning preflight. All 28 attached volumes are healthy
with two actual RW replicas; 16 volumes are detached. Backup target remains
available; the existing configuration SystemBackup remains Ready.
[Exact identities, settings and gaps](../evidence/longhorn-recovery-coverage-20261027.json).

Twelve volumes still have no completed native Backup CR. That fact neither
proves absence of an independent archive nor qualifies current recovery:

| Dataset | State | Existing evidence / remaining requirement |
| --- | --- | --- |
| `ruckus/ruckus-db-data-0-security-20261025` | Detached | Historical copied recovery source; cold and restore lineage in RUCKUS-HA-RECOVERY.md. Bind the exact retained directory contents to the authenticated archive. |
| `ruckus/ruckus-db-upstream-20261026` | Attached | Current MySQL 8.4 writer. Cutover cold archive covers the earlier source and original rows; it is not a fresh backup of current 8.4 state. |
| `ingenium/ingenium-state` | Attached | Separate owner's current active state. Preserve its verification hold; coordinate a consistent checkpoint after that interval. |
| `pihole/pihole-data-0`, `pihole/pihole-data-1` | Detached | Retained partial migration claims, distinct from the live retry1 claims. Live Pi-hole cold backups cannot be substituted without exact content evidence. |
| `plex/gluetun-data-1`, `plex/qbittorrent-data-0` | Detached | Retained earlier claims. Current application acceptance does not prove byte-level recovery of these separate datasets. |
| `bortus/bortus-restore-b473091bebef` | Detached | Retained restore fixture. Bind fixture provenance and every retained file to its original archive/restore evidence. |
| `wordpress/wordpress-db-upstream-20261026` | Detached | Retirement evidence says never mounted/populated. Observed allocation zero alone is insufficient; preserve the claim and verify that historical lineage. |
| `migration-system/migration-storage-restored` | Detached | Retained restore fixture; establish exact producer/archive binding. |
| `migration-system/migration-storage-proof` | Detached | Retained storage proof; preserve unique witnesses and establish exact producer binding. |
| `migration-system/migration-nas-bortus-restore` | Detached | Retained NAS restore fixture; establish exact archive/restore binding. |

No dataset was mounted, attached, modified or deleted by this observation.
No Secret values were read, backups requested or images pulled. Native Secrets
and volume-encryption-key recovery are separately covered by the
[fresh control-plane checkpoint](FRESH-CONTROL-PLANE-RECOVERY-20261027.md);
that checkpoint contains no application-volume payloads.

The fixed maintained read-only preflight source, source ownership and three small
live/receipt/coverage metadata files remain under the existing F-backed root:
`operator-control/fresh-recovery-coverage-preflight-{20261027.py,ownership-20261027.json}`
and `platform-upstream-review-20261027/longhorn-preflight-recovery-mapping`.
No build/dependency/cache/raw data scratch was created. Regeneration is the
same pinned read-only preflight into a fresh evidence namespace. All original
source, archives, runtime and failures remain protected. No recovered-byte claim
is made for this observation. The full upgrade and migration goal remains active.
