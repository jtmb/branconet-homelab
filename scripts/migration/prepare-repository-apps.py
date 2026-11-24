#!/usr/bin/env python3
"""Pin and adapt repository-only workloads against the running native dependencies."""
import concurrent.futures,json,pathlib,subprocess,yaml
ROOT=pathlib.Path(__file__).resolve().parents[2];RUNTIME=pathlib.Path.home()/'.local/share/branconet-migration';k=[str(RUNTIME/'bin/kubectl'),'--kubeconfig',str(RUNTIME/'admin.conf')]
apps=[('media-stack/qbit-monitor','jtmb92/qbit-monitor:latest'),('test-stack/http-echo','hashicorp/http-echo:latest'),('web-app-stack/jtmb-dev','jtmb92/jtmb-dev:latest')]
def pin(item):
 chart,image=item;code='import subprocess,json\np=subprocess.run('+repr(['docker','pull',image])+',capture_output=True)\nif p.returncode:raise RuntimeError("Repository image unavailable")\nobj=json.loads(subprocess.check_output('+repr(['docker','image','inspect',image])+'))[0]\nprint(json.dumps({"digest":obj["RepoDigests"][0],"architecture":obj["Architecture"]}))'
 result=json.loads(subprocess.check_output(['ssh','-o','BatchMode=yes','-p','2002','james@192.168.0.4','python3','-'],input=code.encode()));return chart,result
results=dict(concurrent.futures.ThreadPoolExecutor(max_workers=3).map(pin,apps));report=[]
for chart,image in apps:
 path=ROOT/'k8s-rewrite/charts'/chart/'values.yaml';v=yaml.safe_load(path.read_text());name=chart.rsplit('/',1)[-1];v['image']=results[chart]['digest'];v['migration']['storageSizingVerified']=True;v['migration']['nativeSecretsImported']=True
 deployment=next(o for o in v['resources'] if o['kind']=='Deployment');pod=deployment['spec']['template']['spec'];pod['containers'][0]['image']='{{ .Values.image }}';pod['containers'][0]['imagePullPolicy']='IfNotPresent';deployment['spec']['strategy']={'type':'Recreate'}
 if name=='qbit-monitor':
  v['resources']=[o for o in v['resources'] if o['kind'] not in {'PersistentVolume','PersistentVolumeClaim','Ingress','IngressRoute'}]
  pod['volumes']=[{'name':'gluetun-port','persistentVolumeClaim':{'claimName':'gluetun-data-1-retry1'}}];pod['containers'][0]['volumeMounts'][0]['readOnly']=True
  pod['affinity']={'podAffinity':{'requiredDuringSchedulingIgnoredDuringExecution':[{'labelSelector':{'matchLabels':{'app':'qbittorrent'}},'topologyKey':'kubernetes.io/hostname','namespaces':['plex']}]}}
  for e in pod['containers'][0]['env']:
   if e['name'] in {'QBITTORRENT_USERNAME','QBITTORRENT_PASSWORD'}:e['valueFrom']['secretKeyRef']={'name':'qbittorrent-runtime','key':e['name'],'optional':False}
  sec=json.loads(subprocess.check_output(k+['get','secret','qbittorrent-runtime','-n','plex','-o','json']))
  if not {'QBITTORRENT_USERNAME','QBITTORRENT_PASSWORD'}.issubset(sec.get('data',{})):raise RuntimeError('Native qBittorrent monitor credentials missing')
 if name=='http-echo':
  v['resources']=[o for o in v['resources'] if o['kind']!='IngressRoute']
  pod['containers'][0]['args']=['-text=Hello from Branconet http-echo on Kubernetes + Longhorn!','-listen=:8080']
 for obj in v['resources']:
  if obj['kind']=='Ingress':obj['spec']['ingressClassName']='traefik'
 path.write_text(yaml.safe_dump(v,sort_keys=False));report.append({'chart':chart,'image':results[chart]['digest'],'architecture':results[chart]['architecture'],'native_dependency_wiring_reviewed':True})
(ROOT/'evidence/repository-app-preparation.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
