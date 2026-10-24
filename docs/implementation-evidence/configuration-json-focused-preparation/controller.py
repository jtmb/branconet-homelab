import pathlib,subprocess,json,os,time,re,hashlib,sys
os.umask(0o077);mode=sys.argv[1];assert mode in ['pristine','old-parse','save-noop','remove-noop'];root=pathlib.Path('/home/brajam/.local/share/branconet-migration/configuration-json-focused-20261015-v1');assert pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip()=='19d54e89-533f-46e2-b89d-25657251c8d7'and os.getuid()==1000
start=root/'started.json'
if not start.exists():
 with start.open('x')as f:json.dump(dict(boot='19d54e89-533f-46e2-b89d-25657251c8d7',started=time.monotonic(),absolute=time.monotonic()+240),f)
started=json.loads(start.read_bytes());assert started['boot']=='19d54e89-533f-46e2-b89d-25657251c8d7';absolute=started['absolute'];assert time.monotonic()<absolute-20
out=root/mode;out.mkdir(mode=0o700);name='bortus-configuration-json-focused-20261015-v1-'+mode;docker='/usr/bin/docker';assert hashlib.sha256(pathlib.Path(docker).read_bytes()).hexdigest()=='018f1a3d2dacf73614077ded6d05d2b9954630627a3722f1f19e46f5c973cec6'
def command(args,seconds=10):
 result=subprocess.run([docker,*args],capture_output=True,timeout=max(.1,min(seconds,absolute-time.monotonic())));return result
prior=command(['container','ls','-aq','--filter','name=^/'+name+'$']);assert prior.returncode==0 and not prior.stdout.strip()
rows=json.loads((root/'manifest.json').read_bytes())
for row in rows:assert hashlib.sha256((root/'source'/row['path']).read_bytes()).hexdigest()==row['sha256']
args=['create','--pull','never','--name',name,'--cidfile',str(out/'container.cid'),'--label','bortus.configuration-json-focused=20261015-v1','--network','none','--read-only','--cap-drop','ALL','--security-opt','no-new-privileges','--cpus','2','--memory','1g','--memory-swap','1g','--pids-limit','256','--user','1000:1000','--tmpfs','/tmp:rw,exec,nosuid,nodev,size=134217728,mode=1777','--mount','type=bind,source='+str(root/'source')+',target=/source,readonly','--mount','type=bind,source=/home/brajam/.cache/bortus-controlled-perf/flux-argv-full-20261015-v1/source/node_modules,target=/deps/node_modules,readonly','--mount','type=bind,source='+str(root)+',target=/producer,readonly','--mount','type=bind,source='+str(out)+',target=/output','--env','HOME=/tmp','--env','DATABASE_URL=file:/tmp/unused-fixture.db','--env','NEXT_TELEMETRY_DISABLED=1','--env','NODE_ENV=test','--entrypoint','node','node@sha256:c4d5523090a817b7aa86d2111241fdd4f66d1e27782b44160e6aa63b357ecb2d','/producer/run.cjs',mode]
(root/(mode+'-intent.json')).write_text(json.dumps(dict(args=args,seconds=240,child=30,closure=20))+'\n');cid=None;primary=None;cleanup=None
try:
 create=command(args);(out/'create.stdout').write_bytes(create.stdout);(out/'create.stderr').write_bytes(create.stderr);assert create.returncode==0
 cid=(out/'container.cid').read_text().strip();assert re.fullmatch('[a-f0-9]{64}',cid)and create.stdout.strip().decode()==cid
 inspect=command(['inspect',cid]);assert inspect.returncode==0;d=json.loads(inspect.stdout)[0];(out/'created-inspect.json').write_bytes(inspect.stdout);assert d['Id']==cid and d['Name']=='/'+name and d['Config']['Labels']['bortus.configuration-json-focused']=='20261015-v1'and d['HostConfig']['NetworkMode']=='none'and d['HostConfig']['ReadonlyRootfs']and d['HostConfig']['NanoCpus']==2000000000 and d['HostConfig']['Memory']==d['HostConfig']['MemorySwap']==1073741824
 attach=command(['start','--attach',cid],40);(out/'attach.stdout').write_bytes(attach.stdout);(out/'attach.stderr').write_bytes(attach.stderr);assert attach.returncode==0
 inspect=command(['inspect',cid]);d=json.loads(inspect.stdout)[0];(out/'completed-inspect.json').write_bytes(inspect.stdout);assert not d['State']['Running']and d['State']['ExitCode']==0
except BaseException as e:primary=dict(type=type(e).__name__)
finally:
 if cid:
  remove=command(['rm','-f',cid]);cleanup=dict(actualExit=remove.returncode);(out/'remove.stdout').write_bytes(remove.stdout);(out/'remove.stderr').write_bytes(remove.stderr)
  check=command(['inspect','--format','{{.Id}}',cid]);checkname=command(['container','ls','-aq','--filter','name=^/'+name+'$']);cleanup.update(exactCIDAbsent=check.returncode!=0 and not check.stdout.strip(),exactNameAbsent=checkname.returncode==0 and not checkname.stdout.strip())
 for row in rows:assert hashlib.sha256((root/'source'/row['path']).read_bytes()).hexdigest()==row['sha256']
 result=dict(mode=mode,actualExit=0 if primary is None and cleanup and cleanup['actualExit']==0 and cleanup['exactCIDAbsent']and cleanup['exactNameAbsent']else 1,primary=primary,cleanup=cleanup,confirmedOwnedCID=cid,createUncertain=cid is None,sourceUnchanged=True,oldCorpusReplayed=False)
 (out/'outer-terminal.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result));raise SystemExit(result['actualExit'])
