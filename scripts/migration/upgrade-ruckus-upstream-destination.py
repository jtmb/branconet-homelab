#!/usr/bin/env python3
"""Upgrade only the separately restored Ruckus claim while Flux writers are cold.

Preparation requires a fresh complete authenticated source and NAS receipt.
No operation scales production, mounts its original claim, or resets a password.
"""
import argparse
import ast
import datetime
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import tarfile
import uuid

F = Path('/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025')
OUT = F / 'upstream-ruckusdb-20261026'
SOURCE = F / 'control-source/upstream-ruckusdb-20261026'
SQL_SOURCE = SOURCE / 'reviewed-source/scripts/migration/qualify-ruckusdb.py'
spec = importlib.util.spec_from_file_location('qualified_trial', SOURCE / 'qualify-ruckus-upstream-copy-r7.py')
trial = importlib.util.module_from_spec(spec)
spec.loader.exec_module(trial)
DESTINATION = 'ruckus-db-upstream-20261026'
ACTIVE = '/copy/data-0/security-data-20261025/data-0'


def snapshot_source():
    # Keep every keyed row token for an original-row multiset check after the
    # bot resumes; ordinary new log rows must not hide missing original rows.
    needle = "   tables[q.mac(key,'table-name',(schema+'\\0'+name).encode())]=entry"
    assert trial.SNAPSHOT.count(needle) == 1
    source = trial.SNAPSHOT.replace(needle, "   if kind=='BASE TABLE':entry['rowHMACs']=sorted(q.mac(key,'row',row)for row in rows)\n" + needle)
    source = source.replace("  return s.encode()", "  s=re.sub(r' AUTO_INCREMENT=\\d+','',s)\n  return s.encode()")
    ast.parse(source)
    return source

GUARD = r'''
def guard():
 p=json.loads(call(['get','pod',state['podName'],'-o','json']));assert p['metadata']['uid']==state['podUID']and p['status']['phase']=='Running'and not p['metadata'].get('deletionTimestamp');assert hashlib.sha256(json.dumps(p['spec'],sort_keys=True).encode()).hexdigest()==state['podSpecSHA256']
 assert p['spec']['automountServiceAccountToken']is False and p['spec']['nodeName']=='workernode2'
 for name,duid,huid in [('ruckus-db',q.IDS['deployment'],q.IDS['release']),('ruckus-bot',q.IDS['bot'],q.IDS['bot_release'])]:
  d=q.get('deployment',name);h=q.get('helmrelease',name,'flux-system');assert d['metadata']['uid']==duid and h['metadata']['uid']==huid;assert d['spec']['replicas']==h['spec']['values']['replicaCount']==0 and not h['spec'].get('suspend',False)
  assert d['status'].get('observedGeneration')==d['metadata']['generation']and all(d['status'].get(k,0)==0 for k in['replicas','readyReplicas','availableReplicas','updatedReplicas']);assert any(c['type']=='Ready'and c['status']=='True'for c in h['status'].get('conditions',[]))
  if name=='ruckus-db':assert d['spec']['template']['spec']['containers'][0]['image']==q.NEW and d['spec']['template']['spec']['volumes'][0]['persistentVolumeClaim']['claimName']=='ruckus-db-data-0'
 original=q.get('pvc','ruckus-db-data-0');assert original['metadata']['uid']==q.IDS['pvc']and original['status']['phase']=='Bound'
 claim=q.get('pvc',state['claim']);assert claim['metadata']['uid']==state['claimUID']and claim['status']['phase']=='Bound'and claim['spec']['resources']['requests']['storage']=='4Gi'
 pv=q.get('pv',claim['spec']['volumeName'],None);assert pv['metadata']['uid']==state['pvUID']and pv['spec']['claimRef']['uid']==state['claimUID']and pv['spec']['csi']['driver']=='driver.longhorn.io'
 for pod in q.get('pods')['items']:
  claims=[v.get('persistentVolumeClaim',{}).get('claimName')for v in pod['spec'].get('volumes',[])];active=pod['status'].get('phase')not in['Succeeded','Failed']
  if active and'ruckus-db-data-0'in claims:raise AssertionError('source_claim_still_active')
  if active and state['claim']in claims:assert pod['metadata']['uid']==state['podUID']
 policies=json.loads(call(['get','networkpolicies','-o','json']))['items'];assert len(policies)==1 and policies[0]['metadata']['uid']==state['policyUID'];ps=policies[0]['spec'];assert {**ps,'ingress':ps.get('ingress',[]),'egress':ps.get('egress',[])}=={'podSelector':{'matchLabels':state['labels']},'policyTypes':['Ingress','Egress'],'ingress':[],'egress':[]}
 assert json.loads(call(['get','namespace',ns,'-o','json']))['metadata']['uid']==state['namespaceUID']
 return p
'''


