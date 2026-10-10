# Ansible to BORTUS API interaction

An optional externally supplied `botrus_secret` plugin resolves `GET /api/vars/lookup?key=<alias>` with `Authorization: Bearer <BOTRUS_SECRETS_KEY>` and consumes `{key,value}`. Its runtime-only cache, 10-second timeout and fatal failure behavior remain. Legacy environment/plugin names are compatibility identifiers.

Explicit aliases map namespace/Secret/key via SQLite metadata or `BORTUS_SECRET_ALIASES_FILE`; no underscore parsing occurs. Mapped credentials read Kubernetes directly. Nonsecret configuration reads SQLite. Sensitive legacy DB rows never return values or push them to the cluster. Native/API outages fail clearly (503), without fallback. Invalid Bearer is 401; missing alias/key is 404; conflicting mappings are 409.

`syncVarsToYAML()` emits lookup expressions only for nonsecret configuration and aliases with valid Ansible identifiers. Path-style aliases remain available to direct lookup but are omitted from generated group_vars. Name collisions/unsafe config identifiers fail before writing. Node inventory behavior is retained. No database-to-Kubernetes Secret sync remains.

The local dashboard runner uses independent `ANSIBLE_BECOME_PASSWORD`, `ANSIBLE_PRIVATE_KEY_FILE`, and `ANSIBLE_REMOTE_USER` environment inputs, never old DB credentials. It forwards `BOTRUS_SECRETS_KEY` and `BOTRUS_API_URL`. Container provisioning is disabled; migration uses external Ansible. No changes to lookup plugins/roles are included here.

Bootstrap/recovery must not depend on Secrets in the cluster being created. Keep credentials and operator kubeconfig independently available; migration must adapt bootstrap lookup overrides and sensitive `no_log` tasks. Do not use the old password seed workflow. See [Secrets Engine](SECRETS-ENGINE.md) and [deployment contract](BORTUS-DEPLOYMENT.md).

The optional local runner expects a separately supplied sibling k8s-rewrite/ansible-playbook tree. Kubernetes provisioning roles and lookup plugins are not included in this application-only main merge.
