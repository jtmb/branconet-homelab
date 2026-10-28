# Promoted Ruckus DB: read-only live and restart acceptance

Source prepared only. No SQL, credential access, cluster operations or observer
execution occurred while preparing this helper. It does not start/restart the
DB, start the bot, change grants, create resources or modify storage.

`observe-ruckusdb-promoted.py` runs on **masternode**, using its existing kubectl
context. It imports the exact reviewed `copy-observer-3284b56f3d7e.py`, SHA256
`3284b56f3d7e7f0a570d84823a3a5b3a1c8067249156450bc061af2dadda3751`, and reuses its
unaltered SQL class, native credential loader and snapshot function. It never
calls the old main, administrative snapshots or copy start/upgrade actions.

The only accepted target is namespace `ruckus`, original Deployment
`ruckus-db`, and fresh claim **`ruckus-db-data-0-security-20261025`**. The exact
candidate is
`docker.io/library/ruckusdb-security-20261023@sha256:2f0c391e6c04501862598bbc5446165f8ebba08025168451f6f6447352316349`.
No alternative claim/image/server parameters are offered.

Required chart/runtime contract:

- Original DB, bot, HelmRelease and native Secret UIDs remain unchanged.
- Bot Deployment and Flux values stay at 0; DB Deployment and Flux values are
  1, observed and Ready, with exactly one ready/current candidate container.
- The sole template volume is the new claim; its sole data mount is
  `/var/lib/mysql`, `subPath: data-0`. The normal service-account projection may
  be injected into the Pod; no other data volume/init/ephemeral container is allowed.
- Original resource requests remain exactly 25m CPU / 64Mi memory, without new
  limits. Existing envFrom remains `ruckus-db-runtime`; original default image
  command/entrypoint is used. Pod and template environment/resources must agree.
- Supplied fresh claim/PV UIDs must match the completed restore receipt, distinct
  Longhorn storage, and a claim created after the qualified archive. Claim specs
  must still match the restore proof.
- Original `ruckus-db-data-0` and its original PV remain Bound, with exact original
  UIDs and unchanged spec hashes recorded before restore. No active Pod may mount
  the original claim. The new claim may have only the promoted DB Pod as an active
  user, so root must remove the finished restore Pod before observation.
- The existing DB Service must select this Pod, and every ready Service endpoint
  must reference its UID. SQL uses the guarded Service cluster IP, not arbitrary
  DNS/host arguments.

## Proof inputs and transfer

The helper pins master-side `live-before-01.json` SHA256
`8a24bba03818d874f32ba18b705a2678e314c78d4d4f62f7839d2fa4d7f103a8`.
That baseline contains one application schema, two tables and 3,962 rows under
the original native application account. The qualified archive receipt is pinned
to `0181fa8442048910a51972a2294274aefb48dca41d98db4c8e38251e805ca30c`.
Root supplies the exact completed fresh-restore receipt SHA256. Its full-file
verification, archive/manifest lineage, target claim UID and target PV UID must
match; a readiness-only or partial restore receipt is rejected.

Root copies only this helper and the nonplaintext archive/restore receipts to
`/home/james/.local/share/branconet-migration/acceptance-ruckus-20261025/`, preserving
receipt bytes and private permissions. The original master baseline and pinned
observer already exist there. No configuration, credential values, SQL output
or grant hashes should be copied. The HMAC key is the existing private controller
key and arrives exclusively on SSH stdin; credential reads, client-option FD,
SQL results and HMAC comparisons stay in master memory. The process disables
core dumps. Receipts contain only identities, counts, hashes and booleans.

## Initial promoted observation

Run on master through the existing strict WSL SSH, with the existing HMAC key
redirected to stdin. Example master command (replace UID/path placeholders with
root's recorded values; all receipt paths must be directly inside the private
master directory):

```sh
python3 -B /home/james/.local/share/branconet-migration/acceptance-ruckus-20261025/observe-ruckusdb-promoted.py observe-promoted \
  --claim-uid "$NEW_CLAIM_UID" --pv-uid "$NEW_PV_UID" \
  --archive-receipt "$MASTER/upgraded-archive-receipt.json" \
  --restore-receipt "$MASTER/fresh-restore-receipt.json" \
  --restore-receipt-sha256 "$RESTORE_RECEIPT_SHA256" \
  --receipt "$MASTER/promoted-live-01.json"
```

For example, the WSL SSH invocation uses
`-o BatchMode=yes -o StrictHostKeyChecking=yes -o IdentitiesOnly=yes -i /home/brajam/.ssh/id_ed25519 -p 2002 james@192.168.0.4`
and input redirection from
`$FBASE/acceptance-ruckus-20261025/hmac-key.hex`.
Never place the key or application credentials in command arguments.

The same original normal-auth snapshot is captured twice and must be stable.
All accessible rows/multisets, table/column/database DDL, schema objects, server
settings, authenticated account identity, visible grant scope and native Secret
data HMAC must exactly match the original baseline. The only accepted version
change is 5.7.41 to 5.7.44. There is no data exception for natural bot activity:
the bot must stay quiesced. The system-table upgrade DDL difference reviewed on
the isolated clone is not used to relax any application/schema comparison.

## Real declared restart observation

After initial acceptance, root performs its separately authorized DB restart.
This helper does not trigger it. Supply the previous successful promoted receipt
and its exact SHA256:

```sh
python3 -B /home/james/.local/share/branconet-migration/acceptance-ruckus-20261025/observe-ruckusdb-promoted.py observe-restart \
  --claim-uid "$NEW_CLAIM_UID" --pv-uid "$NEW_PV_UID" \
  --archive-receipt "$MASTER/upgraded-archive-receipt.json" \
  --restore-receipt "$MASTER/fresh-restore-receipt.json" \
  --restore-receipt-sha256 "$RESTORE_RECEIPT_SHA256" \
  --previous "$MASTER/promoted-live-01.json" --previous-sha256 "$PREVIOUS_RECEIPT_SHA256" \
  --receipt "$MASTER/promoted-restart-01.json"
```

The Pod UID must change, and the replacement Pod must have been created after
the prior observation finished. Every other guarded identity, spec hash,
resource setting, service identity and mount remains equal. The new snapshot
must match both the original baseline and prior promoted snapshot exactly.
Reobserving the same Pod cannot pass restart acceptance. Prior observations
must use this exact helper SHA256 and the same key/archive/restore lineage.

Failed receipts use new paths and remain retained. No logs or raw SQL errors are
exported. This observer proves application-account-visible state and the guarded
storage lineage; it does not claim new administrative visibility into inaccessible
grant tables. Prior isolated all-account preservation and full encrypted archive
proofs remain required. Root owns later bot startup and broader application
acceptance; this helper performs no Discord/provider/API/bot actions.
