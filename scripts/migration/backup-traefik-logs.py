#!/usr/bin/env python3
"""Archive the source access logs consistently before ingress cutover."""
import datetime,hashlib,io,json,pathlib,shlex,subprocess,sys,tarfile
ROOT=pathlib.Path(__file__).resolve().parents[2];RUNTIME=pathlib.Path.home()/'.local/share/branconet-migration'
request=json.load(sys.stdin);password=request['sudo_password'];host=request.get('host','192.168.0.4')
if host not in {'192.168.0.4','192.168.0.5','192.168.0.6'}:raise RuntimeError('Unexpected host')
code=r'''
import subprocess,sys
ids=subprocess.check_output(['docker','ps','-q','--filter','label=com.docker.swarm.service.name=proxy_traefik'],text=True).split()
if len(ids)>1:raise RuntimeError('More than one original Traefik writer')
if ids:subprocess.run(['docker','pause',ids[0]],capture_output=True,check=True)
try:sys.stdout.buffer.write(subprocess.check_output(['tar','--acls','--xattrs','--numeric-owner','-C','/','-cf','-','var/log/traefik']))
finally:
 if ids:subprocess.run(['docker','unpause',ids[0]],capture_output=True,check=True)
'''
wrapper='import subprocess,sys\nr=subprocess.run('+repr(['sudo','-S','-p','','python3','-c',code])+',input='+repr((password+'\n').encode())+',capture_output=True)\nif r.returncode:raise RuntimeError("Source log backup failed")\nsys.stdout.buffer.write(r.stdout)'
raw=subprocess.check_output(['ssh','-o','BatchMode=yes','-p','2002','james@'+host,'python3','-'],input=wrapper.encode())
with tarfile.open(fileobj=io.BytesIO(raw)) as tar:members=tar.getmembers()
recipient=(pathlib.Path.home()/'.ssh/id_ed25519.pub').read_text().strip();encrypted=subprocess.check_output([str(RUNTIME/'bin/age'),'-r',recipient],input=raw)
stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ');target=RUNTIME/'recovery'/('traefik-logs-'+host+'-'+stamp+'.tar.age');target.write_bytes(encrypted);target.chmod(0o600)
if subprocess.check_output([str(RUNTIME/'bin/age'),'-d','-i',str(pathlib.Path.home()/'.ssh/id_ed25519'),str(target)])!=raw:raise RuntimeError('Archive authentication mismatch')
nas='/mnt/container-backups/k8s-migration-20261009/'+target.name
writer='import pathlib,sys;pathlib.Path('+repr(nas)+').write_bytes(sys.stdin.buffer.read())';subprocess.run(['ssh','-p','2002','james@'+host,'python3','-c',shlex.quote(writer)],input=encrypted,capture_output=True,check=True)
reader='import pathlib,sys;sys.stdout.buffer.write(pathlib.Path('+repr(nas)+').read_bytes())'
if subprocess.check_output(['ssh','-p','2002','james@'+host,'python3','-c',shlex.quote(reader)])!=encrypted:raise RuntimeError('NAS ciphertext differs')
report={'completed_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'paused_writer_archive':True,'source_unpaused':True,'authenticated_recovery_equal':True,'nas_bytes_equal':True,'entries':len(members),'uncompressed_bytes':sum(m.size for m in members),'ciphertext_sha256':hashlib.sha256(encrypted).hexdigest(),'operator_copy':str(target),'nas_copy':nas}
report['host']=host;(ROOT/'evidence'/('traefik-log-backup-'+host+'.json')).write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
