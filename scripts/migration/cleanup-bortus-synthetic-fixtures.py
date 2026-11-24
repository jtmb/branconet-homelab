"""Check and remove only the four completed synthetic review bind directories."""
import argparse,importlib.util,json,os,re,shutil,sqlite3,subprocess
from pathlib import Path
S=Path(__file__).parent;STORE=Path('/mnt/h/AgentArtifacts/projects/branconet/builds/wsl-artifact-store/files');A=STORE/'bortus-operator-recovery';O=A/'empty-list-fix'
def need(v):
 if not v:raise RuntimeError('synthetic_fixture_preservation_check_failed')
def main():
 parser=argparse.ArgumentParser();parser.add_argument('--execute',action='store_true');args=parser.parse_args();need(json.loads((A/'production-release-acceptance.json').read_bytes())['passed']and json.loads((O/'release-review-cleanup.json').read_bytes())['state']=='completed')
 roots=[STORE/'shared-docker-runtime/bortus-review',O/'local-fixture',O/'secured-local-fixture',O/'secured-net-local-fixture'];paths=[];rows=[]
 for root in roots:
  db=root/'data/bortus.db';connection=sqlite3.connect('file:'+str(db)+'?mode=ro',uri=True)
  try:users=connection.execute('SELECT username FROM users').fetchall();need(all(x[0]=='bortus_review'for x in users))
  finally:connection.close()
  if root!=roots[0]:
   kube=json.loads((root/'data/review-kube.json').read_bytes());need(kube['clusters'][0]['cluster']['server']=='https://127.0.0.1:16443'and kube['users'][0]['user']['token']=='synthetic-review-token')
  for leaf in('data','home','tmp'):
   p=root/leaf;need(p.resolve()==p and not p.is_symlink());paths.append(p)
   for file in p.rglob('*'):
    need(not file.is_symlink())
    if file.is_file():
     name=str(file.relative_to(root));need(name in['data/bortus.db','data/probe.crt','data/probe.key','data/review-kube.json','data/mock-api.cjs','home/.cache/checkpoint-nodejs/signature']or re.fullmatch(r'home/\.cache/checkpoint-nodejs/prisma-[a-f0-9]+',name))
   st=p.stat();rows.append({'path':str(p),'device':st.st_dev,'inode':st.st_ino,'allocated_bytes':int(subprocess.check_output(['du','-sx','-B1',str(p)]).split()[0])})
 loader=importlib.util.spec_from_file_location('fixture_inactivity',S/'cleanup-bortus-release-files.py');m=importlib.util.module_from_spec(loader);loader.loader.exec_module(m);m.inactive(paths)
 if not args.execute:
  with(O/'synthetic-fixture-cleanup-check.json').open('x')as f:json.dump({'rows':rows,'only_synthetic_users_and_local_mock_api':True,'actual_nvda_evidence_retained':True,'regenerate':'Retained original review seed and qualify-bortus-empty-list-image.py; production data never used'},f)
  print(json.dumps({'synthetic_only':True,'checked_paths':len(rows),'allocated_bytes':sum(r['allocated_bytes']for r in rows)}));return
 need(rows==json.loads((O/'synthetic-fixture-cleanup-check.json').read_bytes())['rows'])
 for p in paths:shutil.rmtree(p)
 removed_empty=[]
 for root in roots[1:]:
  if not any(root.iterdir()):root.rmdir();removed_empty.append(str(root))
 with(O/'synthetic-fixture-cleanup.json').open('x')as f:json.dump({'removed':rows,'removed_empty_roots':removed_empty,'removed_allocated_bytes':sum(r['allocated_bytes']for r in rows),'actual_acceptance_and_production_data_preserved':True},f)
 print(json.dumps({'synthetic_directories_removed':len(paths),'removed_allocated_bytes':sum(r['allocated_bytes']for r in rows)}))
if __name__=='__main__':main()
