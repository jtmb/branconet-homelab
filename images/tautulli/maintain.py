#!/usr/bin/env python3
"""Narrow Debian/Python maintenance of the inspected immutable Tautulli image."""
import ast
import base64
import csv
import hashlib
import importlib
import importlib.metadata
import importlib.util
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import ssl
import stat
import subprocess
import sys
import urllib.parse
import urllib.request
import zipfile

ROOT = Path('/usr/share/branconet-security/tautulli')
APP = Path('/app')
SITE = Path('/usr/local/lib/python3.13/site-packages')
BOOTSTRAP = Path('/usr/local/lib/python3.13/ensurepip')
PIP = SITE / 'pip'
PIP_METADATA = SITE / 'pip-26.2.1.dist-info'
SOURCE = Path('/etc/apt/sources.list.d/debian.sources')
SOURCE_SHA = '7c723deded4f709a31e729a6ed26092b1cf64017a6cc17b5b1f1d934a8409c75'
FROZEN = {
    '/app/start.sh': 'bf8a951682bd216f05faea950a29aec45d528f47aaaee2a9b75ddd7af9d2157f',
    '/app/Tautulli.py': 'd355312f9cd3650d3bd2409ba5888f0432623fbb85d376e375fa3dd9aa8a1f5f',
    '/app/version.txt': '21eea730d222e10c388d8e51c9d8b8fda006ca2df76c6af750ef59c559600d50',
}
OLD_VENDOR = {
    '/app/lib/certifi/__init__.py': '7a52e5f4205f9b3d12a31898ceaa7e3f6837d19cc230700bcae1a9d91d1486c1',
    '/app/lib/urllib3/_version.py': 'fa032b2a1b0f88e8f45f351ecd515ae7d7754ba4204222a0413e601a0c8cf3ec',
}
# Trivy's Debian advisories concern source versions. In particular bsdutils and
# login have binary epochs/wrappers that must not make an old version pass.
MINIMUM_SOURCE = {
    'bsdutils': '2.41.5-0+deb13u1', 'curl': '8.14.1-2+deb13u7',
    'gzip': '1.13-1+deb13u1', 'libblkid1': '2.41.5-0+deb13u1',
    'libcurl4t64': '8.14.1-2+deb13u7', 'liblastlog2-2': '2.41.5-0+deb13u1',
    'libmount1': '2.41.5-0+deb13u1', 'libpcre2-8-0': '10.46-1~deb13u3',
    'libsmartcols1': '2.41.5-0+deb13u1', 'libsqlite3-0': '3.46.1-7+deb13u2',
    'libssh2-1t64': '1.11.1-1+deb13u2', 'libssl3t64': '3.5.7-1~deb13u3',
    'libuuid1': '2.41.5-0+deb13u1', 'login': '2.41.5-0+deb13u1',
    'mount': '2.41.5-0+deb13u1', 'openssl': '3.5.7-1~deb13u3',
    'openssl-provider-legacy': '3.5.7-1~deb13u3',
    'perl-base': '5.40.1-6+deb13u1', 'util-linux': '2.41.5-0+deb13u1',
}


def need(value, reason):
    if not value:
        raise RuntimeError(reason)


def sha(path):
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


def write_once(name, value):
    with (ROOT / name).open('x') as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write('\n')


def command(*args):
    return subprocess.check_output(args, text=True).strip()


def regular(path):
    info = path.lstat()
    need(stat.S_ISREG(info.st_mode) and path.resolve() == path, 'Unexpected file identity')
    return info


def tree():
    result = {}
    for root in [APP, Path('/usr/local')]:
        need(root.resolve() == root and root.is_dir(), 'Missing protected application/interpreter root')
        paths = [root]
        for folder, dirs, files in os.walk(root, followlinks=False):
            paths.extend(Path(folder) / name for name in sorted(dirs + files))
        need(len(paths) <= 100000, 'Protected tree entry bound')
        for path in paths:
            info = path.lstat()
            item = {'mode': stat.S_IMODE(info.st_mode), 'uid': info.st_uid, 'gid': info.st_gid}
            if stat.S_ISREG(info.st_mode):
                item.update(type='file', sha256=sha(path))
            elif stat.S_ISDIR(info.st_mode):
                item['type'] = 'directory'
            elif stat.S_ISLNK(info.st_mode):
                item.update(type='symlink', target=os.readlink(path))
            else:
                raise RuntimeError('Unexpected protected file type')
            result[str(path)] = item
    return result