def program():
    code = trial.NODE
    start = code.index('def guard():')
    end = code.index('\ntry:\n p=guard()', start)
    code = code[:start] + GUARD.strip() + code[end:]
    code = code.replace("'qualifier'", "state['podName']")
    needle = "'/copy/'+('data-0/data-0'if side=='old'else'slow-copy/data-0/data-0')"
    assert code.count(needle) == 1
    code = code.replace(needle, repr(ACTIVE))
    code = code.replace("other=['old']if side=='old'else['mid','new']", "other=['old','mid','new']")
    code = code.replace("if not r.get('admin',True):", "if not r.get('admin',True)and not r.get('upgradeReadinessOnly'):")
    # The obsolete copy-slow action is unreachable through this controller.
    ast.parse(code)
    return code


def key():
    return (F / 'acceptance-ruckus-20261025/hmac-key.hex').read_text().strip()


def request(state, action, side=None, normal=False):
    return {'state': state, 'action': action, 'side': side, 'admin': not normal,
            'key': key(), 'sqlSource': SQL_SOURCE.read_text(), 'snapshotSource': snapshot_source(),
            'serverSettings': json.loads((OUT / 'live-server-settings.json').read_text())['settings']}


def kube(args, data=None, timeout=90):
    result = subprocess.run(trial.SSH + [shlex.join(['kubectl', '--request-timeout=30s', '-n', 'ruckus', *args])],
                            input=data, capture_output=True, timeout=timeout)
    assert result.returncode == 0, 'kubernetes_operation_failed_raw_details_suppressed'
    return result.stdout


