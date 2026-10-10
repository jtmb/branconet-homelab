# BORTUS workflow guide

The application lives at `k8s-rewrite/front-end/`; its documentation lives at repo-root `docs/`. This main-branch publication includes the dashboard and application runtime. Existing Swarm sources remain in place. Kubernetes charts, provisioning roles and Flux source changes are separate deployment work.

## Local setup

1. Enter `k8s-rewrite/front-end` and run `npm ci`.
2. Configure an untracked `.env` from `.env.example` using independently supplied signing/lookup credentials and a SQLite `DATABASE_URL`. Keep signing material stable across restarts.
3. Supply operator `KUBECONFIG` or `~/.kube/config`, `BORTUS_SECRET_NAMESPACES` and optional metadata-only aliases via `BORTUS_SECRET_ALIASES_FILE`.
4. Run `npm run db:deploy`, then `npm run dev`. Open `http://localhost:4000` and register the first user, which receives the `write` role.
5. Check cluster resources and native Secret metadata. Import native values externally before enabling their consumers. See [deployment contract](BORTUS-DEPLOYMENT.md).

For an existing database, make a consistent backup and assess migration history before deployment. Never reset a production database to make migrations pass.

## Configuration and Secrets

Use **Configuration** (`/configuration`) for nonsecret SQLite settings. Use **Secrets** (`/secrets`) for native Secret metadata and, as a write user, explicit reveal and key CRUD. Create refuses existing keys; update/delete require the current resourceVersion. Unrelated keys, type and metadata are preserved. Deleting the last Opaque key retains an empty Secret object.

Register exact alias/namespace/name/key mappings using `/api/secret-references` or the alias JSON file. Underscores and path-style aliases are not parsed into destinations. Bearer lookup returns mapped native values or nonsecret configuration; legacy sensitive SQLite rows are excluded, including during outages.

See [API usage](API-USAGE.md), [Secrets engine](SECRETS-ENGINE.md) and [permissions](USER-PERMS.md). Protect browser and Bearer traffic with TLS outside loopback development.

## Provisioning integration

Container provisioning is disabled. Provision or recover a cluster from an independent operator environment with independently available credentials. The optional local dashboard runner expects Ansible and a separately supplied sibling tree at `k8s-rewrite/ansible-playbook/`, including `playbooks/` and `inventory/production.ini`. That Kubernetes provisioning tree is not supplied by this application-only merge.

`POST /api/vars/sync` generates lookup expressions and inventory for that optional tree. It never generates Secret values. Local runner inputs are `ANSIBLE_BECOME_PASSWORD`, `ANSIBLE_PRIVATE_KEY_FILE`, `ANSIBLE_REMOTE_USER`, `BOTRUS_API_URL` and `BOTRUS_SECRETS_KEY`. Bootstrap must work while the target cluster is unavailable. Use sensitive task `no_log` handling in the external playbooks.

## Cluster and Flux operations

The dashboard lists nodes, namespaces, pods, deployments, services, ingresses and storage using externally supplied Kubernetes credentials. Database node records describe inventory; creating a record does not provision a machine or join it to Kubernetes.

The **Flux** view reflects installed Flux resources and the repositories configured in the target cluster. Publish manifests to that configured source and path. Adding BORTUS source to `main` does not switch the cluster's Flux branch. See [Flux guide](FLUX-GITOPS.md) and [connection guide](CONNECTING-TO-A-CLUSTER.md).

The write-role terminal executes shell commands with the application's operating-system permissions as well as its Kubernetes permissions. Treat write accounts as operators with application-host access.

## Validation

Run `npm test`, `npm run typecheck`, `npm run build`, then `npm run test:integration`. The HTTP integration suite requires the production build and uses temporary SQLite, fake credentials and a loopback unavailable Kubernetes endpoint. It does not access the operator database or live cluster.

Image and live-cluster evidence are separate from those local checks. See [recorded evidence and runtime contract](BORTUS-DEPLOYMENT.md).