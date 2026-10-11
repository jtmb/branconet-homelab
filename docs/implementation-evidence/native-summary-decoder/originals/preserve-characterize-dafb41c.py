from pathlib import Path
import subprocess,io,zipfile,json,hashlib
base=Path(__file__).parent;target=base/'characterize-dafb41c-complete';target.mkdir(exist_ok=False)
linux=r'''
import pathlib,hashlib,json,io,zipfile,sys
root=pathlib.Path.home()/'.cache/bortus-controlled-perf';p=root/'characterize-dafb41c-v1';build=root/'run-68ece1a7b4cb/candidate'
t=json.loads((p/'terminal.json').read_bytes());assert t['actualExit']==0 and t['ownedLiveContainers']==[] and t['compiledBuildUnchanged'] and t['sourceUnchanged'] and t['frozenDriverUnchanged']
assert all(not pathlib.Path('/proc/'+str(x)).exists() for x in [1874467,1874468])
driver=json.loads((p/'output/candidate-run-1.json').read_bytes());reports=sorted([(f,json.loads(f.read_bytes())) for f in (p/'output').glob('request-*.json')],key=lambda row:row[1]['windows'][0]['startUs']);assert len(reports)==len(driver['profiles'])==6
frames=[]
for (f,r),profile in zip(reports,driver['profiles']):
 assert r['sdkPrototypePatched'] and len(r['windows'])==1 and not (p/'output'/('failure-'+str(r['pid'])+'.json')).exists()
 frames.append({'profile':profile['fixture']['name'],'original':f.relative_to(p).as_posix(),'sdkAuthCalls':len(r['sdkAuth']),'sdkAuthDurationMs':sum(x['durationMs'] or 0 for x in r['sdkAuth']),'httpsRequests':len(r['https']),'tlsHandshakes':sum(x['tlsMs'] is not None for x in r['https']),'reusedRequests':sum(x['reused'] for x in r['https']),'sampledFrames':r['cpu']['frames'],'sampleMeaning':'Weighted sampled approximate stack time includes observer/idle; overlapping inclusive samples are not additive wall causes.'})
compiled=build/'.next/standalone/.next/server/chunks/2732.js';text=compiled.read_text();assert 'capture(' in text and 'new TextDecoder("utf-8",{fatal:!0})' in text
mapping={'compiledModule':'.next/standalone/.next/server/chunks/2732.js','sha256':hashlib.sha256(compiled.read_bytes()).hexdigest(),'bytes':compiled.stat().st_size,'captureOffset':text.index('capture('),'summaryStringOffset':text.index('string(){'),'rejectedPrefixContainsReadUInt32LE':text.count('readUInt32LE')>0,'sourceContract':'Named Reader.capture/text/string methods implement explicit summary parsing; minified rejected-prefix j maps to existing sizing hint grammar. Method and static-source mapping inspected, no dynamic arguments or body retained.'}
analysis={'nonAcceptance':True,'sourceCommit':t['sourceCommit'],'chronologicalFixtureMapping':'sorted native window startUs matched unchanged driver fixture order','ownedPIDsAbsent':[1874467,1874468],'ownedLiveContainers':[],'compiledMapping':mapping,'profiles':frames}
(p/'analysis.json').write_text(json.dumps(analysis,indent=2)+'\n')
b=io.BytesIO()
with zipfile.ZipFile(b,'w',zipfile.ZIP_DEFLATED) as z:
 for f in p.rglob('*'):
  if f.is_file():z.writestr(f.relative_to(p).as_posix(),f.read_bytes())
 z.writestr('compiled-public-source/2732.js',compiled.read_bytes())
sys.stdout.buffer.write(b.getvalue())
'''
r=subprocess.run(['wsl','-d','Ubuntu','--','python3','-B','-c',linux],capture_output=True);assert r.returncode==0,r.stderr.decode();(target/'original-artifacts.zip').write_bytes(r.stdout);manifest=[]
with zipfile.ZipFile(io.BytesIO(r.stdout)) as z:
 for row in z.infolist():
  data=z.read(row);p=target/row.filename;assert p.resolve().is_relative_to(target.resolve());p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data);manifest.append({'path':row.filename,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()})
(target/'manifest.json').write_text(json.dumps({'nonAcceptance':True,'source':'dafb41c3c226ef03913df2ab6c113a9820a709c6','archiveSHA256':hashlib.sha256(r.stdout).hexdigest(),'artifacts':manifest},indent=2)+'\n')
print(json.dumps({'path':str(target),'originals':len(manifest),'archiveSHA256':hashlib.sha256(r.stdout).hexdigest()}))