def sources():
    need(not Path('/etc/apt/sources.list').exists(), 'Unexpected legacy source')
    active = sorted([*Path('/etc/apt/sources.list.d').glob('*.sources'),
                     *Path('/etc/apt/sources.list.d').glob('*.list')])
    need(active == [SOURCE] and sha(SOURCE) == SOURCE_SHA, 'Unexpected signed Debian source configuration')
    regular(SOURCE)
    keyring = Path('/usr/share/keyrings/debian-archive-keyring.pgp')
    regular(keyring)
    return {str(SOURCE): sha(SOURCE), str(keyring): sha(keyring)}


def packages():
    return command('dpkg-query', '-W', '-f=${binary:Package}\t${Version}\t${source:Version}\t${db:Status-Status}\n').splitlines()


def check_base(expected_python=(3, 13, 15)):
    need(os.geteuid() == 0 and sys.version_info[:3] == expected_python, 'Unexpected build user/interpreter')
    need(Path(sys.executable).resolve() == Path('/usr/local/bin/python').resolve(), 'Unexpected Python executable')
    release = dict(line.split('=', 1) for line in Path('/etc/os-release').read_text().splitlines() if '=' in line)
    need(release.get('ID') == 'debian' and release.get('VERSION_ID') == '"13"'
         and release.get('VERSION_CODENAME') == 'trixie', 'Unexpected Debian track')
    need(command('dpkg', '--print-architecture') == 'amd64', 'Unexpected architecture')
    for name, digest in FROZEN.items():
        regular(Path(name))
        need(sha(Path(name)) == digest, 'Vendor application/startup source changed')


def installed(rows):
    return {r.split('\t')[0] for r in rows if r.split('\t')[-1] == 'installed'}


def before_os():
    check_base()
    for name, digest in OLD_VENDOR.items():
        need(sha(Path(name)) == digest, 'Unexpected original vendored runtime dependency')
    need(importlib.metadata.version('pip') == '26.2.1', 'Unexpected original installer')
    write_once('os-before.json', {'sources': sources(), 'packages': packages(), 'protectedTree': tree()})


def after_os():
    check_base()
    old = json.loads((ROOT / 'os-before.json').read_text())
    need(old['sources'] == sources() and old['protectedTree'] == tree(), 'Signed sources or application/Python files changed during OS phase')
    current = packages()
    need(installed(old['packages']) <= installed(current), 'An installed package was removed')
    fixed = {}
    for name, minimum in MINIMUM_SOURCE.items():
        version = command('dpkg-query', '-W', '-f=${source:Version}', name)
        subprocess.run(['dpkg', '--compare-versions', version, 'ge', minimum], check=True)
        fixed[name] = {'sourceVersion': version, 'minimumSourceVersion': minimum}
    write_once('os-after.json', {'osBeforeSHA256': sha(ROOT / 'os-before.json'),
               'packages': current, 'fixedSourceVersions': fixed, 'protectedTreeUnchanged': True,
               'installedPackagesRemoved': False})


def installer_roots():
    scripts = [Path('/usr/local/bin') / name for name in ['pip', 'pip3', 'pip3.13']]
    need(sorted(Path('/usr/local/bin').glob('pip*')) == sorted(scripts), 'Unexpected installer console scripts')
    for path in scripts:
        regular(path)
    for path in [PIP, PIP_METADATA, BOOTSTRAP]:
        need(path.resolve() == path and path.is_dir(), 'Unexpected installer/bootstrap root')
    return [PIP, PIP_METADATA, BOOTSTRAP, *scripts]


