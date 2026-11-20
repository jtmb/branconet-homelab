#!/usr/bin/env python3
"""Records-only independent DNS staging and one exact service refresh per phase."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
STAGE = Path("/mnt/h/AgentArtifacts/projects/branconet/builds/wsl-artifact-store/files/"
             "bortus-operator-recovery/certificates-qualification-20261116")
WORK = STAGE / "ntfy-dns-delivery"
ANSIBLE = ROOT / "k8s-rewrite/ansible-playbook"
RUNTIME = Path("/home/brajam/.local/share/branconet-migration")

REMOTE = r'''
import configparser,hashlib,json,stat,subprocess,time
from pathlib import Path
state=Path('/var/lib/branconet-independent-dns')
def unit(name):
 raw=subprocess.check_output(['systemctl','show',name,'--property=ActiveState,UnitFileState,InvocationID'],text=True)
 return dict(line.split('=',1) for line in raw.splitlines() if '=' in line)
def query(server,port,name,want,transport):
 q=subprocess.run(['dig','@'+server,'-p',str(port),name,'A','+short','+time=2','+tries=1',transport],capture_output=True,text=True,timeout=4)
 assert q.returncode==0 and want in q.stdout.splitlines(), (server,port,name,transport)
for name,before in PARAMS['before']['stateFiles'].items():
 p=state/name;i=p.lstat()
 assert stat.S_ISREG(i.st_mode) and i.st_uid==0 and stat.S_IMODE(i.st_mode)==0o600 and i.st_nlink==1
 if name=='gravity.db': assert hashlib.sha256(p.read_bytes()).hexdigest()==before['sha256']
 else: assert hashlib.sha256(p.read_bytes()).hexdigest()==PARAMS['configSHA256']
for p,info in PARAMS['before']['launchers'].items():
 assert hashlib.sha256(Path(p).read_bytes()).hexdigest()==info['sha256']
dhcp=subprocess.check_output(['systemctl','show','branconet-lan-dhcp.service','--property=InvocationID,ActiveState'],text=True)
assert dhcp==PARAMS['before']['dhcpBefore']
for transport in ['+tcp','+notcp']:
 query('192.168.0.253',53,'notifications.branconet.lan','192.168.0.252',transport)
service='branconet-independent-dns-'+PARAMS['phase']+'.service'
before=unit(service)
assert before['ActiveState']=='active' and before['UnitFileState']=='enabled'
baseline=PARAMS['before']['units'][PARAMS['phase']]['InvocationID']
if PARAMS.get('inspectOnly'):
 assert before['InvocationID']!=baseline
else:
 assert before['InvocationID']==baseline
 subprocess.run(['systemctl','restart',service],check=True,capture_output=True,timeout=60)
after=unit(service)
assert after['ActiveState']=='active' and after['UnitFileState']=='enabled' and after['InvocationID']!=baseline
if PARAMS.get('inspectOnly'): assert after['InvocationID']==before['InvocationID']
# The inbound port53 DNAT is PREROUTING-only. A probe on node03 itself must
# use the actual listening port, not pretend local OUTPUT traverses that rule.
server,port=('127.0.0.1',10554) if PARAMS['phase']=='loopback' else ('192.168.0.5',10554)
deadline=time.monotonic()+20
polls=0
while True:
 polls+=1
 try:
  for transport in ['+tcp','+notcp']:
   query(server,port,'notifications.branconet.lan','192.168.0.252',transport)
  break
 except (AssertionError,subprocess.SubprocessError):
  if time.monotonic()>=deadline: raise
  time.sleep(.5)
for transport in ['+tcp','+notcp']:
 for name,want in [('notifications.branconet.lan','192.168.0.252'),('k8s-api.branconet.lan','192.168.0.251'),('doubleclick.net','0.0.0.0')]:
  query(server,port,name,want,transport)
 query('192.168.0.253',53,'notifications.branconet.lan','192.168.0.252',transport)
other='lan' if PARAMS['phase']=='loopback' else 'loopback'
assert unit('branconet-independent-dns-'+other+'.service')['ActiveState']=='active'
assert subprocess.check_output(['systemctl','show','branconet-lan-dhcp.service','--property=InvocationID,ActiveState'],text=True)==dhcp
assert hashlib.sha256((state/'gravity.db').read_bytes()).hexdigest()==PARAMS['before']['stateFiles']['gravity.db']['sha256']
assert hashlib.sha256((state/'pihole.toml').read_bytes()).hexdigest()==PARAMS['configSHA256']
for p,info in PARAMS['before']['launchers'].items():
 assert hashlib.sha256(Path(p).read_bytes()).hexdigest()==info['sha256']
print(json.dumps({'passed':True,'phase':PARAMS['phase'],'unit':service,'before':before,'after':after,'readinessPolls':polls,'probeEndpoint':server+':'+str(port),'newRecordTCP_UDPVerified':True,'externalAdvertisedPort53ProbeStillRequired':PARAMS['phase']=='lan','filterAndAPIControlsPassed':True,'floatingDNSBeforeAndAfterPassed':True,'gravityAndLaunchersUnchanged':True,'dhcpUnchanged':True,'readOnlyCompletion':bool(PARAMS.get('inspectOnly'))}))
'''


def save(name, value):
    with (WORK / name).open("x") as stream:
        json.dump(value, stream, indent=2)
        stream.write("\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=["stage", "loopback", "lan"])
    recovery = parser.add_mutually_exclusive_group()
    recovery.add_argument("--recover-controller-rpc", action="store_true",
                        help="Only after the recorded initial RPC failure before all tasks")
    recovery.add_argument("--recover-delegated-ssh", action="store_true",
                          help="Only after the first delegated read failed before SSH/tasks")
    args = parser.parse_args()
    phase = args.phase
    assert json.loads((WORK / "primary-result.json").read_text())["passed"]
    prefix = f"independent-{phase}"
    if args.recover_controller_rpc:
        assert phase == "stage"
        assert (WORK / "independent-stage-failure.json").is_file()
        assert not (WORK / "independent-stage-result.json").exists()
        failed = (WORK / "independent-stage.log").read_text()
        assert "Local RPC server did not start" in failed and "PLAY [" not in failed and "TASK [" not in failed
        prefix += "-abstract-rpc"
    if args.recover_delegated_ssh:
        assert phase == "stage"
        assert (WORK / "independent-stage-abstract-rpc-failure.json").is_file()
        assert not (WORK / "independent-stage-result.json").exists()
        failed = (WORK / "independent-stage-abstract-rpc.log").read_text()
        assert "unsupported format character" in failed and "ok=0" in failed and "changed=0" in failed
        assert "TASK [Wait for both DNS" not in failed
        prefix += "-abstract-no-mux"
    assert not (WORK / f"{prefix}-started.json").exists(), "reconcile_existing_phase"
    for prior in {"stage": [], "loopback": ["stage"], "lan": ["stage", "loopback"]}[phase]:
        assert json.loads((WORK / f"independent-{prior}-result.json").read_text())["passed"]
    save(f"{prefix}-started.json", {
        "phase": phase, "driverSHA256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "onlyNamedResolverChanged": True, "noFilteringDBCopyOrDHCPChange": True,
        "priorRPCFailureBeforeAnyRemoteTask": args.recover_controller_rpc,
        "priorSSHFormattingFailureBeforeFirstRemoteRead": args.recover_delegated_ssh})
    spec = importlib.util.spec_from_file_location("notification_saved_credential",
                                                ROOT / "scripts/migration/saved-node-credential.py")
    saved = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(saved)
    password = saved.existing_password()
    try:
        if phase == "stage":
            temp = WORK / (prefix + "-temp")
            temp.mkdir(mode=0o700)
            env = {**os.environ, "BRANCONET_MIGRATION_SUDO_PASSWORD": password,
                   "ANSIBLE_CONFIG": str(ANSIBLE / "ansible.cfg"), "ANSIBLE_NOCOLOR": "1",
                   "PYTHONDONTWRITEBYTECODE": "1", "ANSIBLE_LOCAL_TEMP": str(temp),
                   "ANSIBLE_SSH_ARGS": "-o ControlMaster=no -o ControlPersist=no",
                   "TMPDIR": str(temp), "TMP": str(temp), "TEMP": str(temp)}
            # Match run-lan-dhcp.py: Python's abstract AF_UNIX addresses avoid
            # long/path-incompatible filesystem sockets without moving scratch.
            bootstrap = r"""import multiprocessing.connection as c,secrets
