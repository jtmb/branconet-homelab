#!/usr/bin/env python3
"""GET-only Radarr update observation. Operator runs on master; never run in CI."""
import argparse
import datetime
import hashlib
import hmac
import ipaddress
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET

NS = 'plex'
DEP_UID = '3e2719e0-f7f5-4cf5-8ba9-9d94a68302f0'
PVC_UID = '7f07da4f-a34e-4bd0-a4a0-90b94f5a0fec'
OLD = 'linuxserver/radarr:latest@sha256:ca43905eaf2dd11425efdcfe184892e43806b1ae0a830440c825cecbc2629cfb'
NEW = 'docker.io/linuxserver/radarr:latest@sha256:fc0ae3c50f8128b97e84381903ec8d6845c3a569641cb7117c124376cccb57c1'
NEW_RUNTIME = 'sha256:a466ac12c33425ec22ec4bb0d71c3edb79fd5e5f845bba0e2901c1a6aa59b075'
HOST = 'radarr.branconet.lan'
MAX_REPLY = 16 * 1024 ** 2
MAX_TOTAL = 64 * 1024 ** 2
MAX_RECORDS = 50000


class Refused(Exception):
    pass


def need(value, reason):
    if not value:
        raise Refused(reason)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()


def command(argv, limit=MAX_REPLY):
    # Communicate through memory only; never include raw errors in a receipt.
    child = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                             stderr=subprocess.DEVNULL)
    try:
        # Only fixed narrow resource GETs and a head-bounded config read run here.
        # The subprocess deadline also covers an exec stream that never closes.
        data, _ = child.communicate(timeout=30)
        need(len(data) <= limit, 'command_response_limit')
        need(child.returncode == 0, 'kubectl_failed')
        return data
    finally:
        if child.poll() is None:
            child.kill()
            child.wait(timeout=5)


def kube(*argv, limit=MAX_REPLY):
    return command(['kubectl', '--request-timeout=20s', '-n', NS, *argv], limit)


def obj(*argv):
    return json.loads(kube(*argv, '-o', 'json'))


def identity(mode):
    expected = OLD if mode == 'baseline' else NEW
    dep = obj('get', 'deployment', 'radarr')
    md, ds, state = dep['metadata'], dep['spec'], dep.get('status', {})
    need(md['uid'] == DEP_UID and not md.get('deletionTimestamp'), 'deployment_identity')
    need(ds.get('replicas', 1) == 1 and state.get('observedGeneration', 0) >= md['generation'], 'deployment_generation')
    need(all(state.get(k, 0) == 1 for k in ['replicas', 'updatedReplicas', 'readyReplicas', 'availableReplicas']), 'deployment_not_ready')
    containers = ds['template']['spec']['containers']
    need(len(containers) == 1 and containers[0]['name'] == 'radarr' and containers[0]['image'] == expected, 'deployment_image')
    mounts = containers[0]['volumeMounts']
    need(any(m['name'] == 'data-0' and m['mountPath'] == '/config' and not m.get('subPath') and not m.get('readOnly', False) for m in mounts), 'config_mount')
    claims = {}
    for name in ['radarr-data-0', 'radarr-data-1', 'radarr-data-2']:
        pvc = obj('get', 'pvc', name)
        need(pvc['status']['phase'] == 'Bound' and not pvc['metadata'].get('deletionTimestamp'), 'claim_not_bound')
        claims[name] = {'uid': pvc['metadata']['uid'], 'volume': pvc['spec']['volumeName'],
                        'storage_class': pvc['spec'].get('storageClassName', '')}
    need(claims['radarr-data-0'] == {'uid': PVC_UID, 'volume': 'pvc-' + PVC_UID, 'storage_class': 'longhorn'}, 'config_claim_identity')
    actual_claims = {v.get('persistentVolumeClaim', {}).get('claimName') for v in ds['template']['spec'].get('volumes', [])}
    need(set(claims) <= actual_claims, 'deployment_claims')
    rss = obj('get', 'replicasets', '-l', 'app=radarr')['items']
    owners = {r['metadata']['uid'] for r in rss if any(o.get('uid') == DEP_UID and o.get('controller') for o in r['metadata'].get('ownerReferences', []))}
    pods = [p for p in obj('get', 'pods', '-l', 'app=radarr')['items'] if not p['metadata'].get('deletionTimestamp') and p['status'].get('phase') not in ['Succeeded', 'Failed']]
    need(len(pods) == 1, 'pod_count')
    pod = pods[0]
    need(any(o.get('uid') in owners and o.get('controller') for o in pod['metadata'].get('ownerReferences', [])), 'pod_owner')
    need(pod['status'].get('phase') == 'Running' and any(c['type'] == 'Ready' and c['status'] == 'True' for c in pod['status'].get('conditions', [])), 'pod_not_ready')
    statuses = pod['status'].get('containerStatuses', [])
    need(len(statuses) == 1 and statuses[0]['name'] == 'radarr' and statuses[0].get('ready') is True, 'container_not_ready')
    runtime = statuses[0].get('imageID', '').rsplit('@', 1)[-1]
    need(re.fullmatch(r'sha256:[0-9a-f]{64}', runtime), 'runtime_digest_missing')
    if mode != 'baseline':
        need(runtime in [NEW_RUNTIME, NEW.rsplit('@', 1)[1]], 'runtime_digest')
    service = obj('get', 'service', 'radarr')
    need(service['spec'].get('selector', {}).get('app') == 'radarr', 'service_selector')
    ip = ipaddress.ip_address(service['spec']['clusterIP'])
    need(ip.is_private and not ip.is_loopback and not ip.is_link_local, 'service_address')
    need(any(p['port'] == 7878 and p.get('targetPort') in [7878, 'p7878-tcp'] for p in service['spec']['ports']), 'service_port')
    slices = obj('get', 'endpointslices', '-l', 'kubernetes.io/service-name=radarr')['items']
    endpoints = [e for s in slices for e in s.get('endpoints', []) if e.get('conditions', {}).get('ready') is True]
    need(len(endpoints) == 1 and endpoints[0].get('targetRef', {}).get('uid') == pod['metadata']['uid'] and pod['status']['podIP'] in endpoints[0]['addresses'], 'service_endpoint_identity')
    return {'deployment_uid': DEP_UID, 'deployment_generation': md['generation'], 'claims': claims,
            'pod_uid': pod['metadata']['uid'], 'pod_name': pod['metadata']['name'],
            'restart_count': statuses[0].get('restartCount', 0), 'image': expected,
            'runtime_digest': runtime, 'service_uid': service['metadata']['uid'],
            'cluster_ip': str(ip)}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise Refused('unexpected_redirect')


