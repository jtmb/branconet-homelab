# WordPress retirement — October 26, 22:29 UTC

The user's instruction to remove WordPress supersedes the pending database and
plugin upgrade work. WordPress, wordpress-db, wordpress-redis and phpMyAdmin
are removed from active charts and from the live cluster. No database upgrade,
data copy, credential replacement or volume deletion was performed.

Private charts main, validated and live Flux source are
`801f6b87cbc755454a5942a351c952fad9478155`. The established local validator
passed its existing checks and promoted the revision. Actions remains disabled.
There are now 29 active chart packages and 30 HelmReleases. Historical packages
and values are retained under `retired/wordpress`; validation rejects their
accidental reintroduction into the active release list.

Retirement first reconciled all four releases to zero replicas at
`19c850977bb6df7637dae25d7877c67dccc0e880`, with Helm history retention enabled.
After the final source removed the four releases, their exact UID-bound objects
were deleted to complete Helm-controller uninstall. Global Flux prune/force
settings were preserved. No deployment, Pod, Service or Ingress remains for the
four retired releases. Twenty Helm history Secrets remain.

All four PVC/PV identities and specifications remain unchanged and Bound:
`wordpress-data-0`, `wordpress-db-data-0`, `wordpress-redis-data`, and the unused
`wordpress-db-upstream-20261026`. The last was provisioned before cancellation;
it was never mounted or populated. Eleven native Secret identities, versions
and types are unchanged. The WordPress namespace and separately managed public
certificate are intentionally retained. Original files, MySQL data, SQL/file
backups and their authenticated NAS copies remain protected.

The unexecuted database-upgrade preparation was withdrawn from this checkout;
its exact source patch and completed read-only baseline remain private recovery
evidence. The CoreDNS maintenance check now resolves the surviving Ruckus
database Service. Its actual 18 TCP/UDP DNS checks and four health checks passed.

Final inventory: 3 Ready nodes without pressure, 57 Bound PVCs, 30 Ready
HelmReleases, all Kustomizations Ready, 87 Running Pods, 64 distinct running
images and 287 controllers including historical ReplicaSets. All attached
Longhorn volumes are healthy; there are 43 volumes total. Four older failed
diagnostic Pods remain as protected failure evidence, not active app failures.

Evidence is under the existing F-backed task root:

- `wordpress-retirement-20261026`: original ownership, uninstall preconditions,
  UID-bound completion, preserved-data acceptance and post-retirement DNS proof.
- `operator-control/wordpress-retirement-*`: final cluster/image inventories,
  publisher cleanup and authenticated recovery metadata receipts.
- `control-source/upstream-wordpressdb-20261026`: canceled preparation source
  and the exact executed read-only baseline source.

The metadata archive is 2,796,404 bytes, SHA256
`5dc7a432e0e6e097a89786f49d4b8466a13a8ef1f596c6b011f59e37cf1f64f8`.
Every member and complete NAS read-back passed age authentication using the
existing recovery destination and key backup; old backup archives were not
duplicated inside it. No plaintext secrets were committed.

Cleanup removed 533,012,480 allocated Linux bytes across 2,348 generated source,
tool and empty scratch paths. Exact paths, per-path bytes, regeneration commands,
original Git/blob and tool proofs, inactivity checks and retained exceptions are
in `operator-control/wordpress-retirement-publisher-scratch-reconciliation.json`.
Original Git sources, immutable validation/promotion receipts and reports remain.
All prior runtime, failed-state and ownership exceptions remain unchanged.
No Windows disk recovery is claimed.

The full goal remains active. Plex, remaining platform/fleet security,
owned-source publication, trusted LAN TLS and final Seerr/YTPTube IAB acceptance
remain open. BORTUS application development belongs to its separate owner chat.
