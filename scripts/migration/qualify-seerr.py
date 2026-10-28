#!/usr/bin/env python3
"""Operator-only Seerr read checks. No writes to cluster/config/services."""
import argparse
import datetime
import hashlib
import hmac
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import sqlite3
import tarfile
import tempfile

MAX_ARCHIVE = 128 * 1024 * 1024
TABLES = ['user', 'media_request', 'media', 'season', 'season_request', 'issue', 'issue_comment', 'user_settings', 'user_push_subscription']
USER_COLUMNS = ['id', 'email', 'username', 'password', 'plexId', 'plexUsername', 'plexToken', 'permissions', 'avatar', 'createdAt', 'updatedAt']


def protected_output(path):
    if not path.is_absolute() or path.is_symlink():
        raise ValueError('output-path')
    resolved = path.resolve()
    parent = resolved.parent
    if not parent.is_dir() or resolved.exists() or any((p / '.git').exists() for p in [parent, *parent.parents]):
        raise ValueError('output-path')
    if os.name != 'nt' and (parent.stat().st_uid != os.getuid() or parent.stat().st_mode & 0o077):
        raise ValueError('output-directory-permissions')
    return resolved


def write_private(path, data):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w', encoding='utf-8') as out:
        json.dump(data, out, indent=2, ensure_ascii=False)
        out.write('\n')


def stdin_key():
    raw = sys.stdin.buffer.read(4097)
    key = raw.decode('utf-8').rstrip('\r\n')
    if len(raw) > 4096 or len(key) < 32 or '\n' in key or '\r' in key:
        raise ValueError('key-stdin-required')
    return key


def compact(value):
    # Shared domain avoids Python/ECMAScript number/string serialization drift.
    def validate(v):
        if v is None or isinstance(v, bool):
            return
        if isinstance(v, int) and abs(v) <= 9007199254740991:
            return
        if isinstance(v, str):
            v.encode('utf-8')
            return
        if isinstance(v, list):
            for item in v:
                validate(item)
            return
        if isinstance(v, dict):
            for k, item in v.items():
                if not isinstance(k, str):
                    raise ValueError('canonical-domain')
                validate(k)
                validate(item)
            return
        raise ValueError('canonical-domain')
    validate(value)
    return json.dumps(value, separators=(',', ':'), ensure_ascii=False).encode('utf-8')


