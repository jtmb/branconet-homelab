#!/usr/bin/env python3
"""Pi-hole's two exact cold state claims; complete encrypted archive, no writer changes."""
import argparse
import datetime
import importlib.util
import json
import os
import pathlib
import shlex
import stat
import subprocess
import uuid

REPO = pathlib.Path(__file__).resolve().parents[2]
SHARED = REPO / 'k8s-rewrite/ansible-playbook/roles/metube_state_backup/files'
spec = importlib.util.spec_from_file_location('metube_archive_primitives', SHARED / 'metube_state_backup.py')
shared = importlib.util.module_from_spec(spec)
spec.loader.exec_module(shared)
need, canonical, file_hash = shared.need, shared.canonical, shared.file_hash
# Exact metadata-only discovery on 2026-10-24; these are the actual retained
# retry1 claims, not the abandoned similarly named migration sources.
NAMESPACE = 'pihole'
DEPLOYMENT_UID = 'a00fc6d2-55f3-4182-baf9-5ffc97544f0b'
RELEASE_UID = 'db6aabc6-dd2c-46c3-bbfd-b35ddf453078'
ORIGINAL_IMAGE = 'pihole/pihole:latest@sha256:ee348529cea9601df86ad94d62a39cad26117e1eac9e82d8876aa0ec7fe1ba27'
CLAIMS = {
    'data-0': {'name': 'pihole-data-0-retry1', 'uid': 'b06ca45b-e902-4f0c-a2bf-77e9fca960e8', 'pv_uid': '1d95c7d9-93ba-4d7b-93c4-7b97bb17ec79', 'app_mount': '/etc/dnsmasq.d', 'reader_mount': '/source/dnsmasq'},
    'data-1': {'name': 'pihole-data-1-retry1', 'uid': 'e19b6e39-6a4f-4c6d-b2fe-be27085e1ea9', 'pv_uid': '93d699db-4039-4836-a733-2573997c4406', 'app_mount': '/etc/pihole', 'reader_mount': '/source/pihole'},
}
# Actual 0600 UID1000 files plus a 0640 root:root file require this pair.
# No capability, fsGroup, chmod/chown or supplemental grant is used.
READER_UID, READER_GID = 1000, 0



