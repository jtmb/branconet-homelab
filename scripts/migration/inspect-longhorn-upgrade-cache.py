"""Read only exact public candidate blobs and native committed snapshot metadata."""
import argparse
import base64
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import socket
import stat
import subprocess
import sys

F = Path('/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025')
B = F / 'platform-upstream-review-20261027/longhorn-capacity-budget'


def need(value, reason):
    if not value:
        raise ValueError(reason)


def command(args):
    p = subprocess.run(args, capture_output=True, timeout=45)
    if p.returncode:
        print('native_metadata_failure:' + json.dumps({'command': args, 'exitCode': p.returncode,
              'stderr': p.stderr.decode(errors='replace')[-2000:],
              'stdout': p.stdout.decode(errors='replace')[-2000:]}), file=sys.stderr)
    need(p.returncode == 0 and len(p.stdout) <= 4 * 1024**2, 'bounded_native_metadata_read')
    return p.stdout


def remote(profile):
    need(os.geteuid() == 0 and socket.gethostname() == profile['hostname'], 'fixed_original_node_root')
    need(len(profile['blobs']) <= 256 and len(profile['chains']) <= 256, 'candidate_inventory_bounds')
    runtime = dict(line.split('=', 1) for line in command([
        'systemctl', 'show', 'containerd-k8s', '--property=MainPID,ActiveState']).decode().splitlines())
    need(runtime['ActiveState'] == 'active' and int(runtime['MainPID']) > 0, 'original_active_runtime')
    ctr = ['ctr', '--address', '/run/containerd-k8s/containerd.sock', '--namespace', 'k8s.io',
           'snapshots', '--snapshotter', 'overlayfs']
    table = command(ctr + ['list']).decode().splitlines()
    need(table and table[0].split() == ['KEY', 'PARENT', 'KIND'], 'native_snapshot_table_header')
    cells = [line.split() for line in table[1:] if line.strip()]
    need(all(len(row) in (2, 3) and row[-1].lower() in ('active', 'view', 'committed')
             for row in cells), 'native_snapshot_table_rows')
    kinds = {row[0]: row[-1].lower() for row in cells}
    keys = set(kinds)
    need(0 < len(keys) <= 10000, 'complete_native_snapshot_catalog')
    snapshots = {}
    for key, parent in profile['chains'].items():
        need(re.fullmatch(r'sha256:[0-9a-f]{64}', key), 'public_candidate_chain_id')
        if key in keys:
            info = json.loads(command(ctr + ['info', key]))
            need(info['Name'] == key and info.get('Parent', '') == parent, 'exact_native_snapshot_chain')
            snapshots[key] = {'nativeInfo': info, 'tableKind': kinds[key]}
    blobs = []
    base = Path('/var/lib/containerd-k8s/io.containerd.content.v1.content/blobs/sha256')
    need(base.resolve() == base and base.is_dir(), 'original_runtime_content_directory')
    for key, expected in profile['blobs'].items():
        need(re.fullmatch(r'sha256:[0-9a-f]{64}', key), 'public_candidate_blob_digest')
        path = base / key[7:]
        try:
            before = path.lstat()
        except FileNotFoundError:
            continue
        need(stat.S_ISREG(before.st_mode) and before.st_size <= 2 * 1024**3
             and (expected is None or before.st_size == expected), 'bounded_original_cached_blob')
        h = hashlib.sha256()
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(fd, 'rb') as source:
            need(os.fstat(source.fileno()).st_ino == before.st_ino, 'opened_cached_blob_inode')
            for block in iter(lambda: source.read(1024**2), b''):
                h.update(block)
        after = path.lstat()
        need((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns) ==
             (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns)
             and 'sha256:' + h.hexdigest() == key, 'stable_full_cached_blob_hash')
        blobs.append({'digest': key, 'bytes': before.st_size, 'allocatedBytes': before.st_blocks * 512,
                      'inode': before.st_ino, 'fullSHA256Verified': True})
    space = os.statvfs(base)
    filesystem = json.loads(command(['findmnt', '-J', '-T', str(base), '-o', 'UUID,FSTYPE,SOURCE']))['filesystems'][0]
    print(json.dumps({'UTC': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                     'hostname': socket.gethostname(), 'runtime': runtime, 'filesystem': filesystem,
                     'availableBytes': space.f_bavail * space.f_frsize, 'freeBytes': space.f_bfree * space.f_frsize,
                     'capacityBytes': space.f_blocks * space.f_frsize, 'blockSize': space.f_frsize,
                     'cachedCandidateBlobs': blobs, 'candidateSnapshots': snapshots,
                     'snapshotCatalogCount': len(keys), 'filesChanged': False, 'imagesPulled': False}))


