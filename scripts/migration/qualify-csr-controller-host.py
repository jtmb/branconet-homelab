#!/usr/bin/env python3
"""Managed-host qualification for the observation-only CSR controller (node02).

Phases are exclusive. Approval is never enabled by any phase.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shlex
import subprocess

ROOT = Path(__file__).resolve().parents[2]
STAGE = Path("/mnt/h/AgentArtifacts/projects/branconet/builds/wsl-artifact-store/files/"
             "bortus-operator-recovery/certificates-qualification-20261116")
WORK = STAGE / "csr-host-activation"
NODE = "192.168.0.6"
TOOLS = r'''
import json,subprocess
PROPERTIES='LoadState,ActiveState,UnitFileState,InvocationID,MainPID,ControlGroup,Result'
def props(unit):
    raw=subprocess.check_output(['systemctl','show',unit,'--property='+PROPERTIES],text=True)
    return dict(line.split('=',1) for line in raw.splitlines() if '=' in line)
def messages(unit,count=40):
    out=[]
    for line in subprocess.check_output(['journalctl','-u',unit,'--all','-n',str(count),'-o','json','--no-pager'],text=True).splitlines():
        try:value=json.loads(json.loads(line).get('MESSAGE',''))
        except (ValueError,TypeError):continue
        if isinstance(value,dict):out.append(value)
    return out
'''
CREDENTIAL = TOOLS + r'''
import hashlib,json,stat,subprocess,time
from pathlib import Path
SERVICE='bortus-csr-controller-credential.service';TIMER='bortus-csr-controller-credential.timer'
TOKEN=Path('/run/bortus-csr-controller/token')
assert props(SERVICE)['ActiveState']=='inactive'
subprocess.run(['systemctl','enable','--now',TIMER],check=True,capture_output=True,timeout=30)
deadline=time.monotonic()+300;result=None
while time.monotonic()<deadline:
    for value in messages(SERVICE):
        if value.get('state')=='credential-refreshed':result=value;break
    if result and props(SERVICE)['ActiveState']=='inactive':break
    time.sleep(2)
assert result,'csr_credential_refresh_not_observed'
checks=result['permissionChecks']
allow=[c for c in checks if c['expectedAllowed']];deny=[c for c in checks if not c['expectedAllowed']]
assert len(allow)==4 and len(deny)>=20,(len(allow),len(deny))
assert not any('approval' in json.dumps(c['attributes']) and c['expectedAllowed'] for c in checks)
info=TOKEN.lstat();assert info.st_uid==0 and info.st_gid==997 and stat.S_IMODE(info.st_mode)==0o640
readable=subprocess.run(['runuser','-u','bortus-csr-controller','--','test','-r',str(TOKEN)]).returncode==0
writable=subprocess.run(['runuser','-u','bortus-csr-controller','--','test','-w',str(TOKEN)]).returncode==0
assert readable and not writable
for path in ['/etc/kubernetes/admin.conf','/run/bortus-csr-controller/.refresh.lock']:
    assert subprocess.run(['runuser','-u','bortus-csr-controller','--','test','-r',path]).returncode==1,path
for path in ['/usr/local/libexec/bortus-csr-controller/run-kubelet-csr-controller.py',
             '/etc/systemd/system/bortus-csr-controller.service','/etc/bortus-csr-controller']:
    assert subprocess.run(['runuser','-u','bortus-csr-controller','--','test','-w',path]).returncode==1,path
print(json.dumps({'passed':True,'credential':result,'allowChecks':len(allow),'denyChecks':len(deny),
 'token':{'inode':info.st_ino,'bytes':info.st_size,'uid':info.st_uid,'gid':info.st_gid,'mode':'0640'},
 'consumerReadableNotWritable':True,'bootstrapAndLockUnreadable':True,'codeProfileNotWritable':True,
 'timer':props(TIMER),'approvalEnabled':False}))
'''
SERVICE_PHASE = TOOLS + r'''
import hashlib,json,os,sqlite3,stat,subprocess,time
from pathlib import Path
SERVICE='bortus-csr-controller.service';STATE=Path('/var/lib/bortus-csr-controller');DB=STATE/'csr-controller.sqlite'
def observation():
    for value in reversed(messages(SERVICE,60)):
        if 'mode' in value and 'verdicts' in value:return value
    return None
assert props(SERVICE)['ActiveState'] in ('inactive','failed')
subprocess.run(['systemctl','enable','--now',SERVICE],check=True,capture_output=True,timeout=30)
deadline=time.monotonic()+120;first=None
while time.monotonic()<deadline:
    first=observation()
    if first:break
    time.sleep(2)
assert first and first['mode']=='observe' and first['approvalEnabled'] is False,'csr_controller_observation_missing'
assert first['csrMutationPerformed'] is False
unit=props(SERVICE);assert unit['ActiveState']=='active' and unit['UnitFileState']=='enabled'
pid=int(unit['MainPID']);status=dict(l.split(':',1) for l in Path('/proc',str(pid),'status').read_text().splitlines() if ':' in l)
assert status['Uid'].split()[0]=='997' and int(status['CapEff'].strip(),16)==0 and status['NoNewPrivs'].strip()=='1'
assert 'run-kubelet-csr-controller.py' in Path('/proc',str(pid),'cmdline').read_bytes().decode()
group=Path('/sys/fs/cgroup')/unit['ControlGroup'].lstrip('/')
kernel={n:(group/n).read_text().strip() for n in ['memory.max','memory.swap.max','cpu.max','pids.max','memory.current','memory.events']}
assert kernel['memory.max']=='134217728' and kernel['memory.swap.max']=='0'
assert kernel['cpu.max']=='5000 100000' and kernel['pids.max']=='32'
assert dict(r.split() for r in kernel['memory.events'].splitlines()).get('oom_kill')=='0'
info=DB.lstat();assert info.st_uid==997 and stat.S_IMODE(info.st_mode)==0o600
def dump():
    with sqlite3.connect(DB.as_uri()+'?mode=ro',uri=True,timeout=5) as db:
        assert db.execute('PRAGMA quick_check').fetchone()[0]=='ok'
        return {'decisions':db.execute('SELECT csr_uid,eligible,reasons,approved_at FROM kubelet_csr_decisions ORDER BY csr_uid').fetchall(),
                'approvals':db.execute('SELECT count(*) FROM kubelet_csr_approvals').fetchone()[0]}
before=dump();assert before['approvals']==0
subprocess.run(['systemctl','restart',SERVICE],check=True,capture_output=True,timeout=45)
after_unit=props(SERVICE);assert after_unit['InvocationID']!=unit['InvocationID'] and after_unit['ActiveState']=='active'
deadline=time.monotonic()+90;second=None
while time.monotonic()<deadline:
    for value in messages(SERVICE,80):
        if 'mode' in value and value.get('mode')=='observe':second=value
    if second:break
    time.sleep(2)
assert second and second['approvalEnabled'] is False
after=dump();assert after==before and DB.stat().st_ino==info.st_ino,'state_not_preserved_across_restart'
assert after['approvals']==0
print(json.dumps({'passed':True,'firstObservation':first,'secondObservation':second,'unit':after_unit,
 'kernel':kernel,'actualPythonUID':997,'CapEff':0,'NoNewPrivs':1,'databaseInode':info.st_ino,
 'durableStateBefore':before,'durableStateAfter':after,'restartPreservedState':True,
 'approvalEnabled':False,'approvalCount':0}))
'''


def save(name, value):
    with (WORK / name).open("x") as stream:
        json.dump(value, stream, indent=2)
        stream.write("\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=["credential", "service"])
    args = parser.parse_args()
    prefix = WORK / ("host-" + args.phase)
    assert not prefix.with_suffix(".started.json").exists(), "reconcile_existing_phase"
    assert json.loads((WORK / "host-install-result.json").read_text())["passed"]
    if args.phase == "service":
        assert json.loads((WORK / "host-credential.result.json").read_text())["passed"]
    prefix.with_suffix(".started.json").write_text(json.dumps({
        "phase": args.phase, "host": "node02",
        "sourceSHA256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "approvalEnabled": False}, indent=2) + "\n")
    spec = importlib.util.spec_from_file_location("saved_csr_host",
                                                 ROOT / "scripts/migration/saved-node-credential.py")
    saved = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(saved)
    password = saved.existing_password()
    code = CREDENTIAL if args.phase == "credential" else SERVICE_PHASE
    try:
        result = subprocess.run([
            "ssh", "-p", "2002", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=yes",
            "-o", "ConnectTimeout=8", "-i", "/home/brajam/.ssh/id_ed25519", "james@" + NODE,
            "sudo -S -p '' /usr/bin/python3 -B -c " + shlex.quote(code)],
            input=(password + "\n").encode(), capture_output=True, timeout=420)
        if result.returncode:
            (WORK / ("host-" + args.phase + ".failure.json")).write_text(json.dumps({
                "reason": "remote_phase_failed", "stderr": result.stderr.decode()[-1200:],
                "outcomeRequiresReconciliation": True}, indent=2) + "\n")
            raise RuntimeError("csr_host_phase_failed")
        value = json.loads(result.stdout)
        prefix.with_suffix(".result.json").write_text(json.dumps(value, indent=2) + "\n")
        print(json.dumps(value, indent=2))
        assert value["passed"]
    finally:
        password = None


if __name__ == "__main__":
    main()