def cold_baseline(argv):
    ap = argparse.ArgumentParser(description='Derive HMAC metadata from the verified encrypted cold archive; no live calls.')
    ap.add_argument('--archive', type=Path, required=True)
    ap.add_argument('--verified-receipt', type=Path, required=True)
    ap.add_argument('--age', type=Path, required=True)
    ap.add_argument('--identity', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    ap.add_argument('--already-seerr', action='store_true', help='Fresh full cold snapshot of the already-migrated Seerr instance; no legacy data transformations')
    args = ap.parse_args(argv)
    output = protected_output(args.output)
    if os.name != 'posix' or not Path('/dev/shm').is_dir() or not any(line.split()[1:3] == ['/dev/shm', 'tmpfs'] for line in Path('/proc/mounts').read_text().splitlines()):
        raise ValueError('protected-ram-required')
    key = stdin_key().encode('utf-8')
    digest = lambda value: hmac.new(key, compact(value), hashlib.sha256).hexdigest()
    receipt = json.loads(args.verified_receipt.read_bytes())
    if args.already_seerr:
        if not (receipt.get('status') == 'completed' and receipt.get('application') == 'seerr' and receipt.get('generation') == 'upstream-seerr-20261025' and receipt.get('cold_archive_verified') is True and receipt.get('temporary_pod_deleted') is True):
            raise ValueError('archive-receipt')
        archive_sha = receipt['archive_sha256']
    else:
        if not all(receipt.get(k) is True for k in ['authenticatedDecryption', 'completeArchiveRead']) or receipt.get('sqliteQuickCheck') != 'ok':
            raise ValueError('archive-receipt')
        archive_sha = receipt['archiveSHA256']
    if args.archive.stat().st_size > MAX_ARCHIVE or hashlib.sha256(args.archive.read_bytes()).hexdigest() != archive_sha:
        raise ValueError('archive-binding')
    process = subprocess.Popen([str(args.age), '-d', '-i', str(args.identity), str(args.archive)], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    try:
        blob = process.stdout.read(MAX_ARCHIVE + 1)
        if len(blob) > MAX_ARCHIVE:
            raise ValueError('archive-size')
        if process.wait(timeout=120) != 0:
            raise ValueError('archive-authentication')
    finally:
        process.stdout.close()
        if process.poll() is None:
            process.kill()
            process.wait()
    files = {}
    total = 0
    with tarfile.open(fileobj=io.BytesIO(blob), mode='r:' if args.already_seerr else 'r:gz') as archive:
        for member in archive:
            path = member.name.removeprefix('./')
            if args.already_seerr:
                path = path.removeprefix('data-0/')
            if member.name.startswith('/') or '..' in Path(path).parts or member.size < 0:
                raise ValueError('archive-path')
            total += member.size
            if total > MAX_ARCHIVE:
                raise ValueError('archive-size')
            if path in ['settings.json', 'db/db.sqlite3', 'db/db.sqlite3-wal', 'db/db.sqlite3-shm']:
                if not member.isfile() or path in files:
                    raise ValueError('archive-member')
                files[path] = archive.extractfile(member).read()
    if 'settings.json' not in files or 'db/db.sqlite3' not in files:
        raise ValueError('archive-members-missing')
    result = {'format': 1, 'upstreamSource': '564bfb08b54caa374bddaf820abfd226e5e69151',
              'archiveSHA256': archive_sha, 'sqliteQuickCheck': 'ok', 'counts': {},
              'historyPreservation': {}, 'settingsPreservation': {}, 'settingsAbsent': [],
              'transformations': [], 'archiveDerived': True}
    def ident(name):
        if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', name):
            raise ValueError('schema')
        return '"' + name + '"'
    with tempfile.TemporaryDirectory(prefix='seerr-compare-', dir='/dev/shm') as folder:
        folder = Path(folder)
        folder.chmod(0o700)
        for name, data in files.items():
            if name.startswith('db/'):
                dest = folder / Path(name).name
                dest.write_bytes(data)
                dest.chmod(0o600)
        connection = sqlite3.connect(str(folder / 'db.sqlite3'))
        connection.row_factory = sqlite3.Row
        try:
            if [tuple(r) for r in connection.execute('PRAGMA quick_check')] != [('ok',)]:
                raise ValueError('archive-sqlite')
            for table in TABLES:
                columns = [r['name'] for r in connection.execute('PRAGMA table_info(' + ident(table) + ')')]
                if 'id' not in columns:
                    raise ValueError('archive-schema')
                rows = [dict(r) for r in connection.execute('SELECT ' + ','.join(map(ident, columns)) + ' FROM ' + ident(table) + ' ORDER BY id')]
                result['counts'][table] = len(rows)
                if table in receipt.get('counts', {}) and receipt['counts'][table] != len(rows):
                    raise ValueError('archive-count-binding')
                if table == 'user':
                    users = [{c: r[c] for c in USER_COLUMNS} for r in rows]
                    result['userPreservation'] = {'columns': USER_COLUMNS, 'count': len(users), 'ids': [r['id'] for r in users], 'hmacSHA256': digest(users), 'perColumn': {c: digest([r[c] for r in users]) for c in USER_COLUMNS}}
                    continue
                # Exact vendor transformations only. Never infer from new state.
                if not args.already_seerr and table in ['media', 'season']:
                    for c in ['status', 'status4k']:
                        changed = 0
                        for r in rows:
                            if r[c] == 6:
                                r[c] = 7
                                changed += 1
                        result['transformations'].append({'table': table, 'column': c, 'from': 6, 'to': 7, 'rows': changed})
                if not args.already_seerr and table == 'user_settings':
                    if 'region' in columns:
                        if any(r['region'] not in (None, '') for r in rows):
                            raise ValueError('populated-dropped-user-region')
                        columns.remove('region')
                        result['transformations'].append({'table': table, 'column': 'region', 'removedOnlyNullOrEmpty': True})
                    if 'discordId' in columns:
                        columns[columns.index('discordId')] = 'discordIds'
                        for r in rows:
                            v = r['discordId']
                            r['discordIds'] = '["' + str(v) + '"]' if v not in (None, '') else None
                        result['transformations'].append({'table': table, 'column': 'discordId', 'renamed': 'discordIds', 'sqlSingleItemArray': True})
                    if 'notificationTypes' in columns:
                        for r in rows:
                            if isinstance(r['notificationTypes'], int):
                                r['notificationTypes'] = str(r['notificationTypes'])
                result['historyPreservation'][table] = {'columns': columns, 'ids': [r['id'] for r in rows],
                    'perColumn': {c: digest([r[c] for r in rows]) for c in columns},
                    'perRow': {str(r['id']): digest([r[c] for c in columns]) for r in rows}}
        finally:
            connection.close()
    settings = json.loads(files['settings.json'])
    if args.already_seerr:
        if settings.get('main', {}).get('mediaServerType') != 1 or settings.get('public', {}).get('initialized') is not True:
            raise ValueError('not-initialized-seerr-baseline')
        result['alreadySeerrBaseline'] = True
    else:
        main = settings['main']
        if main.get('mediaServerType'):
            raise ValueError('not-overseerr-baseline')
        main['mediaServerType'] = 1
        if main.get('applicationTitle') == 'Overseerr':
            main['applicationTitle'] = 'Seerr'
        email_options = settings['notifications']['agents']['email']['options']
        if email_options.get('senderName') == 'Overseerr':
            email_options['senderName'] = 'Seerr'
        if not ('discoverRegion' in main and 'streamingRegion' in main):
            region = main.pop('region', None)
            main['discoverRegion'] = region if region else ''
            main['streamingRegion'] = region if region else 'US'
            result['settingsAbsent'].append('/main/region')
        if 'network' not in settings:
            settings['network'] = {k: main.pop(k, default) for k, default in [('csrfProtection', False), ('trustProxy', False), ('forceIpv4First', False), ('proxy', {'enabled': False, 'hostname': '', 'port': 8080, 'useSsl': False, 'user': '', 'password': '', 'bypassFilter': '', 'bypassLocalAddresses': True})]}
            result['settingsAbsent'].extend('/main/' + k for k in ['csrfProtection', 'trustProxy', 'forceIpv4First', 'proxy'])
        agents = settings['notifications']['agents']
        if 'lunasea' in agents:
            if agents['lunasea'].get('enabled'):
                raise ValueError('enabled-removed-lunasea')
            result['removedLunaSeaHMAC'] = digest(agents.pop('lunasea'))
            result['settingsAbsent'].append('/notifications/agents/lunasea')
        for old, new in [('hideBlacklisted', 'hideBlocklisted'), ('blacklistedTags', 'blocklistedTags'), ('blacklistedTagsLimit', 'blocklistedTagsLimit')]:
            if old in main:
                main[new] = main.pop(old)
                result['settingsAbsent'].append('/main/' + old)
        if 'process-blacklisted-tags' in settings.get('jobs', {}):
            settings['jobs']['process-blocklisted-tags'] = settings['jobs'].pop('process-blacklisted-tags')
            result['settingsAbsent'].append('/jobs/process-blacklisted-tags')
    def leaves(value, pointer=''):
        if isinstance(value, dict) and value:
            for name, item in value.items():
                leaves(item, pointer + '/' + name.replace('~', '~0').replace('/', '~1'))
        elif isinstance(value, list) and value:
            result['settingsArrayLengths'][pointer] = len(value)
            for i, item in enumerate(value):
                leaves(item, pointer + '/' + str(i))
        else:
            result['settingsPreservation'][pointer] = digest(value)
    # Migration list is additive; compare retained markers separately, not by index.
    result['settingsPriorMigrations'] = settings.pop('migrations', [])
    result['settingsArrayLengths'] = {}
    leaves(settings)
    write_private(output, result)
    print(json.dumps({'archiveDerived': True, 'tables': len(result['historyPreservation']), 'settingsLeaves': len(result['settingsPreservation']), 'baselineSHA256': hashlib.sha256(output.read_bytes()).hexdigest()}))
    return 0


def run(argv, body=None, timeout=45):
    try:
        p = subprocess.run(argv, input=body, stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE, timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired):
        raise ValueError('transport-failed') from None
    if len(p.stdout) > 2 * 1024 * 1024:
        raise ValueError('response-limit')
    return p


def main():
    if len(sys.argv) > 1 and sys.argv[1] == 'cold-baseline':
        return cold_baseline(sys.argv[2:])
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--pod', required=True)
    ap.add_argument('--pod-uid', required=True)
    ap.add_argument('--deployment-uid', required=True)
    ap.add_argument('--pvc-uid', required=True)
    ap.add_argument('--expected-image', required=True)
    ap.add_argument('--baseline', type=Path, required=True)
    ap.add_argument('--receipt', type=Path, required=True)
    ap.add_argument('--prior-receipt', type=Path)
    ap.add_argument('--runtime-scan-proof', type=Path)
    args = ap.parse_args()
    if not re.fullmatch(r'[a-z0-9][a-z0-9._:/-]*@sha256:[a-f0-9]{64}', args.expected_image):
        raise ValueError('image-required')
    receipt = protected_output(args.receipt)
    baseline_bytes = args.baseline.read_bytes()
    baseline = json.loads(baseline_bytes)
    key = stdin_key()
    payload = Path(__file__).with_suffix('.cjs').read_bytes()
    source = payload.decode('utf-8')

    def kube(*words):
        p = run(['kubectl', '-n', 'plex', *words, '-o', 'json'])
        if p.returncode:
            raise ValueError('kubernetes-read-failed')
        return json.loads(p.stdout)

    def owner(obj, kind):
        refs = [r for r in obj['metadata'].get('ownerReferences', []) if r.get('controller') and r['kind'] == kind]
        if len(refs) != 1:
            raise ValueError('owner-mismatch')
        return refs[0]

    def fence():
        namespace_pods = kube('get', 'pods')['items']
        pods = [p for p in namespace_pods if p['metadata'].get('labels', {}).get('app') == 'overseerr']
        if len(pods) != 1:
            raise ValueError('writer-overlap')
        pod = pods[0]
        holders = [p for p in namespace_pods if any(v.get('persistentVolumeClaim', {}).get('claimName') == 'overseerr-data-0' for v in p['spec'].get('volumes', []))]
        if len(holders) != 1 or holders[0]['metadata']['uid'] != args.pod_uid:
            raise ValueError('claim-holder-overlap')
        if pod['metadata']['name'] != args.pod or pod['metadata']['uid'] != args.pod_uid or pod['metadata'].get('deletionTimestamp') or pod.get('status', {}).get('phase') != 'Running':
            raise ValueError('pod-mismatch')
        ready = [c for c in pod['status'].get('conditions', []) if c['type'] == 'Ready']
        if len(ready) != 1 or ready[0]['status'] != 'True':
            raise ValueError('pod-not-ready')
        rsref = owner(pod, 'ReplicaSet')
        rs = kube('get', 'replicaset', rsref['name'])
        if rs['metadata']['uid'] != rsref['uid']:
            raise ValueError('replicaset-mismatch')
        depref = owner(rs, 'Deployment')
        dep = kube('get', 'deployment', 'overseerr')
        if depref['name'] != 'overseerr' or depref['uid'] != args.deployment_uid or dep['metadata']['uid'] != args.deployment_uid or dep['spec']['replicas'] != 1 or dep.get('status', {}).get('replicas') != 1 or dep.get('status', {}).get('updatedReplicas') != 1 or dep.get('status', {}).get('availableReplicas') != 1 or dep['status'].get('observedGeneration', 0) < dep['metadata']['generation']:
            raise ValueError('deployment-mismatch')
        containers = pod['spec']['containers']
        if len(containers) != 1 or containers[0]['image'] != args.expected_image:
            raise ValueError('spec-image-mismatch')
        container = containers[0]
        if dep['spec']['template']['spec']['containers'][0]['image'] != args.expected_image:
            raise ValueError('deployment-image-mismatch')
        statuses = pod['status'].get('containerStatuses', [])
        if len(statuses) != 1 or statuses[0]['name'] != container['name'] or not statuses[0].get('ready') or not statuses[0].get('state', {}).get('running') or not statuses[0].get('imageID', '').endswith('@' + args.expected_image.split('@')[1]):
            raise ValueError('runtime-image-mismatch')
        mounts = [m for m in container.get('volumeMounts', []) if m['mountPath'] == '/app/config']
        if len(mounts) != 1 or mounts[0].get('subPath') or mounts[0].get('subPathExpr'):
            raise ValueError('config-mount-mismatch')
        volumes = [v for v in pod['spec']['volumes'] if v['name'] == mounts[0]['name']]
        if len(volumes) != 1 or volumes[0].get('persistentVolumeClaim', {}).get('claimName') != 'overseerr-data-0':
            raise ValueError('config-claim-mismatch')
        pvc = kube('get', 'pvc', 'overseerr-data-0')
        if pvc['metadata']['uid'] != args.pvc_uid or pvc['status']['phase'] != 'Bound':
            raise ValueError('pvc-mismatch')
        return {'pod': args.pod, 'podUID': args.pod_uid, 'deploymentUID': args.deployment_uid,
                'pvcUID': args.pvc_uid, 'volumeName': pvc['spec']['volumeName'],
                'container': container['name'], 'restartCount': statuses[0]['restartCount'],
                'startedAt': statuses[0]['state']['running']['startedAt'], 'image': args.expected_image,
                'imageID': statuses[0]['imageID']}

    before = fence()
    runtime_proof = None
    if args.runtime_scan_proof:
        path = args.runtime_scan_proof
        if not path.is_absolute() or path.resolve() != path or path.is_symlink():
            raise ValueError('runtime-proof-path')
        info = path.stat()
        if info.st_uid != os.getuid() or info.st_mode & 0o077 or info.st_size > 1024 * 1024:
            raise ValueError('runtime-proof-permissions')
        proof_bytes = path.read_bytes()
        proof = json.loads(proof_bytes)
        first_path = path.parent / 'after.json'
        first_bytes = first_path.read_bytes()
        first = json.loads(first_bytes)
        pointers = ['/plex/libraries/0/lastScan', '/plex/libraries/1/lastScan']
        baseline_sha = hashlib.sha256(baseline_bytes).hexdigest()
        if proof.get('format') != 1 or proof.get('upstreamSource') != baseline.get('upstreamSource') or proof.get('scannerSourceSHA256') != '823baac8e20d471e3a1519c2855b3cdd5107820d221aa000b5cdf5c7dcdb7fcf':
            raise ValueError('runtime-proof-source')
        if proof.get('baselineSHA256') != baseline_sha or first.get('baselineSHA256') != baseline_sha or proof.get('archiveSHA256') != baseline.get('archiveSHA256') or first.get('archiveSHA256') != baseline.get('archiveSHA256'):
            raise ValueError('runtime-proof-archive-binding')
        if proof.get('firstPreservedReceiptSHA256') != hashlib.sha256(first_bytes).hexdigest() or not proof.get('archiveAuthenticatedCompleteRead') or not proof.get('allOriginalSettingsPreservedBeforeRuntimeScans'):
            raise ValueError('runtime-proof-first-receipt-binding')
        literal = first.get('settings', {}).get('preservation', {})
        if set(literal) != set(baseline.get('settingsPreservation', {})) or len(literal) != 143 or not all(v is True for v in literal.values()) or not all(first['settings'].get(k) is True for k in ['absenceMatches', 'arrayLengthsMatch', 'priorMigrationsRetained']):
            raise ValueError('initial-literal-settings-not-preserved')
        if any(first['identity'][k] != before[k] or proof['identity'][k] != before[k] for k in ['deploymentUID', 'pvcUID', 'volumeName', 'image']):
            raise ValueError('runtime-proof-identity')
        advances = proof.get('advances', [])
        if len(advances) != 2 or {row.get('pointer') for row in advances} != set(pointers):
            raise ValueError('runtime-proof-exact-pointers')
        old_values = {row['pointer']: row['oldTimestamp'] for row in advances}
        for pointer, value in old_values.items():
            if type(value) is not int or not 0 <= value <= 9007199254740991 or hmac.new(key.encode('utf-8'), compact(value), hashlib.sha256).hexdigest() != baseline['settingsPreservation'][pointer]:
                raise ValueError('runtime-proof-original-value-hmac')
        first_ms = int(datetime.datetime.fromisoformat(first['timestamp']).timestamp() * 1000)
        runtime_proof = {'format': 1, 'oldValues': old_values, 'firstPreservedReceiptMS': first_ms,
                         'proofSHA256': hashlib.sha256(proof_bytes).hexdigest(),
                         'firstPreservedReceiptSHA256': hashlib.sha256(first_bytes).hexdigest(),
                         'baselineSHA256': baseline_sha, 'archiveSHA256': baseline['archiveSHA256']}
    if args.prior_receipt:
        prior = json.loads(args.prior_receipt.read_bytes())
        old = prior['identity']
        if not prior.get('helperChecksPassed') or any(old[k] != before[k] for k in ['deploymentUID', 'pvcUID', 'volumeName', 'image']):
            raise ValueError('restart-baseline-mismatch')
        if old['podUID'] == before['podUID'] and before['restartCount'] <= old['restartCount']:
            raise ValueError('restart-not-observed')
    request_data = {'key': key, 'baseline': baseline}
    if runtime_proof is not None:
        request_data['runtimeScanProof'] = runtime_proof
    request = json.dumps(request_data, separators=(',', ':'), ensure_ascii=False).encode()
    p = run(['kubectl', '-n', 'plex', 'exec', '-i', args.pod, '-c', before['container'], '--',
             'node', '-e', source], body=request, timeout=240)
    key = None
    request = None
    after = fence()
    if before != after:
        raise ValueError('identity-changed')
    report = json.loads(p.stdout)
    if p.returncode not in (0, 1, 3) or not isinstance(report, dict):
        raise ValueError('payload-failed')
    report.update(identity=before, baselineSHA256=hashlib.sha256(baseline_bytes).hexdigest(), archiveSHA256=baseline.get('archiveSHA256'),
                  payloadSHA256=hashlib.sha256(payload).hexdigest(), operatorSHA256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                  restartObserved=bool(args.prior_receipt), exitCode=p.returncode)
    write_private(receipt, report)
    print(json.dumps({'helperChecksPassed': report.get('helperChecksPassed', False),
                      'fullPreservation': report.get('fullPreservation', False), 'acceptanceComplete': False,
                      'restartObserved': bool(args.prior_receipt), 'exitCode': p.returncode}))
    return p.returncode


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (ValueError, KeyError, TypeError, OSError, UnicodeError, sqlite3.Error, tarfile.TarError, subprocess.TimeoutExpired):
        print(json.dumps({'failed': True, 'error': 'qualification-refused', 'acceptanceComplete': False}))
        sys.exit(1)