def controller():
    need(F.is_mount() and os.geteuid() == 0, 'existing_root_controller_tty')
    measured = json.loads((B / 'measurement-result.json').read_text())
    need(measured['status'] == 'completed' and measured['allLayersFullyAuthenticated'], 'completed_layer_measurement')
    blobs, chains = {}, {}
    for image in measured['images']:
        parent = ''
        for layer in image['layers']:
            blobs[layer['digest']] = layer['compressedBytes']
            key = layer['diffID'] if not parent else 'sha256:' + hashlib.sha256((parent + ' ' + layer['diffID']).encode()).hexdigest()
            need(key not in chains or chains[key] == parent, 'unique_chain_parent')
            chains[key] = parent
            parent = key
        name = image['reference'].split('/')[2].split(':')[0]
        metadata = json.loads((B.parent / (name + '-metadata.json')).read_text())
        blobs[metadata['rootDigest']] = None
        blobs[image['amd64ManifestDigest']] = next(m['size'] for m in metadata['root']['manifests'] if m['digest'] == image['amd64ManifestDigest'])
        blobs[image['configurationDigest']] = metadata['manifest']['config']['size']
    need(len(blobs) <= 256 and len(chains) <= 256, 'bounded_exact_public_candidates')
    library = {'__name__': 'cache_privilege_input'}
    input_source = Path('/mnt/c/Users/james/.codex/worktrees/cluster-maintenance-ansible/kubernetes migration/k8s-rewrite/ansible-playbook/roles/legacy_plex_preservation/files/controller.py')
    exec(compile(input_source.read_bytes(), '<non-echoing-input>', 'exec'), library)
    record = {'UTC': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'nodes': {},
              'sourceSHA256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'measuredResultSHA256': hashlib.sha256((B / 'measurement-result.json').read_bytes()).hexdigest(),
              'clusterMutated': False, 'credentialsStored': False}
    target = B / 'node-cache-inventory.json'
    need(not target.exists(), 'preserve_previous_inventory')
    password = library['privilege_input']()
    try:
        for address, hostname in [('192.168.0.4', 'masternode'), ('192.168.0.5', 'workernode2'), ('192.168.0.6', 'workernode1')]:
            profile = base64.b64encode(json.dumps({'hostname': hostname, 'blobs': blobs, 'chains': chains}).encode()).decode()
            args = ['cache', '--remote', '--profile-base64', profile]
            code = 'import sys;sys.argv=' + repr(args) + '\n' + Path(__file__).read_text()
            need(len(code.encode()) <= 96 * 1024, 'bounded_public_metadata_argument')
            ssh = ['ssh', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes',
                   '-o', 'UserKnownHostsFile=/home/brajam/.ssh/known_hosts', '-o', 'ConnectTimeout=10',
                   '-i', '/home/brajam/.ssh/id_ed25519', '-p', '2002', 'james@' + address,
                   shlex.join(['sudo', '-S', '-p', '', '--', 'python3', '-B', '-c', code])]
            child = subprocess.run(ssh, input=password + b'\n', capture_output=True, timeout=300)
            need(len(child.stdout) <= 4 * 1024**2, 'bounded_node_result')
            if child.returncode:
                record['nodes'][address] = {'exitCode': child.returncode,
                    'stderrSHA256': hashlib.sha256(child.stderr).hexdigest(),
                    'safeErrorCategory': child.stderr.decode(errors='replace').splitlines()[-1][:200] if child.stderr else 'unknown'}
                native = [line for line in child.stderr.decode(errors='replace').splitlines()
                          if line.startswith('native_metadata_failure:')]
                if native:
                    record['nodes'][address]['publicNativeFailure'] = json.loads(native[-1].split(':', 1)[1])
                raise ValueError('read_only_node_inventory_failed')
            record['nodes'][address] = json.loads(child.stdout)
            print(json.dumps({'node': hostname, 'cachedCandidateBlobs': len(record['nodes'][address]['cachedCandidateBlobs']),
                              'candidateSnapshots': len(record['nodes'][address]['candidateSnapshots'])}), flush=True)
        record['status'] = 'completed'
    finally:
        password = None
        with target.open('x') as out:
            json.dump(record, out, indent=2)
        os.chown(target, 1000, 1000)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--remote', action='store_true')
    parser.add_argument('--profile-base64')
    args = parser.parse_args()
    try:
        remote(json.loads(base64.b64decode(args.profile_base64))) if args.remote else controller()
    except Exception as error:
        print('longhorn_cache_inspection_refused:' + (str(error) if isinstance(error, ValueError) else type(error).__name__), file=sys.stderr)
        raise SystemExit(1)
