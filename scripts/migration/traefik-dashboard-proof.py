#!/usr/bin/env python3
"""Prove native dashboard auth and API; never report credentials or bodies."""
import argparse,base64,datetime,http.client,json,pathlib,socket,ssl,subprocess,sys,yaml

ROOT=pathlib.Path(__file__).resolve().parents[2]
RUNTIME=pathlib.Path.home()/'.local/share/branconet-migration'
K=[str(RUNTIME/'bin/kubectl'),'--kubeconfig',str(RUNTIME/'admin.conf')]
HOST='proxy.branconet.lan'
parser=argparse.ArgumentParser()
parser.add_argument('--credentials-stdin',action='store_true',help='Receive additional existing passwords in memory through protected stdin')
options=parser.parse_args()

def native(name,namespace='bortus-secrets'):
    d=json.loads(subprocess.check_output(K+['get','secret',name,'-n',namespace,'-o','json']))
    return {key:base64.b64decode(value).decode() for key,value in d['data'].items()}

def request(node,path,auth=None):
    with ssl._create_unverified_context().wrap_socket(socket.create_connection((node,443),timeout=15),server_hostname=HOST) as connection:
        headers='GET '+path+' HTTP/1.1\r\nHost: '+HOST+'\r\nConnection: close\r\n'
        if auth:headers+='Authorization: Basic '+auth+'\r\n'
        connection.sendall((headers+'\r\n').encode());response=http.client.HTTPResponse(connection);response.begin();body=response.read()
        return response.status,body

dynamic=yaml.safe_load(native('traefik-dashboard-config','traefik')['dashboard.yaml'])
backup=json.loads((ROOT/'evidence/config-backups.json').read_text())
host=next(h for h in backup['hosts'] if h['host']=='192.168.0.4')
original=json.loads(subprocess.check_output([str(RUNTIME/'bin/age'),'-d','-i',str(pathlib.Path.home()/'.ssh/id_ed25519'),host['operator_copy']]))
source=next(s['Spec'] for s in original['services'] if s['Spec']['Name']=='proxy_traefik')
expected_users=source['Labels']['traefik.http.middlewares.dashboard-auth.basicauth.users'].split(',')
if dynamic['http']['middlewares']['source-dashboard-auth']['basicAuth']['users']!=expected_users:raise RuntimeError('Native auth hashes differ from retained source')
users=[record.split(':',1)[0] for record in dynamic['http']['middlewares']['source-dashboard-auth']['basicAuth']['users']]
candidates=[]
for name in ['vault-cc-dashboard-pass-fdbbe5fb','vault-admin-pass-fc618395','vault-cc-admin-pass-142e7506']:
    candidates.extend(native(name).values())
native_candidates=set(candidates)
if options.credentials_stdin:candidates.extend(json.load(sys.stdin)['passwords'])
auth=None
credential_source=None
for password in dict.fromkeys(candidates):
    for user in users:
        encoded=base64.b64encode((user+':'+password).encode()).decode()
        status,_=request('192.168.0.4','/dashboard/',encoded)
        if status==200:
            auth=encoded;credential_source='native Secrets' if password in native_candidates else 'protected stdin existing credential';break
    if auth:break
checks=[]
invalid=base64.b64encode(b'migration-invalid:no-valid-credential').decode()
for node in ['192.168.0.4','192.168.0.5','192.168.0.6']:
    denied,_=request(node,'/dashboard/');wrong,_=request(node,'/api/http/routers',invalid)
    if denied!=401 or wrong!=401:raise RuntimeError('Dashboard authentication protection failed')
    row={'node':node,'unauthenticated_denied':True,'invalid_credentials_denied':True,'authorized_dashboard_passed':False,'authorized_live_router_api_passed':False}
    if auth:
        status,html=request(node,'/dashboard/',auth);api_status,body=request(node,'/api/http/routers',auth)
        routers=json.loads(body) if api_status==200 else []
        row.update({'authorized_dashboard_passed':status==200 and b'<html' in html.lower(),'authorized_live_router_api_passed':api_status==200 and any(r.get('name')=='source-dashboard@file' for r in routers) and any(r.get('provider')=='kubernetes' for r in routers),'live_router_count':len(routers)})
        if not row['authorized_dashboard_passed'] or not row['authorized_live_router_api_passed']:raise RuntimeError('Authorized dashboard/API content failed')
    checks.append(row)
deployment=json.loads(subprocess.check_output(K+['get','deployment','traefik','-n','traefik','-o','json']))
source_image=source['TaskTemplate']['ContainerSpec']['Image']
if deployment['spec']['template']['spec']['containers'][0]['image']!=source_image:raise RuntimeError('Native Traefik does not use the immutable source image')
pods=json.loads(subprocess.check_output(K+['get','pods','-n','traefik','-l','app=traefik','-o','json']))['items']
image_ids=sorted(set(c['imageID'] for p in pods if not p['metadata'].get('deletionTimestamp') for c in p.get('status',{}).get('containerStatuses',[])))
native_read=subprocess.check_output(K+['auth','can-i','get','secrets','-n','traefik','--as=system:serviceaccount:bortus:bortus']).decode().strip()=='yes'
if not native_read or deployment['status'].get('availableReplicas',0)!=2:raise RuntimeError('Native Secret access or both ingress replicas unavailable')
report={'completed_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'host':HOST,'native_secret_reference':'traefik/traefik-dashboard-config','checks':checks,'source_hashes_preserved':True,'immutable_source_image_preserved':True,'authorized_existing_credentials_found':auth is not None,'credential_source':credential_source,'lan_certificate_verification_skipped':True,'values_or_bodies_reported':False,'live_dashboard_accepted':auth is not None}
report.update({'actual_pod_image_ids':image_ids,'available_ingress_replicas':2,'bortus_native_secret_read_allowed':True})
(ROOT/'evidence/traefik-dashboard-proof.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
if not auth:raise SystemExit('Hash preservation and denial checks passed; authorized dashboard credential proof remains open')
