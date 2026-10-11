from pathlib import Path
import hashlib,json
base=Path(__file__).parent;repo=Path(r'C:\Users\james\.codex\worktrees\bortus-app-recovered\kubernetes migration')
affected=['API-USAGE.md','SECRETS-ENGINE.md','BORTUS-DEPLOYMENT.md','TECH-STACK.md','BORTUS-NATIVE-LIST-PERFORMANCE.md','BORTUS-IMPLEMENTATION.md'];review=[]
note='Selected-ASCII full QA attempt1 stopped before build with50/51 focused tests passing. The existing parse-time deadline test advanced its synthetic clock only through TextDecoder, which the verified ASCII path bypasses. Exact314 first-attempt sources/logs are retained before correction. The test now explicitly observes selected-ASCII materialization and complete metadata decoding in separate cases, requires an actual clock advance and preserves fixed503 timeout/no visit/no accepted items/no retry/exact charged bytes. Production deadline and transport code is unchanged; corrected full qualification remains pending.'
for doc in sorted((repo/'docs').rglob('*.md')):
 text=doc.read_text(encoding='utf-8');changed=doc.parent==repo/'docs' and doc.name in affected;review.append({'path':doc.relative_to(repo).as_posix(),'sha256Before':hashlib.sha256(doc.read_bytes()).hexdigest(),'updated':changed})
 if changed:doc.write_text(text.rstrip()+'\n\n'+note+'\n',encoding='utf-8',newline='')
(base/'summary-selected-ascii-preparation/doc-review-v2.json').write_text(json.dumps(review,indent=2)+'\n')
prior=json.loads((base/'native-summary-decoder-prequalification-source.json').read_bytes());files=[]
for f in prior['files']:
 b=(repo/f['path']).read_bytes();files.append({'path':f['path'],'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()})
changed=[f['path'] for old,f in zip(prior['files'],files) if old['sha256']!=f['sha256']]
assert len(changed)==3,changed
(base/'native-summary-selected-ascii-v2-prequalification-source.json').write_text(json.dumps({'base':'0554aaa74a9ecad806aa156d2cbbe1a4770c953e','files':files,'changedSinceDecoderQA':changed,'scope':'selected unescaped ASCII same-chunk only plus differential/privacy/deadline observer tests; all other production inputs unchanged'},indent=2)+'\n')
s=(base/'native-summary-selected-ascii-quality.ps1').read_text().replace('native-summary-selected-ascii-quality','native-summary-selected-ascii-v2-quality')
(base/'native-summary-selected-ascii-v2-quality.ps1').write_text(s,encoding='utf-8')
print(json.dumps({'frozen':len(files),'changes':changed}))
