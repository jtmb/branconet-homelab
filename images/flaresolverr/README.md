# FlareSolverr 3.5.2 OS/browser and Python security derivative

Prepared source only: no image build, scan, preload or rollout is claimed.
The base is the deployed vendor 3.5.2 immutable index
`sha256:c80ae007ce2ccdcd217a12426e4f039ef763ff90738c808d38810c3e59323767`.
`base-metadata.json` records the SHA-verified public OCI linux/amd64 manifest and
config, excluding environment. Its USER is `flaresolverr`; ENTRYPOINT is
`["/usr/bin/dumb-init", "--"]`, CMD is
`["/usr/local/bin/python", "-u", "/app/flaresolverr.py"]`, WORKDIR is `/app`,
VOLUME is `/config`, and ports are 8191/8192. Only the build's maintenance step
switches to root; the final USER is restored. All other configuration is inherited.

`verify-os.py` refuses other OS/architecture/repository tracks. Existing signed
Debian 12 bookworm main/security repositories are retained; no repository or key
is added. APT upgrades installed OS packages without removing packages, explicitly
upgrading Chromium/common/driver together. All three package versions must be
identical and at least `156.0.8078.47`; actual browser and driver versions must
match them. Availability is checked by the future build, not assumed here.

The vendor Dockerfile **moves** chromedriver from `/usr/bin/chromedriver` to
`/app/chromedriver`. Merely upgrading its Debian package would leave the app using
the old driver. This recipe replaces only that exact relocated regular file from
the upgraded package, preserving its original owner/group/mode. Before/after
hashes bind all remaining `/app`, `/package.json`, and `/usr/local` Python files,
including symlink targets and permissions/ownership. A mismatch fails the build.
Evidence remains under `/usr/share/branconet-security/flaresolverr/` in the image.
These original `before.json`/`after.json` receipts describe only the OS phase:
`pythonDependenciesChanged: false` remains accurate for that phase and neither
receipt is rewritten by the subsequent Python phase. This image runs plain
Python source, not a PyInstaller executable.

The October 23 exact-base scan had 32 critical/1091 high package/advisory rows,
926 with recorded fixes; 903 fixable rows were Chromium/common/driver. The retained
OS-only CI run `40055919730`, attempt 2, OCI archive SHA-256
`401007465e152d36dd5aee1df706cf6bdbe31ab905ecf0d4fc6014a24a8d3441`
scanned to 5 critical/197 high rows. Its five fixable critical/high rows were
certifi, two urllib3 advisories, and setuptools-vendored jaraco.context/wheel.
That observation is not a clean verdict or final Python-image acceptance.

The additive Python phase uses the existing `/usr/local/bin/python` and pip,
with exact official-wheel URLs/SHA-256 in `requirements-security.txt`, no index,
resolver, dependency updates, source builds or bytecode compilation. It installs
certifi 2026.10.19, urllib3 2.8.0 and setuptools 83.0.0. Inspection of the actual
SHA-verified setuptools wheel established Python >=3.10 support and embedded
jaraco.context 6.1.0 / wheel 0.46.3, including their actual source code. Python
3.11 is retained. There is no installer/metadata/SBOM stripping or relabelling;
normal package replacement retires superseded distribution files.

The actual retained OS artifact's vendored UC 3.5.5 patcher imports
`packaging.version`, and no application Python file references `pkg_resources`
or `distutils`; direct imports of those modules were also absent from installed
non-setuptools/non-pip dependency sources. This matters because setuptools 83
no longer includes `pkg_resources`. Final CI imports the unchanged actual UC,
Flare module (without executing its `__main__` server/browser), requests/selenium,
updated certifi/urllib3 and both fixed setuptools vendor modules. The verifier
checks their exact paths, vendor source SHA-256, distribution versions, actual
CA-bundle parsing and `pip check`; final imports must also pass as the inherited
nonroot USER. These are build checks, not a browser retrieval acceptance claim.

`verify-python.py` writes separate exclusive `python-before.json` and
`python-after.json` receipts. Only the exact old/new RECORD-listed files of those
three distributions can change, within their fixed distribution roots. Removed
old files must actually be absent. All remaining application, `/package.json`,
Python interpreter/dependencies, and the OS-upgraded `/app/chromedriver` retain
hashes, modes, ownership and symlink targets. Both original OS receipt hashes
must remain identical. An exact unsuppressed new-image scan must report all
remaining findings; no final image build or native import result is claimed by
this source preparation.

Build through the existing private artifact-only `build-security-images.yml`,
selecting `flaresolverr`. Its original capacity/resource/concurrency/credential
and no-publish/no-deployment limits remain unchanged. Retain original OCI and
provenance; verify inherited config, actual nonroot startup and browser/driver
compatibility. The live acceptance is the existing Flare API version plus a
real `request.get` browser retrieval, then route/restart checks. The user declared
`/config` disposable runtime state; no cleanup or volume deletion is authorized
by this image recipe. Chart values, Secrets, resource limits and mounts are unchanged.

Primary sources: [exact vendor Dockerfile](https://github.com/FlareSolverr/FlareSolverr/blob/93125d6ea6956906c8dfa29e169b2dc67d993dc3/Dockerfile),
[Debian Chromium package](https://packages.debian.org/bookworm/chromium),
[setuptools 83.0.0](https://pypi.org/project/setuptools/83.0.0/),
[certifi 2026.10.19](https://pypi.org/project/certifi/2026.10.19/),
[urllib3 2.8.0](https://pypi.org/project/urllib3/2.8.0/), and
[pinned UC patcher](https://github.com/FlareSolverr/FlareSolverr/blob/93125d6ea6956906c8dfa29e169b2dc67d993dc3/src/undetected_chromedriver/patcher.py).
See the repository's cluster/security image build documentation.


## FlareSolverr production acceptance, 03:53 UTC

Private charts commit `e7aad9893d9823aae489483e8fdba0dc94418c65` passed
validation `40059981764` and reconciled through Flux. The same Deployment and
HelmRelease UIDs now run the scanned immutable derivative in new Pod
`910adb88-cce7-4101-a864-386d73c1b091`. Native LOG_LEVEL/TZ references and
25m/64Mi requests remain; inherited legacy envFrom is cleared.

`qualify-flaresolverr.py` passed on the actual master: nonroot UID1000, exact
Python package versions, Chromium/ChromeDriver both 156.0.8078.47, version3.5.2
through all three node routes, and a real browser `request.get` to
`https://example.com/` returning HTTP200 with the expected page. No cookies or
page contents are retained. Receipt SHA256:
`ddc96a6f0efe73e246ef2b07f02698aa95bc7d782c3113958dfdd1c625c3cf0f`.
The 4 critical/193 high residual rows remain explicitly unfixed in the retained
database; application acceptance is not a clean-cluster verdict.