def no_runtime_installer_imports():
    # Static source review is repeated against actual build files, without
    # executing the application or reading /config. Vendored installer code is
    # deliberately excluded from this check, then removed in full below.
    roots = [APP, SITE / 'cffi', SITE / 'cryptography', SITE / 'OpenSSL']
    for root in roots:
        for path in root.rglob('*.py'):
            # Several actual vendor modules carry a UTF-8 BOM. Python accepts
            # that on file import; strip it for the equivalent AST text review.
            text = path.read_text(encoding='utf-8-sig')
            parsed = ast.parse(text)
            for node in ast.walk(parsed):
                names = [v.name for v in node.names] if isinstance(node, ast.Import) else [node.module or ''] if isinstance(node, ast.ImportFrom) else []
                need(not any(n.split('.')[0] in ['pip', 'ensurepip'] for n in names), 'Runtime imports installer/bootstrap')
                if (isinstance(node, ast.Call) and node.args and isinstance(node.args[0], ast.Constant)
                        and isinstance(node.args[0].value, str)):
                    function = ast.unparse(node.func)
                    invokes = function in ['__import__', 'importlib.import_module', 'os.system', 'os.popen'] or function.startswith('subprocess.')
                    need(not (invokes and re.search(r'\b(?:pip\d*(?:\.\d+)?|ensurepip)\b', node.args[0].value)), 'Runtime literal invokes installer/bootstrap')
    startup = (APP / 'start.sh').read_text()
    need(not re.search(r'\b(?:pip\d*(?:\.\d+)?|ensurepip)\b', startup), 'Startup invokes installer/bootstrap')


def wheel_files(name, pin):
    need(pin['filename'] == name + '-' + pin['version'] + '-py3-none-any.whl'
         and re.fullmatch('[0-9a-f]{64}', pin['sha256'])
         and type(pin['bytes']) is int and 0 < pin['bytes'] <= 8 * 1024 ** 2, 'Unexpected wheel pin shape')
    url = urllib.parse.urlsplit(pin['url'])
    need(url.scheme == 'https' and url.hostname == 'files.pythonhosted.org'
         and not url.username and not url.password and not url.query and not url.fragment, 'Unexpected wheel origin')
    client = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with client.open(pin['url'], timeout=45) as response:
        need(response.url == pin['url'], 'Wheel redirect refused')
        raw = response.read(8 * 1024 ** 2 + 1)
    need(len(raw) == pin['bytes'] <= 8 * 1024 ** 2 and hashlib.sha256(raw).hexdigest() == pin['sha256'], 'Wheel identity mismatch')
    with (ROOT / pin['filename']).open('xb') as stream:
        stream.write(raw)
    dist = name + '-' + pin['version'] + '.dist-info'
    with zipfile.ZipFile(io.BytesIO(raw)) as bundle:
        infos = bundle.infolist()
        names = [row.filename for row in infos]
        need(0 < len(infos) <= 512 and len(set(names)) == len(names)
             and sum(row.file_size for row in infos) <= 32 * 1024 ** 2, 'Wheel member count/duplicates/expanded size')
        data = {}
        for row in infos:
            path = PurePosixPath(row.filename)
            need(not path.is_absolute() and '..' not in path.parts and '\\' not in row.filename
                 and path.parts[0] in [name, dist] and not row.is_dir()
                 and stat.S_IFMT(row.external_attr >> 16) in [0, stat.S_IFREG], 'Unexpected wheel path/type')
            need(0 <= row.file_size <= 4 * 1024 ** 2, 'Wheel member size')
            data[row.filename] = bundle.read(row)
        record_name = dist + '/RECORD'
        rows = list(csv.reader(io.StringIO(data[record_name].decode())))
        need(len(rows) == len(data) and {row[0] for row in rows} == set(data), 'Wheel RECORD membership')
        for path, digest, size in rows:
            if path == record_name:
                need(digest == size == '', 'Wheel RECORD self-entry')
            else:
                actual = base64.urlsafe_b64encode(hashlib.sha256(data[path]).digest()).rstrip(b'=').decode()
                need(digest == 'sha256=' + actual and size == str(len(data[path])), 'Wheel RECORD identity')
    return data


