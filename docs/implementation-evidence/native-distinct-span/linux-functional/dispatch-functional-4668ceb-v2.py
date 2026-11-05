from pathlib import Path
import datetime, hashlib, importlib.util, io, json, subprocess, sys, uuid, zipfile

base=Path(__file__).parent
repo=Path(r'C:\Users\james\.codex\worktrees\bortus-app-recovered\kubernetes migration')
commit='4668ceb40c3120c7e4053d94edff31f57b7e1f7f'
owner='functional-4668ceb-'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:4]
protected=base/(owner+'-preparation'); protected.mkdir(exist_ok=False)
exporter=Path(r'C:\Users\james\.codex\worktrees\8cdf\branconet-charts\scripts\export_bortus_source.py')
assert hashlib.sha256(exporter.read_bytes()).hexdigest()=='5bcdb86fd8a795d72f195dbf5163a46ad09de79b54d0ead4dbba0eadb0743470'
spec=importlib.util.spec_from_file_location('exact_exporter',exporter); module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
archive=protected/'source.tar.gz'; exported=module.export(repo,commit,archive,False)
tests=[]; stream=io.BytesIO()
with zipfile.ZipFile(stream,'w',zipfile.ZIP_DEFLATED) as z:
    z.writestr('source.tar.gz',archive.read_bytes())
    for row in subprocess.check_output(['git','ls-tree','-r','-z',commit,'--','k8s-rewrite/front-end/tests'],cwd=repo).split(b'\0'):
        if not row: continue
        meta,path=row.split(b'\t',1);mode,kind,blob=meta.decode().split();assert kind=='blob' and mode in ['100644','100755']
        data=subprocess.check_output(['git','cat-file','blob',blob],cwd=repo);name=path.decode().removeprefix('k8s-rewrite/front-end/')
        assert hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()==blob
        z.writestr(name,data);tests.append(dict(path=name,mode=mode,blob=blob,sha256=hashlib.sha256(data).hexdigest(),bytes=len(data)))
    z.writestr('input.json',json.dumps({'owner':owner,'sourceCommit':commit,'exported':exported,'archiveSha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'tests':tests},indent=2,default=str))
linux=r'''
import datetime,hashlib,io,json,os,pathlib,subprocess,sys,tarfile,zipfile
os.umask(0o077)
with zipfile.ZipFile(io.BytesIO(sys.stdin.buffer.read())) as z:
    record=json.loads(z.read('input.json')); owner=record['owner'];work=pathlib.Path.home()/'.cache/bortus-controlled-perf'/owner;work.mkdir(mode=0o700,exist_ok=False)
    source=work/'source';source.mkdir()
    (work/'source.tar.gz').write_bytes(z.read('source.tar.gz'))
    assert hashlib.sha256((work/'source.tar.gz').read_bytes()).hexdigest()==record['archiveSha256']
    with tarfile.open(work/'source.tar.gz') as archive:
        for row in archive:
            assert row.isfile() and (source/row.name).resolve().is_relative_to(source.resolve())
        archive.extractall(source,filter='data')
    for row in record['tests']:
        target=source/row['path'];assert target.resolve().is_relative_to(source.resolve());target.parent.mkdir(parents=True,exist_ok=True);data=z.read(row['path']);assert hashlib.sha256(data).hexdigest()==row['sha256'];target.write_bytes(data);target.chmod(int(row['mode'][-3:],8))
    (work/'input.json').write_text(json.dumps(record,indent=2)+'\n')
script=r"""
import datetime,hashlib,json,os,pathlib,subprocess,time
WORK=pathlib.Path(__file__).resolve().parent;SOURCE=WORK/'source';IMAGE='sha256:f628f5688b3fafb391d8d99c9b16aee4d9162aa5aaa121c3ae340f5bc8c2a678'
record=json.loads((WORK/'input.json').read_bytes());record.update(runtimeImage=IMAGE,productionCommands=False,stages=[],networkRuntime='none',sourceManifest={str(p.relative_to(SOURCE)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(SOURCE.rglob('*')) if p.is_file()})
def save():
    p=WORK/'record.next';p.write_text(json.dumps(record,indent=2)+'\n');p.replace(WORK/'record.json')
def unchanged():
    assert all((SOURCE/n).is_file() and hashlib.sha256((SOURCE/n).read_bytes()).hexdigest()==d for n,d in record['sourceManifest'].items())
def stage(phase,command,timeout):
    log=WORK/(phase+'.log');record['activePhase']=phase;save();start=time.time()
    with log.open('xb') as output:
        child=subprocess.Popen(command,stdin=subprocess.DEVNULL,stdout=output,stderr=subprocess.STDOUT)
        record['activePid']=child.pid;record['activeStartTicks']=pathlib.Path('/proc/'+str(child.pid)+'/stat').read_text().split(') ',1)[1].split()[19];save()
        try: code=child.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            name=command[command.index('--name')+1]
            subprocess.run(['docker','stop','--time','5',name],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=20);code=child.wait(timeout=30)
    record['stages'].append(dict(phase=phase,actualExit=code,seconds=time.time()-start,logSha256=hashlib.sha256(log.read_bytes()).hexdigest(),command=command));record.pop('activePid',None);record.pop('activePhase',None);save();unchanged();return code
actual=1
try:
    record['dockerImageId']=json.loads(subprocess.check_output(['docker','inspect',IMAGE]))[0]['Id'];assert record['dockerImageId']==IMAGE
    cpus=','.join(map(str,sorted(os.sched_getaffinity(0))[:4]))
    common=['docker','run','--rm','--pull','never','--cpus','4','--cpuset-cpus',cpus,'--memory','4g','--memory-swap','4g','--pids-limit','256','--user',str(os.getuid())+':'+str(os.getgid()),'--mount','type=bind,source='+str(SOURCE)+',target=/source','--workdir','/source','--env','DATABASE_URL=file:/tmp/bortus-functional-build.db','--env','NEXT_TELEMETRY_DISABLED=1','--env','CIRCLE_NODE_TOTAL=4','--entrypoint','bash']
    build=common+['--name','bortus-functional-build-'+WORK.name,IMAGE,'-lc','npm ci && npm run build']
    actual=stage('fresh-build',build,900)
    if actual==0:
        record['compiledManifest']={str(p.relative_to(SOURCE/'.next')):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((SOURCE/'.next').rglob('*')) if p.is_file()};save()
        # Runtime stages retain fixed source and freshly compiled output read-only.
        runtime=common.copy();runtime[runtime.index('type=bind,source='+str(SOURCE)+',target=/source')]='type=bind,source='+str(SOURCE)+',target=/source,readonly';runtime+=['--network','none','--env','NODE_ENV=test']
        for phase,cmd in [('unit','node node_modules/tsx/dist/cli.mjs --test --test-concurrency=2 tests/*.test.ts'),('lint','npm run lint'),('typecheck','node node_modules/typescript/bin/tsc --noEmit --incremental false'),('http','node node_modules/tsx/dist/cli.mjs --test --test-concurrency=2 tests/*.integration.ts')]:
            actual=stage(phase,runtime+['--name','bortus-functional-'+phase+'-'+WORK.name,IMAGE,'-lc',cmd],600)
            if actual:break
        assert all(hashlib.sha256((SOURCE/'.next'/n).read_bytes()).hexdigest()==d for n,d in record['compiledManifest'].items())
except Exception as error:
    record['failureClassification']=type(error).__name__;actual=actual or 1
finally:
    names=subprocess.check_output(['docker','ps','--format','{{.Names}}']).decode().splitlines();record['ownedLiveContainers']=[n for n in names if n.startswith('bortus-functional-') and n.endswith(WORK.name)]
    record.update(terminal=True,actualExit=actual,terminalAtUTC=datetime.datetime.now(datetime.timezone.utc).isoformat());save();(WORK/'terminal.json').write_text(json.dumps(record,indent=2)+'\n')
raise SystemExit(actual)
"""
(work/'supervisor.py').write_text(script)
with (work/'supervisor.stdout').open('xb') as out,(work/'supervisor.stderr').open('xb') as err:
    child=subprocess.Popen([sys.executable,'-B',str(work/'supervisor.py')],stdin=subprocess.DEVNULL,stdout=out,stderr=err,start_new_session=True)
handle=dict(owner=owner,supervisorPid=child.pid,supervisorStartTicks=pathlib.Path('/proc/'+str(child.pid)+'/stat').read_text().split(') ',1)[1].split()[19],work=str(work),sourceCommit=record['sourceCommit'],testSourceFiles=len(record['tests']),startedAtUTC=datetime.datetime.now(datetime.timezone.utc).isoformat())
(work/'handle.json').write_text(json.dumps(handle,indent=2)+'\n');print(json.dumps(handle),flush=True)
'''
(protected/'linux-dispatch.py').write_text(linux)
(protected/'dispatch-input.zip').write_bytes(stream.getvalue())
r=subprocess.run(['wsl','-d','Ubuntu','--exec','python3','-B','-c',linux],input=stream.getvalue(),stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
(protected/'dispatch.log').write_bytes(r.stdout);print(r.stdout.decode(errors='replace'))
if r.returncode==0:
    (base/'current-functional-4668ceb-preparation.json').write_text(json.dumps({'owner':owner,'sourceCommit':commit,'protected':str(protected),'handle':json.loads(r.stdout)},indent=2)+'\n')
raise SystemExit(r.returncode)
