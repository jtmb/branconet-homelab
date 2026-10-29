"""Opt-in public file-provider key; native Secret private values stay only in RAM."""
import argparse
import base64
import copy
import hashlib
import json
import shlex
import subprocess
import sys

PUBLIC_KEY='bortus-https-redirect.yaml'
PUBLIC_CONTENT='http:\n  middlewares:\n    bortus-lan-https-redirect:\n      redirectScheme:\n        scheme: https\n        permanent: true\n'
SSH=['ssh','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-i','/home/brajam/.ssh/id_ed25519','-p','2002','james@192.168.0.4']

def call(args,body=None):
 result=subprocess.run(SSH+[shlex.join(['kubectl']+args)],input=body,capture_output=True,timeout=45)
 assert result.returncode==0 and len(result.stdout)<1024**2,'Bounded native redirect operation failed'
 return json.loads(result.stdout)

def provider():
 deployment=call(['-n','traefik','get','deployment','traefik','-o','json'])
 assert deployment['metadata']['uid'] and not deployment['metadata'].get('deletionTimestamp')
 spec=deployment['spec']['template']['spec']
 containers=[c for c in spec['containers'] if c['name']=='traefik'];assert len(containers)==1
 container=containers[0];args=container['args']
 assert [x for x in args if x.startswith('--providers.file.directory=')]==['--providers.file.directory=/etc/traefik/dynamic']
 assert [x for x in args if x.startswith('--providers.file.watch=')]==['--providers.file.watch=true']
 mounts=[m for m in container['volumeMounts'] if m['mountPath']=='/etc/traefik/dynamic']
 assert mounts==[{'name':'dashboard-config','mountPath':'/etc/traefik/dynamic','readOnly':True}]
 volumes=[v for v in spec['volumes'] if v['name']=='dashboard-config'];assert len(volumes)==1
 assert set(volumes[0])=={'name','secret'}
 secret=volumes[0]['secret'];assert secret['secretName']=='traefik-dashboard-config' and set(secret)<={'secretName','defaultMode'}
 assert secret.get('defaultMode',420)==420
 assert call(['-n','flux-system','get','helmrelease','bortus','-o','json'])['spec']['suspend'] is True
 return deployment

def preserved(secret):
 # Only API bookkeeping changes when the one public data key is inserted.
 result=copy.deepcopy(secret)
 result['data'].pop(PUBLIC_KEY,None)
 for key in ('resourceVersion','managedFields'):result['metadata'].pop(key,None)
 return result

def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--apply',action='store_true');args=parser.parse_args()
 deployment=provider()
 before=call(['-n','traefik','get','secret','traefik-dashboard-config','-o','json'])
 meta=before['metadata'];assert meta['uid'] and meta['resourceVersion'] and not meta.get('deletionTimestamp')
 assert meta['name']=='traefik-dashboard-config' and meta['namespace']=='traefik' and isinstance(before.get('data'),dict)
 encoded=base64.b64encode(PUBLIC_CONTENT.encode()).decode();changed=False
 if PUBLIC_KEY in before['data']:
  assert before['data'][PUBLIC_KEY]==encoded,'Conflicting public redirect key; existing value retained'
 elif args.apply:
  assert not before.get('immutable',False),'Immutable native Secret retained'
  patch=[{'op':'test','path':'/metadata/uid','value':meta['uid']},{'op':'test','path':'/metadata/resourceVersion','value':meta['resourceVersion']},
         {'op':'add','path':'/data/'+PUBLIC_KEY,'value':encoded}]
  response=call(['-n','traefik','patch','secret','traefik-dashboard-config','--type=json','--patch-file=/dev/stdin','-o','json'],json.dumps(patch).encode())
  assert response['metadata']['uid']==meta['uid'] and response['data'][PUBLIC_KEY]==encoded and preserved(response)==preserved(before)
  changed=True
 else:raise AssertionError('Public redirect key absent; explicit apply is required')
 after=call(['-n','traefik','get','secret','traefik-dashboard-config','-o','json'])
 assert after['metadata']['uid']==meta['uid'] and after['data'][PUBLIC_KEY]==encoded and preserved(after)==preserved(before)
 current=provider();assert current['metadata']['uid']==deployment['metadata']['uid'] and current['spec']==deployment['spec']
 print(json.dumps({'passed':True,'changed':changed,'secretUID':meta['uid'],'publicKey':PUBLIC_KEY,'publicContentSHA256':hashlib.sha256(PUBLIC_CONTENT.encode()).hexdigest(),
  'otherSecretFieldsPreserved':True,'privateValuesWrittenToDiskOrOutput':False,'deploymentChanged':False,'bortusReleaseSuspended':True}))

if __name__=='__main__':
 try:main()
 except Exception as error:
  print(json.dumps({'passed':False,'errorType':type(error).__name__,'privateValuesWrittenToDiskOrOutput':False}));sys.exit(1)
