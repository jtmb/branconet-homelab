#!/usr/bin/env python3
"""Compare original xTeVe accounts/settings/mappings with its maintained successor."""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess

ROOT = Path('/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025')
OUT = ROOT / 'upstream-xteve-20261026'
OLD = 'docker.io/library/xteve-security-20261023@sha256:0ab77160ccccaf9235dcb3864624440551d6dd63c771cfaf97094db869a28656'
NEW = 'ghcr.io/volschin/threadfin:v3.4.0@sha256:79ba430d81feccaa36865cc9ecc905e5cb5d16f593965e30cb2feda128b43216'

NODE = r'''
import io,json,sys,subprocess,hashlib,hmac,tarfile,datetime,urllib.request,urllib.error,time,copy,resource,signal
resource.setrlimit(resource.RLIMIT_CORE,(0,0));signal.alarm(300)
r=json.loads(sys.stdin.buffer.read(2*1024**2+1));key=bytes.fromhex(r['key']);assert len(key)==32;phase=r['phase'];is_new=phase!='baseline'
def mac(v):return hmac.new(key,json.dumps(v,sort_keys=True,separators=(',',':')).encode(),hashlib.sha256).hexdigest()
def call(a):return subprocess.check_output(['kubectl','--request-timeout=30s','-n','plex',*a],stderr=subprocess.DEVNULL,timeout=45)
def get(k,n,ns='plex'):return json.loads(subprocess.check_output(['kubectl','--request-timeout=30s','-n',ns,'get',k,n,'-o','json'],stderr=subprocess.DEVNULL,timeout=40))
def fence():
 d=get('deployment','xteve');h=get('helmrelease','xteve','flux-system');assert d['metadata']['uid']=='52adec00-5c42-4cd2-8fb0-9428828ca368'and h['metadata']['uid']=='ace99a34-343b-40cd-b1b3-6ef2f324a8b0'
 assert d['spec']['replicas']==1 and d['status'].get('observedGeneration')==d['metadata']['generation']and all(d['status'].get(k)==1 for k in ['replicas','readyReplicas','availableReplicas','updatedReplicas']);assert h['spec']['values']['replicaCount']==1 and any(c['type']=='Ready'and c['status']=='True'for c in h['status'].get('conditions',[]))
 pods=json.loads(call(['get','pods','-l','app=xteve','-o','json']))['items'];pods=[p for p in pods if not p['metadata'].get('deletionTimestamp')];assert len(pods)==1;p=pods[0];assert p['status']['phase']=='Running'and p['spec']['nodeName']=='workernode2';statuses={s['name']:s for s in p['status']['containerStatuses']};assert all(s['ready']for s in statuses.values());main=d['spec']['template']['spec']['containers'][0];assert main['name']=='xteve'and main['image']==r['image']and main['envFrom']==[{'secretRef':{'name':'xteve-runtime'}}]
 runtime=statuses['xteve']['imageID'].rsplit('@',1)[-1];assert runtime in [r['image'].rsplit('@',1)[-1],r['amd64']]
 spec=copy.deepcopy(d['spec']);c=spec['template']['spec']['containers'][0];c['image']='<reviewed-maintained-image>';spec['template']['metadata'].get('annotations',{}).pop('maintenance.branconet.lan/restart-proof',None)
 if is_new:
  assert c['env']==[{'name':'THREADFIN_CONF','value':'/root/.xteve'}];c['env']=[];assert c['volumeMounts'][0]['subPath']==r['subPath'];del c['volumeMounts'][0]['subPath'];assert c['volumeMounts'][1]['readOnly']is True;del c['volumeMounts'][1]['readOnly'];assert len(spec['template']['spec']['containers'])==2 and len(spec['template']['spec']['initContainers'])==2
  assert spec['template']['spec']['containers'][1]['name']=='legacy-guide-routes';spec['template']['spec']['containers']=spec['template']['spec']['containers'][:1];del spec['template']['spec']['initContainers'];extra=spec['template']['spec']['volumes'][-2:];assert [v['name']for v in extra]==['guide-gateway-config','guide-gateway-temp'];spec['template']['spec']['volumes']=spec['template']['spec']['volumes'][:-2]
 else:assert len(spec['template']['spec']['containers'])==1 and not spec['template']['spec'].get('initContainers')
 if not c.get('env'):c.pop('env',None)
 storage={}
 for n,uid in [('xteve-data-0','d40f1490-7254-4599-be82-2fad35abb88b'),('xteve-data-1','b7207fe9-3768-4ad5-9ca0-ee4429137b33'),('xteve-data-3','93527524-e3c1-4e2e-a9c4-1a844743d8b1')]:
  claim=get('pvc',n);assert claim['metadata']['uid']==uid and claim['status']['phase']=='Bound';pv=get('pv',claim['spec']['volumeName']);assert pv['spec']['claimRef']['uid']==uid;storage[n]={'uid':uid,'pvUID':pv['metadata']['uid'],'spec':mac(claim['spec']),'pvSpec':mac(pv['spec'])}
 services={}
 for n in ['xteve','xteve-published']:
  s=get('service',n);ss=copy.deepcopy(s['spec'])
  for port in ss['ports']:
   if port['port']==34400:assert port['targetPort']==(34401 if is_new else 34400);port['targetPort']=34400
  services[n]={'uid':s['metadata']['uid'],'spec':mac(ss)}
 s=get('secret','xteve-runtime');assert s['metadata']['uid']=='176c57f7-b8bf-4149-87b1-95b747020c78';stable={'deployment':mac(spec),'releaseSpec':mac(h['spec']),'storage':storage,'services':services,'nativeSecret':mac({k:s.get(k)for k in ['type','immutable','data']})};return stable,{'pod':p['metadata']['name'],'podUID':p['metadata']['uid'],'imageID':runtime,'restartCount':statuses['xteve']['restartCount'],'allContainerRestarts':{n:s['restartCount']for n,s in statuses.items()}},get('service','xteve')['spec']['clusterIP']
def data(pod):
 raw=call(['exec',pod,'-c','xteve','--','tar','-cf','-','-C','/root/.xteve','settings.json','authentication.json','xepg.json','pms.json','urls.json']);assert len(raw)<=32*1024**2;files={}
 with tarfile.open(fileobj=io.BytesIO(raw))as archive:
  for member in archive:
   assert member.isfile()and member.size<=16*1024**2 and member.name not in files;files[member.name]=json.loads(archive.extractfile(member).read())
 assert set(files)=={'settings.json','authentication.json','xepg.json','pms.json','urls.json'};settings=files['settings.json'];assert settings.get('ThreadfinAutoUpdate'if is_new else'xteveAutoUpdate')is False
 normalized=copy.deepcopy(settings)
 assert settings['version']==('0.5.0'if is_new else'2.1.0')
 normalized['version']='2.1.0'  # The vendor loader renumbers this same schema to its DBVersion.
 for name in ['xteveAutoUpdate','ThreadfinAutoUpdate']:normalized.pop(name,None)
 for group in normalized.get('files',{}).values():
  for provider in group.values():
   for field in ['last.update','counter.download','counter.error','provider.availability']:provider.pop(field,None)
   compat=provider.get('compatibility',{});compat.pop('xmltv.channels',None);compat.pop('xmltv.programs',None)
 auth=files['authentication.json'];assert isinstance(auth.get('users'),dict)
 for user in auth['users'].values():user['data'].setdefault('authentication.config',False)
 mappings=files['xepg.json'];assert isinstance(mappings,dict)
 return {'settings':{k:mac(v)for k,v in normalized.items()},'settingsVersion':settings['version'],'authentication':mac(auth),'accountCount':len(auth['users']),'mappings':{mac(k):{field:mac(v)for field,v in row.items()}for k,row in mappings.items()},'activeMappings':sum(v.get('x-active')is True for v in mappings.values()),'mappingCount':len(mappings),'pms':mac(files['pms.json']),'urls':mac(files['urls.json']),'autoUpdateDisabled':True}
def http(address):
 rows={};client=urllib.request.build_opener(urllib.request.ProxyHandler({}))
 for path in ['/web/','/discover.json','/device.xml','/lineup_status.json','/lineup.json','/xmltv/xteve.xml','/xmltv/xteve.xml.gz','/m3u/xteve.m3u','/api/']:
  start=time.monotonic()
  while True:
   try:
    try:response=client.open('http://'+address+':34400'+path,timeout=15)
    except urllib.error.HTTPError as e:response=e
    with response:body=response.read(32*1024**2+1);status=response.code
    assert len(body)<=32*1024**2;break
   except OSError:
    assert time.monotonic()-start<90;time.sleep(3)
  assert status==(423 if path=='/api/'else 200),(path,status);row={'status':status,'bytes':len(body)}
  if path=='/lineup.json':lineup=json.loads(body);row['channelIdentity']=mac(sorted([{k:v for k,v in channel.items()if k!='URL'}for channel in lineup],key=lambda x:json.dumps(x,sort_keys=True)));row['channels']=len(lineup)
  if path=='/discover.json':v=json.loads(body);row['tunerIdentity']=mac({k:v.get(k)for k in ['DeviceID','DeviceAuth','TunerCount']})
  rows[path]=row
 return rows
try:
 before,writer,address=fence();observation=data(writer['pod']);routes=http(address);finish,writer2,address2=fence();assert(before,writer,address)==(finish,writer2,address2);failures=[];details={}
 if is_new:
  old=r['baseline'];assert old['passed'];previous=old['observation'];assert before==old['identity'];missing=sorted(set(previous['settings'])-set(observation['settings']));changed=sorted(k for k,v in previous['settings'].items()if observation['settings'].get(k)!=v);added=sorted(set(observation['settings'])-set(previous['settings']));assert not(set(added)-set(r['allowedNewSettings']))
  if missing or changed:failures.append('original_settings_changed');details.update(missingSettings=missing,changedSettings=changed,addedSettings=added)
  for k in ['authentication','accountCount','mappingCount','activeMappings','pms','urls']:
   if observation[k]!=previous[k]:failures.append(k+'_changed')
  if set(observation['mappings'])!=set(previous['mappings']):failures.append('mapping_identity_changed')
  differences=[]
  for ident,row in previous['mappings'].items():
   current=observation['mappings'].get(ident,{})
   if any(current.get(k)!=v for k,v in row.items()):differences.append(ident)
   assert not(set(current)-set(row)-set(r['allowedNewMappingFields']))
  if differences:failures.append('original_mapping_fields_changed');details['mappingDifferences']=differences
  for path,k in [('/lineup.json','channelIdentity'),('/discover.json','tunerIdentity')]:
   if routes[path][k]!=old['routes'][path][k]:failures.append('published_'+k+'_changed')
  if phase=='restart':assert writer['podUID']!=r['previous']['writer']['podUID']
 result={'passed':not failures,'phase':phase,'UTC':datetime.datetime.now(datetime.timezone.utc).isoformat(),'identity':before,'writer':writer,'observation':observation,'routes':routes,'failures':failures,'differences':details,'rawCredentialsProvidersOrAccountsReturned':False,'personalLoginOrProviderStreamClaimed':False,'fullGoalComplete':False}
except Exception as e:result={'passed':False,'errorType':type(e).__name__,'rawDetailsSuppressed':True,'phase':phase}
print(json.dumps(result))
'''


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('phase', choices=['baseline', 'after', 'restart'])
    p.add_argument('--receipt', type=Path, required=True)
    p.add_argument('--baseline', type=Path)
    p.add_argument('--previous', type=Path)
    p.add_argument('--state-sub-path', default='')
    a = p.parse_args()
    assert os.getuid() == 1000 and a.receipt.parent == OUT and not a.receipt.exists()
    os.umask(0o077)
    import re
    source = ROOT / 'control-source/upstream-xteve-20261026/vendor-threadfin-3.4.0/src/struct-system.go'
    text = source.read_text()
    settings = text.split('type SettingsStruct struct {', 1)[1].split('// LanguageUI', 1)[0]
    all_fields = re.findall(r'`json:"([^",]+)', text)
    request = {'phase': a.phase, 'key': (ROOT / 'acceptance-xteve-20261025/hmac-key').read_text().strip(),
               'image': OLD if a.phase == 'baseline' else NEW, 'subPath': a.state_sub_path,
               'amd64': OLD.rsplit('@', 1)[-1] if a.phase == 'baseline' else 'sha256:c08ba41338bf9660406e6528e765050c5d3b7484483b7ca34f6edbae1d37c748',
               'allowedNewSettings': re.findall(r'`json:"([^",]+)', settings), 'allowedNewMappingFields': sorted(set(all_fields))}
    if a.phase != 'baseline':
        assert a.baseline and re.fullmatch('threadfin-20261026-[a-f0-9]{12}', a.state_sub_path)
        request['baseline'] = json.loads(a.baseline.read_text())
    if a.phase == 'restart':
        assert a.previous
        request['previous'] = json.loads(a.previous.read_text())
    ssh = ['ssh', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes', '-i', '/home/brajam/.ssh/id_ed25519', '-p', '2002', 'james@192.168.0.4']
    proc = subprocess.run(ssh + [shlex.join(['python3', '-B', '-c', NODE])], input=json.dumps(request).encode(), capture_output=True, timeout=360)
    try:
        result = json.loads(proc.stdout)
    except Exception:
        result = {'passed': False, 'rawDetailsSuppressed': True, 'exitCode': proc.returncode}
    result['sourceSHA256'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    with a.receipt.open('x') as f:
        json.dump(result, f, indent=2)
        f.write('\n')
    print(json.dumps({k: result.get(k) for k in ['passed', 'phase', 'failures', 'differences', 'errorType']}))
    return int(proc.returncode != 0 or not result['passed'])


if __name__ == '__main__':
    raise SystemExit(main())
