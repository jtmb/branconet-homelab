"""Retire exact owned reviews and their inactive build graph after live acceptance."""
import argparse,hashlib,json,os,re,subprocess
from pathlib import Path
STORE=Path('/mnt/h/AgentArtifacts/projects/branconet/builds/wsl-artifact-store/files');A=STORE/'bortus-operator-recovery';O=A/'empty-list-fix'
def need(v):
 if not v:raise RuntimeError('release_cleanup_safety_check_failed')
def run(*args):return subprocess.check_output(['docker',*args],stderr=subprocess.PIPE,timeout=90).decode().strip()
def images():
 ids=list(dict.fromkeys(run('image','ls','-aq','--no-trunc').split()));return {i['Id']:i for i in json.loads(run('image','inspect',*ids))}if ids else{}
def main():
 parser=argparse.ArgumentParser();parser.add_argument('--resume-image-cleanup',action='store_true');args=parser.parse_args()
 need(os.geteuid()==0 and (args.resume_image_cleanup or not(O/'release-review-cleanup.json').exists()));accepted=json.loads((A/'production-release-acceptance.json').read_bytes());qualified=json.loads((A/'qualified-final-image.json').read_bytes());need(accepted['passed']is True and accepted['image']==qualified['image'] and accepted['native_cleanup_complete']is True and accepted['original_rows_preserved']is True)
 previous=json.loads((O/'release-review-cleanup.json').read_bytes())if args.resume_image_cleanup else None
 need(run('info','--format','{{.DockerRootDir}}')==str(STORE/'shared-docker-runtime/docker'))
 targets=[('40b777d3c7813b2713a8b392e61e859aa0557efa19f10a2ca05fd3ab36f51563','bortus-review-12dce115','sha256:ac261f9cc146171469dd9bd660acae39ae9563656a9a873e0fa251d4b2fda58b','bortus-local-review',STORE/'shared-docker-runtime/bortus-review')]
 for prefix,name in [('', 'bortus-review-cc319fb'),('secured-','bortus-review-secured-34b8fa1'),('secured-net-','bortus-review-secured-net-34b8fa1')]:
  d=json.loads((O/(prefix+'runtime-qualification.json')).read_bytes());need(d['state']=='completed'and d['reviewed_client_assets_byte_identical']);targets.append((d['container'],name,d['image'],'bortus-empty-list-fix-review',O/(prefix+'local-fixture')))
 inventory=images();ids=run('ps','-aq','--no-trunc').split();containers=json.loads(run('inspect',*ids))if ids else[];selected=[]
 for cid,name,image,owner,root in targets:
  found=[c for c in containers if c['Id']==cid]
  if previous and not found:need(any(c['id']==cid and c['name']=='/'+name for c in previous['containers']));continue
  need(len(found)==1);c=found[0];need(c['Name']=='/'+name and c['Image']==image and c['Config']['Labels']['io.branconet.owner']==owner and {x['Source']for x in c['Mounts']}=={str(root/n)for n in('data','home','tmp')});need(not any(other['Image']==image and other['Id']!=cid for other in containers));selected.append(c)
 # Build-log IDs are bounded to this task; shared upstream tool images are excluded.
 candidates={t[2]for t in targets if t[2]in inventory};protected={'sha256:c4d5523090a817b7aa86d2111241fdd4f66d1e27782b44160e6aa63b357ecb2d'}
 protected.update(i['Id']for i in inventory.values()if'node:22.23.3-bookworm'in(i.get('RepoTags')or[])or any(d.endswith('@sha256:c4d5523090a817b7aa86d2111241fdd4f66d1e27782b44160e6aa63b357ecb2d')for d in(i.get('RepoDigests')or[])))
 for log in ['build.log','build-missing-tailwind.log','build-missing-npm.log','build-changed-lock.log','secured-build.log','secured-net-build.log']:
  for short in re.findall(r'^ ---> ([0-9a-f]{12,64})\s*$',(O/log).read_text(),re.M):
   matches=[i for i in inventory if i.split(':')[1].startswith(short)];need(len(matches)<=1)
   if matches:candidates.add(matches[0])
 candidates-=protected
 allowed_tags={'jtmb92/bortus:release-12dce115006877fed2c674cad1ffd40805932974','jtmb92/bortus:release-cc319fb4124bc4a7b6a0336ff4ec6037c4bc99ec','jtmb92/bortus:release-34b8fa18c34576721ff4fb064923f1499598481d','bortus-build-cache:cc319fb'}
 for image in candidates:
  need(set(inventory[image].get('RepoTags')or[])<=allowed_tags)
 result=previous or {'state':'running','containers':[],'removed_images':[],'retained_images':[],'physical_windows_recovery_claimed':False,'source_and_registry_images_untouched':True};path=O/'release-review-cleanup.json'
 if previous:
  need(previous['state']=='running' and len(previous['containers'])==4)
  result['ownership_reconciliation']='bd69a0fc cache alias is exactly bortus-build-cache@its verified image digest, created by the retained original build/cache recipe; no foreign repository alias, container or consumer is allowed.'
 def save():path.write_text(json.dumps(result));path.chmod(0o600)
 save()
 for c in selected:
  measured=json.loads(run('container','inspect','--size',c['Id']))[0]
  if measured['State']['Running']:run('stop','--time','20',c['Id'])
  run('rm',c['Id']);result['containers'].append({'id':c['Id'],'name':c['Name'],'writable_layer_logical_bytes':measured.get('SizeRw')});save()
 pending=set(candidates)
 while pending:
  current=images();pending&=set(current);progress=False
  for image in list(pending):
   if any(i.get('Parent')==image for i in current.values()):continue
   live=run('ps','-aq','--no-trunc').split();refs=json.loads(run('inspect',*live))if live else[]
   if any(c['Image']==image for c in refs):continue
   info=current[image];tags=info.get('RepoTags')or[];digests=info.get('RepoDigests')or[];allowed_digests={'jtmb92/bortus@'+image}
   if image=='sha256:bd69a0fc25caf81f714c29384be62f59b40953f7df15e5ecf06052fee400f424' and tags==['bortus-build-cache:cc319fb']:allowed_digests.add('bortus-build-cache@'+image)
   need(set(tags)<=allowed_tags and set(digests)<=allowed_digests)
   for reference in tags+digests:
    probe=subprocess.run(['docker','image','inspect',reference],capture_output=True,timeout=30)
    if probe.returncode==0:run('image','rm',reference)
   probe=subprocess.run(['docker','image','inspect',image],capture_output=True,timeout=30)
   if probe.returncode==0:run('image','rm',image)
   need(subprocess.run(['docker','image','inspect',image],capture_output=True,timeout=30).returncode!=0)
   result['removed_images'].append({'id':image,'rootfs_logical_bytes_not_additive':info['Size']});pending.remove(image);progress=True;save();break
  if not progress:break
 current=images()
 for image in pending:result['retained_images'].append({'id':image,'reason':'Existing child image or container reference','children':[i['Id']for i in current.values()if i.get('Parent')==image]})
 result['state']='completed'if not pending else'partial-preserved';save();print(json.dumps({'state':result['state'],'containers_removed':len(result['containers']),'images_removed':len(result['removed_images']),'retained_images':result['retained_images']}))
if __name__=='__main__':main()
