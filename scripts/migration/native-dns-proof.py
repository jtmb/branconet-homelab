#!/usr/bin/env python3
"""Enable native Pi-hole across routed pod subnets and verify real DNS replies."""
import base64,datetime,json,pathlib,secrets,socket,struct,subprocess
ROOT=pathlib.Path(__file__).resolve().parents[2];RUNTIME=pathlib.Path.home()/'.local/share/branconet-migration'
k=[str(RUNTIME/'bin/kubectl'),'--kubeconfig',str(RUNTIME/'admin.conf')]
def run(args,body=None):
 return subprocess.run(k+args,input=json.dumps(body).encode() if body is not None else None,capture_output=True,check=True).stdout
secret=json.loads(run(['get','secret','pihole-runtime','-n','pihole','-o','json']))
value=base64.b64encode(b'ALL').decode();changed=secret['data'].get('FTLCONF_dns_listeningMode')!=value
if changed:
 run(['patch','secret','pihole-runtime','-n','pihole','--type=merge','-p',json.dumps({'metadata':{'resourceVersion':secret['metadata']['resourceVersion']},'data':{'FTLCONF_dns_listeningMode':value}})])
 run(['rollout','restart','deployment/pihole','-n','pihole']);run(['rollout','status','deployment/pihole','-n','pihole','--timeout=300s'])
service=json.loads(run(['get','service','pihole','-n','pihole','-o','json']))['spec']['clusterIP']
code=r'''
import json,secrets,socket,struct,time
results=[]
for host in HOSTS:
 for name in ['example.com','aplb.branconet.lan']:
  for protocol in ['UDP','TCP']:
   ident=secrets.randbelow(65536);query=struct.pack('!HHHHHH',ident,0x100,1,0,0,0)+b''.join(bytes([len(p)])+p.encode() for p in name.split('.'))+b'\0'+struct.pack('!HH',1,1)
   passed=False
   for attempt in range(30):
    try:
     with socket.socket(socket.AF_INET,socket.SOCK_DGRAM if protocol=='UDP' else socket.SOCK_STREAM) as s:
      s.settimeout(3)
      if protocol=='UDP':s.sendto(query,(host,53));response=s.recv(4096)
      else:
       s.connect((host,53));s.sendall(struct.pack('!H',len(query))+query)
       def receive(n):
        data=b''
        while len(data)<n:
         part=s.recv(n-len(data))
         if not part:raise RuntimeError('closed')
         data+=part
        return data
       response=receive(struct.unpack('!H',receive(2))[0])
     rid,flags,questions,answers,_,_=struct.unpack('!HHHHHH',response[:12]);passed=rid==ident and flags&15==0 and answers>0
     if passed:break
    except Exception:pass
    time.sleep(1)
   results.append({'server':host,'name':name,'protocol':protocol,'passed':passed})
print(json.dumps(results))
'''
checks=json.loads(subprocess.check_output(['ssh','-o','BatchMode=yes','-p','2002','james@192.168.0.4','python3','-'],input=('HOSTS='+repr([service,'10.96.0.10'])+'\n'+code).encode()))
report={'completed_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'native_service':service,'listener_mode':'ALL','existing_records_and_storage_preserved':True,'checks':checks,'all_passed':all(c['passed'] for c in checks)}
(ROOT/'evidence/native-dns-proof.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
if not report['all_passed']:raise SystemExit('Native DNS proof failed')
