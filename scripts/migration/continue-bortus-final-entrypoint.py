"""Continue an undispatched stopped release after the exact guard-format correction."""
import hashlib,importlib.util,json,os,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).parent
def load(name,file):
 s=importlib.util.spec_from_file_location(name,ROOT/file);m=importlib.util.module_from_spec(s);sys.modules[name]=m;s.loader.exec_module(m);return m
def main():
 p=load('continue_release','execute-bortus-final-release.py');ph=load('continue_phase','bortus-quiescent-phase.py');m=load('continue_http','verify-bortus-production.py')
 run='5f5d0dd7b5a1';directory=p.A/'recovery/bortus-checkpoints'/run;j=json.loads((directory/'journal.json').read_bytes());q=ph.interval.quiescent
 m.need(j['quiescent']['state']=='guard-transition-open' and 'final_binding' not in j['quiescent'] and not (directory/'entrypoint-publication.json').exists())
 m.need(j['owned_holder_removed'] and j['cold_snapshot_ready'] and j['encrypted_nas_backup_complete'] and j['sqlite_archive_state']=='confirmed')
 cipher=j['sqlite_archive'];m.need(hashlib.sha256(Path(cipher['artifact']).read_bytes()).hexdigest()==cipher['ciphertext_sha256'] and cipher['nas_ciphertext_equal'])
 backup=m.kube('get','backups.longhorn.io',j['backup_name'],'-n','longhorn-system','-o','json');m.need(backup['metadata']['uid']==j['backup_identity']['uid'] and backup['status']['state']=='Completed' and not backup['status'].get('error'))
 controls={};watch=json.loads((directory/'control-watch.json').read_bytes());latest={k:v['resourceVersion'] for k,v in watch['initial'].items()}
 for event in watch['observations']:
  if 'value' in event:latest[event['resource']]=event['resourceVersion']
 transport=ph.interval.watch.TLSControls(ph.interval.archive.credentials.OperatorMTLSOptions(str(p.R/'admin.conf')))
 # Replay retained control history through each current object, rejecting a history gap,
 # identity/spec change or any intermediate writer restart; never invent continuity.
 for key in q.CONTROL_KEYS:
  kind,name,ns,field=q.cold.RESOURCES[key];obj=m.kube('get',kind,name,'-n',ns,'-o','json');expected={'deployment':0,'helmrelease':True,'kustomization':False}[key];pin=watch['pins'][key]
  def check(o):m.need(o['metadata']['uid']==pin['uid'] and q.control_spec(o,key)==pin['spec_sha256'] and o['spec'].get(field,False)==expected and not o['metadata'].get('deletionTimestamp'))
  check(obj);rv=latest[key];target=obj['metadata']['resourceVersion'];connection=response=None
  try:
   connection,response=transport.request(key,{'watch':'true','allowWatchBookmarks':'true','fieldSelector':'metadata.name='+name,'resourceVersion':rv,'timeoutSeconds':'30'},time.monotonic()+35)
   while rv!=target:
    event=json.loads(response.readline(1024*1024))
    if event['type']=='BOOKMARK':continue
    if event['type']!='MODIFIED':raise RuntimeError('control_history_'+key+'_'+event['type']+'_'+str(event.get('object',{}).get('code')))
    check(event['object']);rv=event['object']['metadata']['resourceVersion']
   controls[key]=obj
  finally:
   if response:response.close()
   if connection:connection.close()
 pods=m.kube('get','pods','-n','bortus','-o','json')['items'];m.need(not any(q.cold.preflight.uses_claim(x) and x['status']['phase'] not in ('Succeeded','Failed') for x in pods))
 for kind,source in [('pvc','claim'),('pv','pv')]:
  ident=j['baseline']['identities'][source];o=m.kube('get',kind,ident['name'],*(['-n','bortus'] if kind=='pvc' else []),'-o','json');m.need(o['metadata']['uid']==ident['uid'] and q.sha(o['spec'])==j['baseline']['quiescent_storage_pins'][kind]['spec_sha256'])
 binding=json.loads((directory/'phase-qualification.json').read_bytes())['bindings']['forward-compatible'];api=ph.admission.API(ph.interval.archive.credentials.OperatorMTLSOptions(str(p.R/'admin.conf')))
 for expected in ph.validator.reviewed_renders(binding['contract']):
  actual=api.guard(expected['kind'],expected['metadata']['name'],deadline=time.monotonic()+15);policy=expected['kind']==ph.validator.POLICY;pin=binding['policy_pins'][expected['metadata']['name']];m.need(actual['metadata']['uid']==pin['uid' if policy else 'binding_uid'])
  spec=actual['spec']
  if policy:
   av=next(v for v in spec['variables'] if v['name']=='approvedImages');ev=next(v for v in expected['spec']['variables'] if v['name']=='approvedImages');m.need(json.loads(av['expression'])==json.loads(ev['expression']) and p.LEGACY not in json.loads(av['expression']));av['expression']=ev['expression'];m.need(actual['status']['observedGeneration']==actual['metadata']['generation'] and not actual['status'].get('typeChecking',{}).get('expressionWarnings'))
  m.need(ph.validator.canonical_spec(expected['kind'],spec)==ph.validator.canonical_spec(expected['kind'],expected['spec']))
 p.load('continue_node_images','verify-bortus-current-node-image.py').verify(time.monotonic()+120)
 for key,old in controls.items():
  kind,name,ns,_=q.cold.RESOURCES[key];current=m.kube('get',kind,name,'-n',ns,'-o','json');m.need(current['metadata']['uid']==old['metadata']['uid'] and current['spec']==old['spec'])
 rel='flux/releases/bortus.yaml';path=p.CHARTS/rel;text=path.read_text();m.need(text.count('  suspend: true')==1 and p.IMAGE in text and 'guardedAdoption: false' in text)
 paths=['flux/releases/bortus-restore-maintenance/bortus-kv-guard-'+x+'-policy.json' for x in ('pods','templates','cronjobs')]+[rel]
 m.need(not p.git('diff','--cached','--name-only') and p.git('rev-parse','HEAD')==p.git('ls-remote','origin','refs/heads/main').split()[0])
 p.write_once(directory/'entrypoint-continuation-intent.json',{'history_replayed':True,'guard_difference':'JSON whitespace only; approved image values unchanged','original_image_still_denied':True,'backup_verified':True,'image':p.IMAGE})
 path.write_text(text.replace('  suspend: true','  suspend: false'));p.git('diff','--check','--',*paths);p.git('add','--',*paths);p.git('commit','--only','-m','Deploy qualified BORTUS and preserve canonical guard expressions','--',*paths);commit=p.git('rev-parse','HEAD');p.git('push','origin','HEAD:refs/heads/main')
 p.write_once(directory/'entrypoint-publication.json',{'revision':commit,'image':p.IMAGE,'guarded_adoption':False,'continuation_history_replayed':True})
 print(json.dumps({'entrypoint_published':True,'revision':commit,'image':p.IMAGE}))
if __name__=='__main__':main()
