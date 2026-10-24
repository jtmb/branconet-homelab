
import datetime,hashlib,json,os,pathlib,subprocess,sys,time
WORK=pathlib.Path(__file__).resolve().parent
SOURCE=WORK/'source'
BUILD=pathlib.Path.home()/'.cache/bortus-controlled-perf/run-05381825cdec/candidate'
IMAGE='sha256:f628f5688b3fafb391d8d99c9b16aee4d9162aa5aaa121c3ae340f5bc8c2a678'
record={'sourceCommit':'7e30b9b428a66cd3f5e618cec5e694d5f03302ac','sourceBuildRecord':'run-05381825cdec/record.json','runtimeImage':IMAGE,'readonlySource':True,'network':'none','stages':[],'testConcurrency':2,'productionCommands':False}
def save():
 p=WORK/'record.next';p.write_text(json.dumps(record,indent=2)+'\n');p.replace(WORK/'record.json')
base=['docker','run','--rm','--pull','never','--network','none','--cpus','4','--cpuset-cpus',','.join(map(str,sorted(os.sched_getaffinity(0))[:4])),'--memory','4g','--memory-swap','4g','--pids-limit','512','--mount','type=bind,source='+str(SOURCE)+',target=/source,readonly','--mount','type=bind,source='+str(BUILD/'node_modules')+',target=/source/node_modules,readonly','--mount','type=bind,source='+str(BUILD/'.next')+',target=/source/.next,readonly','--workdir','/source','--env','DATABASE_URL=file:/tmp/disposable-test-default.db','--env','NEXT_TELEMETRY_DISABLED=1','--env','NODE_ENV=test']
steps=[('unit','node node_modules/tsx/dist/cli.mjs --test --test-concurrency=2 tests/*.test.ts'),('http','node node_modules/tsx/dist/cli.mjs --test --test-concurrency=2 tests/*.integration.ts')]
for phase,script in steps:
 name='bortus-functional-'+phase+'-'+WORK.name
 command=base+['--name',name,IMAGE,'sh','-c',script]
 log=WORK/(phase+'.log');start=time.time();record['activePhase']=phase;save()
 with log.open('xb') as output:
  child=subprocess.Popen(command,stdin=subprocess.DEVNULL,stdout=output,stderr=subprocess.STDOUT)
  record['activePid']=child.pid;record['activeStartTicks']=pathlib.Path('/proc/'+str(child.pid)+'/stat').read_text().split(') ',1)[1].split()[19];save()
  try:code=child.wait(timeout=600)
  except subprocess.TimeoutExpired:
   subprocess.run(['docker','stop','--time','5',name],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=20);code=child.wait(timeout=30)
 record['stages'].append({'phase':phase,'actualExit':code,'seconds':time.time()-start,'logSha256':hashlib.sha256(log.read_bytes()).hexdigest(),'command':command});save()
 if code:break
record['terminal']=True;record['actualExit']=record['stages'][-1]['actualExit'];record['terminalAtUTC']=datetime.datetime.now(datetime.timezone.utc).isoformat()
names=subprocess.check_output(['docker','ps','--format','{{.Names}}']).decode().splitlines();record['ownedLiveContainers']=[n for n in names if n.startswith('bortus-functional-') and n.endswith(WORK.name)]
record.pop('activePid',None);record.pop('activePhase',None);save();(WORK/'terminal.json').write_text(json.dumps(record,indent=2)+'\n')
raise SystemExit(record['actualExit'])
