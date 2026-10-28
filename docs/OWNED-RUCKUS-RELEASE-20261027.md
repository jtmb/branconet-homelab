# Repository-backed Ruckus release — October27, 2026

Ruckus now runs from its owned application repository and existing Docker Hub
route. Its database, original accounts/password hashes, native Secrets, storage,
published ports and application behavior are preserved. Production and a separate
Flux restart passed the data, source, process and route checks below.

- Source: [jtmb/ruckus_bot](https://github.com/jtmb/ruckus_bot/tree/cedb2b32694368ed73883ec8f34459879b1e857e), commit `cedb2b32694368ed73883ec8f34459879b1e857e`, branch `codex/production-source-maintenance-20261027`.
- Runtime: `docker.io/jtmb92/ruckus-bot:git-cedb2b32694368ed73883ec8f34459879b1e857e@sha256:f63dd607ee435d24c6b5e97aaecd044b0e3dba5b872db9ff9d3fd8bc4463dd69`.
- Production charts `7501fd96a7a9bd7f0c1f470cbbc0f7b6b1e45f10`; restart/main/validated/live `3a8de93a4034780519bac191bf4a02b4a4c96f96`.
- Production Pod `5620d86a-d579-4b3b-a5a3-ef1b3f40e802`; restarted Pod `f44f5798-4448-49d4-8b25-cc0538d7c23c`.

## Source and runtime

The original repository was a filtered, unmaterialized clone with5,290tracked
generated node_modules entries. Only75real source/assets were imported, with
every original Git blob verified; generated dependencies were never checked out.
The new branch retires those generated index entries, while the original branch,
history and blob objects remain. No dirty checkout was reset or cleaned.

Of48original application source/assets compared with production,46matched. The
two existing live dashboard changes were carried into the maintained source.
Production dependencies now have four committed v3 locks and a repository-owned
lock-refresh operator. It uses the existing supported Windows Node/npm, Linux
target metadata, disabled install scripts and explicitly scoped cache/AppData/temp
under the single F-backed task root. No host node_modules or user-setting change
was created. A helper filename typo failed before execution and was corrected;
both failure and successful exact-tool receipts remain.

The maintained official Node22.23.4 Trixie slim base is pinned by digest. A
checksum-bound official npm12.2.1 is used only to build. API dependencies include
Express4.22.3, bcrypt6.0.0 and mysql2 3.24.6; the bot uses Discord.js14.27.0,
axios1.20.0 and the same maintained callback mysql2 client. The dashboard builds
with Next16.4.3/React19.3.1 and one build worker. Application SQL/schema and native
credential references are unchanged.

Supervisor retains all three program names, working directories, logging,
restart policy and the `bot_run` restart target. It directly runs the existing
API/bot entry points and built Next dashboard on the original ports. Development
npm/npx/nodemon/Yarn/Corepack are excluded from runtime. This avoids shipping
vulnerable bundled npm dependencies without modifying third-party package code.

The owned publisher exports only committed source, uses the existing Docker Hub
account in memory, refuses immutable-tag overwrite, and checks remote manifest,
configuration and source/revision labels. No Actions, new registry, plaintext
credential file or saved-image deployment was used. Source/build/locks/update
instructions are in the owned repository. Its original/default branch remains.

## Security result and limits

The first published candidate was scanned and held before any deployment.
Its [proxy-addr issue](https://github.com/jshttp/proxy-addr/security/advisories/GHSA-jqcg-44mw-7w3h)
is fixed with the locked2.0.8 override. Runtime npm removal also removes its
affected [undici6.29.0](https://github.com/nodejs/undici/security/advisories/GHSA-xjj6-f33q-929c)
and ip-address10.7.2 packages. The first image/source/scan remain recovery evidence.

The promoted exact image was rescanned against the new digest-verified public feed
updated October27,01:25UTC and current CISA catalog. Stored feed bytes passed two
independent readbacks; input hashes were reverified after scanning. No suppression
was used. Results cover102OS packages and219Node packages: **0Critical,65High,
96Medium,78Low and6Unknown package findings**, representing95unique CVEs.
There are **no findings with a listed fixed version and no CISA KEV matches**.
The remaining findings are Debian packages without available fixed versions in
that feed, including Supervisor's Python dependencies. These are explicit residual
findings, not a clean-image or unknown-zero-days assurance. Raw results remain.

An existing application finding also remains: Ruckus's API permits unauthenticated
user/log reads through its Service and published node ports. Both original and
promoted GET observations returned200; source write routes also lack authorization
middleware. No account/data mutation or exploit test was performed. Dependency
maintenance does not establish API authorization, and remediation is not claimed.

## Actual acceptance

The baseline captured3,976application rows. Production and the separate restart
preserved every original keyed row, schema/table metadata, database server identity,
settings, original accounts/password hashes, native Secret identities/content,
claims/backing volumes, Services, Ingresses and unrelated workload fields. The
existing MySQL8.4.13 Pod was neither replaced nor restarted. One ordinary bot-login
row appeared after each application startup; the final comparison includes two
new rows and no missing original rows.

Each rollout passed28API/dashboard checks across its Service and all three
published node addresses. All59committed runtime source/configuration files
matched. Native bcrypt compatibility passed, exact dependency/Node versions were
verified, and unused development launchers were absent. Supervisor reported all
three programs RUNNING; real gateway-ready and normal bot SQL log activity were
observed in memory. No raw application logs, Discord test message, account creation
or data-changing verification SQL was saved/executed. Personal login and browser
acceptance are not claimed here; final IAB remains after implementation.

The frozen executed observer is `scripts/migration/verify-owned-ruckus-release.py`.
Exact baseline/production/restart sources and receipts are in the existing task
root's `owned-ruckus-release-20261027` directory. The baseline source was preserved
by reconstruction against its exact recorded SHA256 before adding runtime checks.

## Cleanup and recovery

All generated work stayed in the existing F-backed task root, ext4UUID
`3c792469-ea0e-4a2c-98e8-1185b141607b`. Both builders were bounded to3GiB RAM,
zero swap,1.5CPU and512processes, then stopped/removed. The first successful build
measured1,520,365,568allocated bytes. The corrected build used a2GiB hard budget
based on that measurement and its reduced runtime. All C:/F: capacity floors
remained15GiB; transient insufficient-RAM preflights created no builder and their
failure evidence remains. No Strata/user workload was stopped.

Removed **3,585,335,296 allocated Linux bytes**. Exact removed paths, bytes,
source/registry/creator/inode/hash checks, complete process/FD/maps/mount checks,
regeneration commands and retained exceptions are in these `operator-control`
receipts under the same task root:

| Reconciliation receipt | Removed allocated bytes |
| --- | ---: |
| `owned-ruckus-build-scratch-reconciliation.json` |1520365568|
| `owned-ruckus-final-build-scratch-reconciliation.json` |1490423808|
| `owned-ruckus-auxiliary-scratch-reconciliation.json` |217927680|
| `owned-ruckus-publisher-scratch-reconciliation.json` |355409920|
| `owned-ruckus-review-scratch-reconciliation.json` |1208320|

These remove both private builds' state/context/client/socket, scoped npm scratch,
the exactly Git-reproducible text import packet, two empty failed-preflight target
sets, two terminal private chart source/tool exports, scan cache and empty Helm
directories. Original Git/source/locks, required published runtimes, scans,
failure evidence, unique receipts, original cold SQL backups and data remain.

Initial guards retained the whole targets before deletion. Exact creator proofs
bound Yarn's UID503 files to the verified pinned base-layer bytes, Apt's UID42
empty directories to its account/transaction, and all OverlayFS0/0 whiteout links
to the same terminated private build. A Linux zombie with unavailable mountinfo
was verified as StateZ with no file descriptors; no process was stopped to force
cleanup. Other source/inode/process/container/mount protections remained intact.
The prior `operator-control/tmp/system-commandline-sentinel-files` and parent
remain: creator/regeneration and complete inactive Windows-handle proof are still
missing. No older failed cache, shared image, volume, source or user data was pruned.
No Windows disk recovery is inferred from these Linux allocation measurements.

New recovery metadata is8,747,300bytes, SHA256
`ceab450ff5795ccb24730174533860445a251e8f24c9de5e7801171a9234b186`.
Every encrypted metadata member and complete NAS ciphertext readback authenticated
using the existing recovery identity/protected key backup. Original cold
ciphertexts and earlier metadata archives were not duplicated into this package.

At02:48UTC, three nodes were Ready without pressure,57claims Bound, all30releases
and all Kustomizations Ready, and87Pods Running. Longhorn has43volumes total:
27attached healthy and16detached. Four old failed diagnostic Pods remain preserved.
The fresh64-image ownership inventory accepts all three migration-owned releases;
BORTUS's intentionally suspended release stays with its separate owner.

Remaining work: platform security updates/reconciliation, Windows client trust,
final Seerr/YTPTube IAB and final fleet/security acceptance. The full goal is active.
