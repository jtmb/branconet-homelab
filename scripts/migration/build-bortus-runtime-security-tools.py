"""Build the two existing runtime tools with patched Go/Otel under one owned H root."""
import argparse,hashlib,importlib.util,json,os,subprocess,time
from pathlib import Path
s=importlib.util.spec_from_file_location('security_tool_inputs',Path(__file__).with_name('prepare-bortus-runtime-security.py'));m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
def main():
 parser=argparse.ArgumentParser();parser.add_argument('--tool',choices=['kubectl','trivy'],required=True);args=parser.parse_args();tool=args.tool;root=m.OUT;go=root/'go/bin/go';source=root/(tool+'-source');state_path=root/(tool+'-build-state.json');m.need(not state_path.exists() and go.is_file() and source.is_dir())
 state={'tool':tool,'state':'preparing','go':'go1.27.4','steps':[]};state_path.write_text(json.dumps(state))
 env=dict(os.environ,PATH=str(go.parent)+':/usr/bin:/bin',HOME=str(root/'home'),GOPATH=str(root/'cache/gopath'),GOMODCACHE=str(root/'cache/modules'),GOCACHE=str(root/'cache/go'),TMPDIR=str(root/'tmp'),TMP=str(root/'tmp'),TEMP=str(root/'tmp'),GOENV='off',GOTOOLCHAIN='local',GOWORK='off',GOPROXY='https://proxy.golang.org',GOSUMDB='sum.golang.org',GOPRIVATE='',GONOPROXY='',GONOSUMDB='',GOINSECURE='',GIT_CONFIG_NOSYSTEM='1',GIT_CONFIG_GLOBAL='/dev/null',GIT_TERMINAL_PROMPT='0',CGO_ENABLED='0',GOOS='linux',GOARCH='amd64',GOMAXPROCS='2',GOFLAGS='-p=2',GOMEMLIMIT='4GiB',LANG='C',LC_ALL='C',TZ='UTC',SOURCE_DATE_EPOCH='1790183182')
 def command(name,argv,seconds=1200):
  state.update(state='running',step=name);state_path.write_text(json.dumps(state))
  with (root/(tool+'-'+name+'.log')).open('xb') as log:r=subprocess.run(argv,cwd=source,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=seconds)
  state['steps'].append({'name':name,'exit':r.returncode});state_path.write_text(json.dumps(state));m.need(r.returncode==0)
 try:
  command('version',[str(go),'version'],30)
  if tool=='kubectl':
   vendor_tmp=root/'tmp/kubectl-vendor';vendor_tmp.mkdir(mode=0o700);env['TMP_DIR']=str(vendor_tmp)
   version=(m.OLD/'custom-version.sh').read_text().replace('bortus.security.1','bortus.security.2');version_path=root/'kubectl-version.sh';version_path.write_text(version);env['KUBE_GIT_VERSION_FILE']=str(version_path);env['KUBE_BUILD_PLATFORMS']='linux/amd64';env['GO_VERSION']='1.27.4'
   for n,module in enumerate(['go.opentelemetry.io/otel','go.opentelemetry.io/otel/trace','go.opentelemetry.io/otel/metric']):command('pin-'+str(n),['/bin/bash','hack/pin-dependency.sh',module,'v1.47.0'])
   command('vendor',['/bin/bash','hack/update-vendor.sh'])
   command('compile',['/bin/bash','hack/make-rules/build.sh','cmd/kubectl'])
   candidate=source/'_output/local/bin/linux/amd64/kubectl';target=root/'bin/kubectl';m.need(candidate.is_file());target.write_bytes(candidate.read_bytes());target.chmod(0o755);command('binary-version',[str(target),'version','--client=true','-o','json'],30)
  else:
   verified=json.loads((root/'trivy-source-verification.json').read_bytes());m.need(verified['all_git_blobs_verified'])
   pins={'github.com/go-jose/go-jose/v4':'v4.1.6','golang.org/x/crypto':'v0.58.1-0.20261009181718-2f1f834330b2','golang.org/x/net':'v0.62.0','golang.org/x/sys':'v0.49.0','golang.org/x/term':'v0.47.0','golang.org/x/text':'v0.43.0','go.opentelemetry.io/otel':'v1.47.0','go.opentelemetry.io/otel/sdk':'v1.47.0','go.opentelemetry.io/otel/trace':'v1.47.0','go.opentelemetry.io/otel/metric':'v1.47.0'}
   command('dependencies',[str(go),'get',*[k+'@'+v for k,v in pins.items()]])
   # The current upstream version symbol is checked from source before this stage.
   command('compile',[str(go),'build','-mod=mod','-trimpath','-ldflags','-s -w -X github.com/aquasecurity/trivy/pkg/version/app.ver=0.76.1-bortus.3','-o',str(root/'bin/trivy'),'./cmd/trivy'])
   target=root/'bin/trivy';command('binary-version',[str(target),'--version'],30)
  command('build-info',[str(go),'version','-m',str(target)],30);state.update(state='completed',binary=str(target),sha256=m.sha(target),bytes=target.stat().st_size);state_path.write_text(json.dumps(state));print(json.dumps({k:state[k]for k in ('tool','state','binary','sha256','bytes')}))
 except Exception as error:state.update(state='failed',error_type=type(error).__name__);state_path.write_text(json.dumps(state));raise
if __name__=='__main__':main()
