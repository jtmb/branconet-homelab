# YTPTube security derivative preparation

The October 23 master builder is retained for status/stop only after the Seerr
attempt caused filesystem pressure. Private charts CI and image builds are now
approved, but its first runner failed the disk reserve preflight. Worker1's safely
expanded filesystem supports the separate guarded worker1-only builder after
full original-resource recovery. The retired master attempts stay frozen.

This directory prepares a local security derivative of the exact official
YTPTube v2.7.5 image, without rebuilding or changing application features.
The first worker1 derivative built successfully at 23:34:07 UTC and its exact
OCI scan completed at 00:00:10 UTC on October 24. It is not an upstream-signed
artifact. That scan found one critical and 72 high rows, including four high
rows with fixes. The revised recipe below is source preparation, not a rebuilt,
rescanned or accepted application.

The immutable base is
`ghcr.io/arabcoders/ytptube:v2.7.5@sha256:3ba09ac58f0b541aa7182feb9198b44d3c62158a7749ec00d26de1abad7ca8d7`.
Use this directory as build context. The pinned uv installer is linux/amd64;
other architectures are outside this prepared recipe.

## Retained production-host attempt (execution disabled)

The single final Dockerfile stage is named `runtime`.
`k8s-rewrite/ansible-playbook/playbooks/ytptube-image-build.yml` uses the separate
`ytptube_image_build` role. The controller launcher is
`scripts/migration/run-ytptube-image-build.py`, with phases `setup`, `runtime`,
`status` and `stop`. There is no dependency-resolution/lock phase for this
derivative. The Seerr build role, helper and sealed remote inputs are untouched.

The historical controller layout staged Dockerfile, patch-provider.py and
verify-python.py alongside the Ansible source. It used the
already verified BuildKit 0.34.1 public binaries in controller
`/home/brajam/.local/share/branconet-migration/seerr-image-20261023/bin`.
The archive provenance remains SHA-256
`a59539daf547fe0958efe2d07e41c0a6944e1112a66d7e519ec1cf5b673ef15b`.

The historical setup used the controller's isolated venv Python and
`--phase setup --context-dir <absolute-staged-images/ytptube> --output-dir
<absolute-protected-evidence-directory>`. The root-owned credential dispatcher
supplies only `{"sudo_password":"..."}` through protected stdin. Setup hashes
each source/tool/helper, copies it into the separate root-owned 0700 directory
`/home/james/.local/share/branconet-migration/ytptube-build-20261023`, and seals
the exact bytes. It does not build. Differing or incomplete prior stages refuse
overwrite. Do not pass a password in argv, settings files or logs.

The former `--phase runtime` dispatch selected only
`bortus-ytptube-build-20261023-runtime.service`, asynchronously. The supervisor,
standalone daemon/client and OCI executions share the reviewed ancestor with
3 GiB RAM, no swap, 150% CPU, allowed CPUs 0-1, 512 tasks and a four-hour limit;
actual cgroup limits are checked. The proven delegated-control-child and
Dockerfile-frontend cgroup-parent mechanics match the separate Seerr builder.
It uses a private empty HOME/DOCKER_CONFIG, native snapshotter, parallelism two,
no CDI and no containerd worker/socket, registry secrets or application mounts.

Only a successful `runtime-finished.json` with archive hash/size establishes
build completion; launcher zero establishes dispatch only. Retained output is
`ytptube-security-20261023.oci.tar` beside build metadata and private logs.
Use `status` for sanitized phase/resource/artifact metadata and `stop` only for
this exact owned runtime unit. All files and caches remain for review. Sequence
builds with the coordinator and finish/stop builders before master maintenance.
Only setup ran for this retained attempt; runtime never dispatched. Current
Ansible refuses both setup and runtime, preserving inspection/stop operations.

## Dependencies and remaining acceptance

