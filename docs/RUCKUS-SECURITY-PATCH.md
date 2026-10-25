# Ruckus database patch preparation

This is prepared source, **not a deployed or accepted patch**. The current
database is MySQL5.7.41; the candidate is the official5.7.44 filesystem with signed
Oracle Linux7 updates and unchanged MySQL binaries, entrypoint and configuration.
Both MySQL5.7 and Oracle Linux7 have support limitations; an in-train patch does
not establish that all vulnerabilities have fixes. Scan the exact built artifact
and retain its unsuppressed residual report before adoption.

The private chart repository contains `images/ruckusdb`, with pinned image/RPM
provenance and a complete source-file manifest. No build or production upgrade is
claimed. Public signing keys and fingerprints in those references are public
provenance, not cluster credentials.

## Data boundary

Read-only discovery confirmed the original `ruckus-db` Deployment UID
`cf0b7d3c-6d8f-48cb-a55f-0ccd39f610d2`, Longhorn claim
`ruckus-db-data-0` UID`2f604004-b45f-4061-bdc4-43f5ca2f7fd8`, and
`/var/lib/mysql` mount. The existing bot Deployment UID is
`dfd27794-a610-445e-b279-6e0933cf1153`. Native Kubernetes Secrets remain the
credential source. The application account is available; a database root
password is not present in its referenced Secret. No password reset, credential
recreation or old container-log scraping is planned.

The opt-in `cold-application-state-backup.yml` now admits only these exact
database/client identities for `cold_application_state_app=ruckus-db`. It requires
both original Flux releases at zero replicas, observed ready generations, no
running client Pod, no other live claim consumer, and the original database image.
It never scales either application itself. The reader is999:999 on workernode2
with strict supplementary groups, no API token, a read-only claim and no network
service. It archives the entire physical datadir without exclusions, encrypts on
the controller, authenticates the whole archive and removes only its own
UID-verified reader. This covers database grant/system tables as well as app data.

New archive transfers require at least15 GiB free on Windows C: and retain15 GiB
on the destination after their bounded estimate. Check mode does not archive or
create a Pod. These new Ruckus source paths have passed Python/Ansible syntax
checks; their actual cold execution remains pending.

## Remaining execution and acceptance

1. Build under the existing bounded offloaded builder, scan the exact digest,
   review residuals and preload through the guarded Ansible path.
2. Quiesce the bot and database through the sole local-validation/Flux owner;
   capture and fully authenticate the original cold datadir archive.
3. Restore a disposable complete copy. Use network-disabled, local-socket-only
   maintenance for the original grant tables; qualify `mysql_upgrade` and a normal
   authenticated restart before considering the original volume. The upgrade
   tool can reload privileges, so do not assume unauthenticated reconnect remains
   possible throughout. Preserve original authentication hashes and grants.
4. Compare every original app table/row and credential/grant identity privately;
   qualify app-account authentication, bot connectivity and restart persistence.
   Estimated row counts are not acceptance evidence.
5. Apply only the qualified operation to the original claim, restore both
   releases, and verify their identities, readiness and data. Retain the old image
   and encrypted full datadir for rollback. Do not downgrade a datadir modified
   by a newer server; restore the original cold archive for rollback instead.

This work does not alter the separate WordPress database or BORTUS application.
