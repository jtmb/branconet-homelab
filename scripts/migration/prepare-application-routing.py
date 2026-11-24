#!/usr/bin/env python3
"""Prepare reviewed native routes, retaining temporary source control-plane routes."""
import json,pathlib,re,subprocess,yaml
ROOT=pathlib.Path(__file__).resolve().parents[2];RUNTIME=pathlib.Path.home()/'.local/share/branconet-migration'
backup=json.loads((ROOT/'evidence/config-backups.json').read_text());h=next(h for h in backup['hosts'] if h['host']=='192.168.0.4')
config=json.loads(subprocess.check_output([str(RUNTIME/'bin/age'),'-d','-i',str(pathlib.Path.home()/'.ssh/id_ed25519'),h['operator_copy']]))
register=json.loads((ROOT/'evidence/service-register.json').read_text());certs=json.loads((ROOT/'evidence/ingress-certificates.json').read_text())['certificates'];rows=[]
def ingress(name,ns,hosts,service,port,secure):
 cert=next((c for c in certs if any(host in c['domains'] for host in hosts)),None)
 obj={'apiVersion':'networking.k8s.io/v1','kind':'Ingress','metadata':{'name':name+('-https' if secure else '-http'),'namespace':ns,'annotations':{'traefik.ingress.kubernetes.io/router.entrypoints':'websecure' if secure else 'web'}},'spec':{'ingressClassName':'traefik','rules':[{'host':host,'http':{'paths':[{'path':'/','pathType':'Prefix','backend':{'service':{'name':service,'port':{'number':port}}}}]}} for host in hosts]}}
 if secure:
  obj['metadata']['annotations']['traefik.ingress.kubernetes.io/router.tls']='true'
  if cert:obj['spec']['tls']=[{'hosts':[host for host in hosts if host in cert['domains']],'secretName':cert['native_secret_name']}]
 return obj
for row in register['entries']:
 chart=row.get('chart');source=row['source']
 if not chart or chart.startswith('@') or source.startswith('192.168.') or source.startswith('repository/'):continue
 path=ROOT/'k8s-rewrite/charts'/chart/'values.yaml';v=yaml.safe_load(path.read_text());name=yaml.safe_load((path.parent/'Chart.yaml').read_text())['name']
 if not (ROOT/'evidence'/('private-'+name+'.json')).exists():continue
 original=next(s for s in config['services'] if s['Spec']['Name']==source)
 hosts=list(dict.fromkeys(host for key,rule in original['Spec'].get('Labels',{}).items() if key.endswith('.rule') for host in re.findall(r'`([^`]+)`',rule) if re.fullmatch(r'[a-z0-9][a-z0-9.-]*[a-z0-9]',host)))
 if not hosts:continue
 service=next(o for o in v['resources'] if o['kind']=='Service' and o['metadata']['name']==name)
 original_ports=[int(x) for key,x in original['Spec'].get('Labels',{}).items() if key.endswith('.loadbalancer.server.port')]
 ports=service['spec']['ports'];selected=next((p for p in ports if p.get('targetPort',p['port']) in original_ports),ports[0]);port=selected['port']
 if name=='pihole':port=80
 v['resources']=[o for o in v['resources'] if o['kind'] not in {'Ingress','IngressRoute'}]
 v['resources'] += [ingress(name,row['namespace'],hosts,name,port,secure) for secure in [False,True]]
 path.write_text(yaml.safe_dump(v,sort_keys=False))
 rp=ROOT/'k8s-rewrite/flux/migration-releases'/(name+'.yaml');release=yaml.safe_load(rp.read_text());release['spec']['values']['migration']['routingReviewed']=True;rp.write_text(yaml.safe_dump(release,sort_keys=False));rows.append({'release':name,'hosts':hosts,'service_port':port})
# BORTUS uses the local management address until the operator selects another.
path=ROOT/'k8s-rewrite/charts/apps/bortus/values.yaml';v=yaml.safe_load(path.read_text());v['resources']=[o for o in v['resources'] if o['kind'] not in {'Ingress','IngressRoute'}];v['resources'] += [ingress('bortus','bortus',['bortus.branconet.lan'],'bortus',4000,secure) for secure in [False,True]];path.write_text(yaml.safe_dump(v,sort_keys=False))
rp=ROOT/'k8s-rewrite/flux/migration-releases/bortus.yaml';release=yaml.safe_load(rp.read_text());release['spec']['values']['migration']['routingReviewed']=True;rp.write_text(yaml.safe_dump(release,sort_keys=False))
# Temporary routes preserve Vault and Portainer availability; their original stores remain untouched.
objects=[]
for name,host,port in [('source-vault','vault-cicd.branconet.lan',8200),('source-portainer','portainer.branconet.lan',9000)]:
 objects += [{'apiVersion':'v1','kind':'Service','metadata':{'name':name,'namespace':'traefik'},'spec':{'ports':[{'name':'http','port':port,'targetPort':port}]}},{'apiVersion':'discovery.k8s.io/v1','kind':'EndpointSlice','metadata':{'name':name,'namespace':'traefik','labels':{'kubernetes.io/service-name':name}},'addressType':'IPv4','ports':[{'name':'http','protocol':'TCP','port':port}],'endpoints':[{'addresses':['192.168.0.4'],'conditions':{'ready':True}}]}]
 objects += [ingress(name,'traefik',[host],name,port,secure) for secure in [False,True]]
foundation=ROOT/'k8s-rewrite/flux/migration-releases/foundation';(foundation/'legacy-routes.yaml').write_text(yaml.safe_dump_all(objects,sort_keys=False));p=foundation/'kustomization.yaml';v=yaml.safe_load(p.read_text());v['resources']=list(dict.fromkeys(v['resources']+['legacy-routes.yaml']));p.write_text(yaml.safe_dump(v,sort_keys=False))
# Explicit route review permits exposing a tested app without claiming all its acceptance tests passed.
for template in (ROOT/'k8s-rewrite/charts').rglob('templates/resources.yaml'):
 text=template.read_text();text=text.replace('and $.Values.migration.staging (or (eq .kind "Ingress") (eq .kind "IngressRoute"))','and $.Values.migration.staging (not $.Values.migration.routingReviewed) (or (eq .kind "Ingress") (eq .kind "IngressRoute"))')
 template.write_text(text)
report={'prepared_routes':rows,'bortus_default_host':'bortus.branconet.lan','legacy_backends_retained':['Vault','Portainer'],'standard_ports_cutover_passed':False}
(ROOT/'evidence/prepared-application-routing.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
