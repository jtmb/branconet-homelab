#!/usr/bin/env python3
"""Sequential exact-candidate transport; never deploy or rebuild BORTUS.

--check performs current private registry/archive/source-script checks only.
--preload additionally reads {"sudo_password": ...} on protected stdin. No replay.
"""
import argparse
import datetime
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shlex
import shutil
import stat
import subprocess
import sys
import threading


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(filename))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


node = load('qualified_preload_node', 'bortus-secured-preload-node.py')
publisher = load('qualified_preload_publication', 'publish-qualified-bortus-image.py')
ROOT = Path('/mnt/h/AgentArtifacts/projects/branconet/builds/wsl-artifact-store/files/bortus-operator-recovery/empty-list-fix')
ARCHIVE = ROOT / 'secured-image.oci.tar'
HOSTS = ('192.168.0.4', '192.168.0.5', '192.168.0.6')
RECEIPT = ROOT / 'preload.json'


def need(ok):
    if not ok:
        raise RuntimeError('qualified_preload_refused')


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def stamp(fd):
    s = os.fstat(fd)
    return s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns


def save(record):
    path = RECEIPT
    pending = path.with_suffix('.next')
    fd = os.open(pending, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'w') as out:
        json.dump(record, out, indent=2)
        out.write('\n')
        out.flush()
        os.fsync(out.fileno())
    os.replace(pending, path)
    directory = os.open(ROOT, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


def check(source):
    need(os.geteuid() == 0 and ROOT.resolve(strict=True) == ROOT and
         ROOT.stat().st_uid == 0 and stat.S_IMODE(ROOT.stat().st_mode) == 0o700)
    need(os.fstat(source.fileno()).st_dev == ROOT.stat().st_dev and
         stat.S_ISREG(os.fstat(source.fileno()).st_mode))
    need(shutil.disk_usage('/mnt/c').free > 15 * 1024**3 and
         shutil.disk_usage('/mnt/h').free > 15 * 1024**3)
    before = stamp(source.fileno())
    need(before[2] == node.ARCHIVE_BYTES and
         hashlib.file_digest(source, 'sha256').hexdigest() == node.ARCHIVE_SHA)
    need(stamp(source.fileno()) == before)
    source.seek(0)
    publication = json.loads((ROOT / 'publication.json').read_text())
    need(publication.get('manifest') == node.MANIFEST and
         publication.get('state') == 'published-private' and
         publication.get('remote_config_and_graph_verified') is True and
         publication.get('current_unfiltered_security_scan_passed') is True)
    helper = Path(__file__).with_name('windows-docker-credential-bortus.py')
    publisher.verify_private_repository(helper)
    token = publisher.registry_token(helper)
    manifest = publisher.document(token, node.MANIFEST)
    config = publisher.document(token, node.CONFIG, kind='blobs')
    need(manifest['digest'] == node.MANIFEST and
         manifest['value']['config']['digest'] == node.CONFIG and
         config['digest'] == node.CONFIG and
         config['value']['config']['Labels']['org.opencontainers.image.revision'] == node.SOURCE)
    return before


def transfer(host, password, source, pinned):
    script_path = Path(__file__).with_name('bortus-secured-preload-node.py')
    script = script_path.read_text()
    script_sha = hashlib.sha256(script_path.read_bytes()).hexdigest()
    command = ['/usr/bin/ssh', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes',
        '-o', 'ForwardAgent=no', '-o', 'ConnectTimeout=15', '-o',
        'UserKnownHostsFile=/home/brajam/.ssh/known_hosts', '-i',
        '/home/brajam/.ssh/id_ed25519', '-p', '2002', 'james@' + host,
        'python3 -c ' + shlex.quote(script)]
    source.seek(0)
    need(stamp(source.fileno()) == pinned)
    envelope = {'protocol': 'bortus-qualified-preload/v1',
                'image_reference': node.REFERENCE, 'sudo_password': password}
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, start_new_session=True)
    failures = []

    def write():
        try:
            process.stdin.write((json.dumps(envelope) + '\n').encode())
            for block in iter(lambda: source.read(1024 * 1024), b''):
                process.stdin.write(block)
            process.stdin.flush()
        except Exception:
            failures.append(True)
        finally:
            try:
                process.stdin.close()
            except Exception:
                failures.append(True)

    writer = threading.Thread(target=write, daemon=True)
    writer.start()
    try:
        code = process.wait(timeout=1500)
        writer.join(timeout=10)
        if writer.is_alive() or failures or code!=0:raise RuntimeError('secured_transfer_failed:'+str(code)+':'+process.stderr.read(4096).decode(errors='replace'))
        raw = process.stdout.read(8193)
        need(len(raw) <= 8192 and stamp(source.fileno()) == pinned and
             hashlib.sha256(script_path.read_bytes()).hexdigest() == script_sha)
        reply = json.loads(raw)
        need(reply.get('protocol') == 'bortus-qualified-preload/v1' and
             reply.get('source_commit') == node.SOURCE and
             reply.get('image_reference') == node.REFERENCE and
             reply.get('manifest_digest') == node.MANIFEST and reply.get('config_digest') == node.CONFIG and
             reply.get('archive_sha256') == node.ARCHIVE_SHA and reply.get('archive_bytes') == node.ARCHIVE_BYTES and
             reply.get('all_layer_blobs_verified') is True and
             reply.get('fully_downloaded_and_unpacked') is True and
             reply.get('disk_archive_created') is False and reply.get('deployed') is False)
        return reply
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=10)
        writer.join(timeout=10)
        process.stdout.close()
        envelope.clear()


