
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
        try:
            name=command[command.index('--name')+1];observed={};until=time.monotonic()+timeout
            while child.poll() is None:
                probe=subprocess.run(['docker','inspect',name],capture_output=True)
                if probe.returncode==0:
                    state=json.loads(probe.stdout)[0]['State'];pid=state['Pid']
                    if pid and str(pid) not in observed:
                        proc=pathlib.Path('/proc/'+str(pid)+'/stat')
                        observed[str(pid)]={'pid':pid,'startTicks':proc.read_text().split(') ',1)[1].split()[19] if proc.exists() else None,'running':state['Running']}
                        record['activeContainer']=name;record['activeContainerProcesses']=list(observed.values());save()
                if time.monotonic()>until:raise subprocess.TimeoutExpired(command,timeout)
                time.sleep(0.5)
            code=child.wait();record.setdefault('observedContainerProcesses',{})[phase]=list(observed.values())
        except subprocess.TimeoutExpired:
            name=command[command.index('--name')+1]
            subprocess.run(['docker','stop','--time','5',name],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=20);code=child.wait(timeout=30)
    record['stages'].append(dict(phase=phase,actualExit=code,seconds=time.time()-start,logSha256=hashlib.sha256(log.read_bytes()).hexdigest(),command=command));record.pop('activePid',None);record.pop('activePhase',None);record.pop('activeContainer',None);record.pop('activeContainerProcesses',None);save();unchanged();return code
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
            selected=runtime.copy()
            if phase=='http':
                selected[selected.index('4')]='2';selected[selected.index(cpus)]=','.join(map(str,sorted(os.sched_getaffinity(0))[:2]));selected[selected.index('4g')]='1g';selected[selected.index('4g')]='1g'
            actual=stage(phase,selected+['--name','bortus-functional-'+phase+'-'+WORK.name,IMAGE,'-lc',cmd],600)
            if actual:break
        assert all(hashlib.sha256((SOURCE/'.next'/n).read_bytes()).hexdigest()==d for n,d in record['compiledManifest'].items())
except Exception as error:
    record['failureClassification']=type(error).__name__;actual=actual or 1
finally:
    names=subprocess.check_output(['docker','ps','--format','{{.Names}}']).decode().splitlines();record['ownedLiveContainers']=[n for n in names if n.startswith('bortus-functional-') and n.endswith(WORK.name)]
    record.update(terminal=True,actualExit=actual,terminalAtUTC=datetime.datetime.now(datetime.timezone.utc).isoformat());save();(WORK/'terminal.json').write_text(json.dumps(record,indent=2)+'\n')
raise SystemExit(actual)
