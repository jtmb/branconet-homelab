#!/usr/bin/env python3
"""Stream cold SQLite files directly through age; never persist plaintext."""
import hashlib
import hmac
import json
import os
import pathlib
import selectors
import stat
import struct
import subprocess
import time

MAGIC = b'BORTUS1\n'
FILES = ('bortus.db', 'bortus.db-wal', 'bortus.db-shm', 'bortus.db-journal')
MAX_FILE = 256 * 1024 * 1024
MAX_TOTAL = 512 * 1024 * 1024
CHUNK = 65536
NODE_READER = r"""
const fs=require('node:fs');
const names=['bortus.db','bortus.db-wal','bortus.db-shm','bortus.db-journal'];
async function put(b){if(!process.stdout.write(b))await new Promise((r,j)=>{const clean=()=>{process.stdout.removeListener('drain',ok);process.stdout.removeListener('error',bad);};const ok=()=>{clean();r();};const bad=()=>{clean();j(new Error('READ_FAILED'));};process.stdout.once('drain',ok);process.stdout.once('error',bad);});}
async function header(o){const b=Buffer.from(JSON.stringify(o));const n=Buffer.alloc(4);n.writeUInt32BE(b.length);await put(n);await put(b);}
(async()=>{
 await put(Buffer.from('BORTUS1\n'));let total=0;const found=[],missing=[];
 for(const name of names){
  const path='/data/'+name;let fd;
  try{fd=fs.openSync(path,fs.constants.O_RDONLY|fs.constants.O_NOFOLLOW|fs.constants.O_NONBLOCK);}
  catch(e){if(e.code==='ENOENT'&&name!=='bortus.db'){missing.push(path);continue;}throw new Error('READ_FAILED');}
  try{
   const before=fs.fstatSync(fd,{bigint:true}),size=Number(before.size);
   if(!before.isFile()||size>268435456||total+size>536870912)throw new Error('READ_FAILED');
   total+=size;found.push(name);await header({name,size});
   if(size){for await(const b of fs.createReadStream(path,{fd,autoClose:false,highWaterMark:65536,start:0,end:size-1}))await put(b);}
   const after=fs.fstatSync(fd,{bigint:true});
   if(['dev','ino','size','mtimeNs','ctimeNs'].some(k=>before[k]!==after[k]))throw new Error('READ_FAILED');
  }finally{fs.closeSync(fd);}
 }
 for(const path of missing){try{fs.lstatSync(path);}catch(e){if(e.code==='ENOENT')continue;throw e;}throw new Error('READ_FAILED');}
 await header({complete:true,files:found});
})().catch(()=>{process.stderr.write('Cold SQLite read failed\n');process.exitCode=1;});
"""


class ArchiveError(Exception):
    pass


def require(condition):
    if not condition:
        raise ArchiveError('cold_sqlite_archive_failed')


class Pipe:
    """Bound every pipe read/write by the operation's monotonic deadline."""
    def __init__(self, stream, deadline, reading):
        self.stream = stream
        self.fd = stream.fileno()
        self.deadline = deadline
        self.reading = reading
        os.set_blocking(self.fd, False)
        self.selector = selectors.DefaultSelector()
        self.selector.register(self.fd, selectors.EVENT_READ if reading else selectors.EVENT_WRITE)

    def ready(self):
        remaining = self.deadline - time.monotonic()
        require(remaining > 0 and self.selector.select(remaining))

    def read(self, count):
        while True:
            self.ready()
            try:
                return os.read(self.fd, count)
            except BlockingIOError:
                continue

    def write(self, data):
        pending = memoryview(data)
        while pending:
            self.ready()
            try:
                count = os.write(self.fd, pending)
                require(count > 0)
                pending = pending[count:]
            except BlockingIOError:
                continue

    def close(self):
        self.selector.close()


def exact(reader, count):
    parts = []
    while count:
        piece = reader.read(min(count, CHUNK))
        require(piece and len(piece) <= count)
        parts.append(piece)
        count -= len(piece)
    return b''.join(parts)


