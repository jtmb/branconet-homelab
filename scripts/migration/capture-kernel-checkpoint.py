"""Bind the actual fresh kernel-maintenance backups to original live identities.

Read-only cluster operations; only a new protected metadata manifest is written.
See docs/KERNEL202-MAINTENANCE.md. Never reuse a partial backup prefix.
"""
import datetime
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import runpy
import subprocess

F=Path('/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025')
H=F/'platform-upstream-review-20261027/autonomous-hardening-20261028'
SUCCESSOR_SHA='d7003cd81b0fcf7ee0596d2abb603775cb52fb19ef1ab08da976e4ff022c1d22'

def kubernetes_successor(rows,nodes,sources,evidence_path,evidence_sha,sha,digest):
 successor=H/'kernel-current58-manifest-concurrent-ingenium.json'
 assert sha(successor)==SUCCESSOR_SHA,'Immutable successful kernel successor changed'
 original=json.loads(successor.read_text())
 assert nodes==original['clusterNodes'] and sources==original['ephemeralSources']
 assert len(rows)==len(original['identities'])==219
 assert evidence_path and evidence_path.resolve()==evidence_path and H in evidence_path.parents
 assert sha(evidence_path)==evidence_sha
 evidence=json.loads(evidence_path.read_text())
 assert evidence['schema']=='kubernetes1372-flare-spec-transition-v1'
 key=lambda r:(r['kind'],r['namespace'],r['name'],r['uid'])
 before={key(r):r for r in original['identities']};after={key(r):r for r in rows}
 assert len(before)==len(after)==219 and before.keys()==after.keys()
 target=('Deployment','plex','flaresolverr','7a6239d9-8a48-40ec-9480-dd4e8667f695')
 assert evidence['identity']==dict(zip(('kind','namespace','name','uid'),target))
 specs=[]
 for field in ('beforeSpec','afterSpec'):
  reference=evidence[field];path=Path(reference['path'])
  assert path.resolve()==path and H in path.parents and sha(path)==reference['sha256']
  specs.append(json.loads(path.read_text()))
 old_spec,new_spec=specs
 assert digest(old_spec)==before[target]['specSHA256'] and digest(new_spec)==after[target]['specSHA256']
 expected=copy.deepcopy(old_spec);pod=expected['template']['spec']
 assert len(pod['containers'])==1 and pod['containers'][0]['name']=='flaresolverr'
 pod['securityContext']={'runAsNonRoot':True,'runAsUser':1000,'runAsGroup':1000,'seccompProfile':{'type':'RuntimeDefault'}}
 pod['containers'][0]['securityContext']={'allowPrivilegeEscalation':False,'capabilities':{'drop':['ALL']}}
 assert expected==new_spec,'Flare transition contains an unreviewed spec change'
 assert before[target]['specSHA256']!=after[target]['specSHA256'],'Require the actual reviewed transition'
 normalized=copy.deepcopy(after);normalized[target]['specSHA256']=before[target]['specSHA256']
 assert normalized==before,'Other projected identities or controller/volume specs changed'
 return {'generation':'kubernetes1372','predecessor':{'path':str(successor),'sha256':SUCCESSOR_SHA},'flareTransitionEvidence':{'path':str(evidence_path),'sha256':evidence_sha},'unchangedOtherIdentityRows':218}

