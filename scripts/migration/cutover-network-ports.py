#!/usr/bin/env python3
"""Move reviewed ingress/DNS ports with encrypted source specifications and rollback."""
import base64,datetime,hashlib,http.client,io,json,pathlib,shlex,socket,ssl,struct,subprocess,time
ROOT=pathlib.Path(__file__).resolve().parents[2];RUNTIME=pathlib.Path.home()/'.local/share/branconet-migration';NODES=['192.168.0.4','192.168.0.5','192.168.0.6']
k=[str(RUNTIME/'bin/kubectl'),'--kubeconfig',str(RUNTIME/'admin.conf')]
def run(args):return subprocess.run(k+args,capture_output=True,check=True).stdout
def remote(code):return subprocess.check_output(['ssh','-o','BatchMode=yes','-p','2002','james@192.168.0.4','python3','-'],input=code.encode())
def docker(args):return remote('import subprocess,sys\nr=subprocess.run('+repr(['docker']+args)+',capture_output=True)\nif r.returncode:raise RuntimeError("Docker port operation failed")\nsys.stdout.buffer.write(r.stdout)')
if not json.loads((ROOT/'evidence/native-dns-proof.json').read_text())['all_passed']:raise RuntimeError('Native DNS checks required')
if len(json.loads((ROOT/'evidence/website-ingress-proof.json').read_text())['checks'])!=12:raise RuntimeError('Website ingress checks required')
for host in NODES:
 if not json.loads((ROOT/'evidence'/('traefik-log-backup-'+host+'.json')).read_text())['authenticated_recovery_equal']:raise RuntimeError('Source logs not protected')
ingresses=json.loads(run(['get','ingress','-A','-o','json']))['items'];hosts={rule['host'] for obj in ingresses for rule in obj['spec'].get('rules',[])}
required={'bortus.branconet.lan','homepage.branconet.lan','jtmb.cc','media.jtmb.cc','pi.branconet.lan','vault-cicd.branconet.lan','portainer.branconet.lan'}
if not required.issubset(hosts):raise RuntimeError('Validated application routes not all deployed')
source=json.loads(docker(['service','inspect','proxy_traefik','pi_pihole']));original={s['Spec']['Name']:s for s in source}
original_services={ns:json.loads(run(['get','svc',name,'-n',ns,'-o','json'])) for ns,name in [('traefik','traefik'),('pihole','pihole')]}
raw=json.dumps({'source_services':source,'kubernetes_services':original_services}).encode();recipient=(pathlib.Path.home()/'.ssh/id_ed25519.pub').read_text().strip();encrypted=subprocess.check_output([str(RUNTIME/'bin/age'),'-r',recipient],input=raw)
stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ');target=RUNTIME/'recovery'/('network-port-rollback-'+stamp+'.json.age');target.write_bytes(encrypted);target.chmod(0o600)
if subprocess.check_output([str(RUNTIME/'bin/age'),'-d','-i',str(pathlib.Path.home()/'.ssh/id_ed25519'),str(target)])!=raw:raise RuntimeError('Rollback authentication failed')
nas='/mnt/container-backups/k8s-migration-20261009/'+target.name
writer='import pathlib,sys;pathlib.Path('+repr(nas)+').write_bytes(sys.stdin.buffer.read())';subprocess.run(['ssh','-p','2002','james@192.168.0.4','python3','-c',shlex.quote(writer)],input=encrypted,capture_output=True,check=True)
changed=[];checks=[]
try:
 for name in ['proxy_traefik','pi_pihole']:
  ports=original[name]['Spec'].get('EndpointSpec',{}).get('Ports',[]);args=['service','update','--detach','--replicas','0']
  for port in ports:args+=['--publish-rm',str(port['TargetPort'])+'/'+port['Protocol']]
  docker(args+[name]);changed.append(name)
 for ns,name in [('traefik','traefik'),('pihole','pihole')]:
  patch={'spec':{'externalIPs':NODES}}
  if ns=='pihole':patch['spec']['ports']=original_services[ns]['spec']['ports']+[{'name':'legacy-admin','port':8079,'targetPort':80,'protocol':'TCP'}]
  run(['patch','svc',name,'-n',ns,'--type=merge','-p',json.dumps(patch)])
 time.sleep(4)
 # Repeated trusted requests allow removal of old routing-mesh rules to settle.
 for node in NODES:
  for name,host in [('aplb','aplb.jtmb.cc'),('lucinda-art-gallery','lucinda.jtmb.cc'),('santos-web','santos.jtmb.cc'),('minecraft-website','mc.jtmb.cc')]:
   expected=json.loads((ROOT/'evidence'/('private-'+name+'.json')).read_text())['private_http']['body_sha256'];passed=False
   for attempt in range(20):
    try:
     with ssl.create_default_context().wrap_socket(socket.create_connection((node,443),timeout=5),server_hostname=host) as connection:
      connection.sendall(('GET / HTTP/1.1\r\nHost: '+host+'\r\nConnection: close\r\n\r\n').encode());response=http.client.HTTPResponse(connection);response.begin();body=response.read();passed=response.status==200 and hashlib.sha256(body).hexdigest()==expected
     if passed:break
    except Exception:pass
    time.sleep(1)
   if not passed:raise RuntimeError('Standard HTTPS routing failed for '+name+' on '+node)
   checks.append({'node':node,'host':host,'port':443,'trusted_tls':True,'body_equal':True})
 subprocess.run([__import__('sys').executable,str(ROOT/'scripts/migration/check-source-dns.py')],capture_output=True,check=True)
 dns=json.loads((ROOT/'evidence/source-dns.json').read_text())
 if not dns['all_passed']:raise RuntimeError('Standard DNS ports failed')
 report={'completed_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'source_ports_removed':changed,'source_services_retained':True,'original_data_retained':True,'standard_https_checks':checks,'three_node_udp_tcp_dns_passed':True,'rollback_operator_copy':str(target),'rollback_nas_copy':nas,'all_passed':True}
 (ROOT/'evidence/network-port-cutover.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
except Exception:
 for ns,name in [('traefik','traefik'),('pihole','pihole')]:
  spec=original_services[ns]['spec'];run(['patch','svc',name,'-n',ns,'--type=merge','-p',json.dumps({'spec':{'externalIPs':spec.get('externalIPs',[]),'ports':spec['ports']}})])
 for name in changed:
  s=original[name]['Spec'];args=['service','update','--detach','--replicas',str(s['Mode']['Replicated']['Replicas'])]
  for port in s.get('EndpointSpec',{}).get('Ports',[]):args += ['--publish-add','published='+str(port['PublishedPort'])+',target='+str(port['TargetPort'])+',protocol='+port['Protocol']+',mode='+port.get('PublishMode','ingress')]
  docker(args+[name])
 raise
