FROM node:22.23.4-alpine3.23@sha256:206878a60dc7014193f418ab9259b6110c15fbd514b3044a267be706509944e4 AS base
RUN apk update && apk upgrade --no-cache && apk add --no-cache tzdata tini \
    && corepack enable && corepack prepare pnpm@10.24.0 --activate
ENV PNPM_HOME=/pnpm NEXT_TELEMETRY_DISABLED=1
ENV PATH=/pnpm:$PATH
WORKDIR /app

FROM base AS source
ADD --checksum=sha256:162d3a03627fd663fa394abcf239ec0b9e219670036d1fa53c950cfba462d2a4 https://codeload.github.com/seerr-team/seerr/tar.gz/564bfb08b54caa374bddaf820abfd226e5e69151 /tmp/source.tar.gz
RUN tar xzf /tmp/source.tar.gz --strip-components=1 -C /app && rm /tmp/source.tar.gz
COPY security-overrides.json /tmp/security-overrides.json
COPY apply-overrides.cjs /tmp/apply-overrides.cjs
RUN node /tmp/apply-overrides.cjs

FROM source AS resolve
RUN pnpm install --lockfile-only --ignore-scripts
FROM scratch AS lock
COPY --from=resolve /app/pnpm-lock.yaml /pnpm-lock.yaml

FROM source AS dependencies
COPY pnpm-lock.yaml /app/pnpm-lock.yaml
RUN apk add --no-cache python3 make g++ && CYPRESS_INSTALL_BINARY=0 pnpm install --frozen-lockfile \
    && node /tmp/apply-overrides.cjs --mail-types

FROM dependencies AS build
ARG COMMIT_TAG=v3.5.1-branconet-security-20261023
ENV COMMIT_TAG=$COMMIT_TAG NODE_OPTIONS=--max-old-space-size=2048
RUN CYPRESS_INSTALL_BINARY=0 pnpm build && rm -rf /app/.next/cache

FROM dependencies AS production-dependencies
RUN pnpm prune --prod --ignore-scripts

FROM node:22.23.4-alpine3.23@sha256:206878a60dc7014193f418ab9259b6110c15fbd514b3044a267be706509944e4 AS runtime
RUN apk update && apk upgrade --no-cache && apk add --no-cache tzdata tini \
    && rm -rf /usr/local/lib/node_modules/npm /usr/local/lib/node_modules/corepack \
    && rm -f /usr/local/bin/npm /usr/local/bin/npx /usr/local/bin/corepack /usr/local/bin/pnpm /usr/local/bin/pnpx
WORKDIR /app
ARG COMMIT_TAG=v3.5.1-branconet-security-20261023
ENV NODE_ENV=production COMMIT_TAG=$COMMIT_TAG
LABEL org.opencontainers.image.title="Seerr with Branconet security dependency patches" \
      org.opencontainers.image.source="https://github.com/seerr-team/seerr" \
      org.opencontainers.image.revision="564bfb08b54caa374bddaf820abfd226e5e69151"
COPY --from=source --chown=node:node /app/ /app/
COPY --from=production-dependencies --chown=node:node /app/node_modules /app/node_modules
COPY --from=build --chown=node:node /app/.next /app/.next
COPY --from=build --chown=node:node /app/dist /app/dist
RUN mkdir -p config && touch config/DOCKER \
    && printf '{"commitTag":"%s"}\n' "$COMMIT_TAG" > committag.json \
    && chown -R node:node config committag.json
USER node:node
EXPOSE 5055
ENTRYPOINT ["/sbin/tini", "--"]
CMD ["node", "dist/index.js"]
