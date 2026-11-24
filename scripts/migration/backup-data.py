#!/usr/bin/env python3
"""Cold application backup with restored source services; credentials via stdin."""
import concurrent.futures
import datetime
import hashlib
import json
import pathlib
import subprocess
import sys
import tarfile
import time

HOME=pathlib.Path.home();ROOT=HOME/".local/share/branconet-migration"
KEY=HOME/".ssh/id_ed25519";AGE=ROOT/"bin/age"
HOSTS=("192.168.0.4","192.168.0.5","192.168.0.6")
NAS="/mnt/container-backups/k8s-migration-20261009"

def emit(event,**fields):print(json.dumps({"event":event,**fields}),flush=True)

def ssh(host,script,timeout=120):
    r=subprocess.run(["ssh","-o","BatchMode=yes","-o","StrictHostKeyChecking=yes","-o","ConnectTimeout=8","-i",str(KEY),"-p","2002",f"james@{host}","python3","-"],input=script,text=True,capture_output=True,timeout=timeout)
    if r.returncode:raise RuntimeError(f"Remote operation failed on {host}: exit {r.returncode}; {r.stderr.strip().splitlines()[-1] if r.stderr.strip() else 'no diagnostic'}")
    return json.loads(r.stdout)

def docker_script(args):
    return "import subprocess,json\nr=subprocess.run("+repr(["docker",*args])+",text=True,capture_output=True)\nprint(json.dumps({'exit_code':r.returncode,'output':r.stdout}))\n"

ROOT_SCRIPT=r'''
import hashlib,json,os,pathlib,subprocess,time
started=time.time()
containers=[]
ids=subprocess.check_output(["docker","ps","-q"],text=True).split()
if ids:containers=json.loads(subprocess.check_output(["docker","inspect",*ids],text=True))
unexpected=[c["Name"] for c in containers if (c["Config"].get("Labels") or {}).get("com.docker.swarm.service.name")!="portainer_agent"]
if unexpected:raise RuntimeError("Application writers still running")
paths=list(CONFIG.get("paths") or ["/var/plex-stack"])
if not CONFIG.get("paths"):
    if CONFIG["host"]=="192.168.0.4":paths += ["/mnt/container-program-files","/mnt/nfs-container-volumes"]
    if CONFIG["host"]=="192.168.0.6":paths += ["/mnt/plex_smb_share/shared-container-folder/ets2"]
paths += CONFIG.get("extra_paths",[])
all_ids=subprocess.check_output(["docker","ps","-aq"],text=True).split()
for c in json.loads(subprocess.run(["docker","inspect",*all_ids],text=True,capture_output=True).stdout or '[]') if all_ids else []:
    for m in c["Mounts"]:
        identity=((c['Config'].get('Labels') or {}).get('com.docker.swarm.service.name'),m['Destination'])
        if m["Type"]=="volume" and identity not in {('media_flaresolverr','/config'),('cicd_vault','/vault/file'),('cicd_vault','/vault/logs')}:paths.append(m["Source"])
missing=[p for p in paths if not pathlib.Path(p).exists()]
if missing:raise RuntimeError("Required source path missing: "+", ".join(missing))
paths=sorted(set(paths))
directory=pathlib.Path(CONFIG["nas"]);directory.mkdir(parents=True,exist_ok=True)
space=os.statvfs(directory)
if space.f_bavail*space.f_frsize < 50*1024**3:raise RuntimeError("Backup share has less than 50 GiB free")
destination=directory/(CONFIG.get("prefix","cold")+"-"+CONFIG["host"]+"-"+CONFIG["stamp"]+".tar.gz.age")
partial=destination.with_suffix(destination.suffix+".partial")
if destination.exists() or partial.exists():raise RuntimeError("Backup destination already exists")
with partial.open("xb") as out:
    tar=subprocess.Popen(["tar","--acls","--xattrs","--numeric-owner",*["--exclude="+p.lstrip("/") for p in CONFIG.get("exclusions",[])],"-C","/","-czf","-",*[p.lstrip("/") for p in paths]],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    enc=subprocess.Popen([CONFIG["age"],"-r",CONFIG["recipient"]],stdin=tar.stdout,stdout=out,stderr=subprocess.PIPE)
    tar.stdout.close()
    _,tarerr=tar.communicate();_,encerr=enc.communicate()
    out.flush();os.fsync(out.fileno())
if tar.returncode or enc.returncode:
    print(json.dumps({"ok":False,"host":CONFIG["host"],"tar_exit":tar.returncode,"encryption_exit":enc.returncode,"error_paths":tarerr.decode(errors="replace"),"partial":str(partial)}));raise SystemExit(0)
partial.rename(destination)
h=hashlib.sha256()
with destination.open("rb") as f:
    for chunk in iter(lambda:f.read(1024*1024),b""):h.update(chunk)
print(json.dumps({"ok":True,"host":CONFIG["host"],"kind":CONFIG.get("prefix","cold"),"archive":str(destination),"source_paths":paths,"excluded_paths":CONFIG.get("exclusions",[]),"encrypted_bytes":destination.stat().st_size,"ciphertext_sha256":h.hexdigest(),"elapsed_seconds":round(time.time()-started)}))
'''

