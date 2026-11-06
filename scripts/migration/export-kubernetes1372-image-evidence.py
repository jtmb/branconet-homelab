"""Project complete native alias results; preserve their original authority."""
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import runpy

F=Path('/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025')
H=F/'platform-upstream-review-20261027/autonomous-hardening-20261028'

def ref(path):
 assert path.resolve()==path and F in path.parents and path.is_file()
 return {'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}

def save(path,value):
 with path.open('x') as stream:json.dump(value,stream,indent=2)
 return ref(path)

def main():
 os.umask(0o077)
 repo=Path(__file__).resolve().parents[2]
 directory=repo/'k8s-rewrite/ansible-playbook/roles/kubernetes1372_vendor_preload/files'
 source=directory/'aliases.py'; vendor=runpy.run_path(str(directory/'controller.py'))
 bound={'path':str(source),'sha256':hashlib.sha256(source.read_bytes()).hexdigest()}; roots=vendor['H']; successful=[]
 for p in roots.glob('aliases-create-*.json'):
  d=json.loads(p.read_text())
  if d['accepted'] and d['sourceSHA256']==bound['sha256']:successful.append((p,d))
 assert len(successful)==1
 p,d=successful[0]; captured=d['clusterAfter']['timestamp']
 age=dt.datetime.now(dt.timezone.utc)-dt.datetime.fromisoformat(captured)
 assert dt.timedelta(0)<=age<=dt.timedelta(hours=6)
 output=H/'kubernetes1372-image-evidence';output.mkdir(mode=0o700,exist_ok=False)
 save(output/'ownership.json',{'owner':'kubernetes1372-security-patch','physicalRoot':str(F),
  'generatedPaths':['ownership.json','COMPONENT-NODE.json','images.json'],
  'lastConsumer':'Native patch independent authority and recovery verification',
  'regeneration':'Project immutable accepted native alias receipts with this script',
  'protected':'Original prestage, before/intent/after and failed results are never rewritten',
  'peakBytes':1024**2,'source':{'path':str(Path(__file__)),'sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}})
 images={}
 for component,entry in vendor['BINDINGS'].items():
  images[component]={}
  for alias,node in [('master','masternode'),('worker2','workernode2'),('worker1','workernode1')]:
   raw=roots/('alias-'+component+'-'+alias+'-result.json'); actual=json.loads(raw.read_text())
   assert actual['accepted'] and not actual['errors'] and actual['sourceSHA256']==bound['sha256']
   after=actual['after']; tag='registry.k8s.io/'+component+':v1.37.2'
   assert after['node']==alias and after['hostname']==node and after['fullyCached'] and after['fits']
   assert after['alias']==tag and after['aliasPresent'] and after['cri']['id']==entry['config']
   assert tag in after['cri']['repoTags'] and any('registry.k8s.io/'+component+'@'+x in after['cri']['repoDigests'] for x in [vendor['PINS'][component]['root'],entry['amd64']])
   row={'capturedAt':captured,'node':node,'nodeUID':d['clusterAfter']['nodes'][alias]['uid'],
    'runtimeEndpoint':'unix:///run/containerd-k8s/containerd.sock','amd64Digest':entry['amd64'],
    'configDigest':entry['config'],'tag':tag,'present':True,'actualAliasResult':ref(raw),
    'completeAliasOperation':ref(p),'aliasController':bound,'projectionOnly':True}
   images[component][node]=save(output/(component+'-'+node+'.json'),row)
 print(json.dumps(save(output/'images.json',{'images':images})))

if __name__=='__main__':main()
