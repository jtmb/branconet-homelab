from pathlib import Path
import subprocess,hashlib,json,zipfile,shutil
base=Path(__file__).parent;repo=Path(r'C:\Users\james\.codex\worktrees\bortus-app-recovered\kubernetes migration');commit='4668ceb40c3120c7e4053d94edff31f57b7e1f7f'
out=base/'native-distinct-span-immutable-v2';out.mkdir(exist_ok=False);sha=lambda b:hashlib.sha256(b).hexdigest()
git=lambda *a:subprocess.check_output(['git',*a],cwd=repo)
archive=out/'raw-git.zip';entries=[];tree=[]
for row in git('ls-tree','-r','-z',commit).split(b'\0'):
 if not row:continue
 meta,name=row.split(b'\t',1);mode,kind,blob=meta.decode().split();path=name.decode();assert kind=='blob';tree.append((mode,blob,path))
payload=subprocess.run(['git','cat-file','--batch'],input=('\n'.join(x[1] for x in tree)+'\n').encode(),cwd=repo,capture_output=True,check=True).stdout
at=0
with zipfile.ZipFile(archive,'w',zipfile.ZIP_STORED) as z:
 for mode,blob,path in tree:
  end=payload.index(b'\n',at);oid,kind,size=payload[at:end].decode().split();assert oid==blob and kind=='blob';size=int(size);at=end+1;b=payload[at:at+size];assert payload[at+size:at+size+1]==b'\n';at+=size+1
  assert hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()==blob,path
  zi=zipfile.ZipInfo(path);zi.create_system=3;zi.external_attr=int(mode,8)<<16;z.writestr(zi,b)
  entries.append({'path':path,'mode':mode,'gitBlob':blob,'bytes':len(b),'sha256':sha(b)})
assert at==len(payload)
receipt=json.loads((base/'native-distinct-span-qualified/receipt.json').read_bytes());prefix='docs/implementation-evidence/native-distinct-span/'
with zipfile.ZipFile(archive) as z:
 for c in receipt['copies']:
  b=z.read(prefix+c['copy']);assert sha(b)==c['sha256'] and len(b)==c['bytes'];assert Path(c['original']).read_bytes()==b
scan=base/'native-distinct-span-raw-git';sr=json.loads((scan/'receipt.json').read_bytes());assert sr['actualExitCode']==0 and sr['findings']==0 and sr['rawProductionFiles']==265
dest=repo/prefix/'raw-source-scan';dest.mkdir(exist_ok=False)
copies=[]
for p in [scan/'receipt.json',scan/'scan.json',scan/'scan.stdout',scan/'scan.stderr',base/'scan-distinct-span-raw-source.py',base/'run-scan-distinct-span-raw-source.py',base/'package-distinct-span-immutable.py',base/'native-distinct-span-immutable/attempt1-failure.json',Path(__file__)]:
 b=p.read_bytes();d=dest/p.name;d.write_bytes(b);copies.append({'original':str(p),'copy':d.name,'bytes':len(b),'sha256':sha(b)})
record={'commit':commit,'archive':str(archive),'archiveSHA256':sha(archive.read_bytes()),'rawGitFiles':entries,'verifiedOriginalArtifacts':len(receipt['copies']),'scan':{'exitCode':0,'findings':0,'productionFiles':265,'scannerVersion':sr['scannerVersion'],'receiptSha256':sha((scan/'receipt.json').read_bytes())},'workingSourceBindings':331,'freshCompiledFiles':687,'copies':copies,'scope':'Exact raw Git blobs/modes plus separate exact Windows tested working-byte bindings. Source-only default scanner; no dependency/image/full-history claim. Linux and frozen performance pending.'}
(out/'handoff.json').write_text(json.dumps(record,indent=2)+'\n');(dest/'handoff.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps({'handoff':str(out/'handoff.json'),'rawFiles':len(entries),'artifacts':len(receipt['copies']),'archiveSHA':record['archiveSHA256'],'handoffSHA':sha((out/'handoff.json').read_bytes()),'scanBindingsRelations':{k:sum(x['relation']==k for x in sr['bindings']) for k in set(x['relation'] for x in sr['bindings'])}}))
