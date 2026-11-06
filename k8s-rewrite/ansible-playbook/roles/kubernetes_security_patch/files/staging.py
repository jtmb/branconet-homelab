"""Finite native binary capture/backup/staging controller. Parent executes explicitly."""
import argparse
import datetime as dt
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import threading

F = Path('/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025')
H = F / 'platform-upstream-review-20261027/autonomous-hardening-20261028'
R = H / 'kubernetes1372-native-stage'
VENDOR = H / 'kubernetes1372-binaries/authority.json'
VENDOR_SHA = 'bb96c82be216747db666b2ef9d10a927688df7e7119b6f3f2775605b6d5e9859'
NODES = {'masternode': '192.168.0.4', 'workernode2': '192.168.0.5', 'workernode1': '192.168.0.6'}
NAMES = ('kubeadm', 'kubelet', 'kubectl')
OLD = dict(kubeadm='087b6340dcea496f2cde2b3888ecd414354c08a0aceabd6b7ca195cccb66ecd3',
           kubelet='cee008c1640c3b41820ef31d35b3cffc132b0c4b78c288be2b8022ebc7aa8293',
           kubectl='65691ff77eb6fa44c908b77a1082c9f092c3b9733b5cefabec0d1104890e21a8')
SSH = ['ssh', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes', '-i', '/home/brajam/.ssh/id_ed25519', '-p', '2002']
HERE = Path(__file__).resolve().parent
SOURCE = (HERE / 'stage_remote.py').read_text()
spec = importlib.util.spec_from_file_location('stage_remote', HERE / 'stage_remote.py')
remote = importlib.util.module_from_spec(spec); spec.loader.exec_module(remote)


def sha(path):
    return remote.digest(path)


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def save(path, value):
    assert path.parent.resolve() == path.parent and R in path.parents
    data = json.dumps(value, indent=2).encode() + b'\n'
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(data); stream.flush(); os.fsync(stream.fileno())
    fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
    return ref(path)


def ref(path):
    assert path.resolve() == path and F in path.parents and path.is_file()
    return dict(path=str(path), sha256=sha(path))


def load_ref(value):
    path = Path(value['path']); assert ref(path) == value
    return json.loads(path.read_text())


def shell(host, code):
    return SSH + ['james@' + NODES[host], code]


def invoke(host, request, mode='observe', password=None, blob=None):
    code = SOURCE + '\nprint(json.dumps(' + mode + '(' + repr(request) + ')))\n'
    argv = ['python3', '-B', '-c', code]
    if mode == 'observe':
        result = subprocess.run(shell(host, shlex.join(argv)), capture_output=True, timeout=180)
        assert result.returncode == 0, 'Read-only native metadata failed on ' + host
        return json.loads(result.stdout)
    # The unprivileged memory-only wrapper consumes the password before sudo.
    # sudo authentication receives ONLY that line. Payload never depends on
    # whether sudo consumes a password (NOPASSWD and cached timestamp are safe).
    wrapper = ('import os,subprocess,sys\n'
               'secret=bytearray()\n'
               'while True:\n'
               ' b=os.read(0,1)\n'
               ' if b==b"\\n": break\n'
               ' assert b and len(secret)<128\n'
               ' secret.extend(b)\n'
               'reset=subprocess.run(["sudo","-k"],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)\n'
               'assert reset.returncode==0,"Timestamp reset failed"\n'
               'r=subprocess.run(["sudo","-S","-p","","-v"],input=bytes(secret)+b"\\n",stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)\n'
               'secret[:]=b"\\0"*len(secret)\n'
               'assert r.returncode==0,"Privilege authentication failed"\n'
               'sys.exit(subprocess.call(' + repr(['sudo', '-n', '--'] + argv) + ',stdin=0))\n')
    process = subprocess.Popen(shell(host, shlex.join(['python3', '-B', '-c', wrapper])), stdin=subprocess.PIPE,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    errors = process.stderr
    process.stderr = None
    diagnostic = {'stderrBytes': 0, 'stderrComplete': False}
    error_hash = hashlib.sha256()

    def drain_errors():
        try:
            for block in iter(lambda: errors.read(65536), b''):
                error_hash.update(block)
                diagnostic['stderrBytes'] += len(block)
        finally:
            errors.close()
            diagnostic['stderrSHA256'] = error_hash.hexdigest()
            diagnostic['stderrComplete'] = True

    reader = threading.Thread(target=drain_errors, daemon=True)
    reader.start()
    try:
        process.stdin.write(password + b'\n')
        with blob.open('rb') as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b''):
                process.stdin.write(block)
        process.stdin.close(); process.stdin = None
        output, _ = process.communicate(timeout=600)
        reader.join(timeout=5)
        diagnostic['exitCode'] = process.returncode
        assert process.returncode == 0, 'Native staging failed; retain intent and path, observe only'
        assert len(output) < 1024**2
        result = json.loads(output)
        result['carrier'] = dict(diagnostic)
        return result
    except Exception as error:
        diagnostic['exitCode'] = process.poll()
        error.carrier_diagnostic = dict(diagnostic)
        raise
    finally:
        if process.stdin is not None:
            try:
                process.stdin.close()
            except BrokenPipeError:
                pass
        # Never stop an uncertain remote write. Parent observes its recorded path.


def node_uids():
    result = subprocess.run(shell('masternode', 'kubectl get nodes -o json'), capture_output=True, timeout=60)
    assert result.returncode == 0
    values = {x['metadata']['name']: x['metadata']['uid'] for x in json.loads(result.stdout)['items']}
    assert set(values) == set(NODES)
    return values


def hostkeys():
    values = {}
    for host, ip in NODES.items():
        result = subprocess.run(['ssh-keygen', '-F', '[' + ip + ']:2002'], capture_output=True, timeout=30)
        assert result.returncode == 0 and result.stdout
        values[host] = hashlib.sha256(result.stdout).hexdigest()
    return values


def fresh(value):
    age = (dt.datetime.now(dt.timezone.utc) - dt.datetime.fromisoformat(value)).total_seconds()
    assert 0 <= age < 6 * 3600, 'Capture older than six hours; do not replay prior intent'


def global_observe(vendor, capture=None):
    uids = node_uids(); keys = hostkeys(); nodes = {}
    if capture:
        assert uids == capture['nodeUIDs'] and keys == capture['sshHostKeys']
    for host in NODES:
        value = invoke(host, vendor)
        assert value['host'] == host
        for name in NAMES:
            old = value['binaries'][name]
            assert old['sha256'] == OLD[name] and (old['uid'], old['gid'], old['mode']) == (0, 0, 0o755)
        if capture:
            assert remote.identity(value) == remote.identity(capture['nodes'][host]), 'Captured origin/boot/config changed'
        nodes[host] = value
    return dict(capturedAt=now(), nodeUIDs=uids, sshHostKeys=keys, nodes=nodes)


def backup(vendor, capture):
    assert not (R / 'backups.json').exists()
    before = global_observe(vendor, capture)
    # Old bytes only; all three hosts were verified identical before dedup.
    required = sum(capture['nodes']['masternode']['binaries'][n]['bytes'] for n in NAMES)
    windows_free = subprocess.check_output(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command',
                                            "[Console]::Write((Get-PSDrive -Name C).Free)"], text=True, timeout=30)
    assert int(windows_free.strip()) >= 15 * 1024**3, 'Windows C safety floor before raw backup download'
    assert shutil.disk_usage(F).free >= 15 * 1024**3 + required
    result = {}
    for name in NAMES:
        old = capture['nodes']['masternode']['binaries'][name]
        target = R / ('original-' + old['sha256'])
        intent = R / ('backup-' + name + '-intent.json')
        save(intent, dict(capturedAt=now(), before=before, target=str(target), original=old,
                         sourceHost='masternode', lastConsumer='verified native rollback retention', regeneration='Original live bytes before replacement only'))
        fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        code = ('import os,sys\nfd=os.open(' + repr(old['path']) + ',os.O_RDONLY|os.O_NOFOLLOW)\n'
                'with os.fdopen(fd,"rb") as f:\n'
                ' while True:\n'
                '  b=f.read(1048576)\n'
                '  if not b: break\n'
                '  sys.stdout.buffer.write(b)\n')
        proc = subprocess.Popen(shell('masternode', shlex.join(['python3', '-B', '-c', code])), stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        total = 0; digest = hashlib.sha256()
        with os.fdopen(fd, 'wb') as stream:
            while True:
                block = proc.stdout.read(min(1024**2, old['bytes'] + 1 - total))
                if not block:
                    break
                total += len(block); assert total <= old['bytes'], 'Oversized original backup'
                digest.update(block); stream.write(block)
            stream.flush(); os.fsync(stream.fileno())
        assert proc.wait(timeout=180) == 0 and total == old['bytes'] and digest.hexdigest() == old['sha256']
        after = global_observe(vendor, capture)
        result[name] = ref(target)
        save(R / ('backup-' + name + '-after.json'), dict(capturedAt=now(), intent=ref(intent), backup=result[name], after=after))
    save(R / 'backups.json', result)


def qualify(host, name, state, capture, vendor):
    original = capture['nodes'][host]['binaries'][name]; entry = vendor['binaries'][name]
    actual = state['stages'][name]
    assert actual and actual['sha256'] == entry['sha256'] and actual['bytes'] == entry['bytes']
    assert all(actual[k] == original[k] for k in ('uid', 'gid', 'mode', 'mtimeNs', 'xattrsSHA256'))
    intent = R / (host + '-' + name + '-intent.json')
    frozen = json.loads(intent.read_text())
    assert frozen['nodeUID'] == capture['nodeUIDs'][host] and frozen['sourceSHA256'] == hashlib.sha256(SOURCE.encode()).hexdigest()
    assert frozen['before']['stages'][name] is None and frozen['binary'] == entry
    assert remote.identity(frozen['before']) == remote.identity(state)
    return dict(capturedAt=now(), node=host, nodeUID=capture['nodeUIDs'][host],
                path=actual['path'], sha256=entry['sha256'], bytes=entry['bytes'],
                ownerTask='kubernetes1372-security-patch', newlyCreated=True,
                intent=ref(intent), observed=state, installPerformed=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['capture', 'backup', 'stage', 'observe'])
    parser.add_argument('--checkpoint', required=True, type=Path)
    parser.add_argument('--checkpoint-sha256', required=True)
    a = parser.parse_args()
    password = None
    if a.mode == 'stage':
        # Consume protected stdin BEFORE any SSH, metadata or privilege call.
        password = sys.stdin.buffer.readline(130)
        assert password.endswith(b'\n') and 1 < len(password) <= 129 and b'\0' not in password
        password = password[:-1]
    os.umask(0o077)
    assert F.is_mount() and R.parent.resolve() == R.parent and sha(VENDOR) == VENDOR_SHA
    checkpoint_ref = dict(path=str(a.checkpoint), sha256=a.checkpoint_sha256)
    checkpoint = load_ref(checkpoint_ref)
    assert set(checkpoint['clusterNodes']) == set(NODES)
    vendor = json.loads(VENDOR.read_text()); assert set(vendor['binaries']) == set(NAMES)
    for entry in vendor['binaries'].values():
        blob = Path(entry['blob']['path'])
        assert ref(blob)['sha256'] == entry['sha256'] and blob.stat().st_size == entry['bytes']
    if a.mode == 'capture':
        R.mkdir(mode=0o700, exist_ok=False)
        save(R / 'ownership.json', dict(owner='kubernetes1372-security-patch', root=str(R), physicalVolume=str(F),
             vendor=ref(VENDOR), sourceSHA256=hashlib.sha256(SOURCE.encode()).hexdigest(),
             controllerSHA256=sha(Path(__file__).resolve()),
             checkpoint=checkpoint_ref,
             generatedPaths=['capture.json', 'original-SHA256', '*-intent.json', '*-after.json', 'backups.json', '*-stage.json', 'binary-evidence.json'],
             regeneration='staging.py capture/backup/stage/observe; never repeat a recorded write intent',
             protected='Raw originals and immutable before/intent/after receipts; no automatic deletion',
             lastConsumer='Native role consumes exact node .new files via atomic rename; raw originals retained for rollback'))
        value = global_observe(vendor)
        assert value['nodeUIDs'] == checkpoint['clusterNodes'], 'Original checkpoint node UID mismatch'
        assert all(s is None for n in value['nodes'].values() for s in n['stages'].values())
        save(R / 'capture.json', value)
        print(json.dumps(ref(R / 'capture.json'))); return
    assert R.resolve() == R and R.stat().st_uid == os.getuid() and not R.stat().st_mode & 0o077
    capture = json.loads((R / 'capture.json').read_text()); fresh(capture['capturedAt'])
    ownership = json.loads((R / 'ownership.json').read_text())
    assert ownership['vendor'] == ref(VENDOR) and ownership['sourceSHA256'] == hashlib.sha256(SOURCE.encode()).hexdigest()
    assert ownership['controllerSHA256'] == sha(Path(__file__).resolve()), 'Staging controller changed since capture'
    assert ownership['checkpoint'] == checkpoint_ref and capture['nodeUIDs'] == checkpoint['clusterNodes']
    if a.mode == 'backup':
        backup(vendor, capture); print(json.dumps(ref(R / 'backups.json'))); return
    backups = json.loads((R / 'backups.json').read_text())
    for name in NAMES:
        assert ref(Path(backups[name]['path'])) == backups[name] and backups[name]['sha256'] == OLD[name]
    all_nodes = global_observe(vendor, capture)
    if a.mode == 'stage':
        # No stage writes until ALL THREE current budgets pass together.
        budgets = {host: remote.budget(value, vendor) for host, value in all_nodes['nodes'].items()}
        save(R / 'stage-global-before.json', dict(capturedAt=now(), observation=all_nodes, budgets=budgets))
        for host in NODES:
            for name in NAMES:
                entry = vendor['binaries'][name]
                before = invoke(host, vendor)
                assert remote.identity(before) == remote.identity(capture['nodes'][host])
                remote.budget(before, vendor)
                assert before['stages'][name] is None
                intent = R / (host + '-' + name + '-intent.json')
                save(intent, dict(capturedAt=now(), nodeUID=capture['nodeUIDs'][host], before=before, binary=entry,
                                 sourceSHA256=hashlib.sha256(SOURCE.encode()).hexdigest(),
                                 ownerTask='kubernetes1372-security-patch', path='/usr/local/bin/.kubernetes1372-' + name + '-' + entry['sha256'] + '.new',
                                 lastConsumer='native_binaries.py atomic replacement', regeneration='Verified vendor blob; never replay uncertain intent'))
                request = dict(binaries=vendor['binaries'], before=before, name=name)
                after = invoke(host, request, 'stage', password, Path(entry['blob']['path']))
                save(R / (host + '-' + name + '-after.json'), dict(capturedAt=now(), intent=ref(intent), after=after))
        password = None
    # Observe is read-only on nodes and may qualify an exact completed authored
    # stage after lost SSH output. An incomplete/missing stage refuses export.
    final = global_observe(vendor, capture)
    result = dict(binaries=vendor['binaries'], signatureTool=vendor['signatureTool'], immutableVendorAuthority=ref(VENDOR))
    for name, entry in result['binaries'].items():
        entry['originalByNode'] = {host: capture['nodes'][host]['binaries'][name] for host in NODES}
        entry['originalBackups'] = {host: backups[name] for host in NODES}
        entry['prestage'] = {}
        for host in NODES:
            value = qualify(host, name, final['nodes'][host], capture, json.loads(VENDOR.read_text()))
            path = R / (host + '-' + name + '-stage.json')
            if path.exists():
                previous = json.loads(path.read_text()); fresh(previous['capturedAt'])
                assert all(previous[k] == value[k] for k in ('node', 'nodeUID', 'path', 'sha256', 'bytes', 'intent'))
            else:
                save(path, value)
            entry['prestage'][host] = ref(path)
    destination = R / 'binary-evidence.json'
    if destination.exists():
        assert json.loads(destination.read_text()) == result
    else:
        save(destination, result)
    print(json.dumps(ref(destination)))


if __name__ == '__main__':
    main()
