#!/usr/bin/env python3
"""Capture migration metadata, never environment values or credential material."""
import argparse
import concurrent.futures
import datetime
import json
import pathlib
import subprocess

HOSTS = ("192.168.0.4", "192.168.0.5", "192.168.0.6")
REMOTE = r'''
import json, subprocess, re, socket
def docker(*args):
    return json.loads(subprocess.check_output(["docker", *args], text=True))
def text(*args):
    return subprocess.check_output(args, text=True).strip()
def mounts(items):
    return [{k:m.get(k) for k in ("Type","Source","Target","Destination","ReadOnly","RW","Name") if k in m} for m in items]
def routes(labels):
    found=[]
    for key,value in (labels or {}).items():
        if key.startswith("traefik.") and key.endswith(".rule"):
            found += re.findall(r"Host\(`([^`]+)`\)", value)
    return sorted(set(found))
out={"hostname":socket.gethostname(),"services":[],"containers":[],"images":{},"mounts":[]}
ids=text("docker","service","ls","-q").split()
for s in docker("service","inspect",*ids) if ids else []:
    spec=s["Spec"]; task=spec["TaskTemplate"]; c=task["ContainerSpec"]
    out["services"].append({"name":spec["Name"],"image":c["Image"],"mode":spec["Mode"],"environment_keys":sorted(v.split("=",1)[0] for v in c.get("Env",[])),"mounts":mounts(c.get("Mounts",[])),"ports":(spec.get("EndpointSpec") or {}).get("Ports",[]),"constraints":(task.get("Placement") or {}).get("Constraints",[]),"networks":task.get("Networks",[]),"routes":routes(spec.get("Labels")),"command_argument_count":len(c.get("Command",[]))+len(c.get("Args",[])),"capabilities":c.get("CapabilityAdd",[]),"user":c.get("User"),"resources":task.get("Resources",{}),"secret_refs":c.get("Secrets",[]),"config_refs":c.get("Configs",[])})
ids=text("docker","ps","-aq").split()
for c in docker("inspect",*ids) if ids else []:
    config=c["Config"]; host=c["HostConfig"]; labels=config.get("Labels") or {}
    out["containers"].append({"name":c["Name"].lstrip("/"),"service":labels.get("com.docker.swarm.service.name"),"state":c["State"]["Status"],"image":config["Image"],"image_id":c["Image"],"mounts":mounts(c["Mounts"]),"environment_keys":sorted(v.split("=",1)[0] for v in config.get("Env",[])),"ports":host.get("PortBindings"),"network_mode":host.get("NetworkMode"),"privileged":host.get("Privileged"),"cap_add":host.get("CapAdd"),"devices":host.get("Devices"),"device_requests":host.get("DeviceRequests"),"compose_project":labels.get("com.docker.compose.project"),"compose_files":labels.get("com.docker.compose.project.config_files")})
    if c["Image"] not in out["images"]:
        im=docker("image","inspect",c["Image"])[0]
        out["images"][c["Image"]]={"repo_digests":im.get("RepoDigests",[]),"architecture":im.get("Architecture"),"os":im.get("Os"),"exposed_ports":list((im.get("Config") or {}).get("ExposedPorts") or {})}
out["mounts"]=json.loads(text("findmnt","-J","-o","TARGET,SOURCE,FSTYPE"))["filesystems"]
out["swarm_nodes"]=text("docker","node","ls","--format","{{.Hostname}}|{{.Status}}|{{.Availability}}|{{.ManagerStatus}}")
out["backup_space"]=text("df","-B1","/mnt/container-backups")
print(json.dumps(out))
'''

def inspect(host):
    command = ["ssh", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=yes",
               "-o", "ConnectTimeout=8", "-i", str(pathlib.Path.home()/".ssh/id_ed25519"),
               "-p", "2002", f"james@{host}", "python3", "-"]
    result = subprocess.run(command, input=REMOTE, text=True, capture_output=True, timeout=90)
    if result.returncode:
        raise RuntimeError(f"Inventory failed on {host}: exit {result.returncode}")
    return host, json.loads(result.stdout)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",type=pathlib.Path,required=True)
    args=parser.parse_args()
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        nodes=dict(pool.map(inspect,HOSTS))
    report={"captured_at":datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "redaction":"Environment values, raw labels, command arguments and credential files excluded", "nodes":nodes}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    primary=nodes[HOSTS[0]]
    standalone=[(ip,c["name"]) for ip,n in nodes.items() for c in n["containers"] if not c["service"]]
    print(json.dumps({"output":str(args.output),"service_count":len(primary["services"]),"standalone":standalone}))

if __name__=="__main__":main()
