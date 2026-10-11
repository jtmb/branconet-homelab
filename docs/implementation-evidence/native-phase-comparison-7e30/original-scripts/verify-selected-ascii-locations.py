from pathlib import Path
import hashlib,json,subprocess
base=Path(__file__).parent
repo=Path(r'C:\Users\james\.codex\worktrees\bortus-app-recovered\kubernetes migration')
qualified=base/'native-summary-selected-ascii-qualified'
receipt=json.loads((qualified/'receipt.json').read_bytes())
sha=lambda b:hashlib.sha256(b).hexdigest()
artifact=[]
for row in receipt['copies']:
 original=Path(row['original']);copy=repo/'docs/implementation-evidence/native-summary-selected-ascii'/row['copy']
 for p in [original,copy]:
  b=p.read_bytes();assert len(b)==row['bytes'] and sha(b)==row['sha256'],str(p)
 gitpath=copy.relative_to(repo).as_posix()
 raw=subprocess.check_output(['git','show','7e30b9b428a66cd3f5e618cec5e694d5f03302ac:'+gitpath],cwd=repo)
 assert sha(raw)==row['sha256'] and len(raw)==row['bytes']
 artifact.append({'copy':row['copy'],'original':str(original),'committedPath':gitpath,'sha256':row['sha256'],'bytes':row['bytes']})
for row in receipt['workingSourceManifest']['files']:
 b=(qualified/'working-source'/row['path']).read_bytes();assert sha(b)==row['sha256'] and len(b)==row['bytes']
for row in receipt['compiledOutputFiles']:
 b=(qualified/'compiled-output'/row['path']).read_bytes();assert sha(b)==row['sha256'] and len(b)==row['bytes']
result={'receiptSHA256':sha((qualified/'receipt.json').read_bytes()),'sourceCommit':'7e30b9b428a66cd3f5e618cec5e694d5f03302ac','copiesBase':str(repo/'docs/implementation-evidence/native-summary-selected-ascii'),'workingSourceBase':str(qualified/'working-source'),'compiledOutputBase':str(qualified/'compiled-output'),'verifiedCopies':len(artifact),'verifiedWorkingFiles':len(receipt['workingSourceManifest']['files']),'verifiedCompiledFiles':len(receipt['compiledOutputFiles']),'artifacts':artifact,'scope':'Locator proof only; original qualification receipt and artifacts unchanged. Each copy also verified against exact committed raw Git bytes.'}
out=base/'selected-ascii-qualified-location-proof.json';assert not out.exists();out.write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({'path':str(out),'sha256':sha(out.read_bytes()),'copies':len(artifact),'working':result['verifiedWorkingFiles'],'compiled':result['verifiedCompiledFiles']}))