class API:
    def __init__(self, state):
        xml = kube('exec', state['pod_name'], '-c', 'radarr', '--', 'head', '-c', '524289', '--', '/config/config.xml', limit=524288)
        root = ET.fromstring(xml)
        self.config = {e.tag: e.text or '' for e in root}
        key = self.config.get('ApiKey', '')
        need(bool(re.fullmatch(r'[a-zA-Z0-9]{20,128}', key)), 'config_api_key_invalid')
        base = self.config.get('UrlBase', '').rstrip('/')
        need(not base or re.fullmatch(r'/[A-Za-z0-9/_-]+', base), 'config_url_base_invalid')
        address = ipaddress.ip_address(state['cluster_ip'])
        self.base = 'http://' + ('[' + str(address) + ']' if address.version == 6 else str(address)) + ':7878' + base
        self.headers = {'X-Api-Key': key, 'Host': HOST, 'Accept': 'application/json'}
        self.client = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
        self.bytes = 0

    def get(self, path):
        need(path.startswith('/api/v3/') and '\n' not in path, 'unexpected_api_path')
        request = urllib.request.Request(self.base + path, headers=self.headers, method='GET')
        try:
            with self.client.open(request, timeout=20) as response:
                data = response.read(MAX_REPLY + 1)
                self.bytes += len(data)
                need(len(data) <= MAX_REPLY and self.bytes <= MAX_TOTAL, 'api_response_limit')
                need(response.status == 200, 'api_status')
                return json.loads(data)
        except urllib.error.HTTPError as error:
            raise Refused('api_http_' + str(error.code)) from None
        except (urllib.error.URLError, TimeoutError):
            raise Refused('api_connection_failed') from None

    def history(self):
        rows, total = [], None
        for page in range(1, 201):
            result = self.get('/api/v3/history?page=' + str(page) + '&pageSize=250&sortKey=id&sortDirection=ascending&includeMovie=false')
            count = result.get('totalRecords')
            need(type(count) is int and 0 <= count <= MAX_RECORDS and isinstance(result.get('records'), list), 'history_shape')
            if total is None:
                total = count
            need(count >= total, 'history_deleted_during_capture')
            rows.extend(result['records'])
            need(len(rows) <= MAX_RECORDS, 'history_record_limit')
            if len(rows) >= total:
                return rows[:total]
            need(result['records'], 'history_incomplete_page')
        raise Refused('history_page_limit')


