#!/usr/bin/env python3
"""Read-only Jackett identity/config, native Torznab API and runtime comparison."""
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
import xml.etree.ElementTree as ET

BASE = Path('/home/brajam/.local/share/branconet-migration')
SSH = ['ssh', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes', '-o', 'ConnectTimeout=10',
       '-i', '/home/brajam/.ssh/id_ed25519', '-p', '2002', 'james@192.168.0.4']
OLD = 'linuxserver/jackett:latest@sha256:cdea5d3209a6ab1fb8eb954ec0b8169b7d54274617f42bf5c74f22a92075755f'
RUNTIME_COOKIES = {'Jackett/Indexers/eztv.json': ['cf_clearance'],
                   'Jackett/Indexers/1337x.json': ['cf_clearance'],
                   'Jackett/Indexers/nyaasi.json': ['__ddg8_', '__ddg10_']}


def need(ok, reason):
    if not ok:
        raise ValueError(reason)


def call(args, timeout=45, allowed_exits=(0,)):
    p = subprocess.run(SSH + [shlex.join(args)], capture_output=True, timeout=timeout)
    need(p.returncode in allowed_exits and len(p.stdout) <= 4 * 1024**2, 'bounded_cluster_operation')
    return p.stdout


def get(kind, name, ns='plex'):
    return json.loads(call(['kubectl', '-n', ns, 'get', kind, name, '-o', 'json']))


def config_bytes(name, raw):
    if name == 'Jackett/ServerConfig.json':
        config = json.loads(raw); config.pop('UpdateDisabled')
        return json.dumps(config, sort_keys=True, separators=(',', ':')).encode()
    if name in RUNTIME_COOKIES:
        # These three pinned definitions are public, with no login fields. Their
        # anti-bot challenge cookies rotate under normal Arr/FlareSolverr traffic.
        # Compare every setting, cookie name and other cookie value; exclude only
        # the four named challenge-value slots. Never rewrite the live files.
        settings = json.loads(raw)
        need(isinstance(settings, list) and all(isinstance(s, dict) and isinstance(s.get('id'), str) for s in settings)
             and len({s['id'] for s in settings}) == len(settings)
             and not any(s['id'].lower() in ['username', 'password', 'passkey', 'apikey', 'cookie'] for s in settings), 'public_indexer_without_login_settings')
        cookie = [s for s in settings if s['id'] == 'cookieheader']
        need(len(cookie) == 1 and isinstance(cookie[0].get('value'), str) and len(cookie[0]['value']) <= 8192, 'one_bounded_runtime_cookie_header')
        pairs = [v.strip().split('=', 1) for v in cookie[0]['value'].split(';')]
        need(0 < len(pairs) <= 32 and all(len(v) == 2 and v[0] and not any(c in v[0] for c in '\r\n"\\') for v in pairs)
             and len({v[0] for v in pairs}) == len(pairs), 'unambiguous_cookie_names')
        need(set(RUNTIME_COOKIES[name]) <= {v[0] for v in pairs}, 'existing_named_challenge_cookies')
        cookie[0]['value'] = '; '.join(k + '=' + ('[runtime-antibot-value]' if k in RUNTIME_COOKIES[name] else v) for k, v in sorted(pairs))
        return json.dumps(settings, sort_keys=True, separators=(',', ':')).encode()
    return raw