The recipe upgrades the existing Debian 13 package set without removing
packages, and checks curl at least `8.14.1-2+deb13u7` and libexpat1 at least
`2.9.0-1~deb13u1`. It does not switch Debian releases or repositories.
Package index resolution remains time-dependent; retain the resulting package
inventory and scan the exact final image digest.

The official final image has a relocatable uv application environment at
`/opt/python` and a separate system interpreter at `/usr/local/bin/python3`.
The final image does not copy the builder's uv executable and does not guarantee
pip in the venv. A checksum-pinned uv 0.13.5 download therefore installs into
each exact interpreter. Both receive certifi 2026.10.19. The app environment also
receives yt-dlp 2026.10.21, EJS 0.8.0, aiohttp 3.14.4, curl_cffi 0.15.0 and
urllib3 2.8.0. Following the exact-image scan, both interpreters additionally
receive msgpack 1.2.1 and urllib3 2.8.0, rather than assuming
the application's updated copy eliminates a second inherited distribution.
Build checks assert each interpreter's distribution versions, exercise a local
MessagePack round-trip, import urllib3, and assert that the
extractor comes from the immutable venv. These are focused security updates;
they do not establish yt-dlp/provider compatibility or actual YouTube access.

The previous r2 build verified both interpreters had patched normal packages,
including setuptools 83.0.0, but its scan retained the old installer-vendored
versions. Official pip 26.2.2 actually vendors msgpack 1.1.2, urllib3 2.7.0 and
the pkg_resources portion of setuptools 70.3.0, and carries their CycloneDX BOM.
The actual immutable base uses CPython 3.13.16, whose official ensurepip source
bundles a complete pip 26.2.1 wheel. Updating
the normal distributions does not patch those separate copies. These are not
dismissed as false positives or fixed by deleting a BOM/version record alone.

The revised recipe uses uv for the package installation, then uninstalls complete
pip/setuptools distributions from both exact interpreters. It removes the entire
fixed ensurepip bootstrap package, including its bundled wheel, and any strictly
recognized leftover pip entry points. The uv installer itself is also removed.
Those are image-layer installation tools, never application/config/NAS paths.
Final per-interpreter checks require pip, setuptools, pkg_resources,
_distutils_hack and ensurepip to be nonimportable, their distribution metadata to
be absent and installer commands to be gone, while patched runtime imports and
the MessagePack round-trip continue to pass. A fresh image scan must establish
the resulting residual findings; no new build or removal is claimed here.

Private CI run `40051139401` passed provider/runtime-package checks and both uv
uninstalls, then refused a leftover installer entry point. Root's immutable-layer
metadata established the exact cause: official Python provides regular `pip3`
and `pip3.13` scripts plus an untracked `/usr/local/bin/pip -> pip3` symlink.
Removing the tracked pip distribution leaves that alias dangling. The source
correction uses lstat/readlink and unlinks only this exact known relative alias,
without following or reading its target. Foreign aliases, absolute targets,
other paths and unexpected regular scripts still refuse. Final command-absence
checks include dangling symlinks. The original failed CI log/artifact remain
retained; a replacement build and scan are not claimed by this source fix.

Static review of all 79 non-test application Python files in the v2.7.5 source
found no direct import of pip, setuptools, pkg_resources or ensurepip. The updater
imports stdlib metadata, packaging and HTTP helpers; it invokes `python -m pip`
only when installation is requested. This is not proof that every optional
third-party feature works without installers. Application startup, core imports,
provider access and a real download must still pass against the final digest.
If a genuine dependency requires pkg_resources, stop and address that dependency
rather than silently bypassing import checks.

Runtime package installation is intentionally unavailable in this derivative.
Keep `YTP_YTDLP_AUTO_UPDATE=false`, `YTP_PIP_IGNORE_UPDATES=true`, an empty
`YTP_PIP_PACKAGES` and no nonempty `/config/pip.txt` lines. The ignore-updates
flag alone only disables upgrades: upstream still tries to install configured
missing packages. Fresh isolated configuration is required; do not carry legacy
installer overlays or pip configuration into the new app. In-place package
changes require a newly built/scanned image instead.

