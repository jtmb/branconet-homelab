#!/usr/bin/env python3
import base64,json,pathlib,subprocess,yaml
ROOT=pathlib.Path(__file__).resolve().parents[2];RUNTIME=pathlib.Path.home()/'.local/share/branconet-migration'
k=[str(RUNTIME/'bin/kubectl'),'--kubeconfig',str(RUNTIME/'admin.conf')]
s=json.loads(subprocess.check_output(k+['get','secret','whoami-launch','-n','whoami','-o','json']))
args=[base64.b64decode(s['data'][key]).decode() for key in sorted(s['data'])]
ports=[]
for index,arg in enumerate(args):
 if arg in ['-port','--port']:ports.append(int(args[index+1]))
 elif arg.startswith(('-port=','--port=')):ports.append(int(arg.split('=',1)[1]))
if ports!=[2001]:raise SystemExit('Source listener evidence differs: '+str(ports))
path=ROOT/'k8s-rewrite/charts/test-stack/whoami/values.yaml';values=yaml.safe_load(path.read_text());deployment=next(o for o in values['resources'] if o['kind']=='Deployment')
deployment['spec']['template']['spec']['containers'][0]['ports'][0]['containerPort']=2001
next(o for o in values['resources'] if o['kind']=='Service')['spec']['ports'][0]['targetPort']=2001
path.write_text(yaml.safe_dump(values,sort_keys=False));print(json.dumps({'verified_source_listener':2001,'service_target_fixed':True}))