def backup_host(host,password,recipient,stamp,paths=None,exclusions=(),prefix="cold",extra_paths=()):
    config={"host":host,"nas":NAS,"stamp":stamp,"recipient":recipient,"age":"/home/james/.local/share/branconet-migration/age","paths":paths,"exclusions":list(exclusions),"prefix":prefix,"extra_paths":list(extra_paths)}
    root="CONFIG="+repr(config)+"\n"+ROOT_SCRIPT
    wrapper="import subprocess,sys,json\nr=subprocess.run("+repr(["sudo","-S","-p","","python3","-c",root])+",input="+repr(password+"\n")+",capture_output=True,text=True)\nif r.returncode:print(json.dumps({'ok':False,'host':"+repr(host)+",'error':r.stderr.strip().splitlines()[-1] if r.stderr.strip() else 'cold backup failed'}))\nelse:sys.stdout.write(r.stdout)\n"
    return ssh(host,wrapper,timeout=3600)

def verify(report):
    host=report["host"]
    source=subprocess.Popen(["ssh","-o","BatchMode=yes","-o","StrictHostKeyChecking=yes","-i",str(KEY),"-p","2002",f"james@{host}","cat",report["archive"]],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    decode=subprocess.Popen([str(AGE),"-d","-i",str(KEY)],stdin=source.stdout,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    source.stdout.close();count=0;bytes_total=0
    with tarfile.open(fileobj=decode.stdout,mode="r|gz") as archive:
        for member in archive:
            count+=1;bytes_total+=member.size
    # Drain all authenticated output; age validates the final chunk on EOF.
    while decode.stdout.read(1024*1024):pass
    decode.stdout.close();decode.wait();source.wait()
    if decode.returncode or source.returncode:raise RuntimeError(f"Authenticated recovery failed on {host}")
    return {**report,"authenticated_decryption_verified":True,"tar_entries":count,"uncompressed_file_bytes":bytes_total}

def main():
    request=json.load(sys.stdin);password=request["sudo_password"]
    evidence=pathlib.Path(request["evidence_output"])
    previous=None
    if request.get("recover_gluster_read_errors"):
        previous=json.loads(evidence.read_text())
        history=evidence.with_name('data-backups-initial.json')
        if history.exists():history=evidence.with_name('data-backups-'+previous['started_at']+'.json')
        history.write_text(json.dumps(previous,indent=2)+'\n')
    recipient=(HOME/".ssh/id_ed25519.pub").read_text().strip()
    stamp=datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    services=ssh(HOSTS[0],"import json,subprocess\nids=subprocess.check_output(['docker','service','ls','-q'],text=True).split()\nprint(subprocess.check_output(['docker','service','inspect',*ids],text=True))\n")
    replicas={s["Spec"]["Name"]:s["Spec"]["Mode"]["Replicated"]["Replicas"] for s in services if "Replicated" in s["Spec"]["Mode"]}
    standalone={}
    for host in HOSTS:
        script="import json,subprocess\nids=subprocess.check_output(['docker','ps','-q'],text=True).split()\ncs=json.loads(subprocess.check_output(['docker','inspect',*ids],text=True)) if ids else []\nprint(json.dumps([c['Name'].lstrip('/') for c in cs if not (c['Config'].get('Labels') or {}).get('com.docker.swarm.service.id')]))\n"
        standalone[host]=ssh(host,script)
        ssh(host,"import pathlib,json\np=pathlib.Path('/home/james/.local/share/branconet-migration');p.mkdir(parents=True,exist_ok=True);print(json.dumps({'ready':True}))\n")
        stage=subprocess.run(["scp","-o","BatchMode=yes","-o","StrictHostKeyChecking=yes","-i",str(KEY),"-P","2002",str(AGE),f"james@{host}:/home/james/.local/share/branconet-migration/age"],capture_output=True,timeout=60)
        if stage.returncode:raise RuntimeError(f"Encryption tool staging failed on {host}")
    baseline=json.loads((evidence.parent/'live-inventory.json').read_text())
    excluded=[]
    anonymous={host:[] for host in HOSTS}
    disposable={('media_flaresolverr','/config'),('cicd_vault','/vault/file'),('cicd_vault','/vault/logs')}
    for host in HOSTS:
        for container in baseline['nodes'][host]['containers']:
            for mount in container['mounts']:
                if mount['Type']!='volume':continue
                identity=(container['service'],mount.get('Destination') or mount.get('Target'))
                if request.get('disposable_runtime_state_confirmed') and identity in disposable:
                    excluded.append({'host':host,'service':identity[0],'destination':identity[1],'original_path':mount['Source'],'classification':'User-confirmed disposable runtime state'})
                else:anonymous[host].append(mount['Source'])
    if any(anonymous.values()):
        raise RuntimeError('Anonymous application data must be independently captured before Swarm task removal; writer shutdown blocked')
    retained=[a for a in (previous or {}).get('archives',[]) if a.get('ok')]
    report={"started_at":stamp,"source_replicas":replicas,"source_standalone":standalone,"archives":retained,"restoration":None}
    report['approved_disposable_runtime_paths']=excluded
    if previous:report['recovery_strategy']='Retain valid original cold archives; rearchive primary local/NFS state, preserve all three raw bricks, and archive worker2 logical Gluster excluding obsolete Plex Logs preserved in brick archives. Raw bricks are recovery originals, not application import sources.'
    evidence.parent.mkdir(parents=True,exist_ok=True)
    def save():evidence.write_text(json.dumps(report,indent=2)+"\n")
    save();emit("maintenance_start",services=len(replicas),standalone=sum(map(len,standalone.values())))
    try:
        scaled=ssh(HOSTS[0],docker_script(["service","scale","--detach",*[f"{name}=0" for name in replicas]]),timeout=180)
        if scaled["exit_code"]:raise RuntimeError("Failed to stop Swarm writers")
        for host,names in standalone.items():
            ordered=sorted(names,key=lambda n:0 if n=="qbittorrent" else 2 if n=="GlueTun-proton" else 1)
            if ordered:
                stopped=ssh(host,docker_script(["stop","--time","60",*ordered]),timeout=180)
                if stopped["exit_code"]:raise RuntimeError(f"Failed to stop standalone writers on {host}")
        for _ in range(30):
            remaining=[]
            for host in HOSTS:
                names=ssh(host,"import json,subprocess\nrows=subprocess.check_output(['docker','ps','--format','{{json .}}'],text=True).splitlines()\nprint(json.dumps([json.loads(row)['Names'] for row in rows if not json.loads(row)['Names'].startswith('portainer_agent.')]))\n")
                remaining+=names
            if not remaining:break
            time.sleep(2)
        else:raise RuntimeError("Application writers did not quiesce")
        emit("writers_stopped")
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
            if previous:
                futures={pool.submit(backup_host,h,password,recipient,stamp,['/gluster/volumes'],(),"gluster-brick",anonymous[h]):h for h in HOSTS}
                futures[pool.submit(backup_host,HOSTS[0],password,recipient,stamp,['/var/plex-stack','/mnt/nfs-container-volumes'],(),"cold-primary",anonymous[HOSTS[0]])]=HOSTS[0]
                logs='/mnt/container-program-files/plex/config/Library/Application Support/Plex Media Server/Logs'
                futures[pool.submit(backup_host,HOSTS[1],password,recipient,stamp,['/mnt/container-program-files'],[logs],"gluster-logical")]=HOSTS[1]
            else:
                futures={pool.submit(backup_host,h,password,recipient,stamp,None,(),"cold",anonymous[h]):h for h in HOSTS}
            for future in concurrent.futures.as_completed(futures):
                try:item=future.result()
                except Exception as failure:item={'ok':False,'host':futures[future],'error':str(failure)}
                report["archives"].append(item);save()
                emit("archive_written",host=item["host"],ok=item["ok"],encrypted_bytes=item.get("encrypted_bytes"))
        if not all(a["ok"] for a in report["archives"]):raise RuntimeError("Cold archive failed; sources preserved")
    except Exception as error:
        report["error"]={"type":type(error).__name__,"message":str(error)};save()
        emit("backup_error",type=type(error).__name__,message=str(error))
    finally:
        # VPN must start before qBittorrent's container-network attachment.
        restoration={"standalone":{},"swarm":None}
        for host,names in standalone.items():
            ordered=sorted(names,key=lambda n:0 if n=="GlueTun-proton" else 2 if n=="qbittorrent" else 1)
            if ordered:
                try:restoration["standalone"][host]=ssh(host,docker_script(["start",*ordered]),timeout=180)["exit_code"]
                except Exception as error:restoration["standalone"][host]=type(error).__name__
        try:restoration["swarm"]=ssh(HOSTS[0],docker_script(["service","scale","--detach",*[f"{name}={count}" for name,count in replicas.items()]]),timeout=180)["exit_code"]
        except Exception as error:restoration["swarm"]=type(error).__name__
        report["restoration"]=restoration;save();emit("source_restarted",restoration=restoration)
    if report.get("error"):raise SystemExit(1)
    if restoration["swarm"] != 0 or any(code != 0 for code in restoration["standalone"].values()):
        report["error"]={"type":"SourceRestorationFailure","message":"One or more source restart commands failed"};save()
        emit("restoration_error",restoration=restoration);raise SystemExit(1)
    emit("recovery_verification_start")
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        report["archives"]=list(pool.map(verify,report["archives"]))
    report["completed_at"]=datetime.datetime.now(datetime.timezone.utc).isoformat();save()
    emit("backup_verified",archives=len(report["archives"]),entries=sum(a["tar_entries"] for a in report["archives"]),evidence=str(evidence))

if __name__=="__main__":main()
