# BORTUS Secrets Engine

Kubernetes native Secrets are the authoritative value store. BORTUS uses a TLS-verified Kubernetes client; SQLite stores identities, nonsecret configuration and explicit `SecretReference` metadata. Legacy sensitive DB rows are ignored, never pushed at startup/CRUD and never used as outage fallback.

## Mapping and API

References have `alias`, `namespace`, `name`, `key`. Register via `/api/secret-references` or a metadata-only JSON array mounted as `BORTUS_SECRET_ALIASES_FILE`. See [deployment contract](BORTUS-DEPLOYMENT.md). No underscore parsing occurs: `openvpn_user` remains an exact data key. Preserve legacy aliases explicitly, including `secret_plex_smb-creds_password`; unmapped sensitive lookups error instead of reading old DB values.

`GET /api/vars/lookup?key=<alias>` retains Bearer `BOTRUS_SECRETS_KEY` authentication and `{key,value}`. Aliases resolve from Kubernetes; nonsecret configuration resolves from SQLite. Encrypted-flag, secret/system-category, secret-prefixed and known credential names cannot return DB values. Invalid Bearer: 401; missing alias/key: 404; Kubernetes/config/RBAC outage: 503; collisions: 409. Responses are private/no-store. Only this exact lookup path bypasses cookie middleware.

`/api/secrets` lists object metadata and keys without values for authenticated users. Value reads and all mutations require fresh DB role `write`. `/secrets` supplies explicit editing/reveal and resourceVersion protection. Readonly users see metadata only. Nonsecret `/api/vars` stays separate.

Create refuses existing keys. Update/delete require `resourceVersion`; concurrent changes return 409 without retry. Preserve unrelated data, type, labels, annotations and owner references. Immutable Secrets refuse changes. Last-key deletion keeps an empty object. Namespaces must already exist and be allowed by `BORTUS_SECRET_NAMESPACES`. The text API rejects non-UTF-8 binary keys on read.

## Provisioning

For typed Secrets that require specific keys, the Kubernetes API may reject deletion of a required last key; BORTUS returns a fixed error and leaves the object intact. Opaque last-key deletion retains an empty object.

`POST /api/vars/sync` writes lookup references for nonsecret config and explicit aliases plus inventory. No Secret manifests/value-bearing arguments are generated. Old sensitive rows do not enter files. Alias/config collisions and unsafe config identifiers fail before writing. Path-style aliases remain directly queryable but are omitted from generated Ansible identifiers. No delayed push queue exists.

Bootstrap credentials must come independently from the operator environment. Container provisioning is disabled. Existing `botrus_secret` plugin and `BOTRUS_*` env names remain compatible. Migration must remove old database secret tasks, import explicit mappings and supply independent bootstrap vars/no_log handling; application development does not edit Ansible roles here.

## Security and recovery

Values use authenticated API bodies and process memory; Secret payloads never enter argv, generated Git files, API errors or app logs. Fixed errors suppress Kubernetes exception bodies. Scope Roles per namespace; service-account list access itself reads values. Browser/Bearer traffic requires TLS. Follow [Kubernetes Secret guidance](https://kubernetes.io/docs/concepts/configuration/secret/) for RBAC and storage protection; base64 is not encryption.

JWT signing material is external and stable, never auto-persisted. Existing sensitive SQLite rows/historical backups require operator cleanup after import verification. Native values survive app restart independently of DB. SQLite loss requires user/config/alias recovery; Kubernetes loss requires protected etcd/Secret recovery. No Vault/SOPS/Git value backend is introduced.

Root independently verifies the [combined eighteen-request/flat16 controls](../evidence/bortus-combined18-flat16-controls-root-20261012.json): all ten admission, cancellation, fresh-credential, namespace, redaction, size, aggregate, item and deadline sections pass on actual loopback HTTPS, alongside 3,674 native grammar cases and eight generic tests. The exact native ELF is loaded; all owner queues drain to zero. Actual runner/container/supervisor/dispatcher exits are zero within the original 60-second bound (24.59 seconds); 1,723 current source/compiled hashes are unchanged, and independent fresh checks prove four process identities and the exact container absent. This qualifies the isolated evaluation controls, not performance, source adoption or deployment. The separately approved single six-profile timing observation uses no control getter.

The [root combined single observation](../evidence/bortus-combined18-flat16-observation-root-20261012.json) retains all 28 originals. The original driver, runner and container exit 0 with six complete native inventories; supervisor and dispatcher exit 1 because their postcheck wrongly expects paired-run-only `runtime_harness_sha256` in direct driver output. That failure is preserved and no benchmark is replayed. Independent metadata-only review binds the pre-dispatch driver hash, verifies all 15 core-only module records and six actual native loads, recomputes 25 latency fields, checks 1,723 current source/compiled hashes and freshly proves four process identities plus the exact container absent. Secret HTTP times are 140.56/90.77/94.97/171.01/206.90/189.03 ms for 334/200/1,000/10,000/25 large/three maximum-size records; all expected inventories are complete. Whole-fixture CPU is 35.55 seconds and peak memory 566.69 MiB, without throttle or OOM. This single observation has no contemporary paired baseline or significance claim; five cases are descriptively slower and memory higher than the prior eight-request/flat16 candidate medians. Eighteen requests is not adopted, canonical source remains at eight, and A07/A21 remain open. Warm Pod and alias hot paths require separate source work; native concurrency does not change their calls.
