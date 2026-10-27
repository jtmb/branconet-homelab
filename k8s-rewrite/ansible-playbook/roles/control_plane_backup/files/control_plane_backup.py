#!/usr/bin/env python3
"""Separate maintenance backup; never import the frozen BORTUS recovery helpers."""
import argparse
import datetime
import hashlib
import io
import json
import os
import pathlib
import re
import shlex
import stat
import subprocess
import sys
import tarfile
import termios
import uuid

MAX_SNAPSHOT = 512 * 1024 * 1024
MAX_CONFIG = 64 * 1024 * 1024
MAX_ARCHIVE = MAX_SNAPSHOT + MAX_CONFIG + 4 * 1024 * 1024
AGE_SHA256 = 'eb7dd1b518f0a307c99cd97782623c5321da049154b04acd2d98d21aa7bc9b2c'
ETCD_SOURCES = {
    'registry.k8s.io/etcd:3.7.0-0': ('3.7.0', {
        'registry.k8s.io/etcd@sha256:6ecefbe2510c4a30573a62a4d6dd175acf881ca67003fcd91849a16df7a724d5'}),
    'registry.k8s.io/etcd:3.7.3-0@sha256:0d27b9478551f431f82d1e0ddb6c87ad07ebae8b904c637f3a99213349523910': ('3.7.3', {
        'registry.k8s.io/etcd:3.7.3-0@sha256:0d27b9478551f431f82d1e0ddb6c87ad07ebae8b904c637f3a99213349523910',
        'registry.k8s.io/etcd@sha256:0d27b9478551f431f82d1e0ddb6c87ad07ebae8b904c637f3a99213349523910',
        'registry.k8s.io/etcd@sha256:b4a41c6864baf573f5213dce18b2a95e1002ec6c5a1a26ad900c2ea166ac6d0b'}),
}
REQUIRED = {
    'etc/kubernetes/encryption-config.json', 'etc/kubernetes/longhorn-crypto-key',
    *('etc/kubernetes/' + name + '.conf' for name in ['admin', 'kubelet', 'controller-manager', 'scheduler']),
    *('etc/kubernetes/manifests/' + name + '.yaml' for name in ['etcd', 'kube-apiserver', 'kube-controller-manager', 'kube-scheduler']),
    *('etc/kubernetes/pki/' + name for name in [
        'ca.crt', 'ca.key', 'sa.key', 'sa.pub', 'apiserver.crt', 'apiserver.key',
        'apiserver-etcd-client.crt', 'apiserver-etcd-client.key',
        'apiserver-kubelet-client.crt', 'apiserver-kubelet-client.key',
        'front-proxy-ca.crt', 'front-proxy-ca.key', 'front-proxy-client.crt', 'front-proxy-client.key',
        'etcd/ca.crt', 'etcd/ca.key', 'etcd/healthcheck-client.crt', 'etcd/healthcheck-client.key',
        'etcd/peer.crt', 'etcd/peer.key', 'etcd/server.crt', 'etcd/server.key',
    ]),
}
SSH = ['/usr/bin/ssh', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes', '-o', 'UserKnownHostsFile=/home/brajam/.ssh/known_hosts', '-o', 'IdentitiesOnly=yes', '-o', 'ForwardAgent=no', '-o', 'ConnectTimeout=15', '-i', '/home/brajam/.ssh/id_ed25519', '-p', '2002', 'james@192.168.0.4']

# This fixed privileged program reads only /etc/kubernetes and its own new snapshot.
# Its archive stdout is piped directly to age, never to an Ansible/tool log.
REMOTE = r'''
import os,sys,pathlib,stat,json,re,tarfile,io,hashlib
run,mode=sys.argv[1:3]
if not re.fullmatch('[0-9a-f]{32}',run) or os.geteuid()!=0:raise SystemExit(1)
root=pathlib.Path('/var/lib/etcd')/('cluster-maintenance-'+run)
def need(ok):
 if not ok:raise ValueError('refused')
def fp(s):return(s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
def safe_open(p,limit):
 need(p.is_absolute() and p.resolve()==p)
 fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK);s=os.fstat(fd)
 need(stat.S_ISREG(s.st_mode) and s.st_uid==0 and not s.st_mode&0o022 and s.st_nlink==1 and 0<=s.st_size<=limit)
 return fd,s
def stable(fd,p,before):
 need(fp(os.fstat(fd))==fp(before)==fp(p.lstat()))
if mode=='prepare':
 parent=pathlib.Path('/var/lib/etcd');s=parent.lstat();need(stat.S_ISDIR(s.st_mode) and s.st_uid==0 and not s.st_mode&0o022)
 fs=os.statvfs(parent);need(fs.f_bavail*fs.f_frsize>2*1024**3)
 os.mkdir(root,0o700);print(json.dumps({'root':str(root)}));raise SystemExit(0)
rs=root.lstat();need(stat.S_ISDIR(rs.st_mode) and rs.st_uid==0 and stat.S_IMODE(rs.st_mode)==0o700)
snapshot=root/'snapshot.db';fd,ss=safe_open(snapshot,512*1024*1024)
need(32<ss.st_size<=512*1024*1024 and ss.st_size%512==32)
h=hashlib.sha256()
with os.fdopen(os.dup(fd),'rb') as f:
 for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
stable(fd,snapshot,ss);binding={'inode':list(fp(ss)),'bytes':ss.st_size,'sha256':h.hexdigest()}
if mode=='metadata':print(json.dumps(binding));os.close(fd);raise SystemExit(0)
if mode=='cleanup':
 expected=json.loads(sys.argv[3]);need(binding==expected)
 need(sorted(x.name for x in root.iterdir())==['snapshot.db'])
 os.unlink(snapshot);os.rmdir(root);print(json.dumps({'removed_owned_snapshot':True}));os.close(fd);raise SystemExit(0)
need(mode=='archive')
config=pathlib.Path('/etc/kubernetes');need(config.resolve()==config)
files=[];total=0
for directory,dirs,names in os.walk(config,followlinks=False):
 need(len(files)+len(dirs)+len(names)<=512)
 for name in dirs:need(not(pathlib.Path(directory)/name).is_symlink())
 for name in sorted(names):
  p=pathlib.Path(directory)/name;f,s=safe_open(p,1024*1024)
  try:
   b=os.read(f,s.st_size+1);need(len(b)==s.st_size);stable(f,p,s)
  finally:os.close(f)
  total+=len(b);need(total<=64*1024*1024)
  files.append((str(p).lstrip('/'),b,s))
need(len(files)<=256)
manifest={'schema_version':1,'snapshot':binding,'files':{name:{'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()} for name,b,s in files}}
with tarfile.open(fileobj=sys.stdout.buffer,mode='w|',format=tarfile.PAX_FORMAT) as tf:
 data=(json.dumps(manifest,sort_keys=True)+'\n').encode();info=tarfile.TarInfo('manifest.json');info.mode=0o600;info.size=len(data);tf.addfile(info,io.BytesIO(data))
 for name,b,s in sorted(files,key=lambda x:x[0]):
  info=tarfile.TarInfo(name);info.mode=stat.S_IMODE(s.st_mode);info.uid=s.st_uid;info.gid=s.st_gid;info.mtime=int(s.st_mtime);info.size=len(b);tf.addfile(info,io.BytesIO(b))
 os.lseek(fd,0,os.SEEK_SET);info=tarfile.TarInfo('snapshot.db');info.mode=0o600;info.size=ss.st_size
 with os.fdopen(os.dup(fd),'rb') as f:tf.addfile(info,f)
stable(fd,snapshot,ss);os.close(fd)
# Detect concurrent configuration replacement after the captured bytes were streamed.
for name,b,s in files:
 p=pathlib.Path('/')/name;need(fp(p.lstat())==fp(s))
'''


def need(condition):
    if not condition:
        raise ValueError('maintenance backup prerequisite refused')


def digest_file(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def protected_file(path, private=False, executable=False):
    need(path.is_absolute() and path.resolve() == path)
    info = path.lstat()
    need(stat.S_ISREG(info.st_mode) and info.st_uid == os.getuid() and not info.st_mode & 0o022)
    if private:
        need(not info.st_mode & 0o077)
    if executable:
        need(os.access(path, os.X_OK))
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def verify_archive(stream, expected_snapshot):
    """Authenticate via age externally; inspect tar in memory, never extract secrets."""
    names = set()
    manifest = None
    config_count = 0
    snapshot_verified = False
    total = 0
    with tarfile.open(fileobj=stream, mode='r|') as archive:
        for member in archive:
            need(member.isfile() and member.name not in names and not member.name.startswith('/') and '..' not in pathlib.PurePosixPath(member.name).parts)
            names.add(member.name)
            total += member.size
            need(len(names) <= 258 and total <= MAX_ARCHIVE)
            source = archive.extractfile(member)
            if member.name == 'manifest.json':
                need(manifest is None and len(names) == 1 and member.size <= 262144)
                manifest = json.loads(source.read())
                need(manifest.get('schema_version') == 1 and manifest.get('snapshot') == expected_snapshot)
                need(REQUIRED <= set(manifest['files']) and len(manifest['files']) <= 256)
                continue
            need(manifest is not None)
            digest = hashlib.sha256()
            if member.name == 'snapshot.db':
                need(member.size == expected_snapshot['bytes'] and member.size % 512 == 32 and member.size <= MAX_SNAPSHOT)
                footer_digest = hashlib.sha256()
                tail = b''
                count = 0
                for block in iter(lambda: source.read(1024 * 1024), b''):
                    count += len(block)
                    digest.update(block)
                    joined = tail + block
                    footer_digest.update(joined[:-32])
                    tail = joined[-32:]
                need(count == member.size and digest.hexdigest() == expected_snapshot['sha256'] and tail == footer_digest.digest())
                snapshot_verified = True
            else:
                need(member.name.startswith('etc/kubernetes/') and member.name in manifest['files'] and member.size <= 1024 * 1024)
                data = source.read()
                digest.update(data)
                expected = manifest['files'][member.name]
                need(len(data) == member.size == expected['bytes'] and digest.hexdigest() == expected['sha256'])
                if member.name in REQUIRED:
                    need(len(data) > 0)
                if member.name == 'etc/kubernetes/encryption-config.json':
                    config = json.loads(data)
                    need(config.get('kind') == 'EncryptionConfiguration' and config.get('resources'))
                if '/pki/' in member.name and member.name.endswith('.crt'):
                    need(b'-----BEGIN CERTIFICATE-----' in data and b'-----END CERTIFICATE-----' in data)
                if '/pki/' in member.name and member.name.endswith('.key'):
                    need(b'PRIVATE KEY-----' in data)
                config_count += 1
    need(manifest is not None and snapshot_verified and names == {'manifest.json', 'snapshot.db'} | set(manifest['files']))
    return config_count


def privilege_input():
    fd = os.open('/dev/tty', os.O_RDWR | os.O_NOCTTY)
    previous = termios.tcgetattr(fd)
    hidden = previous[:]
    hidden[3] &= ~termios.ECHO
    try:
        termios.tcsetattr(fd, termios.TCSAFLUSH, hidden)
        need(not termios.tcgetattr(fd)[3] & termios.ECHO)
        os.write(fd, b'Existing authorized privilege input (terminal echo disabled): ')
        raw = bytearray()
        while True:
            value = os.read(fd, 1)
            if value in (b'\n', b'\r'):
                break
            need(value and len(raw) < 128)
            raw.extend(value)
        need(bool(raw))
        result = bytes(raw)
        raw[:] = b'\0' * len(raw)
        return result
    finally:
        termios.tcsetattr(fd, termios.TCSAFLUSH, previous)
        os.write(fd, b'\n')
        os.close(fd)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for flag in ['output-dir', 'recipient-file', 'identity-file', 'age-binary']:
        parser.add_argument('--' + flag, type=pathlib.Path, required=True)
    parser.add_argument('--etcd-image', required=True)
    parser.add_argument('--etcd-digest', required=True)
    args = parser.parse_args()
    need(args.etcd_image in ETCD_SOURCES)
    expected_version, accepted_runtime_ids = ETCD_SOURCES[args.etcd_image]
    need(args.etcd_digest in accepted_runtime_ids)
    os.umask(0o077)
    # Operator authorization is entered only through the protected controlling
    # terminal and sent through SSH stdin. Never accept a credential environment.
    need('BRANCONET_MIGRATION_SUDO_PASSWORD' not in os.environ)
    supplied = globals().pop('_CONTROL_PLANE_PRIVILEGE_BYTES', None)
    if supplied is None:
        supplied = privilege_input()
    need(type(supplied) is bytes and 0 < len(supplied) <= 256
         and not any(value in supplied for value in (b'\x00', b'\r', b'\n')))
    password_bytes = supplied + b'\n'
    supplied = None
    need(b'\x00' not in password_bytes)
    pins = [(p, protected_file(p, private=p == args.identity_file, executable=p == args.age_binary)) for p in [args.recipient_file, args.identity_file, args.age_binary]]
    need(digest_file(args.age_binary) == AGE_SHA256)
    need(args.identity_file == pathlib.Path('/home/brajam/.ssh/id_ed25519') and args.recipient_file == pathlib.Path('/home/brajam/.ssh/id_ed25519.pub'))
    output = args.output_dir
    need(output.is_absolute() and str(output).startswith('/home/brajam/') and output.resolve() == output)
    source_root = pathlib.Path(__file__).resolve().parents[5]
    need(output != source_root and source_root not in output.parents)
    output.mkdir(parents=True, mode=0o700, exist_ok=True)
    mode = output.lstat()
    need(stat.S_ISDIR(mode.st_mode) and mode.st_uid == os.getuid() and not mode.st_mode & 0o077)
    run_id = uuid.uuid4().hex
    run = output / ('control-plane-' + run_id)
    run.mkdir(mode=0o700)
    receipt = {'schema_version': 1, 'status': 'started', 'run_id': run_id, 'started_at': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'scope': 'cluster-maintenance-control-plane', 'age_version': 'v1.3.2', 'age_binary_sha256': AGE_SHA256, 'restore_verified': False, 'bortus_recovery_accepted': False, 'application_quiesced': False, 'remote_plaintext_retained': False}
    receipt_path = run / 'receipt.json'
    children = []

    def save():
        temporary = run / ('receipt-' + uuid.uuid4().hex + '.tmp')
        with temporary.open('x') as stream:
            json.dump(receipt, stream, sort_keys=True, indent=2)
            stream.flush(); os.fsync(stream.fileno())
        os.replace(temporary, receipt_path)
        fd = os.open(run, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)

    def ssh(argv, privileged=False, stream=False):
        command = (['sudo', '-S', '-k', '-p', '', '/usr/bin/python3', '-c', REMOTE, run_id, *argv] if privileged else argv)
        child = subprocess.Popen(SSH + [shlex.join(command)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, env=dict(os.environ))
        children.append(child)
        if stream:
            child.stdin.write(password_bytes if privileged else b''); child.stdin.close()
            return child
        data, _ = child.communicate(password_bytes if privileged else b'', timeout=180)
        need(child.returncode == 0 and len(data) <= 2 * 1024 * 1024)
        return data

    def pod():
        obj = json.loads(ssh(['kubectl', '-n', 'kube-system', 'get', 'pod', 'etcd-masternode', '-o', 'json']))
        container = next(c for c in obj['spec']['containers'] if c['name'] == 'etcd')
        status = next(c for c in obj['status']['containerStatuses'] if c['name'] == 'etcd')
        need(obj['spec']['nodeName'] == 'masternode' and obj['status']['phase'] == 'Running' and status['ready'] is True and container['image'] == args.etcd_image and status['imageID'] == args.etcd_digest and not obj['metadata'].get('deletionTimestamp'))
        need('--data-dir=/var/lib/etcd' in container.get('command', []) + container.get('args', []))
        mounts = {v['name']: v['hostPath']['path'] for v in obj['spec']['volumes'] if 'hostPath' in v}
        need(any(m.get('mountPath') == '/var/lib/etcd' and mounts.get(m['name']) == '/var/lib/etcd' and not m.get('readOnly', False) for m in container['volumeMounts']))
        return {'name': obj['metadata']['name'], 'uid': obj['metadata']['uid'], 'image': container['image'], 'image_id': status['imageID']}

    save()
    try:
        receipt['phase'] = 'source_preflight'; save()
        original = pod()
        prefix = ['kubectl', '-n', 'kube-system', 'exec', 'etcd-masternode', '-c', 'etcd', '--']
        for tool in ['etcdctl', 'etcdutl']:
            version = ssh(prefix + [tool, 'version']).decode()
            need(tool + ' version: ' + expected_version + '\n' in version)
        receipt['source'] = original
        receipt['phase'] = 'snapshot'; save()
        prepared = json.loads(ssh(['prepare'], privileged=True))
        snapshot = prepared['root'] + '/snapshot.db'
        receipt['remote_snapshot_path'] = snapshot
        receipt['remote_plaintext_retained'] = True; save()
        ctl = ['etcdctl', '--endpoints=https://127.0.0.1:2379', '--cacert=/etc/kubernetes/pki/etcd/ca.crt', '--cert=/etc/kubernetes/pki/etcd/healthcheck-client.crt', '--key=/etc/kubernetes/pki/etcd/healthcheck-client.key', '--dial-timeout=10s', '--command-timeout=120s']
        ssh(prefix + ctl + ['snapshot', 'save', snapshot])
        status = json.loads(ssh(prefix + ['etcdutl', 'snapshot', 'status', snapshot, '--write-out=json']))
        need(isinstance(status, dict) and all(type(status.get(k)) is int and status[k] > 0 for k in ['hash', 'revision', 'totalKey', 'totalSize']))
        binding = json.loads(ssh(['metadata'], privileged=True))
        need(32 < binding['bytes'] <= MAX_SNAPSHOT and re.fullmatch('[0-9a-f]{64}', binding['sha256']))
        need(status['totalSize'] <= binding['bytes'])
        receipt['snapshot_status'] = {k: status[k] for k in ['hash', 'revision', 'totalKey', 'totalSize']}
        receipt['snapshot_sha256'] = binding['sha256']
        receipt['phase'] = 'encrypt_archive'; save()
        cipher = run / 'control-plane.tar.age'
        producer = ssh(['archive'], privileged=True, stream=True)
        with cipher.open('xb') as target:
            encryptor = subprocess.Popen([str(args.age_binary), '-R', str(args.recipient_file)], stdin=producer.stdout, stdout=target, stderr=subprocess.DEVNULL, env=dict(os.environ))
            children.append(encryptor); producer.stdout.close()
            need(encryptor.wait(timeout=300) == 0 and producer.wait(timeout=30) == 0)
            target.flush(); os.fsync(target.fileno())
        need(0 < cipher.stat().st_size <= MAX_ARCHIVE + 1024 * 1024)
        receipt['phase'] = 'authenticate_and_verify'; save()
        decryptor = subprocess.Popen([str(args.age_binary), '-d', '-i', str(args.identity_file), str(cipher)], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, env=dict(os.environ))
        children.append(decryptor)
        count = verify_archive(decryptor.stdout, binding)
        # Drain through EOF so age authenticates the final chunk, including tar padding.
        remainder = 0
        for block in iter(lambda: decryptor.stdout.read(65536), b''):
            remainder += len(block); need(remainder <= 1024 * 1024 and not any(block))
        need(decryptor.wait(timeout=30) == 0 and pod() == original)
        for path, identity in pins:
            need(protected_file(path, private=path == args.identity_file, executable=path == args.age_binary) == identity)
        receipt.update(archive_path=str(cipher), archive_sha256=digest_file(cipher), archive_bytes=cipher.stat().st_size, config_file_count=count, authenticated_archive_verified=True, snapshot_footer_verified=True, snapshot_status_verified=True, off_node_operator_copy=True, nas_copy_verified=False)
        receipt['phase'] = 'remove_only_verified_owned_snapshot'; save()
        need(json.loads(ssh(['cleanup', json.dumps(binding)], privileged=True)) == {'removed_owned_snapshot': True})
        receipt.update(status='completed', phase='completed', remote_plaintext_retained=False, completed_at=datetime.datetime.now(datetime.timezone.utc).isoformat())
        save()
        print(json.dumps({'status': 'completed', 'receipt': str(receipt_path), 'archive_sha256': receipt['archive_sha256']}))
        return 0
    except Exception as error:
        receipt.update(status='failed', error_type=type(error).__name__, completed_at=datetime.datetime.now(datetime.timezone.utc).isoformat())
        save()
        print(json.dumps({'status': 'failed', 'receipt': str(receipt_path), 'phase': receipt.get('phase'), 'error_type': type(error).__name__}))
        return 1
    finally:
        for child in reversed(children):
            if child.poll() is None:
                child.terminate()
                try:
                    child.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    child.kill(); child.wait(timeout=10)
        password_bytes = None


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception:
        raise SystemExit('Control-plane backup refused an unavailable or invalid prerequisite; no credential/configuration diagnostics are emitted')
