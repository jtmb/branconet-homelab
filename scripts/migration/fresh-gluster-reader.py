#!/usr/bin/env python3
"""Create an independent read-only client for stale source FUSE lookups."""
import datetime,json,pathlib,shlex,subprocess,sys
REMOTE=r'''
import subprocess,sys,json,pathlib
pw=sys.stdin.read().strip()
def run(arguments):
 r=subprocess.run(['sudo','-S','-p','',*arguments],input=pw+chr(10),capture_output=True,text=True)
 if r.returncode:raise SystemExit('Privileged read-only mount operation failed: '+arguments[0])
run(['mkdir','-p','/mnt/migration-gluster-read'])
mounted=subprocess.run(['findmnt','-rn','--mountpoint','/mnt/migration-gluster-read'],capture_output=True,text=True)
if mounted.returncode:run(['mount','-t','glusterfs','-o','ro','192.168.0.5:/staging-gfs','/mnt/migration-gluster-read'])
root=pathlib.Path('/mnt/migration-gluster-read')
print(json.dumps({'host':'192.168.0.5','readonly_fresh_gluster_client':True,'source_mount':'/mnt/migration-gluster-read','mounted':True}))
'''
def main():
 password=json.load(sys.stdin)['sudo_password']
 r=subprocess.run(['ssh','-o','BatchMode=yes','-p','2002','james@192.168.0.5','python3','-c',shlex.quote(REMOTE)],input=password,capture_output=True,text=True)
 if r.returncode:raise SystemExit(r.stderr[-1000:])
 report=json.loads(r.stdout);report['completed_at']=datetime.datetime.now(datetime.timezone.utc).isoformat()
 (pathlib.Path(__file__).resolve().parents[2]/'evidence/fresh-gluster-reader.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
if __name__=='__main__':main()
