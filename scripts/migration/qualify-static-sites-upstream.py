#!/usr/bin/env python3
"""Whole served-tree, native config/Secret/storage and real route comparison."""
import argparse
import datetime
import hashlib
import hmac
from html.parser import HTMLParser
import http.client as http_client
import json
import os
import posixpath
from pathlib import Path
import re
import shlex
import socket
import ssl
import subprocess
import tarfile
import time
import urllib.parse

ROOT = Path('/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025')
OLD = 'docker.io/library/nginx-security-20261023@sha256:77219c72642afd0447f32dcf65487ea4c7b540603ceb938b9317fde2e79287f3'
NEW = 'docker.io/library/nginx:1.30.6-alpine3.24-slim@sha256:dede8895648b461178c3bc604f7eed4423efe5220b2c4d839f5eb3d34ac3f8f7'
CHILD = 'sha256:8f06fd647c6687eae0fd7bee8a43df66e61edb9f093bb0a9079d69cb355b879b'
TARGETS = {
    'aplb': ('80efbad9-bd98-4fda-948e-7708b904e7e3', '3c88e364-76d4-4aa0-a0ff-1ed1059fb172', '24b2b0a8-e215-40b2-abe0-7617a7d8ff82', '3874b393-c8b9-4c43-bc15-76d6287a4736', 8082),
    'lucinda-art-gallery': ('27993cd4-c131-453a-b6d2-d2b00b6e5cd3', '84aefe63-0ed2-49e7-a8d7-7d407f9c54f1', 'bc234dae-ef84-4e43-aae0-a63d8e01d202', 'bf143292-c979-4195-a2b9-943dfe1841fe', 8080),
    'minecraft-website': ('5f9c89b5-7464-4ce6-b978-4fe9b33403d1', 'b06660bd-608a-42af-b7f0-1fdc6553935f', '418b136b-9358-4795-acf3-552d1839a21e', '1be12a05-869a-4185-a36f-390e3f3bf126', 8083),
    'santos-web': ('580a80a1-527c-4e59-81f6-87fea9d45043', '804ad19a-c3c2-4554-8cf4-f57c8817a0a3', 'da43b501-44d0-4f09-8e58-a1e0d643ec2a', 'ef1f4490-8ad3-4805-a640-af0dd0eed3a8', 8081),
}
SSH = ['ssh', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes', '-o', 'ConnectTimeout=10',
       '-i', '/home/brajam/.ssh/id_ed25519', '-p', '2002', 'james@192.168.0.4']


def need(ok, reason):
    if not ok:
        raise ValueError(reason)


def call(args):
    p = subprocess.run(SSH + [shlex.join(args)], capture_output=True, timeout=90)
    need(p.returncode == 0 and len(p.stdout) <= 4 * 1024**2, 'bounded_cluster_operation')
    return p.stdout


def get(kind, name, ns='web-apps'):
    return json.loads(call(['kubectl', '--request-timeout=30s', '-n', ns, 'get', kind, name, '-o', 'json']))


