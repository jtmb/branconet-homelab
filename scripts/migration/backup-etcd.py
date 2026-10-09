#!/usr/bin/env python3
"""Encrypt a consistent etcd snapshot and read its Secrets after isolated restore."""
import base64
import datetime
import hashlib
import json
import os
import pathlib
import subprocess
import sys
import time

ROOT=pathlib.Path(__file__).resolve().parents[2]
RUNTIME=pathlib.Path.home()/'.local/share/branconet-migration'

def main():
    request=json.load(sys.stdin)
    stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    snapshot='/var/lib/etcd/migration-recovery-'+stamp+'.snapshot'
    kube=[str(RUNTIME/'bin/kubectl'),'--kubeconfig',str(RUNTIME/'admin.conf')]
    def run(args,body=None,timeout=180):
        result=subprocess.run([*kube,*args],input=body,capture_output=True,timeout=timeout)
        if result.returncode:
            diagnostic=result.stderr.decode(errors='replace').splitlines()[-3:] if 'snapshot' in args or '/proof/snapshot.db' in ' '.join(args) else []
            raise RuntimeError('Etcd recovery check failed: '+args[0]+' '+json.dumps(diagnostic))
        return result.stdout
    etcd=json.loads(run(['get','pod','etcd-masternode','-n','kube-system','-o','json']))
    original=['exec','-n','kube-system','etcd-masternode','--','etcdctl','--endpoints=https://127.0.0.1:2379','--cacert=/etc/kubernetes/pki/etcd/ca.crt','--cert=/etc/kubernetes/pki/etcd/healthcheck-client.crt','--key=/etc/kubernetes/pki/etcd/healthcheck-client.key']
    expected=json.loads(run([*original,'get','/registry/secrets/','--prefix','--write-out=json']))['kvs']
    expected={record['key']:record['value'] for record in expected}
    run([*original,'snapshot','save',snapshot])
    # Read the snapshot only through an authenticated root pipe; never a plaintext operator file.
    remote="import pathlib,subprocess,sys\ncommand=['sudo','-S','-p','','python3','-c',"+repr("import pathlib,sys;p=pathlib.Path("+repr(snapshot)+");p.chmod(0o600);sys.stdout.buffer.write(p.read_bytes())")+"]\nresult=subprocess.run(command,input="+repr(request['sudo_password']+'\n')+".encode(),capture_output=True)\nif result.returncode:raise SystemExit('Snapshot recovery read failed')\nsys.stdout.buffer.write(result.stdout)\n"
    result=subprocess.run(['ssh','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-p','2002','james@192.168.0.4','python3','-'],input=remote.encode(),capture_output=True,timeout=60)
    if result.returncode:raise SystemExit('Consistent snapshot could not be read')
    raw=result.stdout
    recipient=(pathlib.Path.home()/'.ssh/id_ed25519.pub').read_text().strip()
    encrypted=subprocess.run([str(RUNTIME/'bin/age'),'-r',recipient],input=raw,capture_output=True,check=True).stdout
    directory=RUNTIME/'recovery';directory.mkdir(mode=0o700,parents=True,exist_ok=True)
    target=directory/('etcd-'+stamp+'.snapshot.age')
    fd=os.open(target,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    with os.fdopen(fd,'wb') as output:output.write(encrypted)
    recovered=subprocess.run([str(RUNTIME/'bin/age'),'-d','-i',str(pathlib.Path.home()/'.ssh/id_ed25519'),str(target)],capture_output=True,check=True).stdout
    if recovered!=raw:raise RuntimeError('Authenticated snapshot recovery differs')
    nas='/mnt/container-backups/k8s-migration-20261009/'+target.name
    subprocess.run(['scp','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-P','2002',str(target),'james@192.168.0.4:'+nas],capture_output=True,check=True)
    remote_hash=subprocess.run(['ssh','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-p','2002','james@192.168.0.4','sha256sum',nas],capture_output=True,text=True,check=True).stdout.split()[0]
    digest=hashlib.sha256(encrypted).hexdigest()
    if remote_hash!=digest:raise RuntimeError('NAS encrypted snapshot checksum differs')
    name='etcd-recovery-'+stamp.lower()
    labels={'app':name}
    run(['apply','-f','-'],json.dumps({'apiVersion':'networking.k8s.io/v1','kind':'NetworkPolicy','metadata':{'name':name,'namespace':'migration-system'},'spec':{'podSelector':{'matchLabels':labels},'policyTypes':['Ingress','Egress'],'ingress':[],'egress':[]}}).encode())
    pod={'apiVersion':'v1','kind':'Pod','metadata':{'name':name,'namespace':'migration-system','labels':labels},'spec':{'automountServiceAccountToken':False,'restartPolicy':'Never','nodeName':'masternode','containers':[{'name':'transfer','image':'busybox@sha256:73aaf090f3d85aa34ee199857f03fa3a95c8ede2ffd4cc2cdb5b94e566b11662','command':['sh','-c','sleep 1800'],'volumeMounts':[{'name':'proof','mountPath':'/proof'}],'resources':{'requests':{'cpu':'10m','memory':'16Mi'},'limits':{'memory':'64Mi'}}},{'name':'etcd','image':etcd['spec']['containers'][0]['image'],'command':['etcd','--name=empty','--data-dir=/proof/empty','--listen-client-urls=http://127.0.0.1:12379','--advertise-client-urls=http://127.0.0.1:12379','--listen-peer-urls=http://127.0.0.1:12380','--initial-advertise-peer-urls=http://127.0.0.1:12380','--initial-cluster=empty=http://127.0.0.1:12380'],'volumeMounts':[{'name':'proof','mountPath':'/proof'}],'resources':{'requests':{'cpu':'100m','memory':'128Mi'},'limits':{'memory':'512Mi'}}}],'volumes':[{'name':'proof','emptyDir':{}}]}}
    pod['spec']['securityContext']={'runAsUser':0,'runAsGroup':0}
    # Recovery bytes have already authenticated and compared equal to this exact
    # root-only source snapshot. Read-only mounting avoids exec stdin corruption.
    pod['spec']['containers']=[pod['spec']['containers'][1]]
    pod['spec']['containers'][0]['volumeMounts'].append({'name':'snapshot','mountPath':'/snapshot','readOnly':True})
    pod['spec']['volumes'].append({'name':'snapshot','hostPath':{'path':snapshot,'type':'File'}})
    run(['create','-f','-'],json.dumps(pod).encode())
    running=None
    try:
        run(['wait','pod/'+name,'-n','migration-system','--for=condition=Ready','--timeout=180s'])
        prefix=['exec','-n','migration-system',name,'-c','etcd','--']
        status=json.loads(run([*prefix,'etcdutl','snapshot','status','/snapshot','--write-out=json']))
        run([*prefix,'etcdutl','snapshot','restore','/snapshot','--data-dir=/proof/restored','--name=proof','--initial-cluster=proof=http://127.0.0.1:32380','--initial-advertise-peer-urls=http://127.0.0.1:32380'])
        running=subprocess.Popen([*kube,*prefix,'etcd','--name=proof','--data-dir=/proof/restored','--listen-client-urls=http://127.0.0.1:32379','--advertise-client-urls=http://127.0.0.1:32379','--listen-peer-urls=http://127.0.0.1:32380','--initial-advertise-peer-urls=http://127.0.0.1:32380','--initial-cluster=proof=http://127.0.0.1:32380'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        restored=None
        for _ in range(30):
            probe=subprocess.run([*kube,*prefix,'etcdctl','--endpoints=http://127.0.0.1:32379','--dial-timeout=2s','--command-timeout=3s','get','/registry/secrets/','--prefix','--write-out=json'],capture_output=True,timeout=15)
            if probe.returncode==0:restored=json.loads(probe.stdout)['kvs'];break
            time.sleep(1)
        if restored is None:raise RuntimeError('Isolated restored etcd did not serve its snapshot')
        actual={record['key']:record['value'] for record in restored}
        if any(actual.get(key)!=value for key,value in expected.items()):raise RuntimeError('Restored native Secret ciphertext differs from the source snapshot')
        imported=json.loads((ROOT/'evidence/native-secret-import.json').read_text())
        for secret in imported['secrets']:
            key=base64.b64encode(('/registry/secrets/'+secret['namespace']+'/'+secret['name']).encode()).decode()
            if key not in actual or not base64.b64decode(actual[key]).startswith(b'k8s:enc:aescbc:v1:'):raise RuntimeError('Imported encrypted Secret missing from restored etcd')
        report={'completed_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'kind':'consistent etcd snapshot','operator_copy':str(target),'nas_copy':nas,'ciphertext_sha256':digest,'authenticated_decryption_equal':True,'snapshot_status':status,'isolated_restore_and_start_passed':True,'source_secret_records_compared':len(expected),'imported_encrypted_secret_records_verified':len(imported['secrets']),'production_etcd_untouched':True,'api_encryption_key_recovery_reference':'evidence/config-backups.json','plaintext_exported_to_operator':False}
        (ROOT/'evidence/etcd-recovery.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report),flush=True)
    finally:
        if running:
            running.terminate()
            try:running.wait(timeout=10)
            except subprocess.TimeoutExpired:running.kill()
        # These exact newly owned test resources contain temporary snapshot copies.
        run(['delete','pod',name,'-n','migration-system','--wait=true'])
        run(['delete','networkpolicy',name,'-n','migration-system'])

if __name__=='__main__':main()
