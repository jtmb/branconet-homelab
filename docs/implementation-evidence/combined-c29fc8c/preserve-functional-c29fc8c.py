from pathlib import Path
import hashlib,io,json,subprocess,zipfile
base=Path(__file__).parent
preparation=json.loads((base/'current-functional-c29fc8c-preparation.json').read_bytes());handle=preparation['handle']
target=base/(handle['owner']+'-complete');assert not target.exists()
linux=r'''
import hashlib,io,json,pathlib,re,subprocess,sys,zipfile
w=pathlib.Path(sys.argv[1]);record=json.loads((w/'terminal.json').read_bytes());handle=json.loads((w/'handle.json').read_bytes())
assert record['actualExit']==0 and record['ownedLiveContainers']==[] and not pathlib.Path('/proc/'+str(handle['supervisorPid'])).exists()
assert [x['phase'] for x in record['stages']]==['fresh-build','unit','lint','typecheck','http'] and all(x['actualExit']==0 for x in record['stages'])
assert not any(n.startswith('bortus-functional-') and n.endswith(w.name) for n in subprocess.check_output(['docker','ps','--format','{{.Names}}']).decode().splitlines())
counts={}
for phase,expected in [('unit',214),('http',4)]:
    text=(w/(phase+'.log')).read_text();summary={name:int(re.search(r'^# '+name+r' (\d+)$',text,re.M).group(1)) for name in ['tests','pass','fail','cancelled','skipped','todo']}
    assert summary=={'tests':expected,'pass':expected,'fail':0,'cancelled':0,'skipped':0,'todo':0}
    counts[phase]=summary
assert all(hashlib.sha256((w/'source'/n).read_bytes()).hexdigest()==d for n,d in record['sourceManifest'].items())
assert all(hashlib.sha256((w/'source/.next'/n).read_bytes()).hexdigest()==d for n,d in record['compiledManifest'].items())
proof={'sourceCommit':record['sourceCommit'],'unitAndHttp':counts,'allFiveStagesExit0':True,'ownedSupervisorAbsent':True,'ownedContainersAbsent':True,'sourceFilesUnchanged':len(record['sourceManifest']),'compiledFilesUnchanged':len(record['compiledManifest']),'retainedFullLinuxSource':str(w/'source'),'runtimeImage':record['runtimeImage'],'noPerformanceAcceptance':True}
b=io.BytesIO()
with zipfile.ZipFile(b,'w',zipfile.ZIP_DEFLATED) as z:
    for p in sorted(w.iterdir()):
        if p.is_file():z.writestr(p.name,p.read_bytes())
    z.writestr('ownership-source-proof.json',json.dumps(proof,indent=2)+'\n')
sys.stdout.buffer.write(b.getvalue())
'''
r=subprocess.run(['wsl','-d','Ubuntu','--exec','python3','-B','-c',linux,handle['work']],capture_output=True)
(base/'functional-c29fc8c-preservation.stderr').write_bytes(r.stderr);assert r.returncode==0,r.stderr.decode()
target.mkdir(exist_ok=False);(target/'linux-original-artifacts.zip').write_bytes(r.stdout);manifest=[]
with zipfile.ZipFile(io.BytesIO(r.stdout)) as z:
    for item in z.infolist():
        p=target/item.filename;assert p.resolve().is_relative_to(target.resolve());data=z.read(item);p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data);manifest.append({'path':item.filename,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()})
proof=json.loads((target/'ownership-source-proof.json').read_bytes());proof.update(originalArtifacts=manifest,originalArchiveSha256=hashlib.sha256(r.stdout).hexdigest(),protectedPreparation=preparation['protected'],retainedLaunchFailures=[])
(target/'manifest.json').write_text(json.dumps(proof,indent=2)+'\n')
print(json.dumps({'target':str(target),'originalArtifacts':len(manifest),'manifestSha256':hashlib.sha256((target/'manifest.json').read_bytes()).hexdigest(),'counts':proof['unitAndHttp'],'compiledFiles':proof['compiledFilesUnchanged']}))
