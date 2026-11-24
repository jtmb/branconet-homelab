#!/usr/bin/env python3
"""Detector health, real monitor outage, real recovery and host delivery.

Phases are exclusive and no successful/unknown phase is repeated. The outage is
a bounded stop of the accepted node02 monitor; it is always restarted and its
private database/policy are never replaced. Acknowledgement is host delivery,
not attended human receipt.
"""
import argparse
import datetime as dt
import hashlib
import importlib.util
import json
from pathlib import Path
import shlex
import subprocess
import time

ROOT = Path(__file__).resolve().parents[2]
STAGE = Path("/mnt/h/AgentArtifacts/projects/branconet/builds/wsl-artifact-store/files/"
             "bortus-operator-recovery/certificates-qualification-20261116")
WORK = STAGE / "watchdog-host-activation"
NODE03, NODE02 = "192.168.0.5", "192.168.0.6"
REMOTE_TOOLS = r'''
import json,subprocess
PROPERTIES='LoadState,ActiveState,UnitFileState,InvocationID,MainPID,NRestarts,Result,ExecMainStatus'
def props(unit):
    raw=subprocess.check_output(['systemctl','show',unit,'--property='+PROPERTIES],text=True)
    return dict(line.split('=',1) for line in raw.splitlines() if '=' in line)
def journal(unit,count=40):
    rows=[]
    for line in subprocess.check_output(['journalctl','-u',unit,'--all','-n',str(count),'-o','json','--no-pager'],text=True).splitlines():
        try:value=json.loads(json.loads(line).get('MESSAGE',''))
        except (ValueError,TypeError):continue
        if isinstance(value,dict):rows.append(value)
    return rows
'''
DETECTOR = r'''
import json,os,sqlite3,stat,subprocess,time
from pathlib import Path
UNIT='bortus-certificate-watchdog.service'
STATE=Path('/var/lib/bortus-certificate-watchdog');DB=STATE/'watchdog.sqlite'
def unit():
    return dict(line.split('=',1) for line in subprocess.check_output(['systemctl','show',UNIT,'--property=ActiveState,UnitFileState,InvocationID,MainPID,ControlGroup'],text=True).splitlines() if '=' in line)
def observations(count=200):
    rows=[]
    for line in subprocess.check_output(['journalctl','-u',UNIT,'--all','-n',str(count),'-o','json','--no-pager'],text=True).splitlines():
        try:value=json.loads(json.loads(line).get('MESSAGE',''))
        except (ValueError,TypeError):continue
        if isinstance(value,dict) and 'coverage' in value:rows.append(value)
    return rows
def database():
    info=DB.lstat()
    assert stat.S_ISREG(info.st_mode) and info.st_uid==997 and stat.S_IMODE(info.st_mode)==0o600
    # The long-running detector may hold a hot journal for a moment; a read-only
    # open can fail transiently. Retry without ever opening the DB read-write.
    deadline=time.monotonic()+15
    while True:
        try:
            with sqlite3.connect(DB.as_uri()+'?mode=ro',uri=True,timeout=2) as db:
                assert db.execute('PRAGMA quick_check').fetchone()[0]=='ok'
                return {'inode':info.st_ino,'bytes':info.st_size,
                        'state':db.execute('SELECT reason,state FROM certificate_watchdog_state ORDER BY reason').fetchall(),
                        'outbox':db.execute('SELECT id,resource,uid,state,created_at,delivered_at FROM certificate_monitor_outbox ORDER BY rowid').fetchall()}
        except sqlite3.OperationalError:
            if time.monotonic()>=deadline:raise
            time.sleep(.5)
def resources():
    u=unit();assert u['ActiveState']=='active'
    pid=int(u['MainPID'])
    status=dict(line.split(':',1) for line in Path('/proc',str(pid),'status').read_text().splitlines() if ':' in line)
    assert status['Uid'].split()[0]=='997' and int(status['CapEff'].strip(),16)==0 and status['NoNewPrivs'].strip()=='1'
    assert 'run-certificate-watchdog.py' in Path('/proc',str(pid),'cmdline').read_bytes().decode()
    group=Path('/sys/fs/cgroup')/u['ControlGroup'].lstrip('/')
    kernel={name:(group/name).read_text().strip() for name in ['memory.max','memory.swap.max','cpu.max','pids.max','memory.current','memory.events']}
    assert kernel['memory.max']=='134217728' and kernel['memory.swap.max']=='0'
    assert kernel['cpu.max']=='5000 100000' and kernel['pids.max']=='32'
    assert dict(row.split() for row in kernel['memory.events'].splitlines()).get('oom_kill')=='0'
    directory=STATE.stat();assert directory.st_uid==997 and stat.S_IMODE(directory.st_mode)&0o077==0
    return {'unit':u,'kernel':kernel,'actualPythonUID':997,'CapEff':0,'NoNewPrivs':1}
'''


