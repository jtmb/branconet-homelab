#!/usr/bin/env python3
"""Cold MeTube state archive and full-claim legacy reobservation; never scale writers."""
import argparse
import datetime
import hashlib
import json
import os
import pathlib
import re
import shlex
import stat
import subprocess
import sys
import tarfile
import uuid

SSH = ['/usr/bin/ssh', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes', '-o', 'IdentitiesOnly=yes', '-o', 'ForwardAgent=no', '-o', 'ConnectTimeout=15', '-i', '/home/brajam/.ssh/id_ed25519', '-p', '2002', 'james@192.168.0.4']
AGE = pathlib.Path('/home/brajam/.local/share/branconet-migration/bin/age')
AGE_SHA256 = 'eb7dd1b518f0a307c99cd97782623c5321da049154b04acd2d98d21aa7bc9b2c'
RECIPIENT = pathlib.Path('/home/brajam/.ssh/id_ed25519.pub')
IDENTITY = pathlib.Path('/home/brajam/.ssh/id_ed25519')
OLD = 'ghcr.io/alexta69/metube@sha256:afd3fa2b229e3e6d4c8750618fe148af33a1f70b32af4441ecbd2d08f29d8221'
DEPLOYMENT_UID = 'b6f10b2b-3350-49f5-9b1c-182f80db4af5'
CLAIMS = {'ytdl-data-0': '5411bcf9-4331-43bd-9a8d-7d0fbf0a9324', 'ytdl-data-1': 'dcc218b0-929e-4892-bd72-1a226157af5d', 'ytdl-data-2': '7c3e8710-a79d-408f-b8fb-df3b87bdb0de'}
EXCLUDED = ['data-0/ytptube-config', 'data-1/ytptube-cache', 'data-1/ytptube-deno']
MAX_DATA = 4 * 1024**3
MAX_METADATA = 8 * 1024 * 1024
CHUNK = 1024 * 1024


def need(value):
    if not value:
        raise ValueError('preservation prerequisite refused')


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':')).encode()


def file_hash(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(CHUNK), b''):
            digest.update(block)
    return digest.hexdigest()


def protected(path, private=False):
    need(path.is_absolute() and path.resolve() == path)
    info = path.lstat()
    need(stat.S_ISREG(info.st_mode) and info.st_uid == os.getuid() and not info.st_mode & 0o022)
    if private:
        need(not info.st_mode & 0o077)
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def verify_archive(stream, max_entries=4096, max_data=MAX_DATA, max_metadata=MAX_METADATA):
    """Read every archived byte in bounded chunks without extracting plaintext."""
    need((max_entries, max_data, max_metadata) in [(4096, 1024**3, MAX_METADATA), (4096, MAX_DATA, MAX_METADATA), (8192, MAX_DATA, MAX_METADATA), (131072, 16 * 1024**3, 64 * 1024**2)])
    seen = set(); manifest = None; total = 0
    with tarfile.open(fileobj=stream, mode='r|') as archive:
        for member in archive:
            name = member.name.rstrip('/')
            need(name not in seen and not name.startswith('/') and '..' not in pathlib.PurePosixPath(name).parts)
            seen.add(name); need(len(seen) <= max_entries + 1)
            source = archive.extractfile(member) if member.isfile() else None
            if name == 'manifest.json':
                need(len(seen) == 1 and member.isfile() and member.size <= max_metadata)
                manifest = json.loads(source.read()); need(manifest.get('schema_version') == 1 and not manifest.get('excluded_new_paths'))
                continue
            need(manifest is not None and name in manifest['entries'] and name.split('/')[0] in ['data-0', 'data-1'])
            row = manifest['entries'][name]
            need(member.mode == row['mode'] and member.uid == row['uid'] and member.gid == row['gid'])
            if row['kind'] == 'directory':
                need(member.isdir())
            elif row['kind'] == 'symlink':
                need(member.issym() and member.linkname == row['link'])
            else:
                need(row['kind'] == 'file' and member.isfile() and member.size == row['bytes'])
                total += member.size; need(total <= max_data)
                digest = hashlib.sha256(); count = 0
                for block in iter(lambda: source.read(CHUNK), b''):
                    digest.update(block); count += len(block)
                need(count == member.size and digest.hexdigest() == row['sha256'])
    need(manifest is not None and seen == {'manifest.json'} | set(manifest['entries']) and total == manifest['total_file_bytes'])
    return manifest