def fence(image):
    d, h, pvc = get('deployment', 'jackett'), get('helmrelease', 'jackett', 'flux-system'), get('pvc', 'jackett-data-0')
    need(d['metadata']['uid'] == '8ff38b3e-d114-4a03-adfd-2078d359530c'
         and h['metadata']['uid'] == 'cc166e8b-d45a-4e77-bdfe-e874240cfb4d'
         and pvc['metadata']['uid'] == '7d4e8aea-5715-4ee3-8e56-352b7b1e99f0'
         and pvc['status']['phase'] == 'Bound', 'original_workload_and_data')
    need(d['spec']['replicas'] == 1 and d['status'].get('observedGeneration') == d['metadata']['generation']
         and all(d['status'].get(k) == 1 for k in ['replicas', 'updatedReplicas', 'readyReplicas', 'availableReplicas'])
         and h['status'].get('observedGeneration') == h['metadata']['generation']
         and any(c['type'] == 'Ready' and c['status'] == 'True' for c in h['status'].get('conditions', [])), 'ready_flux_writer')
    pods = json.loads(call(['kubectl', '-n', 'plex', 'get', 'pods', '-l', 'app=jackett', '-o', 'json']))['items']
    need(len(pods) == 1, 'one_owned_pod')
    pod = pods[0]; c = pod['spec']['containers'][0]; cs = pod['status']['containerStatuses'][0]
    need(not pod['metadata'].get('deletionTimestamp') and cs['ready'] and c['name'] == 'jackett'
         and c['image'] == image and c['envFrom'] == [{'secretRef': {'name': 'jackett-runtime'}}]
         and any(v.get('persistentVolumeClaim', {}).get('claimName') == 'jackett-data-0' for v in pod['spec']['volumes']), 'original_launch_and_config')
    if image != OLD:
        need(image.startswith('docker.io/library/jackett-security-20261023@sha256:')
             and cs['imageID'].endswith('@' + image.rsplit('@', 1)[1])
             and {'name': 'AUTO_UPDATE', 'value': 'false'} in c.get('env', []), 'exact_patched_runtime_no_bootstrap_update')
    secret = call(['kubectl', '-n', 'plex', 'get', 'secret', 'jackett-runtime', '-o', 'jsonpath={.metadata.uid}{" "}{.metadata.resourceVersion}']).decode().split()
    need(len(secret) == 2, 'metadata_only_secret_identity')
    pv = get('pv', pvc['spec']['volumeName'])
    need(pv['spec']['claimRef']['uid'] == pvc['metadata']['uid'] and pv['spec']['csi']['driver'] == 'driver.longhorn.io', 'original_longhorn_volume')
    return {'deploymentUID': d['metadata']['uid'], 'releaseUID': h['metadata']['uid'], 'pvcUID': pvc['metadata']['uid'],
            'pvUID': pv['metadata']['uid'], 'pod': pod['metadata']['name'], 'podUID': pod['metadata']['uid'],
            'secretUID': secret[0], 'secretRV': secret[1], 'image': image, 'imageID': cs['imageID']}


