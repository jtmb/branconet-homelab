#!/usr/bin/env python3
"""Compare complete static-site PVC content and metadata across the nginx patch."""
import argparse
import datetime
import hashlib
import hmac
import json
import os
from pathlib import Path
import shlex
import subprocess
import tarfile
import time
import uuid

BASE = Path('/home/brajam/.local/share/branconet-migration')
SSH = ['ssh', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes', '-o', 'ConnectTimeout=10',
       '-i', '/home/brajam/.ssh/id_ed25519', '-p', '2002', 'james@192.168.0.4']
OLD = 'nginx:latest@sha256:dec7a90bd0973b076832dc56933fe876bc014929e14b4ec49923951405370112'
NEW = 'docker.io/library/nginx-security-20261023@sha256:77219c72642afd0447f32dcf65487ea4c7b540603ceb938b9317fde2e79287f3'


def need(ok, reason):
    if not ok:
        raise ValueError(reason)


def call(args, timeout=35):
    r = subprocess.run(SSH + [shlex.join(args)], capture_output=True, timeout=timeout)
    need(r.returncode == 0 and len(r.stdout) <= 4 * 1024 ** 2, 'bounded_cluster_read')
    return r.stdout


def get(kind, name, namespace='web-apps'):
    return json.loads(call(['kubectl', '--request-timeout=30s', '-n', namespace, 'get', kind, name, '-o', 'json']))