def ingenium_successor(rows,nodes,sources,evidence_path,evidence_sha,sha,digest):
 predecessor=H/'kubernetes1372-current58-manifest.json'
 predecessor_sha='7de0db518a9d913ff4efd9b4fc36bc9667956daaeba7f07417e21ea870a99902'
 assert sha(predecessor)==predecessor_sha,'Immutable Kubernetes checkpoint changed'
 original=json.loads(predecessor.read_text())
 assert nodes==original['clusterNodes'] and sources==original['ephemeralSources']
 assert len(rows)==len(original['identities'])==219
 assert evidence_path and evidence_path.resolve()==evidence_path and H in evidence_path.parents and sha(evidence_path)==evidence_sha
 evidence=json.loads(evidence_path.read_text())
 assert evidence['schema']=='kubernetes1372-current-ingenium-spec-transition-v1'
 target=('Deployment','ingenium','ingenium','399abce7-cf4e-49d5-a743-a3e647390d9c')
 assert evidence['identity']==dict(zip(('kind','namespace','name','uid'),target))
 key=lambda r:(r['kind'],r['namespace'],r['name'],r['uid'])
 before={key(r):r for r in original['identities']};after={key(r):r for r in rows}
 assert len(before)==len(after)==219 and before.keys()==after.keys()
 assert before[target]['specSHA256']=='5ede791bee9db31642cf0e2c8d011eeba8412cadc4890bfd1f3a804dd6fb403e'
 assert after[target]['specSHA256']=='5126c66d81b7111d52b72a09cab676fba71dc12d29d07bd0d403333b247ceb10'
 def bound(reference):
  path=Path(reference['path']);assert path.resolve()==path and H in path.parents and sha(path)==reference['sha256']
  return json.loads(path.read_text())
 old_spec=bound(evidence['beforeSpec']);new_spec=bound(evidence['afterSpec'])
 assert digest(old_spec)==before[target]['specSHA256'] and digest(new_spec)==after[target]['specSHA256']
 # Bind the coordinator's actual chart/pipeline full-spec comparison proof too.
 bound(evidence['chartEvidence'])
 revision=evidence['chartsRevision'];assert len(revision)==40 and all(c in '0123456789abcdef' for c in revision)
 expected_image='docker.io/jtmb92/ingenium@sha256:b9484ea1ee956dd776200b8251886464364a6083b403b5d63447d736c94c5c64'
 assert evidence['expectedImage']==expected_image
 annotations=evidence['expectedChecksumAnnotations']
 assert set(annotations)=={'checksum/bootstrap-installer','checksum/lan-gateway'}
 assert all(len(v)==64 and all(c in '0123456789abcdef' for c in v) for v in annotations.values())
 expected=copy.deepcopy(old_spec);pod=expected['template']['spec']
 assert [c['name'] for c in pod['containers']]==['ingenium']
 assert [c['name'] for c in pod['initContainers']]==['prepare-bootstrap-ownership']
 pod['containers'][0]['image']=expected_image;pod['initContainers'][0]['image']=expected_image
 actual_annotations=expected['template']['metadata'].setdefault('annotations',{})
 assert {k for k in actual_annotations if k.startswith('checksum/')}==set(annotations)
 actual_annotations.update(annotations)
 commands=evidence.get('reviewedCommands',{})
 assert set(commands)<= {'containers/ingenium','initContainers/prepare-bootstrap-ownership'}
 for location,transition in commands.items():
  kind,name=location.split('/');container=next(c for c in pod[kind] if c['name']==name)
  assert set(transition)=={'before','after'} and container.get('command')==transition['before']
  assert isinstance(transition['after'],list) and transition['after'] and all(isinstance(v,str) for v in transition['after'])
  container['command']=transition['after']
 assert expected==new_spec,'Unreviewed Ingenium principal, mount, resource, argument, environment, selector or other spec transition'
 normalized=copy.deepcopy(after);normalized[target]['specSHA256']=before[target]['specSHA256']
 assert normalized==before,'Other 218 projected rows or original identity changed'
 return {'generation':'kubernetes1372-current-ingenium','predecessor':{'path':str(predecessor),'sha256':predecessor_sha},'ingeniumTransitionEvidence':{'path':str(evidence_path),'sha256':evidence_sha},'chartsRevision':revision,'expectedImage':expected_image,'expectedChecksumAnnotations':annotations,'unchangedOtherIdentityRows':218}

