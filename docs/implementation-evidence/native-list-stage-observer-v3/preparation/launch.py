import argparse,datetime,hashlib,importlib.util,json,os,pathlib,re,subprocess,tarfile,time
IMAGE='sha256:f628f5688b3fafb391d8d99c9b16aee4d9162aa5aaa121c3ae340f5bc8c2a678'
SOURCES={'baseline':'51e8cd66379c1f40a95ea02f4da7c8aed848f2a4','candidate':'15786222e4b01b0692ad9aebab99b8734b505c7b'}
parser=argparse.ArgumentParser();parser.add_argument('--repository',type=pathlib.Path,required=True);parser.add_argument('--exporter',type=pathlib.Path,required=True);parser.add_argument('--owner',required=True);args=parser.parse_args()
assert re.fullmatch('native-stage-[a-z0-9-]{8,80}',args.owner) and os.name=='posix'
assert {0,1,2,3}.issubset(os.sched_getaffinity(0))
HERE=pathlib.Path(__file__).resolve().parent;WORK=pathlib.Path.home()/'.cache/bortus-controlled-perf'/args.owner
assert WORK.is_dir() and not (WORK/'record.json').exists()
os.umask(0o077)
sha=lambda data:hashlib.sha256(data).hexdigest()
spec=importlib.util.spec_from_file_location('exact_export',args.exporter);exporter=importlib.util.module_from_spec(spec);spec.loader.exec_module(exporter)
assert exporter.git(args.exporter.parents[1],'show','a82a6cb9e244b0ec05489bc7251f3e29411c64dc:scripts/export_bortus_source.py')==args.exporter.read_bytes()
driver_manifest=json.loads((HERE/'driver/manifest.json').read_bytes());assert sha((HERE/'driver/native-stage-driver.mjs').read_bytes())==driver_manifest['derived_sha256']
record={'owner':args.owner,'launcher_pid':os.getpid(),'scope':'One instrumented baseline/candidate diagnostic pair; never acceptance','sources':{},'steps':[],'measurements':[],'image':IMAGE,'driver_manifest':driver_manifest,'passed':False,'terminal':False}
def save():
 temporary=WORK/'record.json.next';temporary.write_text(json.dumps(record,indent=2)+'\n');temporary.replace(WORK/'record.json')
def unchanged(folder,manifest):return all((folder/name).is_file() and sha((folder/name).read_bytes())==digest for name,digest in manifest.items())
def step(name,command,timeout):
 start=time.perf_counter();print(json.dumps({'phase':name,'state':'started'}),flush=True)
 try:
  result=subprocess.run(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=timeout);code=result.returncode;out=result.stdout;err=result.stderr
 except subprocess.TimeoutExpired as error:
  code=124;out=error.stdout or b'';err=error.stderr or b''
  if '--name' in command:
   owned=command[command.index('--name')+1]
   assert owned.startswith('bortus-native-stage-') and owned.endswith(args.owner)
   subprocess.run(['docker','stop','--time','5',owned],stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=15)
 (WORK/(name+'.stdout')).write_bytes(out);(WORK/(name+'.stderr')).write_bytes(err)
 item={'phase':name,'exit_code':code,'elapsed_seconds':round(time.perf_counter()-start,3)};record['steps'].append(item);save();print(json.dumps(item),flush=True)
 if code:raise RuntimeError('Protected diagnostic phase failed')
 return out
try:
 inspect=json.loads(step('inspect-image',['docker','inspect',IMAGE],30));assert inspect[0]['Id']==IMAGE
 for label,commit in SOURCES.items():
  bound=HERE/('baseline-v3-51e8cd6' if label=='baseline' else 'candidate-v2-15786222');manifest=json.loads((bound/'manifest.json').read_bytes());assert manifest['commit']==commit
  archive=WORK/(label+'-original.tar.gz');info=exporter.export(args.repository,commit,archive,False);folder=WORK/label;folder.mkdir(mode=0o700)
  with tarfile.open(archive) as source:
   for member in source:assert member.isfile() and (folder/member.name).resolve().is_relative_to(folder.resolve())
   source.extractall(folder,filter='data')
  original={str(file.relative_to(folder)):sha(file.read_bytes()) for file in folder.rglob('*') if file.is_file()}
  expected=dict(original)
  for name,digest in manifest['instrumented_source_sha256'].items():
   assert original[name]==manifest['original_source_sha256'][name] and sha((bound/name).read_bytes())==digest
   (folder/name).write_bytes((bound/name).read_bytes());expected[name]=digest
  record['sources'][label]={'commit':commit,'export':{key:value for key,value in info.items() if key!='output'},'archive_sha256':sha(archive.read_bytes()),'original_manifest':original,'instrumented_manifest':expected,'binding_manifest':manifest};save()
  assert unchanged(folder,expected)
  name='bortus-native-stage-build-'+label+'-'+args.owner
  command=['docker','run','--rm','--pull','never','--name',name,'--cpus','4','--cpuset-cpus','0-3','--memory','4g','--memory-swap','4g','--pids-limit','256','--user',str(os.getuid())+':'+str(os.getgid()),'--mount','type=bind,src='+str(folder)+',dst=/app','--workdir','/app','-e','NEXT_TELEMETRY_DISABLED=1','-e','DATABASE_URL=file:/tmp/native-stage-build.db','-e','CIRCLE_NODE_TOTAL=4','--entrypoint','bash',IMAGE,'-lc','npm ci && npm run build']
  step('build-'+label,command,900);assert unchanged(folder,expected)
 for label,commit in SOURCES.items():
  folder=WORK/label;results=WORK/(label+'-results');results.mkdir(mode=0o700)
  assert unchanged(folder,record['sources'][label]['instrumented_manifest'])
  command=['docker','run','--rm','--pull','never','--network','none','--name','bortus-native-stage-runtime-'+label+'-'+args.owner,'--cpus','2','--cpuset-cpus','0-1','--memory','1g','--memory-swap','1g','--pids-limit','256','--user',str(os.getuid())+':'+str(os.getgid()),'--mount','type=bind,src='+str(folder)+',dst=/app,readonly','--mount','type=bind,src='+str(HERE)+',dst=/diagnostic,readonly','--mount','type=bind,src='+str(results)+',dst=/results','--workdir','/app','-e','BORTUS_PERF_LABEL='+label,'-e','BORTUS_PERF_RUN=1','-e','BORTUS_NATIVE_DIAGNOSTIC_SOURCE='+commit,'--entrypoint','node',IMAGE,'/diagnostic/driver/native-stage-driver.mjs']
  step('runtime-'+label,command,600);assert unchanged(folder,record['sources'][label]['instrumented_manifest'])
  raw=json.loads((results/(label+'-run-1.json')).read_bytes());assert raw['passed'] and raw['diagnostic_only'] and raw['source_commit']==commit
  record['measurements'].append({'label':label,'raw_file':str(results/(label+'-run-1.json'))});save()
 record['passed']=True
except Exception as error:record['failure_kind']=type(error).__name__;raise
finally:
 names=subprocess.run(['docker','ps','--format','{{.Names}}'],stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=15)
 record['owned_live_containers']=[name for name in names.stdout.decode().splitlines() if name.startswith('bortus-native-stage-') and name.endswith(args.owner)]
 record['terminal']=True;record['finished_at_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat();save()
