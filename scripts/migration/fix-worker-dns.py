#!/usr/bin/env python3
"""Use the verified working homelab DNS address for worker2 during migration."""
import json
import pathlib
import subprocess
import sys

REMOTE=r'''
import json,subprocess
before=subprocess.check_output(['resolvectl','dns','enp3s0'],text=True).strip()
changed=subprocess.run(['resolvectl','dns','enp3s0','192.168.0.6'],capture_output=True,text=True)
if changed.returncode:raise SystemExit('Temporary resolver override failed')
subprocess.run(['resolvectl','flush-caches'],check=True)
check=subprocess.run(['getent','ahostsv4','github.com'],capture_output=True,text=True,timeout=20)
print(json.dumps({'host':'192.168.0.5','interface':'enp3s0','original_runtime_dns':before,'temporary_runtime_dns':'192.168.0.6','github_resolution_passed':check.returncode==0,'persistent_configuration_changed':False,'pihole_policy_changed':False}))
'''

def main():
    request=json.load(sys.stdin)
    wrapper="import subprocess,sys\nr=subprocess.run("+repr(['sudo','-S','-p','','python3','-c',REMOTE])+",input="+repr(request['sudo_password']+'\n')+",text=True,capture_output=True)\nif r.returncode:raise SystemExit('Worker DNS repair failed')\nsys.stdout.write(r.stdout)\n"
    result=subprocess.run(['ssh','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-p','2002','james@192.168.0.5','python3','-'],input=wrapper,capture_output=True,text=True,timeout=35)
    if result.returncode:raise SystemExit('Worker DNS repair failed')
    report=json.loads(result.stdout)
    (pathlib.Path(__file__).resolve().parents[2]/'evidence/worker-dns-override.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report))
    raise SystemExit(0 if report['github_resolution_passed'] else 1)

if __name__=='__main__':main()