def legacy_view(manifest):
    # Root directory mtimes change when the three allowed new subdirectories appear.
    return {name: {k: v for k, v in row.items() if k not in ['fingerprint', 'mtime_ns']} for name, row in manifest['entries'].items()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=['backup', 'reobserve'])
    parser.add_argument('--output-dir', type=pathlib.Path, required=True)
    parser.add_argument('--backup-node', choices=['workernode1', 'workernode2'], default='workernode2')
    parser.add_argument('--baseline-receipt', default='')
    parser.add_argument('--baseline-sha256', default='')
    parser.add_argument('--expected-writer-image', default='')
    parser.add_argument('--snapshot-profile', choices=['original-metube', 'current-ytptube'], default='original-metube')
    args = parser.parse_args(); os.umask(0o077)
    if args.snapshot_profile == 'current-ytptube':
        need(args.phase == 'backup' and args.expected_writer_image in ['docker.io/library/ytptube-security-20261023@sha256:7c637f7e9cadf6f7def2243b517ff6101354287e17f9aebed8b0aa386fd1b754', 'ghcr.io/arabcoders/ytptube:v2.7.5@sha256:3ba09ac58f0b541aa7182feb9198b44d3c62158a7749ec00d26de1abad7ca8d7'])
    # No sudo or application credential is required or forwarded to subprocesses.
    os.environ.pop('BRANCONET_MIGRATION_SUDO_PASSWORD', None)
    pins = [(p, protected(p, p == IDENTITY)) for p in [AGE, RECIPIENT, IDENTITY]]
    need(file_hash(AGE) == AGE_SHA256 and os.access(AGE, os.X_OK))
    output = args.output_dir; repo = pathlib.Path(__file__).resolve().parents[5]
    need(output.is_absolute() and str(output).startswith('/home/brajam/') and output.resolve() == output and output != repo and repo not in output.parents)
    output.mkdir(mode=0o700, parents=True, exist_ok=True)
    info = output.lstat(); need(info.st_uid == os.getuid() and not info.st_mode & 0o077)
    run_id = uuid.uuid4().hex; run = output / ('metube-' + args.phase + '-' + run_id); run.mkdir(mode=0o700)
    receipt_path = run / 'receipt.json'; children = []; reader = None
    receipt = {'schema_version': 1, 'phase': args.phase, 'status': 'started', 'started_at': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'restore_verified': False, 'nas_mounted_or_walked': False, 'legacy_reobserved': False, 'writer_scaled_by_helper': False, 'temporary_pod_deleted': False}

    receipt['snapshot_profile'] = args.snapshot_profile

    def save():
        path = run / ('receipt-' + uuid.uuid4().hex + '.tmp')
        with path.open('x') as stream:
            json.dump(receipt, stream, sort_keys=True, indent=2); stream.flush(); os.fsync(stream.fileno())
        os.replace(path, receipt_path)

    def call(argv, body=None, timeout=90, stream=False):
        child = subprocess.Popen(SSH + [shlex.join(argv)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        children.append(child)
        if stream:
            if body:
                child.stdin.write(body)
            child.stdin.close(); return child
        data, _ = child.communicate(body, timeout=timeout)
        need(child.returncode == 0 and len(data) <= MAX_METADATA)
        return data

    def kube(*argv, body=None, timeout=90):
        return call(['kubectl', '-n', 'plex', *argv], body, timeout)

    def obj(*argv):
        return json.loads(kube(*argv, '-o', 'json'))

    def claims():
        rows = []
        for name, uid in CLAIMS.items():
            pvc = obj('get', 'pvc', name); need(pvc['metadata']['uid'] == uid and pvc['status']['phase'] == 'Bound' and not pvc['metadata'].get('deletionTimestamp'))
            rows.append({'namespace': 'plex', 'name': name, 'uid': uid})
        return rows

    def source_guard(own_pod=None):
        current_claims = claims(); dep = obj('get', 'deployment', 'ytdl')
        need(dep['metadata']['uid'] == DEPLOYMENT_UID and not dep['metadata'].get('deletionTimestamp') and dep['status'].get('observedGeneration', 0) >= dep['metadata']['generation'])
        active = []
        for pod in obj('get', 'pods')['items']:
            if own_pod and pod['metadata']['uid'] == own_pod:
                continue
            mounts = [v['persistentVolumeClaim']['claimName'] for v in pod['spec'].get('volumes', []) if 'persistentVolumeClaim' in v]
            if not set(mounts) & {'ytdl-data-0', 'ytdl-data-1'}:
                continue
            running = any('running' in c.get('state', {}) for c in pod['status'].get('containerStatuses', []) + pod['status'].get('initContainerStatuses', []))
            if pod['status'].get('phase') not in ['Failed', 'Succeeded'] or running:
                active.append(pod)
        if args.phase == 'backup':
            need(dep['spec'].get('replicas', 1) == 0 and all(dep['status'].get(k, 0) == 0 for k in ['replicas', 'readyReplicas', 'availableReplicas']) and not active)
            if args.snapshot_profile == 'current-ytptube':
                containers = dep['spec']['template']['spec']['containers']
                need(len(containers) == 1 and containers[0]['image'] == args.expected_writer_image)
            node = args.backup_node
            writer_identity = None
        else:
            need(re.fullmatch(r'[^@\s]+@sha256:[0-9a-f]{64}', args.expected_writer_image) and args.expected_writer_image != OLD)
            need(dep['spec'].get('replicas', 1) == 1 and len(active) == 1)
            pod = active[0]; need(not pod['metadata'].get('deletionTimestamp') and pod['status']['phase'] == 'Running')
            owner = next(x for x in pod['metadata'].get('ownerReferences', []) if x.get('controller'))
            need(owner['kind'] == 'ReplicaSet'); rs = obj('get', 'replicaset', owner['name']); need(rs['metadata']['uid'] == owner['uid'])
            need(any(x.get('controller') and x['kind'] == 'Deployment' and x['uid'] == DEPLOYMENT_UID for x in rs['metadata'].get('ownerReferences', [])))
            container = next(c for c in pod['spec']['containers'] if c['name'] == 'ytdl'); status = next(c for c in pod['status']['containerStatuses'] if c['name'] == 'ytdl')
            # CRI omits the tag from an official tag@digest reference. Require
            # the exact requested spec and immutable runtime digest together.
            need(container['image'] == args.expected_writer_image and status.get('imageID', '').endswith('@' + args.expected_writer_image.split('@', 1)[1]) and status['ready'])
            node = pod['spec']['nodeName']
            writer_identity = {'pod': pod['metadata']['name'], 'uid': pod['metadata']['uid'], 'image': args.expected_writer_image, 'imageID': status['imageID']}
        node_object = obj('get', 'node', node)
        need(not node_object['spec'].get('unschedulable', False))
        need(any(c['type'] == 'Ready' and c['status'] == 'True' for c in node_object['status']['conditions']))
        need(not any(c['type'] in ['DiskPressure', 'MemoryPressure', 'PIDPressure', 'NetworkUnavailable'] and c['status'] == 'True' for c in node_object['status']['conditions']))
        return {'deployment_uid': DEPLOYMENT_UID, 'claims': current_claims, 'reader_node': node, 'writer_identity': writer_identity}

    def check_reader():
        current = obj('get', 'pod', reader['name'])
        need(current['metadata']['uid'] == reader['uid'] and not current['metadata'].get('deletionTimestamp'))
        spec = current['spec']; container = spec['containers'][0]
        need(len(spec['containers']) == 1 and not spec.get('initContainers') and spec.get('automountServiceAccountToken') is False and container['image'] == OLD)
        need({v['persistentVolumeClaim']['claimName'] for v in spec['volumes']} == {'ytdl-data-0', 'ytdl-data-1'} and len(spec['volumes']) == 2)
        need(all(v['persistentVolumeClaim'].get('readOnly') is True for v in spec['volumes']))
        need({v['mountPath'] for v in container['volumeMounts']} == {'/state', '/tmp_dir'} and all(v.get('readOnly') is True and not v.get('subPath') for v in container['volumeMounts']))
        need(current['status']['phase'] == 'Running' and current['status']['containerStatuses'][0].get('imageID') == OLD and current['status']['containerStatuses'][0]['ready'])
        return current

    def execute(mode, body=None, streaming=False):
        check_reader()
        return call(['kubectl', '-n', 'plex', 'exec', '-i', reader['name'], '-c', 'reader', '--', 'python3', '-B', '-c', program, mode], body, 600, streaming)

    def decrypt(cipher):
        child = subprocess.Popen([str(AGE), '-d', '-i', str(IDENTITY), str(cipher)], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        children.append(child); manifest = verify_archive(child.stdout)
        trailing = 0
        for block in iter(lambda: child.stdout.read(65536), b''):
            trailing += len(block); need(trailing <= 1024 * 1024 and not any(block))
        need(child.wait(timeout=30) == 0)
        return manifest

    save()
    try:
        stage = 'preflight'; receipt['operation'] = stage; save()
        before = source_guard(); receipt.update(before)
        program = pathlib.Path(__file__).with_name('pod_reader.py').read_text()
        baseline = None; original_manifest = None
        if args.phase == 'reobserve':
            path = pathlib.Path(args.baseline_receipt); protected(path, True); need(path.stat().st_size <= 65536 and file_hash(path) == args.baseline_sha256)
            baseline = json.loads(path.read_text()); need(baseline['status'] == 'completed' and baseline['phase'] == 'backup' and baseline['cold_archive_verified'] is True and baseline['claims'] == before['claims'])
            cipher = pathlib.Path(baseline['archive_path']); protected(cipher, True); need(0 < cipher.stat().st_size <= MAX_DATA + 32 * 1024 * 1024 and file_hash(cipher) == baseline['archive_sha256'])
            original_manifest = decrypt(cipher); need(hashlib.sha256(canonical(original_manifest)).hexdigest() == baseline['manifest_sha256'])
        name = 'metube-state-' + args.phase + '-' + run_id[:12]
        pod = {'apiVersion': 'v1', 'kind': 'Pod', 'metadata': {'name': name, 'namespace': 'plex', 'labels': {'migration-task': 'metube-state-preservation-20261023', 'preservation-run': run_id}}, 'spec': {'nodeName': before['reader_node'], 'restartPolicy': 'Never', 'activeDeadlineSeconds': 1800, 'automountServiceAccountToken': False, 'securityContext': {'runAsUser': 1000, 'runAsGroup': 1000, 'runAsNonRoot': True, 'seccompProfile': {'type': 'RuntimeDefault'}}, 'containers': [{'name': 'reader', 'image': OLD, 'imagePullPolicy': 'IfNotPresent', 'command': ['python3', '-B', '-c', 'import time;time.sleep(1800)'], 'resources': {'requests': {'cpu': '10m', 'memory': '32Mi'}, 'limits': {'cpu': '500m', 'memory': '256Mi'}}, 'securityContext': {'allowPrivilegeEscalation': False, 'readOnlyRootFilesystem': True, 'capabilities': {'drop': ['ALL']}}, 'volumeMounts': [{'name': 'state', 'mountPath': '/state', 'readOnly': True}, {'name': 'temporary', 'mountPath': '/tmp_dir', 'readOnly': True}]}], 'volumes': [{'name': 'state', 'persistentVolumeClaim': {'claimName': 'ytdl-data-0', 'readOnly': True}}, {'name': 'temporary', 'persistentVolumeClaim': {'claimName': 'ytdl-data-1', 'readOnly': True}}]}}
        receipt['operation'] = 'create_owned_read_only_reader'; save()
        created = json.loads(kube('create', '-f', '-', '-o', 'json', body=canonical(pod))); reader = {'name': name, 'uid': created['metadata']['uid']}; receipt['temporary_pod'] = reader; save()
        kube('wait', 'pod/' + name, '--for=condition=Ready', '--timeout=180s', timeout=200)
        check_reader(); source_guard(reader['uid'])
        receipt['operation'] = 'full_file_fingerprints'; save()
        manifest = json.loads(execute('inventory' if args.phase == 'backup' else 'reobserve'))
        need(manifest['schema_version'] == 1 and manifest['total_file_bytes'] <= MAX_DATA and len(manifest['entries']) <= 4096)
        if args.phase == 'backup':
            if args.snapshot_profile == 'original-metube':
                need(not any(name == base or name.startswith(base + '/') for name in manifest['entries'] for base in EXCLUDED))
            cipher = run / 'metube-complete-state.tar.age'
            receipt['operation'] = 'stream_complete_archive'; save()
            producer = execute('archive', canonical(manifest), True)
            with cipher.open('xb') as target:
                encryptor = subprocess.Popen([str(AGE), '-R', str(RECIPIENT)], stdin=producer.stdout, stdout=target, stderr=subprocess.DEVNULL)
                children.append(encryptor); producer.stdout.close()
                need(encryptor.wait(timeout=600) == 0 and producer.wait(timeout=30) == 0)
                target.flush(); os.fsync(target.fileno())
            receipt['operation'] = 'authenticate_complete_archive'; save()
            recovered = decrypt(cipher); need(recovered == manifest)
            metadata = {'claims': before['claims'], 'algorithm': 'sha256', 'legacy_state_files': {name: row['sha256'] for name, row in manifest['entries'].items() if row['kind'] == 'file'}, 'excluded_new_paths': [] if args.snapshot_profile == 'current-ytptube' else EXCLUDED}
            metadata_path = run / ('current-state-metadata.json' if args.snapshot_profile == 'current-ytptube' else 'cold-legacy-metadata.json')
            with metadata_path.open('x') as stream:json.dump(metadata, stream, sort_keys=True, indent=2); stream.flush(); os.fsync(stream.fileno())
            receipt.update(cold_archive_verified=True, archive_path=str(cipher), archive_sha256=file_hash(cipher), archive_bytes=cipher.stat().st_size, manifest_sha256=hashlib.sha256(canonical(manifest)).hexdigest(), preservation_baseline=str(metadata_path), preservation_baseline_sha256=file_hash(metadata_path), file_count=len(metadata['legacy_state_files']), file_bytes=manifest['total_file_bytes'], excluded_new_paths=[] if args.snapshot_profile == 'current-ytptube' else EXCLUDED)
        else:
            need(manifest['excluded_new_paths'] == sorted(EXCLUDED))
            observed = {'claims': before['claims'], 'algorithm': 'sha256', 'legacy_state_files': {name: row['sha256'] for name, row in manifest['entries'].items() if row['kind'] == 'file'}, 'excluded_new_paths': [] if args.snapshot_profile == 'current-ytptube' else EXCLUDED}
            observed_path = run / 'legacy-observed-metadata.json'
            with observed_path.open('x') as stream:json.dump(observed, stream, sort_keys=True, indent=2); stream.flush(); os.fsync(stream.fileno())
            expected_view = legacy_view(original_manifest); actual_view = legacy_view(manifest)
            different = [name for name in sorted(set(expected_view) | set(actual_view)) if expected_view.get(name) != actual_view.get(name)]
            receipt.update(observed_metadata=str(observed_path), observed_metadata_sha256=file_hash(observed_path), legacy_mismatch_count=len(different))
            if different:
                with (run / 'legacy-mismatches.json').open('x') as stream:json.dump({'paths': different}, stream, indent=2)
                save()
            need(not different)
            receipt.update(legacy_reobserved=True, baseline_receipt=str(path), baseline_receipt_sha256=args.baseline_sha256, expected_writer_image=args.expected_writer_image, manifest_sha256=hashlib.sha256(canonical(manifest)).hexdigest(), file_count=sum(row['kind'] == 'file' for row in manifest['entries'].values()), file_bytes=manifest['total_file_bytes'], excluded_new_paths=[] if args.snapshot_profile == 'current-ytptube' else EXCLUDED)
        need(source_guard(reader['uid']) == before); check_reader()
        for path, identity in pins:need(protected(path, path == IDENTITY) == identity)
        receipt['operation'] = 'delete_only_verified_reader'; save()
        options = {'apiVersion': 'v1', 'kind': 'DeleteOptions', 'preconditions': {'uid': reader['uid']}, 'propagationPolicy': 'Foreground'}
        kube('delete', '--raw', '/api/v1/namespaces/plex/pods/' + reader['name'], '-f', '-', body=canonical(options))
        kube('wait', 'pod/' + reader['name'], '--for=delete', '--timeout=120s', timeout=140)
        receipt.update(status='completed', operation='completed', temporary_pod_deleted=True, completed_at=datetime.datetime.now(datetime.timezone.utc).isoformat()); save()
        print(json.dumps({'status': 'completed', 'phase': args.phase, 'receipt': str(receipt_path), 'file_count': receipt['file_count'], 'file_bytes': receipt['file_bytes']})); return 0
    except Exception as error:
        receipt.update(status='failed', error_type=type(error).__name__, completed_at=datetime.datetime.now(datetime.timezone.utc).isoformat()); save()
        print(json.dumps({'status': 'failed', 'receipt': str(receipt_path), 'operation': receipt.get('operation'), 'error_type': type(error).__name__})); return 1
    finally:
        for child in reversed(children):
            if child.poll() is None:
                child.terminate()
                try:child.wait(timeout=10)
                except subprocess.TimeoutExpired:child.kill(); child.wait(timeout=10)


if __name__ == '__main__':
    try:raise SystemExit(main())
    except Exception:raise SystemExit('MeTube preservation refused invalid inputs; no file contents, request data or raw diagnostics are emitted')
