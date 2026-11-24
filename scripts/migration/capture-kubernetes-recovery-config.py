#!/usr/bin/env python3
"""Capture fixed Kubernetes recovery files into a verified private age archive.

The caller supplies the separately qualified checkpoint Transport, including its
absolute deadline, tool pins and private credential provider. No live CLI fallback
to the historical backup-config.py is permitted.
"""
import base64
import hashlib
import importlib.util
import json
import os
import pathlib
import re
import shlex


def load_checkpoint():
    path = pathlib.Path(__file__).with_name('backup-etcd.py')
    spec = importlib.util.spec_from_file_location('recovery_config_checkpoint', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not all(hasattr(module, name) for name in ('Transport', 'Ledger', 'read_age', 'left')):
        raise Refused('transport')
    return module


PKI_PAIRS = (
    'ca', 'apiserver', 'apiserver-kubelet-client', 'front-proxy-ca',
    'front-proxy-client', 'apiserver-etcd-client', 'etcd/ca', 'etcd/server',
    'etcd/peer', 'etcd/healthcheck-client',
)
FILES = tuple(sorted(
    ['/etc/kubernetes/pki/' + name + suffix for name in PKI_PAIRS
     for suffix in ('.crt', '.key')]
    + ['/etc/kubernetes/pki/sa.key', '/etc/kubernetes/pki/sa.pub',
       '/etc/kubernetes/encryption-config.json', '/etc/kubernetes/longhorn-crypto-key']
    + ['/etc/kubernetes/' + name + '.conf' for name in
       ('admin', 'kubelet', 'controller-manager', 'scheduler')]
    + ['/etc/kubernetes/manifests/' + name + '.yaml' for name in
       ('kube-apiserver', 'kube-controller-manager', 'kube-scheduler', 'etcd')]
))
MAX_FILE = 1024 * 1024
# Leave ciphertext framing headroom under the checkpoint's 32MiB config pin.
MAX_DOCUMENT = 31 * 1024 * 1024


class Refused(RuntimeError):
    def __init__(self, code):
        self.code = code if code in (
            'transport', 'input', 'files', 'drift', 'archive', 'deadline', 'cleanup'
        ) else 'archive'
        super().__init__('Recovery configuration capture refused: ' + self.code)


def need(value, code):
    if not value:
        raise Refused(code)


def validate_files(files):
    need(type(files) is dict and set(files) == set(FILES), 'files')
    decoded = {}
    for name in FILES:
        encoded = files[name]
        need(type(encoded) is str and 0 < len(encoded) <= (MAX_FILE + 2) // 3 * 4,
             'files')
        try:
            raw = base64.b64decode(encoded, validate=True)
        except Exception:
            raise Refused('files') from None
        need(0 < len(raw) <= MAX_FILE and base64.b64encode(raw).decode() == encoded,
             'files')
        decoded[name] = raw
    return decoded


def nas_program(e, prefix='config'):
    """Keep the NAS writer strict; admit mount-forced0755 only for CIFS ciphertext.

    The operator archive remains pinned0600. The remote program receives only
    authenticated ciphertext; it never handles a plaintext configuration/key.
    The mount identity is checked throughout, with no shared-helper changes.
    """
    need(type(prefix) is str and prefix in ('config', 'etcd', 'bortus-sqlite'), 'input')
    program = e.q.NAS_PROGRAM.replace('bortus-sqlite-', prefix + '-')
    mount_reader = r'''
def mount_identity():
 with open('/proc/self/mountinfo',encoding='utf-8')as stream:
  raw=stream.read(1048577)
 if len(raw)>1048576:raise ValueError()
 selected=None
 import re
 for line in raw.splitlines():
  fields=line.split();cut=fields.index('-')
  mount=re.sub(r'\\([0-7]{3})',lambda m:chr(int(m[1],8)),fields[4])
  if str(root)==mount or str(root).startswith(mount.rstrip('/')+'/'):
   if selected is None or len(mount)>len(selected[0]):
    selected=(mount,tuple(fields[:6]),tuple(fields[cut+1:]))
 if selected is None:raise ValueError()
 return selected
'''
    old_reopen = "if tuple(getattr(before,k)for k in('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns'))!=tuple(getattr(os.fstat(target),k)for k in('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns')):raise ValueError()"
    new_reopen = """after=os.fstat(target)
 core_fields=('st_dev','st_ino','st_uid','st_mode','st_nlink','st_size')
 full_fields=core_fields+('st_mtime_ns','st_ctime_ns')
 cifs_close=mount_before[0]=='/mnt/container-backups' and mount_before[2][0]=='cifs'
 close_fields=core_fields if cifs_close else full_fields
 if tuple(getattr(before,k)for k in close_fields)!=tuple(getattr(after,k)for k in close_fields):raise ValueError()
 check(after)
 reopened=tuple(getattr(after,k)for k in full_fields)
 def check_reopened():
  current=os.fstat(target)
  check(current)
  if tuple(getattr(current,k)for k in full_fields)!=reopened:raise ValueError()"""
    replacements = {
        old_reopen: new_reopen,
        'block=os.read(target,65536)': 'check_reopened()\n  block=os.read(target,65536)\n  check_reopened()',
        'check(os.fstat(target))': 'check_reopened()',
        'try:\n header=': mount_reader + '\ntry:\n mount_before=mount_identity()\n header=',
        'for v in (i,n):': 'if mount_identity()!=mount_before:raise ValueError()\n  for v in (i,n):',
        'stat.S_IMODE(v.st_mode)!=0o600':
            '(stat.S_IMODE(v.st_mode)!=0o600 and not (stat.S_IMODE(v.st_mode)==0o755 and mount_before[0]=="/mnt/container-backups" and mount_before[2][0]=="cifs"))',
        "'same_inode_readback':True}":
            "'same_inode_readback':True,'cipher_mode':stat.S_IMODE(os.fstat(target).st_mode),'cifs_mount':mount_before[0]=='/mnt/container-backups' and mount_before[2][0]=='cifs'}",
    }
    for original, replacement in replacements.items():
        need(program.count(original) == 1, 'transport')
        program = program.replace(original, replacement)
    return program


def copy_nas(client, e, cipher, run_id, expected_sha, deadline):
    """Publish only ciphertext through the fixed exclusive/readback NAS program."""
    cipher.check()
    size = os.fstat(cipher.fd).st_size
    need(0 < size <= MAX_DOCUMENT + 1048576, 'archive')
    name = 'config-' + run_id + '.age'
    program = nas_program(e)
    child = pipe = None
    failure = None
    try:
        child = client.spawn([*e.SSH, shlex.join(['python3', '-c', program])])
        pipe = e.q.archive.Pipe(child.stdin, deadline, False)
        pipe.write(json.dumps({'name': name, 'bytes': size, 'sha256': expected_sha,
                               'seconds': e.left(deadline)},
                              separators=(',', ':')).encode() + b'\n')
        os.lseek(cipher.fd, 0, os.SEEK_SET)
        digest = hashlib.sha256()
        for block in iter(lambda: os.read(cipher.fd, 65536), b''):
            e.left(deadline)
            digest.update(block)
            pipe.write(block)
        child.stdin.close()
        cipher.check()
        need(digest.hexdigest() == expected_sha, 'archive')
        response = e.decode(e.collect(child, deadline, client.children, maximum=1024))
        need(type(response) is dict and set(response) == {
            'bytes', 'sha256', 'fsynced', 'same_inode_readback', 'cipher_mode', 'cifs_mount'
        } and type(response['bytes']) is int and response['bytes'] == size
            and response['sha256'] == expected_sha
            and response['fsynced'] is True
            and response['same_inode_readback'] is True
            and type(response['cipher_mode']) is int
            and type(response['cifs_mount']) is bool
            and (response['cipher_mode'] == 0o600 or
                 response['cipher_mode'] == 0o755 and response['cifs_mount'] is True), 'archive')
        cipher.check()
        client.check()
    except Exception:
        failure = 'archive'
    finally:
        if pipe:
            try:
                pipe.close()
            except Exception:
                failure = 'cleanup'
        if child:
            try:
                client.children(child)
            except Exception:
                failure = 'cleanup'
            for stream in (child.stdin, child.stdout, child.stderr):
                if stream and not stream.closed:
                    try:
                        stream.close()
                    except Exception:
                        failure = 'cleanup'
    if failure:
        raise Refused(failure)
    e.left(deadline)
    return {'path': e.q.NAS_ROOT + '/' + name,
            'cipher_mode': response['cipher_mode'], 'cifs_mount': response['cifs_mount']}


def capture(*, client, checkpoint, parent, run_id, recipient_file, identity_file):
    """Once-only read-only capture; caller retains and closes its Transport.

    Two fixed remote reads must match around encryption, authentication and NAS
    publication. This is per-read consistency, not a continuous file watcher or
    proof of etcd/API/Longhorn restoration. Failed/uncertain artifacts are retained.
    """
    result = failure = None
    try:
        result = _capture(client, checkpoint, parent, run_id, recipient_file, identity_file)
    except Refused as exc:
        failure = exc.code
    except Exception:
        failure = 'archive'
    if failure:
        # Keep private credential/file bytes out of a public exception traceback.
        client = checkpoint = parent = recipient_file = identity_file = result = None
        raise Refused(failure) from None
    return result


def _capture(client, e, parent, run_id, recipient_file, identity_file):
    need(type(run_id) is str and re.fullmatch('[0-9a-f]{12}', run_id), 'input')
    need(hasattr(client, 'deadline') and callable(client.check), 'transport')
    deadline = client.deadline
    e.left(deadline)
    ledger = recipient = identity = cipher = child = pipe = None
    raw = recovered = decoded = files = second = None
    failure = None
    result = None
    try:
        # A distinct config-capture parent is required: never share checkpoint runs.
        parent = pathlib.Path(parent)
        need(parent.name == 'config-captures', 'input')
        ledger = e.Ledger(parent, run_id)
        ledger.r.update(kind='kubernetes-recovery-configuration',
                        file_count=len(FILES), files=list(FILES),
                        actual_production_checkpoint_accepted=False)
        ledger.intent('read_configuration', {'file_count': len(FILES)})
        recipient = e.q.Pin(recipient_file, 65536)
        identity = e.q.Pin(identity_file, 65536)
        files = client.remote({'mode': 'keys', 'run_id': run_id, 'paths': list(FILES)})
        decoded = validate_files(files)
        # Validate current encryption config/key shapes using the checkpoint contract.
        e.keys({'files': files})
        ledger.confirm('read_configuration', {'complete': True})
        raw = (json.dumps({'files': files}, sort_keys=True,
                          separators=(',', ':')) + '\n').encode()
        need(0 < len(raw) <= MAX_DOCUMENT, 'files')
        ledger.intent('encrypt_configuration', {'name': 'configuration.json.age'})
        target = ledger.path / 'configuration.json.age'
        fd = os.open(target.name, os.O_CREAT | os.O_EXCL | os.O_RDWR | os.O_NOFOLLOW,
                     0o600, dir_fd=ledger.fd)
        try:
            with os.fdopen(fd, 'wb', closefd=False) as output:
                client.check()
                child = client.spawn([str(e.RUNTIME / 'bin/age'), '-R',
                                      recipient.child_path], stdout=output)
                pipe = e.q.archive.Pipe(child.stdin, deadline, False)
                pipe.write(raw)
                child.stdin.close()
                need(child.wait(timeout=e.left(deadline)) == 0, 'archive')
                output.flush()
                os.fsync(fd)
                os.fsync(ledger.fd)
        finally:
            os.close(fd)
        pipe.close()
        pipe = None
        client.children(child)
        child = None
        recipient.check()
        identity.check()
        cipher = e.q.Pin(target, MAX_DOCUMENT + 1048576)
        recovered = e.read_age(client, cipher, identity.child_path, deadline,
                               MAX_DOCUMENT)
        need(recovered == raw, 'archive')
        recovered = None
        os.lseek(cipher.fd, 0, os.SEEK_SET)
        digest = hashlib.sha256()
        for block in iter(lambda: os.read(cipher.fd, 65536), b''):
            e.left(deadline)
            digest.update(block)
        cipher.check()
        cipher_sha = digest.hexdigest()
        ledger.confirm('encrypt_configuration', {
            'ciphertext_sha256': cipher_sha,
            'encrypted_bytes': os.fstat(cipher.fd).st_size,
            'authenticated_equal_bytes': True,
        })
        # Checkpoint copy_nas is fixed/exclusive, uses the pinned explicit SSH key,
        # retains uncertain ciphers, and verifies same-inode ciphertext readback.
        ledger.intent('publish_configuration', {'ciphertext_sha256': cipher_sha})
        nas = copy_nas(client, e, cipher, run_id, cipher_sha, deadline)
        ledger.confirm('publish_configuration', dict(nas, readback=True))
        second = client.remote({'mode': 'keys', 'run_id': run_id, 'paths': list(FILES)})
        need(validate_files(second) == decoded, 'drift')
        client.check()
        recipient.check()
        identity.check()
        cipher.check()
        ledger.r.update(phase='completed', actual_exit_code=0,
                        per_read_configuration_equal=True,
                        continuous_file_watch=False,
                        api_decryption_restored=False,
                        longhorn_restore_proved=False)
        e.left(deadline)
        ledger.save()
        e.left(deadline)
        result = {'path': str(target), 'sha256': cipher_sha,
                  'record': str(ledger.path / 'record.json'), 'nas_copy': nas['path'],
                  'nas_cipher_mode': nas['cipher_mode'], 'nas_cifs_mount': nas['cifs_mount'],
                  'file_count': len(FILES)}
    except Exception as exc:
        failure = exc.code if isinstance(exc, Refused) else 'archive'
        if ledger:
            try:
                ledger.r.update(phase='refused', error=failure, actual_exit_code=1)
                ledger.save()
            except Exception:
                pass
    finally:
        raw = recovered = decoded = files = second = None
        if pipe:
            try:
                pipe.close()
            except Exception:
                failure = 'cleanup'
        if child:
            try:
                client.children(child)
            except Exception:
                failure = 'cleanup'
            for stream in (child.stdin, child.stdout, child.stderr):
                if stream and not stream.closed:
                    try:
                        stream.close()
                    except Exception:
                        failure = 'cleanup'
        for pin in (cipher, identity, recipient):
            if pin:
                try:
                    pin.close()
                except Exception:
                    failure = 'cleanup'
        if ledger:
            try:
                ledger.close()
            except Exception:
                failure = 'cleanup'
    if failure:
        raise Refused(failure)
    e.left(deadline)
    return result
