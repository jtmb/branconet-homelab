#!/usr/bin/env python3
"""Plan or explicitly restore the verified upgraded archive to one fresh claim.

Never creates/deletes Kubernetes resources. The original claim is never mounted.
Plan is read-only. Restore requires an operator-created exact Pod and UID pins.
"""
import argparse
import datetime
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import traceback
import uuid

ROOT = Path(__file__).resolve().parents[2]
ARCHIVER = Path(__file__).with_name('archive-ruckusdb-qualified-copy.py')
COPY_HELPER = Path(__file__).with_name('qualify-ruckusdb-copies.py')
COPY_SHA = '74bb2fc2feaf400d211dfc62410c3846c43f3e46f69b06ba8ddff42c3686749c'
ORIGINAL_CLAIM = 'ruckus-db-data-0'
ORIGINAL_UID = '2f604004-b45f-4061-bdc4-43f5ca2f7fd8'
NEW_IMAGE = 'docker.io/library/ruckusdb-security-20261023@sha256:2f0c391e6c04501862598bbc5446165f8ebba08025168451f6f6447352316349'
LABEL = 'branconet.net/ruckusdb-restore'


def need(ok, code):
    if not ok:
        raise RuntimeError(code)


def module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def plan(shared, args):
    labels = {LABEL: args.run_id}
    pod = {'apiVersion': 'v1', 'kind': 'Pod',
           'metadata': {'name': 'ruckusdb-restore-' + args.run_id, 'namespace': 'ruckus', 'labels': labels},
           'spec': {'nodeSelector': {'kubernetes.io/hostname': 'workernode2'}, 'restartPolicy': 'Never',
                    'activeDeadlineSeconds': 1800, 'automountServiceAccountToken': False, 'enableServiceLinks': False,
                    'hostNetwork': False, 'hostPID': False, 'hostIPC': False,
                    'securityContext': {'fsGroup': 65534, 'supplementalGroupsPolicy': 'Strict', 'seccompProfile': {'type': 'RuntimeDefault'}},
                    'containers': [{'name': 'restore', 'image': shared.OLD, 'imagePullPolicy': 'Never',
                                    'command': ['python3', '-B', '-c', 'import time;time.sleep(1800)'],
                                    'securityContext': {'runAsUser': 0, 'runAsGroup': 65534, 'allowPrivilegeEscalation': False,
                                                        'readOnlyRootFilesystem': True,
                                                        'capabilities': {'drop': ['ALL'], 'add': ['CHOWN', 'FOWNER', 'DAC_OVERRIDE']}},
                                    'resources': {'requests': {'cpu': '25m', 'memory': '32Mi'}, 'limits': {'cpu': '500m', 'memory': '512Mi'}},
                                    'volumeMounts': [{'name': 'fresh', 'mountPath': '/restore'}]}],
                    'volumes': [{'name': 'fresh', 'persistentVolumeClaim': {'claimName': args.claim}}]}}
    policy = {'apiVersion': 'networking.k8s.io/v1', 'kind': 'NetworkPolicy',
              'metadata': {'name': pod['metadata']['name'], 'namespace': 'ruckus', 'labels': labels},
              'spec': {'podSelector': {'matchLabels': labels}, 'policyTypes': ['Ingress', 'Egress'], 'ingress': [], 'egress': []}}
    return {'apiVersion': 'v1', 'kind': 'List', 'items': [policy, pod]}


