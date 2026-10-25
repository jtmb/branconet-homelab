#!/usr/bin/env python3
"""Configure only the labelled controller-side maintenance builder network."""
import argparse,json,os,pathlib,re,subprocess
NAME='branconet-maintenance-build-20261025'
LABELS={'branconet.owner':'cluster-maintenance','branconet.task-id':'01a12045-bf7e-73b3-8557-752d17c72ffd'}
DOCKER=['docker','--host','unix:///var/run/docker.sock']
BASE=pathlib.Path('/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025')
assert os.getuid()==1000 and 'microsoft' in pathlib.Path('/proc/sys/kernel/osrelease').read_text().lower()
assert BASE.is_mount() and BASE.resolve()==BASE and BASE.stat().st_dev!=pathlib.Path('/').stat().st_dev
CONTROL=BASE/'network-control';CONTROL.mkdir(mode=0o700,exist_ok=True)
for name in ['tmp','home','cache','docker-config']:(CONTROL/name).mkdir(mode=0o700,exist_ok=True)
ENV={'PATH':'/usr/local/bin:/usr/bin:/bin','HOME':str(CONTROL/'home'),'DOCKER_CONFIG':str(CONTROL/'docker-config'),'TMPDIR':str(CONTROL/'tmp'),'TEMP':str(CONTROL/'tmp'),'TMP':str(CONTROL/'tmp'),'XDG_CACHE_HOME':str(CONTROL/'cache')}
def call(argv):
 r=subprocess.run(argv,env=ENV,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=30)
 if r.returncode:raise ValueError('controller_network_command_failed')
 return r.stdout
p=argparse.ArgumentParser();p.add_argument('--apply',action='store_true');a=p.parse_args()
assert os.name=='posix'
rows=[json.loads(x) for x in call(DOCKER+['network','ls','--format','json']).splitlines()]
exists=any(x['Name']==NAME for x in rows)
if not exists and not a.apply:
 print(json.dumps({'apply':False,'network':NAME,'wouldCreate':True}));raise SystemExit(0)
created=False
if not exists:
 assert subprocess.run(['ip','link','show','bn-build0'],capture_output=True).returncode!=0
 args=DOCKER+['network','create','--driver','bridge','--opt','com.docker.network.bridge.name=bn-build0','--opt','com.docker.network.bridge.enable_icc=false']
 for k,v in LABELS.items():args+=['--label',k+'='+v]
 args+=[NAME];call(args);created=True
n=json.loads(call(DOCKER+['network','inspect',NAME]));assert len(n)==1;n=n[0]
assert re.fullmatch('[0-9a-f]{64}',n['Id']) and n['Name']==NAME and n['Driver']=='bridge' and n['Scope']=='local' and n['Internal'] is False
assert n['Labels']==LABELS and n['Options']['com.docker.network.bridge.name']=='bn-build0' and n['Options']['com.docker.network.bridge.enable_icc']=='false'
assert subprocess.run(['ip','link','show','bn-build0'],capture_output=True).returncode==0
print(json.dumps({'created':created,'network':NAME,'id':n['Id'],'driver':n['Driver'],'labels':n['Labels'],'attachedContainers':len(n.get('Containers',{})),'existingNetworksChanged':False}))
