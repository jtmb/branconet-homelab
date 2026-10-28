"""Bounded worker2 validation tool retirement. No trees or runtime state removed."""
import datetime
import hashlib
import json
import os
from pathlib import Path
import pwd
import socket
import stat
import subprocess
import time

BASE = Path('/home/james/.local/share/branconet-migration') / ('charts-validation-' + '20261023-70daf1e5ec72') / 'source' / '.tools'
HASHES = {'helm': '57ce7fc4ea77b28ee6fa91ae071abcade74d3f524e80c9decff5877a5ac8eda4', 'kubectl': '65691ff77eb6fa44c908b77a1082c9f092c3b9733b5cefabec0d1104890e21a8', 'gitleaks': '88f91962aa2f93ac6ab281d553b9e125f5197bbbce38f9f2437f7299c32e5509'}

def need(ok, reason):
    if not ok:
        raise ValueError(reason)

def command(*args):
    return subprocess.check_output(args, text=True, stderr=subprocess.DEVNULL, timeout=90)

def identity(p):
    s = p.lstat()
    return {k: getattr(s, 'st_' + k) for k in ('dev', 'ino', 'mode', 'uid', 'gid', 'nlink', 'size', 'mtime_ns', 'ctime_ns', 'blocks')}

def sha(p):
    digest = hashlib.sha256()
    with p.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()

def siblings():
    result = {}
    for root, dirs, files in os.walk(BASE.parent.parent, followlinks=False):
        for name in files:
            p = Path(root) / name
            if p.parent == BASE and name in HASHES:
                continue
            result[str(p)] = identity(p)
    return result

def consumers():
    refs = {name: [] for name in HASHES}
    commands = {}
    for user in ('root', 'james'):
        commands[user] = command('sudo', '-n', '-u', user, '-H', 'sh', '-lc', 'for n in helm kubectl gitleaks; do command -v "$n" || true; done').splitlines()
        for value in commands[user]:
            for name in HASHES:
                if Path(value).resolve() == BASE / name:
                    refs[name].append('configured_command:' + user + ':' + value)
    roots = [Path(p) for p in ('/etc/systemd', '/etc/cron.d', '/etc/cron.daily', '/etc/cron.hourly', '/etc/cron.weekly', '/etc/cron.monthly', '/var/spool/cron', '/etc/profile.d', '/home/james/.config/systemd')]
    files = [Path(p) for p in ('/etc/crontab', '/etc/profile', '/etc/environment', '/home/james/.profile', '/home/james/.bashrc', '/root/.profile', '/root/.bashrc')]
    for root in roots:
        if root.exists():
            files.extend(p for p in root.rglob('*') if p.is_file())
    for p in files:
        if p.is_file():
            need(p.stat().st_size < 8 * 1024**2, 'oversize_configuration:' + str(p))
            content = p.read_bytes()
            for name in HASHES:
                if str(BASE / name).encode() in content or str(BASE).encode() in content or str(BASE.parent).encode() in content:
                    refs[name].append('configuration:' + str(p))
    for directory in ('/usr/local/bin', '/usr/local/sbin', '/usr/bin', '/usr/sbin', '/bin', '/sbin', '/home/james/.local/bin', '/root/.local/bin'):
        p = Path(directory)
        if p.is_dir():
            for link in p.iterdir():
                if link.is_symlink():
                    for name in HASHES:
                        if link.resolve() == BASE / name:
                            refs[name].append('command_symlink:' + str(link))
    return {'references': refs, 'commands': commands, 'configurationFilesChecked': len(files)}

