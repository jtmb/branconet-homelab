"""Replace only the repaired kubectl in the already compiled/reviewed image."""
import hashlib,io,json,os,subprocess,tarfile
from pathlib import Path
O=Path('/mnt/h/AgentArtifacts/projects/branconet/builds/wsl-artifact-store/files/bortus-operator-recovery/empty-list-fix')
def need(v):
 if not v:raise RuntimeError('net_package_verification_failed')
def main():
 b=json.loads((O/'secured-build.json').read_bytes());n=json.loads((O/'security-tools/kubectl-net-build-state.json').read_bytes());p=Path(n['binary']);need(n['state']=='completed' and hashlib.sha256(p.read_bytes()).hexdigest()==n['sha256']);need(not(O/'secured-net-build.json').exists())
 recipe=f'''FROM {b['image']}
USER 0:0
COPY --chown=0:0 kubectl /usr/local/bin/kubectl
RUN chmod 555 /usr/local/bin/kubectl
LABEL io.branconet.bortus.kubectl-sha256="{n['sha256']}" io.branconet.bortus.kubectl-x-net="v0.62.0"
USER 1000:1000
'''
 c=O/'secured-net-context.tar'
 with tarfile.open(c,'x',format=tarfile.GNU_FORMAT)as t:
  raw=recipe.encode();x=tarfile.TarInfo('Dockerfile');x.size=len(raw);x.mode=0o644;t.addfile(x,io.BytesIO(raw));t.add(p,arcname='kubectl',recursive=False)
 r={'state':'building','source':b['source'],'tag':b['tag'],'base':b['image'],'kubectl_sha256':n['sha256'],'recipe':recipe,'context_sha256':hashlib.sha256(c.read_bytes()).hexdigest()};(O/'secured-net-build.json').write_text(json.dumps(r))
 with c.open('rb')as f,(O/'secured-net-build.log').open('xb')as log:job=subprocess.run(['docker','build','--pull=false','--tag',r['tag'],'-'],stdin=f,stdout=log,stderr=subprocess.STDOUT,env=dict(os.environ,DOCKER_BUILDKIT='0'),timeout=300)
 r.update(state='built'if job.returncode==0 else'failed',exit_code=job.returncode);(O/'secured-net-build.json').write_text(json.dumps(r));need(job.returncode==0)
 i=json.loads(subprocess.check_output(['docker','image','inspect',r['tag']]))[0];r.update(image=i['Id'],bytes=i['Size'],layers=i['RootFS']['Layers']);(O/'secured-net-build.json').write_text(json.dumps(r));print(json.dumps({k:r[k]for k in ('state','source','image','tag')}))
if __name__=='__main__':main()
