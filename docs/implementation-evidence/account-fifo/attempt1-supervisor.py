import pathlib,json,subprocess,os,time,datetime,hashlib
p=pathlib.Path(__file__).resolve().parent;qa=p/'qa';out=p/'output';out.mkdir();original=pathlib.Path('/home/brajam/.cache/bortus-controlled-perf/functional-ab8d450-20261011-125210-2d8f04');source=original/'source';old=json.loads((original/'record.json').read_bytes());prepared=json.loads((qa/'prepared.json').read_bytes());sha=lambda b:hashlib.sha256(b).hexdigest();record={'startedUtc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'pid':os.getpid(),'startTicks':pathlib.Path('/proc/self/stat').read_text().split(') ',1)[1].split()[19],'prepared':prepared,'originalTerminalSHA256':sha((original/'terminal.json').read_bytes()),'performanceAcceptance':False};name='bortus-'+p.name;actual=1
def save():
 t=p/'record.next';t.write_text(json.dumps(record,indent=2)+'\n');t.replace(p/'record.json')
def verify():
 assert all(sha((qa/'source'/n).read_bytes())==s for n,s in prepared['sourceManifest'].items());assert all(sha((source/n).read_bytes())==s for n,s in old['sourceManifest'].items());assert all(sha((source/'.next'/n).read_bytes())==s for n,s in old['compiledManifest'].items())
try:
 verify();record['beforeVerified']=True;cpus=','.join(map(str,sorted(os.sched_getaffinity(0))[:2]));command=['docker','run','--rm','--pull','never','--name',name,'--network','none','--read-only','--cpus','2','--cpuset-cpus',cpus,'--memory','1g','--memory-swap','1g','--pids-limit','256','--user',str(os.getuid())+':'+str(os.getgid()),'--tmpfs','/tmp:rw,noexec,nosuid,size=256m','--mount','type=bind,source='+str(source)+',target=/source,readonly','--mount','type=bind,source='+str(qa)+',target=/qa,readonly','--mount','type=bind,source='+str(out)+',target=/output','--workdir','/qa/source','--entrypoint','node','sha256:f628f5688b3fafb391d8d99c9b16aee4d9162aa5aaa121c3ae340f5bc8c2a678','/qa/launch.cjs'];record['command']=command;record['container']=name
 with (p/'stdout').open('xb') as stdout,(p/'stderr').open('xb') as stderr:
  child=subprocess.Popen(command,stdin=subprocess.DEVNULL,stdout=stdout,stderr=stderr);record['dockerPid']=child.pid;record['dockerStartTicks']=pathlib.Path('/proc/'+str(child.pid)+'/stat').read_text().split(') ',1)[1].split()[19];save();deadline=time.monotonic()+360
  while child.poll() is None:
   if 'nodePid' not in record:
    probe=subprocess.run(['docker','inspect',name],stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)
    if probe.returncode==0:
     row=json.loads(probe.stdout)[0];pid=row['State']['Pid']
     if pid and pathlib.Path('/proc/'+str(pid)+'/stat').exists():record['nodePid']=pid;record['nodeStartTicks']=pathlib.Path('/proc/'+str(pid)+'/stat').read_text().split(') ',1)[1].split()[19];record['containerId']=row['Id'];save()
   if time.monotonic()>deadline:record['deadlineExceeded']=True;subprocess.run(['docker','stop','--time','2',name],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=10);break
   time.sleep(.1)
  actual=child.wait(timeout=10)
 verify();record['afterVerified']=True
except Exception as e:record['failureClassification']=type(e).__name__
finally:
 record['ownedPidsRemaining']=[record[k] for k in ['dockerPid','nodePid'] if k in record and pathlib.Path('/proc/'+str(record[k])).exists()];record['ownedContainersRemaining']=[n for n in subprocess.check_output(['docker','ps','-a','--format','{{.Names}}']).decode().splitlines() if n==name];record.update(terminal=True,actualExit=actual,completedUtc=datetime.datetime.now(datetime.timezone.utc).isoformat());save();(p/'terminal.json').write_text(json.dumps(record,indent=2)+'\n')
raise SystemExit(actual)
