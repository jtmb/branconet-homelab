#!/usr/bin/env python3
"""Read-only ingress/TLS checks and authenticated BORTUS access; no value output."""
import base64,concurrent.futures,datetime,http.client,json,pathlib,socket,ssl,subprocess
ROOT=pathlib.Path(__file__).resolve().parents[2];RUNTIME=pathlib.Path.home()/'.local/share/branconet-migration'
k=[str(RUNTIME/'bin/kubectl'),'--kubeconfig',str(RUNTIME/'admin.conf')]
ingresses=json.loads(subprocess.check_output(k+['get','ingress','-A','-o','json']))['items']
hosts=sorted({rule['host'] for obj in ingresses for rule in obj['spec'].get('rules',[])})
def request(host,path='/',body=None,cookie=None):
 public=host.endswith('.jtmb.cc') or host=='jtmb.cc'
 context=ssl.create_default_context() if public else ssl._create_unverified_context()
 with context.wrap_socket(socket.create_connection(('192.168.0.4',443),timeout=20),server_hostname=host) as connection:
  headers={'Host':host,'Connection':'close'}
  if cookie:headers['Cookie']=cookie
  if body is not None:headers.update({'Content-Type':'application/json','Content-Length':str(len(body))})
  wire=('POST' if body is not None else 'GET')+' '+path+' HTTP/1.1\r\n'+''.join(key+': '+value+'\r\n' for key,value in headers.items())+'\r\n'
  connection.sendall(wire.encode()+(body or b''));response=http.client.HTTPResponse(connection);response.begin();data=response.read()
  return response.status,data,response.headers,public
def check(host):
 try:
  status,body,headers,trusted=request(host)
  return {'host':host,'https_status':status,'bytes':len(body),'public_trusted_tls_name_chain_verified':trusted,'lan_certificate_verification_skipped':not trusted,'responding':status in [200,301,302,303,307,308,401,403]}
 except Exception as error:return {'host':host,'responding':False,'error_type':type(error).__name__}
with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:checks=list(pool.map(check,hosts))
access=json.loads(subprocess.check_output(k+['get','secret','bortus-operator-access','-n','bortus','-o','json']))
login={'username':base64.b64decode(access['data']['username']).decode(),'password':base64.b64decode(access['data']['password']).decode()}
host='bortus.branconet.lan';unauth=request(host,'/api/secrets')[0]
status,body,headers,_=request(host,'/api/auth/login',json.dumps(login).encode())
if status!=200 or unauth!=401:raise RuntimeError('BORTUS ingress auth contract failed')
cookie=headers['Set-Cookie'].split(';')[0];status,body,_,_=request(host,'/api/cluster/nodes',cookie=cookie)
nodes=json.loads(body).get('nodes',[])
if status!=200 or len(nodes)!=3 or any(n['status']!='ready' for n in nodes):raise RuntimeError('Authenticated HTTPS dashboard must show three Ready nodes')
status,body,_,_=request(host,'/api/secrets',cookie=cookie)
if status!=200:raise RuntimeError('Native Secrets HTTPS endpoint unavailable')
report={'completed_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'node':'192.168.0.4','port':443,'checks':checks,'bortus':{'host':host,'unauthenticated_401':True,'native_operator_login_passed':True,'live_ready_nodes':3,'native_secrets_endpoint_passed':True,'lan_default_certificate_untrusted':True},'secret_values_reported':False,'all_routes_responding':all(c['responding'] for c in checks)}
(ROOT/'evidence/final-routing-proof.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