GUARD = r'''import datetime,hashlib,importlib.util,json,sys
x=json.load(sys.stdin);stage='observer'
def filtered(kind,value,tb): print(json.dumps({'guard_stage':stage,'error_type':kind.__name__}))
sys.excepthook=filtered
assert hashlib.sha256(open(x['observer'],'rb').read()).hexdigest()==x['observer_sha']
s=importlib.util.spec_from_file_location('q',x['observer']);q=importlib.util.module_from_spec(s);s.loader.exec_module(q)
stage='original_identity'
original=q.get('pvc','ruckus-db-data-0');assert original['metadata']['uid']==q.IDS['pvc'] and not original['metadata'].get('deletionTimestamp')
opv=q.get('pv',original['spec']['volumeName'],None);assert opv['metadata']['uid']==x['source']['pv_uid'] and opv['spec']['claimRef']['uid']==q.IDS['pvc']
assert opv['spec']['csi']['driver']=='driver.longhorn.io'
stage='fresh_claim'
claim=q.get('pvc',x['claim']);assert claim['metadata']['uid']==x['claim_uid']!=q.IDS['pvc'] and not claim['metadata'].get('deletionTimestamp')
assert claim['status']['phase']=='Bound' and claim['spec']['storageClassName']=='longhorn'
assert not claim['spec'].get('dataSource') and not claim['spec'].get('dataSourceRef')
assert datetime.datetime.fromisoformat(claim['metadata']['creationTimestamp'].replace('Z','+00:00'))>datetime.datetime.fromisoformat(x['archive_started'])
pv=q.get('pv',claim['spec']['volumeName'],None);assert pv['spec']['claimRef']['uid']==x['claim_uid'] and pv['spec']['csi']['driver']=='driver.longhorn.io'
assert pv['metadata']['uid']!=opv['metadata']['uid'] and pv['spec']['csi']['volumeHandle']!=opv['spec']['csi']['volumeHandle'] and not pv['metadata'].get('deletionTimestamp')
stage='paused_writers'
for name,dk,hk in [('ruckus-db','deployment','release'),('ruckus-bot','bot','bot_release')]:
 d=q.get('deployment',name);h=q.get('helmrelease',name,'flux-system')
 assert d['metadata']['uid']==q.IDS[dk] and h['metadata']['uid']==q.IDS[hk] and not d['metadata'].get('deletionTimestamp') and not h['metadata'].get('deletionTimestamp')
 assert d['spec'].get('replicas',1)==0 and all(d['status'].get(k,0)==0 for k in ['replicas','updatedReplicas','readyReplicas','availableReplicas'])
 assert h['spec'].get('values',{}).get('replicaCount')==0 and not h['spec'].get('suspend',False)
 assert all(o['status'].get('observedGeneration',0)>=o['metadata']['generation'] for o in [d,h])
 assert any(c['type']=='Ready' and c['status']=='True' for c in h['status'].get('conditions',[]))
 if name=='ruckus-db':
  t=d['spec']['template']['spec'];assert len(t['containers'])==1;c=t['containers'][0]
  assert c['image']==x['new_image'] and not c.get('args') and not c.get('command') and c.get('envFrom')==[{'secretRef':{'name':'ruckus-db-runtime'}}]
  assert c.get('resources',{})==x['source']['resources']
  vs=[v for v in t['volumes'] if v.get('persistentVolumeClaim')];assert len(vs)==1 and vs[0]['persistentVolumeClaim']['claimName']==x['claim']
  ms=[v for v in c['volumeMounts'] if v['name']==vs[0]['name']];assert len(ms)==1 and ms[0]['mountPath']=='/var/lib/mysql' and ms[0].get('subPath')=='data-0' and not ms[0].get('subPathExpr')
stage='native_secret'
values,native=q.native(bytes.fromhex(x['key_hex']));del values;assert native==x['native_secret']
stage='claim_users'
pods=q.get('pods')['items']
for p in pods:
 uses=[v.get('persistentVolumeClaim',{}).get('claimName') for v in p['spec'].get('volumes',[])]
 if 'ruckus-db-data-0' in uses:
  assert p['status'].get('phase') in ['Failed','Succeeded']
  assert not any('running' in c.get('state',{}) for k in ['containerStatuses','initContainerStatuses','ephemeralContainerStatuses'] for c in p['status'].get(k,[]))
 if x['claim'] in uses:assert p['metadata']['name']==x['plan']['items'][1]['metadata']['name'] and x['pod_uid'] and p['metadata']['uid']==x['pod_uid']
stage='restore_pod'
if x['pod_uid']:
 expected=x['plan']['items'][1];p=q.get('pod',expected['metadata']['name']);assert p['metadata']['uid']==x['pod_uid'] and not p['metadata'].get('deletionTimestamp')
 assert p['metadata'].get('labels',{}).get(x['label'])==x['run_id'] and p['spec']['nodeName']=='workernode2'
 assert not p['spec'].get('initContainers') and not p['spec'].get('ephemeralContainers')
 for k,v in expected['spec'].items():
  if k=='containers':
   assert len(p['spec'][k])==1
   for ck,cv in v[0].items():assert p['spec'][k][0].get(ck)==cv
   assert not p['spec'][k][0].get('env') and not p['spec'][k][0].get('envFrom')
  else:assert p['spec'].get(k,False)==v
 policy=q.get('networkpolicy',expected['metadata']['name']);assert policy['metadata']['uid']==x['policy_uid'] and not policy['metadata'].get('deletionTimestamp')
 assert policy['spec']['podSelector']==x['plan']['items'][0]['spec']['podSelector'] and set(policy['spec']['policyTypes'])=={'Ingress','Egress'} and not policy['spec'].get('ingress') and not policy['spec'].get('egress')
 assert p['status']['containerStatuses'][0]['ready'] and p['status']['containerStatuses'][0]['imageID']==x['reader']
print(json.dumps({'source_pvc_uid':original['metadata']['uid'],'source_pvc_spec_sha256':hashlib.sha256(json.dumps(original['spec'],sort_keys=True).encode()).hexdigest(),
 'source_pv_uid':opv['metadata']['uid'],'source_pv_spec_sha256':hashlib.sha256(json.dumps(opv['spec'],sort_keys=True).encode()).hexdigest(),
 'fresh_pvc_uid':claim['metadata']['uid'],'fresh_pv_uid':pv['metadata']['uid'],'fresh_pvc_spec_sha256':hashlib.sha256(json.dumps(claim['spec'],sort_keys=True).encode()).hexdigest(),
 'native_secret':native,'pod_uid':x['pod_uid'],'policy_uid':x['policy_uid']}))
'''


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=['plan', 'restore'])
    p.add_argument('--archive-receipt', type=Path, required=True)
    p.add_argument('--archive-receipt-sha256', required=True)
    p.add_argument('--claim', required=True); p.add_argument('--claim-uid', required=True)
    p.add_argument('--run-id', required=True)
    p.add_argument('--pod-uid'); p.add_argument('--policy-uid')
    a = p.parse_args(); os.umask(0o077)
    arc = module(ARCHIVER, 'qualified_archiver'); shared = arc.load_shared()
    need(re.fullmatch('ruckus-db-[a-z0-9-]+', a.claim) and a.claim != ORIGINAL_CLAIM and a.claim_uid != ORIGINAL_UID, 'fresh_named_claim')
    need(re.fullmatch('[a-f0-9]{12}', a.run_id), 'run_id')
    need(a.archive_receipt.resolve().is_relative_to(arc.OUTPUT) and arc.digest(a.archive_receipt) == a.archive_receipt_sha256, 'archive_receipt_pin')
    receipt = json.loads(a.archive_receipt.read_bytes())
    need(receipt['status'] == 'completed' and receipt['cold_archive_verified'] and receipt['complete_inventory_unchanged'], 'verified_upgraded_archive')
    cipher = Path(receipt['archive_path'])
    need(cipher.resolve().is_relative_to(arc.OUTPUT) and arc.digest(cipher) == receipt['archive_sha256'], 'cipher_pin')
    need(arc.digest(ARCHIVER) == receipt['controller_sha256'], 'reviewed_archive_controller')
    need(arc.digest(COPY_HELPER) == COPY_SHA and arc.digest(shared.AGE) == shared.AGE_SHA256, 'restore_primitives_pin')
    tool_pins = [(f, shared.protected(f, f == shared.IDENTITY)) for f in (shared.AGE, shared.RECIPIENT, shared.IDENTITY)]
    objects = plan(shared, a)

    def guard():
        data = {'observer': arc.OBSERVER, 'observer_sha': arc.OBSERVER_SHA, 'source': receipt['before']['source_identity'],
                'claim': a.claim, 'claim_uid': a.claim_uid, 'archive_started': receipt['started_at'], 'new_image': NEW_IMAGE,
                'key_hex': (arc.PRIVATE / 'hmac-key.hex').read_text().strip(), 'native_secret': receipt['before']['native_secret'],
                'plan': objects, 'pod_uid': a.pod_uid, 'policy_uid': a.policy_uid, 'label': LABEL,
                'run_id': a.run_id, 'reader': shared.OLD}
        return json.loads(arc.remote(shared, ['python3', '-B', '-c', GUARD], shared.canonical(data)))

    if a.action == 'plan':
        need(not a.pod_uid and not a.policy_uid, 'plan_before_pod_creation')
        guard()
        print(json.dumps(objects, indent=2)); return
    need(a.pod_uid and a.policy_uid, 'explicit_owned_resource_uids')
    run = arc.OUTPUT / ('restore-' + uuid.uuid4().hex); run.mkdir(mode=0o700)
    result = {'status': 'started', 'operation': 'guard', 'controller_sha256': arc.digest(Path(__file__)),
              'archive_receipt_sha256': a.archive_receipt_sha256, 'source_claim_never_mounted': True,
              'new_claim': a.claim, 'new_claim_uid': a.claim_uid, 'pod_uid': a.pod_uid, 'policy_uid': a.policy_uid}

    def save():
        temp = run / ('receipt-' + uuid.uuid4().hex + '.tmp')
        with temp.open('x') as f:
            json.dump(result, f, indent=2, sort_keys=True); f.write('\n'); f.flush(); os.fsync(f.fileno())
        os.replace(temp, run / 'receipt.json')

    save()
    try:
        before = guard()
        result['before'] = before; result['operation'] = 'authenticate_before_write'; save()
        expected = arc.decrypt(shared, cipher)
        need(hashlib.sha256(shared.canonical(expected)).hexdigest() == receipt['manifest_sha256'], 'exact_archive_manifest')
        copies = module(COPY_HELPER, 'restore_primitives')
        program = copies.RESTORE
        old = "expected=sys.stdin.buffer.readline().decode().strip();side=sys.argv[1];assert side in ['old','new']"
        need(program.count(old) == 1, 'receiver_preimage_1')
        program = program.replace(old, "expected=sys.stdin.buffer.readline().decode().strip();side='fresh-claim'")
        old = "root=pathlib.Path('/copies')/side;assert root.is_dir() and not root.is_symlink() and not list(root.iterdir())"
        need(program.count(old) == 1, 'receiver_preimage_2')
        program = program.replace(old, "root=pathlib.Path('/restore');assert root.is_dir() and not root.is_symlink();extras=list(root.iterdir());assert all(p.name=='lost+found' and p.is_dir() and not p.is_symlink() and not list(p.iterdir()) for p in extras)")
        before_stream = guard(); need(before_stream == before, 'prewrite_identity_stable')
        result['operation'] = 'restore_fresh_claim_only'; save()
        command = ['kubectl', '-n', 'ruckus', 'exec', '-i', objects['items'][1]['metadata']['name'], '-c', 'restore', '--', 'python3', '-B', '-c', program]
        receiver = subprocess.Popen(shared.SSH + [arc.shlex.join(command)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        receiver.stdin.write((receipt['manifest_sha256'] + '\n').encode()); receiver.stdin.flush()
        dec = subprocess.Popen([str(shared.AGE), '-d', '-i', str(shared.IDENTITY), str(cipher)], stdout=receiver.stdin, stderr=subprocess.DEVNULL)
        receiver.stdin.close()
        code = dec.wait(timeout=600); out = receiver.stdout.read(); receiver_code = receiver.wait(timeout=30)
        need(code == 0 and receiver_code == 0, 'authenticated_receiver_finished')
        restored = json.loads(out); need(restored['restored'] and restored['full_manifest_sha256'] == receipt['manifest_sha256'], 'restored_full_manifest')
        result['operation'] = 'verify_all_restored_bytes'; save()
        reader = "__name__='restore_verifier'\n" + (arc.SHARED / 'pod_reader.py').read_text()
        reader += "\nROOTS={'data-0':'/restore/data-0'}\nEXCLUDED=set()\nMAX_BYTES=384*1024**2\nprint(json.dumps(inventory(False),sort_keys=True))\n"
        actual = json.loads(arc.remote(shared, command[:-1] + [reader]))
        # Inodes/devices/ctime necessarily change across filesystems; every stored
        # byte, path, mode, uid, gid, symlink and nanosecond mtime must match.
        view = lambda m: dict(m, entries={n: {k: v for k, v in row.items() if k != 'fingerprint'} for n, row in m['entries'].items()})
        need(view(actual) == view(expected), 'full_restored_bytes_and_metadata')
        need(guard() == before and arc.digest(cipher) == receipt['archive_sha256'], 'postrestore_identities')
        for path, ident in tool_pins:
            need(shared.protected(path, path == shared.IDENTITY) == ident, 'key_tool_identity_stable')
        result.update(status='completed', operation='complete', restored_manifest_sha256=receipt['manifest_sha256'],
                      full_file_metadata_equal=True, file_bytes=actual['total_file_bytes'], entries=len(actual['entries']),
                      resource_cleanup_performed=False, original_archive_retained=True)
        save()
    except Exception as error:
        result.update(status='failed', error_code=str(error) if isinstance(error, RuntimeError) else 'filtered_error',
                      error_type=type(error).__name__, source_lines=[f.lineno for f in traceback.extract_tb(error.__traceback__) if f.filename == __file__])
        save(); print(json.dumps({'status': 'failed', 'receipt': str(run / 'receipt.json'), 'operation': result['operation']})); raise SystemExit(1)
    print(json.dumps({'status': 'completed', 'receipt': str(run / 'receipt.json'), 'restored_manifest_sha256': receipt['manifest_sha256']}))


if __name__ == '__main__':
    main()
