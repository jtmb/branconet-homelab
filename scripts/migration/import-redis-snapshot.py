#!/usr/bin/env python3
"""Restore the protected current Redis snapshot into its new retained claim."""
import base64,datetime,hashlib,io,json,pathlib,subprocess,tarfile,yaml
ROOT=pathlib.Path(__file__).resolve().parents[2];RUNTIME=pathlib.Path.home()/'.local/share/branconet-migration'
def main():
 evidence=json.loads((ROOT/'evidence/redis-current-backup.json').read_text());raw=subprocess.check_output([str(RUNTIME/'bin/age'),'-d','-i',str(pathlib.Path.home()/'.ssh/id_ed25519'),evidence['operator_copy']])
 with tarfile.open(fileobj=io.BytesIO(raw)) as archive:
  member=next(m for m in archive.getmembers() if m.name.endswith('/dump.rdb'));dump=archive.extractfile(member).read()
 k=[str(RUNTIME/'bin/kubectl'),'--kubeconfig',str(RUNTIME/'admin.conf')];h=[str(RUNTIME/'bin/helm'),'--kubeconfig',str(RUNTIME/'admin.conf')];directory=ROOT/'k8s-rewrite/charts/apps/wordpress-redis'
 subprocess.run(h+['upgrade','--install','wordpress-redis',str(directory),'-n','wordpress','--set','enabled=true,migration.staging=true,replicaCount=0'],capture_output=True,check=True)
 name='redis-snapshot-import';pod={'apiVersion':'v1','kind':'Pod','metadata':{'name':name,'namespace':'wordpress'},'spec':{'restartPolicy':'Never','automountServiceAccountToken':False,'terminationGracePeriodSeconds':5,'containers':[{'name':'restore','image':'python@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1','command':['python3','-c','import time;time.sleep(900)'],'volumeMounts':[{'name':'data','mountPath':'/data'}]}],'volumes':[{'name':'data','persistentVolumeClaim':{'claimName':'wordpress-redis-data'}}]}}
 subprocess.run(k+['create','-f','-'],input=json.dumps(pod).encode(),capture_output=True,check=True)
 try:
  subprocess.run(k+['wait','pod/'+name,'-n','wordpress','--for=condition=Ready','--timeout=300s'],capture_output=True,check=True)
  code="import pathlib,base64,hashlib,json,os\np=pathlib.Path('/data/dump.rdb')\nif p.exists():raise SystemExit('Existing data must be reviewed')\nb=base64.b64decode("+repr(base64.b64encode(dump).decode())+")\np.write_bytes(b);p.chmod(0o600);os.chown(p,999,999)\nprint(json.dumps({'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}))"
  actual=json.loads(subprocess.run(k+['exec','-i','-n','wordpress',name,'--','python3','-'],input=code.encode(),capture_output=True,check=True).stdout)
  if actual['sha256']!=hashlib.sha256(dump).hexdigest():raise SystemExit('Snapshot file readback mismatch')
 finally:subprocess.run(k+['delete','pod',name,'-n','wordpress','--wait=true'],capture_output=True)
 subprocess.run(['ssh','-o','BatchMode=yes','-p','2002','james@192.168.0.4','docker','service','scale','--detach','wordpress_redis-db=0'],capture_output=True,check=True)
 subprocess.run(h+['upgrade','wordpress-redis',str(directory),'-n','wordpress','--set','enabled=true,migration.staging=true,replicaCount=1','--wait','--timeout','5m'],capture_output=True,check=True)
 ping=subprocess.check_output(k+['exec','-n','wordpress','deployment/wordpress-redis','--','redis-cli','PING'],text=True).strip()
 if ping!='PONG':raise SystemExit('Restored Redis PING failed')
 count=int(subprocess.check_output(k+['exec','-n','wordpress','deployment/wordpress-redis','--','redis-cli','DBSIZE'],text=True).strip())
 report={'completed_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'chart':'apps/wordpress-redis','snapshot_readback_equal':True,'native_redis_ping':True,'current_keys':count,'persistent_claim':'wordpress-redis-data','original_removed_state_recovered':False,'production_routing_accepted':False,'source_current_backup_retained':True}
 (ROOT/'evidence/private-wordpress-redis.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
if __name__=='__main__':main()
