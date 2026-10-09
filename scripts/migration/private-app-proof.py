#!/usr/bin/env python3
"""Run a copied/private HTTP application and prove restart/worker relocation."""
import argparse
import datetime
import hashlib
import json
import pathlib
import shutil
import socket
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
import yaml

ROOT=pathlib.Path(__file__).resolve().parents[2]
RUNTIME=pathlib.Path.home()/'.local/share/branconet-migration'

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--chart',required=True);parser.add_argument('--port',type=int,required=True);parser.add_argument('--path',default='/');parser.add_argument('--stable-body',action='store_true');parser.add_argument('--relocate',action='store_true');args=parser.parse_args()
    directory=ROOT/'k8s-rewrite/charts'/args.chart
    if ROOT/'k8s-rewrite/charts' not in directory.resolve().parents:raise SystemExit('Invalid chart path')
    values=yaml.safe_load((directory/'values.yaml').read_text());name=yaml.safe_load((directory/'Chart.yaml').read_text())['name']
    deployment=next(o for o in values['resources'] if o['kind']=='Deployment');ns=deployment['metadata']['namespace']
    if deployment['spec']['template']['spec'].get('hostNetwork'):raise SystemExit('Host ports need a separate reviewed cutover')
    if values['migration'].get('dataCopies'):
        copy=json.loads((ROOT/'evidence'/('copy-'+name+'.json')).read_text())
        if not all(c['manifest_equal'] for c in copy['copies']) or not copy['source_writers_stopped']:raise SystemExit('Accepted cold-copy evidence is required')
    if not values['migration'].get('nativeSecretsImported'):raise SystemExit('Native environment review required')
    kube=[str(RUNTIME/'bin/kubectl'),'--kubeconfig',str(RUNTIME/'admin.conf')]
    helm=[str(RUNTIME/'bin/helm'),'--kubeconfig',str(RUNTIME/'admin.conf')]
    def run(arguments,body=None):
        result=subprocess.run([*kube,*arguments],input=json.dumps(body) if body is not None else None,capture_output=True,text=True,timeout=400)
        if result.returncode:raise RuntimeError('Private application operation failed: '+arguments[0])
        return result.stdout
    def pod():
        pods=json.loads(run(['get','pods','-n',ns,'-l','app='+name,'-o','json']))['items']
        candidates=[p for p in pods if not p['metadata'].get('deletionTimestamp') and any(c['type']=='Ready' and c['status']=='True' for c in p.get('status',{}).get('conditions',[]))]
        if len(candidates)!=1:raise RuntimeError('Expected one Ready application pod')
        return candidates[0]
    def http():
        holder=socket.socket();holder.bind(('127.0.0.1',0));port=holder.getsockname()[1];holder.close()
        forward=subprocess.Popen([*kube,'port-forward','-n',ns,'service/'+name,str(port)+':'+str(args.port),'--address','127.0.0.1'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        try:
            for _ in range(45):
                try:
                    with urllib.request.urlopen('http://127.0.0.1:'+str(port)+args.path,timeout=20) as response:
                        body=response.read();return {'status':response.status,'bytes':len(body),'body_sha256':hashlib.sha256(body).hexdigest()}
                except (urllib.error.URLError,TimeoutError,ConnectionError):time.sleep(1)
            raise RuntimeError('Private HTTP endpoint did not pass')
        finally:
            forward.terminate()
            try:forward.wait(timeout=10)
            except subprocess.TimeoutExpired:forward.kill()
    with tempfile.TemporaryDirectory(prefix='migration-app-proof-') as work:
        chart=pathlib.Path(work)/'chart';shutil.copytree(directory,chart)
        arguments=['--set','enabled=true,migration.staging=true,replicaCount=1','--wait','--timeout','5m']
        subprocess.run([*helm,'upgrade','--install',name,str(chart),'-n',ns,*arguments],capture_output=True,text=True,check=True)
        initial=pod();first=http()
        claims={c['metadata']['name']:(c['metadata']['uid'],c['spec'].get('volumeName')) for c in json.loads(run(['get','pvc','-n',ns,'-o','json']))['items'] if c['metadata']['name'] in {v['persistentVolumeClaim']['claimName'] for v in deployment['spec']['template']['spec'].get('volumes',[]) if 'persistentVolumeClaim' in v}}
        run(['rollout','restart','deployment/'+name,'-n',ns]);run(['rollout','status','deployment/'+name,'-n',ns,'--timeout=300s'])
        restarted=pod();second=http()
        if restarted['metadata']['uid']==initial['metadata']['uid']:raise RuntimeError('Application did not actually restart')
        if args.stable_body and second['body_sha256']!=first['body_sha256']:raise RuntimeError('Stable HTTP content changed after restart')
        relocated=None
        if args.relocate:
            node='workernode1' if restarted['spec']['nodeName']!='workernode1' else 'workernode2'
            staged=yaml.safe_load((chart/'values.yaml').read_text());item=next(o for o in staged['resources'] if o['kind']=='Deployment')
            item['spec']['template']['spec']['nodeSelector']={'kubernetes.io/hostname':node}
            (chart/'values.yaml').write_text(yaml.safe_dump(staged,sort_keys=False))
            subprocess.run([*helm,'upgrade',name,str(chart),'-n',ns,*arguments],capture_output=True,text=True,check=True)
            relocated=pod();third=http()
            if relocated['spec']['nodeName']!=node:raise RuntimeError('Application did not relocate to selected worker')
            if args.stable_body and third['body_sha256']!=first['body_sha256']:raise RuntimeError('Stable HTTP content changed after relocation')
            # Restore the chart's normal scheduler policy after proving relocation.
            shutil.copyfile(directory/'values.yaml',chart/'values.yaml')
            subprocess.run([*helm,'upgrade',name,str(chart),'-n',ns,*arguments],capture_output=True,text=True,check=True)
            http()
        for claim,(uid,volume) in claims.items():
            actual=json.loads(run(['get','pvc',claim,'-n',ns,'-o','json']))
            if actual['metadata']['uid']!=uid or actual['spec']['volumeName']!=volume:raise RuntimeError('Claim identity changed during application tests')
        report={'completed_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'chart':args.chart,'release':name,'namespace':ns,'private_http':first,'restart_http_passed':True,'stable_body_verified':args.stable_body,'relocation_http_passed':bool(relocated),'original_node':initial['spec']['nodeName'],'relocated_node':relocated['spec']['nodeName'] if relocated else None,'persistent_claim_identity_verified':list(claims),'image_ids':[c['imageID'] for c in pod()['status']['containerStatuses']],'production_routing_accepted':False,'source_originals_retained':True}
        (ROOT/'evidence'/('private-'+name+'.json')).write_text(json.dumps(report,indent=2)+'\n')
        # Flux retains the tested private state when it adopts the Helm release.
        release_path=ROOT/'k8s-rewrite/flux/migration-releases'/(name+'.yaml')
        release=yaml.safe_load(release_path.read_text());release['spec']['values']={'enabled':True,'replicaCount':1,'migration':{'staging':True}}
        release_path.write_text(yaml.safe_dump(release,sort_keys=False))
        print(json.dumps(report),flush=True)

if __name__=='__main__':main()