def save(name, value):
    with (WORK / name).open("x") as stream:
        json.dump(value, stream, indent=2)
        stream.write("\n")


def ssh(host, code, password, timeout=240, data=None):
    command = ["ssh", "-p", "2002", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=yes",
               "-o", "ConnectTimeout=8", "-i", "/home/brajam/.ssh/id_ed25519", "james@" + host,
               "sudo -S -p '' /usr/bin/python3 -B -c " + shlex.quote(code)]
    payload = (password + "\n").encode() + (data or b"")
    result = subprocess.run(command, input=payload, capture_output=True, timeout=timeout)
    if result.returncode:
        raise RuntimeError("remote_phase_failed")
    return json.loads(result.stdout)


def node02_monitor(password):
    code = REMOTE_TOOLS + r'''
print(json.dumps({'monitor':props('bortus-certificate-monitor.service'),
                  'notifications':props('bortus-certificate-notifications.service'),
                  'timer':props('bortus-certificate-credential.timer'),
                  'databaseInode':__import__('os').stat('/var/lib/bortus-certificate-monitor/monitor.sqlite').st_ino}))
'''
    return ssh(NODE02, code, password, timeout=40)


def healthy(password):
    code = REMOTE_TOOLS + DETECTOR + r'''
before=unit()
assert before['ActiveState'] in ('inactive',) and before['UnitFileState']=='disabled'
assert Path('/var/lib/bortus-certificate-watchdog').exists() is False
subprocess.run(['systemctl','start',UNIT],check=True,capture_output=True,timeout=25)
deadline=time.monotonic()+150;healthy=None
while time.monotonic()<deadline:
    for value in observations(80):
        if all(value.get(key)=='healthy' for key in ('coverage','monitorHeartbeat','node02Lease')):
            healthy=value;break
    if healthy:break
    time.sleep(2)
assert healthy,'detector_healthy_state_timeout'
subprocess.run(['systemctl','enable',UNIT],check=True,capture_output=True,timeout=15)
state=database();assert not state['outbox'] and all(row[1]=='healthy' for row in state['state'])
sample=resources()
print(json.dumps({'passed':True,'detectorHealthyObservation':healthy,'database':state,'resources':sample,
                  'detectorEnabled':True,'notifierStillInactive':props('bortus-certificate-watchdog-notifications.service').get('ActiveState')=='inactive'}))
'''
    return ssh(NODE03, code, password, timeout=260)


def wait_event(password, matched, seconds, label):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        record = detector_state(password)
        found = [row for row in record["database"]["outbox"] if matched(row)]
        if found:
            return found
        time.sleep(5)
    raise RuntimeError(label)


def detector_state(password):
    code = REMOTE_TOOLS + DETECTOR + r'''
print(json.dumps({'unit':unit(),'database':database(),
                  'notifier':props('bortus-certificate-watchdog-notifications.service'),
                  'observations':observations(30)[-3:]}))
'''
    return ssh(NODE03, code, password, timeout=45)


