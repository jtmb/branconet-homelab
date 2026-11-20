"""Keep only lossless source edits/module manifests before retiring generated tool trees."""
import hashlib,importlib.util,io,json,os,tarfile
from pathlib import Path
S=Path(__file__).parent;s=importlib.util.spec_from_file_location('tool_delta_inputs',S/'prepare-bortus-runtime-security.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
def main():
 root=m.OUT;target=root.parent/'runtime-tool-source-deltas.tar';m.need(not target.exists());expected=json.loads((m.OLD/'source-inputs.json').read_bytes());entries=[];total=0
 with tarfile.open(target,'x')as out:
  def add(path,name):
   nonlocal total
   raw=path.read_bytes();total+=len(raw);m.need(total<16*1024**2);i=tarfile.TarInfo(name);i.size=len(raw);i.mode=path.stat().st_mode&0o777;out.addfile(i,io.BytesIO(raw));entries.append({'path':name,'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw)})
  base=root/'kubectl-source'
  for current,dirs,files in os.walk(base,followlinks=False):
   relative=Path(current).relative_to(base)
   if relative.parts and relative.parts[0]in('vendor','LICENSES','_output'):dirs[:]=[];continue
   for name in files:
    path=Path(current)/name;n=str(path.relative_to(base))
    if path.is_symlink():
     m.need(expected.get(n,{}).get('link')==os.readlink(path));continue
    prior=expected.get(n)
    if prior is None or m.sha(path)!=prior.get('sha256'):add(path,'kubectl/'+n)
  # The vendor graph is reproducible from the exact retained lockfiles and scripts.
  add(base/'vendor/modules.txt','kubectl/vendor/modules.txt')
  original={}
  with tarfile.open(root/'trivy-source.tar.gz')as archive:
   members=archive.getmembers();prefix=members[0].name.rstrip('/')+'/'
   for item in members:
    if item.isfile():original[item.name[len(prefix):]]=hashlib.sha256(archive.extractfile(item).read()).hexdigest()
  base=root/'trivy-source'
  for path in base.rglob('*'):
   if path.is_file()and not path.is_symlink():
    n=str(path.relative_to(base))
    if m.sha(path)!=original.get(n):add(path,'trivy/'+n)
 record={'state':'preserved','archive':str(target),'sha256':m.sha(target),'bytes':target.stat().st_size,'entries':entries,'protected_original_capsules':[str(m.CAP),str(m.OLD)],'kubectl_baseline':'Verified original/diff capsules and source-inputs.json; apply kubectl delta, then retained hack/update-vendor.sh with Go1.27.4','trivy_baseline':'All Git blobs of e713f67f7d54decdcd9b3132c9751833dcced698 verified by trivy-source-verification.json; apply trivy delta','recipes':['build-bortus-runtime-security-tools.py','repair-bortus-kubectl-net.py'],'compiler':'Official go1.27.4.linux-amd64.tar.gz SHA256 7226736c2339719cda28fbf3a54d71aa63bcefe376e98cef00034268dab24840','runtime_payload_consumer':'Exact binaries already in verified private image e7539b9 on all nodes; generated tool/compiler/source trees have no remaining active consumer'}
 (root.parent/'runtime-tool-source-deltas.json').write_text(json.dumps(record));print(json.dumps({'source_deltas_preserved':True,'files':len(entries),'bytes':target.stat().st_size,'sha256':record['sha256']}))
if __name__=='__main__':main()
