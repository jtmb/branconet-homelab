FROM node:22.23.3-trixie-slim@sha256:154ba2f4d6fec323d28e4f4bb86bba4677f1223391a1979cf521304e03a98dfa AS base
# Record the actual resulting package inventory; an immutable base and upgrade
# do not imply that every distribution advisory has an available fix.
RUN apt-get update && apt-get upgrade -y \
 && apt-get install -y --no-install-recommends ca-certificates openssl bash \
 && rm -rf /var/lib/apt/lists/*
COPY --from=bortus_kubectl /kubectl /usr/local/bin/kubectl
ARG BORTUS_KUBECTL_SHA256
RUN echo "${BORTUS_KUBECTL_SHA256}  /usr/local/bin/kubectl" | sha256sum --check && chmod 755 /usr/local/bin/kubectl
WORKDIR /app

FROM node:22.23.3-bookworm@sha256:c4d5523090a817b7aa86d2111241fdd4f66d1e27782b44160e6aa63b357ecb2d AS builder
WORKDIR /app
COPY package.json package-lock.json ./
COPY scripts/patch-zod-collections.mjs ./scripts/patch-zod-collections.mjs
RUN npm ci
COPY . .
RUN node scripts/provision-scanner.mjs /scanner
ENV NEXT_TELEMETRY_DISABLED=1 DATABASE_URL=file:/data/bortus.db
RUN npm run build && npm prune --omit=dev

FROM base AS runtime
COPY --from=builder /scanner /opt/bortus-scanner
ENV BORTUS_TRIVY_PATH=/opt/bortus-scanner/trivy BORTUS_TRIVY_CACHE_DIR=/opt/bortus-scanner/cache
# The entrypoint invokes the local Prisma CLI through node. Package managers
# are build tools; none is required to migrate, start, or operate this image.
RUN rm -rf /usr/local/lib/node_modules/npm /usr/local/lib/node_modules/corepack /opt/yarn-v1.22.22 \
 && rm -f /usr/local/bin/npm /usr/local/bin/npx /usr/local/bin/corepack /usr/local/bin/yarn /usr/local/bin/yarnpkg
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 PORT=4000 HOSTNAME=0.0.0.0 \
    DATABASE_URL=file:/data/bortus.db BORTUS_DISABLE_PROVISIONING=true
COPY --from=builder --chown=node:node /app/.next/standalone ./
COPY --from=builder --chown=node:node /app/.next/static ./.next/static
COPY --from=builder --chown=node:node /app/public ./public
COPY --from=builder --chown=node:node /app/node_modules ./node_modules
COPY --from=builder --chown=node:node /app/prisma ./prisma
COPY --chown=node:node docker-entrypoint.sh ./
RUN mkdir -p /data /home/shell && chown node:node /data /home/shell && sed -i 's/\r$//' docker-entrypoint.sh && chmod 755 docker-entrypoint.sh
USER node
EXPOSE 4000
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s CMD node -e "fetch('http://127.0.0.1:4000/api/health/live').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"
ENTRYPOINT ["./docker-entrypoint.sh"]
