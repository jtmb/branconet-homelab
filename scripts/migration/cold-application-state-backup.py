#!/usr/bin/env python3
"""One allowlisted app's cold encrypted config PVC; never scales a workload."""
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
# Exact identities from metadata-only strict SSH discovery, 2026-10-23.
TARGETS = {
    'qbit-monitor': ('plex', '8ea48d58-186d-4c3d-a90a-d6bda3414246', '09945782-cfa0-4dee-ba5f-19b5788d947c', '29f9332d-c2a6-4f24-a83f-210620046cd2', 'jtmb92/qbit-monitor@sha256:b1ba462564843f9f328b287a34e8a7dc4cd1f218e085862a77f42aaa1703ffec'),
    'homepage': ('homepage', '67484b9d-4971-4840-9385-5478fb0b6b32', '0abccce8-85f7-49df-baea-7825262a258e', 'f1eb8c61-46dc-4743-b5e4-b7ce75110189', 'ghcr.io/gethomepage/homepage:latest@sha256:b129cb0f674bd6d204e215bde2c2fc3f11d6ad0e82f6d20007cf80f74e1acbb1'),
    'qbittorrent': ('plex', '404fad04-5e8b-460b-aa29-dbc7450e4a54', 'd5fd0644-d2b2-4fe0-925f-9ed9a27a83da', '999128b4-0ae2-4396-a8e4-eebace5d26f0', 'lscr.io/linuxserver/qbittorrent@sha256:570aeb63bdedcb5f9dd2500bd8f0a75581ba07c518c05cabbef0cfeb15451b3f'),
    'unpackerr': ('plex', '176fa046-630c-41df-9a53-5c4f5f5d6024', 'c7af079e-7de5-4e8d-a4ca-1c7d763e023b', '4644e693-b613-465d-a7ff-a5a9d3e1ffc1', 'golift/unpackerr:latest@sha256:4ec141eeb0cb2f971d7c92f21cc40b0d2d50d7920eb7a0557443cca52270c0b0'),
    'plex': ('plex', '62dbb208-e8a8-487c-8264-788cd90e3f9d', '66bf6326-157d-4875-b4c5-1a4d03636f5e', 'f1f3f7d0-4706-43ff-871d-e7b6f7bfe7f2', 'lscr.io/linuxserver/plex@sha256:a3a3a850a64fb747c59f85dbc19b157781c3b9c921a83799127894b0ebdf3a68'),
    'jackett': ('plex', '8ff38b3e-d114-4a03-adfd-2078d359530c', 'cc166e8b-d45a-4e77-bdfe-e874240cfb4d', '7d4e8aea-5715-4ee3-8e56-352b7b1e99f0', 'linuxserver/jackett:latest@sha256:cdea5d3209a6ab1fb8eb954ec0b8169b7d54274617f42bf5c74f22a92075755f'),
    'wordpress': ('wordpress', 'c5b60268-c0d4-43f8-8014-4c04e427a122', '65ca0d62-fc47-4063-81a5-4ed59767e907', '90b7695b-3cbf-41d9-b6d1-1f9ee3fd5e2f', 'wordpress:latest@sha256:ee74dc0ebbe7ec43b7f473c0fb4f1dfb6b211d7785f0a95bcdfa10e628c2e67f'),
    'wordpress-redis': ('wordpress', '5af2864b-476a-427f-97a5-acebc3ffa27f', '7ecea459-5e34-499f-8ab3-c073bc050ae0', 'e44745fc-6fb4-4f4e-b8f8-8968441260ee', 'redis:alpine@sha256:2afba59292f25f5d1af200496db41bea2c6c816b059f57ae74703a50a03a27d0'),
    'radarr': ('plex', '3e2719e0-f7f5-4cf5-8ba9-9d94a68302f0', 'bbd87da8-8746-4e3e-8c11-d8ae3a5d1504', '7f07da4f-a34e-4bd0-a4a0-90b94f5a0fec', 'linuxserver/radarr:latest@sha256:ca43905eaf2dd11425efdcfe184892e43806b1ae0a830440c825cecbc2629cfb'),
    'sonarr': ('plex', '30d19648-2af7-48cd-9d72-e9d41f4ecb20', '8568f6b9-f6a8-4ed2-9720-ce84c3a592e0', 'ff5158b3-cecf-46f9-b85e-ad8566cb9068', 'linuxserver/sonarr:latest@sha256:76414c033f290d3c9f1f9dfad71150abe71d92592369a3377a5903d579e6e2b2'),
    'bazarr': ('plex', '2bfbbb63-e949-4a5d-afd3-a923e2d02472', 'fc21743f-4473-4ac2-9cd6-be84edf2a4f4', '5bddaab4-1974-4211-bcae-8392d1006804', 'ghcr.io/hotio/bazarr:latest@sha256:004b1072983d1af766fc11d048121ded9d296fdd64ea304762afa9dfcaf51edb'),
    'tautulli': ('plex', '9db52ebb-23c8-47c6-82c8-ebde3b0a2775', 'e5aa088f-22a3-4f47-b7c4-094be5354bf4', '97eb095e-37ec-4185-80ed-4d8f3c19f486', 'ghcr.io/tautulli/tautulli:latest@sha256:746b2accd580c8551bff3570eab9c6606bbefe9b33567feace2a3c3c9863a1d1'),
    'vaultwarden': ('vaultwarden', '668bb3cd-e382-48b0-910f-7440351bc7d1', '3022a586-c52e-4dcd-850b-149f6b38b603', '0fb0e918-ea61-43f5-af95-662c12f8ffe8', 'vaultwarden/server:latest@sha256:43498a94b22f9563f2a94b53760ab3e710eefc0d0cac2efda4b12b9eb8690664'),
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('application', choices=sorted(TARGETS))
    parser.add_argument('--output-dir', required=True, type=pathlib.Path)
    parser.add_argument('--node', choices=['masternode', 'workernode1', 'workernode2'], default='workernode2')
    parser.add_argument('--reader-uid', type=int, choices=[0, 33, 999, 1000], required=True)
    parser.add_argument('--reader-gid', type=int, choices=[0, 33, 999, 1000], required=True)
    parser.add_argument('--apply', action='store_true', help='Explicit execution; no implicit dry-run mutation')
    args = parser.parse_args()
    need(args.apply and os.name == 'posix' and args.reader_uid == args.reader_gid)
    need(args.reader_uid == 33 if args.application == 'wordpress' else args.reader_uid == 999 if args.application == 'wordpress-redis' else args.reader_uid in [0, 1000])
    need(args.application != 'plex' or args.reader_uid == 1000)
    need(args.application != 'homepage' or (args.reader_uid == 1000 and args.node == 'workernode1'))
    need(args.application != 'qbit-monitor' or args.reader_uid == 1000)
    need(args.node == 'masternode' if args.application in ['qbittorrent', 'qbit-monitor'] else args.node in ['workernode1', 'workernode2'])
    max_entries = 131072 if args.application == 'plex' else 8192 if args.application == 'wordpress' else 4096
    max_data = 16 * 1024**3 if args.application == 'plex' else shared.MAX_DATA
    max_metadata = 64 * 1024**2 if args.application == 'plex' else shared.MAX_METADATA
    os.umask(0o077)
    os.environ.pop('BRANCONET_MIGRATION_SUDO_PASSWORD', None)
    pins = [(p, shared.protected(p, p == shared.IDENTITY)) for p in [shared.AGE, shared.RECIPIENT, shared.IDENTITY]]
    need(file_hash(shared.AGE) == shared.AGE_SHA256 and os.access(shared.AGE, os.X_OK))
    output = args.output_dir
    need(output.is_absolute() and str(output).startswith('/home/brajam/') and output.resolve() == output and output != REPO and REPO not in output.parents)
    output.mkdir(mode=0o700, parents=True, exist_ok=True)
    info = output.lstat(); need(stat.S_ISDIR(info.st_mode) and info.st_uid == os.getuid() and not info.st_mode & 0o077)
    if args.application == 'plex':
        mount = pathlib.Path('/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025')
        need(mount.is_mount() and mount in output.parents and output.stat().st_dev == mount.stat().st_dev)
        fs = os.statvfs(output); need(fs.f_bavail * fs.f_frsize >= max_data + 8 * 1024**3)
    run_id = uuid.uuid4().hex
    run = output / (args.application + '-cold-' + run_id); run.mkdir(mode=0o700)
    namespace, deployment_uid, release_uid, claim_uid, original_image = TARGETS[args.application]
    claim = ('qbit-monitor-state' if args.application == 'qbit-monitor' else
             'qbittorrent-data-0-retry1' if args.application == 'qbittorrent' else
             'wordpress-redis-data' if args.application == 'wordpress-redis' else
             args.application + '-data-1' if args.application in ['unpackerr', 'homepage'] else args.application + '-data-0')
    mount_alias = 'monitor-state' if args.application == 'qbit-monitor' else 'data' if args.application == 'wordpress-redis' else 'data-1' if args.application in ['unpackerr', 'homepage'] else 'data-0'
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
        need(child.returncode == 0 and len(data) <= max_metadata)
        return data

    def kube(*argv, ns=namespace, body=None, timeout=90):
        return call(['kubectl', '-n', ns, *argv], body, timeout=timeout)

    def get(kind, name=None, ns=namespace):
        return json.loads(kube('get', kind, *([name] if name else []), '-o', 'json', ns=ns))

    def guard():
        pvc = get('pvc', claim); dep = get('deployment', args.application); release = get('helmrelease', args.application, 'flux-system')
        need(pvc['metadata']['uid'] == claim_uid and not pvc['metadata'].get('deletionTimestamp') and pvc['status']['phase'] == 'Bound' and pvc['spec'].get('storageClassName') == 'longhorn' and pvc['spec']['volumeName'] == 'pvc-' + claim_uid)
        need(dep['metadata']['uid'] == deployment_uid and not dep['metadata'].get('deletionTimestamp') and dep['status'].get('observedGeneration', 0) >= dep['metadata']['generation'])
        need(dep['spec'].get('replicas', 1) == 0 and all(dep['status'].get(k, 0) == 0 for k in ['replicas', 'readyReplicas', 'availableReplicas', 'updatedReplicas']))
        containers = dep['spec']['template']['spec']['containers']; need(len(containers) == 1 and containers[0]['name'] == args.application and containers[0]['image'] == original_image)
        state_mount = next(m for m in containers[0]['volumeMounts'] if m['name'] == mount_alias)
        need(state_mount['mountPath'] == ('/var/www/html' if args.application == 'wordpress' else '/app/config' if args.application == 'homepage' else '/app/state' if args.application == 'qbit-monitor' else '/data' if args.application in ['vaultwarden', 'wordpress-redis'] else '/config') and not state_mount.get('subPath') and not state_mount.get('subPathExpr'))
        need(any(v['name'] == mount_alias and v.get('persistentVolumeClaim', {}).get('claimName') == claim for v in dep['spec']['template']['spec']['volumes']))
        need(release['metadata']['uid'] == release_uid and not release['metadata'].get('deletionTimestamp') and release['spec'].get('releaseName') == args.application and release['spec'].get('targetNamespace') == namespace and release['spec'].get('values', {}).get('replicaCount') == 0 and not release['spec'].get('suspend', False))
        need(release['status'].get('observedGeneration', 0) >= release['metadata']['generation'] and any(c['type'] == 'Ready' and c['status'] == 'True' for c in release['status'].get('conditions', [])))
        for pod in get('pods')['items']:
            if reader and pod['metadata']['uid'] == reader['uid']: continue
            if not any(v.get('persistentVolumeClaim', {}).get('claimName') == claim for v in pod['spec'].get('volumes', [])): continue
            running = any('running' in c.get('state', {}) for key in ['containerStatuses', 'initContainerStatuses', 'ephemeralContainerStatuses'] for c in pod['status'].get(key, []))
            need(pod['status'].get('phase') in ['Failed', 'Succeeded'] and not running)
        node = get('node', args.node)
        if args.application in ['wordpress-redis', 'wordpress', 'plex']:
            need(node['status'].get('features', {}).get('supplementalGroupsPolicy') is True)
        need(not node['spec'].get('unschedulable', False) and any(c['type'] == 'Ready' and c['status'] == 'True' for c in node['status']['conditions']))
        need(not any(c['type'] in ['DiskPressure', 'MemoryPressure', 'PIDPressure', 'NetworkUnavailable'] and c['status'] == 'True' for c in node['status']['conditions']))
        return {'namespace': namespace, 'deployment_uid': deployment_uid, 'deployment_generation': dep['metadata']['generation'], 'helmrelease_uid': release_uid, 'helmrelease_generation': release['metadata']['generation'], 'original_image': original_image, 'claim': claim, 'claim_uid': claim_uid, 'volume': pvc['spec']['volumeName'], 'reader_node': args.node}

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
        program = "__name__ = 'application_state_reader'\n" + reader_source + "\nROOTS = {'data-0': '/source'}\nEXCLUDED = set()\ntry:\n if sys.argv[1] == 'inventory': print(json.dumps(inventory(False),sort_keys=True))\n elif sys.argv[1] == 'archive':\n  raw=sys.stdin.buffer.read(8*1024*1024+1); need(len(raw)<=8*1024*1024); archive(json.loads(raw))\n else: raise ValueError()\nexcept Exception: raise SystemExit(1)\n"
        receipt.update(shared_reader_sha256=file_hash(SHARED / 'pod_reader.py'), shared_controller_sha256=file_hash(SHARED / 'metube_state_backup.py'), controller_sha256=file_hash(pathlib.Path(__file__)))
        name = 'cold-' + args.application + '-' + run_id[:12]
        pod = {'apiVersion': 'v1', 'kind': 'Pod', 'metadata': {'name': name, 'namespace': namespace, 'labels': {'preservation-run': run_id, 'migration-task': 'cold-application-state'}}, 'spec': {'nodeName': args.node, 'restartPolicy': 'Never', 'activeDeadlineSeconds': 1800, 'automountServiceAccountToken': False, 'securityContext': {'runAsUser': args.reader_uid, 'runAsGroup': args.reader_gid, 'runAsNonRoot': args.reader_uid != 0, 'seccompProfile': {'type': 'RuntimeDefault'}}, 'containers': [{'name': 'reader', 'image': shared.OLD, 'imagePullPolicy': 'IfNotPresent', 'command': ['python3', '-B', '-c', 'import time;time.sleep(1800)'], 'resources': {'requests': {'cpu': '10m', 'memory': '32Mi'}, 'limits': {'cpu': '500m', 'memory': '256Mi'}}, 'securityContext': {'allowPrivilegeEscalation': False, 'readOnlyRootFilesystem': True, 'capabilities': {'drop': ['ALL']}}, 'volumeMounts': [{'name': 'state', 'mountPath': '/source', 'readOnly': True}]}], 'volumes': [{'name': 'state', 'persistentVolumeClaim': {'claimName': claim, 'readOnly': True}}]}}
        if args.application == 'plex':
            program = program.replace('raw=sys.stdin.buffer.read(8*1024*1024+1); need(len(raw)<=8*1024*1024)', 'raw=sys.stdin.buffer.read(64*1024*1024+1); need(len(raw)<=64*1024*1024)')
            program = program.replace("EXCLUDED = set()\n", "EXCLUDED = set()\nMAX_BYTES = " + str(max_data) + "\nMAX_MANIFEST_BYTES = " + str(max_metadata) + "\n")
            pod['spec']['containers'][0]['resources']['limits']['memory'] = '768Mi'
        if args.application in ['wordpress-redis', 'wordpress', 'plex']:
            pod['spec']['securityContext']['supplementalGroupsPolicy'] = 'Strict'
            program = program.replace("EXCLUDED = set()\n", "EXCLUDED = set()\nMAX_ENTRIES = " + str(max_entries) + "\nneed(os.geteuid() == " + str(args.reader_uid) + " and os.getegid() == " + str(args.reader_gid) + " and set(os.getgroups()) <= {" + str(args.reader_gid) + "})\n")
        receipt['operation'] = 'create_owned_readonly_reader'; save()
        created = json.loads(kube('create', '-f', '-', '-o', 'json', body=canonical(pod)))
        reader = {'name': name, 'uid': created['metadata']['uid']}; receipt['temporary_pod'] = reader; save()
        kube('wait', 'pod/' + name, '--for=condition=Ready', '--timeout=180s', timeout=200)
        receipt['operation'] = 'full_config_file_hashes'; save()
        manifest = json.loads(execute('inventory')); need(manifest['schema_version'] == 1 and not manifest['excluded_new_paths'])
        need(manifest['total_file_bytes'] <= max_data and len(manifest['entries']) <= max_entries)
        cipher = run / (args.application + '-complete-config.tar.age')
        receipt['operation'] = 'stream_complete_encrypted_config'; save()
        producer = execute('archive', canonical(manifest), True)
        with cipher.open('xb') as target:
            encryptor = subprocess.Popen([str(shared.AGE), '-R', str(shared.RECIPIENT)], stdin=producer.stdout, stdout=target, stderr=subprocess.DEVNULL)
            children.append(encryptor); producer.stdout.close()
            need(encryptor.wait(timeout=900) == 0 and producer.wait(timeout=30) == 0)
            target.flush(); os.fsync(target.fileno())
        receipt['operation'] = 'authenticate_entire_archive'; save()
        decryptor = subprocess.Popen([str(shared.AGE), '-d', '-i', str(shared.IDENTITY), str(cipher)], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL); children.append(decryptor)
        recovered = shared.verify_archive(decryptor.stdout, max_entries=max_entries, max_data=max_data, max_metadata=max_metadata)
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
