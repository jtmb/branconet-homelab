from pathlib import Path
import json,hashlib,subprocess
base=Path(__file__).parent;repo=Path(r'C:\Users\james\.codex\worktrees\bortus-app-recovered\kubernetes migration')
affected=['API-USAGE.md','SECRETS-ENGINE.md','BORTUS-DEPLOYMENT.md','TECH-STACK.md','BORTUS-NATIVE-LIST-PERFORMANCE.md','BORTUS-IMPLEMENTATION.md']
paragraph='''The next summary-only candidate reuses the existing complete string byte grammar to identify selected, unescaped ASCII strings that begin and end in one chunk. Only those selected key/header/type strings use Buffer ASCII decoding directly after full validation, avoiding selected-piece and JSON decoder allocations. Escaped, multibyte and cross-chunk strings retain the document-owned fatal UTF-8/JSON fallback; complete metadata objects and booleans retain their existing parsing. Native data/stringData/unknown values remain validated without capture/materialization. Transport, fresh authentication, budgets, concurrency, charging and frozen gates are unchanged. Differential selected-byte/chunk/escape/Unicode/prototype/header and value-nonmaterialization tests, bounded identical-input characterization and full functional/build/HTTP qualification are pending. Exact8f1a remains performance failed; no parser timing or final-image acceptance is inferred.'''
review=[]
for doc in sorted((repo/'docs').rglob('*.md')):
 text=doc.read_text(encoding='utf-8');changed=doc.parent==repo/'docs' and doc.name in affected
 review.append({'path':doc.relative_to(repo).as_posix(),'sha256Before':hashlib.sha256(doc.read_bytes()).hexdigest(),'updated':changed})
 if changed:doc.write_text(text.rstrip()+'\n\n'+paragraph+'\n',encoding='utf-8',newline='')
out=base/'summary-selected-ascii-preparation';out.mkdir(exist_ok=False)
(out/'doc-review.json').write_text(json.dumps(review,indent=2)+'\n')
for name in ['src/lib/secret-summary-json.ts','tests/native-summary-json.test.ts']:
 p=repo/'k8s-rewrite/front-end'/name;d=out/'draft-source'/name;d.parent.mkdir(parents=True,exist_ok=True);d.write_bytes(p.read_bytes())
node=Path(r'C:\Users\james\AppData\Local\Temp\bortus-node22-3f6ebe6f1fca4cb092a488a5d635fb66\node-v22.23.3-win-x64\node.exe')
command=[str(node),str(repo/'k8s-rewrite/front-end/node_modules/tsx/dist/cli.mjs'),'--test','tests/native-summary-json.test.ts']
r=subprocess.run(command,cwd=repo/'k8s-rewrite/front-end',capture_output=True,timeout=30)
(out/'focused.stdout').write_bytes(r.stdout);(out/'focused.stderr').write_bytes(r.stderr);(out/'focused-terminal.json').write_text(json.dumps({'actualExit':r.returncode,'command':command,'retainedDraftSources':True},indent=2)+'\n')
print(r.stdout.decode(errors='replace'));print(r.stderr.decode(errors='replace'));raise SystemExit(r.returncode)
