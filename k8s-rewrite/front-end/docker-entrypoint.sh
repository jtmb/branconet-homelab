#!/bin/sh
set -eu
: "${BOTRUS_JWT_SECRET:?BOTRUS_JWT_SECRET must be supplied}"
: "${BOTRUS_SECRETS_KEY:?BOTRUS_SECRETS_KEY must be supplied}"
./node_modules/.bin/prisma migrate deploy
exec node server.js
