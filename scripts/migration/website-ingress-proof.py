#!/usr/bin/env python3
"""Verify original website hostnames/certificates/content through each new ingress node."""
import datetime,hashlib,http.client,json,pathlib,socket,ssl,yaml
ROOT=pathlib.Path(__file__).resolve().parents[2]
ctx=ssl.create_default_context();results=[]
for name,host in [('aplb','aplb.jtmb.cc'),('lucinda-art-gallery','lucinda.jtmb.cc'),('santos-web','santos.jtmb.cc'),('minecraft-website','mc.jtmb.cc')]:
 expected=json.loads((ROOT/'evidence'/('private-'+name+'.json')).read_text())['private_http']['body_sha256']
 for node in ['192.168.0.4','192.168.0.5','192.168.0.6']:
  with ctx.wrap_socket(socket.create_connection((node,30443),timeout=20),server_hostname=host) as connection:
   connection.sendall(('GET / HTTP/1.1\r\nHost: '+host+'\r\nConnection: close\r\n\r\n').encode());response=http.client.HTTPResponse(connection);response.begin();body=response.read();actual=hashlib.sha256(body).hexdigest()
   if response.status!=200 or actual!=expected:
    print(json.dumps({'release':name,'node':node,'status':response.status,'bytes':len(body),'body_matches':actual==expected,'content_type':response.getheader('Content-Type')}))
    raise SystemExit('Website routing/content mismatch for '+name+' on '+node)
   results.append({'release':name,'host':host,'node':node,'port':30443,'status':response.status,'trusted_tls_name_chain_verified':True,'body_matches_private_source_proof':True})
report={'completed_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'checks':results,'standard_80_443_cutover_accepted':False}
(ROOT/'evidence/website-ingress-proof.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
