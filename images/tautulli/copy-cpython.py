#!/usr/bin/env python3
"""Copy only the verified official CPython core; retain every existing package."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import stat
import struct
import subprocess
import sys
import sysconfig
import uuid

ROOT = Path('/usr/share/branconet-security/tautulli')
LOCAL = Path('/usr/local')
EXPORT = Path('/cpython-runtime')
INPUT = ROOT / 'cpython-input'
MANIFEST = ROOT / 'cpython-core-manifest.json'
CORE_BINS = {'idle', 'idle3', 'idle3.13', 'pydoc', 'pydoc3', 'pydoc3.13',
             'python', 'python3', 'python3.13', 'python-config', 'python3-config', 'python3.13-config'}
PARENTS = {'bin', 'include', 'lib', 'lib/pkgconfig', 'share', 'share/man', 'share/man/man1'}
TK = 'lib/python3.13/lib-dynload/_tkinter.cpython-313-x86_64-linux-gnu.so'
LINK_OBJECT = 'lib/python3.13/config-3.13-x86_64-linux-gnu/python.o'
GUI_GAP = ['libtcl8.6.so', 'libtk8.6.so']


def need(value, reason):
    if not value:
        raise RuntimeError(reason)


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for data in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(data)
    return h.hexdigest()


def selected(relative):
    if relative in PARENTS:
        return True
    if relative.startswith('bin/'):
        return relative.split('/', 1)[1] in CORE_BINS
    if relative == 'lib/python3.13' or relative.startswith('lib/python3.13/'):
        return not any(relative == p or relative.startswith(p + '/') for p in
                       ['lib/python3.13/site-packages', 'lib/python3.13/ensurepip'])
    return (relative == 'include/python3.13' or relative.startswith('include/python3.13/')
            or relative in ['lib/libpython3.so', 'lib/libpython3.13.so', 'lib/libpython3.13.so.1.0']
            or relative.startswith('lib/pkgconfig/python') or relative.startswith('share/man/man1/python'))


def entry(path):
    info = path.lstat()
    value = {'mode': stat.S_IMODE(info.st_mode), 'uid': info.st_uid, 'gid': info.st_gid}
    if stat.S_ISREG(info.st_mode):
        value.update(type='file', sha256=sha(path))
    elif stat.S_ISDIR(info.st_mode):
        value['type'] = 'directory'
    elif stat.S_ISLNK(info.st_mode):
        value.update(type='symlink', target=os.readlink(path))
    else:
        raise RuntimeError('Unexpected core file type')
    return value


def snapshot(root):
    need(root.resolve() == root and root.is_dir(), 'Core root is not canonical')
    result = {}
    for folder, dirs, files in os.walk(root, followlinks=False):
        for name in sorted(dirs + files):
            path = Path(folder) / name
            relative = path.relative_to(root).as_posix()
            if selected(relative):
                result[relative] = entry(path)
    need(0 < len(result) <= 10000, 'Core entry count')
    return result


def write_once(name, value):
    with (ROOT / name).open('x') as stream:
        json.dump(value, stream, sort_keys=True, indent=2)
        stream.write('\n')


def manifest():
    value = json.loads(MANIFEST.read_text())
    need(value['sourcePythonVersion'] == '3.13.17' and value['expectedInheritedOptionalGUIUnresolved'] == GUI_GAP,
         'Unexpected core manifest scope')
    need(value['sourceImage'] == 'docker.io/library/python:3.13.17-slim-trixie@sha256:fe14fd57a4c0361110eaa0c284112b189750bcb43fb04bb5d1ee7b7744027ccf',
         'Unexpected official source image')
    for key in ['oldCore', 'newCore']:
        need(0 < len(value[key]) <= 10000 and all(selected(p) for p in value[key]), 'Unexpected core path scope')
        need(all(not Path(p).is_absolute() and '..' not in Path(p).parts and '\\' not in p
                 and item['type'] in ['file', 'directory', 'symlink']
                 and item['uid'] == 0 and item['gid'] == 0 for p, item in value[key].items()),
             'Unexpected core member identity')
        need(not any(p.startswith('lib/python3.13/site-packages') or p.startswith('lib/python3.13/ensurepip')
                     or p.startswith('bin/pip') for p in value[key]), 'Installer/package entered core payload')
    return value


def abi(value):
    need(sys.version_info[:3] == (3, 13, 17) and os.uname().machine == 'x86_64', 'Unexpected official runtime')
    need({key: sysconfig.get_config_var(key) for key in value['sourceABI']} == value['sourceABI'], 'CPython ABI/configuration changed')
    release = dict(line.split('=', 1) for line in Path('/etc/os-release').read_text().splitlines() if '=' in line)
    need(release.get('ID') == 'debian' and release.get('VERSION_ID') == '"13"'
         and release.get('VERSION_CODENAME') == 'trixie', 'Unexpected Debian ABI track')


def linked(path):
    env = {key: val for key, val in os.environ.items() if key not in ['LD_LIBRARY_PATH', 'LD_PRELOAD']}
    env.update(LC_ALL='C', LANG='C')
    result = subprocess.run(['ldd', str(path)], env=env, capture_output=True, text=True, timeout=15)
    missing = sorted(re.findall(r'^\s*(\S+)\s+=>\s+not found\s*$', result.stdout, re.M))
    need(result.returncode == 0, 'Core ldd failed')
    need(len(result.stdout) + len(result.stderr) <= 65536, 'Core ldd output bound')
    return {'missing': missing, 'lddSHA256': hashlib.sha256(result.stdout.encode()).hexdigest()}


def copy_entries(source, destination, entries):
    for relative, expected in sorted(entries.items(), key=lambda item: (item[0].count('/'), item[0])):
        src, dst = source / relative, destination / relative
        need(entry(src) == expected, 'Official payload source changed')
        if expected['type'] == 'directory':
            if dst.exists():
                need(dst.is_dir() and not dst.is_symlink(), 'Core destination directory conflict')
            else:
                dst.mkdir()
            os.chmod(dst, expected['mode'])
            os.chown(dst, expected['uid'], expected['gid'])
            continue
        need(dst.parent.resolve() == dst.parent and dst.parent.is_dir(), 'Core destination ancestor changed')
        temporary = dst.parent / ('.branconet-core-' + uuid.uuid4().hex)
        try:
            if expected['type'] == 'symlink':
                os.symlink(expected['target'], temporary)
            else:
                shutil.copyfile(src, temporary, follow_symlinks=False)
                os.chmod(temporary, expected['mode'])
            os.chown(temporary, expected['uid'], expected['gid'], follow_symlinks=False)
            need(entry(temporary) == expected, 'Staged core file differs from official payload')
            os.replace(temporary, dst)
        finally:
            if os.path.lexists(temporary):
                temporary.unlink()


def maintenance():
    spec = importlib.util.spec_from_file_location('tautulli_maintenance_proof', ROOT / 'maintain.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def frozen(tree):
    return {p: value for p, value in tree.items()
            if not (p.startswith(str(LOCAL) + '/') and selected(p[len(str(LOCAL)) + 1:]))}


def export(value):
    abi(value)
    need(snapshot(LOCAL) == value['newCore'], 'Official source core does not match all inspected files')
    donor_gap = linked(LOCAL / TK)
    need(donor_gap['missing'] == GUI_GAP, 'Official optional GUI baseline differs')
    EXPORT.mkdir(mode=0o755)
    copy_entries(LOCAL, EXPORT, value['newCore'])
    need(snapshot(EXPORT) == value['newCore'], 'Core export differs from official source')
    need(not (EXPORT / 'lib/python3.13/site-packages').exists()
         and not (EXPORT / 'lib/python3.13/ensurepip').exists()
         and not any((EXPORT / 'bin').glob('pip*')), 'Installer/package entered exported payload')
    write_once('cpython-export.json', {'sourceImage': value['sourceImage'], 'manifestSHA256': sha(MANIFEST),
               'coreEntries': len(value['newCore']), 'sourceCoreVerified': True,
               'sitePackagesExported': False, 'installerOrBootstrapExported': False,
               'inheritedOptionalGUI': donor_gap, 'sourceABI': value['sourceABI']})


def before(value):
    proof = maintenance()
    proof.check_base()
    all_files = proof.tree()
    old_os = json.loads((ROOT / 'os-before.json').read_text())
    os_after = json.loads((ROOT / 'os-after.json').read_text())
    need(old_os['protectedTree'] == all_files and os_after['protectedTreeUnchanged'] is True
         and os_after['osBeforeSHA256'] == sha(ROOT / 'os-before.json'), 'Original OS preservation proof changed')
    need(snapshot(LOCAL) == value['oldCore'], 'Current original core differs from inspected image')
    baseline_gap = linked(LOCAL / TK)
    need(baseline_gap['missing'] == GUI_GAP, 'Original optional GUI baseline differs')
    write_once('cpython-before.json', {'manifestSHA256': sha(MANIFEST), 'protectedTree': all_files,
               'osReceipts': {name: sha(ROOT / name) for name in ['os-before.json', 'os-after.json']},
               'inheritedOptionalGUI': baseline_gap})


def install(value):
    proof = maintenance()
    proof.check_base()
    saved = json.loads((ROOT / 'cpython-before.json').read_text())
    need(saved['manifestSHA256'] == sha(MANIFEST) and saved['protectedTree'] == proof.tree(), 'Original interpreter phase state changed')
    need(snapshot(INPUT) == value['newCore'], 'Staged official core payload differs')
    exported = json.loads((ROOT / 'cpython-export.json').read_text())
    need(exported['sourceImage'] == value['sourceImage'] and exported['manifestSHA256'] == sha(MANIFEST)
         and exported['sourceCoreVerified'] is True and exported['inheritedOptionalGUI']['missing'] == GUI_GAP,
         'Official export receipt mismatch')
    # Replace exact files atomically. The running old interpreter retains its
    # mapped inodes until exit; no subprocess or fresh import runs after this.
    copy_entries(INPUT, LOCAL, value['newCore'])
    obsolete = set(value['oldCore']) - set(value['newCore'])
    for relative in sorted(obsolete, key=lambda p: (-p.count('/'), p)):
        path = LOCAL / relative
        need(entry(path) == value['oldCore'][relative], 'Obsolete core path changed')
        if value['oldCore'][relative]['type'] == 'directory':
            path.rmdir()
        else:
            path.unlink()
    need(snapshot(LOCAL) == value['newCore'], 'Installed core differs from complete official payload')


def after(value):
    proof = maintenance()
    proof.check_base((3, 13, 17))
    abi(value)
    saved = json.loads((ROOT / 'cpython-before.json').read_text())
    need(snapshot(LOCAL) == value['newCore'] and frozen(proof.tree()) == frozen(saved['protectedTree']),
         'Official core or frozen application/noninstaller package changed')
    need(all(sha(ROOT / name) == digest for name, digest in saved['osReceipts'].items()), 'OS receipts overwritten')
    need(os.environ.get('PYTHON_VERSION') == value['sourcePythonVersion']
         and os.environ.get('PYTHON_SHA256') == value['sourcePythonSHA256'], 'Interpreter ENV metadata differs from actual source')
    import ssl
    import ctypes
    import sqlite3
    import pyexpat
    expat = tuple(map(int, pyexpat.EXPAT_VERSION.removeprefix('expat_').split('.')))
    need(expat >= (2, 8, 5), 'Bundled Expat remains below the fixed release')
    link_results = {}
    for relative, expected in value['newCore'].items():
        path = LOCAL / relative
        if expected['type'] != 'file':
            continue
        with path.open('rb') as stream:
            elf = stream.read(4) == b'\x7fELF'
        if elf:
            if relative == LINK_OBJECT:
                # The official SDK link object is ET_REL, not a runtime DSO.
                # Keep it in the full manifest; ldd correctly refuses this type.
                header = path.read_bytes()[:64]
                need(len(header) == 64 and header[:7] == b'\x7fELF\x02\x01\x01', 'Official link object ELF identity')
                fields = struct.unpack_from('<HHIQQQIHHHHHH', header, 16)
                need(fields[0:3] == (1, 62, 1) and fields[4] == 0
                     and fields[7] == 64 and fields[9] == 0, 'Official link object must be ET_REL without program headers')
                need(sha(path) == 'e16f3a4671cc70794d679b71093672d780d888e172deee5b0b5e691755673232',
                     'Official link object primary digest differs')
                result = {'elfType': 'ET_REL', 'sha256': sha(path), 'runtimeLinkCheckApplicable': False,
                          'classification': 'retained exact official SDK link object; no runtime program headers'}
            else:
                result = linked(path)
                result['runtimeLinkCheckApplicable'] = True
                need(result['missing'] == (GUI_GAP if relative == TK else []), 'New or unexpected unresolved core dependency')
            link_results[relative] = result
    need(len(link_results) == 82, 'Unexpected official core ELF coverage')
    need(sum(r['runtimeLinkCheckApplicable'] for r in link_results.values()) == 81
         and link_results[LINK_OBJECT]['elfType'] == 'ET_REL', 'Official ELF classification coverage')
    need(snapshot(LOCAL) == value['newCore'] and frozen(proof.tree()) == frozen(saved['protectedTree']),
         'Core checks modified protected files')
    write_once('cpython-after.json', {'sourceImage': value['sourceImage'], 'sourceAMD64ManifestSHA256': value['sourceAMD64ManifestSHA256'],
               'manifestSHA256': sha(MANIFEST), 'cpythonBeforeSHA256': sha(ROOT / 'cpython-before.json'),
               'exportReceiptSHA256': sha(ROOT / 'cpython-export.json'), 'osReceipts': saved['osReceipts'],
               'pythonVersion': sys.version, 'sourceABI': value['sourceABI'], 'coreMatchesAllOfficialFiles': True,
               'applicationAndAllExistingSitePackagesUnchanged': True, 'sslVersion': ssl.OPENSSL_VERSION,
               'sqliteVersion': sqlite3.sqlite_version, 'expatVersion': pyexpat.EXPAT_VERSION,
               'ctypesImported': True, 'linkResults': link_results,
               'optionalGUIException': {'onlyModule': TK, 'missing': GUI_GAP,
                    'independentlyMatchedOldAndDonor': True, 'notAClaimThatAllELFsResolve': True}})
    need(INPUT.resolve() == INPUT and INPUT.parent == ROOT, 'Staged payload cleanup path changed')
    shutil.rmtree(INPUT)


def main():
    need(os.geteuid() == 0 and os.environ.get('PYTHONDONTWRITEBYTECODE') == '1', 'Root/bytecode contract')
    need(sys.argv[1:] in [['export'], ['before'], ['install'], ['after']], 'Unexpected core phase')
    value = manifest()
    {'export': export, 'before': before, 'install': install, 'after': after}[sys.argv[1]](value)


if __name__ == '__main__':
    main()
