#!/usr/bin/env python3
"""Check imported Secret ciphertext in etcd without exporting values/blobs."""
import base64
import datetime
import json
import pathlib
import subprocess

ROOT=pathlib.Path(__file__).resolve().parents[2]

def main():
    imported=json.loads((ROOT/'evidence/native-secret-import.json').read_text())
    if not imported.get('executed') or not all(s['readback_equal'] for s in imported['secrets']):raise SystemExit('Native import/readback must complete first')
    targets=[{'namespace':s['namespace'],'name':s['name']} for s in imported['secrets']]
    remote="TARGETS="+repr(targets)+"\n"+r'''
import base64,datetime,json,subprocess
results=[]
for target in TARGETS:
 key='/registry/secrets/'+target['namespace']+'/'+target['name']
 command=['kubectl','exec','-n','kube-system','etcd-masternode','--','etcdctl','--endpoints=https://127.0.0.1:2379','--cacert=/etc/kubernetes/pki/etcd/ca.crt','--cert=/etc/kubernetes/pki/etcd/healthcheck-client.crt','--key=/etc/kubernetes/pki/etcd/healthcheck-client.key','get',key,'--write-out=json']
 result=subprocess.run(command,capture_output=True,text=True,timeout=30)
 if result.returncode:raise SystemExit('etcd ciphertext check failed')
 records=json.loads(result.stdout).get('kvs',[])
 if len(records)!=1:raise SystemExit('Secret missing from expected etcd registry path')
 encrypted=base64.b64decode(records[0]['value'])
 if not encrypted.startswith(b'k8s:enc:aescbc:v1:'):raise SystemExit('Secret is not stored with configured API encryption')
 results.append({**target,'aescbc_ciphertext_verified':True})
print(json.dumps({'captured_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'secret_count':len(results),'ciphertext_exported':False,'plaintext_exported':False,'checks':results}))
'''
    result=subprocess.run(['ssh','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-p','2002','james@192.168.0.4','python3','-'],input=remote,capture_output=True,text=True,timeout=700)
    if result.returncode:raise SystemExit('Live Secret ciphertext verification failed')
    report=json.loads(result.stdout)
    (ROOT/'evidence/secret-encryption.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'secret_count':report['secret_count'],'ciphertext_verified':True,'values_reported':False}),flush=True)

if __name__=='__main__':main()
