# Current Longhorn recovery coverage

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

The fixed maintained read-only preflight source, source ownership and four small
live/receipt/coverage metadata files remain under the existing F-backed root:
`operator-control/fresh-recovery-coverage-preflight-{20261027.py,ownership-20261027.json}`
and `platform-upstream-review-20261027/longhorn-preflight-recovery-mapping`.
No build/dependency/cache/raw data scratch was created. Regeneration is the
same pinned read-only preflight into a fresh evidence namespace. All original
source, archives, runtime and failures remain protected. No recovered-byte claim
is made for this observation. The full upgrade and migration goal remains active.
