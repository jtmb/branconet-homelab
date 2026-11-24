#!/usr/bin/env python3
"""Owned node02 credential-service qualification; never starts the monitor.

Uses the existing saved sudo credential in memory/stdin, not arguments/logs.
Each phase has exclusive H receipts. Observe is read-only and may wait for the
real twenty-minute timer; interruption never authorizes restarting that timer.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shlex
import sys

from certificate_monitor_process import run_bounded

REPO = Path(__file__).resolve().parents[2]
STAGE = Path("/mnt/h/AgentArtifacts/projects/branconet/builds/wsl-artifact-store/files/bortus-operator-recovery/certificates-qualification-20261116")
REMOTE = r'''
import datetime as dt,hashlib,json,os,selectors,socket,subprocess,sys,time
import shlex
from pathlib import Path
PROFILE=PARAMS.get('profile','monitor')
if PROFILE not in ('monitor','watchdog'):raise RuntimeError('fixed_qualification_profile_required')
IS_WATCHDOG=PROFILE=='watchdog'
SERVICE='bortus-certificate-watchdog-credential.service' if IS_WATCHDOG else 'bortus-certificate-credential.service'
TIMER='bortus-certificate-watchdog-credential.timer' if IS_WATCHDOG else 'bortus-certificate-credential.timer'
MONITOR='bortus-certificate-watchdog.service' if IS_WATCHDOG else 'bortus-certificate-monitor.service'
RUNTIME=Path('/run/bortus-certificate-watchdog' if IS_WATCHDOG else '/run/bortus-certificate-monitor')
PHASE=PARAMS['phase']
EVIDENCE={}
def need(value,code):
    if not value: raise RuntimeError(code)
def props(unit):
    text=subprocess.check_output(['systemctl','show',unit],text=True,timeout=10)
    return dict(line.split('=',1) for line in text.splitlines() if '=' in line)
def next_due():
    root='/org/freedesktop/systemd1'
    value=shlex.split(subprocess.check_output(['busctl','call','org.freedesktop.systemd1',root,
        'org.freedesktop.systemd1.Manager','GetUnit','s',TIMER],text=True,timeout=10))
    need(value[0]=='o','timer_object_path_invalid')
    raw=subprocess.check_output(['busctl','get-property','org.freedesktop.systemd1',value[1],
        'org.freedesktop.systemd1.Timer','NextElapseUSecMonotonic'],text=True,timeout=10).split()
    need(raw[0]=='t','timer_due_type_invalid')
    return int(raw[1])
def monitor_off():
    value=props(MONITOR)
    if IS_WATCHDOG:
        need(value.get('LoadState')=='not-found','watchdog_detector_already_installed')
    else:
        need(value.get('ActiveState')=='inactive' and value.get('UnitFileState')=='disabled','monitor_not_disabled_inactive')
def token_info():
    p=RUNTIME/'token';s=p.lstat()
    need(p.is_file() and not p.is_symlink() and s.st_uid==0 and s.st_mode&0o777==0o640,'token_mode_owner_invalid')
    if IS_WATCHDOG:need(s.st_gid==997,'watchdog_token_group_mismatch')
    return {'inode':s.st_ino,'mtimeNS':s.st_mtime_ns,'bytes':s.st_size,'uid':s.st_uid,'gid':s.st_gid,'mode':'0640'}
def last_success():
    # journalctl otherwise replaces JSON fields over 4096 bytes with null.
    # The metadata-only 26-check result is larger than that default threshold.
    raw=subprocess.check_output(['journalctl','-u',SERVICE,'-o','json','--all','--no-pager','-n','100'],text=True,timeout=10)
    values=[]
    for line in raw.splitlines():
        row=json.loads(line)
        try:value=json.loads(row.get('MESSAGE',''))
        except (ValueError,TypeError):continue
        if value.get('state')=='credential-refreshed':
            values.append({'result':value,'invocationID':row.get('_SYSTEMD_INVOCATION_ID'),
                           'monotonicUSec':int(row['__MONOTONIC_TIMESTAMP'])})
    need(values,'no_successful_broker_record')
    return values[-1]
def verify_result():
    p=props(SERVICE)
    need(p.get('Result')=='success' and p.get('ExecMainStatus')=='0' and p.get('ActiveState')=='inactive','credential_service_failed')
    value=last_success()
    need(value['result']['serviceAccountUID']==PARAMS['uid'],'published_uid_mismatch')
    checks=value['result']['permissionChecks']
    expected_counts=(2,30) if IS_WATCHDOG else (7,19)
    need((sum(x['expectedAllowed'] for x in checks),sum(not x['expectedAllowed'] for x in checks))==expected_counts,'permission_check_counts')
    if IS_WATCHDOG:
        need(value['result']['subject']=='system:serviceaccount:bortus:bortus-certificate-watchdog','watchdog_subject_mismatch')
        need(value['result']['metadataCounts']=={'ConfigMap':1,'Lease':1},'watchdog_exact_reads_mismatch')
    need(not list(RUNTIME.glob('.pending-*')),'pending_credential_files_remain')
    monitor_off()
    return {'service':{k:p.get(k) for k in ['Result','ExecMainStatus','ActiveState','CPUUsageNSec','MemoryCurrent','TasksCurrent',
            'MemoryMax','MemorySwapMax','CPUQuotaPerSecUSec','TasksMax','LimitFSIZE','NoNewPrivileges','ProtectSystem','ProtectHome',
            'CapabilityBoundingSet','IPIngressBytes','IPEgressBytes','ExecMainStartTimestampMonotonic']},
             'credential':value,'tokenMetadata':token_info(),
             ('watchdogDetectorAbsent' if IS_WATCHDOG else 'monitorDisabledInactive'):True}
def wait_finished(deadline):
    while time.monotonic()<deadline:
        p=props(SERVICE)
        if p.get('ActiveState') not in ('activating','active','deactivating'):
            return
        time.sleep(.2)
    raise RuntimeError('credential_service_wait_timeout')
def capture_run():
    job=subprocess.Popen(['systemctl','start',SERVICE],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    samples=[];status=None;first_status=None
    while job.poll() is None:
        p=props(SERVICE);group=p.get('ControlGroup','')
        if group.startswith('/system.slice/') and p.get('MainPID','0')!='0':
            base=Path('/sys/fs/cgroup'+group)
            if base.exists() and (base/'memory.max').exists():
                def read(name):
                    try:return (base/name).read_text().strip()
                    except FileNotFoundError:return None
                samples.append({k:read(k) for k in ['memory.max','memory.swap.max','memory.current','memory.peak','pids.max','pids.current','cpu.max','cpu.stat','memory.events']})
                proc=Path('/proc')/p['MainPID']/'status'
                if proc.exists():
                    observed={k:v.strip() for k,v in (line.split(':',1) for line in proc.read_text().splitlines() if ':' in line)
                              if k in ['Name','Uid','Gid','NoNewPrivs','CapEff','CapBnd']}
                    if first_status is None:first_status=observed
                    # MainPID can identify systemd's executor before it applies
                    # the final exec security context. Qualify the broker itself.
                    if observed.get('Name','').startswith('python'):status=observed
                    EVIDENCE.update(firstProcessSecurity=first_status,lastBrokerSecurity=status,
                                    kernelLast=samples[-1],resourceSampleCount=len(samples))
        if len(samples)>2500:raise RuntimeError('resource_observation_limit')
        time.sleep(.1)
    out,err=job.communicate(timeout=5)
    need(job.returncode==0,'credential_service_start_failed')
    need(samples,'no_live_kernel_resource_observation')
    for sample in samples:
        need(sample['memory.max']=='268435456' and sample['memory.swap.max']=='0' and sample['pids.max']=='64','kernel_limits_mismatch')
        if sample['cpu.max']:
            quota,period=map(int,sample['cpu.max'].split())
            need(quota*10==period,'kernel_cpu_quota_mismatch')
        if sample['memory.events']:
            need(dict(row.split() for row in sample['memory.events'].splitlines()).get('oom_kill')=='0','kernel_oom_kill_observed')
    need(status and status['NoNewPrivs']=='1' and int(status['CapBnd'],16)==9,'process_security_mismatch')
    result=verify_result()
    result.update(resourceSampleCount=len(samples),kernelFirst=samples[0],kernelLast=samples[-1],
                  maxObservedMemoryBytes=max(int(x['memory.current'] or 0) for x in samples),
                  maxObservedTasks=max(int(x['pids.current'] or 0) for x in samples),processSecurity=status,
                  firstProcessSecurity=first_status)
    return result
try:
    need(os.geteuid()==0 and os.uname().nodename==('node03' if IS_WATCHDOG else 'node02'),'wrong_host_or_privilege')
    for name,expected in PARAMS['files'].items():
        path=Path(name);info=path.lstat()
        need(path.is_file() and not path.is_symlink() and info.st_uid==0 and not info.st_mode&0o022,'installed_file_ownership_mismatch')
        need(hashlib.sha256(path.read_bytes()).hexdigest()==expected,'installed_source_hash_mismatch')
    if IS_WATCHDOG:
        need(json.loads(Path('/etc/bortus-certificate-watchdog/identity.json').read_text())==PARAMS['publicEnrollment'],'watchdog_public_enrollment_changed')
    monitor_off()
    if PHASE=='monitor-preflight':
        p=props(MONITOR)
        state=Path('/var/lib/bortus-certificate-monitor')
        database=state/'monitor.sqlite'
        result={'monitorDisabledInactive':True,
                'installedMonitorProperties':{k:p.get(k) for k in
                    ['ActiveState','UnitFileState','User','Group','MemoryMax','MemorySwapMax','CPUQuotaPerSecUSec',
                     'TasksMax','NoNewPrivileges','CapabilityBoundingSet','ProtectHome','ProtectSystem','RuntimeDirectory']},
                'stateDirectory':{'uid':state.stat().st_uid,'mode':oct(state.stat().st_mode&0o777),
                                  'databaseExists':database.exists()},
                'tokenMetadata':token_info(),
                'stagedCheckpointHashesVerified':True,
                'proposedSourceDifferences':PARAMS['proposedDifferences'],
                'serviceOrCredentialMutation':False,
                'readyToActivate':False}
    elif PHASE=='inspect':
        result=verify_result()
    elif PHASE=='once':
        need(props(SERVICE).get('ActiveState')=='inactive' and props(TIMER).get('ActiveState')=='inactive','existing_credential_run_requires_reconciliation')
        if IS_WATCHDOG:need(not (RUNTIME/'token').exists(),'watchdog_first_run_outcome_requires_reconciliation')
        result=capture_run()
    elif PHASE=='timer':
        previous=verify_result()
        if IS_WATCHDOG:
            need(props(TIMER).get('ActiveState')=='inactive' and props(TIMER).get('UnitFileState')=='disabled','watchdog_timer_already_armed')
        subprocess.run(['systemctl','enable','--now',TIMER],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,timeout=10)
        # OnBootSec may fire immediately on a long-running host. Let that initial
        # timer activation finish, then record its *next* actual periodic due time.
        if IS_WATCHDOG:
            deadline=time.monotonic()+450
            while time.monotonic()<deadline:
                p=props(SERVICE)
                if p.get('ActiveState')=='inactive':
                    current=last_success()
                    if current['invocationID']!=previous['credential']['invocationID']:break
                time.sleep(.5)
            else:raise RuntimeError('watchdog_initial_timer_run_not_observed')
        else:time.sleep(1)
        wait_finished(time.monotonic()+210)
        result=verify_result();p=props(TIMER)
        need(p.get('ActiveState')=='active' and p.get('UnitFileState')=='enabled','timer_not_armed')
        due=next_due()
        need(0<due-int(time.monotonic()*1e6)<=21*60*1e6,'timer_due_not_in_expected_window')
        result['timer']={k:p.get(k) for k in ['ActiveState','UnitFileState','NextElapseUSecMonotonic','TimersMonotonic','LastTriggerUSecMonotonic']}
        result['expectedPeriodicDueUSec']=due
    else:
        baseline=PARAMS['baseline'];due=baseline['expectedPeriodicDueUSec']
        need(Path('/proc/sys/kernel/random/boot_id').read_text().strip()==baseline['bootID'],'boot_changed_reconcile_timer')
        need(props(TIMER).get('ActiveState')=='active','timer_not_active')
        # Follow only the owned unit's journal. No service starts or timer resets.
        follower=subprocess.Popen(['journalctl','-f','-u',SERVICE,'-o','json','--all','--no-pager','--since','-40min'],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        deadline=time.monotonic()+max(0,due/1e6-time.monotonic())+240
        try:
            with selectors.DefaultSelector() as selector:
                selector.register(follower.stdout,selectors.EVENT_READ)
                found=False
                pending=b''
                while time.monotonic()<deadline and not found:
                    if not selector.select(min(30,max(.1,deadline-time.monotonic()))):continue
                    chunk=os.read(follower.stdout.fileno(),65536)
                    if not chunk:raise RuntimeError('journal_follower_ended')
                    pending+=chunk
                    need(len(pending)<=262144,'journal_record_limit')
                    while b'\n' in pending:
                        line,pending=pending.split(b'\n',1)
                        row=json.loads(line)
                        try:value=json.loads(row.get('MESSAGE',''))
                        except (ValueError,TypeError):continue
                        if value.get('state')=='credential-refreshed' and int(row['__MONOTONIC_TIMESTAMP'])>=due:
                            found=True;break
                need(found,'periodic_refresh_not_observed')
        finally:
            follower.terminate()
            follower.communicate(timeout=10)
        wait_finished(time.monotonic()+210);result=verify_result()
        need(result['credential']['invocationID']!=baseline['credential']['invocationID'],'invocation_not_new')
        need(result['tokenMetadata']['mtimeNS']>baseline['tokenMetadata']['mtimeNS'],'credential_not_replaced')
        result['periodicRefreshObserved']=True
        result['elapsedMonotonicSeconds']=(result['credential']['monotonicUSec']-baseline['credential']['monotonicUSec'])/1e6
        result['expectedPeriodicDueUSec']=due
    result.update(phase=PHASE,bootID=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),observedAt=dt.datetime.now(dt.timezone.utc).isoformat())
    print(json.dumps(result),flush=True)
except Exception as error:
    reason=str(error) if isinstance(error,RuntimeError) else type(error).__name__
    print(json.dumps({'phase':PHASE,'state':'qualification-failed','reason':reason,'evidence':EVIDENCE}),flush=True)
    sys.exit(0)
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=["once", "timer", "observe", "inspect", "monitor-preflight"])
    parser.add_argument("--attempt", default="")
    args = parser.parse_args()
    if args.attempt and (not args.attempt.replace("-", "").isalnum() or len(args.attempt)>32):
        parser.error("Short path-safe attempt label required")
    prefix = STAGE / ("node02-credential-" + args.phase + ("-" + args.attempt if args.attempt else ""))
    if prefix.with_suffix(".started.json").exists() or prefix.with_suffix(".result.json").exists():
        parser.error("Existing phase evidence requires reconciliation, not replay")
    started = json.loads((STAGE / "node02-credential-stage-started.json").read_text())
    files = {}
    proposed_differences = {}
    for local, digest in started["sourceSHA256"].items():
        path = Path(local)
        if path.name == "certificate-monitor-host.yml":
            continue
        proposed = hashlib.sha256(path.read_bytes()).hexdigest()
        if proposed != digest:
            if args.phase != "monitor-preflight":
                parser.error("Source differs from the staged checkpoint")
            proposed_differences[str(path)] = {"installedCheckpointSHA256": digest, "proposedSHA256": proposed}
        remote = ("/etc/systemd/system/" if path.suffix in (".service", ".timer")
                  else "/usr/local/libexec/bortus-certificate-monitor/") + path.name
        files[remote] = digest
    enrollment = json.loads((STAGE / "host-credential-enrollment-candidate.json").read_text())
    params = {"phase": args.phase, "files": files, "uid": enrollment["serviceAccountUID"]}
    if args.phase == "monitor-preflight":
        params["proposedDifferences"] = proposed_differences
    if args.phase == "observe":
        params["baseline"] = json.loads((STAGE / "node02-credential-timer.result.json").read_text())
    prefix.with_suffix(".started.json").write_text(json.dumps(
        {"phase": args.phase, "host": "node02", "files": files, "monitorActivation": False}, indent=2) + "\n")
    spec = importlib.util.spec_from_file_location("saved_node", REPO / "scripts/migration/saved-node-credential.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    password = module.existing_password()
    code = "PARAMS=" + repr(params) + "\n" + REMOTE
    command = ["ssh", "-p", "2002", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=yes",
               "-o", "ConnectTimeout=8", "-i", "/home/brajam/.ssh/id_ed25519", "james@192.168.0.6",
               "sudo -S -p '' /usr/bin/python3 -B -c " + shlex.quote(code)]
    try:
        raw = run_bounded(command, data=(password + "\n").encode(), output_limit=256 * 1024,
                          timeout=1800 if args.phase == "observe" else 260)
        result = json.loads(raw)
        prefix.with_suffix(".result.json").write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps(result, indent=2), flush=True)
        if result.get("state") == "qualification-failed":
            return 1
    except Exception as error:
        # A remote start may have succeeded. Never infer that retry is safe.
        failure = {"phase": args.phase, "state": "transport-or-qualification-failed",
                   "reason": type(error).__name__, "outcomeRequiresReconciliation": True}
        prefix.with_suffix(".failure.json").write_text(json.dumps(failure, indent=2) + "\n")
        print(json.dumps(failure), flush=True)
        return 1
    finally:
        password = None
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
