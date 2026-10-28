# Capacity recovered; original application-batch check passed

Worker2 now passes the unchanged Longhorn 25% plus 512 MiB guard. The original
strict verifier accepted all 14 applications and 17 volumes, using their original
images, templates, claim/volume identities and replica directories, with two
actual healthy RW replicas and mounted-data reads. All 58 claims, 14 NAS bindings,
three Ready nodes and desired controllers survive. Flux is Ready/Healthy at
`a1904230a34495dbd0ea428b8246df1f174e98d7`.
[Exact path/byte/receipt and live-state evidence](../evidence/worker2-capacity-recovery-20261028.json).

| Node | Available bytes | Unchanged required bytes |
| --- | ---: | ---: |
| masternode | 29,674,700,800 | 29,462,389,761 |
| workernode1 | 96,573,849,600 | 62,867,478,529 |
| workernode2 | 30,303,846,400 | 29,462,389,761 |

These are observations, not a reservation for future scheduling. A further
cohort must budget native image payload and unpack costs on eligible nodes.
The original failed capacity result and its insufficient placement budget remain
in the [batch history](LONGHORN-APPLICATION-BATCH-20261028.md).

## Exact cleanup

Recovered **3,154,370,560 allocated node Linux bytes** on worker2:

- **3,004,600,320 bytes / 71 qualified filesystem-cache directories**, individually
  listed in the evidence. Only the native snapshot API was used. All image
  records and 95 original OCI blobs were retained and fully authenticated,
  including uncompressed layer identities. Complete process, mount, descriptor,
  unit, container, lease and image/parent/child exclusions passed.
- **149,770,240 bytes** from only `helm` (65,916,928), `kubectl` (61,890,560) and
  `gitleaks` (21,962,752) under
  `/home/james/.local/share/branconet-migration/charts-validation-20261023-70daf1e5ec72/source/.tools`.
  Their Windows originals and all 341 sibling file identities remain unchanged.

The first native operation stopped at one NotFound response after 32 direct
acknowledgements. That key was not retried. A fresh qualification covered seven
other remaining keys and all seven removals completed. The final stable native
metadata and filesystem projection proves all original 71 target paths absent,
all 575 other backend IDs preserved and no orphan directories. There are 39
direct acknowledgements; 32 additional qualified paths were observed absent.
Parent cache collection is consistent with vendor behavior, but their individual
removal cause was not observed. The initial exit 1/journal/source remain intact.
No image/content/lease/container pruning, raw snapshot-directory deletion,
volume/data deletion, threshold change, filesystem growth or reboot occurred.

The empty `.tools` directory above remains **4,096 allocated bytes** because
`original_manifest_hash` failed. The raw manifest hash differs from its older
receipt field; this alone does not prove corruption. Do not retry its deletion
through another path or tool. The tool helper's executed-source reconstruction
is history-derived, not a source hash recorded by the original execution receipt.
That limitation remains explicit in its source-binding receipt.

All new metadata lives beneath the existing F-backed task root, in
`platform-upstream-review-20261027/longhorn-application-batch-20261028`.
`cache-recovery-inventory.json` lists each retained unique qualification,
execution, failure and data witness. No archive, dependency, extracted payload or
bulk cache was generated on the controller. Its inactive zero-byte
`native-cache-qualification/operation.lock` was removed after full Linux reference
and exclusive Windows handle checks; all source and evidence survive. Earlier
protected original/failed-safety-check exceptions remain protected. Linux
allocated recovery is separate from Windows free space; no VHDX recovery is
claimed.

Both host operations have opt-in Ansible entrypoints:
`retired-native-unpack-cache.yml` and `retired-worker2-validation-tools.yml`.
They default to no mutation and refuse replay of existing receipts/previously
submitted native keys. Cache regeneration uses the preserved original OCI graph
and pinned native offline unpack; tool regeneration copies the retained,
individually hash-verified original binaries.

Four old-runtime engines remain: Pi-hole two, Ingenium one and held BORTUS one.
Those cycles, final current-image/security reconciliation, original app-account/
history/restart checks, normal Seerr/YTPTube browser acceptance and final cleanup
remain in the active goal. Runtime batch acceptance does not complete the goal.
