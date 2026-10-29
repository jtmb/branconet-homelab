#!/usr/bin/env python3
"""Finite create-only kubeadm tag aliases after all twelve native staging results."""
import argparse,hashlib,json,os,runpy,shlex,stat,subprocess,sys,uuid
from pathlib import Path
PRESTAGER_SHA='433bd1a9565e561c0e3c0ff88bce0e252e32d600b9a5148b89ef89b784d8afed'
CRI_SHA='8329d8bca6d1ca8357ec2ee45495002e2b5676945bafb1480853ab763dbc26b4'

def need(ok,reason):
 if not ok:raise ValueError(reason)
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

# These functions execute only inside the authenticated remote RAM namespace.
def alias_inspect(request):
 plan=request['plan'];tag=PINS[plan['service']]['repository']+':v1.37.2'
 profile=node_observe(request)
 need(profile['fullyCached'] and profile['fits'],'complete_native_source_and_floors_before_alias')
 need(sha('/opt/containerd-k8s/bin/crictl')==CRI_SHA,'original_crictl_binary')
 existing=profile['inventory']['images'].get(tag)
 need(existing is None or (existing['digest']==plan['root'] and existing['managed']),'existing_alias_conflict_never_overwrite')
 profile['alias']=tag;profile['aliasPresent']=existing is not None
 # Native task list order is unspecified (confirmed across three unchanged
 # live observations). Preserve header, every complete row and multiplicity;
 # compare that full unordered inventory rather than its incidental row order.
 for kind in ['containers','tasks']:
  rows=native([kind,'list']).splitlines();need(bool(rows),'native_list_header_missing')
  profile[kind+'SHA256']=hashlib.sha256(b'\n'.join([rows[0],*sorted(rows[1:])])).hexdigest()
 if existing is not None:
  state=json.loads(read(['/opt/containerd-k8s/bin/crictl','--runtime-endpoint','unix:///run/containerd-k8s/containerd.sock','inspecti',tag]))['status']
  need(state['id']==plan['config'] and tag in state.get('repoTags',[]) and any(PINS[plan['service']]['repository']+'@'+d in state.get('repoDigests',[]) for d in [plan['root'],plan['manifest']]),'cri_tag_exact_config_and_root_or_amd64')
  profile['cri']={k:state.get(k) for k in ['id','repoTags','repoDigests']}
 return profile

def alias_node(request):
 before=alias_inspect(request);result={'accepted':False,'created':False,'errors':[],'before':public_profile(before)};plan=request['plan'];tag=before['alias']
 if request['mode']=='observe':return result
 try:
  qualified=request['qualified']
  need(before['continuity']==qualified['continuity'] and before['containersSHA256']==qualified['containersSHA256'] and before['tasksSHA256']==qualified['tasksSHA256'],'fresh_alias_runtime_identity')
  need(public_profile(before)['nativeInventorySummary']==qualified['nativeInventorySummary'],'native_inventory_stable_before_alias')
  if not before['aliasPresent']:
   # v2.4.2 --local copies the full source Image record (including Labels),
   # changes only Name, then Create; no --force means no delete/overwrite.
   result['mutationStarted']=True
   native(['images','tag','--local',plan['image'],tag]);result['created']=True
  else:result['method']='existing_exact_alias_readonly'
 except Exception as exc:result['errors'].append(str(exc) if isinstance(exc,ValueError) else type(exc).__name__)
 finally:
  try:
   # CRI image-create event delivery may lag the synchronous image record create.
   import time
   after=None
   for attempt in range(6):
    try:after=alias_inspect(request);break
    except ValueError:
     if attempt==5:raise
     time.sleep(1)
   need(after is not None and after['aliasPresent'],'alias_and_cri_verified_after')
   old,new=before['inventory'],after['inventory']
   need(all(new['images'].get(k)==v for k,v in old['images'].items()),'all_prior_image_records_and_labels_preserved')
   need(set(new['images'])==set(old['images'])|{tag},'only_expected_alias_added')
   need(all(set(old[k])<=set(new[k]) for k in ['content','leases','snapshots']),'all_prior_content_leases_snapshots_preserved')
   need(after['continuity']==before['continuity'] and after['containersSHA256']==before['containersSHA256'] and after['tasksSHA256']==before['tasksSHA256'],'runtime_containers_tasks_preserved')
   if result['created']:need(new['images'][tag]==old['images'][plan['image']],'alias_copies_exact_source_digest_labels')
   need(max(0,before['freeBytes']-after['freeBytes'])<=METADATA_ALLOWANCE and after['freeBytes']>=after['floorAndMarginBytes'] and after['availableBytes']>=AVAILABLE_FLOOR,'alias_metadata_budget_and_original_floors')
   result['after']=public_profile(after);result['accepted']=not result['errors']
  except Exception as exc:result['errors'].append('after:'+(str(exc) if isinstance(exc,ValueError) else type(exc).__name__))
 return result

