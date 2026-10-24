from pathlib import Path
import json,hashlib,re,shutil
b=Path(__file__).parent;repo=Path(r'C:\Users\james\.codex\worktrees\bortus-app-recovered\kubernetes migration');front=repo/'k8s-rewrite/front-end'
owner=b/'fixed-field-quality-v1';retained=b/'fixed-field-qualified';retained.mkdir(exist_ok=False)
dest=repo/'docs/implementation-evidence/fixed-field-qualification';dest.mkdir(exist_ok=False)
sha=lambda raw:hashlib.sha256(raw).hexdigest()
terminal=json.loads((owner/'terminal.json').read_bytes().decode('utf-8-sig'));closed=json.loads((owner/'attached-terminal.json').read_bytes())
assert terminal['terminal'] and terminal['exitCode']==0 and len(terminal['checks'])==6 and all(x['exitCode']==0 for x in terminal['checks'])
assert closed['actualExit']==closed['childExit']==0 and closed['qualityAbsent'] and closed['reaped'] and closed['exitBinding']
log=(owner/'full-cli.txt').read_bytes().decode('utf-8-sig');counts=[int(x) for x in re.findall(r'# tests (\d+)',log)]
assert counts==[56,213,4] and not any(int(x) for x in re.findall(r'# (?:fail|skipped) (\d+)',log))
manifest=json.loads((owner/'source-manifest.json').read_bytes())
for row in manifest['files']:
 raw=(repo/row['path']).read_bytes();assert sha(raw)==row['sha256'];assert (owner/'working-source'/row['path']).read_bytes()==raw
outputs=[]
selected=[front/'.next/BUILD_ID',front/'.next/required-server-files.json',front/'.next/routes-manifest.json',front/'.next/standalone/server.js']
selected += [p for root in [front/'.next/server',front/'.next/static'] for p in root.rglob('*') if p.is_file()]
for p in sorted(selected):
 raw=p.read_bytes();rel=p.relative_to(front);copy=retained/'compiled-output'/rel;copy.parent.mkdir(parents=True,exist_ok=True);copy.write_bytes(raw)
 assert copy.read_bytes()==raw
 outputs.append({'path':rel.as_posix(),'bytes':len(raw),'sha256':sha(raw)})
copies=[]
for p in sorted(owner.iterdir()):
 if not p.is_file():continue
 raw=p.read_bytes();(dest/p.name).write_bytes(raw);(retained/p.name).write_bytes(raw)
 copies.append({'original':str(p),'copy':p.name,'bytes':len(raw),'sha256':sha(raw)})
for p in [Path(__file__),b/'prepare-fixed-field-quality.py',b/'apply-fixed-field-candidate.py',b/'fixed-field-candidate-applied.json']:
 raw=p.read_bytes();target=dest/'scripts'/p.name;target.parent.mkdir(exist_ok=True);target.write_bytes(raw);(retained/p.name).write_bytes(raw)
 copies.append({'original':str(p),'copy':target.relative_to(dest).as_posix(),'bytes':len(raw),'sha256':sha(raw)})
receipt={'sourceBase':'08304d8d8b695f827af347ebcc9b294e4d93fed8','stage':'fixed known schema duplicate guards','qualification':terminal,'closure':closed,'focusedPassed':56,'unitPassed':213,'httpPassed':4,'skipped':0,'workingSourceManifest':manifest,'frozenWorkingSourceRetained':str(owner/'working-source'),'compiledOutputFiles':outputs,'compiledOutputRetained':str(retained/'compiled-output'),'copies':copies,'firstLauncherLimitation':'Launcher46024 vanished before writing owner/terminal metadata; its exit remains unknown. Test process37112 continued normally. Exact PID/start watcher attached while live and bound cached OS actual0 to child terminal0; no test restart occurred. Initial owner read failure692e22 retained by classification.','originalParserMethods':json.loads((b/'fixed-field-candidate-applied.json').read_bytes())['originalMethods'],'performanceAcceptance':False,'scope':'Fresh WindowsNode22.23.3 build/focused/full/lint/types/fourHTTP only. Linux/frozen endpoint performance/image/live/actualAT remain open.'}
(dest/'.gitattributes').write_bytes(b'* -text\n');(dest/'qualification.json').write_bytes((json.dumps(receipt,indent=2)+'\n').encode());(retained/'receipt.json').write_bytes((dest/'qualification.json').read_bytes())
note='The narrow known-schema duplicate-guard candidate passed56 focused security/native tests,213 full units, a fresh production build, zero-warning lint, types and all four strict production HTTP suites on Windows Node22.23.3, no skips. All332 frozen working inputs and687 selected compiled output files are retained with exact hashes; both original Reader methods and capture/decode semantics remain exact. The first supervising launcher vanished before ownership metadata (exit unknown), but the exact still-live test PID/start was attached without restarting tests; cached OS exit0 matches the child durable terminal0 and owned process/child absence was verified. [Functional source/artifact qualification](implementation-evidence/fixed-field-qualification/qualification.json) retains that limitation, all original logs/scripts and full inputs. This does not establish Linux functional or A07/A21 endpoint performance; no new paired run or live rollout occurred. The mixed-tail public allocation diagnostic remains separate.'
review=[]
for p in sorted((repo/'docs').rglob('*.md')):
 raw=p.read_bytes();text=raw.decode('utf-8-sig');update=(p.parent==repo/'docs' and p.name in {'API-USAGE.md','SECRETS-ENGINE.md','BORTUS-DEPLOYMENT.md','TECH-STACK.md','BORTUS-IMPLEMENTATION.md','BORTUS-NATIVE-LIST-PERFORMANCE.md','BORTUS-CONTROLLED-PERFORMANCE.md'}) or p==repo/'docs/implementation-evidence/README.md'
 review.append({'path':p.relative_to(repo).as_posix(),'beforeSHA256':sha(raw),'updated':update})
 if update:
  eol='\r\n' if b'\r\n' in raw else '\n';text=text.replace('Fresh functional qualification of this draft remains pending; no paired comparison or image/live acceptance is claimed.','This candidate has passed the scoped fresh Windows functional qualification recorded below; Linux and endpoint performance remain separate, and no paired comparison or image/live acceptance is claimed.')
  p.write_bytes((text+eol+eol+note.replace('687 selected',str(len(outputs))+' selected')+eol).encode())
(dest/'doc-review.json').write_bytes((json.dumps(review,indent=2)+'\n').encode())
print(json.dumps({'receiptSHA256':sha((dest/'qualification.json').read_bytes()),'outputs':len(outputs),'frozenSources':len(manifest['files']),'artifacts':len(copies),'protected':str(retained)}))
