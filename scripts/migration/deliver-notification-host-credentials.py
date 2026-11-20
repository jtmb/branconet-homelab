#!/usr/bin/env python3
"""One-time native publisher delivery; values travel only through memory/stdin."""
import argparse
import base64
import importlib.util
import json
from pathlib import Path
import re
import shlex
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("notification_native_transport",
                                             Path(__file__).with_name("stage-ntfy-cluster.py"))
API = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(API)
WORK = API.STAGE / "monitor-host-activation"
HOSTS = {"node02": ("192.168.0.6", "bortus-certificate-monitor", "monitor-token", "bortus-certificates"),
         "node03": ("192.168.0.5", "bortus-certificate-watchdog", "watchdog-token", "bortus-monitor-health")}
REMOTE = r'''
import grp,hashlib,json,os,pwd,re,stat,subprocess,sys
from pathlib import Path
try:
 raw=sys.stdin.buffer.read(65537)
 assert len(raw)<=65536
 data=json.loads(raw)
 assert set(data)=={'host','account','token','ca','config'}
 assert subprocess.check_output(['hostname'],text=True).strip()==data['host']
 account=data['account']
 assert (data['host'],account) in [('node02','bortus-certificate-monitor'),('node03','bortus-certificate-watchdog')]
 directory=Path('/etc')/account
 targets=[directory/name for name in ['notification-token','notification-ca.crt','notifications.json']]
 assert all(not p.exists() and not p.is_symlink() for p in targets)
 created_account=False
 try: user=pwd.getpwnam(account)
 except KeyError:
  assert data['host']=='node03' and not directory.exists()
  try: grp.getgrnam(account)
  except KeyError: pass
  else: raise ValueError('account_group_collision')
  subprocess.run(['useradd','--system','--user-group','--no-create-home','--home-dir','/var/lib/'+account,'--shell','/usr/sbin/nologin',account],check=True,capture_output=True)
  user=pwd.getpwnam(account);created_account=True
 assert user.pw_uid!=0 and user.pw_shell in ['/usr/sbin/nologin','/sbin/nologin']
 if not directory.exists():
  directory.mkdir(mode=0o750);os.chown(directory,0,user.pw_gid)
 for parent in directory.parents:
  i=parent.lstat();assert stat.S_ISDIR(i.st_mode) and i.st_uid==0 and not i.st_mode&0o022
 info=directory.lstat();assert stat.S_ISDIR(info.st_mode) and info.st_uid==0 and info.st_gid==user.pw_gid and stat.S_IMODE(info.st_mode)==0o750
 assert re.fullmatch(r'tk_[-_A-Za-z0-9]{29}',data['token'])
 config=data['config'];assert config['address']=='192.168.0.252'
 assert config['tokenFile']==str(targets[0]) and config['caFile']==str(targets[1])
 topic='bortus-certificates' if data['host']=='node02' else 'bortus-monitor-health'
 assert config['url']=='https://notifications.branconet.lan/'+topic
 payloads=[data['token'].encode(),data['ca'].encode(),(json.dumps(config,sort_keys=True)+'\n').encode()]
 records=[]
 for path,payload in zip(targets,payloads):
  fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o640)
  try:
   os.fchown(fd,0,user.pw_gid)
   with os.fdopen(fd,'wb',closefd=False) as stream: stream.write(payload);stream.flush();os.fsync(fd)
  finally: os.close(fd)
  i=path.lstat();assert path.read_bytes()==payload and i.st_uid==0 and i.st_gid==user.pw_gid and stat.S_IMODE(i.st_mode)==0o640
  subprocess.run(['runuser','-u',account,'--','test','-r',str(path)],check=True,capture_output=True)
  assert subprocess.run(['runuser','-u',account,'--','test','-w',str(path)],capture_output=True).returncode==1
  assert subprocess.run(['runuser','-u','nobody','--','test','-r',str(path)],capture_output=True).returncode==1
  records.append({'path':str(path),'uid':i.st_uid,'gid':i.st_gid,'mode':'0640','inode':i.st_ino})
 fd=os.open(directory,os.O_RDONLY|os.O_DIRECTORY)
 try: os.fsync(fd)
 finally: os.close(fd)
 print(json.dumps({'passed':True,'host':data['host'],'account':account,'uid':user.pw_uid,'gid':user.pw_gid,'accountCreated':created_account,'files':records,'tokenMatchesSelectedNativeKey':True,'publicCA_SHA256':hashlib.sha256(data['ca'].encode()).hexdigest(),'unprivilegedReadableNotWritable':True,'unrelatedUserCannotRead':True,'serviceStarted':False,'subscriberCredentialDelivered':False}))
except Exception:
 print(json.dumps({'passed':False,'reason':'delivery_outcome_requires_reconciliation','privateValuesWithheld':True}))
 sys.exit(1)
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("host", choices=HOSTS)
    host = parser.parse_args().host
    ip, account, key, topic = HOSTS[host]
    prefix = WORK / (host + "-publisher")
    assert not prefix.with_suffix(".started.json").exists(), "reconcile_prior_delivery"
    assert json.loads((WORK / "preflight.json").read_text())["hosts"][host]
    auth = API.call(["get", "secret", "private-ntfy-auth", "-n", "bortus-notifications", "-o", "json"])
    assert auth["metadata"]["uid"] == "29ce9801-a320-4352-b7ef-6808c8df3887"
    token = base64.b64decode(auth["data"][key], validate=True).decode()
    assert re.fullmatch(r"tk_[-_A-Za-z0-9]{29}", token)
    ca = base64.b64decode(API.run_bounded(API.BASE + [
        "get", "secret", "private-ntfy-tls", "-n", "bortus-notifications",
        "-o", r"jsonpath={.data.ca\.crt}"], output_limit=16384, timeout=20)).decode()
    config = {"version": 1, "url": "https://notifications.branconet.lan/" + topic,
              "address": "192.168.0.252", "tokenFile": f"/etc/{account}/notification-token",
              "caFile": f"/etc/{account}/notification-ca.crt"}
    prefix.with_suffix(".started.json").write_text(json.dumps({
        "host": host, "nativeSecretUID": auth["metadata"]["uid"], "selectedKey": key,
        "ordinaryPublisherOnly": True, "config": config, "noServiceActivation": True}, indent=2) + "\n")
    spec = importlib.util.spec_from_file_location("saved_notification_delivery",
                                                ROOT / "scripts/migration/saved-node-credential.py")
    saved = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(saved)
    password = saved.existing_password()
    try:
        payload = json.dumps(dict(host=host, account=account, token=token, ca=ca, config=config))
        result = subprocess.run(["ssh", "-p", "2002", "-o", "BatchMode=yes", "-o",
            "StrictHostKeyChecking=yes", "-o", "ConnectTimeout=8", "-i",
            "/home/brajam/.ssh/id_ed25519", "james@" + ip,
            "sudo -k -S -p '' python3 -B -c " + shlex.quote(REMOTE)],
            input=(password + "\n" + payload).encode(), capture_output=True, timeout=50)
        if result.returncode:
            prefix.with_suffix(".failure.json").write_text(json.dumps({
                "reason": "remote_delivery_outcome_unknown", "reconcileNativeAndHostFilesBeforeRetry": True}))
            raise RuntimeError("publisher_delivery_failed_reconcile_before_retry")
        value = json.loads(result.stdout)
        assert value["passed"]
        prefix.with_suffix(".result.json").write_text(json.dumps(value, indent=2) + "\n")
        print(json.dumps(value, indent=2))
    finally:
        password = token = payload = auth = None


if __name__ == "__main__":
    main()
