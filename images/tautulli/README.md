# Tautulli 2.18.2 maintenance candidate

This recipe derives from the exact inspected vendor candidate:

`ghcr.io/tautulli/tautulli@sha256:a4323bc09b27e265e269d79421ed3eb795083ef988bb84788eba89e5738c8005`

Its linux/amd64 manifest is
`sha256:7a7de616c6e62e5bcdb74325a20f9e6c9744b5d737a98d078ba1450abd068b1f`,
and config is
`sha256:1dfe0413a7049e55dc397478fd34decd3ce8d2ef7f3405fc8ae0ef01304c9b40`.
All ten public layer hashes were verified, totaling 73,100,349 compressed bytes.
The actual application source is `9484667bc1f2d159368a999320b8f495bbfbd00a`;
the image label `version=master` is not its application version.

## Scope and preservation

The original vendor uses Debian 13, Python 3.13.15, `/app`, `./start.sh`, and
`python Tautulli.py --datadir /config`. USER is unset/root: startup applies
PUID/PGID and then executes the application with `gosu tautulli`. This Dockerfile
does not override USER, ENTRYPOINT, CMD, WORKDIR, VOLUME, ports or healthcheck.
Only PYTHON_VERSION and PYTHON_SHA256 change to describe the actual official
3.13.17 interpreter payload; all other inherited ENV fields remain unchanged.
Both root and UID1000 import checks run during the future build without changing
the inherited runtime configuration.

The OS phase keeps the exact existing signed trixie/trixie-updates/security
sources. APT authentication and validity checks stay enabled; `--no-remove`
forbids package removal. Nineteen source-version floors cover the 63 recorded
fixable critical/high OS rows: util-linux family, curl/libcurl, gzip, PCRE2,
SQLite, libssh2, OpenSSL and perl-base. Source versions are checked explicitly
because binary epochs/wrappers on bsdutils/login must not make an old source
version appear fixed.

`os-before.json` captures hashes, modes, numeric ownership and symlink targets
for the entire application and `/usr/local`, including directories, plus signed
source/keyring hashes and installed package inventory. The OS phase must preserve
that complete tree and repository configuration. The separate interpreter phase
below retains those original OS receipt hashes, replaces only the complete
inspected CPython core and freezes every application/noncore/package file.
The subsequent Python dependency phase retains both OS and interpreter receipt
hashes unchanged; it permits only the exact dependency/installer roots below to
change. The new interpreter, every unrelated application/startup/dependency file
and noninstaller distribution metadata remain frozen during that final phase.
The build never mounts, traverses or reads `/config`, starts Tautulli, accesses
Plex, migrates a database, regroups history or sends notifications.

## Complete official CPython 3.13.17 core

Python3.13.15 is superseded. The official 3.13.16 release fixes eight security
issues (SSL contexts/hostname validation, tarfile filters, zipfile decompression,
HTTPPasswordMgr scheme handling and StringPrep) and updates bundled Expat.
3.13.17 is the current 3.13 security release; its additional change updates
embedded pip/certifi for the eMudhra incident. Installer removal alone cannot
replace the core fixes.

The donor is the exact official image
`docker.io/library/python:3.13.17-slim-trixie@sha256:fe14fd57a4c0361110eaa0c284112b189750bcb43fb04bb5d1ee7b7744027ccf`,
linux/amd64 manifest
`sha256:d879ed88565a7a3c614b980b369d4a5025a9d057b71f93d09fc6d0b2ca823a18`.
Its four layer hashes were verified, totaling 43,057,528 compressed bytes.
Both images use Debian13/trixie. Sixteen inspected ABI fields and the complete
CONFIG_ARGS are identical: shared, GIL-enabled, nondebug CPython313, x86_64,
the same extension suffix and `/usr/local` paths.

`copy-cpython.py export` runs only in that donor stage. It verifies every core
file against the retained primary-image manifest and exports 1,154 core entries
(about25MB), including runtime/stdlib, shared libraries, headers, sysconfig,
pkgconfig and console/manual metadata. **No donor site-packages, pip console
scripts or ensurepip are exported or copied.** The existing packages and their
console script `cffi-gen-src` are preserved. The runtime stage captures its
original state before the copy, atomically replaces only these core files, and
removes precisely162 obsolete old core/bytecode paths. It then verifies complete
official core identity and every unchanged app/noncore/site-package file,
including modes, numeric ownership and symlink targets. Separate before/export/
after receipts preserve all prior phase hashes; the staged core input is removed
only after that copy proof succeeds.

