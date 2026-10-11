import base64, datetime, hashlib, io, json, pathlib, subprocess, zipfile
owner = pathlib.Path(__file__).parent
work = '/home/brajam/.cache/bortus-controlled-perf/functional-ab8d450-20261011-125210-2d8f04'
sha = lambda d: hashlib.sha256(d).hexdigest()
code = """
import hashlib,json,pathlib,subprocess,zipfile
w=pathlib.Path(WORK);r=json.loads((w/'terminal.json').read_bytes());h=json.loads((w/'handle.json').read_bytes())
assert r['terminal'] and r['actualExit']==0 and not r['ownedLiveContainers']
assert not pathlib.Path('/proc/'+str(h['supervisorPid'])).exists()
names=subprocess.check_output(['docker','ps','--format','{{.Names}}']).decode().splitlines();assert not [n for n in names if n.startswith('bortus-functional-') and n.endswith(w.name)]
assert len(r['stages'])==3 and all(s['actualExit']==0 for s in r['stages'])
source=w/'source'
assert all(hashlib.sha256((source/n).read_bytes()).hexdigest()==d for n,d in r['sourceManifest'].items())
assert all(hashlib.sha256((source/'.next'/n).read_bytes()).hexdigest()==d for n,d in r['compiledManifest'].items())
http=(w/'http.log').read_text();assert '# tests 4' in http and '# pass 4' in http and '# fail 0' in http and '# skipped 0' in http
affected=(w/'affected-http.log').read_text();assert '"checks":13,"failed":0' in affected and '"childExit":[0,null]' in affected and '"fixtureRemoved":true' in affected
files=['fresh-build.log','http.log','affected-http.log','handle.json','input.json','record.json','source.tar.gz','supervisor.py','supervisor.stdout','supervisor.stderr','terminal.json']
copies=[{'path':n,'bytes':(w/n).stat().st_size,'SHA256':hashlib.sha256((w/n).read_bytes()).hexdigest()} for n in files]
proof={'sourceCommit':r['sourceCommit'],'actualTerminal':r['terminalAtUTC'],'owner':h,'stages':[{'phase':s['phase'],'actualExit':s['actualExit'],'seconds':s['seconds'],'command':s['command']} for s in r['stages']],'sourceFilesUnchanged':len(r['sourceManifest']),'compiledFilesUnchanged':len(r['compiledManifest']),'originalHTTPPassed':4,'supplementalHTTPChecks':13,'ownedSupervisorAbsent':True,'ownedContainersAbsent':True,'retainedSource':str(source),'retainedCompiled':str(source/'.next'),'copies':copies}
(w/'complete-proof.json').write_text(json.dumps(proof,indent=2)+'\\n')
with zipfile.ZipFile(OUTPUT,'x',compression=zipfile.ZIP_DEFLATED) as z:
 for n in files+['complete-proof.json']:z.write(w/n,n)
print(json.dumps(proof))
"""
linux_output = '/mnt/c/' + str(owner / 'complete-originals.zip')[3:].replace('\\', '/')
code = 'WORK='+repr(work)+'\nOUTPUT='+repr(linux_output)+'\n'+code
run = subprocess.run(['wsl.exe','--exec','python3','-c',"exec(__import__('base64').b64decode('"+base64.b64encode(code.encode()).decode()+"'))"],capture_output=True)
(owner/'package.stdout').write_bytes(run.stdout);(owner/'package.stderr').write_bytes(run.stderr)
(owner/'package-terminal.json').write_text(json.dumps({'actualExit':run.returncode,'completedUtc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'stdoutSHA256':sha(run.stdout),'stderrSHA256':sha(run.stderr)},indent=2)+'\n',encoding='utf-8')
assert run.returncode==0
proof=json.loads(run.stdout)
with zipfile.ZipFile(owner/'complete-originals.zip') as z:
    for row in proof['copies']:assert sha(z.read(row['path']))==row['SHA256']
    assert json.loads(z.read('complete-proof.json'))==proof
(owner/'complete-proof.json').write_text(json.dumps(proof,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'actualExit':0,'originalHTTPPassed':4,'supplementalChecks':13,'sourceFiles':proof['sourceFilesUnchanged'],'compiledFiles':proof['compiledFilesUnchanged'],'copies':len(proof['copies']),'zipSHA256':sha((owner/'complete-originals.zip').read_bytes())}))
