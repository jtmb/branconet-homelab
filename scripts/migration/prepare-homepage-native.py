#!/usr/bin/env python3
"""Preserve Homepage configuration while replacing its Docker dependency."""
import json,pathlib,subprocess,yaml,shlex,base64,copy
ROOT=pathlib.Path(__file__).resolve().parents[2];RUNTIME=pathlib.Path.home()/'.local/share/branconet-migration'
k=[str(RUNTIME/'bin/kubectl'),'--kubeconfig',str(RUNTIME/'admin.conf')]
remote="import pathlib,json;p=pathlib.Path('/mnt/migration-gluster-read/homepage/app');print(json.dumps({f:(p/f).read_text() for f in ['services.yaml','widgets.yaml','docker.yaml'] if (p/f).exists()}))"
original=json.loads(subprocess.check_output(['ssh','-o','BatchMode=yes','-p','2002','james@192.168.0.5','python3','-c',shlex.quote(remote)]))
docker_names=set((yaml.safe_load(original.pop('docker.yaml','{}')) or {}).keys())
def strip_docker(obj,legacy=False):
 if isinstance(obj,dict):
  if legacy or 'container' in obj or obj.get('server') in docker_names:
   for key in ['server','container','docker']:obj.pop(key,None)
  for value in obj.values():strip_docker(value,legacy)
 elif isinstance(obj,list):
  for value in obj:strip_docker(value,legacy)
data={'kubernetes.yaml':'mode: cluster\ningress: true\n','docker.yaml':'{}\n'}
legacy_data=dict(data)
for filename,text in original.items():
 obj=yaml.safe_load(text);old=copy.deepcopy(obj);strip_docker(old,True);legacy_data[filename]=yaml.safe_dump(old,sort_keys=False)
 strip_docker(obj);data[filename]=yaml.safe_dump(obj,sort_keys=False)
secret={'apiVersion':'v1','kind':'Secret','metadata':{'name':'homepage-rendered-config','namespace':'homepage'},'type':'Opaque','stringData':data}
existing=subprocess.run(k+['get','secret','homepage-rendered-config','-n','homepage','--ignore-not-found','-o','json'],capture_output=True,text=True,check=True).stdout
if existing:
 actual=json.loads(existing)
 actual_data={key:base64.b64decode(value).decode() for key,value in actual['data'].items()}
 if actual_data!=data:
  if actual_data!=legacy_data:raise SystemExit('Existing generated configuration differs; review required')
  actual.pop('data',None);actual['stringData']=data
  subprocess.run(k+['replace','-f','-'],input=json.dumps(actual).encode(),capture_output=True,check=True)
else:subprocess.run(k+['create','-f','-'],input=json.dumps(secret).encode(),capture_output=True,check=True)
path=ROOT/'k8s-rewrite/charts/homepage/values.yaml';values=yaml.safe_load(path.read_text());deployment=next(o for o in values['resources'] if o['kind']=='Deployment');pod=deployment['spec']['template']['spec'];container=pod['containers'][0]
pod['volumes']=[v for v in pod['volumes'] if v['name']!='data-0'];pod['nodeSelector']={};container['volumeMounts']=[v for v in container['volumeMounts'] if v['name']!='data-0']
pod['serviceAccountName']='homepage';pod['volumes'].append({'name':'native-config','secret':{'secretName':'homepage-rendered-config'}})
for filename in data:container['volumeMounts'].append({'name':'native-config','mountPath':'/app/config/'+filename,'subPath':filename,'readOnly':True})
values['migration']['hostDockerDependencies']=[]
values['resources']=[o for o in values['resources'] if not (o['kind']=='ServiceAccount' and o['metadata']['name']=='homepage') and not (o['kind'] in ['ClusterRole','ClusterRoleBinding'] and o['metadata']['name']=='homepage-read')]
values['resources'] += [
 {'apiVersion':'v1','kind':'ServiceAccount','metadata':{'name':'homepage','namespace':'homepage'}},
 {'apiVersion':'rbac.authorization.k8s.io/v1','kind':'ClusterRole','metadata':{'name':'homepage-read'},'rules':[{'apiGroups':[''],'resources':['namespaces','pods','nodes'],'verbs':['get','list','watch']},{'apiGroups':['networking.k8s.io'],'resources':['ingresses'],'verbs':['get','list','watch']},{'apiGroups':['metrics.k8s.io'],'resources':['nodes','pods'],'verbs':['get','list']}]},
 {'apiVersion':'rbac.authorization.k8s.io/v1','kind':'ClusterRoleBinding','metadata':{'name':'homepage-read'},'roleRef':{'apiGroup':'rbac.authorization.k8s.io','kind':'ClusterRole','name':'homepage-read'},'subjects':[{'kind':'ServiceAccount','name':'homepage','namespace':'homepage'}]},
]
path.write_text(yaml.safe_dump(values,sort_keys=False));print(json.dumps({'configuration_files':list(data),'native_secret':'homepage/homepage-rendered-config','docker_socket_removed':True,'source_configuration_preserved':True}))