MOVIE_FIELDS = ['id', 'tmdbId', 'path', 'qualityProfileId', 'monitored', 'minimumAvailability', 'rootFolderPath', 'tags', 'added', 'addOptions']
HISTORY_FIELDS = ['id', 'movieId', 'sourceTitle', 'languages', 'quality', 'date', 'downloadId', 'eventType', 'data']
CONFIG_FIELDS = ['ApiKey', 'AuthenticationMethod', 'AuthenticationRequired', 'UrlBase', 'Port', 'EnableSsl', 'SslPort', 'BindAddress']
QBITTORRENT_NEW_FIELDS = ['host', 'port', 'useSsl', 'urlBase', 'apiKey', 'username', 'password',
                         'movieCategory', 'movieImportedCategory', 'recentMoviePriority',
                         'olderMoviePriority', 'initialState', 'sequentialOrder', 'firstAndLast',
                         'contentLayout']


def project_qbittorrent_v644(values):
    """Reverse only the pinned upstream addition of an unused API-key UI field."""
    need(isinstance(values, list), 'download_client_list_shape')
    projected, mappings = [], []
    for value in values:
        need(isinstance(value, dict), 'download_client_shape')
        if value.get('implementation') != 'QBittorrent':
            projected.append(value)
            continue
        fields = value.get('fields')
        need(isinstance(fields, list) and len(fields) == 15 and all(isinstance(f, dict) for f in fields), 'qbittorrent_schema_field_count')
        need([f.get('name') for f in fields] == QBITTORRENT_NEW_FIELDS, 'qbittorrent_schema_field_names')
        need(all(type(f.get('order')) is int and f['order'] == i for i, f in enumerate(fields)), 'qbittorrent_schema_field_orders')
        # A nonempty/masked API key could change authentication semantics. Refuse it.
        need(fields[4].get('value') in (None, ''), 'qbittorrent_new_api_key_not_empty')
        old_fields = [dict(f) for i, f in enumerate(fields) if i != 4]
        for i, field in enumerate(old_fields):
            field['order'] = i
        projected.append(dict(value, fields=old_fields))
        mappings.append({'downloadclient_id': value.get('id'), 'mapping': 'qbittorrent-v6.4.4-unused-apiKey-field-and-order-only'})
    return projected, mappings


def capture(api, key, mode):
    def mac(value):
        return hmac.new(key, canonical(value), hashlib.sha256).hexdigest()

    def records(values, fields=None):
        need(isinstance(values, list) and len(values) <= MAX_RECORDS, 'record_list_shape')
        output = {}
        for value in values:
            need(isinstance(value, dict) and type(value.get('id')) is int and value['id'] >= 0, 'record_identity_shape')
            rid = str(value['id'])
            need(rid not in output, 'duplicate_record_identity')
            # Per-field fingerprints allow new response fields without ignoring old ones.
            selected = value if fields is None else {k: value[k] for k in fields if k in value}
            if 'tags' in selected:
                selected = dict(selected, tags=sorted(selected['tags']))
            output[rid] = {field: mac(content) for field, content in selected.items()}
        return output

    status = api.get('/api/v3/system/status')
    need(isinstance(status, dict) and status.get('appName') == 'Radarr', 'app_identity')
    version = status.get('version')
    expected = '6.0.4.10291' if mode == 'baseline' else '6.4.4.10685'
    need(version == expected, 'application_version')
    result = {'config_xml': {k: mac(api.config.get(k)) for k in CONFIG_FIELDS},
              'movie': records(api.get('/api/v3/movie'), MOVIE_FIELDS),
              'history': records(api.history(), HISTORY_FIELDS)}
    schema_mappings = []
    for endpoint in ['downloadclient', 'indexer', 'qualityprofile', 'tag', 'remotepathmapping', 'customformat']:
        values = api.get('/api/v3/' + endpoint)
        if endpoint == 'downloadclient' and mode != 'baseline':
            values, schema_mappings = project_qbittorrent_v644(values)
        result[endpoint] = records(values)
    roots = api.get('/api/v3/rootfolder')
    need(all(r.get('accessible') is True for r in roots), 'root_folder_inaccessible')
    result['rootfolder'] = records(roots, ['id', 'path'])
    health = api.get('/api/v3/health')
    need(isinstance(health, list), 'health_shape')
    # Health output may contain paths/remote names: record only issue categories and counts.
    categories = sorted(str(r.get('type', 'unknown')) for r in health)
    return {'version': version, 'fingerprints': result,
            'counts': {k: len(v) for k, v in result.items() if k != 'config_xml'},
            'health_categories': categories, 'api_bytes': api.bytes, 'schema_mappings': schema_mappings,
            'key_binding': mac('radarr-qualification-key-v1')}