def cold_tree(receipt_path, expected_sha, key):
    need(receipt_path.resolve() == receipt_path and BASE in receipt_path.parents
         and not receipt_path.stat().st_mode & 0o077
         and hashlib.sha256(receipt_path.read_bytes()).hexdigest() == expected_sha, 'exact_private_cold_receipt')
    r = json.loads(receipt_path.read_bytes())
    need(r['application'] == 'jackett' and r['status'] == 'completed' and r['cold_archive_verified']
         and r['temporary_pod_deleted'] and r['original_image'] == OLD
         and r['claim_uid'] == '7d4e8aea-5715-4ee3-8e56-352b7b1e99f0', 'original_completed_cold_archive')
    path = Path(r['archive_path']); need(path.parent == receipt_path.parent and not path.stat().st_mode & 0o077, 'original_private_archive')
    digest = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024**2), b''): digest.update(block)
    need(digest.hexdigest() == r['archive_sha256'], 'original_ciphertext_sha')
    need(hashlib.sha256((BASE / 'bin/age').read_bytes()).hexdigest() == 'eb7dd1b518f0a307c99cd97782623c5321da049154b04acd2d98d21aa7bc9b2c', 'pinned_archive_authenticator')
    child = subprocess.Popen([str(BASE / 'bin/age'), '-d', '-i', '/home/brajam/.ssh/id_ed25519', str(path)],
                             stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    entries = {}; seen = set(); total = 0; manifest = None
    try:
        with tarfile.open(fileobj=child.stdout, mode='r|') as archive:
            for m in archive:
                name = m.name.rstrip('/'); need(name not in seen and len(seen) < 4097, 'bounded_complete_cold_members'); seen.add(name)
                if name == 'manifest.json':
                    need(len(seen) == 1 and m.isfile() and m.size <= 8 * 1024**2, 'original_cold_manifest')
                    manifest = json.load(archive.extractfile(m)); continue
                need(manifest is not None and name in manifest['entries'], 'manifest_member')
                row = manifest['entries'][name]
                need(m.mode == row['mode'] and m.uid == row['uid'] and m.gid == row['gid'], 'original_cold_metadata')
                if row['kind'] == 'directory': need(m.isdir(), 'cold_directory'); continue
                if row['kind'] == 'symlink': need(m.issym() and m.linkname == row['link'], 'cold_symlink'); continue
                need(m.isfile() and m.size == row['bytes'] and m.size <= 128 * 1024**2, 'bounded_cold_config_file')
                total += m.size; need(total <= 128 * 1024**2, 'bounded_complete_cold_config')
                raw = archive.extractfile(m).read(); need(len(raw) == m.size and hashlib.sha256(raw).hexdigest() == row['sha256'], 'complete_cold_file')
                if not name.startswith('data-0/Jackett/'): continue
                name = name[len('data-0/'):]
                if name.startswith('Jackett/log') or name.startswith('Jackett/Logs/') or name.startswith('Jackett/Cache/') or name.endswith('.bak'): continue
                raw = config_bytes(name, raw)
                entries[name] = {'hmac': hmac.new(key, raw, hashlib.sha256).hexdigest(), 'mode': m.mode, 'uid': m.uid, 'gid': m.gid}
        for block in iter(lambda: child.stdout.read(65536), b''): need(not any(block), 'cold_padding_only')
        need(child.wait(timeout=30) == 0 and seen == {'manifest.json'} | set(manifest['entries'])
             and total == manifest['total_file_bytes'], 'full_cold_archive_authentication_and_inventory')
    finally:
        if child.poll() is None: child.kill(); child.wait(timeout=10)
    return hmac.new(key, json.dumps(entries, sort_keys=True).encode(), hashlib.sha256).hexdigest()


def main():
    p = argparse.ArgumentParser(); p.add_argument('--output-dir', type=Path, required=True)
    p.add_argument('--baseline', type=Path); p.add_argument('--image', default=OLD)
    p.add_argument('--cold-receipt', type=Path); p.add_argument('--cold-sha256'); a = p.parse_args()
    os.umask(0o077)
    need(os.name == 'posix' and a.output_dir.resolve() == a.output_dir and BASE in a.output_dir.parents, 'private_native_output')
    a.output_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    report = {'passed': False, 'comparisonVersion': 2, 'startedUTC': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'volatilePublicAntiBotCookieValuesExcluded': RUNTIME_COOKIES,
              'sourceSHA256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), 'externalSearchOrNotificationSent': False}
    try:
        keyfile = a.output_dir / 'observation.key'
        if not keyfile.exists():
            with keyfile.open('xb') as f: f.write(os.urandom(32))
        key = keyfile.read_bytes(); need(len(key) == 32 and not keyfile.stat().st_mode & 0o077, 'private_observation_key')
        before = fence(a.image); prefix = ['kubectl', '-n', 'plex', 'exec', before['pod'], '--']
        # The upstream command-line parser deliberately exits 1 after printing help.
        version = call(prefix + ['/app/Jackett/jackett', '--help'], allowed_exits=(0, 1)).decode()
        need('0.24.1440' in version, 'unchanged_application_version')
        if a.image != OLD:
            call(prefix + ['sh', '-c', "ps -eo args | grep -q '^/app/Jackett/jackett --NoUpdates'"])
            report['runtimeSelfUpdatesDisabled'] = True
        # The API accepts the native query credential. Construct it inside the Pod,
        # send via curl stdin, and return only the public capabilities XML.
        shell = r'''set -eu
jq -er '.APIKey | select(type == "string" and length > 0) | ("http://127.0.0.1:9117/api/v2.0/indexers/all/results/torznab?t=caps&apikey=" + .) | "url = " + tojson' /config/Jackett/ServerConfig.json | curl --silent --show-error --fail --max-time 30 --config -
'''
        caps = ET.fromstring(call(prefix + ['sh', '-c', shell])); need(caps.tag == 'caps' and caps.find('searching') is not None, 'native_authenticated_torznab_capabilities')
        child = subprocess.Popen(SSH + [shlex.join(prefix + ['tar', '-cf', '-', '-C', '/config', 'Jackett'])], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        entries = {}; total = 0; start = time.monotonic(); configured = 0
        try:
            with tarfile.open(fileobj=child.stdout, mode='r|') as archive:
                for m in archive:
                    need(len(entries) < 8192 and not m.name.startswith('/') and '..' not in Path(m.name).parts
                         and time.monotonic() - start < 120 and (m.isfile() or m.isdir()), 'bounded_config_tree')
                    if not m.isfile(): continue
                    total += m.size; need(total <= 128 * 1024**2, 'bounded_config_bytes')
                    raw = archive.extractfile(m).read(); need(len(raw) == m.size, 'complete_config_file')
                    name = m.name.removeprefix('./')
                    if name.startswith('Jackett/log') or name.startswith('Jackett/Logs/') or name.startswith('Jackett/Cache/') or name.endswith('.bak'): continue
                    if name == 'Jackett/ServerConfig.json':
                        config = json.loads(raw); report['updateDisabled'] = config['UpdateDisabled']
                        need(bool(config.get('APIKey')) and bool(config.get('AdminPassword')), 'existing_api_and_admin_identity')
                    raw = config_bytes(name, raw)
                    if name.startswith('Jackett/Indexers/') and name.endswith('.json'): configured += 1
                    entries[name] = {'hmac': hmac.new(key, raw, hashlib.sha256).hexdigest(), 'mode': m.mode, 'uid': m.uid, 'gid': m.gid}
            for block in iter(lambda: child.stdout.read(65536), b''): need(not any(block), 'archive_padding_only')
            need(child.wait(timeout=20) == 0 and 'Jackett/ServerConfig.json' in entries, 'complete_config_tree')
        finally:
            if child.poll() is None: child.kill(); child.wait(timeout=10)
        need(fence(a.image) == before, 'stable_observed_writer')
        report.update(writer=before, configTreeHMAC=hmac.new(key, json.dumps(entries, sort_keys=True).encode(), hashlib.sha256).hexdigest(),
                      comparedFiles=len(entries), observedConfigBytes=total, configuredIndexers=configured, torznabAuthenticated=True, appVersion='0.24.1440')
        if a.baseline:
            need(a.baseline.parent == a.output_dir, 'same_baseline_scope'); old = json.loads(a.baseline.read_bytes())
            expected_tree = old['configTreeHMAC']
            if a.cold_receipt:
                expected_tree = cold_tree(a.cold_receipt, a.cold_sha256, key)
                report.update(coldReceiptSHA256=a.cold_sha256, fullColdArchiveAuthenticated=True,
                              originalActiveByteBaselineRetained=True)
            need(old['passed'] and expected_tree == report['configTreeHMAC'] and old['configuredIndexers'] == configured, 'original_credentials_indexers_and_protection_files')
            need(all(before[k] == old['writer'][k] for k in ['deploymentUID', 'releaseUID', 'pvcUID', 'pvUID', 'secretUID', 'secretRV'])
                 and before['podUID'] != old['writer']['podUID'], 'same_native_identity_and_data_new_pod')
        report['passed'] = True
    except Exception as error:
        report['failure'] = str(error) if isinstance(error, ValueError) else type(error).__name__
    report['endedUTC'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    out = a.output_dir / ('jackett-functional-' + uuid.uuid4().hex + '.json'); out.write_text(json.dumps(report, sort_keys=True, indent=2) + '\n')
    print(json.dumps({'passed': report['passed'], 'receipt': str(out), 'receiptSHA256': hashlib.sha256(out.read_bytes()).hexdigest(), 'failure': report.get('failure')}))
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
