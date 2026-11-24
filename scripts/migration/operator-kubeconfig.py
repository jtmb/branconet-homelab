#!/usr/bin/env python3
"""Recover operator kubeconfig from authenticated age backup outside Git."""
import base64
import json
import os
import pathlib
import subprocess

def main():
    root=pathlib.Path(__file__).resolve().parents[2]
    runtime=pathlib.Path.home()/'.local/share/branconet-migration'
    records=json.loads((root/'evidence/config-backups.json').read_text())
    source=next(host for host in records['hosts'] if host['host']=='192.168.0.4')
    if not source['recovery_verified']:raise SystemExit('Configuration recovery is not verified')
    decoded=subprocess.run([str(runtime/'bin/age'),'-d','-i',str(pathlib.Path.home()/'.ssh/id_ed25519'),source['operator_copy']],capture_output=True)
    if decoded.returncode:raise SystemExit('Authenticated configuration decode failed')
    document=json.loads(decoded.stdout)
    admin=document['files'].get('/etc/kubernetes/admin.conf')
    if not admin:raise SystemExit('Post-provision admin configuration not archived')
    target=runtime/'admin.conf'
    fd=os.open(target,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600);os.chmod(target,0o600)
    with os.fdopen(fd,'wb') as output:output.write(base64.b64decode(admin))
    check=subprocess.run([str(runtime/'bin/kubectl'),'--kubeconfig',str(target),'get','nodes','-o','json'],capture_output=True,text=True)
    if check.returncode:raise SystemExit('Operator Kubernetes API check failed')
    nodes=json.loads(check.stdout)['items']
    print(json.dumps({'protected_operator_file':str(target),'nodes':[{'name':node['metadata']['name'],'ready':any(condition['type']=='Ready' and condition['status']=='True' for condition in node['status']['conditions'])} for node in nodes],'secret_material_reported':False}))

if __name__=='__main__':main()
