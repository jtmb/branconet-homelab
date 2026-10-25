#!/usr/bin/env python3
"""Disable only xTeVe's binary updater after both full cold archives authenticate."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shlex
import stat
import subprocess
import uuid

ROOT = Path(__file__).resolve().parents[2]
DEP = '52adec00-5c42-4cd2-8fb0-9428828ca368'
HR = 'ace99a34-343b-40cd-b1b3-6ef2f324a8b0'
CLAIMS = {'xteve-data-0': 'd40f1490-7254-4599-be82-2fad35abb88b',
          'xteve-data-1': 'b7207fe9-3768-4ad5-9ca0-ee4429137b33'}
PV_UIDS = {'xteve-data-0': '0ab90957-d5ce-496d-9ddc-658299729a15',
           'xteve-data-1': '8be538e5-bcca-490e-b075-7556d1c0aa31'}


def need(ok):
    if not ok:
        raise ValueError('xTeVe updater prerequisite refused')


PATCH = r'''
import hashlib,json,os,re,stat,sys
p=json.load(sys.stdin); root=os.lstat('/source')
assert stat.S_ISDIR(root.st_mode) and not stat.S_ISLNK(root.st_mode)
fd=os.open('/source/settings.json',os.O_RDWR|os.O_NOFOLLOW)
try:
 before=os.fstat(fd)
 assert stat.S_ISREG(before.st_mode) and before.st_nlink==1 and before.st_size<=131072
 assert [before.st_uid,before.st_gid,stat.S_IMODE(before.st_mode)]==p['metadata']
 raw=os.read(fd,131073); assert len(raw)==before.st_size
 old=json.loads(raw); assert isinstance(old.get('xteveAutoUpdate'),bool)
 pattern=rb'("xteveAutoUpdate"\s*:\s*)(true|false)'
 assert len(re.findall(pattern,raw))==1
 original=re.sub(pattern,lambda m:m[1]+b'true',raw)
 assert hashlib.sha256(original).hexdigest()==p['sha256']
 new=re.sub(pattern,lambda m:m[1]+b'false',raw)
 expected=dict(old,xteveAutoUpdate=False); assert json.loads(new)==expected
 changed=raw!=new
 if changed:
  os.lseek(fd,0,os.SEEK_SET); view=memoryview(new)
  while view:
   count=os.write(fd,view); assert count>0; view=view[count:]
  os.ftruncate(fd,len(new));os.fsync(fd)
 os.lseek(fd,0,os.SEEK_SET); assert os.read(fd,131073)==new
 after=os.fstat(fd); current=os.lstat('/source/settings.json')
 assert (before.st_dev,before.st_ino)==(after.st_dev,after.st_ino)==(current.st_dev,current.st_ino)
 assert (before.st_uid,before.st_gid,before.st_mode)==(after.st_uid,after.st_gid,after.st_mode)==(current.st_uid,current.st_gid,current.st_mode)
 print(json.dumps({'changed':changed,'only_field':'xteveAutoUpdate','disabled':True,'metadata_preserved':True,'inode_preserved':True,'before_sha256':hashlib.sha256(raw).hexdigest(),'after_sha256':hashlib.sha256(new).hexdigest()}))
finally:os.close(fd)
'''


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--apply', action='store_true')
    for name in ['state', 'config']:
        p.add_argument('--'+name+'-receipt', type=Path, required=True)
        p.add_argument('--'+name+'-receipt-sha256', required=True)
    p.add_argument('--receipt', type=Path, required=True)
    a = p.parse_args(); need(a.apply and os.name == 'posix'); os.umask(0o077)
    spec = importlib.util.spec_from_file_location('backup', ROOT/'k8s-rewrite/ansible-playbook/roles/metube_state_backup/files/metube_state_backup.py')
    shared = importlib.util.module_from_spec(spec); spec.loader.exec_module(shared)
    need(a.receipt.is_absolute() and a.receipt.resolve() == a.receipt and not a.receipt.exists())
    need(a.receipt.parent.stat().st_uid == os.getuid() and not a.receipt.parent.stat().st_mode & 0o077)
    need(shared.file_hash(shared.AGE) == shared.AGE_SHA256)
    pins = [(path, shared.protected(path, path == shared.IDENTITY)) for path in [shared.AGE, shared.RECIPIENT, shared.IDENTITY]]
    manifests = {}; proofs = {}
    for scope, app, claim in [('state', 'xteve', 'xteve-data-0'), ('config', 'xteve-config', 'xteve-data-1')]:
        path = getattr(a, scope+'_receipt'); digest = getattr(a, scope+'_receipt_sha256')
        shared.protected(path, True); need(re.fullmatch('[0-9a-f]{64}', digest) and shared.file_hash(path) == digest)
        proof = json.loads(path.read_bytes())
        need(proof['application'] == app and proof['status'] == 'completed' and proof['cold_archive_verified'] is True and proof['temporary_pod_deleted'] is True)
        need(proof['deployment_uid'] == DEP and proof['helmrelease_uid'] == HR and proof['claim_uid'] == CLAIMS[claim])
        archive = Path(proof['archive_path']); shared.protected(archive, True)
        need(shared.file_hash(archive) == proof['archive_sha256'])
        child = subprocess.Popen([str(shared.AGE), '-d', '-i', str(shared.IDENTITY), str(archive)], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        try:
            manifest = shared.verify_archive(child.stdout)
            trailing = child.stdout.read(1024**2+1); need(len(trailing) <= 1024**2 and not any(trailing))
            need(child.wait(timeout=30) == 0)
        finally:
            if child.poll() is None: child.terminate(); child.wait(timeout=10)
        need(hashlib.sha256(shared.canonical(manifest)).hexdigest() == proof['manifest_sha256'])
        manifests[scope] = manifest; proofs[scope] = {'receipt_sha256': digest, 'archive_sha256': proof['archive_sha256']}
    row = manifests['state']['entries']['data-0/settings.json']; need(row['kind'] == 'file')

    def kube(*args, body=None):
        result = subprocess.run(shared.SSH+[shlex.join(['kubectl','--request-timeout=25s','-n','plex',*args])], input=body, capture_output=True, timeout=180)
        need(result.returncode == 0 and len(result.stdout) <= 8*1024**2)
        return result.stdout

    def obj(kind, name, ns='plex'):
        return json.loads(kube('-n',ns,'get',kind,name,'-o','json'))

    owned = None
    def guard():
        dep = obj('deployment','xteve'); hr = obj('helmrelease','xteve','flux-system')
        need(dep['metadata']['uid']==DEP and hr['metadata']['uid']==HR)
        for item in [dep,hr]:
            need(not item['metadata'].get('deletionTimestamp') and item['status'].get('observedGeneration',0)>=item['metadata']['generation'])
        need(dep['spec']['replicas']==0 and all(dep['status'].get(k,0)==0 for k in ['replicas','readyReplicas','availableReplicas','updatedReplicas']))
        need(hr['spec']['values']['replicaCount']==0 and not hr['spec'].get('suspend',False))
        need(any(c['type']=='Ready' and c['status']=='True' for c in hr['status'].get('conditions',[])))
        for name,uid in CLAIMS.items():
            pvc=obj('pvc',name);need(pvc['metadata']['uid']==uid and pvc['status']['phase']=='Bound' and pvc['spec']['volumeName']=='pvc-'+uid)
            pv=obj('pv','pvc-'+uid);need(pv['metadata']['uid']==PV_UIDS[name] and pv['spec']['claimRef']['uid']==uid and pv['spec']['csi']['driver']=='driver.longhorn.io')
        node=obj('node','workernode2');need(node['metadata']['uid']=='eda66e65-f388-4b97-b64f-a709cda81894')
        need(any(c['type']=='Ready' and c['status']=='True' for c in node['status']['conditions']))
        need(not any(c['type'] in ['MemoryPressure','DiskPressure','PIDPressure'] and c['status']=='True' for c in node['status']['conditions']))
        for pod in json.loads(kube('get','pods','-o','json'))['items']:
            if owned and pod['metadata']['uid']==owned['uid']:continue
            if any(v.get('persistentVolumeClaim',{}).get('claimName') in CLAIMS for v in pod['spec'].get('volumes',[])):
                need(pod['status'].get('phase') in ['Succeeded','Failed'] and not any('running' in c.get('state',{}) for k in ['containerStatuses','initContainerStatuses','ephemeralContainerStatuses'] for c in pod['status'].get(k,[])))
        return {'deployment_generation':dep['metadata']['generation'],'release_generation':hr['metadata']['generation']}

    before=guard();run=uuid.uuid4().hex;name='xteve-updater-'+run[:12]
    pod={'apiVersion':'v1','kind':'Pod','metadata':{'name':name,'namespace':'plex','labels':{'migration-task':'xteve-updater','preservation-run':run}},'spec':{'nodeName':'workernode2','restartPolicy':'Never','activeDeadlineSeconds':300,'automountServiceAccountToken':False,'securityContext':{'runAsUser':0,'runAsGroup':0,'supplementalGroupsPolicy':'Strict','seccompProfile':{'type':'RuntimeDefault'}},'containers':[{'name':'reader','image':shared.OLD,'imagePullPolicy':'Never','command':['python3','-B','-c','import time;time.sleep(300)'],'securityContext':{'allowPrivilegeEscalation':False,'readOnlyRootFilesystem':True,'capabilities':{'drop':['ALL']}},'resources':{'requests':{'cpu':'10m','memory':'32Mi'},'limits':{'cpu':'200m','memory':'128Mi'}},'volumeMounts':[{'name':'state','mountPath':'/source'}]}],'volumes':[{'name':'state','persistentVolumeClaim':{'claimName':'xteve-data-0'}}]}}
    receipt={'status':'started','cold_proofs':proofs,'source_sha256':shared.file_hash(Path(__file__)),'writer_scaled_by_helper':False,'nas_mounted_or_walked':False}
    def save():
        a.receipt.write_text(json.dumps(receipt,sort_keys=True,indent=2)+'\n')
    save()
    try:
        created=json.loads(kube('create','-f','-','-o','json',body=shared.canonical(pod)))
        owned={'name':name,'uid':created['metadata']['uid']};receipt['pod']=owned;save()
        kube('wait','pod/'+name,'--for=condition=Ready','--timeout=120s')
        receipt['operation']='validate-admitted-reader';save()
        current=obj('pod',name);need(current['metadata']['uid']==owned['uid'])
        need(current['spec']['securityContext']==pod['spec']['securityContext'] and current['spec']['volumes']==pod['spec']['volumes'])
        need(current['spec']['automountServiceAccountToken'] is False and len(current['spec']['containers'])==1 and not current['spec'].get('initContainers') and not current['spec'].get('ephemeralContainers'))
        for key in ['image','command','securityContext','volumeMounts']:
            need(current['spec']['containers'][0][key]==pod['spec']['containers'][0][key])
        receipt['operation']='recheck-quiescent-writer';save()
        need(current['status']['containerStatuses'][0]['imageID']==shared.OLD and guard()==before)
        payload={'sha256':row['sha256'],'metadata':[row[k] for k in ['uid','gid','mode']]}
        receipt['operation']='change-single-updater-boolean';save()
        receipt['result']=json.loads(kube('exec','-i',name,'-c','reader','--','python3','-B','-c',PATCH,body=shared.canonical(payload)))
        receipt['operation']='verify-post-change-fences';save()
        need(guard()==before)
        for path,pin in pins:need(shared.protected(path,path==shared.IDENTITY)==pin)
        options={'apiVersion':'v1','kind':'DeleteOptions','preconditions':{'uid':owned['uid']}}
        kube('delete','--raw','/api/v1/namespaces/plex/pods/'+name,'-f','-',body=shared.canonical(options))
        kube('wait','pod/'+name,'--for=delete','--timeout=120s')
        receipt.update(status='completed',temporary_pod_deleted=True);save()
        print(json.dumps({'status':'completed','receipt':str(a.receipt),'changed':receipt['result']['changed']}))
    except Exception as error:
        import traceback
        receipt['status']='failed';receipt['error_type']=type(error).__name__
        receipt['error_source_lines']=[frame.lineno for frame in traceback.extract_tb(error.__traceback__) if frame.filename==__file__]
        save();raise


if __name__=='__main__':
    try:main()
    except Exception:raise SystemExit('xTeVe updater change refused; private receipt retained; raw values suppressed')
