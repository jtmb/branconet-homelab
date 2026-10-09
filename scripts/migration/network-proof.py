#!/usr/bin/env python3
"""Prove DNS and bidirectional cross-worker pod networking with test pods."""
import json
import pathlib
import subprocess

REMOTE=r'''
import datetime,json,subprocess
def kube(args,body=None):
 r=subprocess.run(['kubectl',*args],input=json.dumps(body) if body is not None else None,text=True,capture_output=True,timeout=330)
 if r.returncode:raise RuntimeError('Kubernetes network proof command failed: '+args[0])
 return r.stdout
namespace='migration-system';names=['netprobe-workernode1','netprobe-workernode2']
kube(['apply','-f','-'],{'apiVersion':'v1','kind':'Namespace','metadata':{'name':namespace}})
for name,node in zip(names,['workernode1','workernode2']):
 kube(['apply','-f','-'],{'apiVersion':'v1','kind':'Pod','metadata':{'name':name,'namespace':namespace},'spec':{'nodeName':node,'automountServiceAccountToken':False,'restartPolicy':'Never','containers':[{'name':'probe','image':'busybox:1.36.1','imagePullPolicy':'IfNotPresent','command':['sh','-c','sleep 1800'],'resources':{'requests':{'cpu':'10m','memory':'16Mi'},'limits':{'memory':'64Mi'}}}]}})
kube(['wait','-n',namespace,*['pod/'+name for name in names],'--for=condition=Ready','--timeout=300s'])
pods=[json.loads(kube(['get','pod',name,'-n',namespace,'-o','json'])) for name in names]
checks=[]
for index,pod in enumerate(pods):
 other=pods[1-index]['status']['podIP']
 kube(['exec','-n',namespace,pod['metadata']['name'],'--','nslookup','kubernetes.default.svc.cluster.local'])
 kube(['exec','-n',namespace,pod['metadata']['name'],'--','ping','-c','3','-W','3',other])
 checks.append({'pod':pod['metadata']['name'],'node':pod['spec']['nodeName'],'pod_ip':pod['status']['podIP'],'image_id':pod['status']['containerStatuses'][0]['imageID'],'cluster_dns_passed':True,'peer_ping_passed':True})
nodes=json.loads(kube(['get','nodes','-o','json']))
print(json.dumps({'captured_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'checks':checks,'nodes':[{'name':n['metadata']['name'],'ready':any(c['type']=='Ready' and c['status']=='True' for c in n['status']['conditions']),'kubelet_version':n['status']['nodeInfo']['kubeletVersion'],'runtime':n['status']['nodeInfo']['containerRuntimeVersion']} for n in nodes['items']],'test_pods_retained_for_storage_checks':True}))
'''

def main():
    result=subprocess.run(['ssh','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-p','2002','james@192.168.0.4','python3','-'],input=REMOTE,text=True,capture_output=True,timeout=700)
    if result.returncode:raise SystemExit('Network proof failed; test pods retained for diagnosis')
    report=json.loads(result.stdout)
    output=pathlib.Path(__file__).resolve().parents[2]/'evidence/network-proof.json'
    output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report),flush=True)

if __name__=='__main__':main()
