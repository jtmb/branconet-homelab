# Pi-hole OS security derivative

Prepared source only; no build, scan, preload or deployment has been dispatched.
The final Dockerfile stage is named `runtime` for the isolated build entry point.
The immutable base is the current running vendor image, application 2026.02.0,
Alpine 3.23.3. Public registry config is recorded in `base-metadata.json`
without its environment. USER is unset (root); inherited ENTRYPOINT is
`start.sh`, CMD is unset. No USER/ENTRYPOINT/CMD/ENV/VOLUME instruction overrides
that contract. Existing chart configuration, mounts, PVCs and Secrets are unchanged.

The only package mutation is `apk upgrade --no-cache` through the existing
same-branch main/community repositories; a branch/repository guard refuses other
tracks. This preserves vendor application files, checked by before/after SHA-256
lists. It does not run the application, its updater, or any configuration migration.
The built image retains actual old/new package versions, Alpine release and
application hashes under `/usr/share/branconet-security/`. `package-candidates.json`
is the dated repository comparison, not evidence those versions were installed.
Alpine index hashes record retrieved public metadata; APK signature validation
occurs in the future build. No unsigned-package or untrusted-key flag is used.

An isolated build must verify its actual package delta, application hash equality,
and inherited config metadata, then run the existing unsuppressed pinned Trivy
scan before adopting an immutable derivative digest. No clean verdict is claimed.
All current critical/high baseline rows are OS packages; rebuilt scan remains required.

Primary sources: [vendor source revision](https://github.com/pi-hole/docker-pi-hole/blob/b890f5db95e837f8b94f954a25f2ea3d2dc54765/src/Dockerfile),
[Alpine branch main index](https://dl-cdn.alpinelinux.org/alpine/v3.23/main/x86_64/APKINDEX.tar.gz).
See [cluster maintenance scope](../../docs/CLUSTER-SECURITY.md).