def main():
 path=Path(__file__).resolve();prestage=path.with_name('controller.py');need(sha(prestage)==PRESTAGER_SHA,'exact_reviewed_prestager')
 vendor=runpy.run_path(str(prestage));original=path.parents[2]/'official_vendor_preload/files/controller.py';need(sha(original)==vendor['ORIGINAL_SHA'],'original_native_core')
 core=runpy.run_path(str(original));H=vendor['H'];core['save'].__globals__['H']=H
 # Match the prestager's finite post-kernel202 equality while retaining the
 # unchanged original cluster/disk/UID/runtime controls.
 import inspect
 cluster_source=inspect.getsource(core['cluster'])
 need(cluster_source.count("'5.15.0-198-generic'")==1,'exact_original_kernel_equality')
 scope=core['cluster'].__globals__
 exec(compile(cluster_source.replace("'5.15.0-198-generic'","'5.15.0-202-generic'"),str(path)+':kernel202-cluster','exec'),scope)
 core['cluster']=scope['cluster']
 parser=argparse.ArgumentParser();parser.add_argument('mode',choices=['observe','create']);parser.add_argument('--password-stdin',action='store_true');args=parser.parse_args()
 # Consume bounded protected input BEFORE any subprocess can inherit stdin.
 names=[n for n in ['KUBERNETES1372_PRELOAD_SUDO_PASSWORD','ANSIBLE_BECOME_PASSWORD'] if n in os.environ]
 need(len(names)<=1 and not(args.password_stdin and names),'one_privilege_input_source')
 if args.password_stdin:
  st=os.fstat(sys.stdin.fileno());need(not sys.stdin.isatty() and (stat.S_ISFIFO(st.st_mode) or(stat.S_ISREG(st.st_mode) and st.st_uid==os.getuid() and not st.st_mode&0o077)),'protected_stdin')
  password=sys.stdin.buffer.readline(130).removesuffix(b'\n')
 elif names:password=os.environ.pop(names[0]).encode()
 else:
  helper=path.parents[2]/'legacy_plex_preservation/files/controller.py';password=runpy.run_path(str(helper))['privilege_input']()
 need(0<len(password)<=128 and not any(x in password for x in [b'\n',b'\r',b'\0']),'bounded_privilege_input')
 record={'mode':args.mode,'sourceSHA256':sha(path),'prestagerSHA256':PRESTAGER_SHA,'accepted':False,'errors':[]};save=core['save']
 try:
  need(os.getuid()==1000 and core['F'].is_mount() and core['read'](['findmnt','-n','-o','UUID','-T',str(core['F'])]).decode().strip()==core['VOLUME'],'original_owned_F_volume')
  need(H.resolve()==H and H.is_dir() and H.stat().st_uid==1000 and not H.stat().st_mode&0o077,'existing_private_prestage_root')
  record['controllerSpace']=core['controller_space']()
  stages={}
  for service in vendor['PINS']:
   for node in core['NODES']:
    f=H/(service+'-'+node+'-result.json');need(f.resolve()==f and f.is_file(),'all_twelve_stage_results_required');r=json.loads(f.read_bytes())
    need(r['accepted'] is True and r['controllerSHA256']==PRESTAGER_SHA and r['measurementSHA256']==vendor['FILES']['oci-staging-budget.json'] and r['after']['fullyCached'],'all_twelve_stages_accepted_exact_source')
    stages[f.name]=sha(f)
  record['stageResults']=stages;plans={s:vendor['measurement'](s) for s in vendor['PINS']};live=core['cluster']();record['clusterBefore']=live
  import ast
  tree=ast.parse(path.read_text());funcs=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ['alias_inspect','alias_node']]
  addon=ast.unparse(ast.Module(body=funcs,type_ignores=[]))
  source=original.read_text()+'\nPINS='+repr(vendor['PINS'])+'\nCRI_SHA='+repr(CRI_SHA)+'\n'+addon
  def dispatch(node,request):
   # Preserve original bounded complete-error codec; use the alias entrypoint.
   code=source+'\ntry:\n print(json.dumps(alias_node(json.load(sys.stdin))))\nexcept Exception as exc:\n print(json.dumps({"remoteFailure":str(exc) if isinstance(exc,ValueError) else type(exc).__name__}))\n'
   wrapped='exec(compile('+repr(code)+", '<official-alias-memory>', 'exec'), {'__name__':'official_alias_memory'})"
   argv=['sudo','-k','-S','-p','','--','python3','-B','-c',wrapped]
   p=subprocess.run(core['SSH']+['james@'+core['NODES'][node]['ip'],shlex.join(argv)],input=password+b'\n'+json.dumps(request).encode(),capture_output=True,timeout=600)
   need(p.returncode==0,'remote_alias_exit_'+str(p.returncode));need(len(p.stdout)<=8*1024**2,'bounded_remote_metadata');v=json.loads(p.stdout);need('remoteFailure' not in v,'remote_alias:'+v.get('remoteFailure',''));return v
  qualified={}
  for service,plan in plans.items():
   for node in core['NODES']:
    request={'node':node,'plan':plan,'cluster':live,'mode':'observe'};q=dispatch(node,request)['before'];qualified[service+'-'+node]=q
  for node in core['NODES']:
   values=[qualified[service+'-'+node] for service in plans];peak=len(plans)*core['METADATA_ALLOWANCE']
   need(min(x['freeBytes'] for x in values)>=max(x['floorAndMarginBytes'] for x in values)+peak and min(x['availableBytes'] for x in values)>=core['AVAILABLE_FLOOR']+peak,'aggregate_four_alias_metadata_floor_before_first_create')
  need(core['same_controls'](live,core['cluster']()),'all_three_controls_after_alias_preflight')
  qualification='alias-qualification-'+uuid.uuid4().hex+'.json';save(qualification,{'sourceSHA256':sha(path),'plans':plans,'cluster':live,'stageResults':stages,'nodes':qualified});record['qualification']=qualification
  if args.mode=='create':
   for service,plan in plans.items():
    for node in core['NODES']:
     key=service+'-'+node;intent='alias-'+key+'-intent.json';result='alias-'+key+'-result.json';q=qualified[key]
     if (H/intent).exists() or (H/result).exists():
      need((H/result).is_file(),'alias_uncertain_intent_observe_only:'+key);prior=json.loads((H/result).read_bytes());need(prior['accepted'] and prior['sourceSHA256']==sha(path) and q['aliasPresent'],'alias_prior_failure_or_changed_source_no_replay:'+key);continue
     fresh=core['cluster']();need(core['same_controls'](live,fresh),'three_node_controls_before_alias');core['controller_space']()
     q=dispatch(node,{'node':node,'plan':plan,'cluster':fresh,'mode':'observe'})['before']
     need(q['continuity']==qualified[key]['continuity'] and q['containersSHA256']==qualified[key]['containersSHA256'] and q['tasksSHA256']==qualified[key]['tasksSHA256'],'all_twelve_preflight_runtime_continuity')
     save(intent,{'sourceSHA256':sha(path),'qualification':qualification,'node':node,'image':plan['image'],'tag':q['alias'],'noUncertainReplay':True,'before':q})
     result_value=dispatch(node,{'node':node,'plan':plan,'cluster':fresh,'mode':'create','qualified':q});result_value['sourceSHA256']=sha(path);save(result,result_value);need(result_value['accepted'],'alias_not_accepted_observe_only:'+key)
  record['clusterAfter']=core['cluster']();need(core['same_controls'](live,record['clusterAfter']),'original_cluster_controls_preserved');record['accepted']=True
 except BaseException as exc:record['errors'].append(str(exc) if isinstance(exc,ValueError) else type(exc).__name__)
 finally:
  password=None
  save('aliases-'+args.mode+'-'+uuid.uuid4().hex+'.json',record)
 print(json.dumps({'accepted':record['accepted'],'errors':record['errors']}));return 0 if record['accepted'] else 1
if __name__=='__main__':raise SystemExit(main())
