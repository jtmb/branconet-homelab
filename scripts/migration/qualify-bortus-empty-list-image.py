"""Run the repaired image against empty TLS API lists, preserving the reviewed UI."""
import argparse,base64,hashlib,importlib.util,json,os,secrets,subprocess,time,urllib.request
from pathlib import Path
s=importlib.util.spec_from_file_location('fixed_image_build',Path(__file__).with_name('build-bortus-empty-list-fix.py'));b=importlib.util.module_from_spec(s);s.loader.exec_module(b)
def run(*args,timeout=30):return subprocess.check_output(list(args),stderr=subprocess.PIPE,timeout=timeout).decode().strip()
def main():
 parser=argparse.ArgumentParser();parser.add_argument('--secured',action='store_true');parser.add_argument('--net-fixed',action='store_true');args=parser.parse_args();args.secured=args.secured or args.net_fixed
 b.need(os.geteuid()==0);out=b.OUT;result=json.loads((out/('secured-net-build.json'if args.net_fixed else 'secured-build.json'if args.secured else 'result.json')).read_bytes());b.need(result['exit_code']==0)
 tag=result['tag'] if args.secured else b.TAG;commit=result['source']if args.secured else b.COMMIT;prefix='secured-'if args.secured else '';port='21090'if args.secured else '21089';container_name='bortus-review-secured-34b8fa1'if args.secured else 'bortus-review-cc319fb'
 if args.net_fixed:prefix='secured-net-';port='21091';container_name='bortus-review-secured-net-34b8fa1'
 image=json.loads(run('docker','image','inspect',tag))[0];base=json.loads(run('docker','image','inspect',b.BASE))[0]
 b.need(image['Config']['Labels']['org.opencontainers.image.revision']==commit and image['RootFS']['Layers'][:len(base['RootFS']['Layers'])]==base['RootFS']['Layers'])
 b.need(not (out/(prefix+'local-review.json')).exists());fixture=out/(prefix+'local-fixture');fixture.mkdir(mode=0o700)
 for name in ('data','home','tmp'):(fixture/name).mkdir(mode=0o700);os.chown(fixture/name,1000,1000)
 data=fixture/'data';run('openssl','req','-x509','-newkey','rsa:2048','-nodes','-keyout',str(data/'probe.key'),'-out',str(data/'probe.crt'),'-days','2','-subj','/CN=localhost','-addext','subjectAltName=IP:127.0.0.1,DNS:localhost')
 for path in (data/'probe.key',data/'probe.crt'):path.chmod(0o600);os.chown(path,1000,1000)
 kube={'apiVersion':'v1','kind':'Config','clusters':[{'name':'fixture','cluster':{'server':'https://127.0.0.1:16443','certificate-authority-data':base64.b64encode((data/'probe.crt').read_bytes()).decode()}}],'users':[{'name':'fixture','user':{'token':'synthetic-review-token'}}],'contexts':[{'name':'fixture','context':{'cluster':'fixture','user':'fixture'}}],'current-context':'fixture'}
 (data/'review-kube.json').write_text(json.dumps(kube));os.chown(data/'review-kube.json',1000,1000)
 (data/'mock-api.cjs').write_text("const fs=require('fs');require('https').createServer({key:fs.readFileSync('/data/probe.key'),cert:fs.readFileSync('/data/probe.crt')},(q,r)=>{r.writeHead(q.headers.authorization==='Bearer synthetic-review-token'?200:401,{'Content-Type':'application/json'});r.end(JSON.stringify({apiVersion:'meta.k8s.io/v1',kind:'PartialObjectMetadataList',metadata:{resourceVersion:'1'},items:null}));}).listen(16443,'127.0.0.1');")
 os.chown(data/'mock-api.cjs',1000,1000)
 env=fixture/'review.env';env.write_text('BOTRUS_JWT_SECRET='+secrets.token_hex(32)+'\nBOTRUS_SECRETS_KEY='+secrets.token_hex(32)+'\nBORTUS_DISABLE_PROVISIONING=true\nKUBECONFIG=/data/review-kube.json\nHOME=/home/shell\nBORTUS_SECRET_NAMESPACES=default,bortus-secrets\nBORTUS_HISTORY_NAMESPACE=bortus-history\nBORTUS_KV_GUARDED_ADOPTION=true\n');env.chmod(0o600)
 try:
  create=['docker','create','--name',container_name,'--label','io.branconet.owner=bortus-empty-list-fix-review','--restart=no','--read-only','--cpus=2','--memory=1g','--memory-swap=1g','--pids-limit=256','--cap-drop=ALL','--security-opt=no-new-privileges','--log-opt=max-size=5m','--log-opt=max-file=1','--publish','127.0.0.1:'+port+':4000','--env-file',str(env)]
  for leaf,target in [('data','/data'),('home','/home/shell'),('tmp','/tmp')]:create+=['--mount','type=bind,src='+str(fixture/leaf)+',dst='+target]
  cid=run(*create,tag);(out/(prefix+'local-review.json')).write_text(json.dumps({'container':cid,'image':image['Id'],'state':'created','production_data_used':False}));run('docker','start',cid);run('docker','exec','-d',cid,'node','/data/mock-api.cjs')
 finally:env.unlink()
 deadline=time.monotonic()+90
 while time.monotonic()<deadline:
  try:
   with urllib.request.urlopen('http://127.0.0.1:'+port+'/api/health/ready',timeout=3) as r:
    if r.status==200 and json.load(r)['status']=='ready':break
  except OSError:time.sleep(1)
 else:raise RuntimeError('corrected_empty_namespace_runtime_not_ready')
 native_checks={}
 if args.secured:
  b.need('Version: 0.76.1-bortus.3' in run('docker','exec',cid,'/opt/bortus-scanner/trivy','--version'))
  version=json.loads(run('docker','exec',cid,'/usr/local/bin/kubectl','version','--client=true','-o','json'));b.need(version['clientVersion']['goVersion']=='go1.27.4')
  if args.net_fixed:
   net=json.loads((out/'security-tools/kubectl-net-build-state.json').read_bytes());b.need(run('docker','exec',cid,'sha256sum','/usr/local/bin/kubectl').split()[0]==net['sha256'])
  reply=json.loads(run('docker','exec',cid,'/usr/local/bin/kubectl','--kubeconfig=/data/review-kube.json','get','--raw','/api/v1/namespaces/default/secrets?limit=1'));b.need(reply['kind']=='PartialObjectMetadataList' and reply['items'] is None)
  changes=json.loads((out/'security-tools/libc/patch.json').read_bytes())['changed_existing_paths'];expected={c['path']:c['after']for c in changes if 'after'in c}
  check="const fs=require('fs'),c=require('crypto'),out={};for(const p of JSON.parse(process.argv[1]))out[p]=c.createHash('sha256').update(fs.readFileSync('/'+p)).digest('hex');console.log(JSON.stringify(out));"
  actual=json.loads(run('docker','exec',cid,'node','-e',check,json.dumps(list(expected))));b.need(actual==expected)
  native_checks={'scanner_version_passed':True,'kubectl_patched_go_and_real_tls_passed':True,'signed_libc_files_exact':len(expected),'sqlite_and_node_with_patched_libc_ready':True}
 js="const fs=require('fs'),path=require('path'),crypto=require('crypto'),out={};function visit(p){for(const f of fs.readdirSync(p,{withFileTypes:true})){const q=path.join(p,f.name);if(f.isDirectory())visit(q);else if(/\\.(js|css)$/.test(f.name)&&!['_buildManifest.js','_ssgManifest.js'].includes(f.name))out[q.slice('/app/.next/static/'.length)]=crypto.createHash('sha256').update(fs.readFileSync(q)).digest('hex')}}visit('/app/.next/static');console.log(JSON.stringify(out));"
 old_assets=json.loads(run('docker','exec','bortus-review-12dce115','node','-e',js));new_assets=json.loads(run('docker','exec',cid,'node','-e',js));same=old_assets==new_assets
 receipt={'state':'completed','source':commit,'image':image['Id'],'real_tls_empty_current_and_history_ready':True,'guarded_adoption_enabled_in_synthetic_fixture':True,'base_image_layers_retained':True,'native_runtime_security_patches_applied':args.secured,'native_checks':native_checks,'reviewed_client_assets_byte_identical':same,'old_client_asset_count':len(old_assets),'new_client_asset_count':len(new_assets),'actual_nvda_original_report_preserved':True,'production_data_used':False,'container':cid}
 (out/(prefix+'runtime-qualification.json')).write_text(json.dumps(receipt));print(json.dumps(receipt));b.need(same)
if __name__=='__main__':main()
