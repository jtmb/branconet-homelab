#!/usr/bin/env python3
"""Build the separately committed BORTUS app on the existing Docker builder.

The context explicitly excludes local credentials, databases and build output.
This builds only an image; it does not run or deploy the application.
"""
import datetime
import json
import os
import pathlib
import subprocess

ROOT=pathlib.Path(__file__).resolve().parents[2]
SOURCE=pathlib.Path('/mnt/c/Users/james/.codex/worktrees/4ef5/kubernetes migration/k8s-rewrite/front-end')
TAG='bortus:migration-1438b27'

def main():
    reference=(SOURCE.parents[1]/'.git').read_text().strip().removeprefix('gitdir: ')
    if len(reference)>2 and reference[1]==':':reference='/mnt/'+reference[0].lower()+'/'+reference[3:].replace('\\','/')
    commit=subprocess.check_output(['git','--git-dir',reference,'rev-parse','HEAD'],text=True).strip()
    if commit!='1438b278cdf21e98429b4836c018636b01b982a3':raise SystemExit('BORTUS delivery commit changed; review before building')
    log=pathlib.Path.home()/'.local/share/branconet-migration/bortus-image-build.log'
    fd=os.open(log,os.O_CREAT|os.O_TRUNC|os.O_WRONLY,0o600);os.chmod(log,0o600)
    started=datetime.datetime.now(datetime.timezone.utc).isoformat()
    excludes=['node_modules','.next','.env','.env.*','*.db','*.db-*','*.sqlite','*.sqlite-*','*.tsbuildinfo','tests','.git','*.log','*.tmp']
    context=subprocess.Popen(['tar',*[f'--exclude={p}' for p in excludes],'-C',str(SOURCE),'-czf','-','.'],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    with os.fdopen(fd,'w') as output:
        builder=subprocess.Popen(['ssh','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-p','2002','james@192.168.0.4','docker','build','--build-arg','KUBECTL_VERSION=v1.37.1','-t',TAG,'-'],stdin=context.stdout,stdout=output,stderr=subprocess.STDOUT)
        context.stdout.close();builder.wait();context.wait()
    record={'started_at':started,'completed_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'source_commit':commit,'image_tag':TAG,'builder_host':'192.168.0.4','build_exit_code':builder.returncode,'context_exit_code':context.returncode,'operator_log':str(log),'deployed':False,'runtime_accepted':False}
    if builder.returncode==0 and context.returncode==0:
        inspected=subprocess.run(['ssh','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-p','2002','james@192.168.0.4','docker','image','inspect',TAG],capture_output=True,text=True)
        if inspected.returncode:raise SystemExit('Built image inspection failed')
        image=json.loads(inspected.stdout)[0]
        record.update({'image_id':image['Id'],'image_bytes':image['Size']})
    (ROOT/'evidence/bortus-image.json').write_text(json.dumps(record,indent=2)+'\n')
    print(json.dumps(record),flush=True)
    raise SystemExit(0 if builder.returncode==0 and context.returncode==0 else 1)

if __name__=='__main__':main()
