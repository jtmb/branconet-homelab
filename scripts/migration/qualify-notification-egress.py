#!/usr/bin/env python3
"""One live sender-cgroup allow/deny check, then resume its unchanged outbox."""
import hashlib
import importlib.util
import json
from pathlib import Path
import shlex
import subprocess

ROOT = Path(__file__).resolve().parents[2]
WORK = Path("/mnt/h/AgentArtifacts/projects/branconet/builds/wsl-artifact-store/files/"
            "bortus-operator-recovery/certificates-qualification-20261116/monitor-host-activation")
PROBE = r'''
import http.client,json,os,socket,ssl
assert os.geteuid()==998
class C(http.client.HTTPSConnection):
 def connect(self):
  self.sock=self._context.wrap_socket(socket.create_connection(('192.168.0.252',443),timeout=3),server_hostname=self.host)
c=C('notifications.branconet.lan',context=ssl.create_default_context(cafile='/etc/bortus-certificate-monitor/notification-ca.crt'),timeout=3)
c.request('GET','/v1/health');r=c.getresponse();r.read(4096);assert r.status==200;c.close()
denied=[]
for endpoint in [('192.168.0.251',6443),('192.168.0.252',80)]:
 try:
  sock=socket.create_connection(endpoint,timeout=2);sock.close()
 except OSError:denied.append(endpoint)
 else:raise RuntimeError('unexpected_egress_allowed')
print(json.dumps({'egressQualification':True,'positiveTrustedHTTPS':200,'deniedEndpoints':denied,'UID':os.geteuid(),'tokenReadOrPublish':False}),flush=True)
'''
REMOTE = r'''
import hashlib,json,os,socket,sqlite3,subprocess,time
from pathlib import Path
UNIT='bortus-certificate-notifications.service'
def run(args,timeout=25):
 return subprocess.check_output(args,text=True,stderr=subprocess.PIPE,timeout=timeout)
def state():
 return dict(l.split('=',1) for l in run(['systemctl','show',UNIT,'--property=ActiveState,SubState,Result,InvocationID']).splitlines() if '=' in l)
assert state()['ActiveState']=='inactive'
assert hashlib.sha256(Path('/usr/local/libexec/bortus-certificate-monitor/certificate_notification_firewall.py').read_bytes()).hexdigest()==HELPER_SHA
for endpoint in [('192.168.0.251',6443),('192.168.0.252',80)]:
 sock=socket.create_connection(endpoint,timeout=3);sock.close()
path=Path('/run/bortus-notification-egress-probe.py')
directory=Path('/run/systemd/system/bortus-certificate-notifications.service.d')
assert not path.exists() and not directory.exists()
path.write_text(PROBE);path.chmod(0o644);directory.mkdir(mode=0o755)
drop=directory/'qualification.conf'
settings='[Service]\nRestart=no\nExecStart=\nExecStart=/usr/bin/python3 -B '+str(path)+'\n'
drop.write_text(settings);drop.chmod(0o644)
run(['systemctl','daemon-reload'])
start=subprocess.run(['systemctl','start',UNIT],capture_output=True,text=True,timeout=25)
deadline=time.monotonic()+90
while state()['ActiveState'] in ['active','activating','deactivating'] and time.monotonic()<deadline:time.sleep(.2)
final=state()
logs=[json.loads(l) for l in run(['journalctl','-u',UNIT,'--all','-n','30','-o','json','--no-pager']).splitlines()]
messages=[l.get('MESSAGE','') for l in logs]
proof=[]
for message in messages:
 try:value=json.loads(message)
 except (ValueError,TypeError):continue
 if value.get('egressQualification'):proof.append(value)
if start.returncode or final['Result']!='success' or len(proof)!=1:
 print(json.dumps({'passed':False,'state':final,'unitMessages':messages,'runtimeOverridesRetainedForReconciliation':True}))
 raise SystemExit(1)
assert proof[0]['positiveTrustedHTTPS']==200 and len(proof[0]['deniedEndpoints'])==2
tables=json.loads(run(['nft','-j','list','tables']))['nftables']
assert not any(v.get('table',{}).get('name')=='bortus_certificate_notifications' for v in tables)
assert path.read_text()==PROBE and drop.read_text()==settings
drop.unlink();directory.rmdir();path.unlink()
run(['systemctl','daemon-reload'])
run(['systemctl','start',UNIT])
active=state();assert active['ActiveState']=='active'
print(json.dumps({'passed':True,'realSenderCgroupPositiveNegative':proof[0],'probeEndedPolicyRemoved':True,'runtimeOverrideAndProbeRemoved':True,'actualSenderResumed':active,'backoffOrEventReset':False,'currentPodOrSubnetAllowAdded':False}))
'''


def main():
    assert json.loads((WORK / "egress-repair-result.json").read_text())["passed"]
    assert not (WORK / "egress-live-started.json").exists(), "reconcile_prior_qualification"
    helper = hashlib.sha256((ROOT / "scripts/migration/certificate_notification_firewall.py").read_bytes()).hexdigest()
    (WORK / "egress-live-started.json").write_text(json.dumps({
        "sourceSHA256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "helperSHA256": helper, "noTokenReadOrPublishByProbe": True,
        "oneSenderOnlyNoMonitorOrTimerRestart": True}, indent=2) + "\n")
    spec = importlib.util.spec_from_file_location("saved_egress", ROOT / "scripts/migration/saved-node-credential.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    password = module.existing_password()
    try:
        result = subprocess.run(["ssh", "-p", "2002", "-o", "BatchMode=yes", "-o",
            "StrictHostKeyChecking=yes", "-i", "/home/brajam/.ssh/id_ed25519", "james@192.168.0.6",
            "sudo -S -p '' python3 -B -c " + shlex.quote(
                "PROBE=" + repr(PROBE) + "\nHELPER_SHA=" + repr(helper) + "\n" + REMOTE)],
            input=(password + "\n").encode(), capture_output=True, timeout=180)
        if result.stdout:
            value = json.loads(result.stdout)
            (WORK / "egress-live-result.json").write_text(json.dumps(value, indent=2) + "\n")
            print(json.dumps(value, indent=2))
        assert result.returncode == 0, "reconcile_live_egress_before_retry"
    finally:
        password = None


if __name__ == "__main__":
    main()
