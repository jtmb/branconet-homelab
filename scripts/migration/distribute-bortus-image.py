#!/usr/bin/env python3
"""Load the locally built app image into each independent Kubernetes runtime."""
import concurrent.futures
import hashlib
import json
import os
import pathlib
import shlex
import subprocess
import sys

ROOT=pathlib.Path(__file__).resolve().parents[2]
RUNTIME=pathlib.Path.home()/'.local/share/branconet-migration'
TAG='bortus:migration-1438b27'

REMOTE=r'''
import json,subprocess,sys
request=json.loads(sys.stdin.buffer.readline())
authenticated=subprocess.run(['sudo','-S','-p','','-v'],input=request['sudo_password'].encode()+bytes([10]),capture_output=True)
if authenticated.returncode:raise SystemExit('Runtime image import authorization failed')
command=['sudo','-n','/opt/containerd-k8s/bin/ctr','--address','/run/containerd-k8s/containerd.sock','--namespace','k8s.io','images']
def inspect():
 result=subprocess.run(command+['list'],capture_output=True,text=True,check=True)
 rows=[line.split() for line in result.stdout.splitlines()[1:] if line.split() and line.split()[0] in ['bortus:migration-1438b27','docker.io/library/bortus:migration-1438b27']]
 return {'tag_present_in_runtime':bool(rows),'runtime_manifest_digest':rows[0][2] if rows else None}
existing=inspect()
print(json.dumps({'requires_import':not existing['tag_present_in_runtime'],**existing}),flush=True)
if existing['tag_present_in_runtime']:
 print(json.dumps({'image_import_exit_code':0,'already_present':True,**existing}),flush=True)
 raise SystemExit(0)
process=subprocess.Popen(command+['import','-'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
while True:
 chunk=sys.stdin.buffer.read(1024*1024)
 if not chunk:break
 process.stdin.write(chunk)
process.stdin.close()
out=process.stdout.read();err=process.stderr.read();process.wait()
print(json.dumps({'image_import_exit_code':process.returncode,'already_present':False,**inspect(),'diagnostic':err.decode(errors='replace').splitlines()[-1:] if process.returncode else []}))
'''

def main():
    request=json.load(sys.stdin)
    build=json.loads((ROOT/'evidence/bortus-image.json').read_text())
    if build['build_exit_code'] or build['context_exit_code']:raise SystemExit('Image build must succeed first')
    archive=RUNTIME/'bortus-migration-1438b27.tar'
    if not archive.exists():
        fd=os.open(archive,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
        with os.fdopen(fd,'wb') as output:
            exported=subprocess.run(['ssh','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-p','2002','james@192.168.0.4','docker','save',TAG],stdout=output,stderr=subprocess.PIPE)
        if exported.returncode:raise SystemExit('Image export failed; inspect incomplete operator archive before rerunning')
    digest=hashlib.sha256()
    with archive.open('rb') as source:
        for chunk in iter(lambda:source.read(1024*1024),b''):digest.update(chunk)
    evidence=ROOT/'evidence/bortus-image-distribution.json'
    previous=json.loads(evidence.read_text()) if evidence.exists() else None
    expected_manifest=None
    if previous:
        if digest.hexdigest()!=previous['archive_sha256']:raise SystemExit('Image archive differs from the verified deployed export')
        manifests={n['runtime_manifest_digest'] for n in previous['nodes']}
        if len(manifests)!=1:raise SystemExit('Previously recorded runtime images do not agree')
        expected_manifest=next(iter(manifests))
    def load(host):
        remote_command='python3 -c '+shlex.quote(REMOTE)
        process=subprocess.Popen(['ssh','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-p','2002','james@'+host,remote_command],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        process.stdin.write((json.dumps({'sudo_password':request['sudo_password']})+'\n').encode())
        process.stdin.flush()
        preflight_line=process.stdout.readline()
        if not preflight_line:raise RuntimeError('Runtime inspection failed on '+host)
        preflight=json.loads(preflight_line)
        if preflight['requires_import']:
            with archive.open('rb') as source:
                for chunk in iter(lambda:source.read(1024*1024),b''):process.stdin.write(chunk)
        process.stdin.close()
        output=process.stdout.read();error=process.stderr.read();process.wait()
        if process.returncode:raise RuntimeError('Image loading failed on '+host)
        result=json.loads(output)
        if result['image_import_exit_code'] or not result['tag_present_in_runtime']:raise RuntimeError('Runtime image import failed on '+host+': '+json.dumps(result))
        if expected_manifest and result['runtime_manifest_digest']!=expected_manifest:raise RuntimeError('Runtime image differs from the verified deployed manifest on '+host)
        return {'host':host,**result}
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        results=list(pool.map(load,['192.168.0.4','192.168.0.5','192.168.0.6']))
    report={'image_tag':TAG,'source_image_id':build['image_id'],'operator_archive':str(archive),'archive_sha256':digest.hexdigest(),'nodes':results,'application_started':False}
    (ROOT/'evidence/bortus-image-distribution.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report),flush=True)

if __name__=='__main__':main()
