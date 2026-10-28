#!/usr/bin/env python3
"""Qualify native ABI/module loading without starting Ruckus or mounting data."""
import json,pathlib,shlex,subprocess,time,uuid,os
SSH=['ssh','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-i','/home/brajam/.ssh/id_ed25519','-p','2002','james@192.168.0.4']
IMAGE='docker.io/library/ruckus-bot-security-20261023@sha256:5da497fc6680b06cc26f7ee94aa2d46cccfdddfbfe26ce71676be518a182262a'
CODE=r'''const assert=require('assert'),fs=require('fs'),crypto=require('crypto');
assert(process.version==='v22.23.4');
const bcrypt=require('/app/api/node_modules/bcrypt');
const sample=bcrypt.hashSync('fixture',4);assert(bcrypt.compareSync('fixture',sample));assert(!bcrypt.compareSync('other',sample));
const original=JSON.parse(fs.readFileSync('/usr/share/branconet-security/ruckus-bot/original-runtime.json'));
const addons=Object.keys(require.cache).filter(p=>p.endsWith('.node')&&p.includes('/bcrypt/'));assert(addons.length===1);
for(const p of addons)assert(crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex')===original[p].sha256);
assert(typeof require('/app/api/node_modules/mysql2').createConnection==='function');
assert(typeof require('/app/api/node_modules/express')==='function');
assert(typeof require('/app/bot/node_modules/discord.js').Client==='function');
assert(require('/app/dashboard/node_modules/next/package.json').version==='14.2.7');
console.log(JSON.stringify({passed:true,node:process.version,bcryptOriginalNativeBytes:true,bcryptPositiveNegativeComparison:true,mysqlExpressDiscordModulesLoaded:true,nextOriginalVersion:true,applicationStarted:false,credentialsLoaded:false,outboundRequests:0}));'''
def k(args,data=None):
 p=subprocess.run(SSH+[shlex.join(['kubectl','--request-timeout=30s',*args])],input=data,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=180);assert p.returncode==0,'Kubernetes fixture operation failed; raw stderr withheld';return p.stdout

def main():
 os.umask(0o077);run=uuid.uuid4().hex[:12];name='ruckus-abi-'+run;label={'branconet.net/ruckus-abi':run};owned=[]
 policy={'apiVersion':'networking.k8s.io/v1','kind':'NetworkPolicy','metadata':{'name':name,'namespace':'ruckus','labels':label},'spec':{'podSelector':{'matchLabels':label},'policyTypes':['Ingress','Egress'],'ingress':[],'egress':[]}}
 pod={'apiVersion':'v1','kind':'Pod','metadata':{'name':name,'namespace':'ruckus','labels':label},'spec':{'nodeSelector':{'kubernetes.io/hostname':'workernode2'},'restartPolicy':'Never','activeDeadlineSeconds':90,'automountServiceAccountToken':False,'enableServiceLinks':False,'securityContext':{'runAsUser':1000,'runAsGroup':1000,'runAsNonRoot':True,'seccompProfile':{'type':'RuntimeDefault'}},'containers':[{'name':'fixture','image':IMAGE,'imagePullPolicy':'Never','command':['/usr/bin/env','-i','PATH=/usr/local/bin:/usr/bin:/bin','/usr/local/bin/node','-e',CODE],'securityContext':{'allowPrivilegeEscalation':False,'readOnlyRootFilesystem':True,'capabilities':{'drop':['ALL']}},'resources':{'requests':{'cpu':'25m','memory':'32Mi'},'limits':{'cpu':'500m','memory':'256Mi'}}}]}}
 receipt={'status':'started','run':run,'image':IMAGE,'no_data_or_secret_mount':True};path=pathlib.Path('/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025/acceptance-ruckus-20261025')/('bot-abi-'+run+'.json')
 for obj in [policy,pod]:
  actual=json.loads(k(['create','-f','-','-o','json'],json.dumps(obj).encode()));owned.append({'kind':actual['kind'],'name':name,'uid':actual['metadata']['uid']})
 receipt['owned']=owned;path.write_text(json.dumps(receipt,indent=2))
 k(['-n','ruckus','wait','pod/'+name,'--for=jsonpath={.status.phase}=Succeeded','--timeout=90s']);live=json.loads(k(['-n','ruckus','get','pod',name,'-o','json']));assert live['metadata']['uid']==owned[1]['uid'] and live['status']['containerStatuses'][0]['imageID']==IMAGE and not live['spec'].get('volumes')
 result=json.loads(k(['-n','ruckus','logs',name]));assert result['passed'];receipt['result']=result
 for obj in reversed(owned):
  prefix='/api/v1/namespaces/ruckus/pods/'if obj['kind']=='Pod'else'/apis/networking.k8s.io/v1/namespaces/ruckus/networkpolicies/';current=json.loads(k(['-n','ruckus','get','pod'if obj['kind']=='Pod'else'networkpolicy',name,'-o','json']));assert current['metadata']['uid']==obj['uid']
  k(['delete','--raw',prefix+name,'-f','-'],json.dumps({'apiVersion':'v1','kind':'DeleteOptions','preconditions':{'uid':obj['uid']},'propagationPolicy':'Foreground'}).encode())
 k(['-n','ruckus','wait','pod/'+name,'--for=delete','--timeout=120s']);receipt.update(status='passed',owned_resources_deleted=True);path.write_text(json.dumps(receipt,indent=2));print(json.dumps({'status':'passed','receipt':str(path),'result':result}))
if __name__=='__main__':main()
