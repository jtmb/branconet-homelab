#!/usr/bin/env python3
"""Observe the pinned Tautulli API/Plex reads; never mutate or restart a workload."""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import stat
import subprocess
import uuid

RUNTIME = Path('/home/brajam/.local/share/branconet-migration')
SSH = ['ssh','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-o','ConnectTimeout=10',
       '-i','/home/brajam/.ssh/id_ed25519','-p','2002','james@192.168.0.4']
IMAGE = 'docker.io/library/tautulli-security-20261023@sha256:769aa67e07e35bdfe714a486591eb1a34c9ad9bd6cf2da89da130dcdab9de05a'
DEPLOYMENT = '9db52ebb-23c8-47c6-82c8-ebde3b0a2775'
RELEASE = 'e5aa088f-22a3-4f47-b7c4-094be5354bf4'
CLAIM = '97eb095e-37ec-4185-80ed-4d8f3c19f486'

# Public code is passed to the existing candidate Pod. The original API key is
# read there, used only in an HTTP header on loopback, and never returned.
POD_PROGRAM = r'''import configparser,hashlib,json,os,re,sqlite3,stat,time,urllib.error,urllib.parse,urllib.request
from pathlib import Path

def need(ok,reason):
 if not ok: raise ValueError(reason)

def main():
 # The image's exec default is root; drop only this observer process to the
 # existing data owner. The running service and its configuration are unchanged.
 if os.geteuid()==0:
  os.setgroups([]);os.setgid(1000);os.setuid(1000)
 import ctypes
 need(ctypes.CDLL(None).prctl(38,1,0,0,0)==0,'observer_no_new_privileges')
 need(os.getuid()==os.geteuid()==1000 and os.getgid()==1000 and not os.getgroups(),'candidate_uid')
 process_status=Path('/proc/self/status').read_text()
 need(re.search(r'(?m)^CapEff:\s+0+$',process_status) and re.search(r'(?m)^CapPrm:\s+0+$',process_status),'observer_capabilities')
 # Public file checksums use explicit metadata labels, not API-key assignments.
 pins={
  'api2.py': {'sha256': '9c5e10ffd8c2d8bea0075011d8879425df23ddb682bb3a5e7f58caf33c9e1389'},
  'common.py': {'sha256': '80b16f9dfc9acc33d63d4f6d7426809f00f6e1269331a5f14fd4743c0fd88489'},
  'webserve.py': {'sha256': 'b848c3234157a680715eaaa3d1d8c6e701ec89e0afb9fec8cc7906d51df90de1'},
  'pmsconnect.py': {'sha256': 'b55989a0f6b550aac4103c066d290a0b71251590dc2e133b89e9ff35a09ea83f'},
  'users.py': {'sha256': '3477e714d83e366220a095c27f90ed3f818bf06949bb702cb5172baf3e67dbf3'},
  'libraries.py': {'sha256': '65c037f267f5bc8ae28c4f1854680a7ccf77d5822257ed905954309b806b13a3'},
  'datafactory.py': {'sha256': '59ea53ee6d1b67d2faf4504adfb6a20f224d25f85a2f7614c054bd5214bc3d03'},
  'notifiers.py': {'sha256': '368c5a3220302a7d1109194c5722743191e544c297db4ecfa26691c82b8a4c71'},
 }
 for name,wanted in pins.items():
  p=Path('/app/plexpy')/name
  need(p.is_file() and not p.is_symlink() and hashlib.sha256(p.read_bytes()).hexdigest()==wanted['sha256'],'candidate_protocol_source')
 fd=os.open('/config/config.ini',os.O_RDONLY|os.O_NOFOLLOW)
 with os.fdopen(fd,'rb') as f:
  before=os.fstat(f.fileno()); raw=f.read(1024*1024+1); after=os.fstat(f.fileno())
 need(stat.S_ISREG(before.st_mode) and len(raw)<=1024*1024 and (before.st_ino,before.st_size,before.st_mtime_ns)==(after.st_ino,after.st_size,after.st_mtime_ns),'stable_config_read')
 c=configparser.ConfigParser(interpolation=None,strict=True,empty_lines_in_values=False)
 c.read_string(raw.decode('utf-8-sig'))
 def value(section,key,default=''):
  s=c.get(section,key,fallback=default).strip()
  return s[1:-1] if len(s)>=2 and s[0]==s[-1] and s[0] in ('"',"'") else s
 key=value('General','api_key')
 need(len(key)==32 and '\r' not in key and '\n' not in key and value('General','api_enabled')=='1','existing_api_configuration')
 need(value('General','enable_https','0')=='0','expected_loopback_http')
 port=int(value('General','http_port','8181')); need(1<=port<=65535,'http_port')
 root=value('General','http_root').strip('/')
 need(not root or re.fullmatch('[a-zA-Z0-9_/-]+',root),'http_root')
 base='http://127.0.0.1:'+str(port)+'/'+(root+'/' if root else '')+'api/v2'
 class NoRedirect(urllib.request.HTTPRedirectHandler):
  def redirect_request(self,*args,**kwargs): return None
 opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
 start=time.monotonic(); total=0; requests=[]
 def api(command,auth=True,**params):
  nonlocal total
  need(time.monotonic()-start<180,'overall_deadline')
  url=base+'?'+urllib.parse.urlencode({'cmd':command,'out_type':'json',**params})
  request=urllib.request.Request(url,headers={'X-Api-Key':key} if auth else {},method='GET')
  try:
   with opener.open(request,timeout=30) as response:
    status=response.status; data=response.read(4*1024*1024+1)
  except urllib.error.HTTPError as e:
   status=e.code; data=e.read(4*1024*1024+1)
  total+=len(data);need(len(data)<=4*1024*1024 and total<=16*1024*1024,'response_size')
  requests.append({'command':command,'authenticated':auth,'http_status':status,'response_bytes':len(data)})
  if not auth:
   need(status==401,'unauthenticated_api_must_reject');return None
  need(status==200,'authenticated_http_failure')
  response=json.loads(data)['response'];need(response['result']=='success','authenticated_api_failure')
  return response['data']
 api('status',auth=False)
 api('status')
 info=api('get_tautulli_info')
 need(info['tautulli_version']=='v2.18.2' and info['tautulli_python_version']=='3.13.17','expected_app_runtime')
 configured=api('get_server_info'); identifier=value('PMS','pms_identifier')
 need(identifier and configured['pms_identifier']==identifier,'configured_plex_identity')
 plex=api('get_server_identity')
 need(plex['machine_identifier']==identifier and isinstance(plex['version'],str) and plex['version'],'actual_plex_identity')
 # Query-only local SQLite reads establish the expected IDs for the API views.
 # No app module import, SQL API, checkpoint, backup, refresh or schema write.
 db=sqlite3.connect('file:/config/tautulli.db?mode=ro',uri=True,timeout=5,isolation_level=None)
 try:
  db.execute('PRAGMA query_only=ON');db.execute('PRAGMA busy_timeout=5000');db.execute('BEGIN')
  user_ids={str(r[0]) for r in db.execute('SELECT user_id FROM users WHERE deleted_user=0')}
  library_ids={str(r[0]) for r in db.execute('SELECT section_id FROM library_sections WHERE deleted_section=0')}
  # Keep every historical/local library in the API/database proof. Connectivity
  # applies to active real Plex libraries;999999 is the pinned Live TV sentinel.
  active_real_libraries={str(r[0]) for r in db.execute('SELECT section_id FROM library_sections WHERE deleted_section=0 AND is_active=1 AND section_id<>999999')}
  configured_notifiers={int(r[0]):(int(r[1]),r[2]) for r in db.execute('SELECT id,agent_id,agent_name FROM notifiers')}
  users=api('get_user_names')
  need(isinstance(users,list) and {str(x['user_id']) for x in users}==user_ids and len(users)==len(user_ids),'user_view')
  libraries=api('get_library_names')
  need(isinstance(libraries,list) and {str(x['section_id']) for x in libraries}==library_ids and len(libraries)==len(library_ids),'library_database_view')
  live_libraries=api('get_libraries')
  need(isinstance(live_libraries,list) and live_libraries and
       active_real_libraries=={str(x['section_id']) for x in live_libraries},'plex_library_connectivity')
  for x in live_libraries: need(str(x['count']).isdigit(),'plex_library_statistics')
  history=api('get_history',grouping=0,include_activity=0,length=1,start=0)
  need(isinstance(history,dict) and int(history['recordsTotal'])>0 and isinstance(history['data'],list) and len(history['data'])==1,'history_read')
  row_id=history['data'][0]['row_id']
  need(db.execute('SELECT COUNT(*) FROM session_history WHERE id=?',(row_id,)).fetchone()==(1,),'history_row_exists')
  notifiers=api('get_notifiers')
  need(isinstance(notifiers,list) and {int(x['id']):(int(x['agent_id']),x['agent_name']) for x in notifiers}==configured_notifiers,'notifier_view')
  # These pinned-source agents inherit the pure config constructor; their
  # options use only static providers/formatting, never device discovery/send.
  safe={'browser','discord','facebook','gotify','groupme','growl','ifttt','xbmc','lunasea','microsoftteams','mqtt','ntfy','plex','prowl','slack','telegram','twitter','webhook','zapier'}
  for entry in notifiers:
   need(entry['agent_name'] in safe,'notifier_config_read_requires_source_review')
   config=api('get_notifier_config',notifier_id=int(entry['id']))
   need(int(config['id'])==int(entry['id']) and int(config['agent_id'])==int(entry['agent_id'])
        and config['agent_name']==entry['agent_name'] and isinstance(config['config'],dict)
        and isinstance(config['actions'],dict) and isinstance(config['notify_text'],dict)
        and isinstance(config['config_options'],list),'notifier_configuration_read')
  db.rollback()
 finally: db.close()
 return {'passed':True,'transport':'pod-loopback-http','authentication':'existing-config-X-Api-Key-header',
  'unauthenticated_rejected':True,'app_version':'v2.18.2','python_version':'3.13.17',
  'configured_and_actual_plex_identity_match':True,'user_count':len(users),
  'stored_library_count':len(libraries),'live_plex_library_count':len(live_libraries),
  'active_real_plex_libraries_verified':len(active_real_libraries),
  'history_total':int(history['recordsTotal']),'history_sample_rows':len(history['data']),
  'notifier_count':len(notifiers),'notifier_configuration_reads':len(notifiers),
  'requests':requests,'protocol_source_sha256':pins,'real_notification_sent':False,
  'login_refresh_or_mutation_called':False,'raw_responses_or_credentials_returned':False}
try:
 print(json.dumps(main()))
except Exception as e:
 reason=str(e) if isinstance(e,ValueError) and re.fullmatch('[a-z0-9_]+',str(e)) else type(e).__name__
 print(json.dumps({'passed':False,'failure':reason,'raw_responses_or_credentials_returned':False}))
 raise SystemExit(1)
'''


