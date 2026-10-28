#!/usr/bin/env python3
"""Stream two exact retired public trees into authenticated native-WSL archives."""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import shlex
import stat
import subprocess
import tarfile
import threading
import uuid

RUNTIME = Path('/home/brajam/.local/share/branconet-migration')
AGE = RUNTIME / 'bin/age'
KEY = Path('/home/brajam/.ssh/id_ed25519')
RECIPIENT = Path('/home/brajam/.ssh/id_ed25519.pub')
AGE_SHA = 'eb7dd1b518f0a307c99cd97782623c5321da049154b04acd2d98d21aa7bc9b2c'
NAMES = {k: 'root-custom-kubectl-build-20261012-' + k for k in ('b5d6d1', 'f73dc0')}
SSH = ['/usr/bin/ssh', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes',
       '-o', 'IdentitiesOnly=yes', '-o', 'ForwardAgent=no', '-o', 'ConnectTimeout=10',
       '-o', 'ServerAliveInterval=15', '-o', 'ServerAliveCountMax=2', '-i', str(KEY),
       '-p', '2002', 'james@192.168.0.4']


def need(ok, category='offload_prerequisite_refused'):
    if not ok:
        raise ValueError(category)


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 ** 2), b''):
            h.update(chunk)
    return h.hexdigest()


def write_new(path, data):
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), 'w') as stream:
        json.dump(data, stream, indent=2, sort_keys=True)
        stream.write('\n'); stream.flush(); os.fsync(stream.fileno())


def protected(path, private=False):
    need(path.is_absolute() and path.resolve() == path)
    info = path.lstat()
    need(stat.S_ISREG(info.st_mode) and info.st_uid == os.getuid() and not info.st_mode & (0o077 if private else 0o022))
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


class HashReader:
    def __init__(self, stream):
        self.stream = stream
        self.sha = hashlib.sha256()
        self.bytes = 0

    def read(self, size=-1):
        need(size >= 0, 'unbounded_archive_read_refused')
        data = self.stream.read(size)
        self.sha.update(data); self.bytes += len(data)
        need(self.bytes <= 18 * 1024 ** 3, 'decrypted_archive_bound')
        return data


