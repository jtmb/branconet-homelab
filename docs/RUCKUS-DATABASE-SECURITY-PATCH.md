# Ruckus database and runtime security cutover

The database now runs5.7.44 on a separately restored Longhorn claim. The original
5.7.41 claim remains intact for rollback. Both normal-auth observations, including
a real Flux-declared restart, preserved every original application row, schema,
account identity and native Secret fingerprint: one schema, two tables,3,962 rows.
The bot's unchanged native bcrypt binary passed positive/negative verification
under Node22.23.4 before one normal bot instance was restored through Flux.

```mermaid
flowchart LR
  O[Retained original PVC:5.7.41] --> A[Complete encrypted cold archive]
  A --> C[Isolated full tmpfs copies]
  C --> U[Official5.7.44 upgrade and all-account comparison]
  U --> Q[Authenticated qualified encrypted archive]
  Q --> N[Fresh Longhorn claim:subPath data-0]
  N --> D[Normal-auth DB and real restart accepted]
  D --> B[Single bot through Flux]
```

Original source claim UID:`2f604004-b45f-4061-bdc4-43f5ca2f7fd8`.
New claim`ruckus-db-data-0-security-20261025`, UID
`0bf707c8-628e-4284-9aa0-35b711c8749b`; PV UID
`d6706cd4-91a7-449f-a41f-8434108f047e`. Both claims retain the Helm keep policy.
The new claim was created after the qualified archive, with no dataSource and
no preexisting data. Restore mounted only that new claim; original source PVC/PV
specs and native credentials remained unchanged. All restored files, owners,
groups, modes and nanosecond timestamps were rechecked against the complete
archive manifest. The restore Pod/policy were then removed using recorded UIDs.

The original encrypted archive contains216,491,611 file bytes; cipher SHA256
`d9055b97e35af0afc9b2d6a9379697dd8b889e1633c27d5822e840e726cf86e0`.
The qualified upgraded archive covers all290 files/213,330,338 file bytes;
cipher SHA256
`b9fe57342ddeac73e1877788f24d520d501e19cd3a483020c3a583878cf52fe8`.
Both full archives remain authenticated and retained. No root password was
looked up/reset and no production account/grant bypass was used for cutover.

Before upgrade, all administrative SQL state matched between full original/new
copies, including all six grant tables and every credential/privilege column.
The actual bundled mysql.time_zone_transition table has119,560 rows; only its
fixture bound was set to200,000, while the100,000 app-table bound stayed fixed.
After the official mysql_upgrade and restart, every row/grant/account/setting
and other DDL still matched. The sole reviewed DDL change was
`mysql.gtid_executed` gaining`STATS_PERSISTENT=0`, explicitly issued by
[MySQL5.7.44's upgrade script](https://github.com/mysql/mysql-server/blob/mysql-5.7.44/scripts/mysql_system_tables_fix.sql#L733).
The initial strict failed comparison and all preflight/restore failures remain.
Both copied databases then passed normal authentication with the original
Kubernetes application credential and identical full application state.

Private proof roots use`FBASE` from[local storage](LOCAL-BUILD-STORAGE.md):

| Proof | SHA256 |
| --- | --- |
| qualified archive receipt |0181fa8442048910a51972a2294274aefb48dca41d98db4c8e38251e805ca30c|
| completed fresh restore |26ad95198e83ca170d721ad020b4994edb1c7e1cd8f40026ebf9f193a3b84f6b|
| promoted-live-02.json |4cd16c0d6cd006a20a17766750ed29d50c62ab30fcf9ed4260e2ef75795c0940|
| promoted-restart-01.json |0695ce75843f00da6897192efe4db90fce465ce8a540c232fab5815904134369|
| stopped temporary-copy cleanup |ec6595e9bf719007d8b2430e57cda3377cb3b54792d1cd127e3a0301b0278aff|

The app observers are under`FBASE/acceptance-ruckus-20261025`. The fresh restore
is under`FBASE/ruckus-upgraded-cold-20261025/restore-7cb2181d5197445e9cea2956455814c9`.
Native ABI receipt`bot-abi-31f41d99849d.json` proves original bcrypt bytes,
positive/negative synthetic checks and loading of the actual MySQL/Express/Discord
modules. It used a finite deny-all Pod without credentials, API token or volumes;
no application or gateway session started, and all owned fixture resources were
removed. Production bot restoration is charts commit384c86b931dc1163b7869aa55b59090e521d1972;
DB declared restart is7ede53e0237b6c42d5c7f15f4f0f760ce71921b8.

Repeatable restore is wrapped by the disabled-default Ansible
`playbooks/ruckus-qualified-restore.yml`; plan is read-only and restore requires
the explicit archive hash, fresh claim UID and precreated Pod/policy UIDs.
See[archive/restore](../scripts/migration/ruckusdb-qualified-copy-archive.md)
and[promoted app checks](../scripts/migration/observe-ruckusdb-promoted.md).

These patches do not make MySQL5.7/OracleLinux7 or the bot's old Next14 closure
supported. Raw final scans remain visible: database5 critical/89 high and
bot10 critical/140 high, with the exact package/available-fix review retained.
A modern database/application migration needs its own compatibility work; no
zero-vulnerability or personal-login claim follows from the preservation checks.
