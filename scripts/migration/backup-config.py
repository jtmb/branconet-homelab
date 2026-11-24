#!/usr/bin/env python3
"""Encrypt live runtime configuration outside Git; credentials arrive over stdin."""
import concurrent.futures
import datetime
import hashlib
import json
import pathlib
import subprocess

HOSTS=("192.168.0.4","192.168.0.5","192.168.0.6")
HOME=pathlib.Path.home()
ROOT=HOME/".local/share/branconet-migration"
KEY=HOME/".ssh/id_ed25519"
AGE=ROOT/"bin/age"
NAS="/mnt/container-backups/k8s-migration-20261009"
ROOT_SCRIPT=r'''
import base64,glob,json,pathlib,re,subprocess,socket
def docker(*args):return json.loads(subprocess.check_output(["docker",*args],text=True))
def ids(*args):return subprocess.check_output(["docker",*args],text=True).split()
services=ids("service","ls","-q"); containers=ids("ps","-aq")
data={"host":socket.gethostname(),"services":docker("service","inspect",*services) if services else [],"containers":docker("inspect",*containers) if containers else [],"files":{},"missing_files":[]}
paths=set(["/etc/fstab","/etc/hosts","/etc/resolv.conf","/etc/containerd/config.toml","/etc/docker/daemon.json"])
paths.update(glob.glob("/etc/systemd/system/docker.service.d/*"))
paths.update(str(p) for p in pathlib.Path('/etc/kubernetes').rglob('*') if p.is_file())
paths.update(glob.glob('/etc/containerd-k8s/*'))
paths.update(['/etc/systemd/system/containerd-k8s.service','/etc/systemd/system/kubelet.service'])
for c in data["containers"]:
    labels=c["Config"].get("Labels") or {}
    paths.update(p for p in labels.get("com.docker.compose.project.config_files","").split(",") if p)
try:
    fstab=pathlib.Path("/etc/fstab").read_text()
    paths.update(re.findall(r"credentials=([^,\s]+)",fstab))
except OSError:pass
for p in sorted(paths):
    try:data["files"][p]=base64.b64encode(pathlib.Path(p).read_bytes()).decode()
    except OSError:data["missing_files"].append(p)
print(json.dumps(data))
'''

def ssh(host,*args,**kwargs):
    return subprocess.run(["ssh","-o","BatchMode=yes","-o","StrictHostKeyChecking=yes",
        "-o","ConnectTimeout=8","-i",str(KEY),"-p","2002",f"james@{host}",*args],**kwargs)

def backup(host,password,recipient,stamp):
    wrapper="import subprocess,sys\nr=subprocess.run("+repr(["sudo","-S","-p","","python3","-c",ROOT_SCRIPT])+",input="+repr(password+"\n")+",text=True,capture_output=True,timeout=60)\nif r.returncode: print('privileged configuration capture failed',file=sys.stderr);sys.exit(r.returncode)\nsys.stdout.write(r.stdout)\n"
    result=ssh(host,"python3","-",input=wrapper,text=True,capture_output=True,timeout=75)
    if result.returncode:raise RuntimeError(f"Configuration capture failed on {host}: exit {result.returncode}")
    raw=result.stdout.encode()
    configuration=json.loads(raw)
    directory=ROOT/"recovery";directory.mkdir(mode=0o700,parents=True,exist_ok=True)
    target=directory/f"config-{host}-{stamp}.json.age"
    encrypted=subprocess.run([str(AGE),"-r",recipient],input=raw,capture_output=True,check=True).stdout
    target.write_bytes(encrypted);target.chmod(0o600)
    recovered=subprocess.run([str(AGE),"-d","-i",str(KEY),str(target)],capture_output=True,check=True).stdout
    if recovered!=raw:raise RuntimeError(f"Recovery comparison failed on {host}")
    prepare="import os;os.makedirs("+repr(NAS)+",exist_ok=True);print('backup-directory-ready')"
    result=ssh(host,"python3","-",input=prepare,text=True,capture_output=True,timeout=20)
    if result.returncode:raise RuntimeError(f"NAS directory unavailable on {host}")
    destination=NAS+"/"+target.name
    uploaded=subprocess.run(["scp","-o","BatchMode=yes","-o","StrictHostKeyChecking=yes","-i",str(KEY),"-P","2002",str(target),f"james@{host}:{destination}"],capture_output=True,timeout=90)
    if uploaded.returncode:raise RuntimeError(f"Encrypted NAS upload failed on {host}")
    digest=hashlib.sha256(encrypted).hexdigest()
    check=ssh(host,"sha256sum",destination,text=True,capture_output=True,timeout=20)
    if check.returncode or check.stdout.split()[0]!=digest:raise RuntimeError(f"NAS checksum failed on {host}")
    return {"host":host,"operator_copy":str(target),"nas_copy":destination,"encrypted_bytes":len(encrypted),"ciphertext_sha256":digest,"recovery_verified":True,"service_count":len(configuration["services"]),"container_count":len(configuration["containers"]),"captured_file_count":len(configuration["files"]),"missing_files":configuration["missing_files"]}

def main():
    credentials=json.load(__import__("sys").stdin)
    recipient=(HOME/".ssh/id_ed25519.pub").read_text().strip()
    stamp=datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        reports=list(pool.map(lambda host:backup(host,credentials["sudo_password"],recipient,stamp),HOSTS))
    report={"created_at":stamp,"kind":"encrypted runtime/host configuration backup, not application-data backup","hosts":reports}
    destination=pathlib.Path(credentials["evidence_output"])
    destination.parent.mkdir(parents=True,exist_ok=True)
    if destination.exists():
        previous=json.loads(destination.read_text())
        destination.with_name('config-backups-'+previous['created_at']+'.json').write_text(json.dumps(previous,indent=2)+'\n')
    destination.write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps({"evidence":str(destination),"hosts":len(reports),"recovery_verified":all(r["recovery_verified"] for r in reports),"nas_copy_verified":True}))

if __name__=="__main__":main()
