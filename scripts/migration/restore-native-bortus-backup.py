#!/usr/bin/env python3
"""Restore the native encrypted NAS backup into a separate retained Longhorn claim."""
import datetime,json,pathlib,subprocess,time
ROOT=pathlib.Path(__file__).resolve().parents[2];RUNTIME=pathlib.Path.home()/'.local/share/branconet-migration';k=[str(RUNTIME/'bin/kubectl'),'--kubeconfig',str(RUNTIME/'admin.conf')]
def run(args,body=None):return subprocess.run(k+args,input=json.dumps(body).encode() if body is not None else None,capture_output=True,check=True,timeout=650).stdout
report=json.loads((ROOT/'evidence/native-volume-backups.json').read_text());source=next(v for v in report['volumes'] if v['namespace']=='bortus')
if not report['snapshots_consistent'] or source.get('backup_state')!='Completed':raise RuntimeError('Completed cold BORTUS NAS backup required')
sc=json.loads(run(['get','storageclass','longhorn','-o','json']));params=dict(sc['parameters']);params['fromBackup']=source['url'];name='migration-nas-bortus-restore'
if run(['get','pvc',name,'-n','migration-system','--ignore-not-found','-o','json']):raise RuntimeError('Inspect prior independent restore before repeating')
run(['create','-f','-'],{'apiVersion':'storage.k8s.io/v1','kind':'StorageClass','metadata':{'name':name},'provisioner':'driver.longhorn.io','allowVolumeExpansion':True,'reclaimPolicy':'Retain','volumeBindingMode':'Immediate','parameters':params})
run(['create','-f','-'],{'apiVersion':'v1','kind':'PersistentVolumeClaim','metadata':{'name':name,'namespace':'migration-system'},'spec':{'storageClassName':name,'accessModes':['ReadWriteOnce'],'resources':{'requests':{'storage':'1Gi'}}}})
run(['create','-f','-'],{'apiVersion':'v1','kind':'Pod','metadata':{'name':name,'namespace':'migration-system'},'spec':{'automountServiceAccountToken':False,'restartPolicy':'Never','nodeName':'workernode2','containers':[{'name':'restore-check','image':'python@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1','command':['python3','-c','import time;time.sleep(1800)'],'volumeMounts':[{'name':'data','mountPath':'/data','readOnly':True}],'resources':{'requests':{'cpu':'10m','memory':'32Mi'},'limits':{'memory':'256Mi'}}}],'volumes':[{'name':'data','persistentVolumeClaim':{'claimName':name,'readOnly':True}}]}})
run(['wait','pod/'+name,'-n','migration-system','--for=condition=Ready','--timeout=600s'])
code="import sqlite3,json,hashlib,pathlib;p=pathlib.Path('/data/bortus.db');db=sqlite3.connect('file:'+str(p)+'?mode=ro',uri=True);tables=[r[0] for r in db.execute(\"select name from sqlite_master where type='table' and name not like 'sqlite_%'\")];print(json.dumps({'database_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'integrity':db.execute('PRAGMA integrity_check').fetchone()[0],'table_counts':{name:db.execute('select count(*) from '+chr(34)+name+chr(34)).fetchone()[0] for name in tables}}))"
restored=json.loads(run(['exec',name,'-n','migration-system','--','python3','-c',code]));expected=report['bortus_cold_database']
if restored!=expected or restored['integrity']!='ok':raise RuntimeError('Restored SQLite contents or integrity differs')
pvc=json.loads(run(['get','pvc',name,'-n','migration-system','-o','json']));volume=json.loads(run(['get','volumes.longhorn.io',pvc['spec']['volumeName'],'-n','longhorn-system','-o','json']))
if not volume['spec']['encrypted'] or volume['spec']['numberOfReplicas']!=2:raise RuntimeError('Restored volume encryption/replica policy differs')
proof={'completed_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'source_backup':source['backup'],'source_claim':'bortus/bortus-data','independent_restored_claim':'migration-system/'+name,'actual_offcluster_nas_restore':True,'native_luks_key_decryption_passed':True,'database_bytes_sha256_equal':True,'sqlite_integrity':'ok','all_table_counts_equal':True,'encrypted_two_replica_volume':True,'source_and_restore_claims_retained':True}
(ROOT/'evidence/native-bortus-restore.json').write_text(json.dumps(proof,indent=2)+'\n');print(json.dumps(proof))