def transfer(reader, writer, *, file_factory=None):
    """Validate framing and bound allocations; return only an in-memory digest."""
    digest = hashlib.sha256()

    def send(data):
        digest.update(data)
        if writer:
            writer.write(data)

    magic = exact(reader, len(MAGIC))
    require(magic == MAGIC)
    send(magic)
    found, total = [], 0
    while True:
        prefix = exact(reader, 4)
        length = struct.unpack('>I', prefix)[0]
        require(0 < length <= 1024)
        raw = exact(reader, length)
        try:
            def unique(pairs):
                require(len({k for k, _ in pairs}) == len(pairs))
                return dict(pairs)
            header = json.loads(raw, object_pairs_hook=unique)
        except (ValueError, UnicodeError):
            raise ArchiveError('cold_sqlite_archive_failed') from None
        require(isinstance(header, dict))
        send(prefix)
        send(raw)
        if set(header) == {'complete', 'files'}:
            require(header['complete'] is True and header['files'] == found and
                    found and found[0] == 'bortus.db' and not reader.read(1))
            return {'files': found, 'total_bytes': total}, digest.digest()
        require(set(header) == {'name', 'size'})
        name, size = header['name'], header['size']
        require(name in FILES and name not in found and
                (not found and name == FILES[0] or found and FILES.index(name) > FILES.index(found[-1])) and
                type(size) is int and 0 <= size <= MAX_FILE and total + size <= MAX_TOTAL)
        if name == 'bortus.db':
            require(size >= 512)
        found.append(name)
        total += size
        sink = file_factory(name, size) if file_factory else None
        try:
            remaining = size
            first = True
            while remaining:
                chunk = exact(reader, min(remaining, CHUNK))
                if first and name == 'bortus.db':
                    require(chunk.startswith(b'SQLite format 3\x00'))
                send(chunk)
                if sink:
                    sink.write(chunk)
                remaining -= len(chunk)
                first = False
        finally:
            if sink:
                sink.close()


def stop_owned(process):
    if process is not None and process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=3)