def compare(before, after):
    need(before['key_binding'] == after['key_binding'], 'hmac_key_changed')
    failures = {}
    for table, rows in before['fingerprints'].items():
        current = after['fingerprints'].get(table, {})
        if table == 'config_xml':
            failures[table] = sum(current.get(k) != v for k, v in rows.items())
        else:
            failures[table] = sum(rid not in current or any(current[rid].get(field) != value for field, value in fields.items()) for rid, fields in rows.items())
    need(not any(failures.values()), 'preexisting_record_fingerprints_changed')
    return failures


def protected_file(path):
    need(path.is_absolute() and path.resolve() == path, 'protected_path_required')
    info = path.lstat()
    need(stat.S_ISREG(info.st_mode) and info.st_uid == os.getuid() and not info.st_mode & 0o077 and info.st_size <= MAX_TOTAL, 'protected_file_permissions')
    return json.loads(path.read_text())


def write_new(path, value):
    need(path.is_absolute() and path.resolve() == path and not path.is_symlink(), 'receipt_path')
    need(not any((parent / '.git').exists() for parent in path.parents), 'receipt_inside_git')
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    info = path.parent.lstat()
    need(stat.S_ISDIR(info.st_mode) and info.st_uid == os.getuid() and not info.st_mode & 0o077, 'receipt_parent_permissions')
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), 'w') as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write('\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['baseline', 'after', 'restart'])
    parser.add_argument('--baseline', type=Path)
    parser.add_argument('--prior-receipt', type=Path)
    parser.add_argument('--receipt', required=True, type=Path)
    args = parser.parse_args()
    os.umask(0o077)
    # Exactly one existing operator HMAC key; never create or persist key material here.
    raw = sys.stdin.buffer.read(66)
    need(re.fullmatch(b'[0-9a-f]{64}\n?', raw) is not None, 'stdin_requires_32_byte_hex_key')
    key = bytes.fromhex(raw.decode().strip())
    need((args.mode == 'baseline') == (args.baseline is None), 'baseline_argument')
    need((args.mode == 'restart') == (args.prior_receipt is not None), 'restart_argument')
    start = identity(args.mode)
    api = API(start)
    observation = capture(api, key, args.mode)
    finish = identity(args.mode)
    need(start == finish, 'runtime_changed_during_observation')
    checks = None
    baseline_sha = None
    if args.baseline:
        prior = protected_file(args.baseline)
        need(prior.get('mode') == 'baseline' and prior.get('schema_version') == 1, 'baseline_shape')
        need(prior['identity']['claims'] == start['claims'] and prior['identity']['service_uid'] == start['service_uid'], 'original_claim_or_service_changed')
        checks = compare(prior['observation'], observation)
        baseline_sha = hashlib.sha256(args.baseline.read_bytes()).hexdigest()
    if args.prior_receipt:
        prior = protected_file(args.prior_receipt)
        need(prior.get('mode') == 'after' and prior.get('schema_version') == 1 and prior.get('baseline_sha256') == baseline_sha, 'prior_receipt_shape')
        need(prior['identity']['claims'] == start['claims'] and prior['identity']['image'] == start['image'], 'restart_identity')
        need(prior['identity']['pod_uid'] != start['pod_uid'] or prior['identity']['restart_count'] < start['restart_count'], 'restart_not_observed')
        compare(prior['observation'], observation)
    # Private runtime names/IPs are used in memory but omitted from durable receipts.
    safe_identity = {k: v for k, v in start.items() if k not in ['pod_name', 'cluster_ip']}
    receipt = {'schema_version': 1, 'mode': args.mode, 'captured_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
               'identity': safe_identity, 'observation': observation, 'comparison_mismatches': checks,
               'baseline_sha256': baseline_sha, 'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
               'get_only': True, 'api_preservation_passed': args.mode != 'baseline',
               'sql_integrity_verified': False, 'user_password_table_verified': False,
               'integration_connection_tests_run': False, 'external_routes_verified': False,
               'full_acceptance_complete': False}
    write_new(args.receipt, receipt)
    print(json.dumps({'status': 'observed', 'mode': args.mode, 'version': observation['version'],
                      'counts': observation['counts'], 'api_preservation_passed': args.mode != 'baseline',
                      'full_acceptance_complete': False}))


if __name__ == '__main__':
    try:
        main()
    except Refused as error:
        print(json.dumps({'status': 'refused', 'reason': str(error)}))
        raise SystemExit(1)
    except Exception:
        print(json.dumps({'status': 'refused', 'reason': 'unexpected_operation_failed_raw_details_suppressed'}))
        raise SystemExit(1)
