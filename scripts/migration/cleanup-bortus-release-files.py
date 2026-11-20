"""Retire only completed task exports, contexts and generated tool trees with exact checks."""
import argparse,hashlib,importlib.util,json,os,shutil,subprocess,tarfile
from pathlib import Path
S=Path(__file__).parent;STORE=Path('/mnt/h/AgentArtifacts/projects/branconet/builds/wsl-artifact-store/files');A=STORE/'bortus-operator-recovery';O=A/'empty-list-fix';SEC=O/'security-tools'
def need(v):
 if not v:raise RuntimeError('release_file_cleanup_safety_check_failed')
def sha(p):
 with p.open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()
def inactive(paths):
 roots=[str(p)for p in paths];mounts=[x.split()[4]for x in Path('/proc/self/mountinfo').read_text().splitlines()];need(not any(m==r or m.startswith(r+'/')for m in mounts for r in roots))
 for process in Path('/proc').glob('[0-9]*'):
  refs=[process/'cwd',process/'exe']
  try:refs+=list((process/'fd').iterdir())
  except FileNotFoundError:continue
  for ref in refs:
   try:value=os.readlink(ref)
   except FileNotFoundError:continue
   need(not any(value==r or value.startswith(r+'/')for r in roots))
 ids=subprocess.check_output(['docker','ps','-aq','--no-trunc']).decode().split();containers=json.loads(subprocess.check_output(['docker','inspect',*ids]))if ids else[]
 need(not any(x['Source']==r or x['Source'].startswith(r+'/')for c in containers for x in c.get('Mounts',[])for r in roots))
def main():
 parser=argparse.ArgumentParser();parser.add_argument('--execute',action='store_true');args=parser.parse_args();need(os.geteuid()==0);accept=json.loads((A/'production-release-acceptance.json').read_bytes());reviews=json.loads((O/'release-review-cleanup.json').read_bytes());need(accept['passed']and reviews['state']=='completed')
 delta=json.loads((O/'runtime-tool-source-deltas.json').read_bytes());need(delta['state']=='preserved'and sha(Path(delta['archive']))==delta['sha256'])
 with tarfile.open(delta['archive'])as t:
  for item in delta['entries']:need(hashlib.sha256(t.extractfile(item['path']).read()).hexdigest()==item['sha256'])
 paths=[]
 for name in ('original','transport','final'):
  recipe=json.loads((O/('lossless-'+name+'-oci-recipe.json')).read_bytes());p=Path(recipe['archive_path']);need(recipe['private_registry_regeneration_verified']and sha(p)==recipe['archive_sha256']);paths.append(p)
 for n in ('context.tar','secured-context.tar','secured-net-context.tar','trivy'):
  p=O/n
  if p.exists():paths.append(p)
 for n in ('go','kubectl-source','trivy-source','tmp','bin','home'):
  p=SEC/n
  if p.exists():paths.append(p)
 # Reconcile every non-generated kubectl source edit against the retained capsule/delta.
 loader=importlib.util.spec_from_file_location('cleanup_source_inputs',S/'prepare-bortus-runtime-security.py');m=importlib.util.module_from_spec(loader);loader.loader.exec_module(m);baseline=json.loads((m.OLD/'source-inputs.json').read_bytes());edits={x['path']:x['sha256']for x in delta['entries']};deleted=[];links={};modes={}
 base=SEC/'kubectl-source'
 for n,prior in baseline.items():
  if Path(n).parts[0]in('vendor','LICENSES','_output'):continue
  p=base/n
  if not p.exists()and not p.is_symlink():deleted.append(n);continue
  if p.is_symlink():
   if os.readlink(p)!=prior.get('link'):links[n]=os.readlink(p)
  else:
   digest=sha(p);need(digest==prior.get('sha256')or edits.get('kubectl/'+n)==digest)
   if p.stat().st_mode&0o777!=prior.get('mode'):modes[n]=p.stat().st_mode&0o777
 rehydration={'deleted_non_generated_baseline_paths':deleted,'changed_links':links,'changed_modes':modes,'delta_sha256':delta['sha256'],'original_capsules_preserved':[str(m.CAP),str(m.OLD)]}
 if not args.execute:(O/'runtime-tool-rehydration.json').write_text(json.dumps(rehydration))
 else:need(json.loads((O/'runtime-tool-rehydration.json').read_bytes())==rehydration)
 for p in paths:need(p.resolve()==p and not p.is_symlink()and STORE in p.parents and not(S in p.parents))
 inactive(paths);rows=[]
 for p in paths:
  st=p.stat();allocated=int(subprocess.check_output(['du','-sx','-B1',str(p)]).split()[0]);rows.append({'path':str(p),'device':st.st_dev,'inode':st.st_ino,'allocated_bytes':allocated,'directory':p.is_dir()})
 if not args.execute:
  with(O/'release-file-cleanup-check.json').open('x')as f:json.dump({'rows':rows,'regeneration':'Lossless OCI registry recipes; retained frontend commits/build recipes; original source capsules plus verified source-delta archive and module manifests','no_process_container_or_mount_references':True},f)
  print(json.dumps({'checked_paths':len(rows),'allocated_bytes':sum(x['allocated_bytes']for x in rows)}));return
 previous=json.loads((O/'release-file-cleanup-check.json').read_bytes());need(rows==previous['rows']);before=os.statvfs(O).f_favail;removed=[]
 # Success/failure records and source capsules remain outside these exact targets.
 for row in rows:
  p=Path(row['path']);shutil.rmtree(p)if row['directory']else p.unlink();need(not p.exists());removed.append(row)
 result={'removed':removed,'removed_allocated_bytes':sum(x['allocated_bytes']for x in removed),'free_inodes_before':before,'free_inodes_after':os.statvfs(O).f_favail,'source_capsules_deltas_and_unique_failure_evidence_preserved':True,'windows_recovery_claimed':False}
 with(O/'release-file-cleanup.json').open('x')as f:json.dump(result,f)
 print(json.dumps({'removed_paths':len(removed),'removed_allocated_bytes':result['removed_allocated_bytes'],'free_inodes_after':result['free_inodes_after']}))
if __name__=='__main__':main()
