from pathlib import Path
import hashlib,json,zipfile
base=Path(__file__).parent
repo=Path(r'C:\Users\james\.codex\worktrees\bortus-app-recovered\kubernetes migration')
dest=repo/'docs/implementation-evidence/native-phase-comparison-7e30'
assert not dest.exists();dest.mkdir()
sha=lambda b:hashlib.sha256(b).hexdigest()
copies=[];analyses={};terminals={}
for label,folder,analysisname in [('candidate','characterize-phase-7e30b9b-complete','analysis-v2.json'),('baseline','characterize-phase-baseline-51e8-complete','analysis.json')]:
 src=base/folder;manifest=json.loads((src/'manifest.json').read_bytes())
 assert sha((src/'originals.zip').read_bytes())==manifest['archiveSHA256']
 with zipfile.ZipFile(src/'originals.zip') as z:
  assert sorted(z.namelist())==sorted(x['path'] for x in manifest['originals'])
  for row in manifest['originals']:
   b=(src/row['path']).read_bytes();assert z.read(row['path'])==b and sha(b)==row['sha256'] and len(b)==row['bytes']
   out=dest/label/row['path'];out.parent.mkdir(parents=True,exist_ok=True);out.write_bytes(b)
   copies.append({'original':str(src/row['path']),'copy':out.relative_to(dest).as_posix(),'bytes':len(b),'sha256':sha(b)})
 for name in ['manifest.json',analysisname]+(['analysis.json'] if label=='candidate' else []):
  b=(src/name).read_bytes();out=dest/label/name;out.write_bytes(b)
  copies.append({'original':str(src/name),'copy':out.relative_to(dest).as_posix(),'bytes':len(b),'sha256':sha(b)})
 analyses[label]=json.loads((src/analysisname).read_bytes());t=json.loads((src/'terminal.json').read_bytes());terminals[label]=t
 assert t['actualExit']==0 and t['terminal'] and t['ownedLiveContainers']==[] and all(t[k] for k in ['sourceUnchanged','compiledBuildUnchanged','frozenDriverUnchanged'])
 assert len(analyses[label]['rows'])==6
for name in ['child-shim.cjs','request-profiler.cjs']:
 assert (dest/'candidate'/name).read_bytes()==(dest/'baseline'/name).read_bytes()
metrics=['nativeWindowMs','preFirstNativeRequestCombinedMs','firstNativeStartToLastNativeEndCombinedMs','postLastNativeEndToResponseEndCombinedMs','nativeRequestCount','tlsConnectionCount','fixtureStringifySumMs','fixtureRequestToResponseEndCombinedMedianMs','dataHandlerSynchronousSumMs','endEventHandlerSynchronousSumMs']
rows=[]
for b,c in zip(analyses['baseline']['rows'],analyses['candidate']['rows']):
 assert b['fixture']==c['fixture'];rows.append({'fixture':b['fixture'],'baseline':{k:b[k] for k in metrics},'candidate':{k:c[k] for k in metrics}})
scripts=['prepare-phase-observer-7e30.py','dispatch-phase-observer-7e30.py','preserve-analyze-phase-7e30.py','qualify-phase-analysis-v2.py','dispatch-baseline-phase-observer.py','analyze-baseline-phase.py','preserve-analyze-baseline-phase.py','verify-selected-ascii-locations.py','selected-ascii-qualified-location-proof.json']
for name in scripts:
 b=(base/name).read_bytes();out=dest/'original-scripts'/name;out.parent.mkdir(exist_ok=True);out.write_bytes(b);copies.append({'original':str(base/name),'copy':out.relative_to(dest).as_posix(),'bytes':len(b),'sha256':sha(b)})