The provider's scanner-identified
`/opt/bgutil-provider/node_modules/follow-redirects` is replaced with official
1.16.1 and `node_modules/ip-address` 10.7.3 with 10.7.4, each after verifying its
fixed official SHA-512 npm integrity. Existing deno.lock,
package-lock.json and hidden npm lock metadata are updated together. No npm
lifecycle scripts or unrelated dependency reinstall runs. The provider remains
started by upstream's existing Deno command. Its exact pinned lock shape and a
real provider request must be qualified after building.

The inherited tini entrypoint, application CMD, healthcheck, working directory,
port and `app` UID 1000 are retained. Automatic extractor updates default false.
Do not deploy with the earlier chart's `YTP_YTDLP_AUTO_UPDATE=true` or
`PYTHONPATH=/config/python3.13-packages:/app`: those settings can replace the
qualified immutable packages with a writable overlay. Use fresh isolated
configuration and remove that overlay path from environment. The current chart
candidate uses a new subdirectory on the existing healthy Longhorn state claim,
preserving legacy queue files, with large temporary downloads on the existing NAS.
Preserve original MeTube
state and NAS downloads. No chart or production configuration was changed here.

The original scan reports unfixed critical libxml2 CVE-2026-6653 and 68 high
findings without fixes. A package upgrade does not prove these are resolved.
The first derivative scan still reported msgpack 1.1.2, setuptools 70.3.0 and
urllib3 2.7.0 with no package-path attribution, plus provider ip-address 10.7.3.
The revised recipe updates both known interpreters and the exact provider path,
then removes complete installer/bootstrap implementations and their vendored trees;
only a fresh resulting scan establishes whether other inherited copies remain.
Do not invent paths, suppress findings, or claim this image is clean. Updated
only the resulting scan can establish which inherited copies remain.

Before adoption, build with retained logs, inventory every normal/vendored
Python copy and provider lock, scan OS/language packages in the exact final
digest, and review all remaining findings. Run as UID 1000 with a fresh /config,
preserved /downloads and separate temporary space; verify Deno/EJS/FFmpeg and
provider health, local login, a bounded actual YouTube download, playable
audio/video, queue/history persistence and restart. HTTP 403, cookie/IP/token
restrictions remain possible. A successful build or healthcheck is insufficient.

The prepared [operator acceptance helper](../../docs/YTPTUBE-ACCEPTANCE.md)
separates absent-only native Secret bootstrap, one bounded actual YouTube sample,
and post-restart history/media verification. It binds the original three PVC UIDs
and a cold legacy fingerprint baseline; it does not itself observe sibling MeTube
state through the application's config subPath. Root must separately verify that
preservation. No acceptance helper mode has been run by this source preparation.

Official sources: [release Dockerfile](https://github.com/arabcoders/ytptube/blob/v2.7.5/Dockerfile),
[startup updater](https://github.com/arabcoders/ytptube/blob/v2.7.5/app/upgrader.py),
[uv environments](https://docs.astral.sh/uv/pip/environments/),
[uv 0.13.5](https://github.com/astral-sh/uv/releases/tag/0.13.5),
[follow-redirects metadata](https://registry.npmjs.org/follow-redirects/1.16.1),
[pip 26.2.2 vendored versions](https://github.com/pypa/pip/blob/26.2.2/src/pip/_vendor/vendor.txt),
[pip BOM and vendoring rules](https://github.com/pypa/pip/blob/26.2.2/pyproject.toml),
[CPython bootstrap wheel](https://github.com/python/cpython/blob/v3.13.16/Lib/ensurepip/__init__.py),
[official Python installer alias](https://github.com/docker-library/python/blob/master/3.13/slim-trixie/Dockerfile),
[upstream installer behavior](https://github.com/arabcoders/ytptube/blob/v2.7.5/app/library/PackageInstaller.py).
