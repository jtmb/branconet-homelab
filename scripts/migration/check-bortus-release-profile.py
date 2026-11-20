"""Render and server-dry-run only the prepared BORTUS release; no deployment."""
import argparse,hashlib,json,os,subprocess
from pathlib import Path
import yaml
ROOT=Path('/mnt/c/Users/james/AppData/Local/BORTUS/repos/branconet-charts')
A=Path('/mnt/h/AgentArtifacts/projects/branconet/builds/wsl-artifact-store/files/bortus-operator-recovery')
T=Path('/home/brajam/.local/share/branconet-migration')
image='docker.io/jtmb92/bortus@sha256:ac261f9cc146171469dd9bd660acae39ae9563656a9a873e0fa251d4b2fda58b'
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--explain-errors',action='store_true');args=parser.parse_args()
hr=yaml.safe_load((ROOT/'flux/releases/bortus.yaml').read_text());values=hr['spec']['values']
assert hr['spec']['suspend'] is True and values['nativeKv']['guardedAdoption'] is False and values['image']==image
result=subprocess.run([str(T/'bin/helm'),'template','bortus',str(ROOT/'charts/bortus'),'-n','bortus','--values','-'],input=yaml.safe_dump(values).encode(),capture_output=True,timeout=30)
assert result.returncode==0
objects=[v for v in yaml.safe_load_all(result.stdout) if v]
d=next(v for v in objects if v['kind']=='Deployment' and v['metadata']['name']=='bortus')
assert d['spec']['strategy']['type']=='Recreate'
pod=d['spec']['template']['spec'];assert pod['serviceAccountName']=='bortus-kv'
app=next(c for c in pod['containers'] if c['name']=='bortus');env={v['name']:v for v in app['env']}
assert app['image']==image and app['imagePullPolicy']=='Never' and env['BORTUS_KV_GUARDED_ADOPTION']['value']=='false'
assert any(v.get('persistentVolumeClaim',{}).get('claimName')=='bortus-data' for v in pod['volumes'])
check=subprocess.run([str(T/'bin/kubectl'),'--kubeconfig',str(T/'admin.conf'),'--request-timeout=30s','apply','--dry-run=server','-f','-','-o','name'],input=result.stdout,capture_output=True,timeout=60)
receipt={'state':'passed' if check.returncode==0 else 'failed','render_sha256':hashlib.sha256(result.stdout).hexdigest(),'objects':len(objects),'server_dry_run_exit':check.returncode,'recreate':True,'original_claim_retained':True,'adoption':False,'suspended':True,'production_changed':False}
if check.returncode:receipt['failure_output']='\n'.join(line for line in check.stderr.decode(errors='replace').splitlines() if not line.startswith('Warning:'))[-8192:]
out=A/('prepared-release-server-dry-run-details.json' if args.explain_errors else 'prepared-release-server-dry-run.json');fd=os.open(out,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
with os.fdopen(fd,'w') as f:json.dump(receipt,f);f.flush();os.fsync(f.fileno())
print(json.dumps({k:v for k,v in receipt.items() if k!='failure_output' or args.explain_errors}))
raise SystemExit(0 if check.returncode==0 else 1)
