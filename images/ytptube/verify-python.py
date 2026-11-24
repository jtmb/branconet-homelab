"""Build-time inventory gate; image/runtime and real downloads still need QA."""
import importlib.metadata as metadata
import importlib.util
import json
import os
from pathlib import Path
import shutil
import stat
import sys
import sysconfig

if len(sys.argv) not in (2, 3) or sys.argv[1] not in ('system', 'app'):
    raise SystemExit('Expected selected interpreter and optional verification phase')
phase = sys.argv[2] if len(sys.argv) == 3 else 'packages'
if phase not in ('packages', 'strip-bootstrap', 'runtime'):
    raise SystemExit('Unexpected verification phase')

if phase == 'strip-bootstrap':
    # Image-build-only removal of complete install/bootstrap functionality, not
    # scanner metadata. No application, config, cache or data directory is used.
    if sys.version_info[:2] != (3, 13) or sys.prefix not in ('/usr/local', '/opt/python'):
        raise SystemExit('Unexpected immutable interpreter layout')
    standard_library = Path(sysconfig.get_path('stdlib'))
    if standard_library != Path('/usr/local/lib/python3.13') or standard_library.resolve() != standard_library:
        raise SystemExit('Unexpected standard-library bootstrap layout')
    bootstrap = standard_library / 'ensurepip'
    removed = []
    if bootstrap.exists():
        if not bootstrap.is_dir() or bootstrap.is_symlink() or bootstrap.resolve() != bootstrap:
            raise SystemExit('Unexpected ensurepip package path')
        shutil.rmtree(bootstrap)
        removed.append(str(bootstrap))
    scripts = Path(sysconfig.get_path('scripts'))
    if scripts not in (Path('/usr/local/bin'), Path('/opt/python/bin')) or scripts.resolve() != scripts:
        raise SystemExit('Unexpected installer script layout')
    for name in ('pip', 'pip3', 'pip3.13'):
        shim = scripts / name
        try:
            entry = shim.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(entry.st_mode):
            # The immutable official Python base creates this untracked alias.
            # uv removes its tracked pip3 target; unlink only the known alias,
            # including when dangling, without reading/following its target.
            if scripts != Path('/usr/local/bin') or name != 'pip' or os.readlink(shim) != 'pip3':
                raise SystemExit('Unexpected leftover installer symlink alias')
            shim.unlink()
            removed.append(str(shim))
            continue
        if not stat.S_ISREG(entry.st_mode) or entry.st_size > 16384:
            raise SystemExit('Unexpected leftover installer entry point')
        if 'from pip._internal.cli.main import main' not in shim.read_text():
            raise SystemExit('Installer entry point did not match its expected implementation')
        shim.unlink()
        removed.append(str(shim))
    print(json.dumps({'interpreter': sys.executable, 'removedInstallerBootstrap': removed}))
    raise SystemExit(0)

expected = {'certifi': '2026.10.19', 'msgpack': '1.2.1', 'urllib3': '2.8.0'}
if sys.argv[1] == 'app':
    expected.update({'yt-dlp': '2026.10.21', 'yt-dlp-ejs': '0.8.0',
                     'aiohttp': '3.14.4', 'curl_cffi': '0.15.0', 'urllib3': '2.8.0'})
for package, version in expected.items():
    if metadata.version(package) != version:
        raise SystemExit('Required Python package version mismatch: ' + package)
import certifi
import msgpack
import urllib3
if msgpack.unpackb(msgpack.packb({'bounded': [1, True, 'ok']})) != {'bounded': [1, True, 'ok']}:
    raise SystemExit('MessagePack round-trip failed')
if urllib3.__version__ != expected['urllib3']:
    raise SystemExit('urllib3 imported version differs from distribution metadata')
if certifi.__version__ != '2026.10.19':
    raise SystemExit('The runtime certificate bundle remains outdated')
if phase == 'runtime':
    for name in ('pip', 'setuptools'):
        try:
            metadata.distribution(name)
        except metadata.PackageNotFoundError:
            pass
        else:
            raise SystemExit('An install-only distribution remains in the runtime')
    for name in ('pip', 'setuptools', 'pkg_resources', '_distutils_hack', 'ensurepip'):
        if importlib.util.find_spec(name) is not None:
            raise SystemExit('An install-only module remains importable in the runtime')
    for name in ('pip', 'pip3', 'pip3.13'):
        command = Path(sysconfig.get_path('scripts')) / name
        if command.exists() or command.is_symlink():
            raise SystemExit('An install-only command remains in the runtime')
if sys.argv[1] == 'app':
    import aiohttp
    import curl_cffi
    import yt_dlp
    if not Path(yt_dlp.__file__).is_relative_to('/opt/python'):
        raise SystemExit('Extractor is not loaded from the immutable application venv')
print(json.dumps({'interpreter': sys.executable, 'prefix': sys.prefix,
                  'packages': expected, 'certifi_path': certifi.__file__,
                  'installer_absence_verified': phase == 'runtime'}, sort_keys=True))