def need(ok,reason):
    if not ok: raise ValueError(reason)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def private_receipt(path,wanted):
    need(path.is_absolute() and path.resolve()==path and re.fullmatch('[0-9a-f]{64}',wanted),'receipt_path_or_fingerprint')
    info=path.lstat()
    need(stat.S_ISREG(info.st_mode) and info.st_uid==os.getuid() and not info.st_mode&0o077
         and info.st_nlink==1 and info.st_size<=4*1024**2 and digest(path)==wanted,'private_receipt')
    return json.loads(path.read_bytes())


def call(argv,timeout=60):
    result=subprocess.run(SSH+[shlex.join(argv)],capture_output=True,timeout=timeout)
    need(len(result.stdout)<=4*1024**2,'metadata_bound')
    return result


def get(kind,name,namespace='plex'):
    result=call(['kubectl','--request-timeout=30s','-n',namespace,'get',kind,name,'-o','json'])
    need(result.returncode==0,'cluster_metadata_read')
    return json.loads(result.stdout)


def fence():
    dep=get('deployment','tautulli');release=get('helmrelease','tautulli','flux-system');pvc=get('pvc','tautulli-data-0')
    need(dep['metadata']['uid']==DEPLOYMENT and release['metadata']['uid']==RELEASE and pvc['metadata']['uid']==CLAIM,'original_workload_storage_identity')
    need(dep['spec'].get('replicas',1)==1 and all(dep['status'].get(k)==1 for k in ['replicas','updatedReplicas','readyReplicas','availableReplicas']),'one_ready_writer')
    need(not release['spec'].get('suspend',False) and release['status'].get('observedGeneration')==release['metadata']['generation']
         and any(c['type']=='Ready' and c['status']=='True' for c in release['status'].get('conditions',[])),'flux_release_ready')
    pods=get('pods','-l=app=tautulli')['items']
    need(len(pods)==1,'single_writer_pod');pod=pods[0]
    need(not pod['metadata'].get('deletionTimestamp') and pod['status']['phase']=='Running','writer_running')
    owners=[o for o in pod['metadata'].get('ownerReferences',[]) if o.get('controller')]
    need(len(owners)==1 and owners[0]['kind']=='ReplicaSet','writer_replicaset_owner')
    rs=get('replicaset',owners[0]['name'])
    need(rs['metadata']['uid']==owners[0]['uid'] and any(o.get('controller') and o['kind']=='Deployment' and o['uid']==DEPLOYMENT for o in rs['metadata'].get('ownerReferences',[])),'writer_deployment_owner')
    cs=pod['status'].get('containerStatuses',[]);containers=pod['spec']['containers']
    need(len(cs)==len(containers)==1 and cs[0]['ready'] and containers[0]['name']==cs[0]['name']=='tautulli'
         and containers[0]['image']==IMAGE and cs[0]['imageID'].rsplit('@',1)[-1]==IMAGE.rsplit('@',1)[-1],'exact_ready_candidate')
    need(pvc['status']['phase']=='Bound' and pvc['spec']['volumeName']=='pvc-'+CLAIM,'original_bound_claim')
    need(any(v.get('persistentVolumeClaim',{}).get('claimName')=='tautulli-data-0' and v['name']=='data-0' for v in pod['spec']['volumes'])
         and any(m['name']=='data-0' and m['mountPath']=='/config' and not m.get('readOnly',False) for m in containers[0]['volumeMounts']),'original_config_mount')
    return {'deployment_uid':DEPLOYMENT,'helmrelease_uid':RELEASE,'pvc_uid':CLAIM,
            'generation':dep['metadata']['generation'],'helmrelease_generation':release['metadata']['generation'],
            'pod_uid':pod['metadata']['uid'],'pod_name':pod['metadata']['name'],'image':IMAGE,
            'restart_count':cs[0].get('restartCount',0)}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state-receipt',type=Path,required=True)
    parser.add_argument('--state-receipt-sha256',required=True)
    parser.add_argument('--previous-functional-receipt',type=Path)
    parser.add_argument('--previous-functional-receipt-sha256',default='')
    parser.add_argument('--output-dir',type=Path,required=True)
    args=parser.parse_args();need(os.name=='posix','native_operator_required');os.umask(0o077)
    state=private_receipt(args.state_receipt,args.state_receipt_sha256)
    need(state.get('status')=='completed' and state.get('application')=='tautulli'
         and all(state.get(k) is True for k in ['all_original_application_rows_fields_preserved','canonical_configuration_preserved_with_exact_source_changes','temporary_pod_deleted']),'completed_data_preservation_required')
    need(bool(args.previous_functional_receipt)==bool(args.previous_functional_receipt_sha256),'restart_receipt_pair')
    output=args.output_dir
    need(output.is_absolute() and output.resolve()==output and RUNTIME in output.parents
         and not any((p/'.git').exists() for p in [output,*output.parents]),'native_output_outside_git')
    output.mkdir(mode=0o700,parents=True,exist_ok=True);info=output.lstat()
    need(info.st_uid==os.getuid() and stat.S_ISDIR(info.st_mode) and not info.st_mode&0o077,'private_output')
    path=output/('functional-'+uuid.uuid4().hex+'.json')
    receipt={'schema_version':1,'application':'tautulli','passed':False,'started_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),
             'state_receipt_sha256':args.state_receipt_sha256,'cold_receipt_sha256':state['cold_receipt_sha256'],
             'source_sha256':digest(Path(__file__)),'pod_program_sha256':hashlib.sha256(POD_PROGRAM.encode()).hexdigest(),
             'writer_restarted_by_observer':False,'external_routes_or_browser_accepted':False,'full_goal_complete':False}
    try:
        before=fence();receipt['writer']=before
        need(all(state['writer'].get(k)==v for k,v in before.items()),'writer_changed_since_data_preservation')
        if args.previous_functional_receipt:
            previous=private_receipt(args.previous_functional_receipt,args.previous_functional_receipt_sha256)
            need(previous.get('passed') is True and previous['cold_receipt_sha256']==state['cold_receipt_sha256']
                 and previous['writer']['pod_uid']!=before['pod_uid'] and state.get('restart_preservation_observed') is True,'independent_restart_not_proven')
            receipt.update(previous_functional_receipt_sha256=args.previous_functional_receipt_sha256,different_writer_pod_verified=True)
        result=call(['kubectl','--request-timeout=240s','-n','plex','exec',before['pod_name'],'-c','tautulli','--','python3','-B','-c',POD_PROGRAM],timeout=260)
        observation=json.loads(result.stdout)
        need(result.returncode==0 and observation.get('passed') is True,'functional_read_refused_'+str(observation.get('failure','unknown')))
        receipt['observation']=observation
        need(fence()==before,'writer_changed_during_reads')
        private_receipt(args.state_receipt,args.state_receipt_sha256)
        receipt['passed']=True
    except Exception as e:
        receipt['failure']=str(e) if isinstance(e,ValueError) and re.fullmatch('[a-zA-Z0-9_]+',str(e)) else type(e).__name__
    receipt['completed_at']=datetime.datetime.now(datetime.timezone.utc).isoformat()
    with path.open('x') as out:json.dump(receipt,out,sort_keys=True,indent=2);out.write('\n')
    print(json.dumps({'passed':receipt['passed'],'receipt':str(path),'receipt_sha256':digest(path)}))
    return 0 if receipt['passed'] else 1


if __name__=='__main__':
    raise SystemExit(main())