def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', required=True, type=pathlib.Path)
    parser.add_argument('--node', choices=['workernode1', 'workernode2'], default='workernode2')
    parser.set_defaults(application='pihole', reader_uid=READER_UID, reader_gid=READER_GID)
    parser.add_argument('--apply', action='store_true', help='Explicit execution; no implicit dry-run mutation')
    args = parser.parse_args()
    need(args.apply and os.name == 'posix')
    os.umask(0o077)
    os.environ.pop('BRANCONET_MIGRATION_SUDO_PASSWORD', None)
    pins = [(p, shared.protected(p, p == shared.IDENTITY)) for p in [shared.AGE, shared.RECIPIENT, shared.IDENTITY]]
    need(file_hash(shared.AGE) == shared.AGE_SHA256 and os.access(shared.AGE, os.X_OK))
    output = args.output_dir
    need(output.is_absolute() and str(output).startswith('/home/brajam/') and output.resolve() == output and output != REPO and REPO not in output.parents)
    output.mkdir(mode=0o700, parents=True, exist_ok=True)
    info = output.lstat(); need(stat.S_ISDIR(info.st_mode) and info.st_uid == os.getuid() and not info.st_mode & 0o077)
    run_id = uuid.uuid4().hex
    run = output / (args.application + '-cold-' + run_id); run.mkdir(mode=0o700)
    namespace, deployment_uid, release_uid, original_image = NAMESPACE, DEPLOYMENT_UID, RELEASE_UID, ORIGINAL_IMAGE
    receipt = {'schema_version': 1, 'application': args.application, 'status': 'started', 'started_at': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'reader_uid': args.reader_uid, 'reader_gid': args.reader_gid, 'restore_verified': False, 'writer_scaled_by_helper': False, 'nas_mounted_or_walked': False, 'temporary_pod_deleted': False}
    children = []; reader = None

    def save():
        tmp = run / ('receipt-' + uuid.uuid4().hex + '.tmp')
        with tmp.open('x') as stream:
            json.dump(receipt, stream, sort_keys=True, indent=2); stream.flush(); os.fsync(stream.fileno())
        os.replace(tmp, run / 'receipt.json')

    def call(argv, body=None, streaming=False, timeout=90):
        child = subprocess.Popen(shared.SSH + [shlex.join(argv)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        children.append(child)
        if streaming:
            if body: child.stdin.write(body)
            child.stdin.close(); return child
        data, _ = child.communicate(body, timeout=timeout)
        need(child.returncode == 0 and len(data) <= shared.MAX_METADATA)
        return data

    def kube(*argv, ns=namespace, body=None, timeout=90):
        return call(['kubectl', '-n', ns, *argv], body, timeout=timeout)

    def get(kind, name=None, ns=namespace):
        return json.loads(kube('get', kind, *([name] if name else []), '-o', 'json', ns=ns))

    def guard():
        dep = get('deployment', 'pihole'); release = get('helmrelease', 'pihole', 'flux-system')
        need(dep['metadata']['uid'] == deployment_uid and not dep['metadata'].get('deletionTimestamp') and dep['status'].get('observedGeneration', 0) >= dep['metadata']['generation'])
        need(dep['spec'].get('replicas', 1) == 0 and all(dep['status'].get(k, 0) == 0 for k in ['replicas', 'readyReplicas', 'availableReplicas', 'updatedReplicas']))
        containers = dep['spec']['template']['spec']['containers']
        need(len(containers) == 1 and containers[0]['name'] == 'pihole' and containers[0]['image'] == original_image)
        mounts = containers[0].get('volumeMounts', [])
        volumes = dep['spec']['template']['spec'].get('volumes', [])
        claims = {}
        for alias, target in CLAIMS.items():
            pvc = get('pvc', target['name'])
            need(pvc['metadata']['uid'] == target['uid'] and not pvc['metadata'].get('deletionTimestamp')
                 and pvc['status']['phase'] == 'Bound' and pvc['spec'].get('storageClassName') == 'longhorn'
                 and pvc['spec']['volumeName'] == 'pvc-' + target['uid'])
            pv = get('pv', pvc['spec']['volumeName'])
            binding = pv['spec'].get('claimRef', {})
            need(pv['metadata']['uid'] == target['pv_uid'] and not pv['metadata'].get('deletionTimestamp')
                 and pv['spec'].get('csi', {}).get('driver') == 'driver.longhorn.io'
                 and pv['spec']['csi'].get('volumeHandle') == pvc['spec']['volumeName']
                 and binding.get('uid') == target['uid'] and binding.get('name') == target['name']
                 and binding.get('namespace') == namespace)
            state_mounts = [m for m in mounts if m['name'] == alias]
            need(len(state_mounts) == 1 and state_mounts[0]['mountPath'] == target['app_mount']
                 and not state_mounts[0].get('subPath') and not state_mounts[0].get('subPathExpr'))
            need(any(v['name'] == alias and v.get('persistentVolumeClaim', {}).get('claimName') == target['name'] for v in volumes))
            claims[alias] = {'name': target['name'], 'uid': target['uid'], 'volume': pvc['spec']['volumeName'], 'pv_uid': target['pv_uid'], 'app_mount': target['app_mount']}
        need(release['metadata']['uid'] == release_uid and not release['metadata'].get('deletionTimestamp')
             and release['spec'].get('releaseName') == 'pihole' and release['spec'].get('targetNamespace') == namespace
             and release['spec'].get('values', {}).get('replicaCount') == 0 and not release['spec'].get('suspend', False))
        need(release['status'].get('observedGeneration', 0) >= release['metadata']['generation'] and any(c['type'] == 'Ready' and c['status'] == 'True' for c in release['status'].get('conditions', [])))
        for current in get('pods')['items']:
            if reader and current['metadata']['uid'] == reader['uid']: continue
            if not any(v.get('persistentVolumeClaim', {}).get('claimName') in {t['name'] for t in CLAIMS.values()} for v in current['spec'].get('volumes', [])): continue
            running = any('running' in c.get('state', {}) for key in ['containerStatuses', 'initContainerStatuses', 'ephemeralContainerStatuses'] for c in current['status'].get(key, []))
            need(current['status'].get('phase') in ['Failed', 'Succeeded'] and not running)
        node = get('node', args.node)
        need(node['status'].get('features', {}).get('supplementalGroupsPolicy') is True)
        need(not node['spec'].get('unschedulable', False) and any(c['type'] == 'Ready' and c['status'] == 'True' for c in node['status']['conditions']))
        need(not any(c['type'] in ['DiskPressure', 'MemoryPressure', 'PIDPressure', 'NetworkUnavailable'] and c['status'] == 'True' for c in node['status']['conditions']))
        return {'namespace': namespace, 'deployment_uid': deployment_uid, 'deployment_generation': dep['metadata']['generation'],
                'helmrelease_uid': release_uid, 'helmrelease_generation': release['metadata']['generation'],
                'original_image': original_image, 'claims': claims, 'reader_node': args.node}

    def check_reader():
        current = get('pod', reader['name'])
        need(current['metadata']['uid'] == reader['uid'] and not current['metadata'].get('deletionTimestamp'))
        pod_spec = current['spec']; c = pod_spec['containers'][0]
        need(len(pod_spec['containers']) == 1 and not pod_spec.get('initContainers') and not pod_spec.get('ephemeralContainers') and pod_spec.get('automountServiceAccountToken') is False)
        need(pod_spec['securityContext'] == pod['spec']['securityContext'] and c['securityContext'] == pod['spec']['containers'][0]['securityContext'])
        need(c['image'] == shared.OLD and c['command'] == pod['spec']['containers'][0]['command'] and not c.get('env') and not c.get('envFrom'))
        need(pod_spec['volumes'] == pod['spec']['volumes'] and c['volumeMounts'] == pod['spec']['containers'][0]['volumeMounts'])
        need(current['status']['phase'] == 'Running' and current['status']['containerStatuses'][0].get('imageID') == shared.OLD and current['status']['containerStatuses'][0]['ready'])

    def execute(mode, body=None, streaming=False):
        check_reader(); guard()
        return call(['kubectl', '-n', namespace, 'exec', '-i', reader['name'], '-c', 'reader', '--', 'python3', '-B', '-c', program, mode], body, streaming, 900)

    save()
    try:
        receipt['operation'] = 'cold_identity_preflight'; save()
        before = guard(); receipt.update(before); save()
        # Reuse the new MeTube reader unchanged: suppress its CLI, select one full
        # root, then call its inventory/archive primitives with no exclusions.
        reader_source = (SHARED / 'pod_reader.py').read_text()
        program = "__name__ = 'application_state_reader'\n" + reader_source + "\nneed(os.geteuid() == 1000 and os.getegid() == 0 and set(os.getgroups()) <= {0})\nstatus = dict(line.split(':', 1) for line in pathlib.Path('/proc/self/status').read_text().splitlines() if ':' in line)\nneed(all(int(status[k].strip(), 16) == 0 for k in ['CapEff', 'CapPrm', 'CapAmb']) and status['NoNewPrivs'].strip() == '1')\nROOTS = {'data-0': '/source/dnsmasq', 'data-1': '/source/pihole'}\nEXCLUDED = set()\ntry:\n if sys.argv[1] == 'inventory': print(json.dumps(inventory(False),sort_keys=True))\n elif sys.argv[1] == 'archive':\n  raw=sys.stdin.buffer.read(8*1024*1024+1); need(len(raw)<=8*1024*1024); archive(json.loads(raw))\n else: raise ValueError()\nexcept Exception: raise SystemExit(1)\n"
        receipt.update(shared_reader_sha256=file_hash(SHARED / 'pod_reader.py'), shared_controller_sha256=file_hash(SHARED / 'metube_state_backup.py'), controller_sha256=file_hash(pathlib.Path(__file__)))
        name = 'cold-' + args.application + '-' + run_id[:12]
        pod = {'apiVersion': 'v1', 'kind': 'Pod', 'metadata': {'name': name, 'namespace': namespace, 'labels': {'preservation-run': run_id, 'migration-task': 'cold-application-state'}}, 'spec': {'nodeName': args.node, 'restartPolicy': 'Never', 'activeDeadlineSeconds': 1800, 'automountServiceAccountToken': False, 'securityContext': {'runAsUser': args.reader_uid, 'runAsGroup': args.reader_gid, 'runAsNonRoot': True, 'supplementalGroupsPolicy': 'Strict', 'seccompProfile': {'type': 'RuntimeDefault'}}, 'containers': [{'name': 'reader', 'image': shared.OLD, 'imagePullPolicy': 'IfNotPresent', 'command': ['python3', '-B', '-c', 'import time;time.sleep(1800)'], 'resources': {'requests': {'cpu': '10m', 'memory': '32Mi'}, 'limits': {'cpu': '500m', 'memory': '256Mi'}}, 'securityContext': {'allowPrivilegeEscalation': False, 'readOnlyRootFilesystem': True, 'capabilities': {'drop': ['ALL']}}, 'volumeMounts': [{'name': alias, 'mountPath': target['reader_mount'], 'readOnly': True} for alias, target in CLAIMS.items()]}], 'volumes': [{'name': alias, 'persistentVolumeClaim': {'claimName': target['name'], 'readOnly': True}} for alias, target in CLAIMS.items()]}}
        receipt['operation'] = 'create_owned_readonly_reader'; save()
        created = json.loads(kube('create', '-f', '-', '-o', 'json', body=canonical(pod)))
        reader = {'name': name, 'uid': created['metadata']['uid']}; receipt['temporary_pod'] = reader; save()
        kube('wait', 'pod/' + name, '--for=condition=Ready', '--timeout=180s', timeout=200)
        receipt['operation'] = 'full_config_file_hashes'; save()
        manifest = json.loads(execute('inventory')); need(manifest['schema_version'] == 1 and not manifest['excluded_new_paths'])
        need(manifest['total_file_bytes'] <= shared.MAX_DATA and len(manifest['entries']) <= 4096)
        cipher = run / (args.application + '-complete-state.tar.age')
        receipt['operation'] = 'stream_complete_encrypted_config'; save()
        producer = execute('archive', canonical(manifest), True)
        with cipher.open('xb') as target:
            encryptor = subprocess.Popen([str(shared.AGE), '-R', str(shared.RECIPIENT)], stdin=producer.stdout, stdout=target, stderr=subprocess.DEVNULL)
            children.append(encryptor); producer.stdout.close()
            need(encryptor.wait(timeout=900) == 0 and producer.wait(timeout=30) == 0)
            target.flush(); os.fsync(target.fileno())
        receipt['operation'] = 'authenticate_entire_archive'; save()
        decryptor = subprocess.Popen([str(shared.AGE), '-d', '-i', str(shared.IDENTITY), str(cipher)], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL); children.append(decryptor)
        recovered = shared.verify_archive(decryptor.stdout)
        trailing = 0
        for block in iter(lambda: decryptor.stdout.read(65536), b''):
            trailing += len(block); need(trailing <= 1024 * 1024 and not any(block))
        need(decryptor.wait(timeout=30) == 0 and recovered == manifest)
        need(guard() == before); check_reader()
        for path, identity in pins: need(shared.protected(path, path == shared.IDENTITY) == identity)
        need(receipt['shared_reader_sha256'] == file_hash(SHARED / 'pod_reader.py') and receipt['shared_controller_sha256'] == file_hash(SHARED / 'metube_state_backup.py') and receipt['controller_sha256'] == file_hash(pathlib.Path(__file__)))
        receipt.update(cold_archive_verified=True, archive_path=str(cipher), archive_sha256=file_hash(cipher), archive_bytes=cipher.stat().st_size, manifest_sha256=shared.hashlib.sha256(canonical(manifest)).hexdigest(), file_bytes=manifest['total_file_bytes'], file_count=sum(r['kind'] == 'file' for r in manifest['entries'].values()))
        receipt['operation'] = 'delete_only_verified_reader'; save()
        options = {'apiVersion': 'v1', 'kind': 'DeleteOptions', 'preconditions': {'uid': reader['uid']}, 'propagationPolicy': 'Foreground'}
        kube('delete', '--raw', '/api/v1/namespaces/' + namespace + '/pods/' + name, '-f', '-', body=canonical(options))
        kube('wait', 'pod/' + name, '--for=delete', '--timeout=120s', timeout=140)
        receipt.update(status='completed', operation='completed', temporary_pod_deleted=True, completed_at=datetime.datetime.now(datetime.timezone.utc).isoformat()); save()
        print(json.dumps({'status': 'completed', 'application': args.application, 'receipt': str(run / 'receipt.json')})); return 0
    except Exception as error:
        receipt.update(status='failed', error_type=type(error).__name__, completed_at=datetime.datetime.now(datetime.timezone.utc).isoformat()); save()
        print(json.dumps({'status': 'failed', 'receipt': str(run / 'receipt.json'), 'operation': receipt.get('operation'), 'error_type': type(error).__name__})); return 1
    finally:
        for child in reversed(children):
            if child.poll() is None:
                child.terminate()
                try: child.wait(timeout=10)
                except subprocess.TimeoutExpired: child.kill(); child.wait(timeout=10)


if __name__ == '__main__':
    try: raise SystemExit(main())
    except Exception: raise SystemExit('Cold application preservation refused; raw diagnostics and file contents are suppressed')
