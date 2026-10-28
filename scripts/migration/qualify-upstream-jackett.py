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
OLD = 'docker.io/library/jackett-security-20261023@sha256:08f115ddcbc3e01bf5379e4c91ea594fae49666678b53ed20af889773b1ca729'
NEW = 'docker.io/linuxserver/jackett:0.24.2910@sha256:19d90927b95397f2d1364e4999e11456abdbbb382b54cd765fc3b3da24d7088b'
CHILD = 'sha256:c7089eab050a2bbd6b71c33030c7fe7f560c93e50ec07029164a15a8200557f6'
RUNTIME_COOKIES = {'Jackett/Indexers/eztv.json': ['cf_clearance'],
                   'Jackett/Indexers/1337x.json': ['cf_clearance'],
                   'Jackett/Indexers/nyaasi.json': ['__ddg8_', '__ddg10_']}

ROUTES = r'''
import http.client,ssl,subprocess,hashlib,json,http.cookies,urllib.parse
routes={};certificates={}
for ip in ['192.168.0.4','192.168.0.5','192.168.0.6']:
 for port in [9117,80,443]:
  c=http.client.HTTPConnection(ip,port,timeout=20)
  try:
   trusted=None
   if port==443:
    try:c.connect();c.sock=ssl.create_default_context().wrap_socket(c.sock,server_hostname='jackett.branconet.lan');trusted=True
    except ssl.SSLCertVerificationError as e:
     assert e.verify_code==18;c.close();c=http.client.HTTPConnection(ip,port,timeout=20);c.connect()
     ctx=ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT);ctx.check_hostname=False;ctx.verify_mode=ssl.CERT_NONE
     c.sock=ctx.wrap_socket(c.sock,server_hostname='jackett.branconet.lan');trusted=False
     der=c.sock.getpeercert(binary_form=True)
     proof=subprocess.run(['openssl','x509','-inform','DER','-noout','-subject','-issuer'],input=der,capture_output=True,timeout=10)
     assert proof.returncode==0 and proof.stdout.decode().strip().splitlines()==['subject=CN = TRAEFIK DEFAULT CERT','issuer=CN = TRAEFIK DEFAULT CERT']
    certificates[ip]={'sha256':hashlib.sha256(c.sock.getpeercert(binary_form=True)).hexdigest(),'trustedHostnameAndChain':trusted}
   cookies={};path='/UI/Login';scheme='https'if port==443 else'http'
   for hop in range(6):
    headers={'Host':'jackett.branconet.lan','Accept-Encoding':'identity'}
    if cookies:headers['Cookie']='; '.join(cookies.values())
    c.request('GET',path,headers=headers);r=c.getresponse();b=r.read(2097153);assert len(b)<=2097152
    for name,value in r.getheaders():
     if name.lower()=='set-cookie':
      parsed=http.cookies.SimpleCookie();parsed.load(value)
      for name,morsel in parsed.items():
       if not morsel['secure']or port==443:cookies[name]=morsel.OutputString(attrs=[])
    if r.status in[301,302,303,307,308]:
     uri=urllib.parse.urlsplit(urllib.parse.urljoin(scheme+'://jackett.branconet.lan'+path,r.getheader('Location')or''))
     assert uri.scheme==scheme and uri.hostname=='jackett.branconet.lan'and uri.port in[None,port]and uri.path.startswith('/UI/')
     path=urllib.parse.urlunsplit(('','',uri.path,uri.query,''));continue
    assert r.status==200 and b'Jackett'in b and b'password'in b.lower();break
   else:raise ValueError('bounded_original_login_cookie_flow')
   routes[ip+':'+str(port)]={'status':r.status,'jackettUI':True}
  finally:c.close()
print(json.dumps({'routes':routes,'certificates':certificates}))
'''


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
        config = json.loads(raw)
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
        if name == 'Jackett/Indexers/1337x.json':
            # Vendor 0.24.2910 changed the setting IDs and iTorrents selector
            # enum. Compare the same original primary/fallback choices; a
            # reversal to the vendor defaults still fails this comparison.
            ids = {s['id'] for s in settings}
            old = {'downloadlink', 'downloadlink(fallback)'}
            new = {'primarydownloadlink', 'fallbackdownloadlink'}
            need((old <= ids and not new & ids) or (new <= ids and not old & ids), 'one_declared_1337x_schema')
            legacy = old <= ids
            aliases = {'downloadlink': 'primarydownloadlink', 'downloadlink(fallback)': 'fallbackdownloadlink'}
            for setting in settings:
                if setting['id'] in (old if legacy else new):
                    primary = setting['id'] in {'downloadlink', 'primarydownloadlink'}
                    expected_name = ('Download link' if primary else 'Download link (fallback)') if legacy else ('Primary Download link' if primary else 'Fallback Download link')
                    expected_options = {'http://itorrents.org/': 'iTorrents.org', 'magnet:': 'magnet'} if legacy else {'//itorrents.': 'iTorrents', 'magnet:': 'magnet'}
                    need(setting.get('type') == 'inputselect' and setting.get('name') == expected_name
                         and setting.get('options') == expected_options, 'exact_declared_download_selector_schema')
                    need(setting['value'] in ({'http://itorrents.org/', 'magnet:'} if legacy else {'//itorrents.', 'magnet:'}), 'declared_download_link_enum')
                    setting['id'] = aliases.get(setting['id'], setting['id'])
                    setting['value'] = '[magnet]' if setting['value'] == 'magnet:' else '[iTorrents]'
                    setting['name'] = '[primary]' if primary else '[fallback]'
                    setting['options'] = {'[iTorrents]': 'iTorrents', '[magnet]': 'magnet'}
        return json.dumps(settings, sort_keys=True, separators=(',', ':')).encode()
    return raw


