"""Retire only this release's two completed CI exports, preserving all receipts."""
import argparse,hashlib,importlib.util,json,os,shutil,subprocess
from pathlib import Path
STORE=Path('/mnt/h/AgentArtifacts/projects/branconet/builds/wsl-artifact-store/files');O=STORE/'bortus-operator-recovery/empty-list-fix';SCRIPTS=Path(__file__).parent
STAGES=[('local-charts-publish-5db38ca0c9854bf2b0265924d0ba4f22','8ba156c1b23be161bf4a2a67cc191ce6aa6959a2'),('local-charts-publish-4a2234c898f14200b9964b94d61408b7','1580091e76b77a0175ff879e239642ac52064d4c')]
TOOLS=Path('/mnt/c/Users/james/.codex/local-ci/branconet-charts-local-ci/.tools')
def need(v):
 if not v:raise RuntimeError('final_ci_export_preservation_check_failed')
def sha(p):
 with p.open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()
def main():
 parser=argparse.ArgumentParser();parser.add_argument('--execute',action='store_true');args=parser.parse_args();need(os.geteuid()==0);need(json.loads((STORE/'bortus-operator-recovery/production-release-acceptance.json').read_bytes())['passed'])
 loader=importlib.util.spec_from_file_location('ci_export_inactive',SCRIPTS/'cleanup-bortus-release-files.py');m=importlib.util.module_from_spec(loader);loader.loader.exec_module(m);rows=[]
 for name,commit in STAGES:
  stage=STORE/'local-charts-publisher'/name;need(stage.resolve()==stage and stage.is_dir());p=json.loads((stage/'prepare.json').read_bytes());c=json.loads((stage/'check.json').read_bytes());publication=json.loads((stage/'publish.json').read_bytes());need(p['sourceSHA']==c['sourceSHA']==publication['sourceSHA']==commit and c['passed']is True and publication['passed']is True)
  paths=[stage/'source',stage/'home',stage/'tmp'];m.inactive(paths);files=0;found=set()
  for target in paths:
   need(target.resolve()==target and not target.is_symlink())
   for path in target.rglob('*'):
    need(not path.is_symlink()and path.lstat().st_uid==1000)
    if not path.is_file():continue
    files+=1;need(path.is_relative_to(stage/'source'));relative=str(path.relative_to(stage/'source'));raw=path.read_bytes()
    if relative in p['manifest']:need(hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()==p['manifest'][relative]['oid']);found.add(relative)
    elif relative.startswith('.tools/'):
     tool=path.name;need(tool in p['binariesSHA256']and hashlib.sha256(raw).hexdigest()==p['binariesSHA256'][tool]and sha(TOOLS/tool)==p['binariesSHA256'][tool])
    else:need(relative=='.validation/validation.json')
  need(found==set(p['manifest']))
  result=stage/'source/.validation/validation.json';need(result.is_file()and not(stage/'validation-result.json').exists());rows.append({'stage':str(stage),'commit':commit,'paths':[str(x)for x in paths],'allocated_bytes':sum(int(subprocess.check_output(['du','-sx','-B1',str(x)]).split()[0])for x in paths),'validation_sha256':sha(result),'files':files,'canonical_tool_source':str(TOOLS)})
 if not args.execute:
  with(O/'final-ci-export-cleanup-check.json').open('x')as f:json.dump({'rows':rows,'protected_older_5aaf_stage_untouched':True},f)
  print(json.dumps({'checked_stages':len(rows),'allocated_bytes':sum(r['allocated_bytes']for r in rows),'exported_files':sum(r['files']for r in rows)}));return
 need(rows==json.loads((O/'final-ci-export-cleanup-check.json').read_bytes())['rows']);removed=[]
 for row in rows:
  stage=Path(row['stage']);(stage/'source/.validation/validation.json').rename(stage/'validation-result.json');need(sha(stage/'validation-result.json')==row['validation_sha256'])
  for path in map(Path,row['paths']):shutil.rmtree(path);need(not path.exists())
  removed.append(row)
 with(O/'final-ci-export-cleanup.json').open('x')as f:json.dump({'removed':removed,'removed_allocated_bytes':sum(r['allocated_bytes']for r in rows),'validation_results_and_phase_receipts_preserved':True,'protected_older_5aaf_stage_untouched':True,'windows_recovery_claimed':False},f)
 print(json.dumps({'retired_stages':len(rows),'removed_allocated_bytes':sum(r['allocated_bytes']for r in rows),'free_inodes':os.statvfs(O).f_favail}))
if __name__=='__main__':main()
