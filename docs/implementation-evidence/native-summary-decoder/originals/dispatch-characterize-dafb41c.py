from pathlib import Path
import hashlib,io,json,subprocess,zipfile
base=Path(__file__).parent;repo=Path(r'C:\Users\james\.codex\worktrees\bortus-app-recovered\kubernetes migration');owner='characterize-dafb41c-v1'
old=repo/'docs/implementation-evidence/native-request-characterization-3f9b21c/characterize-3f9b21c-v3'
files={n:(old/n).read_bytes() for n in ['child-shim.cjs','request-profiler.cjs','supervisor.py']}
s=files['supervisor.py'].decode().replace('run-622cdf52624a','run-68ece1a7b4cb').replace('preparation-paired-3f9b21c-20261011-065856-3b80','preparation-paired-dafb41c-20261011-074727-252a').replace('3f9b21cd5beb568c8faddec75d6ba55ae889c310','dafb41c3c226ef03913df2ab6c113a9820a709c6')
s=s.replace("command=['docker'", "build_manifest=json.loads((p/'compiled-build-manifest.json').read_bytes())\nfor row in build_manifest['files']:assert hashlib.sha256((source/row['path']).read_bytes()).hexdigest()==row['sha256']\nrecord['compiledBuildManifestSHA256']=hashlib.sha256((p/'compiled-build-manifest.json').read_bytes()).hexdigest()\nrecord['compiledBuildFiles']=len(build_manifest['files'])\ncommand=['docker'")
s=s.replace("record['terminalAtUTC']=", "record['compiledBuildUnchanged']=all(hashlib.sha256((source/row['path']).read_bytes()).hexdigest()==row['sha256'] for row in build_manifest['files'])\nrecord['terminalAtUTC']=")
files['supervisor.py']=s.encode();b=io.BytesIO()
with zipfile.ZipFile(b,'w',zipfile.ZIP_DEFLATED) as z:
 for name,data in files.items():z.writestr(name,data)
linux=r'''
import datetime,hashlib,io,json,os,pathlib,subprocess,sys,zipfile
os.umask(0o077);root=pathlib.Path.home()/'.cache/bortus-controlled-perf';owner='characterize-dafb41c-v1';work=root/owner
assert all(not pathlib.Path('/proc/'+str(p)).exists() for p in [1871068,1873221,1863568,1863569])
assert json.loads((root/'functional-dafb41c-20261011-075425/terminal.json').read_bytes())['actualExit']==0
work.mkdir(mode=0o700,exist_ok=False)
with zipfile.ZipFile(io.BytesIO(sys.stdin.buffer.read())) as z:
 for row in z.infolist():
  p=work/row.filename;assert p.resolve().is_relative_to(work.resolve());p.write_bytes(z.read(row));p.chmod(0o600)
source=root/'run-68ece1a7b4cb/candidate';compiled={}
for prefix in ['.next/server','.next/static','.next/standalone/.next']:
 for p in (source/prefix).rglob('*'):
  if p.is_file():compiled[p.relative_to(source).as_posix()]=p
compiled['.next/standalone/server.js']=source/'.next/standalone/server.js'
files=[{'path':name,'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for name,p in sorted(compiled.items())]
(work/'compiled-build-manifest.json').write_text(json.dumps({'candidate':'dafb41c3c226ef03913df2ab6c113a9820a709c6','sourceRecord':'run-68ece1a7b4cb/record.json','files':files},indent=2)+'\n')
with (work/'supervisor.stdout').open('xb') as out,(work/'supervisor.stderr').open('xb') as err:
 child=subprocess.Popen(['python3','-B',str(work/'supervisor.py')],stdin=subprocess.DEVNULL,stdout=out,stderr=err,start_new_session=True)
handle={'owner':owner,'supervisorPID':child.pid,'startTicks':pathlib.Path('/proc/'+str(child.pid)+'/stat').read_text().split(') ',1)[1].split()[19],'work':str(work),'nonAcceptance':True,'compiledFiles':len(files),'scriptHashes':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in work.iterdir() if p.suffix in ['.cjs','.py']}}
(work/'dispatch.json').write_text(json.dumps(handle,indent=2)+'\n');print(json.dumps(handle),flush=True)
'''
r=subprocess.run(['wsl','-d','Ubuntu','--','python3','-B','-c',linux],input=b.getvalue(),capture_output=True);(base/'characterize-dafb41c-dispatch.log').write_bytes(r.stdout+r.stderr);print(r.stdout.decode(errors='replace'));print(r.stderr.decode(errors='replace'));raise SystemExit(r.returncode)
