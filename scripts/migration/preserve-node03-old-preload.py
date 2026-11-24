"""Losslessly move one completed historical BORTUS staging tar to encrypted H."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shlex
import subprocess

spec = importlib.util.spec_from_file_location('old_preload_journal_transport',
    Path(__file__).with_name('preserve-node03-archived-journals.py'))
transport = importlib.util.module_from_spec(spec)
spec.loader.exec_module(transport)
SOURCE = '/home/james/.bortus-release-preload-5aba82c28d5cad1d571416ea9c06f5d2d61260b3/image.tar'
SHA = '97bf962ff6a54aca49b032c24b500d3031edd8cf426550b13466d1472bb1bd21'
SIZE = 478084096
CHECK = """import os,pathlib,stat,json,time,hashlib,sys
p=pathlib.Path(sys.argv[1]);expected=json.loads(sys.argv[2]) if len(sys.argv)>2 else None
assert str(p)=='/home/james/.bortus-release-preload-5aba82c28d5cad1d571416ea9c06f5d2d61260b3/image.tar'
s=p.lstat();assert p.resolve()==p and stat.S_ISREG(s.st_mode) and s.st_nlink==1 and s.st_uid==1000 and s.st_mtime<time.time()-72*3600
record=json.loads((p.parent/'record.json').read_text());assert record['phase']=='completed' and record['archive_sha256']=='97bf962ff6a54aca49b032c24b500d3031edd8cf426550b13466d1472bb1bd21'
h=hashlib.sha256()
with p.open('rb') as f:
 for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
assert s.st_size==478084096 and h.hexdigest()==record['archive_sha256']
result={'path':str(p),'dev':s.st_dev,'ino':s.st_ino,'size':s.st_size,'allocated':s.st_blocks*512,'mode':stat.S_IMODE(s.st_mode),'uid':s.st_uid,'gid':s.st_gid,'mtime_ns':s.st_mtime_ns,'ctime_ns':s.st_ctime_ns,'sha256':h.hexdigest()}
assert p.stat().st_mtime_ns==s.st_mtime_ns and p.stat().st_ctime_ns==s.st_ctime_ns
for proc in pathlib.Path('/proc').iterdir():
 if not proc.name.isdigit():continue
 try:entries=list((proc/'fd').iterdir())
 except FileNotFoundError:continue
 for fd in entries:
  try:t=fd.stat()
  except FileNotFoundError:continue
  assert (t.st_dev,t.st_ino)!=(s.st_dev,s.st_ino)
if expected is not None:
 assert result==expected
 t=p.lstat();assert (t.st_dev,t.st_ino,t.st_size,t.st_mtime_ns,t.st_ctime_ns)==(s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
 p.unlink();result['removed']=True
print(json.dumps(result))
"""


def main():
    root = transport.ROOT
    receipt = root / 'old-preload-retirement.json'
    need = transport.need
    need(root.is_dir() and not receipt.exists())
    password = source = encryptor = decryptor = None
    state = {'state': 'inspecting', 'source_retired': False, 'source': SOURCE,
             'remaining_consumer': 'Unique historical qualified image; lossless restoration before any future use',
             'plaintext_persisted': False}
    def save():
        fd = os.open(receipt, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, 'w') as out:
            json.dump(state, out, indent=2)
            out.write('\n'); out.flush(); os.fsync(out.fileno())
        fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    def query(expected=None):
        args = ['sudo', '-S', '-k', '-p', '', 'python3', '-c', CHECK, SOURCE]
        if expected is not None:
            args.append(json.dumps(expected, separators=(',', ':')))
        r = subprocess.run(transport.SSH + [shlex.join(args)], input=(password + '\n').encode(),
                           capture_output=True, timeout=60)
        need(r.returncode == 0 and len(r.stdout) < 4096)
        return json.loads(r.stdout)
    try:
        password = transport.saved_password()
        before = query()
        state.update(state='copying', source_metadata=before)
        save()
        partial = root / 'old-preload-5aba82c.oci.tar.age.partial'
        final = root / 'old-preload-5aba82c.oci.tar.age'
        need(not final.exists() and not partial.exists())
        source = subprocess.Popen(transport.SSH + [shlex.join(['cat', '--', SOURCE])],
                                  stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        encryptor = subprocess.Popen([str(transport.RUNTIME / 'bin/age'), '-R', '/home/brajam/.ssh/id_ed25519.pub', '-o', str(partial)],
            stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        incoming = transport.HashedPipe(source.stdout)
        count = 0
        while block := incoming.read(1024 * 1024):
            count += len(block); need(count <= SIZE); encryptor.stdin.write(block)
        encryptor.stdin.close()
        need(source.wait(timeout=30) == 0 and encryptor.wait(timeout=30) == 0 and count == SIZE
             and incoming.hashed.hexdigest() == SHA)
        with partial.open('rb') as file:
            os.fsync(file.fileno())
        decryptor = subprocess.Popen([str(transport.RUNTIME / 'bin/age'), '-d', '-i', '/home/brajam/.ssh/id_ed25519', str(partial)],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        recovered = transport.HashedPipe(decryptor.stdout)
        count = 0
        while block := recovered.read(1024 * 1024):
            count += len(block); need(count <= SIZE)
        need(decryptor.wait(timeout=30) == 0 and count == SIZE and recovered.hashed.hexdigest() == SHA)
        partial.rename(final)
        state.update(state='preserved-verified', authenticated_original_bytes_equal=True,
                     ciphertext_bytes=final.stat().st_size)
        save()
        state['retirement_intent'] = True
        save()
        after = query(before)
        need(after['removed'] is True)
        state.update(state='completed', source_retired=True, allocated_bytes_removed=before['allocated'])
        save()
        print(json.dumps({'state': state['state'], 'allocated_bytes_removed': before['allocated'],
                          'ciphertext_bytes': state['ciphertext_bytes'], 'plaintext_persisted': False}))
    except Exception:
        state['state'] = 'failed-preserve-and-inspect-before-retry'
        save()
        raise RuntimeError('old_preload_preservation_failed; inspect retained receipt') from None
    finally:
        password = None
        for process in (source, encryptor, decryptor):
            transport.stop(process)
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