All82 official core ELF objects remain in the exact-file manifest. The81 runtime
ELF objects must pass ldd with no new missing library. The remaining exact
`config-3.13-x86_64-linux-gnu/python.o` is an ET_REL SDK link object with no
program headers: its complete primary digest and ELF header are checked instead,
because ldd does not apply to a relocatable object.
The sole documented exception is `_tkinter`: both the original Tautulli image
and the official donor independently lack exactly `libtk8.6.so` and
`libtcl8.6.so`, while containing their optional GUI extension. Root reviewed
retaining that inherited headless-image gap without adding Tk/Tcl/X11 packages.
The complete official `_tkinter` code remains present; it is neither excluded
nor hidden from vulnerability analysis. This is not a claim that all ELF
dependencies resolve. No other missing dependency is allowed.

Future build checks require actual Python3.13.17, the inspected ABI, SSL/ctypes/
SQLite imports and Expat>=2.8.5. Final root and UID1000 imports additionally
exercise Tautulli's actual Requests/PlexAPI/cffi/cryptography/OpenSSL dependencies,
new vendored code and CA parsing without starting the app or accessing user data.
Source/static ABI inspection is preparation, not proof those future runtime
checks or an exact new-image scan have passed.

## Actual Python paths

The retained scan records five fixable Python rows, all inside pip 26.2.1's
vendors: certifi 2026.6.17, msgpack 1.1.2, pkg_resources/setuptools 70.3.0 and
urllib3 2.7.0. Installing newer top-level packages would leave those copies in
place. The inspected latest pip 26.2.2 fixes its certifi copy but still vendors
the other affected versions; this recipe does not use a blanket pip upgrade.

Tautulli additionally loads **`/app/lib` first**. It has real vendored certifi
2026.7.22 and urllib3 2.7.0 directories, without their normal distribution
metadata. A regular site-packages install would not replace the application's
imports. This recipe replaces precisely those two vendored directories using
the official, exact hash-pinned certifi 2026.10.19 and urllib3 2.8.0 wheels.
Every wheel member and its complete RECORD are verified; actual package code,
licenses and distribution metadata are retained. Superseded package code is
removed as part of replacement. Existing overlapping paths keep their original
modes/ownership; unrelated application and library files stay frozen.

The complete install-only pip distribution, console scripts and `ensurepip`
bootstrap are removed, including their actual vulnerable vendor code. This is
not metadata/SBOM stripping: runtime distribution metadata is preserved and new
wheel metadata is installed with its real code. Before removal, build checks
the exact original installer and repeats the static startup/application/runtime
dependency import review. The normal vendor startup has no installer command.
Future checks require pip/ensurepip to be absent on disk and unimportable, and
the actual application import order to resolve the new certifi/urllib3 code.
Requests, PlexAPI, cffi, cryptography, OpenSSL and SQLite must still import;
the updated certifi trust bundle must parse without a network request or TLS
bypass. Bytecode generation is disabled.

Runtime package installation and `python -m venv` with pip bootstrap are no
longer available. Before adoption, the operator must verify that effective
production environment, custom startup/package configuration and external
notification scripts do not rely on those capabilities. This source recipe
does not establish that production prerequisite.

## Remaining execution and migration gates

No image build, vulnerability scan or deployment is established by source
preparation. The private artifact-only build workflow/operator allowlists now
include the exact seventh `tautulli` identifier and fixed local alias. Their existing resource, capacity,
publication and credential boundaries when wiring it later. Retain the exact
OCI/provenance and perform an unsuppressed new-image scan; report residuals
honestly rather than forecasting zero critical/high findings.

Before a 2.16.1-to-2.18.2 application cutover, retain and authenticate the full
encrypted cold `/config` archive, database/WAL pairs, API key and Plex/device/
notification configuration. Preserve all users and history rows/fingerprints,
qualify the actual schema changes, existing API authentication and Plex/library
connectivity, normal routes and restart persistence. Review removed `get_apikey`,
OneSignal-to-push-relay behavior and history regrouping changes. Do not call
removed setup APIs, regroup production history or send notifications as a probe.
An image-only downgrade after a data migration is not a rollback procedure;
retain the original full state and image together.

Primary sources: [vendor Dockerfile](https://github.com/Tautulli/Tautulli/blob/9484667bc1f2d159368a999320b8f495bbfbd00a/Dockerfile),
[vendor startup](https://github.com/Tautulli/Tautulli/blob/9484667bc1f2d159368a999320b8f495bbfbd00a/start.sh),
[application import order](https://github.com/Tautulli/Tautulli/blob/9484667bc1f2d159368a999320b8f495bbfbd00a/Tautulli.py),
[certifi 2026.10.19](https://pypi.org/project/certifi/2026.10.19/),
[urllib3 2.8.0](https://pypi.org/project/urllib3/2.8.0/),
[pip 26.2.2](https://pypi.org/project/pip/26.2.2/) and
[Debian package information](https://packages.debian.org/trixie/).
Interpreter advisories: [Python3.13.16](https://www.python.org/downloads/release/python-31316/)
and [Python3.13.17](https://www.python.org/downloads/release/python-31317/).
