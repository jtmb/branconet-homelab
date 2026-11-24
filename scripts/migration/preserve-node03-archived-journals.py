"""Preserve closed node03 journals encrypted on H before exact local retirement.

No journal rotation, retention setting, service restart or live-volume change.
Only archived system journals older than 72 hours and with no open FD qualify.
"""
import base64
import argparse
from decimal import Decimal
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import select
import shlex
import shutil
import subprocess
import tarfile
import time

RUNTIME = Path('/home/brajam/.local/share/branconet-migration')
ROOT = Path('/mnt/h/AgentArtifacts/projects/branconet/builds/wsl-artifact-store/files/bortus-operator-recovery/node03-archived-journals-20261114')
SSH = ['ssh', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes', '-o', 'ConnectTimeout=10',
       '-i', '/home/brajam/.ssh/id_ed25519', '-p', '2002', 'james@192.168.0.5']
REMOTE = """import os,pathlib,stat,json,time,hashlib,sys
def sanitized_error(kind,value,tb):
 while tb.tb_next:tb=tb.tb_next
 sys.stderr.write('journal_check_'+kind.__name__+'_line_'+str(tb.tb_lineno)+'\\n')
sys.excepthook=sanitized_error
base=pathlib.Path('/var/log/journal'); mode=sys.argv[1]
expected=json.loads(sys.argv[2]) if len(sys.argv)>2 else None
def info(p):
 s=p.lstat()
 assert p.resolve()==p and stat.S_ISREG(s.st_mode) and s.st_nlink==1 and s.st_uid==0
 assert p.parent.parent==base and len(p.parent.name)==32 and p.name.startswith('system@') and p.name.endswith('.journal')
 assert s.st_mtime<time.time()-72*3600
 digest=hashlib.sha256()
 with p.open('rb') as f:
  for block in iter(lambda:f.read(1024*1024),b''):digest.update(block)
 digest=digest.hexdigest()
 t=p.lstat();assert (s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns)==(t.st_dev,t.st_ino,t.st_size,t.st_mtime_ns,t.st_ctime_ns)
 return {'relative':str(p.relative_to(base)),'dev':s.st_dev,'ino':s.st_ino,'bytes':s.st_size,'allocated':s.st_blocks*512,
  'uid':s.st_uid,'gid':s.st_gid,'mode':stat.S_IMODE(s.st_mode),'mtime_ns':s.st_mtime_ns,'ctime_ns':s.st_ctime_ns,'sha256':digest,
  'xattr_names':sorted(os.listxattr(p))}
if expected is None:
 paths=sorted((p for p in base.glob('*/system@*.journal') if p.lstat().st_mtime<time.time()-72*3600),key=lambda p:p.lstat().st_mtime)
 rows=[info(p) for p in paths]
else:
 rows=[info(base/r['relative']) for r in expected];assert rows==expected
assert 0<len(rows)<=32 and sum(r['bytes'] for r in rows)<=3*1024**3
identities={(r['dev'],r['ino']) for r in rows}
for proc in pathlib.Path('/proc').iterdir():
 if not proc.name.isdigit():continue
 try: entries=list((proc/'fd').iterdir())
 except FileNotFoundError:continue
 for fd in entries:
  try:s=fd.stat()
  except FileNotFoundError:continue
  assert (s.st_dev,s.st_ino) not in identities
if mode=='retire':
 assert expected is not None
 removed=[]
 for row in rows:
  p=base/row['relative'];s=p.lstat()
  assert (s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns)==(row['dev'],row['ino'],row['bytes'],row['mtime_ns'],row['ctime_ns'])
  p.unlink();removed.append(row['relative'])
 print(json.dumps({'removed':removed,'allocated_bytes_removed':sum(r['allocated'] for r in rows)}))
else:print(json.dumps({'files':rows}))
"""


def need(ok):
    if not ok:
        raise RuntimeError('archived_journal_preservation_failed')


