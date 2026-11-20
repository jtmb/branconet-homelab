"""Prepare source-bound runtime security tools inside the existing H task root."""
import hashlib,json,os,subprocess,tarfile,urllib.request,zipfile
from pathlib import Path
OUT=Path('/mnt/h/AgentArtifacts/projects/branconet/builds/wsl-artifact-store/files/bortus-operator-recovery/empty-list-fix/security-tools')
OLD=Path('/home/brajam/.local/share/branconet-migration/next-security-01a1740e/a19-secret-capacity-01a1797a/kubectl-remediation')
CAP=Path('/home/brajam/.local/share/branconet-migration/root-custom-kubectl-review-20261012-53c90b1e408a/originals')
def need(v):
 if not v:raise RuntimeError('runtime_security_input_verification_failed')
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def download(url,p,expected=None,maximum=512*1024**2,algorithm='sha256'):
 need(algorithm in ('sha256','sha512'));h=hashlib.new(algorithm);n=0
 with urllib.request.urlopen(url,timeout=90) as source,p.open('xb') as target:
  for block in iter(lambda:source.read(1024**2),b''):n+=len(block);need(n<=maximum);h.update(block);target.write(block)
 digest=h.hexdigest();need(expected is None or digest==expected);return {'url':url,algorithm:digest,'bytes':n}
def main():
 need(os.geteuid()==0 and not OUT.exists());OUT.mkdir(mode=0o700)
 record={'owner':'01a18518-24e7-7ce3-b620-f9ca775bfd1c','purpose':'Repair observed libc/Go/Otel runtime findings before BORTUS publication','root':str(OUT),'protected_inputs':[str(OLD),str(CAP)],'generated_paths':['go','kubectl-source','trivy-source','cache','tmp','home','bin'],'end_condition':'Remove compiler/source/cache bulk after qualified binaries enter the verified production image','state':'preparing'}
 (OUT/'ownership.json').write_text(json.dumps(record))
 for n in ('cache','tmp','home','bin'):(OUT/n).mkdir(mode=0o700)
 releases=json.load(urllib.request.urlopen('https://go.dev/dl/?mode=json',timeout=30));release=next(r for r in releases if r['version']=='go1.27.4');file=next(f for f in release['files'] if f['os']=='linux' and f['arch']=='amd64' and f['kind']=='archive')
 go_archive=OUT/file['filename'];record['go']=download('https://go.dev/dl/'+file['filename'],go_archive,file['sha256']);need(go_archive.stat().st_size==file['size'])
 with tarfile.open(go_archive) as t:t.extractall(OUT,filter='data')
 need((OUT/'go/VERSION').read_text().splitlines()[0]=='go1.27.4')
 # Rehydrate the exact previously qualified kubectl source, never edit the capsule.
 grounding=json.loads((OLD/'old-binary-source-grounding.json').read_bytes())['inputs']
 for n in ('source-original.zip','source-diff.zip','source-diff-metadata.json'):need(sha(CAP/n)==grounding[n]['sha256'])
 expected=json.loads((OLD/'source-inputs.json').read_bytes());meta=json.loads((CAP/'source-diff-metadata.json').read_bytes());target=OUT/'kubectl-source';target.mkdir(mode=0o700);links=[]
 with zipfile.ZipFile(CAP/'source-original.zip') as original,zipfile.ZipFile(CAP/'source-diff.zip') as diff:
  for n,r in expected.items():
   need(not Path(n).is_absolute() and '..' not in Path(n).parts);p=target/n;p.parent.mkdir(parents=True,exist_ok=True)
   if 'link' in r:links.append((p,r['link']));continue
   data=diff.read('after/'+n) if meta['entries'].get(n,{}).get('after') else original.read(n);need(hashlib.sha256(data).hexdigest()==r['sha256']);p.write_bytes(data);p.chmod(r['mode'])
 for path,link in links:need((path.parent/link).resolve().is_relative_to(target));os.symlink(link,path)
 record['kubectl_source_files']=len(expected)
 archive=OUT/'trivy-source.tar.gz';record['trivy']=download('https://api.github.com/repos/aquasecurity/trivy/tarball/e713f67f7d54decdcd9b3132c9751833dcced698',archive,'5bcd06d8bdae338978b8ef597cb23cd0ff2e710d1ea9097c1143ec6b07d362d6')
 destination=OUT/'trivy-source';destination.mkdir(mode=0o700)
 with tarfile.open(archive) as t:
  members=t.getmembers();prefix=members[0].name.rstrip('/')+'/'
  for member in members:
   if member.name.rstrip('/')==prefix.rstrip('/'):continue
   need(member.name.startswith(prefix));member.name=member.name[len(prefix):];t.extract(member,destination,filter='data')
 record['state']='prepared';(OUT/'ownership.json').write_text(json.dumps(record));print(json.dumps({'security_inputs_prepared':True,'root':str(OUT),'go':'go1.27.4','kubectl_files':len(expected)}))
if __name__=='__main__':main()
