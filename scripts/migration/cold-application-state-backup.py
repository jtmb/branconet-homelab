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
import traceback
import uuid

REPO = pathlib.Path(__file__).resolve().parents[2]
SHARED = REPO / 'k8s-rewrite/ansible-playbook/roles/metube_state_backup/files'
spec = importlib.util.spec_from_file_location('metube_archive_primitives', SHARED / 'metube_state_backup.py')
shared = importlib.util.module_from_spec(spec)
spec.loader.exec_module(shared)
need, canonical, file_hash = shared.need, shared.canonical, shared.file_hash
# Exact identities from metadata-only strict SSH discovery, 2026-10-23.
TARGETS = {
    'seerr': ('plex', 'e758476b-5d1f-4775-89f7-c0f1f310346a', '7a9394f8-4cc1-491c-8733-6164e5626541', '47b19910-cc95-4971-9779-06bf1d17e3dd', 'docker.io/library/seerr-security-20261023@sha256:7bf03e8c4433460c0d93f789da56db457e3484412c448997102885af185db93c'),
    'xteve': ('plex', '52adec00-5c42-4cd2-8fb0-9428828ca368', 'ace99a34-343b-40cd-b1b3-6ef2f324a8b0', 'd40f1490-7254-4599-be82-2fad35abb88b', 'alturismo/xteve:latest@sha256:7885f2759c0da3c5f2c72b2e45ba4b602bdd7d6f04cc6abba201091f11c93a95'),
    'xteve-config': ('plex', '52adec00-5c42-4cd2-8fb0-9428828ca368', 'ace99a34-343b-40cd-b1b3-6ef2f324a8b0', 'b7207fe9-3768-4ad5-9ca0-ee4429137b33', 'alturismo/xteve:latest@sha256:7885f2759c0da3c5f2c72b2e45ba4b602bdd7d6f04cc6abba201091f11c93a95'),
    'mealie': ('mealie', 'f0dddcf0-0d07-4b56-a3ec-0cd59d484b93', '2d878107-ff9f-46f6-9260-2e8f3a94e38c', 'd015a16d-5098-4253-ade1-72d80af87f18', 'ghcr.io/mealie-recipes/mealie:v1.0.0-RC1.1@sha256:6df1e795f17af43f082146e471113315487b5f0882f2ee7553d469034d929af1'),
    'ruckus-db': ('ruckus', 'cf0b7d3c-6d8f-48cb-a55f-0ccd39f610d2', 'ea951a7f-02cf-47ba-afb9-44e915c6b8f0', '2f604004-b45f-4061-bdc4-43f5ca2f7fd8', 'mysql:5.7.41@sha256:bf18020f32cc5d8f5e2add516d52fbf3afc3de431457076340e938596c528171'),
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


STATIC_TARGETS = {
    'aplb': ('web-apps', '80efbad9-bd98-4fda-948e-7708b904e7e3', '3c88e364-76d4-4aa0-a0ff-1ed1059fb172', '24b2b0a8-e215-40b2-abe0-7617a7d8ff82', 'docker.io/library/nginx-security-20261023@sha256:77219c72642afd0447f32dcf65487ea4c7b540603ceb938b9317fde2e79287f3'),
    'lucinda-art-gallery': ('web-apps', '27993cd4-c131-453a-b6d2-d2b00b6e5cd3', '84aefe63-0ed2-49e7-a8d7-7d407f9c54f1', 'bc234dae-ef84-4e43-aae0-a63d8e01d202', 'docker.io/library/nginx-security-20261023@sha256:77219c72642afd0447f32dcf65487ea4c7b540603ceb938b9317fde2e79287f3'),
    'minecraft-website': ('web-apps', '5f9c89b5-7464-4ce6-b978-4fe9b33403d1', 'b06660bd-608a-42af-b7f0-1fdc6553935f', '418b136b-9358-4795-acf3-552d1839a21e', 'docker.io/library/nginx-security-20261023@sha256:77219c72642afd0447f32dcf65487ea4c7b540603ceb938b9317fde2e79287f3'),
    'santos-web': ('web-apps', '580a80a1-527c-4e59-81f6-87fea9d45043', '804ad19a-c3c2-4554-8cf4-f57c8817a0a3', 'da43b501-44d0-4f09-8e58-a1e0d643ec2a', 'docker.io/library/nginx-security-20261023@sha256:77219c72642afd0447f32dcf65487ea4c7b540603ceb938b9317fde2e79287f3'),
}
TARGETS.update(STATIC_TARGETS)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('application', choices=sorted(TARGETS))
    parser.add_argument('--output-dir', required=True, type=pathlib.Path)
    parser.add_argument('--node', choices=['masternode', 'workernode1', 'workernode2'], default='workernode2')
    parser.add_argument('--reader-uid', type=int, choices=[0, 33, 999, 1000], required=True)
    parser.add_argument('--reader-gid', type=int, choices=[0, 33, 999, 1000], required=True)
    parser.add_argument('--apply', action='store_true', help='Explicit execution; no implicit dry-run mutation')
    parser.add_argument('--generation', choices=['original', 'media-security-20261025', 'upstream-media-20261025', 'upstream-seerr-20261025', 'upstream-unpackerr-20261025', 'upstream-static-sites-20261026', 'upstream-homepage-20261026', 'upstream-jackett-20261026', 'upstream-mealie-20261026', 'upstream-tautulli-20261026', 'upstream-vaultwarden-20261026', 'upstream-qbittorrent-20261026'], default='original')
    parser.add_argument('--resume-receipt', type=pathlib.Path, help='Static sites only: reverify an existing ciphertext and its still-running original read-only reader')
    parser.add_argument('--resume-sha256', help='Exact original failed receipt SHA256; original receipt is never overwritten')
    args = parser.parse_args()
    need(args.apply and os.name == 'posix' and args.reader_uid == args.reader_gid)
    need(bool(args.resume_receipt) == bool(args.resume_sha256))
    need(not args.resume_receipt or args.application in STATIC_TARGETS)
    need((args.application in STATIC_TARGETS) == (args.generation == 'upstream-static-sites-20261026'))
    need(args.application not in STATIC_TARGETS or args.reader_uid == 0)
    need(args.application not in STATIC_TARGETS or args.node == 'workernode1')
    need((args.application == 'seerr') == (args.generation == 'upstream-seerr-20261025'))
    need(args.application != 'seerr' or (args.reader_uid == 0 and args.node == 'workernode1'))
    need(args.reader_uid == 33 if args.application == 'wordpress' else args.reader_uid == 999 if args.application in ['wordpress-redis', 'ruckus-db'] else args.reader_uid in [0, 1000])
    need(args.application != 'ruckus-db' or args.node == 'workernode2')
    need(args.application != 'plex' or args.reader_uid == 1000)
    need(args.application != 'homepage' or (args.reader_uid == 1000 and args.node == 'workernode1'))
    need(args.application != 'qbit-monitor' or args.reader_uid == 1000)
    need(args.application != 'mealie' or (args.reader_uid == 1000 and args.node == 'workernode1'))
    need(args.application not in ['xteve', 'xteve-config'] or (args.reader_uid == 0 and args.node == 'workernode2'))
    need(args.node == 'masternode' if args.application in ['qbittorrent', 'qbit-monitor'] else args.node in ['workernode1', 'workernode2'])
    max_entries = 131072 if args.application == 'plex' else 8192 if args.application == 'wordpress' else 4096
    # Each finite static-site claim is exactly1GiB; capture its entire tree,
    # with a tighter complete-data bound than the generic4GiB app profile.
    max_data = 1024**3 if args.application in STATIC_TARGETS else 16 * 1024**3 if args.application == 'plex' else shared.MAX_DATA
    max_metadata = 64 * 1024**2 if args.application == 'plex' else shared.MAX_METADATA
    # The cold archive is a new transfer stage. Measure C and the destination
    # before starting it; existing archives and running work are left intact.
    c_free = subprocess.check_output([
        '/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe',
        '-NoProfile', '-NonInteractive', '-Command', '(Get-PSDrive C).Free'], timeout=30)
    need(int(c_free.decode().strip()) >= 15 * 1024**3)
    os.umask(0o077)
    os.environ.pop('BRANCONET_MIGRATION_SUDO_PASSWORD', None)
    pins = [(p, shared.protected(p, p == shared.IDENTITY)) for p in [shared.AGE, shared.RECIPIENT, shared.IDENTITY]]
    need(file_hash(shared.AGE) == shared.AGE_SHA256 and os.access(shared.AGE, os.X_OK))
    output = args.output_dir
    need(output.is_absolute() and str(output).startswith('/home/brajam/') and output.resolve() == output and output != REPO and REPO not in output.parents)
    output.mkdir(mode=0o700, parents=True, exist_ok=True)
    info = output.lstat(); need(stat.S_ISDIR(info.st_mode) and info.st_uid == os.getuid() and not info.st_mode & 0o077)
    fs = os.statvfs(output)
    need(fs.f_bavail * fs.f_frsize >= max_data + 15 * 1024**3)
    if args.application == 'plex':
        mount = pathlib.Path('/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025')
        need(mount.is_mount() and mount in output.parents and output.stat().st_dev == mount.stat().st_dev)
        fs = os.statvfs(output); need(fs.f_bavail * fs.f_frsize >= max_data + 8 * 1024**3)
    resumed = None
    receipt_name = 'receipt.json'
    if args.resume_receipt:
        path = args.resume_receipt
        shared.protected(path, True)
        need(path.name == 'receipt.json' and path.parent.parent == output and path.stat().st_size <= 65536
             and file_hash(path) == args.resume_sha256)
        resumed = json.loads(path.read_bytes())
        need(resumed['application'] == args.application and resumed['generation'] == args.generation
             and resumed['status'] == 'failed' and resumed['operation'] == 'authenticate_entire_archive'
             and resumed['error_type'] == 'ValueError' and not resumed['temporary_pod_deleted'])
        run = path.parent
        run_id = run.name.removeprefix(args.application + '-cold-')
        need(uuid.UUID(run_id).hex == run_id)
        need(resumed['temporary_pod']['name'] == 'cold-' + args.application + '-' + run_id[:12])
        receipt_name = 'recovery-receipt.json'
        need(not (run / receipt_name).exists())
    else:
        run_id = uuid.uuid4().hex
        run = output / (args.application + '-cold-' + run_id); run.mkdir(mode=0o700)
    namespace, deployment_uid, release_uid, claim_uid, original_image = TARGETS[args.application]
    if args.generation == 'upstream-qbittorrent-20261026':
        need(args.application == 'qbittorrent' and args.reader_uid == 0 and args.node == 'masternode')
        original_image = 'docker.io/library/qbittorrent-current-security-20261023@sha256:9e546e0ac277ef9b241cb383bfa9157e47df3269e62481348a63f4d19b87adf8'
    if args.generation == 'upstream-vaultwarden-20261026':
        need(args.application == 'vaultwarden' and args.reader_uid == 1000 and args.node == 'workernode1')
        original_image = 'docker.io/library/vaultwarden-security-20261023@sha256:c6a9b959228bf484038fe502bc0697e5ca5d2d10a515de47969c2611d36cdb0d'
    if args.generation == 'upstream-tautulli-20261026':
        need(args.application == 'tautulli' and args.reader_uid == 1000 and args.node == 'workernode1')
        original_image = 'docker.io/library/tautulli-security-20261023@sha256:769aa67e07e35bdfe714a486591eb1a34c9ad9bd6cf2da89da130dcdab9de05a'
    if args.generation == 'upstream-mealie-20261026':
        need(args.application == 'mealie' and args.reader_uid == 1000 and args.node == 'workernode1')
        original_image = 'docker.io/library/mealie-security-20261023@sha256:a3fc64d6777e22de915a97d3dbb77e1edc5d5998be683b4a1bed8968a26b2bb9'
    if args.generation == 'media-security-20261025':
        current = {
            'bazarr': 'ghcr.io/hotio/bazarr:latest@sha256:c63aa057947400abded2583f7027d6ac1f8d70a8130401c36d5a244ef5999466',
            'radarr': 'docker.io/linuxserver/radarr:latest@sha256:fc0ae3c50f8128b97e84381903ec8d6845c3a569641cb7117c124376cccb57c1',
            'sonarr': 'docker.io/linuxserver/sonarr:latest@sha256:889dcc58c6aea859033985894b519b2e6b1e55d92527ed123f9f52e42ae7c97b',
        }
        need(args.application in current)
        original_image = current[args.application]
    if args.generation == 'upstream-media-20261025':
        current = {'radarr': 'docker.io/library/radarr-security-20261023@sha256:b79e4e0e3bec790e4f8a48cca83fd5b34e1267f672e27496cf1b95e732fed83c', 'sonarr': 'docker.io/library/sonarr-security-20261023@sha256:7d297bbadfd74dd2c346b48d32530d6fa632bc902739d4f7aaadbd898375f593', 'bazarr': 'docker.io/library/bazarr-security-20261023@sha256:bcf9a782f3381b4182bed0985e0d38df79da0218ead2ca47c577595e9dafe21b'}
        need(args.application in current)
        original_image = current[args.application]
    if args.generation == 'upstream-unpackerr-20261025':
        need(args.application == 'unpackerr')
        original_image = 'docker.io/library/unpackerr-security-20261023@sha256:6342be9c7797b126633a56948b4dab131fde45fde3b8b173a3c84a8f4efc6213'
    if args.generation == 'upstream-homepage-20261026':
        need(args.application == 'homepage')
        original_image = 'docker.io/library/homepage-security-20261023@sha256:7f91e85fa5d394b4be0f60686e40bf93e28e7ca0074c60754f3f02a1caa66bd4'
    if args.generation == 'upstream-jackett-20261026':
        need(args.application == 'jackett' and args.node == 'workernode2' and args.reader_uid == 1000)
        original_image = 'docker.io/library/jackett-security-20261023@sha256:08f115ddcbc3e01bf5379e4c91ea594fae49666678b53ed20af889773b1ca729'
    workload = 'overseerr' if args.application == 'seerr' else 'xteve' if args.application in ['xteve', 'xteve-config'] else args.application
    claim = ('overseerr-data-0' if args.application == 'seerr' else 'xteve-data-1' if args.application == 'xteve-config' else
             'qbit-monitor-state' if args.application == 'qbit-monitor' else
             'qbittorrent-data-0-retry1' if args.application == 'qbittorrent' else
             'wordpress-redis-data' if args.application == 'wordpress-redis' else
             args.application + '-data-1' if args.application in ['unpackerr', 'homepage'] else args.application + '-data-0')
    mount_alias = 'monitor-state' if args.application == 'qbit-monitor' else 'data' if args.application == 'wordpress-redis' else 'data-1' if args.application in ['unpackerr', 'homepage', 'xteve-config'] else 'data-0'
    receipt = {'schema_version': 1, 'application': args.application, 'generation': args.generation, 'status': 'started', 'started_at': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'reader_uid': args.reader_uid, 'reader_gid': args.reader_gid, 'restore_verified': False, 'writer_scaled_by_helper': False, 'nas_mounted_or_walked': False, 'temporary_pod_deleted': False}
    if resumed:
        receipt['resumed_failed_receipt'] = {'path': str(args.resume_receipt), 'sha256': args.resume_sha256}
        need(resumed['shared_reader_sha256'] == file_hash(SHARED / 'pod_reader.py'))
    children = []; reader = resumed['temporary_pod'] if resumed else None

    def save():
        tmp = run / ('receipt-' + uuid.uuid4().hex + '.tmp')
        with tmp.open('x') as stream:
            json.dump(receipt, stream, sort_keys=True, indent=2); stream.flush(); os.fsync(stream.fileno())
        os.replace(tmp, run / receipt_name)

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
        pvc = get('pvc', claim); dep = get('deployment', workload); release = get('helmrelease', workload, 'flux-system')
        need(pvc['metadata']['uid'] == claim_uid and not pvc['metadata'].get('deletionTimestamp') and pvc['status']['phase'] == 'Bound' and pvc['spec'].get('storageClassName') == 'longhorn' and pvc['spec']['volumeName'] == 'pvc-' + claim_uid)
        need(args.application not in STATIC_TARGETS or pvc['status'].get('capacity', {}).get('storage') == '1Gi')
        need(dep['metadata']['uid'] == deployment_uid and not dep['metadata'].get('deletionTimestamp') and dep['status'].get('observedGeneration', 0) >= dep['metadata']['generation'])
        need(dep['spec'].get('replicas', 1) == 0 and all(dep['status'].get(k, 0) == 0 for k in ['replicas', 'readyReplicas', 'availableReplicas', 'updatedReplicas']))
        containers = dep['spec']['template']['spec']['containers']; need(len(containers) == 1 and containers[0]['name'] == workload and containers[0]['image'] == original_image)
        state_mount = next(m for m in containers[0]['volumeMounts'] if m['name'] == mount_alias)
        if args.application == 'seerr':
            mounts = [{**m, 'readOnly': m.get('readOnly', False)} for m in containers[0]['volumeMounts']]
            need(mounts == [{'name': 'data-0', 'mountPath': '/config', 'readOnly': True}, {'name': 'data-0', 'mountPath': '/app/config', 'readOnly': False}])
        need(state_mount['mountPath'] == ('/usr/share/nginx/html' if args.application in STATIC_TARGETS else '/root/.xteve' if args.application == 'xteve' else '/app/data' if args.application == 'mealie' else '/var/lib/mysql' if args.application == 'ruckus-db' else '/var/www/html' if args.application == 'wordpress' else '/app/config' if args.application == 'homepage' else '/app/state' if args.application == 'qbit-monitor' else '/data' if args.application in ['vaultwarden', 'wordpress-redis'] else '/config') and not state_mount.get('subPath') and not state_mount.get('subPathExpr'))
        need(any(v['name'] == mount_alias and v.get('persistentVolumeClaim', {}).get('claimName') == claim for v in dep['spec']['template']['spec']['volumes']))
        need(release['metadata']['uid'] == release_uid and not release['metadata'].get('deletionTimestamp') and release['spec'].get('releaseName') == workload and release['spec'].get('targetNamespace') == namespace and release['spec'].get('values', {}).get('replicaCount') == 0 and not release['spec'].get('suspend', False))
        need(release['status'].get('observedGeneration', 0) >= release['metadata']['generation'] and any(c['type'] == 'Ready' and c['status'] == 'True' for c in release['status'].get('conditions', [])))
        pods = get('pods')['items']
        writer_identity = {}
        watched_claims = {claim}
        if args.application in ['xteve', 'xteve-config']:
            # Both finite local-state scopes share one writer. Preserve the SMB
            # binding by metadata only; never mount or traverse NAS content.
            expected_volumes = [
                {'name': 'data-0', 'persistentVolumeClaim': {'claimName': 'xteve-data-0'}},
                {'name': 'data-1', 'persistentVolumeClaim': {'claimName': 'xteve-data-1'}},
                {'name': 'data-2', 'emptyDir': {'medium': 'Memory'}},
                {'name': 'data-3', 'persistentVolumeClaim': {'claimName': 'xteve-data-3'}},
            ]
            expected_mounts = [{'name': 'data-0', 'mountPath': '/root/.xteve'}, {'name': 'data-1', 'mountPath': '/config'},
                               {'name': 'data-2', 'mountPath': '/tmp/xteve'}, {'name': 'data-3', 'mountPath': '/iptv'}]
            need(sorted(dep['spec']['template']['spec']['volumes'], key=lambda v: v['name']) == expected_volumes)
            need(sorted(containers[0]['volumeMounts'], key=lambda v: v['name']) == expected_mounts)
            for claim_name, cuid, puid, volume, driver in [
                ('xteve-data-0', 'd40f1490-7254-4599-be82-2fad35abb88b', '0ab90957-d5ce-496d-9ddc-658299729a15', 'pvc-d40f1490-7254-4599-be82-2fad35abb88b', 'driver.longhorn.io'),
                ('xteve-data-1', 'b7207fe9-3768-4ad5-9ca0-ee4429137b33', '8be538e5-bcca-490e-b075-7556d1c0aa31', 'pvc-b7207fe9-3768-4ad5-9ca0-ee4429137b33', 'driver.longhorn.io'),
                ('xteve-data-3', '93527524-e3c1-4e2e-a9c4-1a844743d8b1', '548595f5-a4ea-4b8d-a225-1f15d7b3c09e', 'plex-xteve-data-3', 'smb.csi.k8s.io'),
            ]:
                other = get('pvc', claim_name); pv = get('pv', volume)
                need(other['metadata']['uid'] == cuid and not other['metadata'].get('deletionTimestamp') and other['status']['phase'] == 'Bound' and other['spec']['volumeName'] == volume)
                need(pv['metadata']['uid'] == puid and not pv['metadata'].get('deletionTimestamp') and pv['spec']['claimRef']['uid'] == cuid and pv['spec']['csi']['driver'] == driver)
                if driver == 'driver.longhorn.io':
                    need(other['spec'].get('storageClassName') == 'longhorn' and pv['spec']['csi']['volumeHandle'] == volume)
            watched_claims = {'xteve-data-0', 'xteve-data-1'}
            writer_identity = {'workload': workload, 'state_mount_alias': mount_alias, 'source_mount': state_mount['mountPath'],
                               'archive_root_alias': 'data-0', 'preserved_smb_claim_uid': '93527524-e3c1-4e2e-a9c4-1a844743d8b1'}
        if args.application == 'ruckus-db':
            bot = get('deployment', 'ruckus-bot')
            bot_release = get('helmrelease', 'ruckus-bot', 'flux-system')
            need(bot['metadata']['uid'] == 'dfd27794-a610-445e-b279-6e0933cf1153' and not bot['metadata'].get('deletionTimestamp'))
            need(bot['status'].get('observedGeneration', 0) >= bot['metadata']['generation'] and bot['spec'].get('replicas', 1) == 0)
            need(all(bot['status'].get(k, 0) == 0 for k in ['replicas', 'readyReplicas', 'availableReplicas', 'updatedReplicas']))
            need(bot_release['metadata']['uid'] == '790c3088-67d8-47cf-ac00-9d2e1f8c6937' and not bot_release['metadata'].get('deletionTimestamp'))
            need(bot_release['spec'].get('releaseName') == 'ruckus-bot' and bot_release['spec'].get('targetNamespace') == namespace and bot_release['spec'].get('values', {}).get('replicaCount') == 0 and not bot_release['spec'].get('suspend', False))
            need(bot_release['status'].get('observedGeneration', 0) >= bot_release['metadata']['generation'] and any(c['type'] == 'Ready' and c['status'] == 'True' for c in bot_release['status'].get('conditions', [])))
            selector = bot['spec']['selector']
            need(selector.get('matchLabels') and not selector.get('matchExpressions'))
            for candidate in pods:
                if all(candidate['metadata'].get('labels', {}).get(k) == v for k, v in selector['matchLabels'].items()):
                    running = any('running' in c.get('state', {}) for key in ['containerStatuses', 'initContainerStatuses', 'ephemeralContainerStatuses'] for c in candidate['status'].get(key, []))
                    need(candidate['status'].get('phase') in ['Failed', 'Succeeded'] and not running)
            writer_identity = {'client_deployment_uid': bot['metadata']['uid'], 'client_generation': bot['metadata']['generation'], 'client_release_uid': bot_release['metadata']['uid'], 'client_release_generation': bot_release['metadata']['generation']}
        for pod in pods:
            if reader and pod['metadata']['uid'] == reader['uid']: continue
            if not any(v.get('persistentVolumeClaim', {}).get('claimName') in watched_claims for v in pod['spec'].get('volumes', [])): continue
            running = any('running' in c.get('state', {}) for key in ['containerStatuses', 'initContainerStatuses', 'ephemeralContainerStatuses'] for c in pod['status'].get(key, []))
            need(pod['status'].get('phase') in ['Failed', 'Succeeded'] and not running)
        node = get('node', args.node)
        if args.application == 'seerr' or args.application in STATIC_TARGETS:
            need(node['metadata']['uid'] == 'e8d4555f-7cea-445f-b84f-6416964045a9')
        if args.application in ['xteve', 'xteve-config']:
            need(node['metadata']['uid'] == 'eda66e65-f388-4b97-b64f-a709cda81894')
        if args.application == 'mealie':
            need(node['metadata']['uid'] == 'e8d4555f-7cea-445f-b84f-6416964045a9')
            pv = get('pv', pvc['spec']['volumeName'])
            need(pv['metadata']['uid'] == '402d45ec-840b-4a57-9c7e-0cede840539d' and pv['spec']['claimRef']['uid'] == claim_uid)
            need(pv['spec']['csi']['driver'] == 'driver.longhorn.io' and pv['spec']['csi']['volumeHandle'] == 'pvc-' + claim_uid)
        if args.application in ['wordpress-redis', 'wordpress', 'plex', 'ruckus-db', 'mealie', 'xteve', 'xteve-config']:
            need(node['status'].get('features', {}).get('supplementalGroupsPolicy') is True)
        need(not node['spec'].get('unschedulable', False) and any(c['type'] == 'Ready' and c['status'] == 'True' for c in node['status']['conditions']))
        need(not any(c['type'] in ['DiskPressure', 'MemoryPressure', 'PIDPressure', 'NetworkUnavailable'] and c['status'] == 'True' for c in node['status']['conditions']))
        return {'namespace': namespace, 'deployment_uid': deployment_uid, 'deployment_generation': dep['metadata']['generation'], 'helmrelease_uid': release_uid, 'helmrelease_generation': release['metadata']['generation'], 'original_image': original_image, 'claim': claim, 'claim_uid': claim_uid, 'volume': pvc['spec']['volumeName'], 'reader_node': args.node, **writer_identity}

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
        if resumed:
            need(all(resumed[k] == v for k, v in before.items()))
        # Reuse the new MeTube reader unchanged: suppress its CLI, select one full
        # root, then call its inventory/archive primitives with no exclusions.
        reader_source = (SHARED / 'pod_reader.py').read_text()
        program = "__name__ = 'application_state_reader'\n" + reader_source + "\nROOTS = {'data-0': '/source'}\nEXCLUDED = set()\ntry:\n if sys.argv[1] == 'inventory': print(json.dumps(inventory(False),sort_keys=True))\n elif sys.argv[1] == 'archive':\n  raw=sys.stdin.buffer.read(8*1024*1024+1); need(len(raw)<=8*1024*1024); archive(json.loads(raw))\n else: raise ValueError()\nexcept Exception: raise SystemExit(1)\n"
        receipt.update(shared_reader_sha256=file_hash(SHARED / 'pod_reader.py'), shared_controller_sha256=file_hash(SHARED / 'metube_state_backup.py'), controller_sha256=file_hash(pathlib.Path(__file__)))
        name = 'cold-' + args.application + '-' + run_id[:12]
        pod = {'apiVersion': 'v1', 'kind': 'Pod', 'metadata': {'name': name, 'namespace': namespace, 'labels': {'preservation-run': run_id, 'migration-task': 'cold-application-state'}}, 'spec': {'nodeName': args.node, 'restartPolicy': 'Never', 'activeDeadlineSeconds': 1800, 'automountServiceAccountToken': False, 'securityContext': {'runAsUser': args.reader_uid, 'runAsGroup': args.reader_gid, 'runAsNonRoot': args.reader_uid != 0, 'seccompProfile': {'type': 'RuntimeDefault'}}, 'containers': [{'name': 'reader', 'image': shared.OLD, 'imagePullPolicy': 'IfNotPresent', 'command': ['python3', '-B', '-c', 'import time;time.sleep(1800)'], 'resources': {'requests': {'cpu': '10m', 'memory': '32Mi'}, 'limits': {'cpu': '500m', 'memory': '256Mi'}}, 'securityContext': {'allowPrivilegeEscalation': False, 'readOnlyRootFilesystem': True, 'capabilities': {'drop': ['ALL']}}, 'volumeMounts': [{'name': 'state', 'mountPath': '/source', 'readOnly': True}]}], 'volumes': [{'name': 'state', 'persistentVolumeClaim': {'claimName': claim, 'readOnly': True}}]}}
        if args.application == 'seerr' or args.application in STATIC_TARGETS:
            # Read the entire claim, including root-owned lost+found and private
            # app-owned files. This adds read/search only, never write access.
            pod['spec']['containers'][0]['securityContext']['capabilities']['add'] = ['DAC_READ_SEARCH']
        if args.application in STATIC_TARGETS:
            program = program.replace("EXCLUDED = set()\n", "EXCLUDED = set()\nMAX_BYTES = " + str(max_data) + "\n")
        if args.application == 'plex':
            program = program.replace('raw=sys.stdin.buffer.read(8*1024*1024+1); need(len(raw)<=8*1024*1024)', 'raw=sys.stdin.buffer.read(64*1024*1024+1); need(len(raw)<=64*1024*1024)')
            program = program.replace("EXCLUDED = set()\n", "EXCLUDED = set()\nMAX_BYTES = " + str(max_data) + "\nMAX_MANIFEST_BYTES = " + str(max_metadata) + "\n")
            pod['spec']['containers'][0]['resources']['limits']['memory'] = '768Mi'
        if args.application in ['wordpress-redis', 'wordpress', 'plex', 'ruckus-db', 'mealie', 'xteve', 'xteve-config']:
            pod['spec']['securityContext']['supplementalGroupsPolicy'] = 'Strict'
            program = program.replace("EXCLUDED = set()\n", "EXCLUDED = set()\nMAX_ENTRIES = " + str(max_entries) + "\nneed(os.geteuid() == " + str(args.reader_uid) + " and os.getegid() == " + str(args.reader_gid) + " and set(os.getgroups()) <= {" + str(args.reader_gid) + "})\n")
        if args.application in ['mealie', 'xteve', 'xteve-config']:
            root_mode = 0o1750 if args.application == 'mealie' else 0o755
            program = program.replace("EXCLUDED = set()\n", "EXCLUDED = set()\nroot_info = pathlib.Path('/source').lstat()\nneed(stat.S_ISDIR(root_info.st_mode) and root_info.st_uid == 1000 and root_info.st_gid == 65534 and stat.S_IMODE(root_info.st_mode) == " + str(root_mode) + ")\n")
        receipt['operation'] = 'create_owned_readonly_reader'; save()
        if not resumed:
            created = json.loads(kube('create', '-f', '-', '-o', 'json', body=canonical(pod)))
            reader = {'name': name, 'uid': created['metadata']['uid']}
        receipt['temporary_pod'] = reader; save()
        kube('wait', 'pod/' + name, '--for=condition=Ready', '--timeout=180s', timeout=200)
        receipt['operation'] = 'full_config_file_hashes'; save()
        manifest = json.loads(execute('inventory')); need(manifest['schema_version'] == 1 and not manifest['excluded_new_paths'])
        need(manifest['total_file_bytes'] <= max_data and len(manifest['entries']) <= max_entries)
        cipher = run / (args.application + '-complete-config.tar.age')
        if resumed:
            shared.protected(cipher, True)
            need(0 < cipher.stat().st_size <= max_data + 32 * 1024**2)
            receipt['existing_ciphertext_reused'] = True
        else:
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
        print(json.dumps({'status': 'completed', 'application': args.application, 'receipt': str(run / receipt_name)})); return 0
    except Exception as error:
        receipt['error_source_lines'] = [frame.lineno for frame in traceback.extract_tb(error.__traceback__) if frame.filename == __file__]
        receipt.update(status='failed', error_type=type(error).__name__, completed_at=datetime.datetime.now(datetime.timezone.utc).isoformat()); save()
        print(json.dumps({'status': 'failed', 'receipt': str(run / receipt_name), 'operation': receipt.get('operation'), 'error_type': type(error).__name__})); return 1
    finally:
        for child in reversed(children):
            if child.poll() is None:
                child.terminate()
                try: child.wait(timeout=10)
                except subprocess.TimeoutExpired: child.kill(); child.wait(timeout=10)


if __name__ == '__main__':
    try: raise SystemExit(main())
    except Exception: raise SystemExit('Cold application preservation refused; raw diagnostics and file contents are suppressed')
