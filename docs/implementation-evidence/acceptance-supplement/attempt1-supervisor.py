
import pathlib,os,subprocess,hashlib,json,time,datetime
work=pathlib.Path(__file__).resolve().parent;qa=work/'qa';out=work/'output';out.mkdir(mode=0o700)
original=pathlib.Path('/home/brajam/.cache/bortus-controlled-perf/functional-ab8d450-20261011-125210-2d8f04');source=original/'source';old=json.loads((original/'record.json').read_bytes());assert old['actualExit']==0
sha=lambda b:hashlib.sha256(b).hexdigest()
manifest=json.loads((qa/'manifest.json').read_bytes());record={'owner':work.name,'supervisorPid':os.getpid(),'supervisorStartTicks':pathlib.Path('/proc/self/stat').read_text().split(') ',1)[1].split()[19],'startedUtc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'sourceCommit':'ab8d450790ed8970c25ccfec78fa924c8f08ff6a','applicationSourceUnchangedAt':'059b7e6008a6b34dbb7ee31c504f06ac177d7304','originalTerminalSHA256':sha((original/'terminal.json').read_bytes()),'originalBuildStages':old['stages'],'sourceManifest':old['sourceManifest'],'compiledManifest':old['compiledManifest'],'overlayManifest':manifest,'performanceAcceptance':False}
def save():
 p=work/'record.next';p.write_text(json.dumps(record,indent=2)+'\n');p.replace(work/'record.json')
def unchanged():
 assert all(sha((source/n).read_bytes())==d for n,d in old['sourceManifest'].items());assert all(sha((source/'.next'/n).read_bytes())==d for n,d in old['compiledManifest'].items());assert all(sha((qa/n).read_bytes())==d for n,d in manifest.items())
name='bortus-acceptance-'+work.name;image='sha256:f628f5688b3fafb391d8d99c9b16aee4d9162aa5aaa121c3ae340f5bc8c2a678';actual=1
try:
 unchanged();record['beforeSourceAndCompiledVerified']=True;assert json.loads(subprocess.check_output(['docker','inspect',image]))[0]['Id']==image;cpus=','.join(map(str,sorted(os.sched_getaffinity(0))[:2]))
 command=['docker','run','--rm','--pull','never','--name',name,'--network','none','--read-only','--cpus','2','--cpuset-cpus',cpus,'--memory','1g','--memory-swap','1g','--pids-limit','256','--user',str(os.getuid())+':'+str(os.getgid()),'--tmpfs','/tmp:rw,nosuid,size=256m','--mount','type=bind,source='+str(source)+',target=/source,readonly','--mount','type=bind,source='+str(qa)+',target=/qa,readonly','--mount','type=bind,source='+str(out)+',target=/output','--workdir','/source','--env','NODE_ENV=test','--entrypoint','node',image,'/qa/supplement.cjs'];record['command']=command;record['container']=name
 with (work/'stdout').open('xb') as stdout,(work/'stderr').open('xb') as stderr:
  child=subprocess.Popen(command,stdin=subprocess.DEVNULL,stdout=stdout,stderr=stderr);record['dockerCliPid']=child.pid;record['dockerCliStartTicks']=pathlib.Path('/proc/'+str(child.pid)+'/stat').read_text().split(') ',1)[1].split()[19];save();deadline=time.monotonic()+120
  while child.poll() is None:
   if 'nodeHostPid' not in record:
    probe=subprocess.run(['docker','inspect',name],stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)
    if probe.returncode==0:
     row=json.loads(probe.stdout)[0];pid=row['State']['Pid']
     if pid and pathlib.Path('/proc/'+str(pid)+'/stat').exists():record['nodeHostPid']=pid;record['nodeStartTicks']=pathlib.Path('/proc/'+str(pid)+'/stat').read_text().split(') ',1)[1].split()[19];record['containerId']=row['Id'];save()
   if time.monotonic()>deadline:record['deadlineExceeded']=True;subprocess.run(['docker','stop','--time','2',name],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=10);break
   time.sleep(.1)
  actual=child.wait(timeout=10)
 unchanged();record['afterSourceAndCompiledVerified']=True
except Exception as e:record['failureClassification']=type(e).__name__
finally:
 names=subprocess.check_output(['docker','ps','-a','--format','{{.Names}}']).decode().splitlines();record['ownedContainersRemaining']=[n for n in names if n==name];record['ownedPidsRemaining']=[record[k] for k in ['dockerCliPid','nodeHostPid'] if k in record and pathlib.Path('/proc/'+str(record[k])).exists()];record.update(terminal=True,actualExit=actual,terminalUtc=datetime.datetime.now(datetime.timezone.utc).isoformat(),outputs={str(p.relative_to(work)):sha(p.read_bytes()) for p in out.rglob('*') if p.is_file()});save();(work/'terminal.json').write_text(json.dumps(record,indent=2)+'\n')
raise SystemExit(actual)
