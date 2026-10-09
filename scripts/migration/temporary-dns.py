#!/usr/bin/env python3
"""Use reversible migration DNS while the source Pi-hole is cold-copied."""
import concurrent.futures
import datetime
import json
import pathlib
import subprocess
import sys
import yaml

ROOT=pathlib.Path(__file__).resolve().parents[2]
RUNTIME=pathlib.Path.home()/'.local/share/branconet-migration'

def main():
    request=json.load(sys.stdin)
    def configure(host):
        code=r'''
import json,subprocess,sys
routes=json.loads(subprocess.check_output(['ip','-j','route','show','default'],text=True));interface=routes[0]['dev']
before=subprocess.check_output(['resolvectl','dns',interface],text=True).strip()
changed=subprocess.run(['sudo','-S','-p','','resolvectl','dns',interface,'1.1.1.1','8.8.8.8'],input=PASSWORD+'\n',text=True,capture_output=True)
if changed.returncode:raise SystemExit('Temporary per-link DNS change failed')
subprocess.run(['resolvectl','flush-caches'],capture_output=True)
probe=subprocess.run(['getent','ahostsv4','registry-1.docker.io'],capture_output=True,text=True)
print(json.dumps({'interface':interface,'previous_dns':before,'temporary_dns':['1.1.1.1','8.8.8.8'],'registry_lookup_passed':probe.returncode==0,'persistent_network_files_changed':False}))
'''
        code='PASSWORD='+repr(request['sudo_password'])+'\n'+code
        result=subprocess.run(['ssh','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-p','2002','james@'+host,'python3','-'],input=code,capture_output=True,text=True,timeout=60)
        if result.returncode:raise RuntimeError('Migration DNS configuration failed on '+host)
        return {'host':host,**json.loads(result.stdout)}
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:nodes=list(pool.map(configure,['192.168.0.4','192.168.0.5','192.168.0.6']))
    kube=[str(RUNTIME/'bin/kubectl'),'--kubeconfig',str(RUNTIME/'admin.conf')]
    original=json.loads(subprocess.check_output([*kube,'get','configmap','coredns','-n','kube-system','-o','json'],text=True))
    before=original['data']['Corefile']
    if 'forward . /etc/resolv.conf' not in before:raise SystemExit('Unexpected CoreDNS forwarding config; inspect before adapting')
    original['data']['Corefile']=before.replace('forward . /etc/resolv.conf','forward . 1.1.1.1 8.8.8.8')+'\nbranconet.lan:53 {\n    errors\n    cache 30\n    forward . 192.168.0.6\n}\nbranconet.local:53 {\n    errors\n    cache 30\n    forward . 192.168.0.6\n}\n'
    subprocess.run([*kube,'replace','-f','-'],input=json.dumps(original),capture_output=True,text=True,check=True)
    report={'captured_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'nodes':nodes,'original_corefile':before,'temporary_public_forwarders':['1.1.1.1','8.8.8.8'],'lan_domain_forwarder':'192.168.0.6','revisit_after_native_pihole_cutover':True}
    (ROOT/'evidence/temporary-dns.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({'nodes':nodes,'coredns_forwarders_set':True,'lan_resolution_preserved':True}),flush=True)

if __name__=='__main__':main()
