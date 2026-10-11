
import pathlib,os,json,subprocess,time,datetime,hashlib
work=pathlib.Path(__file__).resolve().parent; inp=work/'input'; out=work/'output'; out.mkdir(mode=0o700)
name='bortus-selected-batch-'+work.name; image='sha256:f628f5688b3fafb391d8d99c9b16aee4d9162aa5aaa121c3ae340f5bc8c2a678'
manifest=json.loads((work/'dispatch-manifest.json').read_bytes())
record={'owner':work.name,'supervisorPid':os.getpid(),'supervisorStartTicks':pathlib.Path('/proc/self/stat').read_text().split(') ',1)[1].split()[19],'startedUtc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'inputManifest':manifest,'container':name,'productionCalls':False,'stages':[]}
def save():
 p=work/'record.next';p.write_text(json.dumps(record,indent=2)+'\n');p.replace(work/'record.json')
def unchanged():
 assert all(hashlib.sha256((inp/n).read_bytes()).hexdigest()==d for n,d in manifest.items())
actual=1
try:
 unchanged(); assert json.loads(subprocess.check_output(['docker','inspect',image]))[0]['Id']==image
 cpus=','.join(map(str,sorted(os.sched_getaffinity(0))[:2])); record['cpuAffinity']=cpus
 command=['docker','run','--rm','--pull','never','--name',name,'--network','none','--read-only','--cpus','2','--cpuset-cpus',cpus,'--memory','1g','--memory-swap','1g','--pids-limit','256','--user',str(os.getuid())+':'+str(os.getgid()),'--tmpfs','/tmp:rw,noexec,nosuid,size=64m','--mount','type=bind,source='+str(inp)+',target=/input,readonly','--mount','type=bind,source='+str(inp/'typescript')+',target=/typescript,readonly','--mount','type=bind,source='+str(out)+',target=/output','--entrypoint','node',image,'--expose-gc','/input/diagnostic.cjs']; record['command']=command
 with (work/'stdout').open('xb') as stdout,(work/'stderr').open('xb') as stderr:
  child=subprocess.Popen(command,stdin=subprocess.DEVNULL,stdout=stdout,stderr=stderr);record['dockerCliPid']=child.pid;record['dockerCliStartTicks']=pathlib.Path('/proc/'+str(child.pid)+'/stat').read_text().split(') ',1)[1].split()[19];save();deadline=time.monotonic()+60
  while child.poll() is None:
   if 'nodeHostPid' not in record:
    probe=subprocess.run(['docker','inspect',name],stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)
    if probe.returncode==0:
     row=json.loads(probe.stdout)[0]; pid=row['State']['Pid']
     if pid and pathlib.Path('/proc/'+str(pid)+'/stat').exists():record['nodeHostPid']=pid;record['nodeStartTicks']=pathlib.Path('/proc/'+str(pid)+'/stat').read_text().split(') ',1)[1].split()[19];record['containerId']=row['Id'];save()
   if time.monotonic()>deadline:
    record['deadlineExceeded']=True;subprocess.run(['docker','stop','--time','1',name],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=10);break
   time.sleep(.1)
  actual=child.wait(timeout=10)
 unchanged()
except Exception as e:record['failureClassification']=type(e).__name__
finally:
 names=subprocess.check_output(['docker','ps','-a','--format','{{.Names}}']).decode().splitlines();record['ownedContainersRemaining']=[n for n in names if n==name]
 record['ownedPidsRemaining']=[record[k] for k in ['dockerCliPid','nodeHostPid'] if k in record and pathlib.Path('/proc/'+str(record[k])).exists()]
 record.update(actualExit=actual,terminal=True,terminalUtc=datetime.datetime.now(datetime.timezone.utc).isoformat(),outputs={str(p.relative_to(work)):hashlib.sha256(p.read_bytes()).hexdigest() for p in out.rglob('*') if p.is_file()});save();(work/'terminal.json').write_text(json.dumps(record,indent=2)+'\n')
raise SystemExit(actual)
