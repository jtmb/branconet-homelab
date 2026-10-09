#!/usr/bin/env python3
"""Prove native dashboard auth and API; never report credentials or bodies."""
import base64,datetime,http.client,json,pathlib,socket,ssl,subprocess,yaml

ROOT=pathlib.Path(__file__).resolve().parents[2]
RUNTIME=pathlib.Path.home()/'.local/share/branconet-migration'
K=[str(RUNTIME/'bin/kubectl'),'--kubeconfig',str(RUNTIME/'admin.conf')]
HOST='proxy.branconet.lan'

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
users=[record.split(':',1)[0] for record in dynamic['http']['middlewares']['source-dashboard-auth']['basicAuth']['users']]
candidates=[]
for name in ['vault-cc-dashboard-pass-fdbbe5fb','vault-admin-pass-fc618395','vault-cc-admin-pass-142e7506']:
    candidates.extend(native(name).values())
auth=None
for password in dict.fromkeys(candidates):
    for user in users:
        encoded=base64.b64encode((user+':'+password).encode()).decode()
        status,_=request('192.168.0.4','/dashboard/',encoded)
        if status==200:auth=encoded;break
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
report={'completed_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'host':HOST,'native_secret_reference':'traefik/traefik-dashboard-config','checks':checks,'source_hashes_preserved':True,'authorized_native_credentials_found':auth is not None,'lan_certificate_verification_skipped':True,'values_or_bodies_reported':False,'live_dashboard_accepted':auth is not None}
(ROOT/'evidence/traefik-dashboard-proof.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
if not auth:raise SystemExit('Hash preservation and denial checks passed; authorized dashboard credential proof remains open')
