from pathlib import Path
import subprocess,io,json,zipfile,hashlib,statistics
base=Path(__file__).parent;out=base/'characterize-phase-baseline-51e8-complete';out.mkdir(exist_ok=False)
linux=r'''
import pathlib,json,hashlib,io,zipfile,sys
p=pathlib.Path('/home/brajam/.cache/bortus-controlled-perf/characterize-phase-baseline-51e8-v1');t=json.loads((p/'terminal.json').read_bytes());assert t['actualExit']==0 and t['ownedLiveContainers']==[] and t['sourceUnchanged'] and t['compiledBuildUnchanged'] and t['frozenDriverUnchanged'];assert all(not pathlib.Path('/proc/'+str(x)).exists() for x in [t['pid'],t['childPID']])
b=io.BytesIO()
with zipfile.ZipFile(b,'w',zipfile.ZIP_DEFLATED) as z:
 for f in sorted(p.rglob('*')):
  if f.is_file():z.writestr(f.relative_to(p).as_posix(),f.read_bytes())
sys.stdout.buffer.write(b.getvalue())
'''
r=subprocess.run(['wsl','-d','Ubuntu','--','python3','-B','-c',linux],capture_output=True);assert r.returncode==0,r.stderr.decode();(out/'originals.zip').write_bytes(r.stdout);manifest=[]
with zipfile.ZipFile(io.BytesIO(r.stdout)) as z:
 for row in z.infolist():
  p=out/row.filename;assert p.resolve().is_relative_to(out.resolve());data=z.read(row);p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data);manifest.append({'path':row.filename,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()})
records=[json.loads(p.read_bytes()) for p in (out/'output').glob('request-*.json')];records.sort(key=lambda r:r['windows'][0]['startUs']);assert len(records)==6 and all(len(r['windows'])==1 for r in records)
fixture=json.loads((out/'output/fixture-body-metadata.json').read_bytes())['rows'];names=['audit-small','metadata-200','metadata-1000','metadata-10000','kv-sized-native-25','maximum-flat-native-3'];rows=[]
for name,record in zip(names,records):
 w=record['windows'][0];wire=record['https'];f=[r for r in fixture if w['startUs']<=r['startUs']<=w['endUs']];tls=[r['tlsMs']-r['socketMs'] for r in wire if r['tlsMs'] is not None];last=max(r['endHandlersCompleteUs'] or r['endUs'] for r in wire);first=min(r['startUs'] for r in wire)
 accepted=[r for r in wire if r['endHandlersCompleteUs']];rejected=[r for r in wire if not r['endHandlersCompleteUs']]
 frames=record['cpu']['frames'];top=[r for r in frames if r['kind']=='native'][:16]
 rows.append({'fixture':name,'nativeWindowMs':w['durationMs'],'sdkCalls':len(record['sdkAuth']),'sdkAsyncSumMs':sum(a['durationMs'] for a in record['sdkAuth']),'nativeRequestCount':len(wire),'tlsConnectionCount':len(tls),'socketAssignedToTLSCombinedSumMs':sum(tls),'preFirstNativeRequestCombinedMs':(first-w['startUs'])/1000,'firstNativeStartToLastNativeEndCombinedMs':(last-first)/1000,'postLastNativeEndToResponseEndCombinedMs':(w['responseEndStartUs']-last)/1000,'responseEndCallUs':w['responseEndCallUs'],'jsonTiming':w['jsonTiming'],'dataHandlerSynchronousSumMs':sum(r['dataHandlerUs'] for r in wire)/1000,'endEventHandlerSynchronousSumMs':sum(r['endHandlerUs'] for r in accepted)/1000,'responsesWithoutEndEvent':len(rejected),'noEndEventDataHandlerSynchronousSumMs':sum(r['dataHandlerUs'] for r in rejected)/1000,'fixtureRequestsInNativeWindow':len(f),'fixtureStringifySumMs':sum(r['stringifyUs'] for r in f)/1000,'fixtureRequestToResponseEndCombinedMedianMs':statistics.median((r['responseEndStartUs']-r['startUs'])/1000 for r in f),'fixtureRequestToResponseEndCombinedMaxMs':max((r['responseEndStartUs']-r['startUs'])/1000 for r in f),'bodyHeaderToEndEventBeforeHandlerCombinedSumMs':sum(max(0,r['endHandlersCompleteUs']-r['endHandlerUs']-r['startUs']-r['responseMs']*1000) for r in accepted)/1000,'topWeightedCPUFrames':top})
analysis={'nonAcceptance':True,'sourceCommit':'51e8cd66379c1f40a95ea02f4da7c8aed848f2a4','instrumentationOverhead':True,'chronologicalFixtureOrderBound':True,'limitations':['Single diagnostic observation, not before/after performance acceptance.','SDK/TLS/body timings overlap across bounded workers and sums cannot be added as wall attribution.','Data/end synchronous handlers include parser plus listener/cleanup/observer work; combined intervals labelled.','Pre-request and post-native intervals are combined auth/queue/projection/serialization paths, not isolated SQL or projection.','Fixture timer/body-generation includes unchanged12ms delay and scheduling; JSON stringify is separately measured numeric duration only.','No argument, body/key/URL/header/options or dynamic error-local data retained.'],'rows':rows}
(out/'analysis.json').write_text(json.dumps(analysis,indent=2)+'\n',encoding='utf-8');(out/'manifest.json').write_text(json.dumps({'archiveSHA256':hashlib.sha256(r.stdout).hexdigest(),'originals':manifest},indent=2)+'\n')
print(json.dumps({'out':str(out),'originals':len(manifest),'rows':[{k:v for k,v in row.items() if k!='topWeightedCPUFrames'} for row in rows]},indent=2))
