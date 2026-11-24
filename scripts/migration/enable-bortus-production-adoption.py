"""Publish only the approved native-value adoption switch after deployed RBAC checks."""
import importlib.util,json,subprocess,time
from pathlib import Path
ROOT=Path(__file__).parent
def load(name,file):
 s=importlib.util.spec_from_file_location(name,ROOT/file);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
m=load('adoption_http','verify-bortus-production.py');p=load('adoption_release','execute-bortus-final-release.py')
def main():
 receipt=json.loads((m.A/'production-initial-acceptance.json').read_bytes())
 m.need(receipt['state']=='completed' and receipt['original_pvc_preserved'] and receipt['legacy_image_withdrawn'] and len(receipt['effective_rbac'])==9)
 preservation=json.loads((m.A/'production-forward-preservation.json').read_bytes());m.need(preservation['passed'] is True and preservation['plaintext_copies_cleaned'] is True)
 with m.production('pre-adoption') as (api,identity):m.need(api.call('GET','/api/health/ready')['status']=='ready')
 path=p.CHARTS/'flux/releases/bortus.yaml';text=path.read_text();m.need(text.count('      guardedAdoption: false')==1 and '  suspend: false' in text and m.IMAGE in text)
 m.need(not p.git('diff','--cached','--name-only'));m.need(p.git('rev-parse','HEAD')==p.git('ls-remote','origin','refs/heads/main').split()[0])
 path.write_text(text.replace('      guardedAdoption: false','      guardedAdoption: true'))
 rel='flux/releases/bortus.yaml';p.git('diff','--check','--',rel);p.git('add','--',rel);p.git('commit','--only','-m','Enable verified BORTUS native value adoption','--',rel)
 commit=p.git('rev-parse','HEAD');p.git('push','origin','HEAD:refs/heads/main');m.need(p.git('ls-remote','origin','refs/heads/main').split()[0]==commit)
 m.save('production-adoption-publication.json',{'revision':commit,'image':m.IMAGE,'guarded_adoption':True,'rbac_and_preservation_verified':True})
 until=time.monotonic()+650
 while time.monotonic()<until:
  status=json.loads(p.STATUS.read_bytes());repo=m.kube('get','gitrepository','branconet-charts','-n','flux-system','-o','json');owner=m.kube('get','kustomization','migration-releases','-n','flux-system','-o','json');rev='validated@sha1:'+commit
  if status.get('sourceSHA')==commit and status.get('passed') is False and (status.get('phase','').startswith('failed') or status.get('phase')in('check_failed','publish_failed')):raise RuntimeError('adoption_validation_failed')
  if status.get('sourceSHA')==commit and status.get('passed') is True and status.get('actionsUsed') is False and repo.get('status',{}).get('artifact',{}).get('revision')==rev and owner.get('status',{}).get('lastAppliedRevision')==rev and any(c['type']=='Ready' and c['status']=='True' for c in owner.get('status',{}).get('conditions',[])):
   print(json.dumps({'adoption_publication_verified':True,'revision':commit}));return
  time.sleep(3)
 raise RuntimeError('adoption_flux_observation_timeout')
if __name__=='__main__':main()
