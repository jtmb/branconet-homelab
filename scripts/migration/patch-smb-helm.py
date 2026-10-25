#!/usr/bin/env python3
"""Opt-in upgrade of the existing SMB Helm release; private values stay on master.

Default is read-only preflight. Feed a 32-byte hex HMAC key on stdin. No install,
uninstall, force replacement, PVC creation, raw Helm output or credential export.
"""
import argparse
import base64
import hashlib
import json
import os
import resource
from pathlib import Path
import shlex
import subprocess
import sys

CHART_SHA = '27116d0a703d9b7dee87ae65a0ffc95d47dfa4092b0191f1bb7e7cab79abb7f0'
SSH = ['ssh', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes', '-o', 'ConnectTimeout=15',
       '-i', '/home/brajam/.ssh/id_ed25519', '-p', '2002', 'james@192.168.0.4']

# Executed by existing Python/PyYAML on the master. Input and captured subprocess
# output remain in RAM. Only the filtered receipt leaves this process.
REMOTE = r'''
import base64,copy,gzip,hashlib,hmac,io,json,os,resource,subprocess,sys,tarfile,time
import yaml
resource.setrlimit(resource.RLIMIT_CORE,(0,0)); os.umask(0o077)
req=json.load(sys.stdin); key=bytes.fromhex(req['key']); assert len(key)==32
HELM='/usr/local/bin/helm'; NS='kube-system'; RELEASE='csi-driver-smb'
SMB='registry.k8s.io/sig-storage/smbplugin:v1.20.4@sha256:74e049de9d3203b4a968f26c8b73d4b3b15b9c4705688330cfa7281ae5f7b727'
RESIZER='registry.k8s.io/sig-storage/csi-resizer:v2.2.1@sha256:ea1d25e23479000c7e8eeb92d827df66258df4e482ca054c5e7ce3fc0f5c41a5'
OLD_SMB='registry.k8s.io/sig-storage/smbplugin:v1.20.3'
OLD_RESIZER='registry.k8s.io/sig-storage/csi-resizer:v2.2.0'
OLD_HP=OLD_SMB+'-windows-hp'
HP='registry.k8s.io/sig-storage/smbplugin:v1.20.4-windows-hp@sha256:5b8202d29540c6a93f31de8fe881fa7628f0375e86b13bb8077c349c58fc5499'
LABEL_KEYS={'helm.sh/chart','app.kubernetes.io/version'}
KINDS={'ServiceAccount','ClusterRole','ClusterRoleBinding','Deployment','DaemonSet','CSIDriver'}
receipt={'status':'failed','action':req['action'],'helper_sha256':req['helper_sha256']}
def need(ok,code):
 if not ok:raise RuntimeError(code)
def mac(domain,value):
 if not isinstance(value,bytes):value=json.dumps(value,sort_keys=True,separators=(',',':')).encode()
 return hmac.new(key,domain.encode()+b'\0'+value,hashlib.sha256).hexdigest()
def run(args,data=None,timeout=90,fds=()):
 p=subprocess.run(args,input=data,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=timeout,pass_fds=fds)
 need(p.returncode==0,'command_failed_'+args[0].rsplit('/',1)[-1])
 need(len(p.stdout)<32*1024*1024,'response_bound')
 return p.stdout
def kube(kind,name=None,ns=None):
 a=['kubectl','--request-timeout=30s']
 if ns:a+=['-n',ns]
 a+=['get',kind]+([name]if name else [])+['-o','json']
 return json.loads(run(a))
def helm(*args):return run([HELM,*args])
def resource_id(o):return '/'.join([o['kind'],o['metadata'].get('namespace',''),o['metadata']['name']])
def documents(text):
 objects=[o for o in yaml.safe_load_all(text) if o]
 need(all(o['kind'] in KINDS and 'helm.sh/hook' not in o['metadata'].get('annotations',{}) for o in objects),'unreviewed_kind_or_hook')
 mapped={resource_id(o):o for o in objects};need(len(mapped)==len(objects),'duplicate_resource')
 return mapped
def changes(a,b,path=()):
 if type(a)!=type(b):return [(path,a,b)]
 if isinstance(a,dict):
  result=[]
  for k in sorted(set(a)|set(b)):
   if k not in a or k not in b:result.append((path+(k,),a.get(k),b.get(k)))
   else:result+=changes(a[k],b[k],path+(k,))
  return result
 if isinstance(a,list):
  if len(a)!=len(b):return [(path,a,b)]
  return [c for i,(x,y) in enumerate(zip(a,b)) for c in changes(x,y,path+(str(i),))]
 return [] if a==b else [(path,a,b)]
def allowed(path,a,b):
 if len(path)>1 and path[-2]=='labels' and path[-1] in LABEL_KEYS:
  return isinstance(a,str) and '1.20.3' in a and b==a.replace('1.20.3','1.20.4')
 if path[:3]==('spec','template','spec') and path[3] in ('containers','initContainers') and path[-1]=='image':
  return (a,b) in [(OLD_SMB,SMB),(OLD_RESIZER,RESIZER),(OLD_HP,HP)]
 return False
def clean(o,images=False):
 o=copy.deepcopy(o);o.pop('status',None)
 m=o['metadata']
 for k in ['resourceVersion','managedFields','generation','creationTimestamp']:m.pop(k,None)
 m.get('annotations',{}).pop('deployment.kubernetes.io/revision',None)
 for md in [m,o.get('spec',{}).get('template',{}).get('metadata',{})]:
  for k in LABEL_KEYS:
   value=md.get('labels',{}).get(k)
   if value is not None:
    need(isinstance(value,str) and ('1.20.3' in value or '1.20.4' in value),'unexpected_chart_label')
    md['labels'][k]=value.replace('1.20.3','REVIEWED').replace('1.20.4','REVIEWED')
 if images:
  for c in sum([o.get('spec',{}).get('template',{}).get('spec',{}).get(k,[])for k in ('containers','initContainers')],[]):
   if c['image'] in (OLD_SMB,SMB):c['image']='REVIEWED_SMB'
   if c['image'] in (OLD_RESIZER,RESIZER):c['image']='REVIEWED_RESIZER'
   if c['image'] in (OLD_HP,HP):c['image']='REVIEWED_HP'
 return o
def native(o):
 # Include UID/spec/metadata and entire encoded data map in a keyed fingerprint.
 # Never persist raw Secret values, NAS references, claim names or Helm values.
 return {'uid':o['metadata']['uid'],'hmac':mac('preserved-native-object',clean_native(o))}
def clean_native(o):
 o=copy.deepcopy(o);o.pop('status',None)
 for k in ['resourceVersion','managedFields','generation','creationTimestamp']:o['metadata'].pop(k,None)
 return o
def storage():
 pvs=[p for p in kube('pv')['items'] if p.get('spec',{}).get('csi',{}).get('driver')=='smb.csi.k8s.io']
 need(pvs,'no_original_smb_volumes')
 objects={};claims={};secrets=set();classes=set()
 for p in pvs:
  need(p['status']['phase']=='Bound' and not p['metadata'].get('deletionTimestamp'),'smb_pv_not_bound')
  objects[mac('native-id',resource_id(p))]=native(p)
  ref=p['spec']['claimRef'];c=kube('pvc',ref['name'],ref['namespace'])
  need(c['metadata']['uid']==ref['uid'] and c['status']['phase']=='Bound','smb_claim_binding')
  objects[mac('native-id',resource_id(c))]=native(c);claims[(ref['namespace'],ref['name'])]=p['metadata']['uid']
  if p['spec'].get('storageClassName'):classes.add(p['spec']['storageClassName'])
  for k,v in p['spec']['csi'].items():
   if k.endswith('SecretRef') and isinstance(v,dict):secrets.add((v['namespace'],v['name']))
 for name in classes:
  sc=kube('storageclass',name);objects[mac('native-id',resource_id(sc))]=native(sc)
  parameters=sc.get('parameters',{})
  # A templated provisioner credential is resolved for each ORIGINAL claim only.
  for k,v in parameters.items():
   if k.startswith('csi.storage.k8s.io/') and k.endswith('-secret-name'):
    nsvalue=parameters.get(k[:-4]+'namespace')
    need(isinstance(nsvalue,str),'storageclass_secret_namespace_missing')
    for (ns,cn) in claims:
     secretname=v.replace('${pvc.name}',cn).replace('${pvc.namespace}',ns)
     secretns=nsvalue.replace('${pvc.namespace}',ns).replace('${pvc.name}',cn)
     need('${' not in secretname+secretns,'unresolved_storageclass_secret_template')
     secrets.add((secretns,secretname))
 for ns,name in sorted(secrets):
  obj=kube('secret',name,ns);objects[mac('native-id',resource_id(obj))]=native(obj)
 return {'objects':objects,'pv_count':len(pvs),'pvc_count':len(claims),'native_secret_count':len(secrets),'storageclass_count':len(classes)},claims
def samples(claims):
 result=[];sampled=set();attempts=0
 pods=json.loads(run(['kubectl','--request-timeout=30s','get','pods','-A','-o','json']))
 for p in sorted(pods['items'],key=lambda x:x['metadata']['uid']):
  ns=p['metadata']['namespace'];node=p['spec'].get('nodeName')
  if node in sampled or p['status'].get('phase')!='Running' or p['metadata'].get('deletionTimestamp'):continue
  volumes={v['name']:claims[(ns,v['persistentVolumeClaim']['claimName'])] for v in p['spec'].get('volumes',[]) if (ns,v.get('persistentVolumeClaim',{}).get('claimName'))in claims}
  for c in p['spec']['containers']:
   for m in c.get('volumeMounts',[]):
    if m['name'] not in volumes or m.get('subPath') or m.get('subPathExpr') or attempts>=6:continue
    attempts+=1
    try:
     out=run(['kubectl','--request-timeout=15s','-n',ns,'exec',p['metadata']['name'],'-c',c['name'],'--','stat','-L','-c','%F|%a|%u|%g','--',m['mountPath']],timeout=20)
     need(len(out)<256 and out.split(b'|')[0]==b'directory','mount_root_not_directory')
     result.append({'node':node,'pv_uid':volumes[m['name']],'root_stat_hmac':mac('mount-root-stat',out),'passed':True});sampled.add(node)
     break
    except (RuntimeError,subprocess.TimeoutExpired):pass
   if node in sampled:break
  if len(sampled)==3 or attempts>=6:break
 return {'samples':result,'attempts':attempts,'coverage_nodes':len(sampled),'no_walk_or_write':True}
def observe(objects,expected_new=False):
 nodes=kube('nodes')['items'];need(len(nodes)==3,'exact_three_nodes')
 need(all(n['metadata']['labels'].get('kubernetes.io/os')=='linux' and any(c['type']=='Ready' and c['status']=='True' for c in n['status']['conditions'])for n in nodes),'three_linux_nodes_ready')
 observed={};workloads=[]
 for rid,rendered in objects.items():
  live=kube(rendered['kind'],rendered['metadata']['name'],rendered['metadata'].get('namespace'))
  need(not live['metadata'].get('deletionTimestamp'),'owned_resource_deleting')
  annotations=live['metadata'].get('annotations',{})
  need(annotations.get('meta.helm.sh/release-name')==RELEASE and annotations.get('meta.helm.sh/release-namespace')==NS,'existing_helm_owner')
  observed[rid]={'uid':live['metadata']['uid'],'stable_hmac':mac('release-resource',clean(live,images=True))}
  if live['kind']in ['DaemonSet','Deployment']:
   s=live['spec'];t=s['template']['spec'];status=live['status']
   need(status.get('observedGeneration',0)>=live['metadata']['generation'],'workload_unobserved')
   if live['kind']=='Deployment':
    need(s['strategy']=={'type':'Recreate'} and s['replicas']==1,'preserve_controller_recreate')
    need(status.get('readyReplicas',0)==1 and status.get('updatedReplicas',0)==1 and status.get('replicas',0)==1,'controller_not_ready')
   else:
    need(s['updateStrategy']['type']=='RollingUpdate' and s['updateStrategy']['rollingUpdate']['maxUnavailable']==1,'preserve_node_rolling_strategy')
    want=0 if t['nodeSelector']['kubernetes.io/os']=='windows' else 3
    need(all(status.get(k,0)==want for k in ['desiredNumberScheduled','currentNumberScheduled','numberReady','updatedNumberScheduled']),'daemonset_readiness')
   wanted_smb=(HP if expected_new else OLD_HP) if t['nodeSelector']['kubernetes.io/os']=='windows' else (SMB if expected_new else OLD_SMB);wanted_resizer=RESIZER if expected_new else OLD_RESIZER
   for c in t['containers']:
    if c['name']=='smb':need(c['image']==wanted_smb,'smb_image')
    if c['name']=='csi-resizer':need(c['image']==wanted_resizer,'resizer_image')
   workloads.append({'kind':live['kind'],'name':live['metadata']['name'],'uid':live['metadata']['uid'],'ready':True,'images':[c['image']for c in t['containers']],'os':t['nodeSelector']['kubernetes.io/os']})
 storage_state,claims=storage()
 original=kube('secret','sh.helm.release.v1.csi-driver-smb.v1',NS)
 state={'resources':observed,'nodes':{n['metadata']['name']:n['metadata']['uid']for n in nodes},'storage':storage_state,'original_release_secret_uid':original['metadata']['uid']}
 return state,workloads,samples(claims)
def compatibility_chart(raw):
 name='csi-driver-smb/templates/csi-smb-node-windows-hostprocess.yaml'
 block=b'{{- if hasKey .Values.windows "requirePrivacyForGlobalMapping" }}\n            - "--require-privacy-for-global-mapping={{ .Values.windows.requirePrivacyForGlobalMapping }}"\n{{- else }}\n            - "--require-privacy-for-global-mapping=true"\n{{- end }}\n'
 needle=b'{{ .Values.image.smb.tag }}-windows-hp'
 output=io.BytesIO(); changed=0
 with tarfile.open(fileobj=io.BytesIO(raw),mode='r:gz')as original,tarfile.open(fileobj=output,mode='w',format=tarfile.PAX_FORMAT)as target:
  for member in original.getmembers():
   need(member.isfile() and member.size<1024*1024,'chart_member_bounds')
   data=original.extractfile(member).read()
   if member.name==name:
    need(hashlib.sha256(data).hexdigest()=='a804f51f8e74648cb3cfd63738c9a8b8a2f924fe5c677bb51c007e8b31e04ccf' and data.count(needle)==4 and data.count(block)==1,'windows_template_preimage')
    data=data.replace(needle,HP.split(':',1)[1].encode()).replace(block,b'')
    need(hashlib.sha256(data).hexdigest()=='40f1d1304a98f849b4bda58efe85bfca7d6bc7a34cfcf0a1fefa5459ddad058b','windows_template_postimage');changed+=1
   cloned=copy.copy(member);cloned.size=len(data);target.addfile(cloned,io.BytesIO(data))
 need(changed==1,'one_windows_template_only')
 result=io.BytesIO()
 with gzip.GzipFile(filename='',mode='wb',fileobj=result,compresslevel=9,mtime=0)as compressed:compressed.write(output.getvalue())
 data=result.getvalue();need(hashlib.sha256(data).hexdigest()=='ded072737207b41fb166b40c8fb38324f402238c4e83a585463705e9bbb95b5b','patched_chart_hash')
 receipt['patched_chart_sha256']=hashlib.sha256(data).hexdigest()
 return data
def preflight():
 version=helm('version','--short').decode().strip();need(version.startswith('v4.3.0+'),'helm_version_changed')
 helptext=helm('upgrade','--help').decode()
 need(all(x in helptext for x in ['--rollback-on-failure','--reuse-values','--wait','watcher','--dry-run']),'helm4_flags')
 metadata=json.loads(helm('get','metadata',RELEASE,'-n',NS,'-o','json'))
 need(metadata['revision']==1 and metadata['version']=='1.20.3' and metadata['status']=='deployed','original_release_revision')
 # Namespace-wide get would miss Flux-system releases: inspect all namespaces.
 hrs=json.loads(run(['kubectl','get','helmreleases.helm.toolkit.fluxcd.io','-A','-o','json']))['items']
 need(not any(h['spec'].get('releaseName',h['metadata']['name'])==RELEASE and h['spec'].get('targetNamespace',h['metadata']['namespace'])==NS for h in hrs),'competing_flux_owner')
 values=json.loads(helm('get','values',RELEASE,'-n',NS,'-o','json'))
 effective=json.loads(helm('get','values',RELEASE,'-n',NS,'--all','-o','json'))
 need(effective['windows'].get('requirePrivacyForGlobalMapping',True) is True,'unexpected_windows_privacy_override')
 need(effective['linux']['enabled'] and effective['windows']['enabled'] and effective['windows']['useHostProcessContainers'],'preserve_declared_platforms')
 old=documents(helm('get','manifest',RELEASE,'-n',NS))
 state,workloads,mounts=observe(old)
 receipt.update(baseline_observation=state,workloads_before=workloads,mount_roots_before=mounts,helm_version=version,revision_before=1,stored_values_hmac=mac('stored-helm-values',values))
 rendered=json.loads(run(command+['--dry-run=server','--output=json'],timeout=120,fds=(fd,)))
 need(not rendered.get('hooks'),'unexpected_hooks')
 new=documents(rendered['manifest']);need(set(old)==set(new),'resource_add_delete_or_rename')
 diffs=[];unexpected=[]
 for rid in old:
  for path,a,b in changes(old[rid],new[rid]):
   entry={'resource':rid,'path':'/'.join(path),'approved':allowed(path,a,b)}
   if entry['approved'] and path[-1]=='image':entry.update(old=a,new=b)
   diffs.append(entry)
   if not entry['approved']:unexpected.append(entry)
 receipt['manifest_diff']=diffs
 need(not unexpected,'unreviewed_manifest_delta')
 need(any(d['path'].endswith('/image')for d in diffs),'no_image_upgrade')
 baseline={'state':state,'stored_values_hmac':mac('stored-helm-values',values),'old_manifest_hmac':mac('old-manifest',old),'new_manifest_hmac':mac('new-manifest',new)}
 receipt.update(helm_version=version,revision_before=1,chart_sha256=req['chart_sha256'],baseline=baseline,workloads_before=workloads,mount_roots_before=mounts,
  filtered_values={'stored_nondefault_top_level_keys':sorted(values or {}),'linux_enabled':True,'windows_enabled':True,'windows_hostprocess':True,'controller_strategy':'Recreate','controller_replicas':effective['controller']['replicas'],'node_maxUnavailable':effective['node']['maxUnavailable']})
 return baseline,old,new,values
try:
 receipt['key_id']=mac('key-id',b'smb-helm')
 chart=base64.b64decode(req['chart']);need(len(chart)==6899 and hashlib.sha256(chart).hexdigest()==req['chart_sha256']=='27116d0a703d9b7dee87ae65a0ffc95d47dfa4092b0191f1bb7e7cab79abb7f0','chart_integrity')
 chart=compatibility_chart(chart)
 fd=os.memfd_create('public-smb-chart',0);os.write(fd,chart);os.lseek(fd,0,0)
 command=[HELM,'upgrade',RELEASE,'/proc/self/fd/'+str(fd),'-n',NS,'--reuse-values','--set-string','image.smb.tag='+SMB.split(':',1)[1],'--set-string','image.csiResizer.tag='+RESIZER.split(':',1)[1]]
 baseline,old,new,stored_values=preflight()
 if req['action']=='apply':
  approved=req['approval'];need(approved['status']=='passed' and approved['action']=='preflight' and approved['helper_sha256']==req['helper_sha256'] and approved['key_id']==receipt['key_id'] and approved['baseline']==baseline,'approved_preflight_changed')
  # Only this explicit branch writes cluster state. Helm owns the same release.
  receipt['upgrade_attempted']=True
  raw=run(command+['--rollback-on-failure','--wait=watcher','--timeout=10m','--output=json'],timeout=700,fds=(fd,))
  upgraded=json.loads(raw);need(upgraded['version']==2,'unexpected_upgrade_revision')
  after,workloads,mounts=observe(new,expected_new=True)
  receipt.update(after=after,workloads_after=workloads,mount_roots_after=mounts)
  need(after==baseline['state'],'native_identity_spec_data_or_resource_changed')
  actual_values=json.loads(helm('get','values',RELEASE,'-n',NS,'-o','json'))
  expected_values=copy.deepcopy(stored_values or {})
  for field,image in [('smb',SMB),('csiResizer',RESIZER)]:
   expected_values.setdefault('image',{}).setdefault(field,{})['tag']=image.split(':',1)[1]
  need(actual_values==expected_values,'unexpected_stored_values_after_upgrade')
  need(mounts['coverage_nodes']>=receipt['mount_roots_before']['coverage_nodes'],'existing_mount_sample_regressed')
 receipt['status']='passed'
except Exception as e:
 receipt['error']=str(e) if isinstance(e,RuntimeError) else type(e).__name__
print(json.dumps(receipt,sort_keys=True))
'''


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--chart', type=Path, required=True)
    ap.add_argument('--receipt', type=Path, required=True)
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--approved-preflight', type=Path)
    ap.add_argument('--approved-sha256')
    args = ap.parse_args()
    os.umask(0o077)
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    if os.name != 'posix' or args.receipt.exists():
        raise SystemExit('Run in WSL with a new private receipt path.')
    key = sys.stdin.readline().strip()
    if len(bytes.fromhex(key)) != 32:
        raise SystemExit('A 32-byte hex HMAC key is required on stdin.')
    chart = args.chart.read_bytes()
    if hashlib.sha256(chart).hexdigest() != CHART_SHA or len(chart) != 6899:
        raise SystemExit('Public chart hash/size mismatch.')
    req = {'action': 'apply' if args.apply else 'preflight', 'key': key,
           'helper_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
           'chart': base64.b64encode(chart).decode(), 'chart_sha256': CHART_SHA}
    if args.apply:
        if not args.approved_preflight or not args.approved_sha256:
            raise SystemExit('Apply requires the exact reviewed preflight receipt and SHA256.')
        raw = args.approved_preflight.read_bytes()
        if hashlib.sha256(raw).hexdigest() != args.approved_sha256:
            raise SystemExit('Preflight receipt hash mismatch.')
        req['approval'] = json.loads(raw)
    try:
        p = subprocess.run(SSH + ['python3 -B -c ' + shlex.quote(REMOTE)],
                           input=json.dumps(req).encode(), stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE, timeout=1100)
        if p.returncode:
            result = {'status': 'failed', 'stage': 'ssh_or_remote_python', 'exit': p.returncode}
        else:
            result = json.loads(p.stdout)
    except Exception as e:
        result = {'status': 'failed', 'stage': 'transport_or_receipt', 'error': type(e).__name__}
    if args.apply and 'upgrade_attempted' not in result:
        result['apply_outcome_unknown'] = True
    args.receipt.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with args.receipt.open('x', encoding='utf-8') as f:
        json.dump(result, f, sort_keys=True, indent=2); f.write('\n')
    print(json.dumps({'status': result['status'], 'error': result.get('error'),
                      'receipt': str(args.receipt), 'upgrade_attempted': result.get('upgrade_attempted', False)}))
    if result['status'] != 'passed':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