def fence(image, key, revision):
    mac = lambda v: hmac.new(key, json.dumps(v, sort_keys=True, separators=(',', ':')).encode(), hashlib.sha256).hexdigest()
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
    need(image in [OLD, NEW] and cs['imageID'].rsplit('@', 1)[-1] in [image.rsplit('@', 1)[1], CHILD if image == NEW else image.rsplit('@', 1)[1]]
         and {'name': 'AUTO_UPDATE', 'value': 'false'} in c.get('env', []), 'exact_owned_or_vendor_runtime_no_bootstrap_update')
    source = get('gitrepository', 'branconet-charts', 'flux-system')
    need(len(revision) == 40 and source['status']['artifact']['revision'] == 'validated@sha1:' + revision
         and h['status']['lastAttemptedRevision'].endswith('+' + revision[:12]), 'exact_flux_revision')
    secret = get('secret', 'jackett-runtime')
    pv = get('pv', pvc['spec']['volumeName'])
    need(pv['spec']['claimRef']['uid'] == pvc['metadata']['uid'] and pv['spec']['csi']['driver'] == 'driver.longhorn.io', 'original_longhorn_volume')
    normalized = json.loads(json.dumps(d['spec']))
    normalized['template']['spec']['containers'][0]['image'] = '<maintained-image>'
    annotations = normalized['template']['metadata'].get('annotations', {})
    annotations.pop('branconet.lan/security-restart', None)
    if not annotations:
        normalized['template']['metadata'].pop('annotations', None)
    stable = {'deploymentSpecHMAC': mac(normalized), 'pvcSpecHMAC': mac(pvc['spec']), 'pvSpecHMAC': mac(pv['spec']),
              'secretType': secret['type'], 'secretDataHMAC': mac(secret.get('data', {}))}
    for kind, names in [('service', ['jackett', 'jackett-published']), ('ingress', ['jackett-http', 'jackett-https'])]:
        for name in names:
            r = get(kind, name)
            stable[kind + '/' + name] = {'uid': r['metadata']['uid'], 'specHMAC': mac(r['spec']),
                'annotationsHMAC': mac(r['metadata'].get('annotations', {}))}
    return {'deploymentUID': d['metadata']['uid'], 'releaseUID': h['metadata']['uid'], 'pvcUID': pvc['metadata']['uid'],
            'pvUID': pv['metadata']['uid'], 'pod': pod['metadata']['name'], 'podUID': pod['metadata']['uid'],
            'secretUID': secret['metadata']['uid'], 'secretRV': secret['metadata']['resourceVersion'],
            'image': image, 'imageID': cs['imageID'], 'stable': stable}