def encrypt_source(source, target, age, recipient_file, identity_file, deadline, *, directory_fd=None, cleanup=None):
    """Own child handles and encrypted partials; failed artifacts are never accepted."""
    require(cleanup is None or callable(cleanup))
    target = pathlib.Path(target)
    encryptor = decryptor = None
    parent_fd = None
    pipes = []
    try:
        parent_fd = os.dup(directory_fd) if directory_fd is not None else os.open(
            target.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        parent = os.fstat(parent_fd)
        require(stat.S_ISDIR(parent.st_mode) and parent.st_uid == os.getuid() and
                stat.S_IMODE(parent.st_mode) == 0o700)
        parent_identity = (parent.st_dev, parent.st_ino, parent.st_uid)

        def verify_parent():
            for item in (os.fstat(parent_fd), target.parent.lstat()):
                require(stat.S_ISDIR(item.st_mode) and stat.S_IMODE(item.st_mode) == 0o700 and
                        (item.st_dev, item.st_ino, item.st_uid) == parent_identity)

        verify_parent()
        fd = os.open(target.name, os.O_CREAT | os.O_EXCL | os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK,
                     0o600, dir_fd=parent_fd)
        with os.fdopen(fd, 'w+b', buffering=0) as out:
            created = os.fstat(out.fileno())
            created_identity = (created.st_dev, created.st_ino, created.st_uid)

            def verify_ciphertext(expected=None):
                verify_parent()
                current = os.fstat(out.fileno())
                named = os.stat(target.name, dir_fd=parent_fd, follow_symlinks=False)
                for item in (current, named):
                    require(stat.S_ISREG(item.st_mode) and stat.S_IMODE(item.st_mode) == 0o600 and
                            item.st_nlink == 1 and item.st_size <= MAX_TOTAL + 1024 * 1024 and
                            (item.st_dev, item.st_ino, item.st_uid) == created_identity)
                    if expected is not None:
                        require(all(getattr(item, key) == getattr(expected, key) for key in
                                    ('st_dev', 'st_ino', 'st_size', 'st_mtime_ns', 'st_ctime_ns')))
                require(time.monotonic() < deadline)
                return current

            verify_ciphertext()
            encryptor = subprocess.Popen([str(age), '-R', str(recipient_file)], stdin=subprocess.PIPE,
                stdout=out, stderr=subprocess.DEVNULL,
                **({'start_new_session': True} if cleanup is not None else {}))
            reader = Pipe(source.stdout, deadline, True)
            writer = Pipe(encryptor.stdin, deadline, False)
            pipes += [reader, writer]
            metadata, digest = transfer(reader, writer)
            encryptor.stdin.close()
            require(source.wait(timeout=max(0.01, deadline - time.monotonic())) == 0)
            require(encryptor.wait(timeout=max(0.01, deadline - time.monotonic())) == 0)
            out.flush()
            os.fsync(out.fileno())
            encrypted_state = verify_ciphertext()
            os.fsync(parent_fd)
            out.seek(0)
            decryptor = subprocess.Popen([str(age), '-d', '-i', str(identity_file)],
                stdin=out, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                **({'start_new_session': True} if cleanup is not None else {}))
            recovered = Pipe(decryptor.stdout, deadline, True)
            pipes.append(recovered)
            restored_metadata, restored_digest = transfer(recovered, None)
            require(decryptor.wait(timeout=max(0.01, deadline - time.monotonic())) == 0 and
                    restored_metadata == metadata and hmac.compare_digest(restored_digest, digest))
            verify_ciphertext(encrypted_state)
            encrypted_hash = hashlib.sha256()
            out.seek(0)
            while block := out.read(CHUNK):
                require(time.monotonic() < deadline)
                encrypted_hash.update(block)
            verify_ciphertext(encrypted_state)
            os.fsync(parent_fd)
        return {'artifact': str(target), 'ciphertext_sha256': encrypted_hash.hexdigest(),
                'files': metadata['files'], 'plaintext_bytes': metadata['total_bytes'],
                'authenticated_decryption_equal': True, 'plaintext_persisted': False,
                'sqlite_integrity_or_row_preservation_proven': False}
    except Exception:
        raise ArchiveError('cold_sqlite_archive_failed') from None
    finally:
        if cleanup is None:
            for pipe in pipes:
                pipe.close()
            for process in (source, encryptor, decryptor):
                stop_owned(process)
                if process:
                    for stream in (process.stdin, process.stdout, process.stderr):
                        if stream and not stream.closed:
                            stream.close()
            if parent_fd is not None:
                os.close(parent_fd)
        else:
            failed = False
            for pipe in pipes:
                try: pipe.close()
                except Exception: failed = True
            for process in (source, encryptor, decryptor):
                try: cleanup(process)
                except Exception: failed = True
                if process:
                    for stream in (process.stdin, process.stdout, process.stderr):
                        if stream and not stream.closed:
                            try: stream.close()
                            except Exception: failed = True
            if parent_fd is not None:
                try: os.close(parent_fd)
                except Exception: failed = True
            require(not failed)


def capture(checkpoint):
    require(checkpoint.cold())
    runtime = pathlib.Path.home() / '.local/share/branconet-migration'
    source = subprocess.Popen([str(runtime / 'bin/kubectl'), '--kubeconfig', str(runtime / 'admin.conf'),
        '--request-timeout=20s', 'exec', '-i', '-n', 'bortus',
        checkpoint.r['holder_identity']['name'], '-c', 'holder', '--', 'node', '-'],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    try:
        source.stdin.write(NODE_READER.encode())
        source.stdin.close()
        result = encrypt_source(source, checkpoint.journal.directory / 'sqlite-files.age',
            runtime / 'bin/age', pathlib.Path.home() / '.ssh/id_ed25519.pub',
            pathlib.Path.home() / '.ssh/id_ed25519', time.monotonic() + 300,
            directory_fd=checkpoint.journal.directory_fd)
        require(checkpoint.cold())
        run_id = checkpoint.r['run_id']
        require(len(run_id) == 12 and all(c in '0123456789abcdef' for c in run_id))
        nas = '/mnt/container-backups/k8s-migration-20261009/bortus-sqlite-' + run_id + '.age'
        copy = subprocess.run(['scp', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes',
            '-P', '2002', result['artifact'], 'james@192.168.0.4:' + nas],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120)
        require(copy.returncode == 0)
        check = subprocess.run(['ssh', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes',
            '-p', '2002', 'james@192.168.0.4', 'sha256sum', nas],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=20)
        require(check.returncode == 0 and len(check.stdout) < 4096 and
                check.stdout.split()[0].decode('ascii') == result['ciphertext_sha256'])
        result['nas_artifact'] = nas
        result['nas_ciphertext_equal'] = True
        require(checkpoint.cold())
        return result
    finally:
        stop_owned(source)
        for stream in (source.stdin, source.stdout, source.stderr):
            if stream and not stream.closed:
                stream.close()