def outage(password):
    healthy_before = node02_monitor(password)
    assert healthy_before["monitor"]["ActiveState"] == "active"
    assert healthy_before["timer"]["ActiveState"] == "active"
    save("detector-healthy-baseline.json", {
        "monitor": healthy_before["monitor"], "databaseInode": healthy_before["databaseInode"],
        "monitorDatabaseIsNotReplacedByOutage": True})
    code = REMOTE_TOOLS + DETECTOR + r'''
subprocess.run(['systemctl','stop','bortus-certificate-monitor.service'],check=True,capture_output=True,timeout=45)
print(json.dumps({'stopped':props('bortus-certificate-monitor.service')}))
'''
    stopped = ssh(NODE02, code, password, timeout=70)
    assert stopped["stopped"]["ActiveState"] == "inactive"
    opened = dt.datetime.now(dt.timezone.utc)
    try:
        missed = wait_event(password, lambda row: row[1] == "monitor-heartbeat" and row[3] == "missed",
                            420, "watchdog_missed_heartbeat_not_observed")
        detection = (dt.datetime.now(dt.timezone.utc) - opened).total_seconds()
        state = detector_state(password)
        assert state["observations"][-1]["monitorHeartbeat"] == "missed"
        assert state["observations"][-1]["node02Lease"] == "healthy"
        assert state["observations"][-1]["coverage"] == "healthy"
        assert state["notifier"]["LoadState"] == "loaded"
        save("detector-missed-event.json", {
            "event": missed[0], "detectionSeconds": detection,
            "lastObservation": state["observations"][-1],
            "leaseStayedHealthyWhileMonitorHeartbeatMissed": True,
            "notifierNotStartedByDetector": True})
        notify = REMOTE_TOOLS + DETECTOR + r'''
subprocess.run(['systemctl','enable','--now','bortus-certificate-watchdog-notifications.service'],check=True,capture_output=True,timeout=40)
deadline=time.monotonic()+180;delivered=None;ack=None
while time.monotonic()<deadline:
    for value in journal('bortus-certificate-watchdog-notifications.service',40):
        if 'acceptedByServer' in value:ack=value
    rows=database()['outbox']
    if any(row[5] is not None for row in rows):delivered=rows;break
    time.sleep(3)
assert delivered and ack,'watchdog_notification_delivery_timeout'
print(json.dumps({'delivered':delivered,'acknowledgement':ack,
                  'notifier':props('bortus-certificate-watchdog-notifications.service')}))
'''
        sent = ssh(NODE03, notify, password, timeout=220)
        save("detector-missed-delivery.json", {
            "passed": True, "acknowledgement": sent["acknowledgement"],
            "deliveredOutbox": sent["delivered"], "serverAckNotHumanReceipt": True})
        restore = REMOTE_TOOLS + DETECTOR + r'''
subprocess.run(['systemctl','start','bortus-certificate-monitor.service'],check=True,capture_output=True,timeout=45)
print(json.dumps({'monitor':props('bortus-certificate-monitor.service')}))
'''
        restarted = ssh(NODE02, restore, password, timeout=70)
        try:
            recovered = wait_event(password, lambda row: row[1] == "monitor-heartbeat" and row[3] == "recovered",
                                   420, "watchdog_recovery_not_observed")
            final = detector_state(password)
            after = node02_monitor(password)
            assert after["monitor"]["ActiveState"] == "active"
            assert after["databaseInode"] == healthy_before["databaseInode"]
            assert final["observations"][-1]["monitorHeartbeat"] == "healthy"
            save("detector-recovered-event.json", {
                "passed": True, "monitorRestarted": restarted["monitor"],
                "recoveredEvent": recovered[0], "lastObservation": final["observations"][-1],
                "monitorDatabaseInodePreserved": after["databaseInode"],
                "supervisorTimerStillActive": after["timer"]["ActiveState"] == "active"})
        finally:
            pass
    finally:
        final_state = node02_monitor(password)
        if final_state["monitor"]["ActiveState"] != "active":
            ssh(NODE02, REMOTE_TOOLS + r'''
subprocess.run(['systemctl','start','bortus-certificate-monitor.service'],check=True,capture_output=True,timeout=45)
print(json.dumps({'forcedRestart':props('bortus-certificate-monitor.service')}))
''', password, timeout=70)
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=["healthy", "outage"])
    parser.add_argument("--attempt", default="",
                        help="Short path-safe label for a reconciled unstarted retry")
    args = parser.parse_args()
    if args.attempt and (not args.attempt.replace("-", "").isalnum() or len(args.attempt) > 32):
        parser.error("Short path-safe attempt label required")
    prefix = WORK / ("detector-" + args.phase + ("-" + args.attempt if args.attempt else ""))
    if args.attempt:
        prior = WORK / ("detector-" + args.phase + ".failure.json")
        assert prior.is_file(), "named_attempt_requires_reconciled_failure"
        assert json.loads(prior.read_text())["outcomeRequiresReconciliation"] is True
    assert not prefix.with_suffix(".started.json").exists(), "reconcile_existing_phase"
    assert json.loads((WORK / "runtime-install-result.json").read_text())["passed"]
    assert json.loads((WORK / "credential-observe.result.json").read_text())["periodicRefreshObserved"]
    if args.phase == "outage":
        assert json.loads((WORK / "detector-healthy.result.json").read_text())["passed"]
    prefix.with_suffix(".started.json").write_text(json.dumps({
        "phase": args.phase, "sourceSHA256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "boundedNode02MonitorStop": args.phase == "outage",
        "monitorAlwaysRestarted": args.phase == "outage"}, indent=2) + "\n")
    spec = importlib.util.spec_from_file_location("saved_watchdog_detector",
                                                ROOT / "scripts/migration/saved-node-credential.py")
    saved = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(saved)
    password = saved.existing_password()
    try:
        value = healthy(password) if args.phase == "healthy" else {"passed": outage(password)}
        prefix.with_suffix(".result.json").write_text(json.dumps(value, indent=2) + "\n")
        print(json.dumps(value, indent=2))
        assert value["passed"]
    except Exception as error:
        prefix.with_suffix(".failure.json").write_text(json.dumps({
            "reason": str(error) if isinstance(error, RuntimeError) else type(error).__name__,
            "outcomeRequiresReconciliation": True}, indent=2) + "\n")
        raise
    finally:
        password = None


if __name__ == "__main__":
    main()