def python_phase():
    check_base((3, 13, 17))
    original_os = {name: sha(ROOT / name) for name in ['os-before.json', 'os-after.json']}
    core_receipts = {name: sha(ROOT / name) for name in ['cpython-before.json', 'cpython-after.json',
                     'cpython-export.json', 'cpython-core-manifest.json']}
    core = json.loads((ROOT / 'cpython-after.json').read_text())
    need(core['coreMatchesAllOfficialFiles'] is True and core['applicationAndAllExistingSitePackagesUnchanged'] is True,
         'Complete official interpreter preservation proof missing')
    need(json.loads((ROOT / 'os-after.json').read_text())['protectedTreeUnchanged'] is True, 'OS proof missing')
    before = tree()
    for name, digest in OLD_VENDOR.items():
        need(sha(Path(name)) == digest, 'Original vendored dependency changed before Python phase')
    roots = installer_roots()
    no_runtime_installer_imports()
    subprocess.run([sys.executable, '-m', 'pip', '--isolated', '--disable-pip-version-check', 'check'], check=True)
    pins = json.loads((ROOT / 'wheel-inputs.json').read_text())
    need(set(pins) == {'certifi', 'urllib3'}, 'Unexpected runtime wheel scope')
    need(pins['certifi']['version'] == '2026.10.19' and pins['urllib3']['version'] == '2.8.0', 'Unexpected runtime wheel versions')
    wheels = {name: wheel_files(name, pin) for name, pin in pins.items()}
    vendor_roots = []
    for name, pin in pins.items():
        target = APP / 'lib' / name
        info = target.lstat()
        need(target.resolve() == target and stat.S_ISDIR(info.st_mode), 'Vendored dependency root identity')
        dist = APP / 'lib' / (name + '-' + pin['version'] + '.dist-info')
        need(not dist.exists() and not dist.is_symlink(), 'New distribution metadata already exists')
        vendor_roots += [target, dist]
    write_once('python-before.json', {'osReceipts': original_os, 'coreReceipts': core_receipts, 'protectedTree': before,
               'installerRoots': [str(p) for p in roots], 'replacementRoots': [str(p) for p in vendor_roots],
               'wheelInputs': pins, 'runtimeInstallerImportsAbsent': True})
    for name, contents in wheels.items():
        target = APP / 'lib' / name
        info = target.stat()
        # These exact two roots are original, immutable, source-inspected app
        # vendors. No /config, user data, unrelated package or source is removed.
        shutil.rmtree(target)
        for relative, data in contents.items():
            path = APP / 'lib' / relative
            path.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
            with path.open('xb') as stream:
                stream.write(data)
            previous = before.get(str(path))
            os.chmod(path, previous['mode'] if previous else 0o644)
            os.chown(path, info.st_uid, info.st_gid)
        for root in [target, APP / 'lib' / (name + '-' + pins[name]['version'] + '.dist-info')]:
            for folder, dirs, _ in os.walk(root):
                for directory in [Path(folder), *(Path(folder) / n for n in dirs)]:
                    previous = before.get(str(directory))
                    os.chmod(directory, previous['mode'] if previous else 0o755)
                    os.chown(directory, info.st_uid, info.st_gid)
    for path in roots:
        need(path.resolve() == path, 'Installer removal path changed')
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()
    current = tree()
    allowed = [str(p) for p in roots + vendor_roots]
    def frozen(value):
        return {k: v for k, v in value.items() if not any(k == p or k.startswith(p + '/') for p in allowed)}
    need(frozen(before) == frozen(current), 'Unrelated application/interpreter/dependency file changed')
    need(all(sha(ROOT / name) == digest for name, digest in original_os.items()), 'OS proof overwritten')
    need(all(sha(ROOT / name) == digest for name, digest in core_receipts.items()), 'Interpreter proof overwritten')
    for name, contents in wheels.items():
        for relative, data in contents.items():
            need(sha(APP / 'lib' / relative) == hashlib.sha256(data).hexdigest(), 'Installed wheel code/metadata mismatch')
    write_once('python-after.json', {'osReceipts': original_os, 'coreReceipts': core_receipts,
               'pythonBeforeSHA256': sha(ROOT / 'python-before.json'),
               'wheelInputs': pins, 'unrelatedTreeUnchanged': True, 'completeInstallerAndBootstrapRemoved': True,
               'applicationStartupUnchanged': all(sha(Path(p)) == digest for p, digest in FROZEN.items()),
               'nonInstallerDistributionMetadataPreserved': True})


