# Jackett OS security derivative

The isolated worker1 OS-only derivative built successfully. Its exact scan at
00:52:38 UTC on October 24 reports two critical and 29 high rows, all fixable
bundled .NET findings; no high/critical OS rows remain. This does not qualify the
application for deployment. Its retained OCI SHA-256 is
`2e46638a827b3875635624f6f3d24f69db3da4c9e7d246ead5797a1a52a39bec`.
The final Dockerfile stage is named `runtime` for the isolated build entry point.
The immutable base is the current running vendor image, application v0.24.1440-ls351,
Alpine 3.22.3. Public registry config is recorded in `base-metadata.json`
without its environment. USER is unset (root); inherited ENTRYPOINT is
`/init`, CMD is unset. No USER/ENTRYPOINT/CMD/ENV/VOLUME instruction overrides
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
Bundled .NET findings remain outside this OS-only change.

## Separate same-source runtime candidate

`Dockerfile.runtime-candidate` and `prepare-runtime-candidate.py` are a separate,
unbuilt proposal. They do not replace the active OS-only Dockerfile, modify its
sealed build or authorize deployment. No host SDK installation is needed.

The original Jackett v0.24.1440 tag resolves to commit
`141e2013ecc872a51365db8491ea2728ebbbc763`. Its server and updater already target
net9.0 and the upstream pipeline publishes both self-contained for
linux-musl-x64. Microsoft currently publishes the same-major security patch
9.0.21, including fixes for CVE-2026-70188 and CVE-2026-88092, with SDK 9.0.319
and a SHA-512-pinned linux-musl SDK archive. .NET 9 remains supported through
November 10, 2026; a later major-runtime migration still needs planning.
Exact source/artifact provenance is in `runtime-candidate-metadata.json`.

The candidate verifies the source archive, SDK archive and SDK/runtime versions.
It changes only the eight 9.0.14 Microsoft/System package references in the server
and Common projects to existing official 9.0.21 NuGet versions. It checks the
expected original project layout and records that every C# source file stayed
byte-identical. It rebuilds both server and updater under the original application
version, sets RuntimeFrameworkVersion 9.0.21 and retains the resulting dependency
locks and per-file hashes. This is genuine compilation and publish output, never
a replacement of manifest version strings over old binaries.

Builds use one MSBuild worker and only the official NuGet source. Each publish
uses `--no-restore` after the recorded restore. The generated locks must be
exported/reviewed for reproducible future locked restores; they are not yet
generated or qualified. Upstream net471 targets/tests are not run by this
linux-musl-x64 candidate. Its final stage keeps Alpine 3.22, the existing LSIO
`/init`, identity handling, port and `/config` contract; SDK/Python/restore caches
stay out of the runtime. The full old image-layer application bundle is replaced
with rebuilt server output and the updater files, following upstream packaging.

Before adoption, review a new source seal and unchanged resource/capacity limits;
build the candidate in a distinct attempt, verify both actual .NET runtime packs,
scan the exact image unsuppressed, and inspect inherited image metadata. Require
an encrypted cold configuration backup, preserved configured indexers/API identity,
server API functionality, a nonmutating updater/version invocation, existing
consumer queries and restart persistence. The published-dependency checks alone
do not prove any of these live behaviors. Existing NuGet 2.3.9 dependencies and
other residuals remain visible to the scanner rather than being silently changed.

The reviewed chart must explicitly set `AUTO_UPDATE=false`. The inherited LSIO
service otherwise invokes `jackett_launcher.sh` when auto-update is enabled,
which can overwrite this patched bundle with a vendor build. Do not change or
print Secret values to achieve this; use a reviewed explicit chart environment
override. No chart has been changed by this candidate preparation.

Additional primary sources: [same-version server project](https://github.com/Jackett/Jackett/blob/141e2013ecc872a51365db8491ea2728ebbbc763/src/Jackett.Server/Jackett.Server.csproj),
[upstream packaging pipeline](https://github.com/Jackett/Jackett/blob/141e2013ecc872a51365db8491ea2728ebbbc763/azure-pipelines.yml),
[Microsoft release metadata](https://builds.dotnet.microsoft.com/dotnet/release-metadata/9.0/releases.json),
[support lifecycle](https://dotnet.microsoft.com/en-us/platform/support/policy/dotnet-core),
[LSIO service command](https://github.com/linuxserver/docker-jackett/blob/78c06f56945f7f12f56c0de211c7a238c64cbcc3/root/etc/s6-overlay/s6-rc.d/svc-jackett/run).

Primary sources: [vendor source revision](https://github.com/linuxserver/docker-jackett/blob/78c06f56945f7f12f56c0de211c7a238c64cbcc3/Dockerfile),
[Alpine branch main index](https://dl-cdn.alpinelinux.org/alpine/v3.22/main/x86_64/APKINDEX.tar.gz).
See [cluster maintenance scope](../../docs/CLUSTER-SECURITY.md).

The first private runtime build verified SDK/runtime9.0.21 but failed before
NuGet restore: inherited vendor `TMPDIR=/run/jackett-temp` exists only after
LSIO startup, so MSBuild could not create its temporary directory. The build
stage now explicitly uses `/tmp` for TMPDIR/TMP/TEMP; the final runtime inherits
the original vendor path unchanged. Failed run40048484731 and its exact artifact
remain retained. This is a build-only fix, not runtime acceptance.