def main():
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--generation',choices=['kernel202','kubernetes1372','kubernetes1372-current-ingenium'],default='kernel202')
 parser.add_argument('--flare-transition-evidence',type=Path);parser.add_argument('--flare-transition-evidence-sha256')
 parser.add_argument('--ingenium-transition-evidence',type=Path);parser.add_argument('--ingenium-transition-evidence-sha256')
 args=parser.parse_args()
 if args.generation=='kubernetes1372':assert args.flare_transition_evidence and args.flare_transition_evidence_sha256
 else:assert args.flare_transition_evidence is None and args.flare_transition_evidence_sha256 is None
 if args.generation=='kubernetes1372-current-ingenium':assert args.ingenium_transition_evidence and args.ingenium_transition_evidence_sha256
 else:assert args.ingenium_transition_evidence is None and args.ingenium_transition_evidence_sha256 is None
 assert os.geteuid()==1000 and F.is_mount()
 os.umask(0o077)
 repo=Path(__file__).resolve().parents[2]
 helper=repo/'k8s-rewrite/ansible-playbook/roles/security_maintenance/files/kernel_checkpoint.py'
 lib=runpy.run_path(str(helper));sha=lib['file_hash'];digest=lib['digest']
 native=json.loads((H/'kernel-active-volume-checkpoint.json').read_text())
 assert native['status']=='completed' and native['checkpoint_prefix']=='k202-settled-20261028' and len(native['volumes'])==28
 rows=lib['project'](lib['get']('persistentvolumeclaims,persistentvolumes,volumes.longhorn.io,deployments,statefulsets,daemonsets'))
 lib['validate_inventory'](rows)
 claims=lib['get']('persistentvolumeclaims')
 original=json.loads((F/'platform-upstream-review-20261027/final-fleet-post-security-20261028/inventory.json').read_text())
 assert {(x['metadata']['namespace'],x['metadata']['name'],x['metadata']['uid'],x['spec']['volumeName']) for x in claims}=={(x['namespace'],x['name'],x['uid'],x['volumeName']) for x in original['claims']}
 backups=[b for b in lib['get']('backups.longhorn.io') if b['metadata'].get('labels',{}).get('security-maintenance-checkpoint')==native['checkpoint_prefix']]
 assert len(backups)==28
 volumes={r['name']:r for r in rows if r['kind']=='Volume' and r['state']=='attached'}
 assert set(volumes)=={b['status']['volumeName'] for b in backups}
 prefix=args.generation if args.generation in ('kubernetes1372','kubernetes1372-current-ingenium') else 'kernel'
 cp_choices=list((H/(prefix+'-control-plane-backup')).glob('control-plane-*/receipt.json'));assert len(cp_choices)==1
 cp=cp_choices[0];control=json.loads(cp.read_text());nas=H/(prefix+'-control-plane-nas-proof.json')
 manifest={'schema':'kernel202-current58-v1','capturedAt':datetime.datetime.now(datetime.timezone.utc).isoformat(),'identities':rows,'clusterNodes':{x['metadata']['name']:x['metadata']['uid'] for x in lib['get']('nodes')},'ephemeralSources':lib['ephemeral_sources'](),
  'nativeBackups':[{'name':b['metadata']['name'],'uid':b['metadata']['uid'],'volume':b['status']['volumeName'],'volumeUID':volumes[b['status']['volumeName']]['uid'],'statusSHA256':digest(lib['backup_identity'](b['status']))} for b in backups],
  'controlPlane':{'receipt':str(cp),'receiptSHA256':sha(cp),'archiveSHA256':control['archive_sha256'],'source':control['source'],'nasProof':str(nas),'nasProofSHA256':sha(nas)}}
 if args.generation=='kubernetes1372':
  manifest['successorEvidence']=kubernetes_successor(rows,manifest['clusterNodes'],manifest['ephemeralSources'],args.flare_transition_evidence,args.flare_transition_evidence_sha256,sha,digest)
 elif args.generation=='kubernetes1372-current-ingenium':
  manifest['successorEvidence']=ingenium_successor(rows,manifest['clusterNodes'],manifest['ephemeralSources'],args.ingenium_transition_evidence,args.ingenium_transition_evidence_sha256,sha,digest)
 lib['validate'](manifest,rows,backups,control)
 path=H/(prefix+'-current58-manifest.json');assert not path.exists()
 with path.open('x') as out:json.dump(manifest,out,indent=2)
 authority=sha(path)
 r=subprocess.run([str(F.parent/'venv/bin/python3.12'),'-B',str(helper),'--manifest',str(path),'--sha256',authority],capture_output=True,text=True,timeout=180)
 assert r.returncode==0,('Actual checkpoint validation failed',r.stderr[-2000:])
 print(json.dumps({'manifest':str(path),'sha256':authority,'validation':json.loads(r.stdout)}))

if __name__=='__main__':main()