def runtime(expected_uid):
    need(os.geteuid() == expected_uid, 'Unexpected runtime check user')
    need(sys.version_info[:3] == (3, 13, 17) and os.environ.get('PYTHON_VERSION') == '3.13.17'
         and os.environ.get('PYTHON_SHA256') == '6020bd10aff3bf4821be16f088ebb1591beb7b811dcd8fab1da8f7c22a7b27e7',
         'Actual patched interpreter or source ENV mismatch')
    before = tree()
    need(not any(Path('/usr/local/bin').glob('pip*')) and all(not p.exists() for p in [PIP, PIP_METADATA, BOOTSTRAP]), 'Installer/bootstrap artifacts remain')
    need(importlib.util.find_spec('pip') is None and importlib.util.find_spec('ensurepip') is None, 'Installer/bootstrap remains importable')
    sys.path.insert(0, '/app')
    sys.path.insert(0, '/app/lib')  # Match the actual Tautulli.py startup order.
    loaded = {}
    for name in ['certifi', 'urllib3', 'requests', 'plexapi', 'cffi', 'cryptography', 'OpenSSL', 'ssl', 'ctypes', 'sqlite3', 'pyexpat']:
        module = importlib.import_module(name)
        loaded[name] = str(Path(module.__file__).resolve())
    need(loaded['certifi'] == '/app/lib/certifi/__init__.py'
         and loaded['urllib3'] == '/app/lib/urllib3/__init__.py'
         and loaded['requests'] == '/app/lib/requests/__init__.py', 'Actual application import resolution differs')
    certifi = importlib.import_module('certifi')
    urllib3 = importlib.import_module('urllib3')
    need(certifi.__version__ == '2026.10.19' and urllib3.__version__ == '2.8.0', 'Actual runtime vendor version mismatch')
    need(importlib.metadata.version('certifi') == '2026.10.19' and importlib.metadata.version('urllib3') == '2.8.0', 'Actual runtime distribution metadata mismatch')
    need(ssl.create_default_context(cafile=certifi.where()).get_ca_certs(), 'Updated runtime trust store cannot be parsed')
    expat = importlib.import_module('pyexpat').EXPAT_VERSION
    need(tuple(map(int, expat.removeprefix('expat_').split('.'))) >= (2, 8, 5), 'Runtime Expat remains below fixed release')
    compile((APP / 'Tautulli.py').read_text(encoding='utf-8-sig'), '/app/Tautulli.py', 'exec')
    need(tree() == before, 'Runtime checks changed protected files')
    print(json.dumps({'uid': expected_uid, 'pythonVersion': sys.version, 'expatVersion': expat,
                      'imports': loaded, 'certifi': certifi.__version__,
                      'urllib3': urllib3.__version__, 'installerAndBootstrapAbsent': True,
                      'trustStoreParsed': True, 'appStarted': False, 'userDataAccessed': False}, sort_keys=True))


def main():
    need(os.environ.get('PYTHONDONTWRITEBYTECODE') == '1', 'Bytecode writes must be disabled')
    need(sys.argv[1:] in [['before-os'], ['after-os'], ['python'], ['runtime-root'], ['runtime-user']], 'Unexpected maintenance phase')
    {'before-os': before_os, 'after-os': after_os, 'python': python_phase,
     'runtime-root': lambda: runtime(0), 'runtime-user': lambda: runtime(1000)}[sys.argv[1]]()


if __name__ == '__main__':
    main()
