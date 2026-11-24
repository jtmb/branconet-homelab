"""Repair the two actual current x/net findings, reusing the verified tool source/cache."""
import argparse,hashlib,importlib.util,json,os,subprocess
from pathlib import Path
s=importlib.util.spec_from_file_location('net_repair_inputs',Path(__file__).with_name('prepare-bortus-runtime-security.py'));m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
def main():
 parser=argparse.ArgumentParser();parser.add_argument('--resume-vendor-directory',action='store_true');args=parser.parse_args()
 root=m.OUT;source=root/'kubectl-source';state_path=root/'kubectl-net-build-state.json';prior=json.loads((root/'kubectl-build-state.json').read_bytes());m.need(prior['state']=='completed')
 if args.resume_vendor_directory:
  failed=json.loads(state_path.read_bytes());m.need(failed['state']=='failed' and failed['step']=='vendor' and 'No such file or directory'in (root/'kubectl-net-vendor.log').read_text());m.need(not (root/'kubectl-net-build-directory-failure.json').exists());state_path.rename(root/'kubectl-net-build-directory-failure.json')
 else:m.need(not state_path.exists())
 (root/'tmp/kubectl-vendor').mkdir(mode=0o700,exist_ok=True)
 state={'state':'preparing','prior_sha256':prior['sha256'],'reason':['CVE-2026-78661','CVE-2026-97045'],'steps':[]};state_path.write_text(json.dumps(state))
 env=dict(os.environ,PATH=str(root/'go/bin')+':/usr/bin:/bin',HOME=str(root/'home'),GOPATH=str(root/'cache/gopath'),GOMODCACHE=str(root/'cache/modules'),GOCACHE=str(root/'cache/go'),TMPDIR=str(root/'tmp'),TMP=str(root/'tmp'),TEMP=str(root/'tmp'),TMP_DIR=str(root/'tmp/kubectl-vendor'),GOENV='off',GOTOOLCHAIN='local',GOWORK='off',GOPROXY='https://proxy.golang.org',GOSUMDB='sum.golang.org',GOPRIVATE='',GONOPROXY='',GONOSUMDB='',GOINSECURE='',GIT_CONFIG_NOSYSTEM='1',GIT_CONFIG_GLOBAL='/dev/null',GIT_TERMINAL_PROMPT='0',CGO_ENABLED='0',GOOS='linux',GOARCH='amd64',GOMAXPROCS='2',GOFLAGS='-p=2',GOMEMLIMIT='4GiB',LANG='C',LC_ALL='C',TZ='UTC',SOURCE_DATE_EPOCH='1790183182',KUBE_GIT_VERSION_FILE=str(root/'kubectl-version.sh'),KUBE_BUILD_PLATFORMS='linux/amd64',GO_VERSION='1.27.4')
 def command(name,argv,seconds=1200):
  state.update(state='running',step=name);state_path.write_text(json.dumps(state))
  with (root/('kubectl-net-'+name+'.log')).open('xb') as log:r=subprocess.run(argv,cwd=source,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=seconds)
  state['steps'].append({'name':name,'exit':r.returncode});state_path.write_text(json.dumps(state));m.need(r.returncode==0)
 try:
  if not args.resume_vendor_directory:command('pin',['/bin/bash','hack/pin-dependency.sh','golang.org/x/net','v0.62.0'])
  command('vendor-resume'if args.resume_vendor_directory else 'vendor',['/bin/bash','hack/update-vendor.sh'])
  command('compile',['/bin/bash','hack/make-rules/build.sh','cmd/kubectl'])
  target=root/'bin/kubectl-net-fixed';m.need(not target.exists());target.write_bytes((source/'_output/local/bin/linux/amd64/kubectl').read_bytes());target.chmod(0o755)
  command('version',[str(target),'version','--client=true','-o','json'],30);command('build-info',[str(root/'go/bin/go'),'version','-m',str(target)],30)
  info=(root/'kubectl-net-build-info.log').read_text();m.need('go1.27.4'in info and 'golang.org/x/net\tv0.62.0'in info)
  state.update(state='completed',binary=str(target),sha256=m.sha(target),bytes=target.stat().st_size,go_mod_sha256=m.sha(source/'go.mod'),go_sum_sha256=m.sha(source/'go.sum'));state_path.write_text(json.dumps(state));print(json.dumps({k:state[k]for k in ('state','sha256','bytes')}))
 except Exception as e:state.update(state='failed',error_type=type(e).__name__);state_path.write_text(json.dumps(state));raise
if __name__=='__main__':main()