limitations=['Diagnostic only: one instrumented observation per source, not an unchanged three-pair performance acceptance run.','Identical external Inspector/SDK/TLS/JSON/fixture hooks add CPU and scheduling overhead.','Concurrent durations overlap; end handlers include parsing, listener, cleanup and observer work. Baseline full JSON processing occurs outside end callbacks, so these callback sums are not equivalent parser partitions.','Presence or absence of end events does not establish accepted/rejected response status. Original candidate analysis inferred these labels; it remains retained, and corrected analysis-v2 uses neutral event names only.','Baseline SDK hook count zero means the older auth path was not observed by that hook, not that authentication was absent.','Fixture request-to-end includes unchanged12ms timer, generation and scheduling. Fixture stringify is separately timed numeric work.','No arguments, options, values, bodies, keys, URLs, headers or dynamic error locals retained.','No source, build, frozen driver, resource limit, inventory assertion or acceptance gate changed. Performance remains failed.']
receipt={'nonAcceptance':True,'candidate':'7e30b9b428a66cd3f5e618cec5e694d5f03302ac','baseline':'51e8cd66379c1f40a95ea02f4da7c8aed848f2a4','originalArtifactCount':40,'copies':copies,'rows':rows,'terminalProof':{k:{p:t[p] for p in ['pid','childPID','actualExit','terminalAtUTC','ownedLiveContainers','sourceUnchanged','compiledBuildUnchanged','frozenDriverUnchanged','compiledBuildManifestSHA256','compiledBuildFiles']} for k,t in terminals.items()},'limitations':limitations,'ownership':'Actual supervisor and child absence independently checked after both terminals before releasing heavy window to root. No live API or production mutation.'}
(dest/'qualification.json').write_text(json.dumps(receipt,indent=2)+'\n');(dest/'.gitattributes').write_text('* -text\n')
note='A bounded external phase observation compared exact7e30 and the qualified51e8 baseline with identical metadata-only Inspector/SDK/TLS/fixture hooks, unchanged six-profile driver and fixed limits. Both actual terminals were0 with all assertions, source/build/driver bytes unchanged and owned processes/containers absent. This is diagnostic, not acceptance: overlapping intervals and observer costs cannot be summed as wall attribution. In1k, native request window77.042→113.151ms and first-native-start to last-native-end combined59.518→97.680ms increased, while fixture request-to-end median12.039→12.262ms, fixture stringify sum0.808→0.729ms and post-native-to-response-end combined3.915→2.194ms stayed small. The small-profile gap lies mainly inside native request scheduling/transport/callback processing; this observation does not isolate a complete cause. Large25/3 requests18→21/20 and fixture stringify sums42.863→60.506ms /14.619→27.546ms show bounded extra-page generation is part of their native window. Baseline end-callback sums are not equivalent parser partitions because its fullJSON processing occurs later. Baseline SDK hook count0 is an unobserved older path, not absence of fresh authorization. Original candidate analysis incorrectly inferred accepted/rejected status from end events; it remains retained alongside corrected neutral event analysis. [Phase comparison receipt](implementation-evidence/native-phase-comparison-7e30/qualification.json) preserves40 originals, exact hooks, compiled manifests and terminals. No new production change or acceptance pass follows from this characterization;7e30 performance remains failed.'
review=[]
for doc in sorted((repo/'docs').rglob('*.md')):
 raw=doc.read_bytes();text=raw.decode('utf-8');updated=doc.parent==repo/'docs' and doc.name in ['BORTUS-NATIVE-LIST-PERFORMANCE.md','BORTUS-IMPLEMENTATION.md'];review.append({'path':doc.relative_to(repo).as_posix(),'sha256Before':sha(raw),'updated':updated})
 if updated:
  if doc.name=='BORTUS-IMPLEMENTATION.md':
   lines=text.splitlines();matches=[i for i,l in enumerate(lines) if l.startswith('| A07 cache cost |')];assert len(matches)==1
   lines[matches[0]]='| A07 cache cost | Independent coalescing/backoff/retention, resource-only snapshots and bounded complete Pod execution; unchanged fixed Linux baseline51e8 versus exact7e30 | Failed: latest warm1k p50/p95 improve7.209/11.371→6.412/8.989ms and concurrent85.633→73.421ms, but warm200 p50 and small/3large concurrent tails regress; native1k73.698→108.006ms and large profiles regress. Original reports remain immutable; bounded phase characterization is non-acceptance |'
   text='\n'.join(lines)+'\n'
  doc.write_text(text.rstrip()+'\n\n'+note+'\n',encoding='utf-8',newline='')
(dest/'doc-review.json').write_text(json.dumps(review,indent=2)+'\n')
print(json.dumps({'path':str(dest/'qualification.json'),'sha256':sha((dest/'qualification.json').read_bytes()),'copies':len(copies),'originals':40,'docCount':len(review),'updatedDocs':2}))
