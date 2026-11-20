"""Scoped actual native-KV release exercise, persistence check and owned fixture cleanup."""
import argparse,base64,importlib.util,json,os,secrets,subprocess,sys,uuid
from pathlib import Path
ROOT=Path(__file__).parent
spec=importlib.util.spec_from_file_location('live_bortus_http',ROOT/'verify-bortus-production.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
STATE=m.A/'production-native-probe.json'
def read():return json.loads(STATE.read_bytes())
def save(v,first=False):
 fd=os.open(STATE,os.O_WRONLY|os.O_NOFOLLOW|(os.O_CREAT|os.O_EXCL if first else os.O_TRUNC),0o600)
 with os.fdopen(fd,'w') as f:json.dump(v,f);f.flush();os.fsync(f.fileno())
def text(reply):
 field=next(x for x in reply['fields'] if x['field']=='probe');return base64.b64decode(field['value']).decode() if field['encoding']=='base64' else field['value']
def prerequisites(status,revision):return {'resourceVersion':status['resourceVersion'],'expectedHead':status['head'],'pathRevision':revision}
def exercise():
 suffix=uuid.uuid4().hex[:12];state={'state':'pending','suffix':suffix,'namespace':'bortus-secrets','secret_name':'bortus-release-probe-'+suffix,'logical_path':'release/'+suffix,'steps':[],'temporary_user_id':None,'policy_id':None,'native_cleanup_complete':False};save(state,True)
 with m.production('native-exercise') as (api,identity):
  readonly=None
  try:
   mount=api.call('POST','/api/kv/mounts',{'name':'release-'+suffix,'namespaces':[state['namespace']]},expected=(201,));state['mount_id']=mount['id'];save(state)
   path=api.call('POST','/api/kv/paths',{'mountId':mount['id'],'path':state['logical_path'],'namespace':state['namespace'],'name':state['secret_name'],'fields':[{'field':'probe','key':'probe'}],'retention':5},expected=(201,));state['path_id']=path['id'];state['path_revision']=path['revision'];save(state)
   absent=subprocess.run(m.K+['get','secret',state['secret_name'],'-n',state['namespace'],'--ignore-not-found','-o','json'],capture_output=True,timeout=25);m.need(absent.returncode==0 and not absent.stdout.strip())
   base='/api/kv/paths/'+path['id'];first='release-first-'+suffix;second='release-second-'+suffix
   created=api.call('POST',base+'/data',{'resourceVersion':'absent','expectedHead':0,'pathRevision':path['revision'],'fields':[{'field':'probe','encoding':'utf8','value':first}]},expected=(201,));state['steps'].append('native-create');save(state)
   old=api.call('GET',base+'/status');m.need(old['head']==1 and old['guardedAdoption'] is True)
   m.need(text(api.call('GET',base+'/data'))==first)
   changed=api.call('PUT',base+'/data',{**prerequisites(old,path['revision']),'fields':[{'field':'probe','encoding':'utf8','value':second}]});state['steps'].append('native-update');save(state)
   api.call('PUT',base+'/data',{**prerequisites(old,path['revision']),'fields':[{'field':'probe','encoding':'utf8','value':'must-not-write'}]},expected=(409,));state['steps'].append('stale-CAS-denied')
   m.need(text(api.call('GET',base+'/versions/1/data'))==first)
   current=api.call('GET',base+'/status');m.need(current['head']==2)
   api.call('POST',base+'/rollback',{**prerequisites(current,path['revision']),'version':1});m.need(text(api.call('GET',base+'/data'))==first);state['steps'].extend(['historical-read','rollback']);save(state)
   password=secrets.token_urlsafe(24);username='release_ro_'+suffix
   user=api.call('POST','/api/users',{'username':username,'password':password,'role':'readonly'},expected=(201,));state['temporary_user_id']=user['id'];save(state)
   readonly=m.API();readonly.call('POST','/api/auth/login',{'username':username,'password':password});password=None
   session=readonly.call('GET','/api/auth/session');m.need(session['authenticated'] and session['role']=='readonly' and session['engineAdmin'] is False)
   readonly.call('GET',base+'/data',expected=(403,));readonly.call('PUT',base+'/data',{**prerequisites(api.call('GET',base+'/status'),path['revision']),'fields':[]},expected=(403,));state['steps'].append('readonly-values-and-writes-denied')
   policy=api.call('POST','/api/kv/policies',{'principal':'user:'+identity['id'],'mountId':mount['id'],'prefix':state['logical_path'],'effect':'deny','actions':['read']},expected=(201,));state['policy_id']=policy['id'];state['policy_revision']=policy['revision'];save(state)
   api.call('GET',base+'/data',expected=(403,));state['steps'].append('explicit-policy-deny-overrides-allow')
   api.call('DELETE','/api/kv/policies/'+policy['id'],{'revision':policy['revision']});state['policy_id']=None;save(state)
   m.need(text(api.call('GET',base+'/data'))==first)
   versions=api.call('GET',base+'/versions');m.need(versions['head']==3 and len(versions['items'])==3)
   state.update(state='awaiting-production-restart',canonical_uid=versions['uid'],expected_head=3,expected_value=first);save(state)
  finally:
   if state.get('policy_id'):
    api.call('DELETE','/api/kv/policies/'+state['policy_id'],{'revision':state['policy_revision']});state['policy_id']=None;save(state)
   if state.get('temporary_user_id'):
    api.call('DELETE','/api/users/'+state['temporary_user_id']);state['temporary_user_id']=None;save(state)
    if readonly:readonly.call('GET','/api/kv/mounts',expected=(401,));state['steps'].append('deleted-test-session-revoked');save(state)
  print(json.dumps({'native_create_update_history_rollback_passed':True,'stale_cas_denied':True,'readonly_and_explicit_policy_denied':True,'temporary_user_removed':True,'restart_persistence_pending':True}))
def after_restart(cleanup):
 state=read();m.need(state['state']=='awaiting-production-restart')
 with m.production('native-restart') as (api,identity):
  base='/api/kv/paths/'+state['path_id'];versions=api.call('GET',base+'/versions');m.need(versions['uid']==state['canonical_uid'] and versions['head']==state['expected_head'] and text(api.call('GET',base+'/data'))==state['expected_value'])
  state['steps'].append('real-pod-replacement-persistence');save(state)
  if cleanup:
   status=api.call('GET',base+'/status');api.call('DELETE',base+'/data',{**prerequisites(status,state['path_revision']),'confirmPath':state['logical_path']})
   versions=api.call('GET',base+'/versions');status=api.call('GET',base+'/status');m.need(status['tombstone'] is True and versions['uid']==state['canonical_uid'])
   selected=[{'version':v['version'],'name':v['name'],'uid':v['uid']} for v in versions['items']]
   result=api.call('POST',base+'/destroy',{**prerequisites(status,state['path_revision']),'confirmPath':state['logical_path'],'versions':[v['version'] for v in selected],'sourceUid':state['canonical_uid'],'histories':selected});m.need(result['cleanupComplete'] is True)
   source=m.kube('get','secret',state['secret_name'],'-n',state['namespace'],'-o','json');m.need(source['metadata']['uid']==state['canonical_uid'] and not source.get('data') and not source['metadata'].get('ownerReferences'))
   for item in selected:
    response=subprocess.run(m.K+['get','secret',item['name'],'-n','bortus-history','--ignore-not-found','-o','json'],capture_output=True,timeout=25);m.need(response.returncode==0 and not response.stdout.strip())
   options={'apiVersion':'v1','kind':'DeleteOptions','preconditions':{k:source['metadata'][k] for k in ('uid','resourceVersion')}}
   response=subprocess.run(m.K+['delete','--raw','/api/v1/namespaces/'+state['namespace']+'/secrets/'+state['secret_name'],'-f','-'],input=json.dumps(options).encode(),capture_output=True,timeout=25);m.need(response.returncode==0)
   state.update(state='completed',native_cleanup_complete=True,expected_value=None,retained_metadata='Minimal product audit/operation/path metadata; no value payloads or test account retained');save(state)
  print(json.dumps({'real_restart_persistence_passed':True,'owned_native_values_and_histories_removed':cleanup,'temporary_credentials_retained':False}))
if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('mode',choices=['exercise','after-restart-cleanup']);args=parser.parse_args()
 try:exercise() if args.mode=='exercise' else after_restart(True)
 except Exception as error:
  import traceback
  print(json.dumps({'native_acceptance_failed':type(error).__name__,'locations':[Path(f.filename).name+':'+str(f.lineno) for f in traceback.extract_tb(error.__traceback__)]}),file=sys.stderr);raise SystemExit(1)
