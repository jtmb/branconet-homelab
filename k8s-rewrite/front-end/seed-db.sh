#!/bin/sh
# The old helper posted credentials into SQLite and ignored authentication errors.
# Native Secrets now own values; use authenticated configuration/Secrets UI or the migration importer.
printf '%s\n' 'Seed helper retired. Use /configuration for nonsecret settings and /secrets for native credentials.' >&2
exit 1
