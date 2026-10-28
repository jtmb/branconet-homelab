# Retired unused WordPress claim: metadata-only recovery

Read-only verification on October 27, 22:05 UTC established that the preserved
`wordpress/wordpress-db-upstream-20261026` claim has no initialized payload.
The original claim/PV/Longhorn identities and complete original claim spec
match the retirement record. The canceled preparation explicitly executed no
cold backup, upgrade or data copy; the accepted retirement removed every
WordPress runtime object. No existing Pod references this claim.
[Exact source hashes, identities and physical proofs](../evidence/unused-wordpress-volume-lineage-20261027.json).

This conclusion is not based solely on zero allocation. Both original stopped
replicas have never been healthy, the unstarted engine has size zero, there is
no attachment ticket or last-attached identity, and read-only root checks on
both original worker hosts proved that their exact configured replica data
directories do not exist:

- workernode2: `/var/lib/longhorn/replicas/pvc-49df631b-614f-4180-b6e5-f719db4bfe2c-9945de0d`
- workernode1: `/var/lib/longhorn/replicas/pvc-49df631b-614f-4180-b6e5-f719db4bfe2c-c9520521`

No attachment, initialization, mount, snapshot, Secret-value read or deletion
occurred. The claim and volume remain Bound/preserved. Existing encrypted
control-plane recovery preserves their metadata; there are no application
payload bytes to back up for this unused destination. The retained original
WordPress application/database/Redis claims and their archives remain separate
protected datasets. WordPress stays removed from the active stack/charts.

The maintained `scripts/migration/verify-unused-retired-volume.py` records exact
source and historical receipts and refuses drift. Its only outputs are small
ownership/result metadata under the existing F-backed operation root
`platform-upstream-review-20261027/unused-wordpress-lineage-20261027`.
No scratch, tool/dependency copy or payload was created; no recovered-byte
claim is made. Regenerate with the same read-only verifier and original fixed
identity/source checks. Credentials stayed in protected terminal input/stdin.

The three missing native Backup CRs now consist of **two outstanding current
writers** (Ruckus and Ingenium) plus this verified uninitialized claim. This
closes the unused destination's payload-recovery question; it does not claim
a native backup was created or close either writer's recovery gate.