def run(reference, apply=False):
    need(os.geteuid() == 0 and socket.gethostname() == 'workernode2', 'fixed_worker2_root')
    fs = json.loads(command('findmnt', '--json', '--target', str(BASE), '--output', 'UUID,FSTYPE,SOURCE'))['filesystems'][0]
    need(fs['uuid'] == '960bc2c7-2a7e-4bc2-b2c5-dbb6d71207f4' and fs['fstype'] == 'ext4', 'fixed_root_fs')
    need(BASE.resolve() == BASE and BASE.is_dir(), 'exact_directory')
    need(all(not (p / '.git').exists() for p in (BASE, *BASE.parents)), 'git_owned_ancestor')
    preserved = siblings()
    usage = consumers()
    before = os.statvfs(BASE)
    result = {'utc': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'apply': apply, 'filesystem': fs, 'consumers': usage, 'removed': [], 'retained': [], 'qualified': [], 'removedAllocatedBytes': 0, 'protectedSiblingCount': len(preserved)}
    # The reference is hash-pinned by the controller. Expand to ALL properties;
    # preserve its complete process, fd, map and namespace checks verbatim.
    reference = reference.replace("'--property=Id,ExecStart,WorkingDirectory', ", '')
    namespace = {'__name__': 'reference_guard'}
    exec(compile(reference, '<verified-full-properties-reference>', 'exec'), namespace)
    for name, expected in HASHES.items():
        path = BASE / name
        try:
            info = identity(path)
            need(path.resolve() == path and stat.S_ISREG(info['mode']), 'exact_regular_file')
            need(info['uid'] == pwd.getpwnam('james').pw_uid and info['gid'] == pwd.getpwnam('james').pw_gid and info['nlink'] == 1 and info['dev'] == os.stat('/').st_dev, 'source_owned_single_link_device')
            need(info['mode'] & 0o7777 == 0o755, 'expected_executable_mode')
            need(time.time_ns() - max(info['mtime_ns'], info['ctime_ns']) >= 72 * 3600 * 10**9, '72_hour_inactivity')
            need(not os.listxattr(path), 'extended_attributes')
            attrs = command('lsattr', '-d', '--', str(path)).split()[0]
            need(set(attrs) <= set('-e'), 'special_inode_attributes')
            need(sha(path) == expected and identity(path) == info, 'stable_expected_hash')
            need(not usage['references'][name], 'configured_consumer:' + repr(usage['references'][name]))
            namespace.update(BASE=BASE, ATTEMPTS=(name,))
            guard = namespace['idle']()
            record = {'path': str(path), 'identity': info, 'sha256': expected, 'attributes': attrs, 'guard': guard}
            result['qualified'].append(record)
            if apply:
                need(not consumers()['references'][name], 'consumer_changed')
                namespace['idle']()
                need(identity(path) == info and siblings() == preserved, 'identity_or_siblings_changed')
                fd = os.open(BASE, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
                try:
                    need(os.fstat(fd).st_ino == BASE.stat().st_ino, 'directory_identity_changed')
                    os.unlink(name, dir_fd=fd)
                finally:
                    os.close(fd)
                result['removed'].append(record)
                result['removedAllocatedBytes'] += info['blocks'] * 512
        except (ValueError, OSError, subprocess.SubprocessError) as error:
            result['retained'].append({'path': str(path), 'reason': str(error)})
    need(siblings() == preserved, 'protected_sibling_changed')
    after = os.statvfs(BASE)
    result.update(availableBeforeBytes=before.f_bavail * before.f_frsize, availableAfterBytes=after.f_bavail * after.f_frsize)
    return result


def remove_empty(reference):
    """Reconcile only the now-empty generated directory after binary retirement."""
    result = {'utc': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'path': str(BASE), 'removedAllocatedBytes': 0, 'removed': False}
    try:
        need(os.geteuid() == 0 and socket.gethostname() == 'workernode2', 'fixed_worker2_root')
        fs = json.loads(command('findmnt', '--json', '--target', str(BASE), '--output', 'UUID'))['filesystems'][0]
        need(fs['uuid'] == '960bc2c7-2a7e-4bc2-b2c5-dbb6d71207f4', 'fixed_filesystem')
        info = identity(BASE)
        need(BASE.resolve() == BASE and stat.S_ISDIR(info['mode']) and info['uid'] == 1000 and info['gid'] == 1000 and info['nlink'] == 2 and info['dev'] == os.stat('/').st_dev, 'exact_owned_empty_directory')
        need(not list(BASE.iterdir()) and not os.listxattr(BASE), 'empty_without_unique_attributes')
        need(set(command('lsattr', '-d', '--', str(BASE)).split()[0]) <= set('-e'), 'directory_inode_attributes')
        need(all(not (p / '.git').exists() for p in (BASE, *BASE.parents)), 'git_ancestor')
        original = BASE.parent.parent
        receipt = json.loads((original / 'receipt.json').read_text())
        manifest = (original / 'source-manifest.json').read_bytes()
        need(hashlib.sha256(manifest).hexdigest() == receipt['source_manifest_sha256'], 'original_manifest_hash')
        need(b'.tools/' not in manifest and b'".tools"' not in manifest, 'not_source_manifest_owned')
        need(receipt['stage'] == str(original) and receipt['tools']['exit_code'] == 0 and receipt['tool_binary_sha256'] == HASHES and receipt['passed'], 'original_successful_generated_tools')
        generator = BASE.parent / 'scripts/install-tools.py'
        code = generator.read_text()
        need("target = ROOT/'.tools'" in code and 'target.mkdir(exist_ok=True)' in code and 'file.write_bytes(data)' in code, 'actual_generator_creates_tools_directory')
        need('.tools/' in (BASE.parent / '.gitignore').read_text().splitlines(), 'generated_directory_excluded')
        usage = consumers()
        need(not any(usage['references'].values()), 'configured_consumer')
        for directory in ('/usr/local/bin', '/usr/local/sbin', '/usr/bin', '/usr/sbin', '/bin', '/sbin', '/home/james/.local/bin', '/root/.local/bin'):
            if Path(directory).is_dir():
                need(not any(p.is_symlink() and p.resolve() == BASE for p in Path(directory).iterdir()), 'directory_command_link')
        namespace = {'__name__': 'reference_guard'}
        exec(compile(reference.replace("'--property=Id,ExecStart,WorkingDirectory', ", ''), '<verified-full-properties-reference>', 'exec'), namespace)
        namespace.update(BASE=BASE.parent, ATTEMPTS=(BASE.name,))
        guard = namespace['idle']()
        preserved = siblings()
        need(identity(BASE) == info and not list(BASE.iterdir()), 'directory_changed')
        result.update(identity=info, generatorSHA256=sha(generator), originalReceiptSHA256=sha(original / 'receipt.json'), sourceManifestSHA256=receipt['source_manifest_sha256'], guard=guard, protectedSiblingCount=len(preserved), regeneration='mkdir .tools then copy individually hash-pinned original helm, kubectl and gitleaks; no validation replay')
        BASE.rmdir()
        result.update(removed=True, removedAllocatedBytes=info['blocks'] * 512)
        need(not BASE.exists() and BASE.parent.is_dir() and siblings() == preserved, 'source_parent_and_siblings_preserved')
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        result['failedCheck'] = str(error)
    return result
