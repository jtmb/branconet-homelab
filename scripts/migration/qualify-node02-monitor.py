#!/usr/bin/env python3
"""Exclusive live monitor phases; never restart the accepted credential timer."""
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
WORK = STAGE / "monitor-host-activation"
REMOTE = r'''
import datetime as dt,hashlib,json,os,sqlite3,stat,subprocess,time
from pathlib import Path
USER='bortus-certificate-monitor'
MONITOR='bortus-certificate-monitor.service'
SENDER='bortus-certificate-notifications.service'
STATE=Path('/var/lib/bortus-certificate-monitor')
DB=STATE/'monitor.sqlite'
def command(args,timeout=25):
 return subprocess.check_output(args,text=True,stderr=subprocess.PIPE,timeout=timeout)
def unit(name):
 raw=command(['systemctl','show',name,'--property=ActiveState,UnitFileState,InvocationID,MainPID,ControlGroup,NRestarts'])
 return dict(line.split('=',1) for line in raw.splitlines() if '=' in line)
def snapshot():
 raw=command(['runuser','-u',USER,'--','env','KUBECONFIG=/etc/bortus-certificate-monitor/kubeconfig.json','/usr/local/bin/kubectl','--request-timeout=5s','get','configmap','bortus-certificate-observations','-n','bortus','-o','json'],timeout=10)
 return json.loads(json.loads(raw)['data']['snapshot.json'])
def wait_snapshot(test,seconds=150):
 deadline=time.monotonic()+seconds
 while time.monotonic()<deadline:
  try:
   value=snapshot()
   if test(value):return value
  except (subprocess.SubprocessError,ValueError,KeyError):pass
  time.sleep(1)
 raise RuntimeError('expected_monitor_observation_timeout')
def database():
 i=DB.lstat();assert stat.S_ISREG(i.st_mode) and i.st_uid==998 and stat.S_IMODE(i.st_mode)==0o600 and i.st_size<=16*1024**2
 with sqlite3.connect(DB.as_uri()+'?mode=ro',uri=True,timeout=2) as db:
  assert db.execute('PRAGMA quick_check').fetchone()[0]=='ok'
  return {'inode':i.st_ino,'bytes':i.st_size,'runs':db.execute('SELECT id,state FROM certificate_monitor_runs ORDER BY rowid').fetchall(),'policy':db.execute('SELECT uid,revision FROM certificate_monitor_policy').fetchall(),'outbox':db.execute('SELECT id,resource,uid,state,created_at,delivered_at FROM certificate_monitor_outbox ORDER BY rowid').fetchall()}
def resources(name,memory,cpu,tasks):
 u=unit(name);assert u['ActiveState']=='active'
 pid=int(u['MainPID']);assert pid>0
 status=dict(line.split(':',1) for line in Path('/proc',str(pid),'status').read_text().splitlines() if ':' in line)
 assert status['Uid'].split()[0]=='998' and int(status['CapEff'].strip(),16)==0 and status['NoNewPrivs'].strip()=='1'
 group=Path('/sys/fs/cgroup')/u['ControlGroup'].lstrip('/')
 values={n:(group/n).read_text().strip() for n in ['memory.max','memory.swap.max','memory.current','memory.events','cpu.max','pids.max','pids.current']}
 assert values['memory.max']==str(memory) and values['memory.swap.max']=='0' and values['cpu.max']==cpu and values['pids.max']==str(tasks)
 events=dict(line.split() for line in values['memory.events'].splitlines());assert events.get('oom_kill')=='0'
 return {'unit':u,'kernel':values,'actualPythonUID':998,'CapEff':0,'NoNewPrivs':1,'sampledMemoryBytes':int(values['memory.current'])}
try:
 assert command(['hostname']).strip()=='node02'
 for p,h in PARAMS['hashes'].items():assert hashlib.sha256(Path(p).read_bytes()).hexdigest()==h,p
 assert unit('bortus-certificate-credential.timer')['ActiveState']=='active'
 result={'phase':PARAMS['phase']}
 if PARAMS['phase']=='paused':
  assert unit(MONITOR)['ActiveState']=='inactive' and not DB.exists()
  subprocess.run(['systemctl','start',MONITOR],check=True,capture_output=True,timeout=25)
  first=wait_snapshot(lambda v:v.get('mode')=='paused' and v.get('policy',{}).get('uid')==PARAMS['policyUID'] and v.get('lastRun') is None)
  before=database();assert not before['runs'] and not before['outbox']
  samples=[resources(MONITOR,268435456,'10000 100000',64)]
  first_unit=unit(MONITOR)
  duplicate=subprocess.run(['runuser','-u',USER,'--','env','KUBECONFIG=/etc/bortus-certificate-monitor/kubeconfig.json','python3','-B','/usr/local/libexec/bortus-certificate-monitor/run-certificate-monitor.py','--managed-host','--state-dir',str(STATE),'--once','--control-plane'],capture_output=True,text=True,timeout=20)
  assert duplicate.returncode==1 and json.loads(duplicate.stdout)['state']=='already-running'
  subprocess.run(['systemctl','restart',MONITOR],check=True,capture_output=True,timeout=45)
  second=wait_snapshot(lambda v:v.get('mode')=='paused' and v.get('heartbeatAt','')>first['heartbeatAt'])
  after=database();assert before==after and unit(MONITOR)['InvocationID']!=first_unit['InvocationID']
  samples.append(resources(MONITOR,268435456,'10000 100000',64))
  subprocess.run(['systemctl','enable',MONITOR],check=True,capture_output=True,timeout=15)
  result.update(pausedAcknowledged=True,noInventoryScanWhilePaused=True,duplicateOwnerRejected=True,actualServiceRestart=True,durableDatabasePreserved=True,database=after,samples=samples,monitorEnabled=True,notificationServiceStillStopped=unit(SENDER)['ActiveState']=='inactive')
 elif PARAMS['phase']=='restart-pending':
  observed=wait_snapshot(lambda v:v.get('mode')=='monitor' and v.get('lastRun',{}).get('state')=='complete' and any(o.get('uid')==PARAMS['eventUID'] and o.get('state')=='pending' for o in v.get('observations',[])),seconds=180)
  before=database();pending=[r for r in before['outbox'] if r[2]==PARAMS['eventUID']];assert len(pending)==1 and pending[0][5] is None and unit(SENDER)['ActiveState']=='inactive'
  old=unit(MONITOR);subprocess.run(['systemctl','restart',MONITOR],check=True,capture_output=True,timeout=45)
  again=wait_snapshot(lambda v:v.get('heartbeatAt','')>observed['heartbeatAt'] and v.get('lastRun',{}).get('id')==observed['lastRun']['id'])
  after=database();assert before==after and unit(MONITOR)['InvocationID']!=old['InvocationID']
  result.update(realNativePendingObserved=True,durablePendingEvent=pending[0],restartDidNotRepeatRecentScan=True,noDuplicateOutbox=True,database=after,sample=resources(MONITOR,268435456,'10000 100000',64))
 elif PARAMS['phase']=='sender':
  before=database();events=[r for r in before['outbox'] if r[2]==PARAMS['eventUID']];assert len(events)==1 and events[0][5] is None
  subprocess.run(['systemctl','enable','--now',SENDER],check=True,capture_output=True,timeout=25)
  deadline=time.monotonic()+90
  while time.monotonic()<deadline:
   after=database();rows=[r for r in after['outbox'] if r[0]==events[0][0]]
   if len(rows)==1 and rows[0][5] is not None:break
   time.sleep(1)
  else:raise RuntimeError('real_outbox_delivery_timeout')
  first=unit(SENDER);subprocess.run(['systemctl','restart',SENDER],check=True,capture_output=True,timeout=45)
  deadline=time.monotonic()+20
  while unit(SENDER)['ActiveState']!='active' and time.monotonic()<deadline:time.sleep(.5)
  final=database();delivered=[r for r in final['outbox'] if r[0]==events[0][0]]
  assert delivered==rows and unit(SENDER)['InvocationID']!=first['InvocationID']
  result.update(realRunnerOutboxDelivered=True,deliveredEvent=delivered[0],senderRestartPreservedAcknowledgement=True,database=final,sample=resources(SENDER,134217728,'5000 100000',32),serverAckNotHumanReceipt=True)
 result['passed']=True
 result['credentialTimerStillActive']=unit('bortus-certificate-credential.timer')['ActiveState']=='active'
 print(json.dumps(result))
except Exception as error:
 print(json.dumps({'passed':False,'phase':PARAMS['phase'],'reason':str(error) if isinstance(error,RuntimeError) else type(error).__name__,'reconcileBeforeRetry':True,'privateOutputWithheld':True}))
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=["paused", "restart-pending", "sender"])
    phase = parser.parse_args().phase
    prefix = WORK / ("monitor-" + phase)
    assert not prefix.with_suffix(".started.json").exists(), "reconcile_prior_phase"
    assert json.loads((WORK / "upgrade-result.json").read_text())["passed"]
    control = json.loads((WORK / "control-flux-result.json").read_text())
    hashes = json.loads((WORK / "upgrade-started.json").read_text())["installedExpectedHashes"]
    hashes["/etc/systemd/system/bortus-certificate-monitor.service"] = hashlib.sha256(
        (ROOT / "k8s-rewrite/ansible-playbook/playbooks/files/bortus-certificate-monitor.service").read_bytes()).hexdigest()
    for name in ("certificate_monitor_notifications.py", "deliver-certificate-notifications.py"):
        hashes["/usr/local/libexec/bortus-certificate-monitor/" + name] = hashlib.sha256(
            (ROOT / "scripts/migration" / name).read_bytes()).hexdigest()
    params = {"phase": phase, "hashes": hashes, "policyUID": control["policy"]["uid"]}
    if phase != "paused":
        assert json.loads((WORK / "monitor-paused.result.json").read_text())["passed"]
        params["eventUID"] = json.loads((WORK / "native-alert-event.json").read_text())["uid"]
    if phase == "sender":
        assert json.loads((WORK / "monitor-restart-pending.result.json").read_text())["passed"]
    prefix.with_suffix(".started.json").write_text(json.dumps({
        "phase": phase, "hashes": hashes,
        "sourceSHA256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}, indent=2) + "\n")
    spec = importlib.util.spec_from_file_location("saved_monitor_qualification",
                                                ROOT / "scripts/migration/saved-node-credential.py")
    saved = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(saved)
    password = saved.existing_password()
    try:
        result = subprocess.run(["ssh", "-p", "2002", "-o", "BatchMode=yes", "-o",
            "StrictHostKeyChecking=yes", "-o", "ConnectTimeout=8", "-i",
            "/home/brajam/.ssh/id_ed25519", "james@192.168.0.6",
            "sudo -S -p '' python3 -B -c " + shlex.quote("PARAMS=" + repr(params) + "\n" + REMOTE)],
            input=(password + "\n").encode(), capture_output=True, timeout=400)
        assert result.returncode == 0, "remote_phase_unknown"
        value = json.loads(result.stdout)
        prefix.with_suffix(".result.json").write_text(json.dumps(value, indent=2) + "\n")
        print(json.dumps(value, indent=2))
        assert value["passed"], "reconcile_remote_phase"
    finally:
        password = None


if __name__ == "__main__":
    main()
