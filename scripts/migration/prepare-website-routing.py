#!/usr/bin/env python3
"""Prepare existing website hosts only after their complete private data checks."""
import json,pathlib,re,subprocess,yaml
ROOT=pathlib.Path(__file__).resolve().parents[2];RUNTIME=pathlib.Path.home()/'.local/share/branconet-migration'
backup=json.loads((ROOT/'evidence/config-backups.json').read_text());h=next(h for h in backup['hosts'] if h['host']=='192.168.0.4');config=json.loads(subprocess.check_output([str(RUNTIME/'bin/age'),'-d','-i',str(pathlib.Path.home()/'.ssh/id_ed25519'),h['operator_copy']]))
certificates=json.loads((ROOT/'evidence/ingress-certificates.json').read_text())['certificates']
for source,chart in [('ws_aplb','web-app-stack/aplb'),('ws_lucinda','web-app-stack/lucinda-art-gallery'),('ws_santos','web-app-stack/santos-web'),('ws_mcwebsite','apps/minecraft-website')]:
 name=chart.rsplit('/',1)[-1];proof=json.loads((ROOT/'evidence'/('private-'+name+'.json')).read_text())
 if not all(proof[k] for k in ['restart_http_passed','stable_body_verified','relocation_http_passed']):raise SystemExit('Complete private website checks required')
 service=next(s for s in config['services'] if s['Spec']['Name']==source);rules=[v for k,v in service['Spec'].get('Labels',{}).items() if k.endswith('.rule')]
 hosts=[host for rule in rules for host in re.findall(r'`([^`]+)`',rule)];cert=next(c for c in certificates if any(host in c['domains'] for host in hosts))
 path=ROOT/'k8s-rewrite/charts'/chart/'values.yaml';values=yaml.safe_load(path.read_text());values['resources']=[o for o in values['resources'] if o['kind']!='Ingress']
 values['resources'].append({'apiVersion':'networking.k8s.io/v1','kind':'Ingress','metadata':{'name':name,'namespace':'web-apps','annotations':{'traefik.ingress.kubernetes.io/router.tls':'true','traefik.ingress.kubernetes.io/router.entrypoints':'websecure'}},'spec':{'ingressClassName':'traefik','tls':[{'hosts':[h for h in hosts if h in cert['domains']],'secretName':cert['native_secret_name']}],'rules':[{'host':host,'http':{'paths':[{'path':'/','pathType':'Prefix','backend':{'service':{'name':name,'port':{'number':80}}}}]}} for host in hosts]}})
 path.write_text(yaml.safe_dump(values,sort_keys=False))
 release_path=ROOT/'k8s-rewrite/flux/migration-releases'/(name+'.yaml');release=yaml.safe_load(release_path.read_text());release['spec']['suspend']=False;release['spec']['values']={'enabled':True,'replicaCount':1,'migration':{'verified':True,'staging':False}};release_path.write_text(yaml.safe_dump(release,sort_keys=False))
 print(json.dumps({'chart':chart,'existing_hosts':hosts,'native_tls_secret':cert['native_secret_name'],'standard_ports_cutover_accepted':False}))