def verify(cipher, key, remote_proof, children):
    child = subprocess.Popen([str(AGE), '-d', '-i', str(KEY), str(cipher)],
        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    children.append(child)
    reader = HashReader(child.stdout)
    count = files = size = 0
    names = set()
    with tarfile.open(fileobj=reader, mode='r|') as archive:
        for item in archive:
            path = Path(item.name)
            need(not path.is_absolute() and '..' not in path.parts and path.parts[0] == NAMES[key], 'unexpected_archive_member')
            need(item.name not in names, 'duplicate_archive_member')
            names.add(item.name); count += 1
            need(count <= 500000, 'archive_entry_bound')
            need(item.isfile() or item.isdir() or item.issym() or item.islnk() or item.isfifo(), 'unexpected_archive_entry_type')
            if item.islnk():
                need(not Path(item.linkname).is_absolute() and '..' not in Path(item.linkname).parts
                     and Path(item.linkname).parts[0] == NAMES[key], 'foreign_archive_hardlink')
            if item.isfile():
                files += 1; size += item.size
                need(size <= 16 * 1024 ** 3, 'archive_file_byte_bound')
                contents = archive.extractfile(item)
                while contents.read(1024 ** 2):
                    pass
    # Tar's end marker is not age's authentication boundary: drain all remaining bytes.
    while reader.read(1024 ** 2):
        pass
    need(child.wait(timeout=30) == 0, 'authenticated_decryption_failed')
    need(reader.sha.hexdigest() == remote_proof['stream_sha256'] and reader.bytes == remote_proof['stream_bytes'], 'end_to_end_tar_hash_mismatch')
    need(count == remote_proof['source']['entries'], 'archive_source_entry_count_mismatch')
    return {'authenticated_full_decryption': True, 'tar_stream_sha256': reader.sha.hexdigest(),
            'tar_stream_bytes': reader.bytes, 'entries': count, 'regular_files': files, 'logical_file_bytes': size}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=('inspect', 'archive', 'clear-cache'), required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--additional-units-json', default='[]')
    parser.add_argument('--selected-caches-json', default='[]')
    parser.add_argument('--verified-receipt', type=Path)
    parser.add_argument('--reviewed-receipt-sha256', default='')
    args = parser.parse_args()
    os.umask(0o077); os.nice(10)
    password = os.environ.pop('BRANCONET_MIGRATION_SUDO_PASSWORD', '')
    need(0 < len(password) <= 256 and not any(c in password for c in '\r\n\x00'))
    credential = (password + '\n').encode(); password = None
    output = args.output_dir
    need(output.is_absolute() and output.resolve() == output and output.is_relative_to(RUNTIME)
         and output.name.startswith('retired-kubectl-offload-20261023'))
    need(not any((ancestor / '.git').exists() for ancestor in [output, *output.parents]), 'evidence_inside_git')
    output.mkdir(mode=0o700, parents=True, exist_ok=True)
    info = output.lstat()
    need(info.st_uid == os.getuid() and not info.st_mode & 0o077)
    fs = json.loads(subprocess.check_output(['/usr/bin/findmnt', '--json', '--target', str(output), '--output', 'FSTYPE,SOURCE'], text=True))['filesystems'][0]
    need(fs['fstype'] == 'ext4', 'native_wsl_ext4_required')
    units = json.loads(args.additional_units_json)
    selected = json.loads(args.selected_caches_json)
    need(isinstance(units, list) and isinstance(selected, list) and len(selected) == len(set(selected))
         and set(selected) <= set(NAMES), 'invalid_cache_selection')
    run = output / (args.mode + '-' + uuid.uuid4().hex)
    run.mkdir(mode=0o700)
    children = []
    expired = threading.Event()

    def terminate():
        expired.set()
        for child in list(children):
            if child.poll() is None:
                child.terminate()
        for child in list(children):
            if child.poll() is None:
                try:
                    child.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    child.kill()

    timer = threading.Timer(1800, terminate)
    timer.daemon = True; timer.start()
    remote_source = Path(__file__).with_name('remote_artifacts.py').read_text()

    def remote(mode, key, proof=None, streaming=False):
        specification = json.dumps({'additional_units': units, 'proof': proof})
        argv = ['sudo', '-S', '-k', '-p', '', '/usr/bin/python3', '-c', remote_source, mode, key, specification]
        child = subprocess.Popen(SSH + [shlex.join(argv)], stdin=subprocess.PIPE,
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        children.append(child)
        if streaming:
            child.stdin.write(credential); child.stdin.close()
            return child
        stdout, _ = child.communicate(credential, timeout=180)
        need(child.returncode == 0 and len(stdout) <= 2 * 1024 ** 2 and not expired.is_set(), 'remote_metadata_or_cache_operation_failed')
        return json.loads(stdout)

    receipt = {'schema': 1, 'mode': args.mode, 'status': 'started', 'host': 'masternode',
               'started_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
               'selected_caches': selected, 'additional_units': units,
               'helper_sha256': digest(Path(__file__)),
               'remote_helper_sha256': hashlib.sha256(remote_source.encode()).hexdigest(),
               'source_or_output_deletion_authorized': False}
    try:
        if args.mode == 'inspect':
            receipt['inspections'] = {key: remote('inspect', key) for key in NAMES}
        else:
            pins = {path: protected(path, private=path == KEY) for path in (AGE, KEY, RECIPIENT)}
            need(digest(AGE) == AGE_SHA, 'age_binary_checksum_mismatch')
            if args.mode == 'archive':
                need(not selected, 'archive_phase_cannot_select_deletion')
                observations = {key: remote('inspect', key) for key in NAMES}
                available = os.statvfs(output)
                need(available.f_bavail * available.f_frsize >= sum(v['source']['logical_bytes'] + v['source']['entries'] * 2048 for v in observations.values()) + 2 * 1024 ** 3,
                     'native_wsl_capacity_insufficient')
                receipt['archives'] = {}
                for key in NAMES:
                    cipher = run / (NAMES[key] + '.tar.age.partial')
                    producer = remote('archive', key, streaming=True)
                    plaintext = hashlib.sha256(); total = 0
                    with cipher.open('xb') as stream:
                        encryptor = subprocess.Popen([str(AGE), '-R', str(RECIPIENT)], stdin=subprocess.PIPE,
                            stdout=stream, stderr=subprocess.DEVNULL, env=dict(os.environ, GOMAXPROCS='2'))
                        children.append(encryptor)
                        for chunk in iter(lambda: producer.stdout.read(1024 ** 2), b''):
                            total += len(chunk); need(total <= 18 * 1024 ** 3 and not expired.is_set(), 'archive_stream_bound_or_timeout')
                            capacity = os.statvfs(output)
                            need(capacity.f_bavail * capacity.f_frsize >= 2 * 1024 ** 3, 'native_wsl_reserve_floor')
                            plaintext.update(chunk); encryptor.stdin.write(chunk)
                        encryptor.stdin.close()
                        need(encryptor.wait(timeout=60) == 0, 'age_encryption_failed')
                        stream.flush(); os.fsync(stream.fileno())
                    need(producer.wait(timeout=30) == 0, 'source_archive_failed')
                    stderr = producer.stderr.read(2 * 1024 ** 2)
                    proof = json.loads(stderr.splitlines()[-1])
                    need(proof['state'] == 'stream-complete-source-stable'
                         and proof['source'] == observations[key]['source']
                         and proof['stream_sha256'] == plaintext.hexdigest() and proof['stream_bytes'] == total,
                         'source_transport_binding_failed')
                    verification = verify(cipher, key, proof, children)
                    final = cipher.with_suffix('')
                    need(not final.exists()); cipher.rename(final)
                    receipt['archives'][key] = {'path': str(final), 'ciphertext_sha256': digest(final),
                        'ciphertext_bytes': final.stat().st_size, 'remote': proof, 'verification': verification}
                    write_new(run / (key + '-verified-archive.json'), receipt['archives'][key])
            else:
                need(selected and args.verified_receipt and len(args.reviewed_receipt_sha256) == 64,
                     'explicit_reviewed_archive_receipt_and_cache_selection_required')
                protected(args.verified_receipt, private=True)
                need(digest(args.verified_receipt) == args.reviewed_receipt_sha256, 'reviewed_receipt_hash_changed')
                verified = json.loads(args.verified_receipt.read_text())
                need(verified['mode'] == 'archive' and verified['status'] == 'verified-no-deletion'
                     and set(verified['archives']) == set(NAMES), 'both_whole_tree_archives_required')
                for key, record in verified['archives'].items():
                    cipher = Path(record['path']); protected(cipher, private=True)
                    need(cipher.is_relative_to(output) and digest(cipher) == record['ciphertext_sha256'], 'reviewed_archive_changed')
                    verify(cipher, key, record['remote'], children)
                receipt['reviewed_archive_receipt_sha256'] = args.reviewed_receipt_sha256
                write_new(run / 'reviewed-cache-clear-plan.json', {
                    'reviewed_receipt_sha256': args.reviewed_receipt_sha256, 'selected_caches': selected,
                    'exact_paths': {key: verified['archives'][key]['remote']['source']['cache'] for key in selected}})
                receipt['cache_results'] = {}
                for key in selected:
                    receipt['cache_results'][key] = remote('clear-cache', key, verified['archives'][key]['remote'])
                    write_new(run / (key + '-cache-clear-result.json'), receipt['cache_results'][key])
            need(not expired.is_set(), 'offload_deadline')
            for path, identity in pins.items():
                need(protected(path, private=path == KEY) == identity, 'encryption_or_identity_input_changed')
        receipt['status'] = 'verified-no-deletion' if args.mode == 'archive' else 'completed'
        receipt['completed_at'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        write_new(run / 'receipt.json', receipt)
        print(json.dumps({'status': receipt['status'], 'receipt': str(run / 'receipt.json')}))
        return 0
    except Exception as error:
        receipt.update(status='failed-retained-no-automatic-cleanup', error_type=type(error).__name__)
        write_new(run / 'receipt.json', receipt)
        print(json.dumps({'status': receipt['status'], 'receipt': str(run / 'receipt.json')}))
        return 1
    finally:
        timer.cancel()
        terminate()
        credential = None


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception:
        raise SystemExit('Retired public build offload refused invalid prerequisites; no credential diagnostics are emitted')
