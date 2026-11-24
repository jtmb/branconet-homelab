#!/usr/bin/env python3
"""Protect current Redis writable state before any further source task removal."""
import datetime,hashlib,io,json,pathlib,subprocess,tarfile,shlex
ROOT=pathlib.Path(__file__).resolve().parents[2]
RUNTIME=pathlib.Path.home()/'.local/share/branconet-migration'
REMOTE=r'''
import subprocess,sys
ids=subprocess.check_output(['docker','ps','-q','--filter','label=com.docker.swarm.service.name=wordpress_redis-db'],text=True).split()
if len(ids)!=1:raise SystemExit('Exactly one source Redis writer required')
cid=ids[0]
saved=subprocess.run(['docker','exec',cid,'redis-cli','SAVE'],capture_output=True,text=True)
if saved.returncode or saved.stdout.strip()!='OK':raise SystemExit('Redis SAVE not accepted')
paused=False
try:
 subprocess.run(['docker','pause',cid],capture_output=True,check=True);paused=True
 archive=subprocess.check_output(['docker','cp',cid+':/data','-'])
 sys.stdout.buffer.write(archive)
finally:
 if paused:subprocess.run(['docker','unpause',cid],capture_output=True,check=True)
'''
def main():
 raw=subprocess.run(['ssh','-o','BatchMode=yes','-p','2002','james@192.168.0.4','python3','-'],input=REMOTE.encode(),capture_output=True,check=True).stdout
 with tarfile.open(fileobj=io.BytesIO(raw)) as archive:
  members=archive.getmembers();dumps=[m for m in members if m.name.endswith('/dump.rdb') and m.size]
  if not dumps:raise SystemExit('Redis archive has no nonempty saved snapshot')
  for member in members:
   if member.isfile():
    f=archive.extractfile(member)
    while f.read(1024*1024):pass
 recipient=(pathlib.Path.home()/'.ssh/id_ed25519.pub').read_text().strip()
 encrypted=subprocess.run([str(RUNTIME/'bin/age'),'-r',recipient],input=raw,capture_output=True,check=True).stdout
 stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ');target=RUNTIME/'recovery'/('redis-current-'+stamp+'.tar.age')
 target.write_bytes(encrypted);target.chmod(0o600)
 recovered=subprocess.run([str(RUNTIME/'bin/age'),'-d','-i',str(pathlib.Path.home()/'.ssh/id_ed25519'),str(target)],capture_output=True,check=True).stdout
 if raw!=recovered:raise SystemExit('Authenticated archive mismatch')
 nas='/mnt/container-backups/k8s-migration-20261009/'+target.name
 writer="import pathlib,sys;pathlib.Path("+repr(nas)+").write_bytes(sys.stdin.buffer.read())"
 subprocess.run(['ssh','-o','BatchMode=yes','-p','2002','james@192.168.0.4','python3','-c',shlex.quote(writer)],input=encrypted,capture_output=True,check=True)
 reader="import pathlib,sys;sys.stdout.buffer.write(pathlib.Path("+repr(nas)+").read_bytes())"
 actual=subprocess.run(['ssh','-o','BatchMode=yes','-p','2002','james@192.168.0.4','python3','-c',shlex.quote(reader)],capture_output=True,check=True).stdout
 if actual!=encrypted:raise SystemExit('NAS archive byte comparison failed')
 report={'completed_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'source':'wordpress_redis-db','save_and_pause_consistent':True,'source_unpaused':True,'authenticated_decryption_equal':True,'tar_entries':len(members),'dump_bytes':sum(m.size for m in dumps),'ciphertext_sha256':hashlib.sha256(encrypted).hexdigest(),'operator_copy':str(target),'nas_copy':nas,'original_removed_state_recovered':False}
 (ROOT/'evidence/redis-current-backup.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
if __name__=='__main__':main()