original=c.arbitrary_address
c.arbitrary_address=lambda family: ('\0branconet-notification-dns-'+secrets.token_hex(16)) if family=='AF_UNIX' else original(family)
from ansible.cli.playbook import main
main()
"""
            with (WORK / f"{prefix}.log").open("xb") as log:
                result = subprocess.run([str(RUNTIME / "venv/bin/python"), "-B", "-c", bootstrap,
                    "playbooks/independent-dns-policy.yml", "--extra-vars",
                    '{"dns_records_only":true,"dns_records_map":"lan-dns-records-v4"}'],
                    cwd=ANSIBLE, env=env, stdin=subprocess.DEVNULL, stdout=log,
                    stderr=subprocess.STDOUT, timeout=240)
            assert result.returncode == 0, "records_only_ansible_failed"
            save("independent-stage-result.json", {
                "passed": True, "recordsOnly": True, "sourceMap": "lan-dns-records-v4",
                "serviceRestarted": False, "log": f"{prefix}.log"})
            print(json.dumps({"passed": True, "phase": phase, "serviceRestarted": False}))
        else:
            # This is public configuration only, rendered from the same immutable
            # source used by the Ansible play; values/admin settings cannot enter it.
            import yaml
            spec = importlib.util.spec_from_file_location("notification_dns_renderer",
                ANSIBLE / "playbooks/files/independent-lan-dns.py")
            renderer = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(renderer)
            config = yaml.safe_load(Path("/mnt/c/Users/james/AppData/Local/BORTUS/repos/"
                "branconet-charts/flux/releases/foundation/lan-dns-records-v4.yaml").read_text())
            expected = renderer.render_ftl(config["data"], ["8.8.4.4", "8.8.8.8"])
            params = {"phase": phase,
                      "before": json.loads((WORK / "independent-preflight.json").read_text()),
                      # Ansible's command stdout strips the renderer's trailing
                      # newline; the existing copy task adds exactly one back.
                      "configSHA256": hashlib.sha256((expected.rstrip("\n") + "\n").encode()).hexdigest()}
            code = "PARAMS=" + repr(params) + "\n" + REMOTE
            command = ["ssh", "-p", "2002", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=yes",
                       "-o", "ConnectTimeout=8", "-i", "/home/brajam/.ssh/id_ed25519",
                       "james@192.168.0.5", "sudo -S -p '' /usr/bin/python3 -B -c " + shlex.quote(code)]
            result = subprocess.run(command, input=(password + "\n").encode(),
                                    capture_output=True, timeout=110)
            if result.returncode:
                save(f"independent-{phase}-remote-error.json", {
                    "returncode": result.returncode, "stderr": result.stderr.decode()[-2000:]})
            assert result.returncode == 0, "remote_refresh_requires_reconciliation"
            value = json.loads(result.stdout)
            save(f"independent-{phase}-result.json", value)
            print(json.dumps(value, indent=2))
    except Exception as error:
        save(f"{prefix}-failure.json", {
            "errorType": type(error).__name__, "reconcileBeforeRetry": True,
            "noBlindServiceRestart": True})
        raise
    finally:
        password = None


if __name__ == "__main__":
    main()
