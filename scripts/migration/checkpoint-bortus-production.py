"""Checkpoint the deployed candidate and compare every original row after migration."""
import argparse,importlib.util,json,os,sys,time,uuid
from pathlib import Path
ROOT=Path(__file__).parent
def load(name,file):
 s=importlib.util.spec_from_file_location(name,ROOT/file);m=importlib.util.module_from_spec(s);sys.modules[name]=m;s.loader.exec_module(m);return m
def main():
 parser=argparse.ArgumentParser();parser.add_argument('--original-run',required=True);parser.add_argument('--after-native',action='store_true');args=parser.parse_args()
 m=load('checkpoint_prod_http','verify-bortus-production.py');cold=load('checkpoint_prod_cold','checkpoint-bortus-volume.py');norm=load('checkpoint_prod_norm','normalize-bortus-sqlite-archive.py');compare=load('checkpoint_prod_compare','compare-bortus-databases.py')
 m.need(len(args.original_run)==12 and all(c in '0123456789abcdef' for c in args.original_run))
 original=json.loads((m.A/'recovery/bortus-checkpoints'/args.original_run/'journal.json').read_bytes());m.need(original['sqlite_archive_state']=='confirmed' and original['encrypted_nas_backup_complete'] is True)
 with m.production('pre-checkpoint-'+('native' if args.after_native else 'migration')) as (api,identity):m.need(api.call('GET','/api/health/ready')['status']=='ready')
 client=cold.Client();baseline=client.inspect('19cc4b60-4536-4d80-8789-e27b5ad48b79',m.IMAGE)
 run=uuid.uuid4().hex[:12];record=cold.prepare(client,baseline,m.IMAGE,run);directory=m.A/'recovery/bortus-checkpoints'/run
 normalized=[];journal=cold.Journal(directory,record);journal.open(new=True)
 try:
  cold.Checkpoint(client,journal).capture()
  m.need(journal.record['writer_resumed_ready'] and journal.record['reconcile_flags_restored'] and journal.record['owned_holder_removed'] and journal.record['encrypted_nas_backup_complete'])
  deadline=time.monotonic()+120
  for archive in (original['sqlite_archive'],journal.record['sqlite_archive']):normalized.append(norm.normalize(Path(archive['artifact']),archive['ciphertext_sha256'],Path.home()/'.ssh/id_ed25519',age=m.R/'bin/age',seconds=120,deadline=deadline))
  result=compare.compare(Path(normalized[0]['database_path']),Path(normalized[1]['database_path']),'forward',deadline=deadline);m.need(result['passed'] is True)
 finally:
  for item in normalized:norm.cleanup(item['temporary_directory'],item['temporary_directory_identity'])
  journal.close()
 result.update(plaintext_copies_cleaned=True,original_run=args.original_run,deployed_checkpoint=run,image=m.IMAGE,original_pvc_preserved=True,real_pod_replacement=True)
 m.save('production-native-restart-preservation.json' if args.after_native else 'production-forward-preservation.json',result)
 print(json.dumps({'production_original_rows_preserved':True,'checkpoint':run,'plaintext_cleaned':True,'writer_resumed':True}))
if __name__=='__main__':main()
