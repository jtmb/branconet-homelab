#!/usr/bin/env python3
"""Cold-copy one application's retained host directory into new Longhorn claims."""
import argparse
import datetime
import json
import pathlib
import subprocess
import time
import tempfile
import shutil
import yaml

ROOT=pathlib.Path(__file__).resolve().parents[2]
RUNTIME=pathlib.Path.home()/'.local/share/branconet-migration'
NODES={'192.168.0.4':'masternode','192.168.0.5':'workernode2','192.168.0.6':'workernode1'}
COPY=r'''
import hashlib,json,os,pathlib,stat,subprocess
source=pathlib.Path('/source');target=pathlib.Path('/target')
remaining=[p.name for p in target.iterdir() if p.name!='lost+found']
if remaining:raise SystemExit('Destination is not empty; inspect retained data before rerunning')
if (target/'lost+found').exists():(target/'lost+found').rmdir()
def manifest(root):
 result={}
 for directory,dirs,files in os.walk(root,followlinks=False):
  for name in ['.',*sorted(dirs),*sorted(files)]:
   path=pathlib.Path(directory)/name;relative=str(path.relative_to(root));info=path.lstat()
   item={'mode':stat.S_IMODE(info.st_mode),'uid':info.st_uid,'gid':info.st_gid,'mtime_ns':info.st_mtime_ns,'type':stat.S_IFMT(info.st_mode)}
   if path.is_symlink():item['link']=os.readlink(path)
   elif path.is_file():
    digest=hashlib.sha256()
    with path.open('rb') as contents:
     for chunk in iter(lambda:contents.read(1024*1024),b''):digest.update(chunk)
    item['bytes']=info.st_size;item['sha256']=digest.hexdigest()
   attrs={}
   for key in os.listxattr(path,follow_symlinks=False):
    if key.startswith(('trusted.glusterfs.','glusterfs.')):continue
    attrs[key]=hashlib.sha256(os.getxattr(path,key,follow_symlinks=False)).hexdigest()
   item['attribute_hashes']=attrs;result[relative]=item
 return result
before=manifest(source)
producer=subprocess.Popen(['tar','--acls','--xattrs','--xattrs-include=*','--numeric-owner','--format=posix','-C','/source','-cpf','-','.'],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
consumer=subprocess.Popen(['tar','--acls','--xattrs','--xattrs-include=*','--numeric-owner','-C','/target','-xpf','-'],stdin=producer.stdout,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
producer.stdout.close();out,err=consumer.communicate();producer_error=producer.stderr.read();producer.wait()
if producer.returncode or consumer.returncode:raise SystemExit('Source/destination tar failed; originals and partial destination retained')
subprocess.run(['sync'],check=True)
after=manifest(source);copied=manifest(target)
if before!=after:raise SystemExit('Source changed during cold copy; destination is not accepted')
if before!=copied:
 differences=[name for name in before if before[name]!=copied.get(name)]
 print(json.dumps({'manifest_equal':False,'difference_count':len(differences),'extra_entries':len(set(copied)-set(before))}),flush=True)
 raise SystemExit('Destination content/ownership/permissions/time/ACL/attributes differ')
fingerprint=hashlib.sha256(json.dumps(before,sort_keys=True,separators=(',',':')).encode()).hexdigest()
print(json.dumps({'manifest_equal':True,'source_stable':True,'entries':len(before),'manifest_sha256':fingerprint,'file_bytes':sum(item.get('bytes',0) for item in before.values()),'content_ownership_permissions_time_acl_xattrs_verified':True}),flush=True)
'''

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--chart',required=True);args=parser.parse_args()
    directory=ROOT/'k8s-rewrite/charts'/args.chart
    if ROOT/'k8s-rewrite/charts' not in directory.resolve().parents:raise SystemExit('Chart must be inside migration charts')
    values=yaml.safe_load((directory/'values.yaml').read_text());name=yaml.safe_load((directory/'Chart.yaml').read_text())['name']
    register=json.loads((ROOT/'evidence/service-register.json').read_text())
    entries=[entry for entry in register['entries'] if entry.get('chart')==args.chart and entry['source_type'] in {'swarm','standalone'}]
    if not entries:raise SystemExit('A live source is required for data migration')
    selected=entries[0];ns=selected['namespace']
    if not values['migration'].get('nativeSecretsImported') or values['migration'].get('sourceCommandArgumentsRequireReview'):raise SystemExit('Native launch/configuration review must complete first')
    backups=json.loads((ROOT/'evidence/data-backups.json').read_text())
    if not backups.get('completed_at'):raise SystemExit('Verified recovery backup must complete before cold copy')
    report_path=ROOT/'evidence'/('copy-'+name+'.json')
    if report_path.exists():raise SystemExit('Prior copy evidence exists; inspect destination and writer state before retrying')
    kube=[str(RUNTIME/'bin/kubectl'),'--kubeconfig',str(RUNTIME/'admin.conf')]
    helm=[str(RUNTIME/'bin/helm'),'--kubeconfig',str(RUNTIME/'admin.conf')]
    def run(arguments,body=None,timeout=600):
        result=subprocess.run([*kube,*arguments],input=body,capture_output=True,text=True,timeout=timeout)
        if result.returncode:
            diagnostic=RUNTIME/('copy-'+name+'-'+arguments[0]+'.diagnostic')
            diagnostic.write_text(result.stderr);diagnostic.chmod(0o600)
            raise RuntimeError('Application copy Kubernetes operation failed: '+arguments[0]+'; protected diagnostic retained')
        return result.stdout
    def remote(host,code):
        result=subprocess.run(['ssh','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-p','2002','james@'+host,'python3','-'],input=code,capture_output=True,text=True,timeout=120)
        if result.returncode:raise RuntimeError('Source writer operation failed on '+host)
        return result.stdout
    source=selected['source'];swarm=selected['source_type']=='swarm'
    copies=values['migration'].get('dataCopies',[])
    if not copies:raise SystemExit('No data claims for this chart; use the stateless acceptance path')
    source_host='192.168.0.4' if swarm else source.split('/')[0]
    source_name=source if swarm else source.split('/',1)[1]
    original=None;stopped=False;pods=[];copy_results=[];succeeded=False
    with tempfile.TemporaryDirectory(prefix='migration-cold-copy-') as work:
        chart=pathlib.Path(work)/'chart';shutil.copytree(directory,chart)
        # Establish owned zero-replica resources before stopping source writers.
        subprocess.run([*helm,'upgrade','--install',name,str(chart),'-n',ns,'--set','enabled=true,migration.staging=true,replicaCount=0','--timeout','5m'],capture_output=True,text=True,check=True)
        try:
            if swarm:
                original=json.loads(remote(source_host,"import json,subprocess\ns=json.loads(subprocess.check_output(['docker','service','inspect',"+repr(source_name)+"],text=True))[0]\nprint(json.dumps(s['Spec']['Mode']['Replicated']['Replicas']))"))
                if original!=1:raise RuntimeError('Source desired count changed; review before stopping')
                remote(source_host,"import subprocess\nsubprocess.run(['docker','service','scale','--detach',"+repr(source_name+'=0')+"],check=True,capture_output=True)")
            else:
                remote(source_host,"import subprocess\nsubprocess.run(['docker','stop','--time','60',"+repr(source_name)+"],check=True,capture_output=True)")
            stopped=True
            for _ in range(60):
                running=False
                for host in NODES:
                    filters=['docker','ps','-q','--filter',('label=com.docker.swarm.service.name='+source_name) if swarm else ('name=^/'+source_name+'$')]
                    if not swarm and host!=source_host:continue
                    if remote(host,"import subprocess\nprint(subprocess.check_output("+repr(filters)+",text=True).strip())").strip():running=True
                if not running:break
                time.sleep(2)
            else:raise RuntimeError('Source writer did not stop')
            for index,copy in enumerate(copies):
                podname='copy-'+name+'-'+str(index)
                pod={'apiVersion':'v1','kind':'Pod','metadata':{'name':podname,'namespace':ns,'labels':{'branconet.io/migration-copy':name}},'spec':{'nodeName':NODES[copy['sourceHost']],'automountServiceAccountToken':False,'restartPolicy':'Never','securityContext':{'runAsUser':0,'runAsGroup':0},'containers':[{'name':'copy','image':'python:3.12-slim','command':['python3','-c','import time;time.sleep(3600)'],'volumeMounts':[{'name':'source','mountPath':'/source','readOnly':True},{'name':'target','mountPath':'/target'}],'resources':{'requests':{'cpu':'100m','memory':'128Mi'},'limits':{'memory':'512Mi'}}}],'volumes':[{'name':'source','hostPath':{'path':copy['sourcePath'],'type':'Directory'}},{'name':'target','persistentVolumeClaim':{'claimName':copy['destinationPVC']}}]}}
                pod['spec']['terminationGracePeriodSeconds']=10
                if name=='plex':pod['spec']['containers'][0]['resources']['limits']['memory']='2Gi'
                pod['spec']['containers'][0]['image']='python@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1'
                run(['create','-f','-'],json.dumps(pod));pods.append(podname)
                run(['wait','pod/'+podname,'-n',ns,'--for=condition=Ready','--timeout=300s'])
                actual=json.loads(run(['get','pod',podname,'-n',ns,'-o','json']))
                result=json.loads(run(['exec','-i','-n',ns,podname,'--','python3','-'],COPY,timeout=1800))
                result.update(copy);result['utility_image_id']=actual['status']['containerStatuses'][0]['imageID']
                copy_results.append(result)
                run(['delete','pod',podname,'-n',ns,'--wait=true']);pods.remove(podname)
            succeeded=True
            report={'completed_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'source':source,'chart':args.chart,'namespace':ns,'release':name,'source_writers_stopped':True,'originals_retained':True,'target_started':False,'application_accepted':False,'copies':copy_results,'source_desired_before':original,'source_restart_on_success':False}
            report_path.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report),flush=True)
        finally:
            for podname in pods:
                try:run(['delete','pod',podname,'-n',ns,'--wait=true'])
                except Exception:pass
            if stopped and not succeeded:
                if swarm:remote(source_host,"import subprocess\nsubprocess.run(['docker','service','scale','--detach',"+repr(source_name+'='+str(original))+"],check=True,capture_output=True)")
                else:remote(source_host,"import subprocess\nsubprocess.run(['docker','start',"+repr(source_name)+"],check=True,capture_output=True)")

if __name__=='__main__':main()
