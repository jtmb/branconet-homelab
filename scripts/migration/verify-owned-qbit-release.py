#!/usr/bin/env python3
"""Observe a source-backed monitor rollout without exposing credentials or sending messages."""
import argparse, datetime, json, shlex, subprocess
from pathlib import Path
IMAGE='docker.io/jtmb92/qbit-monitor:git-f365b49bad13eab9d5e7083ecebeb4db2cc9fa69@sha256:397c69f6b04bd0ae328c48c3f492795d73fbbc2e19da10b5ae3a08619914b1fe'
PROGRAM=r"""import json,sys,subprocess,datetime,time,ipaddress,http.client
request=json.load(sys.stdin);before=request['before'];previous=request.get('previous');image=request['image']
def need(ok,reason):
 if not ok:raise ValueError(reason)
def get(kind,name,ns='plex'):
 return json.loads(subprocess.check_output(['kubectl','-n',ns,'get',kind,name,'-o','json'],timeout=25))
def pods(label):
 return [p for p in json.loads(subprocess.check_output(['kubectl','-n','plex','get','pods','-l',label,'-o','json']))['items']if not p['metadata'].get('deletionTimestamp')]
start=time.monotonic();seen=None
while time.monotonic()-start<240:
 ps=pods('app=qbit-monitor')
 if len(ps)==1 and ps[0]['status'].get('phase')=='Running' and ps[0]['metadata']['uid'] != before['pod']['uid'] and (not previous or ps[0]['metadata']['uid'] != previous['monitorPodUID']):
  p=ps[0];status=p['status'].get('containerStatuses',[])
  if len(status)==1 and status[0]['ready'] and status[0]['imageID'].endswith(image.split('@')[1]):
   raw=subprocess.check_output(['kubectl','-n','plex','logs',p['metadata']['name'],'--tail=1000','--limit-bytes=2097152'],timeout=25).decode(errors='replace')
   cycles=raw.count('Torrents Validated.');login='Login successful'in raw;forward='listen_port updated'in raw or'Port is unchanged. No update needed.'in raw
   no_failures=not any(x in raw for x in ['Login failed','Unable to retrieve torrent state','Permission denied'])
   if cycles>=2 and login and forward and no_failures:seen=(p,status[0],cycles);break
 time.sleep(5)
need(seen is not None,'real_queue_login_forwarding_not_proven');p,status,cycles=seen;name=p['metadata']['name'];need(status['restartCount']==0,'unexpected_container_restart')
d=get('deployment','qbit-monitor');need(d['metadata']['uid']==before['deployment']['uid'],'deployment_uid_changed');spec=json.loads(json.dumps(d['spec']));need(spec['template']['spec']['containers'][0]['image']==image,'exact_image_missing');spec['template']['spec']['containers'][0]['image']=before['deployment']['spec']['template']['spec']['containers'][0]['image']
annotations=spec['template']['metadata'].get('annotations',{});annotations.pop('branconet.io/owned-monitor-restart',None)
if not annotations:spec['template']['metadata'].pop('annotations',None)
need(spec==before['deployment']['spec'],'unreviewed_monitor_spec_change');need(p['metadata']['uid']!=before['pod']['uid'],'original_pod_not_replaced')
if previous:need(p['metadata']['uid']!=previous['monitorPodUID'],'independent_restart_not_observed')
for a in before['claims']:
 x=get('pvc',a['name']);v=get('pv',a['pvName']);need(x['metadata']['uid']==a['uid'] and v['metadata']['uid']==a['pvUID'] and x['spec']==a['pvcSpec'] and v['spec']==a['pvSpec'] and x['status']['phase']=='Bound','storage_identity_or_wiring_changed')
for a in before['secrets']:
 z=subprocess.check_output(['kubectl','-n','plex','get','secret',a['name'],'-o','jsonpath={.metadata.uid}:{.metadata.resourceVersion}:{.type}']).decode().split(':');need(z==[a['uid'],a['resourceVersion'],a['type']],'native_secret_changed')
for a in before['files']:
 digest=subprocess.check_output(['kubectl','-n','plex','exec',name,'--','sha256sum','/app/'+a['path']]).decode().split()[0];need(digest==a['sha256'],'accepted_script_bytes_changed')
a=before['notificationState'];z=subprocess.check_output(['kubectl','-n','plex','exec',name,'--','stat','-c','%u:%g:%a:%s','/app/state/notified_torrents.txt']).decode().strip().split(':');need(z[:3]==[str(a['uid']),str(a['gid']),a['mode']] and a['bytes']<=int(z[3])<=1024**2,'notification_state_metadata_changed')
digest=subprocess.check_output(['kubectl','-n','plex','exec',name,'--','sh','-c','head -c '+str(a['bytes'])+' /app/state/notified_torrents.txt | sha256sum']).decode().split()[0];need(digest==a['sha256'],'original_notification_bytes_changed');qp=pods('app=qbittorrent');need(len(qp)==1 and qp[0]['metadata']['uid']==before['qbitPodUID'],'qbit_unexpectedly_restarted')
service=get('service','qbittorrent');host=service['spec']['clusterIP'];need(ipaddress.ip_address(host).is_private,'unexpected_api_destination');c=http.client.HTTPConnection(host,8112,timeout=5);c.request('GET','/api/v2/app/preferences',headers={'Referer':'http://'+host+':8112'});response=c.getresponse();response.read(65536);need(response.status in [401,403],'unauthenticated_api_not_denied');c.close()
print(json.dumps({'passed':True,'UTC':datetime.datetime.now(datetime.timezone.utc).isoformat(),'monitorPodUID':p['metadata']['uid'],'exactImage':image,'runtimeImageID':status['imageID'],'realQueueCycles':cycles,'nativeLoginSeen':True,'forwardedPortIntegrationSeen':True,'allNineAcceptedScriptHashesPreserved':True,'nativeSecretsAndStorageUnchanged':True,'originalNotificationBytesPreserved':a['bytes'],'currentNotificationBytes':int(z[3]),'qbitPodUnchanged':True,'allAlertConfigurationUnchanged':True,'unauthenticatedAPIDenied':True,'manualNotificationsSent':False,'independentRestart':bool(previous),'rawLogsReturned':False,'browserAcceptance':False}))
"""
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--baseline',required=True,type=Path);p.add_argument('--receipt',required=True,type=Path);p.add_argument('--previous',type=Path);a=p.parse_args()
 root=Path('/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025');out=a.receipt
 if out.exists() or root not in out.resolve().parents:raise ValueError('new_owned_receipt_required')
 request={'before':json.loads(a.baseline.read_bytes()),'previous':json.loads(a.previous.read_bytes())if a.previous else None,'image':IMAGE}
 cmd=['ssh','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-i','/home/brajam/.ssh/id_ed25519','-p','2002','james@192.168.0.4',shlex.join(['python3','-B','-c',PROGRAM])]
 r=subprocess.run(cmd,input=json.dumps(request).encode(),capture_output=True,timeout=300)
 if r.returncode:raise ValueError('live_observer_failed:'+r.stderr.decode(errors='replace').splitlines()[-1][:200])
 result=json.loads(r.stdout)
 with out.open('x') as f:json.dump(result,f,indent=2);f.write('\n')
 print(json.dumps(result));return 0
if __name__=='__main__':raise SystemExit(main())
