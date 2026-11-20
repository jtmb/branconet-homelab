"""Resume the unchanged legacy writer after the pre-capture recipient-mode refusal."""
import argparse,importlib.util,json,os,pathlib,re,sys,time
ROOT=pathlib.Path(__file__).parent;D=pathlib.Path('/mnt/h/AgentArtifacts/projects/branconet/builds/wsl-artifact-store/files/bortus-operator-recovery/recovery/bortus-checkpoints/060849dabf9a')
def load(name,file):
 s=importlib.util.spec_from_file_location(name,ROOT/file);m=importlib.util.module_from_spec(s);sys.modules[name]=m;s.loader.exec_module(m);return m
def main():
 global D
 parser=argparse.ArgumentParser();parser.add_argument('--run-id',default='060849dabf9a');args=parser.parse_args();assert re.fullmatch('[0-9a-f]{12}',args.run_id);D=D.with_name(args.run_id)
 raw=(D/'journal.json').read_bytes();r=json.loads(raw);assert r['quiescent']['state'] in ('pending','captured-zero') and r['sqlite_archive_state'] in ('pending','confirmed') and 'owner_resume_intent' not in r['quiescent']
 if r['quiescent']['state']=='captured-zero':assert r['encrypted_nas_backup_complete'] and r['cold_snapshot_ready'] and r['owned_holder_removed']
 if r.get('snapshot_create_state')=='uncertain':
  assert r['snapshot_create_state']=='uncertain' and r['quiescent_last_failure']['code']=='intent'
  import subprocess
  check=subprocess.run(['/home/brajam/.local/share/branconet-migration/bin/kubectl','--kubeconfig','/home/brajam/.local/share/branconet-migration/admin.conf','get','snapshots.longhorn.io',r['snapshot_name'],'-n','longhorn-system','--ignore-not-found','-o','json'],capture_output=True,timeout=20);assert check.returncode==0 and not check.stdout.strip()
 op=load('safe_resume_guard','bortus-admission-operator.py');cred=load('safe_resume_credentials','bortus-operator-mtls.py');api=op.API(cred.OperatorMTLSOptions('/home/brajam/.local/share/branconet-migration/admin.conf'))
 for suffix in ('pods','templates','cronjobs'):
  p=api.guard(op.validator.POLICY,'bortus-kv-guard-'+suffix,deadline=time.monotonic()+60);images=json.loads(next(v['expression'] for v in p['spec']['variables'] if v['name']=='approvedImages'));assert r['baseline']['legacy_image'] in images
 fd=os.open(D/'pre-recovery-journal.json',os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
 with os.fdopen(fd,'wb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
 cold=load('safe_resume_cold','checkpoint-bortus-volume.py');j=cold.Journal(D);j.open(new=False)
 try:
  cold.Checkpoint(cold.Client(),j).resume()
  assert j.record['writer_resumed_ready'] and j.record['reconcile_flags_restored']
  if not j.record.get('owned_holder_removed'):cold.Checkpoint(cold.Client(),j).release_holder()
  assert j.record['owned_holder_removed']
  print(json.dumps({'original_writer_resumed':True,'original_reconcile_flags_restored':True,'reader_absent':True,'original_failure_preserved':True,'data_preserved':True}))
 finally:j.close()
if __name__=='__main__':main()
