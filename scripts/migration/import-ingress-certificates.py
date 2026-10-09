#!/usr/bin/env python3
"""Import retained ACME certificates directly into native Secrets, without Git values."""
import base64,datetime,json,pathlib,shlex,subprocess,sys
ROOT=pathlib.Path(__file__).resolve().parents[2];RUNTIME=pathlib.Path.home()/'.local/share/branconet-migration'
def main():
 password=json.load(sys.stdin)['sudo_password']
 code="import pathlib,sys,subprocess;pw=sys.stdin.read().strip();r=subprocess.run(['sudo','-S','-p','','cat','/mnt/migration-gluster-read/traefik/letsencrypt/acme.json'],input=(pw+chr(10)).encode(),capture_output=True);sys.stdout.write(r.stdout.decode());sys.stderr.write(r.stderr.decode() if r.returncode else '');sys.exit(r.returncode)"
 r=subprocess.run(['ssh','-o','BatchMode=yes','-p','2002','james@192.168.0.5','python3','-c',shlex.quote(code)],input=password,capture_output=True,text=True)
 if r.returncode:raise SystemExit('Source certificate read failed: '+r.stderr[-500:])
 store=json.loads(r.stdout)
 certificates=[cert for resolver in store.values() for cert in resolver.get('Certificates',[])]
 k=[str(RUNTIME/'bin/kubectl'),'--kubeconfig',str(RUNTIME/'admin.conf')];report=[]
 namespaces=['traefik','bortus','web-apps','plex','wordpress','ruckus','mealie','pihole','homepage','vaultwarden','whoami','website-stack','http-echo']
 for index,cert in enumerate(certificates):
  domains=[cert['domain']['main'],*cert['domain'].get('sans',[])];name='source-acme-'+str(index)
  details=subprocess.run(['openssl','x509','-noout','-enddate','-fingerprint','-sha256'],input=base64.b64decode(cert['certificate']),capture_output=True,check=True).stdout.decode().strip().splitlines()
  for ns in namespaces:
   secret={'apiVersion':'v1','kind':'Secret','metadata':{'name':name,'namespace':ns,'annotations':{'branconet.io/source':'retained-source-acme'}},'type':'kubernetes.io/tls','data':{'tls.crt':cert['certificate'],'tls.key':cert['key']}}
   existing=subprocess.run(k+['get','secret',name,'-n',ns,'--ignore-not-found','-o','json'],capture_output=True,text=True,check=True).stdout
   if existing:
    actual=json.loads(existing)
    if actual['data']!=secret['data']:raise SystemExit('Existing TLS certificate differs; review required')
   else:subprocess.run(k+['create','-f','-'],input=json.dumps(secret).encode(),capture_output=True,check=True)
  report.append({'native_secret_name':name,'namespaces':namespaces,'domains':domains,'public_certificate_details':details})
 evidence={'completed_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'certificate_count':len(report),'certificates':report,'values_reported':False,'source_acme_preserved':True}
 (ROOT/'evidence/ingress-certificates.json').write_text(json.dumps(evidence,indent=2)+'\n');print(json.dumps(evidence))
if __name__=='__main__':main()
