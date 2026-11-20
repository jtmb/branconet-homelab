"""Remove only the attended BORTUS review container and exclusively owned local image."""
import json,os,subprocess
from pathlib import Path
STORE=Path('/mnt/h/AgentArtifacts/projects/branconet/builds/wsl-artifact-store/files')
A=STORE/'bortus-operator-recovery';REVIEW=STORE/'shared-docker-runtime/bortus-review'
CID='40b777d3c7813b2713a8b392e61e859aa0557efa19f10a2ca05fd3ab36f51563'
IMAGE='sha256:ac261f9cc146171469dd9bd660acae39ae9563656a9a873e0fa251d4b2fda58b'
def need(v):
 if not v:raise RuntimeError('review_cleanup_preservation_check_failed')
def run(*args):return subprocess.check_output(['docker',*args],timeout=45).decode().strip()
def main():
 need(os.geteuid()==0)
 receipt=json.loads((A/'production-release-acceptance.json').read_bytes());need(receipt['passed'] is True and receipt['image'].endswith(IMAGE))
 need(not (A/'local-review-cleanup.json').exists())
 need(run('info','--format','{{.DockerRootDir}}')==str(STORE/'shared-docker-runtime/docker'))
 need(os.stat(STORE).st_dev==os.stat(STORE/'shared-docker-runtime/docker').st_dev)
 target=json.loads(run('inspect',CID))[0];need(target['Id']==CID and target['Name']=='/bortus-review-12dce115' and target['Image']==IMAGE and target['Config']['Labels']['io.branconet.owner']=='bortus-local-review')
 need({x['Source'] for x in target['Mounts']}=={str(REVIEW/n) for n in ('data','home','tmp')})
 all_ids=run('ps','-aq','--no-trunc').splitlines();all_containers=json.loads(run('inspect',*all_ids)) if all_ids else []
 need([x['Id'] for x in all_containers if x['Image']==IMAGE]==[CID])
 image=json.loads(run('image','inspect',IMAGE))[0];need(image['Id']==IMAGE)
 tags=image.get('RepoTags') or [];digests=image.get('RepoDigests') or []
 need(tags==['jtmb92/bortus:release-12dce115006877fed2c674cad1ffd40805932974'] and digests==['jtmb92/bortus@'+IMAGE])
 archive=STORE/'release-v2-12dce115-inputs/candidate-pod-summary-root.oci.tar';need(archive.is_file() and not archive.is_symlink() and archive.stat().st_size==497920000)
 if target['State']['Running']:need(run('stop','--time','20',CID)==CID)
 need(run('rm',CID)==CID)
 for reference in tags+digests:
  probe=subprocess.run(['docker','image','inspect',reference],capture_output=True,timeout=15)
  if probe.returncode==0:run('image','rm',reference)
 need(subprocess.run(['docker','inspect',CID],capture_output=True).returncode!=0 and subprocess.run(['docker','image','inspect',IMAGE],capture_output=True).returncode!=0)
 result={'review_container_removed':CID,'local_image_removed':IMAGE,'logical_image_bytes':image['Size'],'unrelated_images_and_volumes_untouched':True,'physical_windows_recovery_claimed':False,'retained_fixture_directory':str(REVIEW),'retained_archive_consumer':'Qualified release recovery input; retirement requires preservation reconciliation'}
 fd=os.open(A/'local-review-cleanup.json',os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
 with os.fdopen(fd,'w') as f:json.dump(result,f)
 print(json.dumps(result))
if __name__=='__main__':main()
