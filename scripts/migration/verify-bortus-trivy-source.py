"""Verify the differently named GitHub tarball against every blob of the pinned commit."""
import hashlib,importlib.util,json,tarfile,urllib.request
from pathlib import Path
s=importlib.util.spec_from_file_location('verified_tool_source',Path(__file__).with_name('prepare-bortus-runtime-security.py'));m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
COMMIT='e713f67f7d54decdcd9b3132c9751833dcced698'
def document(path):
 with urllib.request.urlopen(urllib.request.Request('https://api.github.com/repos/aquasecurity/trivy/'+path,headers={'User-Agent':'BORTUS-security-build','Accept':'application/vnd.github+json'}),timeout=30) as f:return json.loads(f.read(32*1024**2))
def main():
 out=m.OUT;archive=out/'trivy-source.tar.gz';target=out/'trivy-source';m.need(archive.is_file() and not target.exists())
 commit=document('git/commits/'+COMMIT);m.need(commit['sha']==COMMIT);tree=document('git/trees/'+commit['tree']['sha']+'?recursive=1');m.need(tree.get('truncated') is False and tree['sha']==commit['tree']['sha']);expected={x['path']:x for x in tree['tree'] if x['type']=='blob'};seen=set()
 with tarfile.open(archive) as t:
  members=t.getmembers();prefix=members[0].name.rstrip('/')+'/'
  for member in members:
   if member.isdir():continue
   m.need(member.name.startswith(prefix) and (member.isfile() or member.issym()));name=member.name[len(prefix):];m.need(name in expected and name not in seen and '..' not in Path(name).parts)
   data=t.extractfile(member).read() if member.isfile() else member.linkname.encode();m.need(hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()==expected[name]['sha']);seen.add(name)
  m.need(seen==set(expected));target.mkdir(mode=0o700)
  for member in members:
   if member.name.rstrip('/')==prefix.rstrip('/'):continue
   member.name=member.name[len(prefix):];t.extract(member,target,filter='data')
 receipt={'source_commit':COMMIT,'git_tree':tree['sha'],'all_git_blobs_verified':True,'files':len(seen),'archive_sha256':m.sha(archive),'historical_archive_sha256':'5bcd06d8bdae338978b8ef597cb23cd0ff2e710d1ea9097c1143ec6b07d362d6','archive_format_difference_preserved':True,'verification':'Every regular/symlink blob equals the pinned upstream Git tree; no hash requirement silently replaced'}
 (out/'trivy-source-verification.json').write_text(json.dumps(receipt));ownership=json.loads((out/'ownership.json').read_bytes());ownership.update(state='prepared',trivy=receipt,kubectl_source_files=31268);(out/'ownership.json').write_text(json.dumps(ownership));print(json.dumps(receipt))
if __name__=='__main__':main()