def cold_tree(receipt_path, expected_sha, key):
    need(receipt_path.resolve() == receipt_path and BASE in receipt_path.parents
         and not receipt_path.stat().st_mode & 0o077
         and hashlib.sha256(receipt_path.read_bytes()).hexdigest() == expected_sha, 'exact_private_cold_receipt')
    r = json.loads(receipt_path.read_bytes())
    need(r['application'] == 'jackett' and r['status'] == 'completed' and r['cold_archive_verified']
         and r['temporary_pod_deleted'] and r['original_image'] == OLD and r['generation'] == 'upstream-jackett-20261026'
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
    p.add_argument('--phase', choices=['baseline', 'after', 'restart'], required=True)
    p.add_argument('--expected-revision', required=True)
    p.add_argument('--cold-receipt', type=Path); p.add_argument('--cold-sha256'); a = p.parse_args()
    os.umask(0o077)
    root = BASE / 'local-image-build-offload-20261025'
    need(os.name == 'posix' and a.output_dir.resolve() == a.output_dir and root in a.output_dir.parents
         and bool(a.baseline) == (a.phase != 'baseline') and a.image == (OLD if a.phase == 'baseline' else NEW), 'private_native_output_and_finite_phase')
    a.output_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    report = {'passed': False, 'comparisonVersion': 5, 'phase': a.phase, 'startedUTC': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'schemaMigration': {'file': 'Jackett/Indexers/1337x.json', 'preservePrimaryAndFallbackChoices': True,
                  'legacyIDs': ['downloadlink', 'downloadlink(fallback)'], 'vendorIDs': ['primarydownloadlink', 'fallbackdownloadlink'],
                  'sameVendorOption': {'http://itorrents.org/': '//itorrents.'}},
              'volatilePublicAntiBotCookieValuesExcluded': RUNTIME_COOKIES,
              'sourceSHA256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), 'externalSearchOrNotificationSent': False}
    try:
        keyfile = a.output_dir / 'observation.key'
        if not keyfile.exists():
            need(a.phase == 'baseline', 'original_observation_key_required')
            with keyfile.open('xb') as f: f.write(os.urandom(32))
        key = keyfile.read_bytes(); need(len(key) == 32 and not keyfile.stat().st_mode & 0o077, 'private_observation_key')
        before = fence(a.image, key, a.expected_revision); prefix = ['kubectl', '-n', 'plex', 'exec', before['pod'], '--']
        # The upstream command-line parser deliberately exits 1 after printing help.
        version = call(prefix + ['/app/Jackett/jackett', '--help'], allowed_exits=(0, 1)).decode()
        expected_version = '0.24.1440' if a.phase == 'baseline' else '0.24.2910'
        need(expected_version in version, 'exact_reviewed_application_version')
        call(prefix + ['sh', '-c', "ps -eo args | grep -q '^/app/Jackett/jackett --NoUpdates'"])
        report['runtimeSelfUpdatesDisabled'] = True
        # The API accepts the native query credential. Construct it inside the Pod,
        # send via curl stdin, and return only the public capabilities XML.
        shell = r'''set -eu
jq -er '.APIKey | select(type == "string" and length > 0) | ("http://127.0.0.1:9117/api/v2.0/indexers/all/results/torznab?t=caps&apikey=" + .) | "url = " + tojson' /config/Jackett/ServerConfig.json | curl --silent --show-error --fail --max-time 30 --config -
'''
        caps = ET.fromstring(call(prefix + ['sh', '-c', shell])); need(caps.tag == 'caps' and caps.find('searching') is not None, 'native_authenticated_torznab_capabilities')
        tls_route = get('ingress', 'jackett-https')
        need(not any(r.get('secretName') for r in tls_route['spec'].get('tls', [])), 'original_generated_default_certificate_route')
        routes = json.loads(call(['python3', '-c', ROUTES], timeout=180))
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
                        need(type(config['UpdateDisabled']) is bool, 'original_persisted_update_setting')
                        need(bool(config.get('APIKey')) and bool(config.get('AdminPassword')), 'existing_api_and_admin_identity')
                    raw = config_bytes(name, raw)
                    if name.startswith('Jackett/Indexers/') and name.endswith('.json'): configured += 1
                    entries[name] = {'hmac': hmac.new(key, raw, hashlib.sha256).hexdigest(), 'mode': m.mode, 'uid': m.uid, 'gid': m.gid}
            for block in iter(lambda: child.stdout.read(65536), b''): need(not any(block), 'archive_padding_only')
            need(child.wait(timeout=20) == 0 and 'Jackett/ServerConfig.json' in entries, 'complete_config_tree')
        finally:
            if child.poll() is None: child.kill(); child.wait(timeout=10)
        need(fence(a.image, key, a.expected_revision) == before, 'stable_observed_writer')
        report.update(writer=before, configTreeHMAC=hmac.new(key, json.dumps(entries, sort_keys=True).encode(), hashlib.sha256).hexdigest(),
                      comparedFiles=len(entries), observedConfigBytes=total, configuredIndexers=configured, torznabAuthenticated=True,
                      appVersion=expected_version, fluxRevision=a.expected_revision, routes=routes['routes'],
                      certificates=routes['certificates'], authenticatedTLSAccepted=all(r['trustedHostnameAndChain'] for r in routes['certificates'].values()))
        if a.baseline:
            need(a.baseline.parent == a.output_dir, 'same_baseline_scope'); old = json.loads(a.baseline.read_bytes())
            expected_tree = old['configTreeHMAC']
            if a.cold_receipt:
                expected_tree = cold_tree(a.cold_receipt, a.cold_sha256, key)
                report.update(coldReceiptSHA256=a.cold_sha256, fullColdArchiveAuthenticated=True,
                              originalActiveByteBaselineRetained=True)
            need(old['passed'] and expected_tree == report['configTreeHMAC'] and old['configuredIndexers'] == configured, 'original_credentials_indexers_and_protection_files')
            need(all(before[k] == old['writer'][k] for k in ['deploymentUID', 'releaseUID', 'pvcUID', 'pvUID', 'secretUID', 'secretRV', 'stable'])
                 and before['podUID'] != old['writer']['podUID'], 'same_native_identity_and_data_new_pod')
            need(report['routes'] == old['routes'] and report['authenticatedTLSAccepted'] == old['authenticatedTLSAccepted'], 'original_route_availability_and_explicit_trust_status')
            if a.phase == 'restart':
                prior = json.loads((a.output_dir / 'after.json').read_text())
                need(prior['passed'] and prior['writer']['podUID'] != before['podUID'], 'different_restart_pod')
        report['passed'] = True
    except Exception as error:
        report['failure'] = str(error) if isinstance(error, ValueError) else type(error).__name__
    report['endedUTC'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    out = a.output_dir / (a.phase + '.json' if report['passed'] else a.phase + '-failed-' + uuid.uuid4().hex + '.json')
    need(not out.exists(), 'immutable_phase_or_failure_receipt')
    with out.open('x') as f:
        json.dump(report, f, sort_keys=True, indent=2)
    print(json.dumps({'passed': report['passed'], 'receipt': str(out), 'receiptSHA256': hashlib.sha256(out.read_bytes()).hexdigest(), 'failure': report.get('failure')}))
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
