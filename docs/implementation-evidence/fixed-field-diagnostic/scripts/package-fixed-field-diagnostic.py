from pathlib import Path
import json,hashlib,subprocess
b=Path(__file__).parent; repo=Path(r'C:\Users\james\.codex\worktrees\bortus-app-recovered\kubernetes migration')
owner=b/'fixed-field-diagnostic-v1'; dest=repo/'docs/implementation-evidence/fixed-field-diagnostic';dest.mkdir(exist_ok=False)
sha=lambda raw:hashlib.sha256(raw).hexdigest()
r=json.loads((owner/'report.json').read_bytes());t=json.loads((owner/'terminal.json').read_bytes())
assert t['actual_exit']==t['child_exit']==0 and t['reaped'] and t['owned_pid_absent']
assert r['cases']==27161 and r['malformedCases']==20907 and r['equivalencePassed'] and r['exactProductionSourceUnchanged']
assert len(r['timings'])==15 and all(len(x['beforeMs'])==len(x['afterMs'])==15 for x in r['timings'])
assert all(x['equal'] for x in r['structural'])
assert [x['setConstructors'] for x in r['causal']]==[401,200]
copies=[]
for p in sorted(owner.iterdir()):
 if not p.is_file():continue
 raw=p.read_bytes();(dest/p.name).write_bytes(raw);assert (dest/p.name).read_bytes()==raw
 copies.append({'original':str(p),'copy':p.name,'bytes':len(raw),'sha256':sha(raw)})
for p in [Path(__file__),b/'prepare-fixed-field-diagnostic.py']:
 raw=p.read_bytes();d=dest/'scripts'/p.name;d.parent.mkdir(exist_ok=True);d.write_bytes(raw)
 copies.append({'original':str(p),'copy':d.relative_to(dest).as_posix(),'bytes':len(raw),'sha256':sha(raw)})
assert subprocess.check_output(['git','diff','--exit-code','4668ceb40c3120c7e4053d94edff31f57b7e1f7f','HEAD','--','k8s-rewrite/front-end'],cwd=repo)==b''
assessment={'productionCandidate':'4668ceb40c3120c7e4053d94edff31f57b7e1f7f','sourceHeadAtPreparation':'cd25c6bf46577acf4b3e08e725f2e8a35aa19609','copies':copies,'terminal':t,'cases':r['cases'],'malformedRefusals':r['malformedCases'],'structural':r['structural'],'causal':r['causal'],'sourceChanges':r['sourceChanges'],'timings':r['timings'],'timingTrimmed':False,'sourceEdited':False,'productionProposal':'Replace only known root/item duplicate-field Sets and includes arrays with scalar bits; no production adoption or functional qualification yet.','decision':'Typical median parser benefit demonstrated with complete differential corpus; mixed p95 regressions retained. This is a narrow proposed allocation optimization, not endpoint acceptance or a sufficient fix for the measured34ms gap.','limitations':r['limitations']+['One pinned one-CPU local public-input diagnostic; no wire fixtures, fresh authorization or endpoint timing were executed.','Original full grammar/capture and typed metadata output remain identical; native values/unknown fields do not enter decoded capture.','No JIT-equivalence claim follows from structural method equality.','All15 alternating timing arrays remain untrimmed, including cold/GC variability.'],'performanceAcceptance':False,'A07':'failed/open','A21':'failed/open'}
(dest/'.gitattributes').write_bytes(b'* -text\n');(dest/'assessment.json').write_bytes((json.dumps(assessment,indent=2)+'\n').encode())
(b/'fixed-field-diagnostic-receipt.json').write_bytes((dest/'assessment.json').read_bytes())
note='A separate fixed-known-field allocation experiment preserves the complete original Reader string/skip/capture/text methods, fatal decoding and JSON parsing, and changes only duplicate guards in an outside-production VM. Its actual one-CPU Node22.23.3 OS/child exit0 and owned cleanup bind27,161 differential cases/20,907 refusals, including escaped known duplicate names and prototype-like unknown names. At200 objects the Set-constructor count falls401→200, while grammar/capture/decode/parse counts remain identical. Typical56-object medians improve15.2%/8.8%/2.7% at256B/16KiB/64KiB chunks;200-object medians improve5.3%/6.8%/6.2%. All15 alternating observation arrays are retained:200-object p95 regresses20.6% at256B and4.2% at16KiB; nested256B p95 regresses2.4%, and long-annotation medians remain approximately flat. This is a narrow allocation candidate awaiting production/functional qualification, not a full endpoint improvement or A07/A21 pass; the56-object/16KiB saving0.149ms per page cannot alone account for the34ms endpoint gap. [Exact diagnostic sources, originals and assessment](implementation-evidence/fixed-field-diagnostic/assessment.json) preserve both improvement and regression observations; no production edit or unchanged broad pair ran.'
review=[]
for p in sorted((repo/'docs').rglob('*.md')):
 raw=p.read_bytes();raw.decode('utf-8-sig');update=p.parent==repo/'docs' and p.name in ['BORTUS-CONTROLLED-PERFORMANCE.md','BORTUS-NATIVE-LIST-PERFORMANCE.md','BORTUS-IMPLEMENTATION.md']
 review.append({'path':p.relative_to(repo).as_posix(),'beforeSHA256':sha(raw),'updated':update})
 if update:
  eol='\r\n' if b'\r\n' in raw else '\n';p.write_bytes(raw+(eol+eol+note+eol).encode())
(dest/'doc-review.json').write_bytes((json.dumps(review,indent=2)+'\n').encode())
print(json.dumps({'assessment':str(dest/'assessment.json'),'sha256':sha((dest/'assessment.json').read_bytes()),'copies':len(copies),'docsChecked':len(review)}))