class Assets(HTMLParser):
    def __init__(self, body):
        super().__init__(convert_charrefs=True)
        self.paths = set()
        self.feed(body.decode('utf-8', errors='replace'))

    def handle_starttag(self, tag, attrs):
        for name, value in attrs:
            if name not in ['src', 'href'] or not value or len(value) > 1024:
                continue
            p = urllib.parse.urlsplit(value)
            if p.scheme or p.netloc or not re.search(r'\.(?:js|css|png|jpe?g|gif|svg|webp|ico|woff2?)$', p.path, re.I):
                continue
            target = urllib.parse.urljoin('/', value)
            if target.startswith('/') and not target.startswith('//'):
                self.paths.add(target)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--app', choices=sorted(TARGETS), required=True)
    p.add_argument('--mode', choices=['baseline', 'after', 'restart'], required=True)
    p.add_argument('--output-dir', type=Path, required=True)
    p.add_argument('--expected-revision', required=True)
    a = p.parse_args()
    os.umask(0o077)
    need(ROOT.is_mount() and ROOT in a.output_dir.parents and a.output_dir.resolve() == a.output_dir
         and re.fullmatch('[0-9a-f]{40}', a.expected_revision), 'canonical_private_scope')
    a.output_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    need(a.output_dir.stat().st_uid == os.getuid() and not a.output_dir.stat().st_mode & 0o077, 'private_output_owner')
    keyfile = a.output_dir / 'observation.key'
    if not keyfile.exists():
        need(a.mode == 'baseline', 'baseline_first')
        with keyfile.open('xb') as f:
            f.write(os.urandom(32))
    key = keyfile.read_bytes()
    need(len(key) == 32 and keyfile.resolve() == keyfile and keyfile.stat().st_uid == os.getuid()
         and not keyfile.stat().st_mode & 0o077, 'private_observation_key')
    directory = a.output_dir / a.app
    directory.mkdir(mode=0o700, exist_ok=True)
    target = directory / (a.mode + '.json')
    need(not target.exists(), 'immutable_observation')
    mac = lambda v: hmac.new(key, json.dumps(v, sort_keys=True, separators=(',', ':')).encode(), hashlib.sha256).hexdigest()
    duid, huid, puid, suid, port = TARGETS[a.app]
    d = get('deployment', a.app)
    hr = get('helmrelease', a.app, 'flux-system')
    source = get('gitrepository', 'branconet-charts', 'flux-system')
    need(d['metadata']['uid'] == duid and hr['metadata']['uid'] == huid
         and d['spec']['replicas'] == 1 and d['status'].get('observedGeneration') == d['metadata']['generation']
         and all(d['status'].get(k) == 1 for k in ['replicas', 'readyReplicas', 'availableReplicas', 'updatedReplicas']), 'original_ready_writer')
    need(source['status']['artifact']['revision'] == 'validated@sha1:' + a.expected_revision
         and hr['status'].get('lastAttemptedRevision', '').endswith('+' + a.expected_revision[:12])
         and hr['status'].get('observedGeneration') == hr['metadata']['generation']
         and any(c['type'] == 'Ready' and c['status'] == 'True' for c in hr['status'].get('conditions', [])), 'exact_reconciled_revision')
    pods = json.loads(call(['kubectl', '-n', 'web-apps', 'get', 'pods', '-l', 'app=' + a.app, '-o', 'json']))['items']
    need(len(pods) == 1, 'one_owned_pod')
    pod = pods[0]
    cs = pod['status']['containerStatuses'][0]
    image = OLD if a.mode == 'baseline' else NEW
    template = d['spec']['template']['spec']
    need(len(template['containers']) == 1 and template['containers'][0]['image'] == image
         and template['containers'][0]['envFrom'] == [{'secretRef': {'name': a.app + '-runtime'}}]
         and any(v.get('persistentVolumeClaim', {}).get('claimName') == a.app + '-data-0' for v in template['volumes'])
         and any(m['mountPath'] == '/usr/share/nginx/html' and not m.get('subPath') and not m.get('subPathExpr')
                 for m in template['containers'][0]['volumeMounts']), 'original_native_launch_and_content_mount')
    need(not pod['metadata'].get('deletionTimestamp') and pod['status']['phase'] == 'Running' and cs['ready']
         and pod['spec']['containers'][0]['image'] == image
         and cs['imageID'].rsplit('@', 1)[-1] in ({OLD.rsplit('@', 1)[1]} if a.mode == 'baseline' else {NEW.rsplit('@', 1)[1], CHILD}), 'exact_runtime')
    pvc = get('pvc', a.app + '-data-0')
    pv = get('pv', pvc['spec']['volumeName'])
    need(pvc['metadata']['uid'] == puid and pvc['status']['phase'] == 'Bound' and pvc['status']['capacity']['storage'] == '1Gi'
         and pv['spec']['claimRef']['uid'] == puid and pv['spec']['csi']['driver'] == 'driver.longhorn.io', 'original_longhorn_content')
    secret = get('secret', a.app + '-runtime')
    need(secret['metadata']['uid'] == suid, 'original_native_secret')
    stable = {'deploymentUID': duid, 'releaseUID': huid, 'pvcUID': puid, 'pvcSpecHMAC': mac(pvc['spec']),
              'pvUID': pv['metadata']['uid'], 'pvSpecHMAC': mac(pv['spec']), 'secret': {'uid': suid,
              'rv': secret['metadata']['resourceVersion'], 'type': secret.get('type', 'Opaque'), 'contentHMAC': mac(secret.get('data', {}))}}
    secret = None
    normalized = json.loads(json.dumps(d['spec']))
    normalized['template']['spec']['containers'][0]['image'] = '<reviewed-image>'
    annotations = normalized['template']['metadata'].get('annotations', {})
    annotations.pop('branconet.lan/security-restart', None)
    if not annotations:
        normalized['template']['metadata'].pop('annotations', None)
    stable['deploymentSpecHMAC'] = mac(normalized)
    stable['services'] = {}
    for name in [a.app, a.app + '-published']:
        obj = get('service', name)
        stable['services'][name] = {'uid': obj['metadata']['uid'], 'specHMAC': mac(obj['spec'])}
    ingresses = json.loads(call(['kubectl', '-n', 'web-apps', 'get', 'ingresses', '-o', 'json']))['items']
    ingresses = [r for r in ingresses if any(path.get('backend', {}).get('service', {}).get('name') == a.app
                 for rule in r['spec'].get('rules', []) for path in rule.get('http', {}).get('paths', []))]
    need(len(ingresses) == 2, 'original_http_https_ingresses')
    stable['ingresses'] = {r['metadata']['name']: {'uid': r['metadata']['uid'], 'specHMAC': mac(r['spec']),
                           'annotationsHMAC': mac(r['metadata'].get('annotations', {}))} for r in ingresses}
    public_hosts = sorted({host for r in ingresses for tls in r['spec'].get('tls', []) for host in tls.get('hosts', [])})
    hosts = sorted({rule['host'] for r in ingresses for rule in r['spec'].get('rules', [])})
    need(len(public_hosts) == 1 and all(re.fullmatch(r'[A-Za-z0-9.-]{1,253}', h) for h in hosts), 'finite_existing_route_hosts')
    prefix = ['kubectl', '-n', 'web-apps', 'exec', pod['metadata']['name'], '--']
    config = call(prefix + ['nginx', '-T'])
    stable['activeConfigHMAC'] = hmac.new(key, config, hashlib.sha256).hexdigest()
    version = call(prefix + ['sh', '-c', 'nginx -v 2>&1']).decode().strip()
    need(version == 'nginx version: nginx/1.30.6', 'same_patched_nginx_version')
    producer = subprocess.Popen(SSH + [shlex.join(prefix + ['tar', '-cf', '-', '-C', '/usr/share/nginx/html', '.'])],
                                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    entries = {}
    total = 0
    start = time.monotonic()
    try:
        with tarfile.open(fileobj=producer.stdout, mode='r|') as tar:
            for member in tar:
                name = member.name.removeprefix('./').rstrip('/')
                if name in ['', '.']:
                    name = '@root'
                need(name not in entries and not name.startswith('/') and '..' not in Path(name).parts
                     and len(entries) < 65536 and time.monotonic() - start < 180, 'bounded_served_tree')
                row = {'uid': member.uid, 'gid': member.gid, 'mode': member.mode}
                if member.isdir():
                    row['kind'] = 'directory'
                elif member.issym() or member.islnk():
                    link = posixpath.normpath(posixpath.join(posixpath.dirname(name) if member.issym() else '', member.linkname))
                    need(not link.startswith('/') and link != '..' and not link.startswith('../'), 'in_tree_link_only')
                    row.update(kind='symlink' if member.issym() else 'hardlink', targetHMAC=mac(member.linkname))
                else:
                    need(member.isfile() and 0 <= member.size <= 1024**3, 'regular_bounded_content')
                    total += member.size
                    need(total <= 1024**3, 'one_GiB_complete_content_bound')
                    stream = tar.extractfile(member)
                    digest = hmac.new(key, digestmod=hashlib.sha256)
                    count = 0
                    for b in iter(lambda: stream.read(1024**2), b''):
                        digest.update(b)
                        count += len(b)
                    need(count == member.size, 'complete_content_file')
                    row.update(kind='file', bytes=count, hmac=digest.hexdigest())
                entries[name] = row
        need(producer.wait(timeout=30) == 0 and entries, 'complete_content_tar')
    finally:
        if producer.poll() is None:
            producer.terminate()
            producer.wait(timeout=10)
    stable['content'] = entries
    http = {}
    index = None
    tls_context = ssl.create_default_context()
    def fetch(ip, request_port, path='/', host=None, secure=False):
        conn = http_client.HTTPConnection(ip, request_port, timeout=20)
        try:
            if secure:
                conn.connect()
                conn.sock = tls_context.wrap_socket(conn.sock, server_hostname=host)
            conn.request('GET', path, headers={'Host': host or ip, 'Accept-Encoding': 'identity'})
            r = conn.getresponse()
            b = r.read(16 * 1024**2 + 1)
            need(r.status == 200 and len(b) <= 16 * 1024**2, 'successful_bounded_site_response')
            return b, {'status': r.status, 'bytes': len(b), 'contentType': r.getheader('Content-Type'),
                       'bodyHMAC': hmac.new(key, b, hashlib.sha256).hexdigest()}
        finally:
            conn.close()
    for ip in ['192.168.0.4', '192.168.0.5', '192.168.0.6']:
        body, response = fetch(ip, port)
        if index is None:
            index = body
        else:
            need(index == body, 'same_content_all_published_nodes')
        http[ip + ':published'] = response
        for host in hosts:
            body, response = fetch(ip, 80, host=host)
            need(body == index, 'same_ingress_http_content')
            http[ip + ':http:' + host] = response
        body, response = fetch(ip, 443, host=public_hosts[0], secure=True)
        need(body == index, 'same_verified_https_content')
        http[ip + ':https:' + public_hosts[0]] = response
    for path in sorted(Assets(index).paths)[:8]:
        _, response = fetch('192.168.0.4', port, path=path)
        http['asset:' + path] = response
    stable['http'] = http
    failures = []
    if a.mode != 'baseline':
        before = json.loads((directory / 'baseline.json').read_bytes())
        need(before['passed'] and before['keyBinding'] == mac('static-sites-upstream-v1:' + a.app), 'exact_original_baseline')
        failures = [name for name, value in before['stable'].items() if stable.get(name) != value]
        need(pod['metadata']['uid'] != before['podUID'], 'different_adoption_pod')
        if a.mode == 'restart':
            prior = json.loads((directory / 'after.json').read_bytes())
            need(prior['passed'] and pod['metadata']['uid'] != prior['podUID'], 'different_restart_pod')
    result = {'app': a.app, 'mode': a.mode, 'passed': not failures, 'mismatches': failures, 'stable': stable,
              'keyBinding': mac('static-sites-upstream-v1:' + a.app), 'podUID': pod['metadata']['uid'],
              'image': image, 'imageID': cs['imageID'], 'restartCount': cs['restartCount'], 'version': version,
              'contentBytes': total, 'contentEntries': len(entries), 'contentFiles': sum(r['kind'] == 'file' for r in entries.values()),
              'httpChecks': len(http), 'fluxRevision': source['status']['artifact']['revision'],
              'sourceSHA256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'observedUTC': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'browserAccepted': False}
    need(len(json.dumps(result)) <= 64 * 1024**2, 'bounded_private_receipt')
    with target.open('xb') as f:
        f.write((json.dumps(result, sort_keys=True, indent=2) + '\n').encode())
    print(json.dumps({k: result[k] for k in ['app', 'mode', 'passed', 'mismatches', 'podUID', 'contentBytes', 'contentFiles', 'contentEntries', 'httpChecks']}))
    return int(bool(failures))


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as error:
        print(json.dumps({'passed': False, 'errorCategory': str(error) if type(error) is ValueError else type(error).__name__, 'rawDetailsSuppressed': True}))
        raise SystemExit(1)