def saved_password():
    spec = importlib.util.spec_from_file_location('journal_saved_credential', Path(__file__).with_name('saved-node-credential.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.existing_password()


def query(password, mode, expected=None):
    args = ['sudo', '-S', '-k', '-p', '', 'python3', '-c', REMOTE, mode]
    if expected is not None:
        args.append(json.dumps(expected, separators=(',', ':')))
    result = subprocess.run(SSH + [shlex.join(args)], input=(password + '\n').encode(),
                            capture_output=True, timeout=120)
    if result.returncode:
        import re
        code = re.search(rb'journal_check_[A-Za-z]+_line_[0-9]+', result.stderr)
        raise RuntimeError(code.group().decode() if code else 'bounded_journal_query_failed')
    need(len(result.stdout) <= 65536)
    return json.loads(result.stdout)


class HashedPipe:
    def __init__(self, stream):
        self.stream, self.hashed, self.deadline = stream, hashlib.sha256(), time.monotonic() + 600

    def read(self, count):
        remaining = self.deadline - time.monotonic()
        need(remaining > 0 and select.select([self.stream], [], [], remaining)[0])
        raw = os.read(self.stream.fileno(), min(count, 1024 * 1024))
        self.hashed.update(raw)
        return raw


def stop(process):
    if process and process.poll() is None:
        process.kill()
        process.wait(timeout=10)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--inspect', action='store_true')
    mode.add_argument('--continue-initialization', action='store_true')
    args = parser.parse_args()
    if args.inspect:
        rows = query(saved_password(), 'inspect')['files']
        print(json.dumps({'closed_unchanged_unreferenced_files': len(rows),
                          'allocated_bytes': sum(r['allocated'] for r in rows), 'mutations': 0}))
        return
    need(os.getuid() == 1000 and ROOT.parent.resolve(strict=True) == ROOT.parent)
    need(shutil.disk_usage('/mnt/c').free > 15 * 1024**3 and shutil.disk_usage('/mnt/h').free > 18 * 1024**3)
    if args.continue_initialization:
        need(ROOT.resolve(strict=True) == ROOT and ROOT.stat().st_uid == os.getuid()
             and ROOT.stat().st_mode & 0o777 == 0o700 and {p.name for p in ROOT.iterdir()} == {'receipt.json'})
        old = json.loads((ROOT / 'receipt.json').read_text())
        need(old['state'] == 'failed-preserve-and-inspect-before-retry' and old['source_retired'] is False
             and 'files' not in old and 'retirement_intent' not in old)
    else:
        need(not ROOT.exists())
        ROOT.mkdir(mode=0o700)
    state = {'scope': 'Encrypted preservation of inactive archived system journals only',
             'host': '192.168.0.5', 'state': 'inspecting', 'source_retired': False,
             'plaintext_persisted': False, 'remaining_consumer': 'Unique original node history; preserve encrypted archive and restore metadata'}
    if args.continue_initialization:
        state['prior_initialization_failure'] = 'Python3.10 lacks hashlib.file_digest; no file copy or retirement started'
    def save():
        path = ROOT / 'receipt.json'
        pending = ROOT / 'receipt.next'
        fd = os.open(pending, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, 'w') as out:
            json.dump(state, out, indent=2)
            out.write('\n')
            out.flush()
            os.fsync(out.fileno())
        pending.replace(path)
        fd = os.open(ROOT, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    password = source = encryptor = decryptor = None
    try:
        password = saved_password()
        rows = query(password, 'inspect')['files']
        need(sum(r['bytes'] for r in rows) >= 1700 * 1024**2)
        state.update(files=rows, state='copying')
        save()
        command = ['sudo', '-S', '-k', '-p', '', 'tar', '--format=pax', '--gzip', '--acls', '--xattrs',
                   '--xattrs-include=*', '--numeric-owner', '--atime-preserve=system',
                   '-C', '/var/log/journal', '-cf', '-', '--'] + [r['relative'] for r in rows]
        source = subprocess.Popen(SSH + [shlex.join(command)], stdin=subprocess.PIPE,
                                  stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        source.stdin.write((password + '\n').encode())
        source.stdin.close()
        partial = ROOT / 'archived-system-journals.tar.gz.age.partial'
        final = ROOT / 'archived-system-journals.tar.gz.age'
        encryptor = subprocess.Popen([str(RUNTIME / 'bin/age'), '-R', '/home/brajam/.ssh/id_ed25519.pub',
            '-o', str(partial)], stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        incoming = HashedPipe(source.stdout)
        while block := incoming.read(1024 * 1024):
            encryptor.stdin.write(block)
        encryptor.stdin.close()
        need(source.wait(timeout=30) == 0 and encryptor.wait(timeout=30) == 0)
        with partial.open('rb') as encrypted:
            os.fsync(encrypted.fileno())
        decryptor = subprocess.Popen([str(RUNTIME / 'bin/age'), '-d', '-i', '/home/brajam/.ssh/id_ed25519', str(partial)],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        recovered = HashedPipe(decryptor.stdout)
        expected = {r['relative']: r for r in rows}
        seen = set()
        with tarfile.open(fileobj=recovered, mode='r|gz') as archive:
            for member in archive:
                need(member.name in expected and member.name not in seen and member.isfile())
                row = expected[member.name]
                need((member.size, member.uid, member.gid, member.mode) == (row['bytes'], row['uid'], row['gid'], row['mode']))
                need(int(Decimal(member.pax_headers.get('mtime', str(member.mtime))) * 10**9) == row['mtime_ns'])
                digest = hashlib.sha256()
                with archive.extractfile(member) as content:
                    while block := content.read(1024 * 1024):
                        digest.update(block)
                need(digest.hexdigest() == row['sha256'])
                seen.add(member.name)
        while recovered.read(1024 * 1024):
            pass
        need(decryptor.wait(timeout=30) == 0 and seen == set(expected) and
             incoming.hashed.digest() == recovered.hashed.digest())
        partial.rename(final)
        with final.open('rb') as encrypted:
            state['ciphertext_sha256'] = hashlib.file_digest(encrypted, 'sha256').hexdigest()
        state.update(state='preserved-verified', ciphertext_bytes=final.stat().st_size,
                     authenticated_tar_stream_equal=True, all_original_file_hashes_equal=True,
                     ownership_modes_mtimes_preserved=True)
        save()
        query(password, 'inspect', rows)
        state['retirement_intent'] = True
        save()
        result = query(password, 'retire', rows)
        need(set(result['removed']) == set(expected))
        state.update(state='completed', source_retired=True, **result)
        save()
        print(json.dumps({'state': state['state'], 'files_preserved': len(rows),
                          'allocated_bytes_removed': result['allocated_bytes_removed'],
                          'ciphertext_bytes': state['ciphertext_bytes'], 'plaintext_persisted': False}))
    except Exception as error:
        state['state'] = 'failed-preserve-and-inspect-before-retry'
        state['failure_kind'] = str(error) if isinstance(error, RuntimeError) else type(error).__name__
        save()
        raise RuntimeError('archived_journal_preservation_failed; inspect existing receipt') from None
    finally:
        password = None
        for process in (source, encryptor, decryptor):
            stop(process)
            if process:
                for stream in (process.stdin, process.stdout, process.stderr):
                    if stream and not stream.closed:
                        stream.close()


if __name__ == '__main__':
    try:
        main()
    except RuntimeError as error:
        print(str(error), file=__import__('sys').stderr)
        raise SystemExit(1)
