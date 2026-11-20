"""Verify real native test values never entered the post-write SQLite checkpoint."""
import importlib.util,json,time
from pathlib import Path
S=Path(__file__).parent
def load(name,file):
 s=importlib.util.spec_from_file_location(name,S/file);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
def main():
 m=load('storage_acceptance','verify-bortus-production.py');norm=load('storage_normalize','normalize-bortus-sqlite-archive.py');native=json.loads((m.A/'production-native-probe.json').read_bytes());proof=json.loads((m.A/'production-native-restart-preservation.json').read_bytes());m.need(native['state']=='completed'and native['native_cleanup_complete']and proof['passed']);checkpoint=proof['deployed_checkpoint'];journal=json.loads((m.A/'recovery/bortus-checkpoints'/checkpoint/'journal.json').read_bytes());archive=journal['sqlite_archive'];normalized=None
 try:
  normalized=norm.normalize(Path(archive['artifact']),archive['ciphertext_sha256'],Path.home()/'.ssh/id_ed25519',age=m.R/'bin/age',seconds=120,deadline=time.monotonic()+120)
  data=Path(normalized['database_path']).read_bytes();m.need(all((prefix+native['suffix']).encode()not in data for prefix in('release-first-','release-second-')));data=None
 finally:
  if normalized:norm.cleanup(normalized['temporary_directory'],normalized['temporary_directory_identity'])
 m.save('production-native-storage-acceptance.json',{'passed':True,'native_values_absent_from_post_write_sqlite':True,'checkpoint':checkpoint,'plaintext_removed':True,'values_printed':False});print(json.dumps({'native_values_absent_from_sqlite':True,'plaintext_removed':True}))
if __name__=='__main__':main()
