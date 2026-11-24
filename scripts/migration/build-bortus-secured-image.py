"""Package the verified runtime patches and rebuilt scanner metadata using cached app tooling."""
import argparse,hashlib,io,json,os,subprocess,tarfile
from pathlib import Path
OUT=Path('/mnt/h/AgentArtifacts/projects/branconet/builds/wsl-artifact-store/files/bortus-operator-recovery/empty-list-fix')
SOURCE=Path('/mnt/c/Users/james/OneDrive/Documents/ChatGPT/kubernetes migration/k8s-rewrite/front-end/scripts/scanner-inputs.json')
BASE='jtmb92/bortus@sha256:125ff65843db4b73971ceba5bae89ddca49569d2543bc5986346c4e496d6e564'
def need(v):
 if not v:raise RuntimeError('secured_image_input_check_failed')
def digest(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def main():
 parser=argparse.ArgumentParser();parser.add_argument('--resume-context-format',action='store_true');args=parser.parse_args()
 root=OUT/'security-tools';published=json.loads((OUT/'security-source-publication.json').read_bytes());commit=published['commit'];need(len(commit)==40 and published['public_source_only'])
 if args.resume_context_format:
  prior=json.loads((OUT/'secured-build.json').read_bytes());need(prior['state']=='failed' and prior['exit_code']==1 and prior['source']==commit and 'dockerfile line greater than max allowed size' in (OUT/'secured-build.log').read_text() and digest(OUT/'secured-context.tar')==prior['context_sha256'])
  for proc in Path('/proc').glob('[0-9]*/fd'):
   try:refs=list(proc.iterdir())
   except FileNotFoundError:continue
   for ref in refs:
    try:need(os.readlink(ref)!=str(OUT/'secured-context.tar'))
    except FileNotFoundError:pass
  need(not (OUT/'secured-build-context-format.json').exists());os.rename(OUT/'secured-build.json',OUT/'secured-build-context-format.json');os.rename(OUT/'secured-build.log',OUT/'secured-build-context-format.log')
 else:need(not (OUT/'secured-build.json').exists())
 states={n:json.loads((root/(n+'-build-state.json')).read_bytes())for n in ('kubectl','trivy')}
 for n,s in states.items():need(s['state']=='completed' and digest(root/'bin'/n)==s['sha256'])
 pins=json.loads(SOURCE.read_bytes());need(pins['binarySHA256']==states['trivy']['sha256'] and pins['version']=='0.76.1-bortus.3');need(json.loads((root/'libc/patch.json').read_bytes())['state']=='prepared')
 builder=json.loads(subprocess.check_output(['docker','image','inspect','bortus-build-cache:cc319fb']))[0]['Id'];need(builder.startswith('sha256:bd69a0fc25ca'))
 recipe=f'''FROM {builder} AS builder
USER 0:0
WORKDIR /app
COPY scanner-inputs.json /app/scripts/scanner-inputs.json
RUN rm -rf /app/.next && node node_modules/next/dist/bin/next build --no-lint && rm -rf /app/.next/cache /app/.next/standalone
FROM {BASE}
USER 0:0
WORKDIR /app
COPY --chown=0:0 libc/ /
COPY --chown=0:0 kubectl /usr/local/bin/kubectl
COPY --chown=0:0 trivy /opt/bortus-scanner/trivy
COPY --chown=1000:1000 scanner-inputs.json /app/scripts/scanner-inputs.json
RUN chmod 555 /usr/local/bin/kubectl /opt/bortus-scanner/trivy && rm -rf /app/.next
COPY --from=builder --chown=1000:1000 /app/.next /app/.next
LABEL org.opencontainers.image.revision="{commit}" org.opencontainers.image.base.name="{BASE}" io.branconet.owner="bortus-runtime-security" io.branconet.bortus.trivy-sha256="{states['trivy']['sha256']}" io.branconet.bortus.trivy-version="0.76.1-bortus.3" io.branconet.bortus.trivy-toolchain="go1.27.4" io.branconet.bortus.kubectl-sha256="{states['kubectl']['sha256']}" io.branconet.bortus.kubectl-toolchain="go1.27.4" io.branconet.bortus.compiled-source-scope="Transport empty-list correction and maintained scanner metadata; existing application UI source retained"
USER 1000:1000
'''
 archive=OUT/'secured-context.tar';need(args.resume_context_format or not archive.exists());inputs={}
 with tarfile.open(archive,'w',format=tarfile.GNU_FORMAT)as t:
  data=recipe.encode();member=tarfile.TarInfo('Dockerfile');member.size=len(data);member.mode=0o644;t.addfile(member,io.BytesIO(data))
  for path,name in [(SOURCE,'scanner-inputs.json'),(root/'bin/kubectl','kubectl'),(root/'bin/trivy','trivy')]:t.add(path,arcname=name,recursive=False);inputs[name]=digest(path)
  t.add(root/'libc/patch',arcname='libc')
 record={'state':'building','source':commit,'base':BASE,'tag':'jtmb92/bortus:release-'+commit,'inputs':inputs,'recipe':recipe,'context_sha256':digest(archive),'current_security_and_runtime_acceptance_pending':True};(OUT/'secured-build.json').write_text(json.dumps(record))
 with archive.open('rb') as stream,(OUT/'secured-build.log').open('xb')as log:result=subprocess.run(['docker','build','--pull=false','--tag',record['tag'],'-'],stdin=stream,stdout=log,stderr=subprocess.STDOUT,env=dict(os.environ,DOCKER_BUILDKIT='0'),timeout=1200)
 record.update(state='built'if result.returncode==0 else 'failed',exit_code=result.returncode);(OUT/'secured-build.json').write_text(json.dumps(record));need(result.returncode==0);image=json.loads(subprocess.check_output(['docker','image','inspect',record['tag']]))[0];record.update(image=image['Id'],bytes=image['Size'],layers=image['RootFS']['Layers']);(OUT/'secured-build.json').write_text(json.dumps(record));print(json.dumps({k:record[k]for k in ('state','source','image','tag')}))
if __name__=='__main__':main()
