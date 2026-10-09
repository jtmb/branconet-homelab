#!/usr/bin/env python3
"""Probe xTeve discovery on real LAN interfaces; retain baseline and report metadata only."""
import argparse
import concurrent.futures,datetime,json,pathlib,subprocess
r=pathlib.Path.home()/'.local/share/branconet-migration';k=[str(r/'bin/kubectl'),'--kubeconfig',str(r/'admin.conf')]
pod=json.loads(subprocess.check_output(k+['get','pods','-n','plex','-l','app=xteve','-o','json']))['items'][0]
def inspect(host):
 code=r'''import json,socket,time,urllib.parse
host=HOST
pod=POD
results=[]
for destination,label in [('239.255.255.250','lan_multicast'),(pod,'pod_unicast')]:
 sock=socket.socket(socket.AF_INET,socket.SOCK_DGRAM,socket.IPPROTO_UDP);sock.bind((host,0));sock.setsockopt(socket.IPPROTO_IP,socket.IP_MULTICAST_IF,socket.inet_aton(host));sock.setsockopt(socket.IPPROTO_IP,socket.IP_MULTICAST_TTL,2);sock.settimeout(.5)
 query=b'M-SEARCH * HTTP/1.1\r\nHOST: 239.255.255.250:1900\r\nMAN: "ssdp:discover"\r\nMX: 1\r\nST: ssdp:all\r\n\r\n'
 sock.sendto(query,(destination,1900));deadline=time.monotonic()+3;matches=[];count=0
 while time.monotonic()<deadline:
  try:data,address=sock.recvfrom(65535)
  except socket.timeout:continue
  count+=1;headers={}
  for line in data.decode(errors='replace').splitlines()[1:]:
   if ':' in line:
    key,value=line.split(':',1);headers[key.lower().strip()]=value.strip()
  location=urllib.parse.urlsplit(headers.get('location',''))
  if location.port==34400:matches.append({'responder':address[0],'location_host':location.hostname,'location_port':location.port,'http_response':data.startswith(b'HTTP/1.1 200')})
 sock.close();results.append({'probe':label,'responses':count,'xteve_matches':matches})
print(json.dumps(results))
'''.replace('HOST',repr(host),1).replace('POD',repr(pod['status']['podIP']),1)
 result=subprocess.run(['ssh','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-p','2002','james@'+host,'python3','-'],input=code.encode(),capture_output=True,timeout=15)
 if result.returncode:raise RuntimeError('SSDP query failed; response details withheld')
 return {'node':host,'checks':json.loads(result.stdout)}
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:checks=list(pool.map(inspect,['192.168.0.4','192.168.0.5','192.168.0.6']))
report={'checked_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'host_network':pod['spec'].get('hostNetwork',False),'checks':checks,'application_configuration_changed':False}

import hashlib,urllib.request
root=pathlib.Path(__file__).resolve().parents[2]
path=root/'evidence/xteve-ssdp-proof.json'
parser=argparse.ArgumentParser();parser.add_argument('--phase',choices=['before','after'],default='after');args=parser.parse_args()
proof=json.loads(path.read_text()) if path.exists() else {}
claims=json.loads(subprocess.check_output(k+['get','pvc','-n','plex','-o','json']))['items']
with urllib.request.urlopen('http://192.168.0.4:34400/discover.json',timeout=10) as response:discovery=json.loads(response.read())
report['storage_and_identity']={'claims':[{'name':p['metadata']['name'],'uid':p['metadata']['uid'],'volume':p['spec'].get('volumeName')} for p in claims if p['metadata']['name'].startswith('xteve-')],'device_identity_sha256':hashlib.sha256(str(discovery.get('DeviceID')).encode()).hexdigest(),'tuner_count':discovery.get('TunerCount')}
if args.phase=='before' and proof.get('before'):raise RuntimeError('Existing baseline must not be overwritten')
proof[args.phase]=report
if args.phase=='after':
 if not proof.get('before'):raise RuntimeError('Original baseline required before acceptance')
 proof['claims_and_identity_preserved']=report['storage_and_identity']==proof['before']['storage_and_identity']
 proof['lan_discovery_passed']=report['host_network'] and all(any(match['responder']==pod['status']['podIP'] and match['location_host']==pod['status']['podIP'] and match['http_response'] for check in node['checks'] if check['probe']=='lan_multicast' for match in check['xteve_matches']) for node in report['checks'])
proof['values_or_settings_reported']=False
path.write_text(json.dumps(proof,indent=2)+'\n')
print(json.dumps({'phase':args.phase,'lan_discovery_passed':proof.get('lan_discovery_passed',False),'claims_and_identity_preserved':proof.get('claims_and_identity_preserved'),'report':report}))
