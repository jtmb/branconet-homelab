# BORTUS application instructions

The application is in `front-end/`; shared application documentation is in repo-root `docs/`. Main contains the app alongside the legacy Swarm sources. Kubernetes provisioning/charts and live migration remain separate work.

## Next.js

Read the relevant guide in `front-end/node_modules/next/dist/docs/` before writing code. The installed Next 15.5.27 package lacks that directory; when absent, use official versioned Next 15 documentation and heed deprecations. Route params are Promises and must be awaited.

## Documentation is part of every change

Before changing a domain, read its relevant docs. After every source change, check every file in `../docs/` and update anything made inaccurate before completion. Code and actual paths are ground truth. Preserve unrelated Swarm instructions and sources.

## Native Secrets and authentication

Read `../docs/BORTUS-DEPLOYMENT.md` and `../docs/SECRETS-ENGINE.md` before changing Secret behavior. Use explicit alias/namespace/name/key references; never split underscores. Values must not persist in SQLite, argv, generated Git files, errors or logs. Update/delete require resourceVersion, preserve unrelated data/type/metadata and retain empty objects. Readonly users list metadata; reveal and mutations require the fresh DB write role. Native outages have no fallback or push queue.

Signing material comes from stable external `BOTRUS_JWT_SECRET`; never auto-generate or persist it in SQLite. Kubernetes credentials are supplied externally. Bootstrap must remain independent of the cluster being created. Container provisioning is disabled.

## Checks

Use `npm test`, `npm run typecheck`, `npm run build` and then `npm run test:integration` in `front-end/`. Integration tests use temporary SQLite and fake credentials. Build images only from the clean Docker context; never distribute local standalone output traced from env files. Never commit env files, databases, kubeconfigs, credentials or generated build artifacts.