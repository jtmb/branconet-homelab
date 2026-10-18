import json,os,pathlib,subprocess,sys,hashlib,shlex,uuid,datetime
request=json.loads(sys.stdin.buffer.readline(8193));assert set(request)=={'sudo_password'}
password=request.pop('sudo_password');assert isinstance(password,str) and 0<len(password)<4097
rt=pathlib.Path('/home/brajam/.local/share/branconet-migration');commit='5aba82c28d5cad1d571416ea9c06f5d2d61260b3';index='sha256:bfc78b697373727aebccf50c70ef1944c76691cc435da0ad3bcc4e44670ff211'
preload=rt/'bortus-release-v2-export-20261018-v2'/('bortus-preload-'+commit)/'record.json';p=json.loads(preload.read_bytes());assert p['phase']=='completed' and len(p['nodes'])==3 and all(n['phase']=='completed' and n['runtime_manifest_digest']==index for n in p['nodes'])
owner=rt/('bortus-release-v2-cache-alias-'+uuid.uuid4().hex[:12]);owner.mkdir(mode=0o700);result={'source':commit,'runtimeIndex':index,'preloadReceiptSHA256':hashlib.sha256(preload.read_bytes()).hexdigest(),'nodes':[],'applicationDeployed':False}
remote=r"""import json,sys,subprocess,hashlib
r=json.loads(sys.stdin.readline());password=r.pop('sudo_password');assert set(r)=={'index','source'}
a=subprocess.run(['sudo','-S','-p','','-v'],input=(password+'\n').encode(),stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=20);password=None;assert a.returncode==0
ctr=['sudo','-n','/opt/containerd-k8s/bin/ctr','--address','/run/containerd-k8s/containerd.sock','--namespace','k8s.io']
def cmd(args):
 p=subprocess.run(ctr+args,capture_output=True,timeout=30);assert p.returncode==0 and len(p.stdout)<1048576 and len(p.stderr)<65536;return p.stdout
def rows():
 lines=cmd(['images','list']).decode().splitlines();assert lines and lines[0].split()[:3]==['REF','TYPE','DIGEST'];return [x.split() for x in lines[1:]]
source='bortus:release-'+r['source'];alias='docker.io/library/bortus@'+r['index'];before=rows();sources=[x for x in before if x[0] in (source,'docker.io/library/'+source)];assert len(sources)==1 and sources[0][2]==r['index'];name=sources[0][0]
raw=cmd(['content','get',r['index']]);assert 'sha256:'+hashlib.sha256(raw).hexdigest()==r['index']
existing=[x for x in before if x[0]==alias];assert len(existing)<=1 and all(x[2]==r['index'] for x in existing)
created=not existing
if created:cmd(['images','tag',name,alias])
after=rows();assert len([x for x in after if x[0]==alias and x[2]==r['index']])==1 and len([x for x in after if x[0]==name and x[2]==r['index']])==1
print(json.dumps({'sourceTag':name,'digestAlias':alias,'runtimeIndex':r['index'],'created':created,'sourceAndAliasVerified':True}))
"""
def save():
 tmp=owner/'result.tmp';tmp.write_text(json.dumps(result,indent=2)+'\n');os.replace(tmp,owner/'result.json')
save()
try:
 for host in ['192.168.0.4','192.168.0.5','192.168.0.6']:
  row={'host':host,'phase':'pending'};result['nodes'].append(row);save()
  args=['ssh','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-o','ForwardAgent=no','-p','2002','james@'+host,shlex.join(['python3','-c',remote])]
  out=subprocess.run(args,input=(json.dumps({'sudo_password':password,'source':commit,'index':index})+'\n').encode(),capture_output=True,timeout=180)
  assert out.returncode==0 and len(out.stdout)<65536 and not out.stderr
  v=json.loads(out.stdout);assert v['runtimeIndex']==index and v['sourceAndAliasVerified'];row.update(v,phase='completed');save()
 result['phase']='completed';result['actualExit']=0
except BaseException:
 result['phase']='uncertain';result['actualExit']=1
finally:
 password=None;result['observedUTC']=datetime.datetime.now(datetime.timezone.utc).isoformat();save();print(json.dumps({'owner':str(owner),'actualExit':result['actualExit'],'completedNodes':sum(n['phase']=='completed' for n in result['nodes'])}));sys.exit(result['actualExit'])