def prepare(archive_receipt):
    assert not (OUT / 'final-state.json').exists()
    assert json.loads((OUT / 'trial-acceptance.json').read_text())['passed']
    assert archive_receipt.resolve() == archive_receipt and archive_receipt.is_relative_to(OUT / 'cold')
    cold = json.loads(archive_receipt.read_text())
    assert cold['status'] == 'completed' and cold['generation'] == 'upstream-ruckusdb-20261026'
    assert cold['cold_archive_verified'] and cold['temporary_pod_deleted'] and cold['claim_uid'] == '2f604004-b45f-4061-bdc4-43f5ca2f7fd8'
    assert cold['file_bytes'] <= 1024**3 and cold['original_image'] == trial.OLD
    age = Path('/home/brajam/.local/share/branconet-migration/bin/age')
    assert hashlib.sha256(age.read_bytes()).hexdigest() == 'eb7dd1b518f0a307c99cd97782623c5321da049154b04acd2d98d21aa7bc9b2c'
    archive = Path(cold['archive_path'])
    assert archive.is_relative_to(OUT / 'cold') and hashlib.file_digest(archive.open('rb'), 'sha256').hexdigest() == cold['archive_sha256']
    nas = json.loads((F / 'operator-control/smb-ruckusdb-upstream-state-copy-status.json').read_text())
    assert len(nas['files']) == 1 and nas['files'][0]['completeAgeAuthentication']
    assert nas['files'][0]['sourceSHA256'] == nas['files'][0]['destinationSHA256'] == cold['archive_sha256']
    for name in ['ruckus-db', 'ruckus-bot']:
        d = json.loads(kube(['get', 'deployment', name, '-o', 'json']))
        h = json.loads(kube(['get', 'helmrelease', name, '-n', 'flux-system', '-o', 'json']))
        assert d['spec']['replicas'] == h['spec']['values']['replicaCount'] == 0
        assert all(d['status'].get(k, 0) == 0 for k in ['replicas', 'readyReplicas', 'availableReplicas', 'updatedReplicas'])
    claim = json.loads(kube(['get', 'pvc', DESTINATION, '-o', 'json']))
    pv = json.loads(kube(['get', 'pv', claim['spec']['volumeName'], '-o', 'json']))
    assert claim['status']['phase'] == 'Bound' and claim['spec']['resources']['requests']['storage'] == '4Gi'
    assert pv['spec']['claimRef']['uid'] == claim['metadata']['uid'] and pv['spec']['csi']['driver'] == 'driver.longhorn.io'
    assert not json.loads(kube(['get', 'networkpolicies', '-o', 'json']))['items']
    ns = json.loads(kube(['get', 'namespace', 'ruckus', '-o', 'json']))
    run = uuid.uuid4().hex[:12]
    name = 'mysql-upstream-final-' + run
    labels = {'mysql-upstream-final': run}
    owned = []
    def create(obj):
        actual = json.loads(kube(['create', '-f', '-', '-o', 'json'], json.dumps(obj).encode()))
        owned.append({'kind': actual['kind'], 'name': name, 'uid': actual['metadata']['uid']})
        return actual
    policy = create({'apiVersion': 'networking.k8s.io/v1', 'kind': 'NetworkPolicy', 'metadata': {'name': name, 'namespace': 'ruckus'},
                     'spec': {'podSelector': {'matchLabels': labels}, 'policyTypes': ['Ingress', 'Egress'], 'ingress': [], 'egress': []}})
    containers = []
    for side, image in [('old', trial.OLD), ('mid', trial.MID), ('new', trial.NEW), ('reader', trial.READER)]:
        reader = side == 'reader'
        mounts = [{'name': 'destination', 'mountPath': '/copies/new' if reader else '/copy'}]
        if not reader:
            mounts.append({'name': side + '-run', 'mountPath': '/run/qual'})
        containers.append({'name': side, 'image': image, 'imagePullPolicy': 'IfNotPresent',
            'command': ['python3', '-B', '-c', 'import time;time.sleep(3600)'] if reader else ['/bin/sh', '-c', 'exec sleep 3600'],
            'resources': {'requests': {'cpu': '25m', 'memory': '32Mi'}, 'limits': {'cpu': '1000m', 'memory': '2048Mi' if reader else '1536Mi'}},
            'securityContext': {'runAsUser': 0 if reader else 999, 'runAsGroup': 0 if reader else 65534,
                'allowPrivilegeEscalation': False, 'readOnlyRootFilesystem': True,
                'capabilities': {'drop': ['ALL'], **({'add': ['CHOWN', 'FOWNER', 'DAC_OVERRIDE']} if reader else {})}},
            'volumeMounts': mounts})
    pod = create({'apiVersion': 'v1', 'kind': 'Pod', 'metadata': {'name': name, 'namespace': 'ruckus', 'labels': labels},
                  'spec': {'nodeName': 'workernode2', 'restartPolicy': 'Never', 'activeDeadlineSeconds': 3600,
                           'automountServiceAccountToken': False, 'enableServiceLinks': False,
                           'securityContext': {'fsGroup': 65534, 'supplementalGroupsPolicy': 'Strict', 'seccompProfile': {'type': 'RuntimeDefault'}},
                           'containers': containers,
                           'volumes': [{'name': 'destination', 'persistentVolumeClaim': {'claimName': DESTINATION}}] +
                                      [{'name': side + '-run', 'emptyDir': {'medium': 'Memory', 'sizeLimit': '64Mi'}} for side in ['old', 'mid', 'new']]}})
    state = {'namespace': 'ruckus', 'namespaceUID': ns['metadata']['uid'], 'podName': name, 'podUID': pod['metadata']['uid'],
             'podSpecSHA256': hashlib.sha256(json.dumps(pod['spec'], sort_keys=True).encode()).hexdigest(),
             'policyUID': policy['metadata']['uid'], 'labels': labels, 'owned': owned,
             'claim': DESTINATION, 'claimUID': claim['metadata']['uid'], 'pvUID': pv['metadata']['uid'],
             'freshArchiveReceipt': str(archive_receipt), 'freshArchiveSHA256': cold['archive_sha256'],
             'activeDatadir': ACTIVE, 'originalClaimMounted': False}
    (OUT / 'final-state.json').write_text(json.dumps(state, indent=2) + '\n')
    kube(['wait', 'pod/' + name, '--for=condition=Ready', '--timeout=180s'], timeout=200)
    assert trial.remote(program(), request(state, 'inspect'))['passed']
    # Reuse the manifest-aware extractor. Only this freshly provisioned claim is
    # writable. Its filesystem lost+found is retained; the data-0 target is new.
    restore = (SOURCE / 'trial-restore-r2.py').read_text()
    restore = restore.replace("and not list(root.iterdir())", "and not (root/'data-0').exists() and set(p.name for p in root.iterdir()) <= {'lost+found'}")
    restore = restore.replace("name=='data-0/data-0/mysql.sock'", "name in ['data-0/mysql.sock','data-0/security-data-20261025/data-0/mysql.sock']")
    restore = restore.replace('384*1024**2', '1024**3')
    ast.parse(restore)
    saved = SOURCE / 'fresh-final-restore.py'
    assert not saved.exists()
    saved.write_text(restore)
    decryptor = subprocess.Popen([str(age), '-d', '-i', '/home/brajam/.ssh/id_ed25519', str(archive)], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    target = subprocess.Popen(trial.SSH + [shlex.join(['kubectl', '-n', 'ruckus', 'exec', '-i', name, '-c', 'reader', '--',
                              'python3', '-B', '-c', restore, 'new'])], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    try:
        target.stdin.write((cold['manifest_sha256'] + '\n').encode())
        for block in iter(lambda: decryptor.stdout.read(1024**2), b''):
            target.stdin.write(block)
        target.stdin.close()
        raw = target.stdout.read(65537)
        assert decryptor.wait(timeout=30) == target.wait(timeout=30) == 0
        restored = json.loads(raw)
        assert restored['restored'] and restored['file_bytes'] == cold['file_bytes']
        assert trial.remote(program(), request(state, 'inspect'))['passed']
    finally:
        for child in [decryptor, target]:
            if child.poll() is None:
                child.terminate()
                child.wait(timeout=15)
    return {'passed': True, 'state': state, 'restore': restored, 'sourceClaimMounted': False,
            'completeFreshArchiveAuthenticatedDuringRestore': True, 'NASVerifiedBeforeRestore': True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['prepare', 'start', 'stop', 'ready', 'snapshot', 'diagnose', 'inspect'])
    parser.add_argument('--label', required=True)
    parser.add_argument('--side', choices=['old', 'mid', 'new'])
    parser.add_argument('--normal-auth', action='store_true')
    parser.add_argument('--upgrade-readiness', action='store_true')
    parser.add_argument('--archive-receipt', type=Path)
    parser.add_argument('--grant-baseline', type=Path)
    parser.add_argument('--startup-receipt', type=Path)
    args = parser.parse_args()
    assert F.is_mount() and os.getuid() == 1000 and re.fullmatch('[a-z0-9-]{1,64}', args.label)
    os.umask(0o077)
    receipt = OUT / ('final-' + args.label + '.json')
    assert not receipt.exists()
    try:
        if args.action == 'prepare':
            assert args.archive_receipt
            result = prepare(args.archive_receipt)
        else:
            state = json.loads((OUT / 'final-state.json').read_text())
            payload = request(state, args.action, args.side, args.normal_auth)
            if args.upgrade_readiness:
                assert args.action == 'ready' and args.normal_auth and args.side in ['mid', 'new']
                payload['upgradeReadinessOnly'] = True
            elif args.normal_auth and args.action in ['ready', 'snapshot']:
                assert args.startup_receipt and args.startup_receipt.parent == OUT
                started = json.loads(args.startup_receipt.read_text())
                assert started['passed'] and '--skip-grant-tables' not in started['flags']
                payload['normalStartupFlags'] = started['flags']
            if args.grant_baseline:
                assert args.grant_baseline.parent == OUT
                baseline = json.loads(args.grant_baseline.read_text())
                assert baseline['passed']
                payload['grantColumns'] = baseline['snapshot']['grantColumns']
            result = trial.remote(program(), payload)
    except Exception as error:
        import traceback
        result = {'passed': False, 'errorType': type(error).__name__, 'rawDetailsSuppressed': True,
                  'sourceLines': [frame.lineno for frame in traceback.extract_tb(error.__traceback__) if frame.filename == __file__],
                  'destinationRetainedForReview': True}
    result.update(UTC=datetime.datetime.now(datetime.timezone.utc).isoformat(), action=args.action,
                  controllerSHA256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  remoteSourceSHA256=hashlib.sha256(program().encode()).hexdigest())
    receipt.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k: result.get(k) for k in ['passed', 'action', 'errorType', 'sourceLines']}))
    return int(not result['passed'])


if __name__ == '__main__':
    raise SystemExit(main())
