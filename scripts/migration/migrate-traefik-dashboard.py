#!/usr/bin/env python3
"""Restore the inspected HTTPS/BasicAuth dashboard using a native Secret.

Secret values remain in memory and the Kubernetes API; only deployment references
and metadata are written to the repository. Run before enabling the file provider.
"""
import base64,datetime,json,pathlib,subprocess,yaml

ROOT=pathlib.Path(__file__).resolve().parents[2]
RUNTIME=pathlib.Path.home()/'.local/share/branconet-migration'
K=[str(RUNTIME/'bin/kubectl'),'--kubeconfig',str(RUNTIME/'admin.conf')]
backup=json.loads((ROOT/'evidence/config-backups.json').read_text())
host=next(h for h in backup['hosts'] if h['host']=='192.168.0.4')
source=json.loads(subprocess.check_output([str(RUNTIME/'bin/age'),'-d','-i',str(pathlib.Path.home()/'.ssh/id_ed25519'),host['operator_copy']]))
original=next(s for s in source['services'] if s['Spec']['Name']=='proxy_traefik')['Spec']
labels=original['Labels'];rule=labels['traefik.http.routers.dashboard.rule']
if rule!='Host(`proxy.branconet.lan`)' or labels['traefik.http.routers.dashboard.entrypoints']!='websecure' or labels['traefik.http.routers.dashboard.service']!='api@internal':
    raise RuntimeError('Source dashboard routing changed; review before migration')
users=labels['traefik.http.middlewares.dashboard-auth.basicauth.users'].split(',')
if not users or any(':' not in value or '$' not in value for value in users):
    raise RuntimeError('Source BasicAuth records are not valid hash records')
dynamic={'http':{'routers':{'source-dashboard':{'rule':rule,'entryPoints':['websecure'],'service':'api@internal','middlewares':['source-dashboard-auth'],'tls':{}}},'middlewares':{'source-dashboard-auth':{'basicAuth':{'users':users}}}}}
secret={'apiVersion':'v1','kind':'Secret','metadata':{'name':'traefik-dashboard-config','namespace':'traefik','annotations':{'branconet.io/source':'retained proxy_traefik BasicAuth and dashboard rule'}},'type':'Opaque','data':{'dashboard.yaml':base64.b64encode(yaml.safe_dump(dynamic,sort_keys=False).encode()).decode()}}
existing=subprocess.check_output(K+['get','secret','traefik-dashboard-config','-n','traefik','--ignore-not-found','-o','json'])
if existing:
    if json.loads(existing)['data']!=secret['data']:raise RuntimeError('Native dashboard config conflict; do not overwrite')
else:subprocess.run(K+['create','-f','-'],input=json.dumps(secret).encode(),capture_output=True,check=True)
actual=json.loads(subprocess.check_output(K+['get','secret','traefik-dashboard-config','-n','traefik','-o','json']))
if actual['data']!=secret['data']:raise RuntimeError('Native dashboard config readback differs')
# Capture the already-deployed foundation spec, excluding API/default/status fields.
deployed=json.loads(subprocess.check_output(K+['get','deployment','traefik','-n','traefik','-o','json']))
spec=deployed['spec'];container=spec['template']['spec']['containers'][0]
for flag in ['--api.dashboard=true','--providers.file.directory=/etc/traefik/dynamic','--providers.file.watch=true']:
    if flag not in container['args']:container['args'].append(flag)
if any(arg.startswith('--api.insecure') for arg in container['args']):raise RuntimeError('Unexpected insecure API flag')
container['volumeMounts']=[m for m in container.get('volumeMounts',[]) if m['name']!='dashboard-config']+[{'name':'dashboard-config','mountPath':'/etc/traefik/dynamic','readOnly':True}]
pod=spec['template']['spec'];pod['volumes']=[v for v in pod.get('volumes',[]) if v['name']!='dashboard-config']+[{'name':'dashboard-config','secret':{'secretName':'traefik-dashboard-config'}}]
spec['template']['metadata'].pop('creationTimestamp',None)
deployment={'apiVersion':'apps/v1','kind':'Deployment','metadata':{'name':'traefik','namespace':'traefik'},'spec':spec}
foundation=ROOT/'k8s-rewrite/flux/migration-releases/foundation'
(foundation/'ingress-deployment.yaml').write_text(yaml.safe_dump(deployment,sort_keys=False))
path=foundation/'kustomization.yaml';composition=yaml.safe_load(path.read_text());composition['resources']=list(dict.fromkeys(composition['resources']+['ingress-deployment.yaml']));path.write_text(yaml.safe_dump(composition,sort_keys=False))
report={'prepared_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'host':'proxy.branconet.lan','source':'proxy_traefik','native_secret':'traefik/traefik-dashboard-config','source_auth_hashes_readback_equal':True,'users':len(users),'https_only':True,'insecure_api_enabled':False,'values_reported':False,'live_dashboard_accepted':False,'source_configuration_retained':True}
(ROOT/'evidence/traefik-dashboard-preparation.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report))
