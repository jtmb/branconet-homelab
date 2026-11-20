"""Build one transport-only derivative using the qualified runtime and existing dependencies."""
import hashlib,io,json,os,subprocess,tarfile,time
from pathlib import Path
STORE=Path('/mnt/h/AgentArtifacts/projects/branconet/builds/wsl-artifact-store/files')
A=STORE/'bortus-operator-recovery';OUT=A/'empty-list-fix';COMMIT='cc319fb4124bc4a7b6a0336ff4ec6037c4bc99ec'
BASE='jtmb92/bortus@sha256:ac261f9cc146171469dd9bd660acae39ae9563656a9a873e0fa251d4b2fda58b'
TAG='jtmb92/bortus:release-'+COMMIT
REPO='/mnt/c/Users/james/OneDrive/Documents/ChatGPT/kubernetes migration';GIT='/mnt/c/Program Files/Git/cmd/git.exe';WIN='C:/Users/james/OneDrive/Documents/ChatGPT/kubernetes migration'
REGISTER=r'''
const fs=require('node:fs'),Module=require('node:module'),ts=require('/app/node_modules/typescript');
const original=Module._resolveFilename;
Module._resolveFilename=function(name,parent,...rest){return original.call(this,name.startsWith('@/')?'/app/src/'+name.slice(2):name,parent,...rest)};
require.extensions['.ts']=function(mod,file){mod._compile(ts.transpileModule(fs.readFileSync(file,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,esModuleInterop:true}}).outputText,file)};
'''
DOCKERFILE=f'''FROM node:22.23.3-bookworm@sha256:c4d5523090a817b7aa86d2111241fdd4f66d1e27782b44160e6aa63b357ecb2d AS npm-tools
FROM {BASE} AS builder
USER 0:0
WORKDIR /app
COPY . .
ENV NEXT_TELEMETRY_DISABLED=1 DATABASE_URL=file:/tmp/bortus-build/test.db CIRCLE_NODE_TOTAL=4 NPM_CONFIG_CACHE=/tmp/bortus-build/npm NPM_CONFIG_LOGS_DIR=/tmp/bortus-build/npm-logs APPDATA=/tmp/bortus-build/appdata LOCALAPPDATA=/tmp/bortus-build/localappdata TMPDIR=/tmp/bortus-build
RUN mkdir -p /tmp/bortus-build && node --require /app/.release-checks/register.cjs --test /app/.release-checks/transport.test.ts
COPY --from=npm-tools /usr/local/lib/node_modules/npm /opt/build-only/npm
RUN before="$(sha256sum package-lock.json)" && node /opt/build-only/npm/bin/npm-cli.js ci --include=dev --ignore-scripts --no-audit --no-fund && test "$before" = "$(sha256sum package-lock.json)" && node scripts/patch-next-body-finalize.mjs && node scripts/patch-zod-collections.mjs && node scripts/patch-minimatch-compat.mjs && node node_modules/prisma/build/index.js generate
RUN rm -rf /app/.next && node node_modules/next/dist/bin/next build --no-lint && rm -rf /app/.next/cache /app/.next/standalone
FROM {BASE}
USER 0:0
WORKDIR /app
RUN rm -rf /app/.next
COPY --from=builder --chown=1000:1000 /app/.next /app/.next
LABEL org.opencontainers.image.revision="{COMMIT}" org.opencontainers.image.base.name="{BASE}" io.branconet.owner="bortus-empty-list-fix"
USER 1000:1000
'''
def need(v):
 if not v:raise RuntimeError('empty_list_build_precondition_failed')
def main():
 need(os.geteuid()==0 and not OUT.exists())
 need(subprocess.check_output(['docker','info','--format','{{.DockerRootDir}}']).decode().strip()==str(STORE/'shared-docker-runtime/docker'))
 need(os.stat(STORE).st_dev==os.stat(STORE/'shared-docker-runtime/docker').st_dev)
 need(os.statvfs(STORE).f_bavail*os.statvfs(STORE).f_frsize>20*1024**3)
 OUT.mkdir(mode=0o700)
 archive=OUT/'context.tar';total=0;source=[]
 child=subprocess.Popen([GIT,'-C',WIN,'archive',COMMIT+':k8s-rewrite/front-end'],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
 try:
  with tarfile.open(fileobj=child.stdout,mode='r|') as incoming,tarfile.open(archive,'w') as outgoing:
   for member in incoming:
    if not member.isfile():continue
    need(member.size<16*1024**2 and not member.name.startswith('/') and '..' not in Path(member.name).parts)
    data=incoming.extractfile(member).read();total+=len(data);need(total<128*1024**2)
    source.append({'path':member.name,'sha256':hashlib.sha256(data).hexdigest()})
    if member.name in ('Dockerfile','.dockerignore'):continue
    if member.name=='tests/transport.test.ts':member.name='.release-checks/transport.test.ts'
    elif member.name.startswith('tests/'):continue
    outgoing.addfile(member,io.BytesIO(data))
   for name,text in [('Dockerfile',DOCKERFILE),('.dockerignore',''),('.release-checks/register.cjs',REGISTER)]:
    data=text.encode();member=tarfile.TarInfo(name);member.size=len(data);member.mode=0o644;outgoing.addfile(member,io.BytesIO(data))
  need(child.wait(timeout=15)==0)
 finally:
  if child.poll() is None:child.terminate();child.wait(timeout=5)
 manifest={'repository':REPO,'source':COMMIT,'parent_runtime':BASE,'purpose':'Transport-only empty metadata-list fix; native/dependency/UI source unchanged','source_files':source,'context_sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'owned_paths':[str(archive),str(OUT/'build.log')],'regeneration':'Run this source recipe after reconciled removal of its inactive owned outputs','physical_volume':'existing H ext4 store e4c3cddc-ace6-4f27-a8b8-23278c17b53f'}
 (OUT/'manifest.json').write_text(json.dumps(manifest));os.chmod(OUT/'manifest.json',0o600)
 with archive.open('rb') as context,(OUT/'build.log').open('wb') as log:
  env=dict(os.environ,DOCKER_BUILDKIT='0');result=subprocess.run(['docker','build','--pull=false','--tag',TAG,'-'],stdin=context,stdout=log,stderr=subprocess.STDOUT,env=env,timeout=1200)
 (OUT/'result.json').write_text(json.dumps({'exit_code':result.returncode,'source':COMMIT,'tag':TAG,'production_deployed':False}));need(result.returncode==0)
 image=json.loads(subprocess.check_output(['docker','image','inspect',TAG]))[0];(OUT/'image.json').write_text(json.dumps({'id':image['Id'],'size':image['Size'],'rootfs_layers':image['RootFS']['Layers']}));print(json.dumps({'built':True,'source':COMMIT,'image':image['Id']}))
if __name__=='__main__':main()
