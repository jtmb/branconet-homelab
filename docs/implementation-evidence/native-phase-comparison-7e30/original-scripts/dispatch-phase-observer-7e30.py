from pathlib import Path
import hashlib,io,json,subprocess,zipfile
base=Path(__file__).parent;old=base/'characterize-phase-7e30b9b-v1';owner='characterize-phase-7e30b9b-v2';prep=base/owner;prep.mkdir(exist_ok=False)
files={n:(old/n).read_bytes() for n in ['child-shim.cjs','request-profiler.cjs','supervisor.py']}
s=files['request-profiler.cjs'].decode();start=s.index('const jsonStringify=');end=s.index('const now=()=>',start);block=s[start:end];s=s[:start]+s[end:];marker="chain=post('Profiler.enable').then(()=>post('Profiler.setSamplingInterval',{interval:100}));";assert s.count(marker)==1;s=s.replace(marker,marker+'\n'+block);files['request-profiler.cjs']=s.encode()
node=r'C:\Users\james\AppData\Local\Temp\bortus-node22-3f6ebe6f1fca4cb092a488a5d635fb66\node-v22.23.3-win-x64\node.exe'
for name,data in files.items():
 (prep/name).write_bytes(data)
 if name.endswith('.cjs'):
  r=subprocess.run([node,'--check',str(prep/name)],capture_output=True);(prep/(name+'.syntax.log')).write_bytes(r.stdout+r.stderr);assert r.returncode==0
b=io.BytesIO()
with zipfile.ZipFile(b,'w',zipfile.ZIP_DEFLATED) as z:
 for name,data in files.items():z.writestr(name,data)
linux=r'''
import hashlib,io,json,os,pathlib,subprocess,sys,zipfile
os.umask(0o077);root=pathlib.Path.home()/'.cache/bortus-controlled-perf';work=root/'characterize-phase-7e30b9b-v2'
assert all(not pathlib.Path('/proc/'+str(p)).exists() for p in [1903609,1895666,1895667])
terminal=json.loads((root/'functional-7e30b9b-20261011-084328/terminal.json').read_bytes());assert terminal['actualExit']==0 and terminal['ownedLiveContainers']==[]
work.mkdir(mode=0o700,exist_ok=False)
with zipfile.ZipFile(io.BytesIO(sys.stdin.buffer.read())) as z:
 for row in z.infolist():
  p=work/row.filename;assert p.resolve().is_relative_to(work.resolve());p.write_bytes(z.read(row));p.chmod(0o600)
source=root/'run-05381825cdec/candidate';compiled={}
for prefix in ['.next/server','.next/static','.next/standalone/.next']:
 for p in (source/prefix).rglob('*'):
  if p.is_file():compiled[p.relative_to(source).as_posix()]=p
compiled['.next/standalone/server.js']=source/'.next/standalone/server.js'
files=[{'path':name,'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for name,p in sorted(compiled.items())]
(work/'compiled-build-manifest.json').write_text(json.dumps({'candidate':'7e30b9b428a66cd3f5e618cec5e694d5f03302ac','sourceRecord':'run-05381825cdec/record.json','files':files},indent=2)+'\n')
with (work/'supervisor.stdout').open('xb') as out,(work/'supervisor.stderr').open('xb') as err:
 child=subprocess.Popen(['python3','-B',str(work/'supervisor.py')],stdin=subprocess.DEVNULL,stdout=out,stderr=err,start_new_session=True)
handle={'owner':work.name,'supervisorPID':child.pid,'startTicks':pathlib.Path('/proc/'+str(child.pid)+'/stat').read_text().split(') ',1)[1].split()[19],'work':str(work),'nonAcceptance':True,'compiledFiles':len(files),'scriptHashes':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in work.iterdir() if p.suffix in ['.cjs','.py']}}
(work/'dispatch.json').write_text(json.dumps(handle,indent=2)+'\n');print(json.dumps(handle),flush=True)
'''
r=subprocess.run(['wsl','-d','Ubuntu','--','python3','-B','-c',linux],input=b.getvalue(),capture_output=True);(prep/'dispatch.log').write_bytes(r.stdout+r.stderr);print(r.stdout.decode(errors='replace'));print(r.stderr.decode(errors='replace'));raise SystemExit(r.returncode)
