#!/usr/bin/env python3
"""Record proven port ownership, separating DNS exposure from ingress port 80."""
import copy,json,pathlib,subprocess,yaml
ROOT=pathlib.Path(__file__).resolve().parents[2];RUNTIME=pathlib.Path.home()/'.local/share/branconet-migration';k=[str(RUNTIME/'bin/kubectl'),'--kubeconfig',str(RUNTIME/'admin.conf')];nodes=['192.168.0.4','192.168.0.5','192.168.0.6']
if not json.loads((ROOT/'evidence/network-port-cutover.json').read_text())['all_passed']:raise RuntimeError('Port proof required')
path=ROOT/'k8s-rewrite/charts/apps/pihole/values.yaml';v=yaml.safe_load(path.read_text());svc=next(o for o in v['resources'] if o['kind']=='Service' and o['metadata']['name']=='pihole');svc['spec'].pop('externalIPs',None);svc['spec']['ports']=[p for p in svc['spec']['ports'] if p['port']!=8079]
public=copy.deepcopy(svc);public['metadata']['name']='pihole-public';public['spec']['externalIPs']=nodes;public['spec']['ports']=[p for p in public['spec']['ports'] if p['port']==53]+[{'name':'legacy-admin','port':8079,'targetPort':80,'protocol':'TCP'}]
v['resources']=[o for o in v['resources'] if not(o['kind']=='Service' and o['metadata']['name']=='pihole-public')]+[public];path.write_text(yaml.safe_dump(v,sort_keys=False))
live=copy.deepcopy(public);live['metadata']['labels']={'app.kubernetes.io/managed-by':'Helm'};live['metadata']['annotations']={'meta.helm.sh/release-name':'pihole','meta.helm.sh/release-namespace':'pihole'}
subprocess.run(k+['apply','-f','-'],input=yaml.safe_dump(live).encode(),capture_output=True,check=True)
subprocess.run(k+['patch','service','pihole','-n','pihole','--type=merge','-p',json.dumps({'spec':{'externalIPs':None,'ports':svc['spec']['ports']}})],capture_output=True,check=True)
# Public Plex ports preserve the former addresses while one backend moves between workers.
path=ROOT/'k8s-rewrite/charts/media-stack/plex/values.yaml';v=yaml.safe_load(path.read_text());svc=next(o for o in v['resources'] if o['kind']=='Service' and o['metadata']['name']=='plex');svc['spec']['externalIPs']=nodes;path.write_text(yaml.safe_dump(v,sort_keys=False))
rp=ROOT/'k8s-rewrite/flux/migration-releases/plex.yaml';v=yaml.safe_load(rp.read_text());v['spec']['values']['migration']['routingReviewed']=True;rp.write_text(yaml.safe_dump(v,sort_keys=False))
subprocess.run(k+['patch','service','plex','-n','plex','--type=merge','-p',json.dumps({'spec':{'externalIPs':nodes}})],capture_output=True,check=True)
for template in (ROOT/'k8s-rewrite/charts').rglob('templates/resources.yaml'):
 text=template.read_text();needle='{{- range .Values.resources }}'
 if 'unset .spec "externalIPs"' not in text:text=text.replace(needle,needle+'\n{{- if and (eq .kind "Service") $.Values.migration.staging (not $.Values.migration.routingReviewed) }}\n{{- $_ := unset .spec "externalIPs" }}\n{{- end }}')
 template.write_text(text)
foundation=ROOT/'k8s-rewrite/flux/migration-releases/foundation';service=json.loads(subprocess.check_output(k+['get','svc','traefik','-n','traefik','-o','json']));obj={'apiVersion':'v1','kind':'Service','metadata':{'name':'traefik','namespace':'traefik'},'spec':{key:service['spec'][key] for key in ['type','selector','ports','externalIPs']}}
(foundation/'ingress-service.yaml').write_text(yaml.safe_dump(obj,sort_keys=False));p=foundation/'kustomization.yaml';v=yaml.safe_load(p.read_text());v['resources']=list(dict.fromkeys(v['resources']+['ingress-service.yaml']));p.write_text(yaml.safe_dump(v,sort_keys=False))
print(json.dumps({'dns_public_service':'pihole/pihole-public','dns_and_ingress_port80_separated':True,'plex_existing_addresses_preserved':nodes}))
