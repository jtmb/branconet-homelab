#!/usr/bin/env python3
"""Test encrypted two-replica Longhorn writes, relocation and snapshot restore."""
import datetime
import hashlib
import json
import pathlib
import subprocess
import sys
import time

ROOT=pathlib.Path(__file__).resolve().parents[2]
RUNTIME=pathlib.Path.home()/'.local/share/branconet-migration'
NAMESPACE='migration-system'

def main():
    request=json.load(sys.stdin)
    command=[str(RUNTIME/'bin/kubectl'),'--kubeconfig',str(RUNTIME/'admin.conf')]
    def kube(args,body=None):
        result=subprocess.run([*command,*args],input=json.dumps(body) if body is not None else None,capture_output=True,text=True,timeout=650)
        if result.returncode:raise RuntimeError('Storage proof command failed: '+args[0]+' '+args[1])
        return result.stdout
    def get(kind,name,namespace=NAMESPACE):return json.loads(kube(['get',kind,name,'-n',namespace,'-o','json']))
    def apply(body):kube(['apply','-f','-'],body)
    def wait(predicate,description):
        for _ in range(90):
            value=predicate()
            if value:return value
            time.sleep(2)
        raise RuntimeError('Storage proof timeout: '+description)
    def claim(name,snapshot=None):
        spec={'storageClassName':'longhorn','accessModes':['ReadWriteOnce'],'resources':{'requests':{'storage':'1Gi'}}}
        if snapshot:spec['dataSource']={'apiGroup':'snapshot.storage.k8s.io','kind':'VolumeSnapshot','name':snapshot}
        apply({'apiVersion':'v1','kind':'PersistentVolumeClaim','metadata':{'name':name,'namespace':NAMESPACE},'spec':spec})
        wait(lambda:get('pvc',name).get('status',{}).get('phase')=='Bound','claim '+name)
    def pod(name,claim_name,node):
        apply({'apiVersion':'v1','kind':'Pod','metadata':{'name':name,'namespace':NAMESPACE},'spec':{'nodeName':node,'automountServiceAccountToken':False,'restartPolicy':'Never','containers':[{'name':'proof','image':'busybox@sha256:73aaf090f3d85aa34ee199857f03fa3a95c8ede2ffd4cc2cdb5b94e566b11662','command':['sh','-c','sleep 3600'],'volumeMounts':[{'name':'data','mountPath':'/data'}],'resources':{'requests':{'cpu':'10m','memory':'16Mi'},'limits':{'memory':'64Mi'}}}],'volumes':[{'name':'data','persistentVolumeClaim':{'claimName':claim_name}}]}})
        kube(['wait','-n',NAMESPACE,'pod/'+name,'--for=condition=Ready','--timeout=600s'])
    def write(name,value):kube(['exec','-n',NAMESPACE,name,'--','sh','-c','printf %s '+value+' > /data/migration-marker; sync'])
    def read(name):return kube(['exec','-n',NAMESPACE,name,'--','cat','/data/migration-marker'])
    source='migration-storage-proof'
    if get_existing(command,source):raise SystemExit('Proof claim already exists; inspect retained state before rerunning')
    claim(source);pod('migration-proof-writer',source,'workernode1');write('migration-proof-writer','migration-proof-v1')
    volume=get('pvc',source)['spec']['volumeName']
    wait(lambda:get('volumes.longhorn.io',volume,'longhorn-system')['status'].get('robustness')=='healthy','two healthy replicas')
    longhorn=get('volumes.longhorn.io',volume,'longhorn-system')
    replicas=json.loads(kube(['get','replicas.longhorn.io','-n','longhorn-system','-o','json']))['items']
    placed=[r for r in replicas if r['spec']['volumeName']==volume and r['status'].get('currentState')=='running']
    nodes={r['spec']['nodeID'] for r in placed}
    if longhorn['spec']['numberOfReplicas']!=2 or not longhorn['spec']['encrypted'] or len(nodes)!=2:raise RuntimeError('Actual encrypted replica placement does not satisfy contract')
    luks=subprocess.run(['ssh','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-p','2002','james@192.168.0.6','sudo','-S','-p',"''",'cryptsetup','isLuks','/dev/longhorn/'+volume],input=request['sudo_password']+'\n',text=True,capture_output=True,timeout=30)
    if luks.returncode:raise RuntimeError('Actual Longhorn block device LUKS header verification failed')
    apply({'apiVersion':'snapshot.storage.k8s.io/v1','kind':'VolumeSnapshotClass','metadata':{'name':'longhorn-migration-snapshot'},'driver':'driver.longhorn.io','deletionPolicy':'Retain','parameters':{'type':'snap'}})
    snapshot='migration-proof-v1'
    apply({'apiVersion':'snapshot.storage.k8s.io/v1','kind':'VolumeSnapshot','metadata':{'name':snapshot,'namespace':NAMESPACE},'spec':{'volumeSnapshotClassName':'longhorn-migration-snapshot','source':{'persistentVolumeClaimName':source}}})
    wait(lambda:get('volumesnapshot',snapshot).get('status',{}).get('readyToUse'),'snapshot readiness')
    write('migration-proof-writer','migration-proof-v2')
    kube(['delete','pod','migration-proof-writer','-n',NAMESPACE,'--wait=true'])
    pod('migration-proof-reader',source,'workernode2')
    if read('migration-proof-reader')!='migration-proof-v2':raise RuntimeError('Reattached volume lost the newer marker')
    restored='migration-storage-restored'
    claim(restored,snapshot);pod('migration-proof-restored',restored,'workernode1')
    if read('migration-proof-restored')!='migration-proof-v1':raise RuntimeError('Snapshot did not restore the older marker')
    report={'completed_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'original_pvc':source,'longhorn_volume':volume,'replica_nodes':sorted(nodes),'number_of_replicas':2,'luks_header_verified':True,'original_write_passed':True,'cross_node_reattachment_passed':True,'relocated_node':'workernode2','snapshot':snapshot,'restored_pvc':restored,'older_snapshot_content_verified':True,'test_resources_retained':True,'production_application_accepted':False}
    (ROOT/'evidence/storage-proof.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report),flush=True)

def get_existing(command,name):
    result=subprocess.run([*command,'get','pvc',name,'-n',NAMESPACE,'--ignore-not-found','-o','json'],capture_output=True,text=True)
    if result.returncode:raise RuntimeError('Proof-claim preflight failed')
    return bool(result.stdout.strip())

if __name__=='__main__':main()
