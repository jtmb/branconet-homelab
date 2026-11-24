"""Reconcile only the recorded inert reader from pre-control final attempt181d7aa3e9ce."""
import hashlib,importlib.util,json,os,sys,time
from pathlib import Path
ROOT=Path(__file__).parent;A=Path('/mnt/h/AgentArtifacts/projects/branconet/builds/wsl-artifact-store/files/bortus-operator-recovery');D=A/'recovery/bortus-checkpoints/181d7aa3e9ce'
def load(name,file):
 s=importlib.util.spec_from_file_location(name,ROOT/file);m=importlib.util.module_from_spec(s);sys.modules[name]=m;s.loader.exec_module(m);return m
def main():
 raw=(D/'journal.json').read_bytes();r=json.loads(raw);assert r['quiescent']['state']=='pending' and not r.get('sqlite_archive_state') and r['holder_create_state']=='confirmed'
 cold=load('reconcile_final_cold','checkpoint-bortus-volume.py');reader=load('reconcile_final_reader','bortus-restore-reader.py');schema=load('reconcile_final_schema','schema-current-writer-v1/current-schema-producer.py')
 client=cold.Client();op=cold.Checkpoint(client,type('ReadOnlyJournal',(),{'record':r})())
 for key,entry in r['controls'].items():
  obj=client.get(*cold.RESOURCES[key][:3]);assert cold.same_id(obj,entry['identity']) and obj['spec'].get(cold.RESOURCES[key][3],False)==entry['original']
 pod=op.holder();reader.inert_holder(pod,r['holder_proposal']);assert pod['metadata']['uid']==r['holder_identity']['uid']
 context={k:pod['metadata'][k] for k in ('name','namespace','uid')}|{'spec_sha256':hashlib.sha256(json.dumps(pod['spec'],sort_keys=True,separators=(',',':')).encode()).hexdigest()}
 options=reader.credentials.OperatorMTLSOptions('/home/brajam/.local/share/branconet-migration/admin.conf');before=schema.snapshot(schema.VerifiedAPI(options).get,time.monotonic()+120,context)
 path=D/'reader-reconciliation.json';fd=os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
 with os.fdopen(fd,'w') as f:json.dump({'state':'delete-pending','original_journal_sha256':hashlib.sha256(raw).hexdigest(),'holder_uid':pod['metadata']['uid'],'actual_schema_with_exact_owned_reader_passed':True},f);f.flush();os.fsync(f.fileno())
 client.delete_holder(pod)
 until=time.monotonic()+90
 while time.monotonic()<until:
  current=cold.preflight.complete_pods(client.get('pods',namespace='bortus'))
  if not any(p['metadata']['uid']==pod['metadata']['uid'] or p['metadata']['name']==pod['metadata']['name'] for p in current):break
  time.sleep(.5)
 else:raise RuntimeError('owned_reader_absence_not_observed')
 assert (D/'journal.json').read_bytes()==raw
 fd=os.open(path,os.O_WRONLY|os.O_TRUNC|os.O_NOFOLLOW)
 with os.fdopen(fd,'w') as f:json.dump({'state':'completed','original_journal_sha256':hashlib.sha256(raw).hexdigest(),'holder_uid':pod['metadata']['uid'],'actual_schema_with_exact_owned_reader_passed':True,'owned_holder_absent':True,'production_writer_unchanged':True},f);f.flush();os.fsync(f.fileno())
 print(json.dumps({'actual_schema_check_corrected':True,'owned_reader_removed':True,'original_writer_and_journal_unchanged':True}))
if __name__=='__main__':main()