def main():
    global RECEIPT
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--check', action='store_true')
    mode.add_argument('--preload', action='store_true')
    mode.add_argument('--preload-saved', action='store_true',
                      help='Use the existing native vaulted node credential in memory')
    parser.add_argument('--host', choices=HOSTS, help='Stage one node; full three-node acceptance remains required')
    parser.add_argument('--resume-capacity', action='store_true', help='Reconcile only the inspected node03 pre-import capacity stop')
    args = parser.parse_args()
    hosts = (args.host,) if args.host else HOSTS
    if args.host:
        RECEIPT = ROOT / ('preload-' + args.host + '.json')
    password = None
    if args.preload_saved:
        password = load('existing_saved_node_credential', 'saved-node-credential.py').existing_password()
    if args.preload:
        raw = sys.stdin.buffer.read(8193)
        need(len(raw) <= 8192)
        request = json.loads(raw)
        need(set(request) == {'sudo_password'})
        password = request.pop('sudo_password')
        need(type(password) is str and 0 < len(password.encode()) <= 4096 and
             not any(c in password for c in '\0\r\n'))
    fd = os.open(ARCHIVE, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, 'rb') as source:
        pinned = check(source)
        if args.check:
            print(json.dumps({'current_private_registry_archive_check': True,
                              'image_reference': node.REFERENCE, 'node_imports': 0}))
            return
        lock_fd = os.open(ROOT / 'preload.lock', os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            if args.resume_capacity:
                need(args.host=='192.168.0.5')
                stopped=json.loads(RECEIPT.read_bytes());inspection=json.loads((ROOT/'preload-inspection-node03-capacity.json').read_bytes());cleanup=json.loads((ROOT/'node03-apt-cache-cleanup.json').read_bytes())
                need(stopped['state']=='stopped' and stopped['image_reference']==node.REFERENCE and len(stopped['nodes'])==1 and stopped['nodes'][0]['state']=='uncertain-inspect-before-retry' and inspection['image_digest']is None and cleanup['removed']is True and cleanup['removed_allocated_bytes']==142913536)
                preserved=ROOT/'preload-192.168.0.5-capacity-failure.json';need(not preserved.exists());RECEIPT.rename(preserved)
            need(not RECEIPT.exists() and not RECEIPT.with_suffix('.next').exists())
            record = {'scope': 'Exact private candidate import only; no deployment/adoption acceptance',
                      'started_at_utc': now(), 'image_reference': node.REFERENCE, 'nodes': [], 'state': 'starting'}
            save(record)
            for host in hosts:
                entry = {'host': host, 'state': 'pending'}
                record['nodes'].append(entry)
                save(record)
                try:
                    entry.update(transfer(host, password, source, pinned), state='verified')
                except Exception:
                    entry['state'] = 'uncertain-inspect-before-retry'
                    record['state'] = 'stopped'
                    save(record)
                    raise
                save(record)
            record.update(state='completed', completed_at_utc=now())
            save(record)
            print(json.dumps({'image_reference': node.REFERENCE, 'verified_nodes': len(hosts), 'deployed': False}))
        finally:
            password = None
            os.close(lock_fd)


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print(str(error)[:4500], file=sys.stderr)
        raise SystemExit(1)
