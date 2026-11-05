from pathlib import Path
import hashlib,json,shutil,zipfile,re
base=Path(__file__).parent;repo=Path(r'C:\Users\james\.codex\worktrees\bortus-app-recovered\kubernetes migration');app=repo/'k8s-rewrite/front-end'
qa=base/'native-distinct-span-quality-v1';out=base/'native-distinct-span-qualified';out.mkdir(exist_ok=False)
dest=repo/'docs/implementation-evidence/native-distinct-span';dest.mkdir(exist_ok=False)
sha=lambda b:hashlib.sha256(b).hexdigest()
terminal=json.loads((qa/'terminal.json').read_text(encoding='utf-8-sig'));assert terminal['terminal'] and terminal['exitCode']==0 and len(terminal['checks'])==6 and all(x['exitCode']==0 for x in terminal['checks'])
freeze=json.loads((qa/'source-manifest.json').read_bytes())
for f in freeze['files']:
 b=(repo/f['path']).read_bytes();assert sha(b)==f['sha256'] and len(b)==f['bytes'],f['path']
shutil.copytree(qa/'working-source',out/'working-source')
build=[];paths=list((app/'.next/server').rglob('*'))+list((app/'.next/static').rglob('*'))+[app/'.next/BUILD_ID',app/'.next/standalone/server.js',app/'.next/routes-manifest.json',app/'.next/required-server-files.json']
for p in sorted(set(p for p in paths if p.is_file())):
 b=p.read_bytes();rel=p.relative_to(app);d=out/'compiled-output'/rel;d.parent.mkdir(parents=True,exist_ok=True);d.write_bytes(b);build.append({'path':rel.as_posix(),'bytes':len(b),'sha256':sha(b)})
copies=[]
folders=[(base/'native-distinct-span-preparation','preparation'),(qa,'quality')]+[(base/f'parser-native-span-7e30-20261011-v{i}',f'diagnostic-v{i}') for i in range(1,5)]
for folder,label in folders:
 for p in sorted(folder.rglob('*')):
  if not p.is_file() or 'working-source' in p.parts:continue
  b=p.read_bytes();rel=Path(label)/p.relative_to(folder);d=dest/rel;d.parent.mkdir(parents=True,exist_ok=True);d.write_bytes(b);copies.append({'original':str(p),'copy':rel.as_posix(),'bytes':len(b),'sha256':sha(b)})
for p in [Path(__file__),base/'implement-distinct-span.py',base/'prepare-distinct-span-qa.py',base/'review-1k-native-gap.py']:
 b=p.read_bytes();d=dest/'scripts'/p.name;d.parent.mkdir(parents=True,exist_ok=True);d.write_bytes(b);copies.append({'original':str(p),'copy':d.relative_to(dest).as_posix(),'bytes':len(b),'sha256':sha(b)})
reader=(app/'src/lib/secret-summary-json.ts').read_bytes();prefix=(app/'src/lib/secret-client.ts').read_bytes()
methods=[reader[reader.index(b'  string(): boolean {'):reader.index(b'  private longString(): boolean {')],prefix[prefix.index(b'  const string = (): number => {'):prefix.index(b'  const longString = (): number => {')]]
assert [sha(x) for x in methods]==['067e12160604549fc94fde2c3579a9a26c3f2697d4ab3d05907e5a9bc2adb4a6','3dbd92deab8549e873b2c82a3995a29c49d60ad3e4a2d33c8fb0f531de353c74']
cli=(qa/'full-cli.txt').read_text(encoding='utf-8-sig');counts=[int(x) for x in re.findall(r'^# tests (\d+)',cli,re.M)];assert counts==[54,211,4],counts
receipt={'sourceBase':'7524a9633eecea6a11d73b763451030e07ea7af4','workingSourceManifest':freeze,'compiledOutputFiles':build,'compiledOutputRetained':str(out/'compiled-output'),'qualification':terminal,'focusedPassed':54,'unitPassed':211,'httpPassed':4,'skipped':0,'originalStringMethodsPreserved':True,'originalStringHashes':[sha(x) for x in methods],'copies':copies,'scope':'Windows fresh build/full functional proof; isolated one-CPU diagnostics retained without timing trimming. No new Linux/paired/performance/image/live acceptance. Historical provenance findings remain open.','performanceAcceptance':False}
(dest/'.gitattributes').write_text('* -text\n')
(dest/'qualification.json').write_text(json.dumps(receipt,indent=2)+'\n');(out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
note='The distinct-value scanner passed54 focused and211 full unit tests, a fresh production build, zero-warning lint, types and all four strict production HTTP suites on Windows Node22.23.3, no skips. The normal launcher terminal,331 exact frozen working inputs and fresh compiled outputs are retained in [distinct scanner qualification](implementation-evidence/native-distinct-span/qualification.json). Both original string methods remain byte-for-byte unchanged. All earlier diagnostic attempts, including the original setup failure and rejected broader/threshold variants with untrimmed timings, are retained. A07/A21 remain failed/open on the preceding frozen candidate; this local functional pass does not establish endpoint latency, Linux, image or live acceptance.'
review=[]
affected=['API-USAGE.md','SECRETS-ENGINE.md','BORTUS-DEPLOYMENT.md','TECH-STACK.md','BORTUS-NATIVE-LIST-PERFORMANCE.md','BORTUS-CONTROLLED-PERFORMANCE.md','BORTUS-IMPLEMENTATION.md']
for doc in sorted((repo/'docs').rglob('*.md')):
 b=doc.read_bytes();text=b.decode('utf-8-sig');updated=doc.parent==repo/'docs' and doc.name in affected
 review.append({'path':doc.relative_to(repo).as_posix(),'sha256Before':sha(b),'updated':updated})
 if updated:
  old='Fresh functional qualification and the unchanged frozen performance comparison are pending for this source.'
  assert text.count(old)==1,doc
  text=text.replace(old,'Windows functional qualification passed as recorded below; Linux qualification and the unchanged frozen performance comparison remain pending for this source.')
  # Preserve the existing raw working line endings rather than rewriting old evidence prose.
  eol='\r\n' if b'\r\n' in b else '\n';doc.write_bytes(text.encode()+ (eol+note+eol).encode())
evidence=repo/'docs/implementation-evidence/README.md';b=evidence.read_bytes();eol='\r\n' if b'\r\n' in b else '\n';text=b.decode('utf-8-sig').replace('Fresh functional qualification and the unchanged frozen performance comparison are pending for this source.','Windows functional qualification passed; Linux and frozen performance remain pending.');evidence.write_bytes(text.encode()+(eol+note.replace('implementation-evidence/native-distinct-span/','native-distinct-span/')+eol).encode())
(dest/'doc-review.json').write_text(json.dumps(review,indent=2)+'\n')
print(json.dumps({'receipt':str(out/'receipt.json'),'copies':len(copies),'workingSources':len(freeze['files']),'compiledFiles':len(build),'receiptSHA':sha((out/'receipt.json').read_bytes())}))