def fence(binding, image):
    app = binding['app']
    d = get('deployment', app)
    h = get('helmrelease', app, 'flux-system')
    pvc = get('pvc', binding['claim'])
    need(d['metadata']['uid'] == binding['deploymentUID'] and h['metadata']['uid'] == binding['releaseUID']
         and pvc['metadata']['uid'] == binding['claimUID'] and pvc['status']['phase'] == 'Bound', 'original_workload_and_claim')
    need(d['status'].get('observedGeneration') == d['metadata']['generation'] and d['spec']['replicas'] == 1
         and all(d['status'].get(k) == 1 for k in ['replicas', 'readyReplicas', 'availableReplicas', 'updatedReplicas'])
         and h['status'].get('observedGeneration') == h['metadata']['generation']
         and any(c['type'] == 'Ready' and c['status'] == 'True' for c in h['status'].get('conditions', [])), 'ready_flux_writer')
    pv = get('pv', pvc['spec']['volumeName'])
    need(pv['spec']['claimRef']['uid'] == binding['claimUID'] and pv['spec']['csi']['driver'] == 'driver.longhorn.io', 'original_longhorn_binding')
    pods = json.loads(call(['kubectl', '-n', 'web-apps', 'get', 'pods', '-l', 'app=' + app, '-o', 'json']))['items']
    need(len(pods) == 1, 'one_owned_site_pod')
    pod = pods[0]
    c = pod['spec']['containers'][0]
    cs = pod['status']['containerStatuses'][0]
    need(not pod['metadata'].get('deletionTimestamp') and cs['ready'] and c['image'] == image
         and c.get('envFrom') == [{'secretRef': {'name': app + '-runtime'}}]
         and any(v.get('persistentVolumeClaim', {}).get('claimName') == binding['claim'] for v in pod['spec']['volumes'])
         and any(v['mountPath'] == '/usr/share/nginx/html' and not v.get('subPath') for v in c['volumeMounts']), 'same_site_launch_mount')
    if image == NEW:
        need(cs['imageID'].rsplit('@', 1)[-1] == NEW.rsplit('@', 1)[-1], 'exact_patched_runtime')
    metadata = call(['kubectl', '-n', 'web-apps', 'get', 'secret', app + '-runtime', '-o', 'jsonpath={.metadata.uid}{" "}{.metadata.resourceVersion}']).decode().split()
    need(len(metadata) == 2, 'metadata_only_native_secret')
    return {'deploymentUID': d['metadata']['uid'], 'releaseUID': h['metadata']['uid'], 'pvcUID': pvc['metadata']['uid'],
            'pvUID': pv['metadata']['uid'], 'pod': pod['metadata']['name'], 'podUID': pod['metadata']['uid'],
            'image': image, 'imageID': cs['imageID'], 'secretUID': metadata[0], 'secretRV': metadata[1]}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output-dir', required=True, type=Path)
    p.add_argument('--baseline', type=Path)
    a = p.parse_args()
    os.umask(0o077)
    need(os.name == 'posix' and a.output_dir.is_absolute() and a.output_dir.resolve() == a.output_dir and BASE in a.output_dir.parents, 'private_native_output')
    a.output_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    need(not a.output_dir.stat().st_mode & 0o077, 'private_output')
    report = {'passed': False, 'comparisonVersion': 3, 'sites': {}, 'startedUTC': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'sourceSHA256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), 'plaintextArchiveWrittenToDisk': False}
    try:
        keyfile = a.output_dir / 'observation.key'
        if a.baseline:
            need(a.baseline.parent == a.output_dir, 'same_baseline_scope')
            old = json.loads(a.baseline.read_bytes())
            need(old['passed'] and old.get('comparisonVersion') == 3, 'accepted_per_file_baseline')
            key = keyfile.read_bytes()
        else:
            key = os.urandom(32)
            if keyfile.exists():
                key = keyfile.read_bytes()
            else:
                with keyfile.open('xb') as f:
                    f.write(key)
        need(len(key) == 32 and not keyfile.stat().st_mode & 0o077, 'private_observation_key')
        bindings = json.loads((BASE / 'web-patch-original-bindings-20261025.json').read_bytes())
        for binding in bindings:
            if binding['namespace'] != 'web-apps':
                continue
            app = binding['app']
            before = fence(binding, NEW if a.baseline else OLD)
            prefix = ['kubectl', '-n', 'web-apps', 'exec', before['pod'], '--']
            call(prefix + ['nginx', '-t'])
            status = call(prefix + ['curl', '--max-time', '20', '-sS', '-o', '/dev/null', '-w', '%{http_code}', 'http://127.0.0.1/']).decode()
            need(status == '200', 'site_http_200')
            args = prefix + ['tar', '--sort=name', '--numeric-owner', '--format=gnu', '-cf', '-', '-C', '/usr/share/nginx/html', '.']
            child = subprocess.Popen(SSH + [shlex.join(args)], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            total = 0
            entries = {}
            start = time.monotonic()
            try:
                with tarfile.open(fileobj=child.stdout, mode='r|') as archive:
                    for member in archive:
                        need(len(entries) < 16384 and member.name not in entries and not member.name.startswith('/')
                             and '..' not in Path(member.name).parts and time.monotonic() - start <= 150, 'bounded_site_members')
                        need(member.isfile() or member.isdir() or member.issym(), 'ordinary_site_file_types')
                        row = {'mode': member.mode, 'uid': member.uid, 'gid': member.gid,
                               'kind': 'file' if member.isfile() else 'directory' if member.isdir() else 'symlink'}
                        if member.isfile():
                            total += member.size
                            need(total <= 2 * 1024 ** 3, 'bounded_complete_site_read')
                            digest = hmac.new(key, digestmod=hashlib.sha256)
                            count = 0
                            stream = archive.extractfile(member)
                            for block in iter(lambda: stream.read(1024 ** 2), b''):
                                digest.update(block)
                                count += len(block)
                                need(time.monotonic() - start <= 150, 'bounded_site_content_deadline')
                            need(count == member.size, 'complete_member_content')
                            row.update(bytes=count, hmac=digest.hexdigest(), mtime=member.mtime)
                        elif member.issym():
                            row['link'] = member.linkname
                        entries[member.name] = row
                for block in iter(lambda: child.stdout.read(65536), b''):
                    need(not any(block), 'only_archive_padding_after_eof')
                need(child.wait(timeout=20) == 0 and entries, 'complete_site_archive_stream')
            finally:
                if child.poll() is None:
                    child.kill()
                    child.wait(timeout=10)
            need(fence(binding, NEW if a.baseline else OLD) == before, 'stable_site_pod')
            tree_hmac = hmac.new(key, json.dumps(entries, sort_keys=True, separators=(',', ':')).encode(), hashlib.sha256).hexdigest()
            item = {'writer': before, 'completeTreeHMAC': tree_hmac, 'fileBytes': total, 'entries': len(entries), 'nginxConfigPassed': True, 'loopbackHTTP': status}
            manifest_path = a.output_dir / ('site-manifest-' + app + '-' + uuid.uuid4().hex + '.json')
            manifest_path.write_text(json.dumps(entries, sort_keys=True, separators=(',', ':')) + '\n')
            item.update(privateManifest=str(manifest_path), manifestSHA256=hashlib.sha256(manifest_path.read_bytes()).hexdigest(), directoryModificationTimesCompared=False)
            report['sites'][app] = item
            if a.baseline:
                prior = old['sites'][app]
                prior_path = Path(prior['privateManifest'])
                need(prior_path.parent == a.output_dir and hashlib.sha256(prior_path.read_bytes()).hexdigest() == prior['manifestSHA256'], 'retained_original_per_file_manifest')
                old_entries = json.loads(prior_path.read_bytes())
                if entries != old_entries:
                    item['changedEntries'] = sum(entries.get(k) != old_entries.get(k) for k in set(entries) | set(old_entries))
                need(item['completeTreeHMAC'] == prior['completeTreeHMAC'] and total == prior['fileBytes'] and len(entries) == prior['entries'], 'complete_original_site_content_and_metadata')
                need(all(before[k] == prior['writer'][k] for k in ['deploymentUID', 'releaseUID', 'pvcUID', 'pvUID', 'secretUID', 'secretRV'])
                     and before['podUID'] != prior['writer']['podUID'], 'same_data_and_native_secret_new_pod')
            report['sites'][app] = item
        need(len(report['sites']) == 4, 'all_four_static_sites')
        report['passed'] = True
    except Exception as error:
        report['failure'] = str(error) if isinstance(error, ValueError) else type(error).__name__
    report['endedUTC'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    out = a.output_dir / ('static-sites-' + uuid.uuid4().hex + '.json')
    out.write_text(json.dumps(report, sort_keys=True, indent=2) + '\n')
    print(json.dumps({'passed': report['passed'], 'receipt': str(out), 'receiptSHA256': hashlib.sha256(out.read_bytes()).hexdigest(), 'failure': report.get('failure')}))
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
