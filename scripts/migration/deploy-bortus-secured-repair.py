"""Publish only the qualified BORTUS readiness repair through the existing private CI."""
import importlib.util,json,time
from pathlib import Path
S=Path(__file__).parent
def load(name,file):
 s=importlib.util.spec_from_file_location(name,S/file);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
def main():
 m=load('repair_acceptance','verify-bortus-production.py');p=load('repair_charts','execute-bortus-final-release.py');q=json.loads(m.QUALIFIED.read_bytes());m.need(q['all_three_nodes_verified'] and q['current_unfiltered_security_scan_passed']);image=m.IMAGE
 m.need(not(m.A/'production-repair-publication.json').exists());old=p.IMAGE
 dep=m.kube('get','deployment','bortus','-n','bortus','-o','json');claim=m.kube('get','pvc','bortus-data','-n','bortus','-o','json');hr=m.kube('get','helmrelease','bortus','-n','flux-system','-o','json')
 m.need(dep['metadata']['uid']=='4deedc67-038a-4f82-a2d4-a83af316f2f6' and dep['spec']['template']['spec']['containers'][0]['image']==old and claim['metadata']['uid']=='19cc4b60-4536-4d80-8789-e27b5ad48b79' and hr['metadata']['uid']=='bed3008a-474f-411e-9956-1248e3718220' and hr['spec']['values']['nativeKv']['guardedAdoption']is False and not hr['spec'].get('suspend',False))
 paths=['flux/releases/bortus-restore-maintenance/bortus-kv-guard-'+x+'-policy.json'for x in ('pods','templates','cronjobs')]+['flux/releases/bortus.yaml']
 m.need(not p.git('diff','--cached','--name-only') and p.git('rev-parse','HEAD')==p.git('ls-remote','origin','refs/heads/main').split()[0] and not p.git('diff','--name-only','--',*paths))
 replacements={}
 for rel in paths[:-1]:
  path=p.CHARTS/rel;raw=path.read_text();d=json.loads(raw);v=next(v for v in d['spec']['variables']if v['name']=='approvedImages');images=json.loads(v['expression']);m.need(old in images and p.LEGACY not in images and image not in images)
  # Keep the existing canonical expression and every unrelated policy byte.
  before=v['expression']
  after=json.dumps(images+[image]);encoded=json.dumps(before);m.need(raw.count(encoded)==1);replacements[rel]=raw.replace(encoded,json.dumps(after))
 rel=paths[-1];raw=(p.CHARTS/rel).read_text();m.need(raw.count(old)==1 and 'guardedAdoption: false'in raw and 'sourceCommit: 12dce115006877fed2c674cad1ffd40805932974'in raw);replacements[rel]=raw.replace(old,image).replace('sourceCommit: 12dce115006877fed2c674cad1ffd40805932974','sourceCommit: '+q['source'])
 m.save('production-repair-intent.json',{'image':image,'source':q['source'],'original_pvc':claim['metadata']['uid'],'schema_parent':old,'adoption':False,'paths':paths,'legacy_image_remains_denied':True})
 for rel,raw in replacements.items():(p.CHARTS/rel).write_text(raw)
 p.git('diff','--check','--',*paths);p.git('add','--',*paths);p.git('commit','--only','-m','Repair empty BORTUS metadata lists and update runtime security tools','--',*paths);commit=p.git('rev-parse','HEAD');p.git('push','origin','HEAD:refs/heads/main');m.need(p.git('ls-remote','origin','refs/heads/main').split()[0]==commit)
 m.save('production-repair-publication.json',{'revision':commit,'image':image,'source':q['source'],'guarded_adoption':False,'paths':paths});print(json.dumps({'published':True,'revision':commit,'image':image}),flush=True)
 until=time.monotonic()+900
 while time.monotonic()<until:
  status=json.loads(p.STATUS.read_bytes());m.need(not(status.get('sourceSHA')==commit and status.get('passed')is False and (status.get('phase','').startswith('failed') or status.get('phase')in('check_failed','publish_failed'))))
  repo=m.kube('get','gitrepository','branconet-charts','-n','flux-system','-o','json');owner=m.kube('get','kustomization','migration-releases','-n','flux-system','-o','json');dep=m.kube('get','deployment','bortus','-n','bortus','-o','json');rev='validated@sha1:'+commit
  if status.get('sourceSHA')==commit and status.get('passed')is True and status.get('actionsUsed')is False and repo.get('status',{}).get('artifact',{}).get('revision')==rev and owner.get('status',{}).get('lastAppliedRevision')==rev and dep['spec']['template']['spec']['containers'][0]['image']==image and dep['status'].get('readyReplicas')==1:
   print(json.dumps({'repair_ready':True,'revision':commit,'image':image}));return
  time.sleep(3)
 raise RuntimeError('repair_reconciliation_timeout_inspect_before_retry')
if __name__=='__main__':main()
